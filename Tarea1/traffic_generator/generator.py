import asyncio
import logging
import os
import random
import time
from typing import List

import httpx
import numpy as np

from queries import (
    BINS_OPTIONS, CONFIDENCE_LEVELS, QUERY_TYPE_WEIGHTS,
    ZONE_IDS, ZONE_PAIRS, Query,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CACHE_URL = os.getenv("CACHE_URL", "http://localhost:8002")
METRICS_URL = os.getenv("METRICS_URL", "http://localhost:8003")
DISTRIBUTION = os.getenv("DISTRIBUTION", "zipf").lower()
ZIPF_S = float(os.getenv("ZIPF_S", "1.2"))
TOTAL_REQUESTS = int(os.getenv("TOTAL_REQUESTS", "1000"))
CONCURRENCY = int(os.getenv("CONCURRENCY", "10"))
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))

def zipf_zone_probabilities(n_zones: int, s: float) -> np.ndarray:
    """
    Genera probabilidades según Zipf: P(k) ∝ 1/k^s
    La zona 0 (Z1) es la más popular, Z5 la menos.
    """
    ranks = np.arange(1, n_zones + 1, dtype=float)
    weights = 1.0 / np.power(ranks, s)
    return weights / weights.sum()


def uniform_zone_probabilities(n_zones: int) -> np.ndarray:
    return np.ones(n_zones) / n_zones


def build_random_query(rng: random.Random, zone_probs: np.ndarray) -> Query:
    """Elige tipo de consulta y zona según las distribuciones configuradas."""
    query_type = rng.choices(
        list(QUERY_TYPE_WEIGHTS.keys()),
        weights=list(QUERY_TYPE_WEIGHTS.values()),
    )[0]

    zone_idx = rng.choices(range(len(ZONE_IDS)), weights=zone_probs.tolist())[0]
    zone_id = ZONE_IDS[zone_idx]

    conf_min = rng.choice(CONFIDENCE_LEVELS)

    if query_type == "Q4":
        pair = rng.choice(ZONE_PAIRS)
        return Query(query_type="Q4", zone_id=pair[0], zone_id_b=pair[1], confidence_min=conf_min)
    elif query_type == "Q5":
        return Query(query_type="Q5", zone_id=zone_id, bins=rng.choice(BINS_OPTIONS))
    else:
        return Query(query_type=query_type, zone_id=zone_id, confidence_min=conf_min)

async def send_query(client: httpx.AsyncClient, query: Query, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        t0 = time.perf_counter()
        try:
            resp = await client.post(f"{CACHE_URL}/query", json=query.to_dict(), timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            latency_ms = (time.perf_counter() - t0) * 1000
            return {"success": True, "source": data.get("source"), "latency_ms": latency_ms}
        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000
            logger.warning("Error enviando consulta: %s (%.1f ms)", e, latency_ms)
            return {"success": False, "latency_ms": latency_ms}



async def run():
    rng = random.Random(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    n_zones = len(ZONE_IDS)
    if DISTRIBUTION == "zipf":
        zone_probs = zipf_zone_probabilities(n_zones, ZIPF_S)
        logger.info("Distribución: Zipf (s=%.2f) | probs=%s", ZIPF_S,
                    [f"{p:.3f}" for p in zone_probs])
    else:
        zone_probs = uniform_zone_probabilities(n_zones)
        logger.info("Distribución: Uniforme")

    queries: List[Query] = [
        build_random_query(rng, zone_probs) for _ in range(TOTAL_REQUESTS)
    ]

    semaphore = asyncio.Semaphore(CONCURRENCY)

    logger.info("Iniciando %d consultas con concurrencia=%d ...", TOTAL_REQUESTS, CONCURRENCY)
    t_global = time.perf_counter()

    async with httpx.AsyncClient() as client:
        tasks = [send_query(client, q, semaphore) for q in queries]
        results = await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - t_global
    hits = sum(1 for r in results if r.get("source") == "cache")
    misses = sum(1 for r in results if r.get("source") == "generator")
    errors = sum(1 for r in results if not r.get("success"))
    latencies = [r["latency_ms"] for r in results if r.get("success")]

    logger.info("=" * 50)
    logger.info("Resumen del experimento")
    logger.info("  Distribución  : %s", DISTRIBUTION.upper())
    logger.info("  Total         : %d consultas en %.2f s", TOTAL_REQUESTS, elapsed)
    logger.info("  Throughput    : %.1f req/s", TOTAL_REQUESTS / elapsed)
    logger.info("  Hits          : %d (%.1f%%)", hits, 100 * hits / max(1, hits + misses))
    logger.info("  Misses        : %d", misses)
    logger.info("  Errores       : %d", errors)
    if latencies:
        latencies_sorted = sorted(latencies)
        p50 = latencies_sorted[int(len(latencies_sorted) * 0.50)]
        p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
        logger.info("  Latencia p50  : %.2f ms", p50)
        logger.info("  Latencia p95  : %.2f ms", p95)
    logger.info("=" * 50)

    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{METRICS_URL}/experiment_done", json={
                "distribution": DISTRIBUTION,
                "total_requests": TOTAL_REQUESTS,
                "elapsed_s": elapsed,
                "hits": hits,
                "misses": misses,
                "errors": errors,
            }, timeout=5.0)
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(run())
