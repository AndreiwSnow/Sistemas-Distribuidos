import hashlib
import json
import logging
import os
import time
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
RESPONSE_GENERATOR_URL = os.getenv("RESPONSE_GENERATOR_URL", "http://localhost:8001")
METRICS_URL = os.getenv("METRICS_URL", "http://localhost:8003")
TTL = int(os.getenv("TTL", 60))

redis_client: aioredis.Redis = None
http_client: httpx.AsyncClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, http_client
    redis_client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    http_client = httpx.AsyncClient(timeout=30.0)
    logger.info("Caché iniciado. Redis: %s:%s | TTL: %ss", REDIS_HOST, REDIS_PORT, TTL)
    yield
    await redis_client.aclose()
    await http_client.aclose()


app = FastAPI(title="Cache Service", lifespan=lifespan)

class QueryRequest(BaseModel):
    query_type: str
    zone_id: str
    confidence_min: float = 0.0
    zone_id_b: str = ""
    bins: int = 5

def build_cache_key(req: QueryRequest) -> str:
    """
    Construye una clave de caché legible y determinista según la tarea:
      Q1: count:{zone_id}:conf={confidence_min}
      Q2: area:{zone_id}:conf={confidence_min}
      Q3: density:{zone_id}:conf={confidence_min}
      Q4: compare:density:{zone_a}:{zone_b}:conf={confidence_min}
      Q5: confidence_dist:{zone_id}:bins={bins}
    """
    prefix_map = {
        "Q1": f"count:{req.zone_id}:conf={req.confidence_min}",
        "Q2": f"area:{req.zone_id}:conf={req.confidence_min}",
        "Q3": f"density:{req.zone_id}:conf={req.confidence_min}",
        "Q4": f"compare:density:{req.zone_id}:{req.zone_id_b}:conf={req.confidence_min}",
        "Q5": f"confidence_dist:{req.zone_id}:bins={req.bins}",
    }
    return prefix_map.get(req.query_type, f"unknown:{hashlib.md5(str(req).encode()).hexdigest()}")


async def record_metric(event: str, cache_key: str, latency_ms: float, extra: dict = None):
    payload = {
        "event": event,
        "cache_key": cache_key,
        "latency_ms": latency_ms,
        **(extra or {}),
    }
    try:
        await http_client.post(f"{METRICS_URL}/record", json=payload, timeout=2.0)
    except Exception:
        pass

@app.get("/health")
async def health():
    try:
        await redis_client.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {"status": "ok", "redis": redis_ok, "ttl": TTL}


@app.post("/query")
async def handle_query(req: QueryRequest):
    cache_key = build_cache_key(req)
    t_start = time.perf_counter()

   
    cached = await redis_client.get(cache_key)
    if cached is not None:
        latency_ms = (time.perf_counter() - t_start) * 1000
        await record_metric("hit", cache_key, latency_ms)
        logger.debug("HIT  %s (%.2f ms)", cache_key, latency_ms)
        return {"source": "cache", "cache_key": cache_key,
                "result": json.loads(cached), "latency_ms": round(latency_ms, 3)}

    try:
        resp = await http_client.post(
            f"{RESPONSE_GENERATOR_URL}/query",
            json=req.model_dump(),
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error en generador de respuestas: {e}")

    data = resp.json()
    result = data["result"]

    await redis_client.setex(cache_key, TTL, json.dumps(result))

    latency_ms = (time.perf_counter() - t_start) * 1000
    await record_metric(
        "miss", cache_key, latency_ms,
        {"processing_time_ms": data.get("processing_time_ms", 0)},
    )
    logger.debug("MISS %s (%.2f ms)", cache_key, latency_ms)

    return {"source": "generator", "cache_key": cache_key,
            "result": result, "latency_ms": round(latency_ms, 3)}
