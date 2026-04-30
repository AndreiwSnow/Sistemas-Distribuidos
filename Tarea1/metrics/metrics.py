import asyncio
import logging
import os
import sqlite3
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Optional
 
import redis.asyncio as aioredis
from fastapi import FastAPI
from pydantic import BaseModel
 
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
 
DB_PATH = os.getenv("DB_PATH", "/metrics/metrics.db")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
EVICTION_POLL_INTERVAL = int(os.getenv("EVICTION_POLL_INTERVAL", 15))
 
 
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                ts                 REAL NOT NULL,
                event              TEXT NOT NULL,
                cache_key          TEXT NOT NULL,
                latency_ms         REAL NOT NULL,
                processing_time_ms REAL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS eviction_samples (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ts              REAL NOT NULL,
                total_evictions INTEGER NOT NULL,
                delta_evictions INTEGER NOT NULL,
                eviction_rate   REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ts              REAL NOT NULL,
                distribution    TEXT,
                total_requests  INTEGER,
                elapsed_s       REAL,
                hits            INTEGER,
                misses          INTEGER,
                errors          INTEGER,
                eviction_rate   REAL DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_event ON events(event)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ts    ON events(ts)")
 
 
@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
 
 
_last_evictions = 0
_last_poll_ts = 0.0
 
 
async def poll_evictions(redis_client: aioredis.Redis):
    global _last_evictions, _last_poll_ts
    while True:
        await asyncio.sleep(EVICTION_POLL_INTERVAL)
        try:
            info = await redis_client.info("stats")
            total_evictions = int(info.get("evicted_keys", 0))
            now = time.time()
            delta = total_evictions - _last_evictions
            elapsed = now - _last_poll_ts if _last_poll_ts else EVICTION_POLL_INTERVAL
            rate_per_min = (delta / elapsed) * 60 if elapsed > 0 else 0
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO eviction_samples (ts, total_evictions, delta_evictions, eviction_rate) "
                    "VALUES (?, ?, ?, ?)",
                    (now, total_evictions, delta, rate_per_min),
                )
            if delta > 0:
                logger.info("Evictions: +%d (total=%d, rate=%.1f/min)", delta, total_evictions, rate_per_min)
            _last_evictions = total_evictions
            _last_poll_ts = now
        except Exception as e:
            logger.warning("Error consultando Redis: %s", e)
 
 
redis_client: aioredis.Redis = None
 
 
@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    init_db()
    redis_client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    asyncio.create_task(poll_evictions(redis_client))
    logger.info("Metricas iniciadas. DB: %s | Redis: %s:%s", DB_PATH, REDIS_HOST, REDIS_PORT)
    yield
    await redis_client.aclose()
 
 
app = FastAPI(title="Metrics Service", lifespan=lifespan)
 
 
class EventRecord(BaseModel):
    event: str
    cache_key: str
    latency_ms: float
    processing_time_ms: float = 0.0
 
 
class ExperimentRecord(BaseModel):
    distribution: Optional[str] = None
    total_requests: int = 0
    elapsed_s: float = 0.0
    hits: int = 0
    misses: int = 0
    errors: int = 0
 
 
@app.get("/health")
def health():
    return {"status": "ok", "db": DB_PATH}
 
 
@app.post("/record", status_code=204)
def record_event(ev: EventRecord):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events (ts, event, cache_key, latency_ms, processing_time_ms) "
            "VALUES (?, ?, ?, ?, ?)",
            (time.time(), ev.event, ev.cache_key, ev.latency_ms, ev.processing_time_ms),
        )
 
 
@app.post("/experiment_done", status_code=204)
def experiment_done(exp: ExperimentRecord):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT AVG(eviction_rate) FROM eviction_samples WHERE ts >= ?",
            (time.time() - exp.elapsed_s - 5,)
        ).fetchone()
        avg_eviction_rate = row[0] or 0.0
        conn.execute(
            "INSERT INTO experiments "
            "(ts, distribution, total_requests, elapsed_s, hits, misses, errors, eviction_rate) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (time.time(), exp.distribution, exp.total_requests,
             exp.elapsed_s, exp.hits, exp.misses, exp.errors, avg_eviction_rate),
        )
    logger.info("Experimento registrado | eviction_rate=%.2f/min", avg_eviction_rate)
 
 
@app.get("/metrics")
def get_raw_metrics(limit: int = 500):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
 
 
@app.get("/metrics/summary")
def get_summary():
    with get_conn() as conn:
        total  = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        hits   = conn.execute("SELECT COUNT(*) FROM events WHERE event='hit'").fetchone()[0]
        misses = conn.execute("SELECT COUNT(*) FROM events WHERE event='miss'").fetchone()[0]
 
        lat_all  = [r[0] for r in conn.execute("SELECT latency_ms FROM events ORDER BY latency_ms").fetchall()]
        lat_hit  = [r[0] for r in conn.execute("SELECT latency_ms FROM events WHERE event='hit' ORDER BY latency_ms").fetchall()]
        lat_miss = [r[0] for r in conn.execute("SELECT latency_ms FROM events WHERE event='miss' ORDER BY latency_ms").fetchall()]
 
        ev_row = conn.execute("SELECT AVG(eviction_rate), SUM(delta_evictions) FROM eviction_samples").fetchone()
        avg_eviction_rate = ev_row[0] or 0.0
        total_evictions   = ev_row[1] or 0
 
        t_cache = conn.execute("SELECT AVG(latency_ms) FROM events WHERE event='hit'").fetchone()[0] or 0
        t_miss  = conn.execute("SELECT AVG(latency_ms) FROM events WHERE event='miss'").fetchone()[0] or 0
        cache_efficiency = ((hits * t_cache) - (misses * t_miss)) / total if total > 0 else 0
 
        exp_row = conn.execute(
            "SELECT total_requests, elapsed_s FROM experiments ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        throughput = (exp_row[0] / exp_row[1]) if exp_row and exp_row[1] > 0 else 0
 
        experiments = [dict(r) for r in conn.execute(
            "SELECT * FROM experiments ORDER BY ts DESC LIMIT 10"
        ).fetchall()]
 
    def percentile(data, p):
        if not data:
            return None
        idx = int(len(data) * p / 100)
        return round(data[min(idx, len(data) - 1)], 3)
 
    hit_rate = hits / total if total > 0 else 0
 
    return {
        "total_events"         : total,
        "hits"                 : hits,
        "misses"               : misses,
        "hit_rate"             : round(hit_rate, 4),
        "miss_rate"            : round(1 - hit_rate, 4),
        "throughput_rps"       : round(throughput, 2),
        "eviction_rate_per_min": round(avg_eviction_rate, 2),
        "total_evictions"      : total_evictions,
        "cache_efficiency"     : round(cache_efficiency, 3),
        "latency": {
            "all" : {"p50": percentile(lat_all, 50),  "p95": percentile(lat_all, 95)},
            "hit" : {"p50": percentile(lat_hit, 50),  "p95": percentile(lat_hit, 95)},
            "miss": {"p50": percentile(lat_miss, 50), "p95": percentile(lat_miss, 95)},
        },
        "recent_experiments": experiments,
    }
 
 
@app.get("/metrics/evictions")
def get_evictions():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM eviction_samples ORDER BY ts DESC LIMIT 100"
        ).fetchall()
    return [dict(r) for r in rows]
 
 
@app.delete("/metrics/reset", status_code=204)
def reset_metrics():
    with get_conn() as conn:
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM experiments")
        conn.execute("DELETE FROM eviction_samples")
    logger.info("Metricas reiniciadas.")
 
