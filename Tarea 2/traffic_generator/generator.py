import asyncio
import json
import logging
import os
import random
import time
import uuid

import httpx
import numpy as np

from queries import (
    BINS_OPTIONS, CONFIDENCE_LEVELS, QUERY_TYPE_WEIGHTS,
    ZONE_IDS, ZONE_PAIRS, Query,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

KAFKA_SERVERS   = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
METRICS_URL     = os.getenv("METRICS_URL", "http://metrics:8003")
CACHE_URL       = os.getenv("CACHE_URL", "http://cache_service:8002")
DISTRIBUTION    = os.getenv("DISTRIBUTION", "zipf").lower()
ZIPF_S          = float(os.getenv("ZIPF_S", "1.2"))
TOTAL_REQUESTS  = int(os.getenv("TOTAL_REQUESTS", "1000"))
CONCURRENCY     = int(os.getenv("CONCURRENCY", "10"))
RANDOM_SEED     = int(os.getenv("RANDOM_SEED", "42"))
USE_KAFKA       = os.getenv("USE_KAFKA", "true").lower() == "true"
SPIKE_ENABLED   = os.getenv("SPIKE_ENABLED", "false").lower() == "true"
SPIKE_REQUESTS  = int(os.getenv("SPIKE_REQUESTS", "500"))
SPIKE_AFTER     = int(os.getenv("SPIKE_AFTER", "500"))
TOPIC_MAIN      = "queries"


def zipf_zone_probabilities(n, s):
    ranks = np.arange(1, n + 1, dtype=float)
    w = 1.0 / np.power(ranks, s)
    return w / w.sum()


def uniform_zone_probabilities(n):
    return np.ones(n) / n


def build_random_query(rng, zone_probs):
    query_type = rng.choices(
        list(QUERY_TYPE_WEIGHTS.keys()),
        weights=list(QUERY_TYPE_WEIGHTS.values()),
    )[0]
    zone_idx = rng.choices(range(len(ZONE_IDS)), weights=zone_probs.tolist())[0]
    zone_id  = ZONE_IDS[zone_idx]
    conf_min = rng.choice(CONFIDENCE_LEVELS)
    if query_type == "Q4":
        pair = rng.choice(ZONE_PAIRS)
        return Query(query_type="Q4", zone_id=pair[0], zone_id_b=pair[1], confidence_min=conf_min)
    elif query_type == "Q5":
        return Query(query_type="Q5", zone_id=zone_id, bins=rng.choice(BINS_OPTIONS))
    else:
        return Query(query_type=query_type, zone_id=zone_id, confidence_min=conf_min)


def publish_batch(producer, queries, label=""):
    t0 = time.time()
    for q in queries:
        msg = {
            "query_id": str(uuid.uuid4()),
            "query": q.to_dict(),
            "retry_count": 0,
            "created_ts": time.time(),
            "distribution": DISTRIBUTION,
        }
        producer.send(TOPIC_MAIN, key=msg["query_id"], value=msg)
    producer.flush()
    elapsed = time.time() - t0
    rate = len(queries) / elapsed if elapsed > 0 else 0
    logger.info("%s: Publicadas %d consultas en %.2f s (%.1f msg/s)",
                label, len(queries), elapsed, rate)
    return elapsed, rate


def run_kafka_mode(queries, rng, zone_probs):
    from kafka import KafkaProducer
    logger.info("Modo KAFKA — %d consultas | spike=%s", len(queries), SPIKE_ENABLED)

    while True:
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode(),
                key_serializer=lambda k: k.encode() if k else None,
            )
            break
        except Exception as e:
            logger.warning("Esperando Kafka: %s", e)
            time.sleep(3)

    total_published = 0

    if SPIKE_ENABLED:
        normal_queries = queries[:SPIKE_AFTER]
        publish_batch(producer, normal_queries, "NORMAL")
        total_published += len(normal_queries)

        logger.info("*** SPIKE DE TRAFICO: publicando %d consultas adicionales ***", SPIKE_REQUESTS)
        spike_queries = [build_random_query(rng, zone_probs) for _ in range(SPIKE_REQUESTS)]
        publish_batch(producer, spike_queries, "SPIKE")
        total_published += len(spike_queries)


        remaining = queries[SPIKE_AFTER:]
        if remaining:
            publish_batch(producer, remaining, "POST-SPIKE")
            total_published += len(remaining)
    else:
        elapsed, rate = publish_batch(producer, queries, "NORMAL")
        total_published = len(queries)

    producer.send(TOPIC_MAIN, key="eof", value={
        "type": "__EOF__",
        "distribution": DISTRIBUTION,
        "total": total_published,
        "spike": SPIKE_ENABLED,
        "ts": time.time(),
    })
    producer.flush()

    try:
        with httpx.Client() as client:
            client.post(f"{METRICS_URL}/kafka_produced", json={
                "total": total_published,
                "elapsed_s": 0,
                "distribution": DISTRIBUTION,
                "rate_per_s": 0,
            }, timeout=5.0)
    except Exception:
        pass

    producer.close()
    logger.info("Total publicado: %d consultas", total_published)


async def send_query_sync(client, query, semaphore):
    async with semaphore:
        t0 = time.perf_counter()
        try:
            resp = await client.post(f"{CACHE_URL}/query", json=query.to_dict(), timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            latency_ms = (time.perf_counter() - t0) * 1000
            return {"success": True, "source": data.get("source"), "latency_ms": latency_ms}
        except Exception:
            latency_ms = (time.perf_counter() - t0) * 1000
            return {"success": False, "latency_ms": latency_ms}


async def run_sync_mode(queries):
    logger.info("Modo SINCRONO — %d consultas", len(queries))
    semaphore = asyncio.Semaphore(CONCURRENCY)
    t_global  = time.perf_counter()

    async with httpx.AsyncClient() as client:
        tasks   = [send_query_sync(client, q, semaphore) for q in queries]
        results = await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - t_global
    hits    = sum(1 for r in results if r.get("source") == "cache")
    misses  = sum(1 for r in results if r.get("source") == "generator")
    errors  = sum(1 for r in results if not r.get("success"))
    lats    = sorted(r["latency_ms"] for r in results if r.get("success"))

    logger.info("=" * 50)
    logger.info("Resumen del experimento (SINCRONO)")
    logger.info("  Distribucion  : %s", DISTRIBUTION.upper())
    logger.info("  Total         : %d consultas en %.2f s", TOTAL_REQUESTS, elapsed)
    logger.info("  Throughput    : %.1f req/s", TOTAL_REQUESTS / elapsed)
    logger.info("  Hits          : %d (%.1f%%)", hits, 100 * hits / max(1, hits + misses))
    logger.info("  Misses        : %d", misses)
    logger.info("  Errores       : %d", errors)
    if lats:
        logger.info("  Latencia p50  : %.2f ms", lats[int(len(lats) * 0.50)])
        logger.info("  Latencia p95  : %.2f ms", lats[int(len(lats) * 0.95)])
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


def main():
    rng = random.Random(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    n = len(ZONE_IDS)
    zone_probs = zipf_zone_probabilities(n, ZIPF_S) if DISTRIBUTION == "zipf" \
                 else uniform_zone_probabilities(n)

    logger.info("Distribucion: %s | Consultas: %d | Modo: %s | Spike: %s",
                DISTRIBUTION.upper(), TOTAL_REQUESTS,
                "KAFKA" if USE_KAFKA else "SINCRONO",
                "SI" if SPIKE_ENABLED else "NO")

    queries = [build_random_query(rng, zone_probs) for _ in range(TOTAL_REQUESTS)]

    if USE_KAFKA:
        run_kafka_mode(queries, rng, zone_probs)
    else:
        asyncio.run(run_sync_mode(queries))


if __name__ == "__main__":
    main()
