import json
import logging
import os
import time
import uuid

import httpx
from kafka import KafkaConsumer, KafkaProducer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

KAFKA_SERVERS  = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
CACHE_URL      = os.getenv("CACHE_URL", "http://cache_service:8002")
METRICS_URL    = os.getenv("METRICS_URL", "http://metrics:8003")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "query-consumers")
MAX_RETRIES    = int(os.getenv("MAX_RETRIES", 3))
CONSUMER_ID    = os.getenv("CONSUMER_ID", "1")
RETRY_DELAY_S  = float(os.getenv("RETRY_DELAY_S", "1.0"))
IDLE_TIMEOUT_S = float(os.getenv("IDLE_TIMEOUT_S", "8.0"))

TOPIC_MAIN  = "queries"
TOPIC_RETRY = "queries-retry"
TOPIC_DLQ   = "queries-dlq"


def make_producer():
    while True:
        try:
            p = KafkaProducer(
                bootstrap_servers=KAFKA_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode(),
                key_serializer=lambda k: k.encode() if k else None,
            )
            return p
        except Exception as e:
            logger.warning("Esperando Kafka producer: %s", e)
            time.sleep(3)


def make_consumer(topics):
    while True:
        try:
            c = KafkaConsumer(
                *topics,
                bootstrap_servers=KAFKA_SERVERS,
                group_id=CONSUMER_GROUP,
                value_deserializer=lambda v: json.loads(v.decode()),
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                consumer_timeout_ms=int(IDLE_TIMEOUT_S * 1000),
            )
            logger.info("Consumer Kafka conectado a topicos: %s", topics)
            return c
        except Exception as e:
            logger.warning("Esperando Kafka consumer: %s", e)
            time.sleep(3)


http_client = httpx.Client(timeout=10.0)


def record_metric(event, query_id, latency_ms, extra=None):
    try:
        http_client.post(f"{METRICS_URL}/record_kafka", json={
            "event": event,
            "query_id": query_id,
            "latency_ms": latency_ms,
            "consumer_id": CONSUMER_ID,
            **(extra or {}),
        }, timeout=2.0)
    except Exception:
        pass


def process_query(msg, producer):
    query_id    = msg.get("query_id", str(uuid.uuid4()))
    retry_count = msg.get("retry_count", 0)
    query_data  = msg.get("query", {})

    t0 = time.perf_counter()
    try:
        resp = http_client.post(f"{CACHE_URL}/query", json=query_data, timeout=8.0)
        resp.raise_for_status()
        latency_ms = (time.perf_counter() - t0) * 1000
        source = resp.json().get("source", "unknown")
        record_metric("success", query_id, latency_ms, {
            "source": source, "retry_count": retry_count,
        })
        return True

    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        logger.warning("FAIL qid=%s retry=%d err=%s", query_id, retry_count, e)

        if retry_count >= MAX_RETRIES:
            producer.send(TOPIC_DLQ, key=query_id, value={
                **msg, "error": str(e), "dlq_ts": time.time(),
            })
            record_metric("dlq", query_id, latency_ms, {
                "retry_count": retry_count, "error": str(e),
            })
            logger.warning("DLQ  qid=%s (max reintentos=%d)", query_id, MAX_RETRIES)
        else:
            time.sleep(RETRY_DELAY_S * (retry_count + 1))
            producer.send(TOPIC_RETRY, key=query_id, value={
                **msg, "retry_count": retry_count + 1, "retry_ts": time.time(),
            })
            record_metric("retry", query_id, latency_ms, {
                "retry_count": retry_count + 1,
            })
            logger.info("RETRY qid=%s intento=%d", query_id, retry_count + 1)
        return False


def print_summary(stats, t_start):
    elapsed = time.time() - t_start
    thr = stats["success"] / elapsed if elapsed > 0 else 0
    lats = sorted(stats["latencies"])
    p50 = lats[int(len(lats) * 0.50)] if lats else 0
    p95 = lats[int(len(lats) * 0.95)] if lats else 0
    total = stats["total"]
    success = stats["success"]

    logger.info("=" * 50)
    logger.info("Resumen del experimento (KAFKA)")
    logger.info("  Distribucion    : %s", stats.get("distribution", "N/A").upper())
    logger.info("  Total           : %d consultas en %.2f s", total, elapsed)
    logger.info("  Throughput      : %.1f req/s", thr)
    logger.info("  Exitosos        : %d (%.1f%%)", success, 100 * success / max(1, total))
    logger.info("  Reintentos      : %d", stats["retry"])
    logger.info("  DLQ             : %d", stats["dlq"])
    logger.info("  Errores         : %d", stats["errors"])
    logger.info("  Latencia p50    : %.2f ms", p50)
    logger.info("  Latencia p95    : %.2f ms", p95)
    logger.info("=" * 50)

    try:
        http_client.post(f"{METRICS_URL}/experiment_done", json={
            "distribution": stats.get("distribution", ""),
            "total_requests": total,
            "elapsed_s": elapsed,
            "hits": stats["hits"],
            "misses": stats["misses"],
            "errors": stats["errors"],
        }, timeout=5.0)
    except Exception:
        pass


def main():
    logger.info("Consumer %s iniciando | grupo=%s | max_reintentos=%d | idle_timeout=%.0fs",
                CONSUMER_ID, CONSUMER_GROUP, MAX_RETRIES, IDLE_TIMEOUT_S)

    producer = make_producer()

    stats = {
        "total": 0, "success": 0, "retry": 0,
        "dlq": 0, "errors": 0, "hits": 0, "misses": 0,
        "latencies": [], "distribution": "",
    }
    t_start = time.time()
    experiment_active = False

    while True:
        consumer = make_consumer([TOPIC_MAIN, TOPIC_RETRY])
        try:
            for message in consumer:
                msg = message.value

                if msg.get("type") == "__EOF__":
                    stats["distribution"] = msg.get("distribution", "")
                    experiment_active = True
                    continue

                experiment_active = True
                stats["total"] += 1

                if msg.get("distribution"):
                    stats["distribution"] = msg.get("distribution", "")

                t0 = time.perf_counter()
                success = process_query(msg, producer)
                latency_ms = (time.perf_counter() - t0) * 1000

                if success:
                    stats["success"] += 1
                    stats["latencies"].append(latency_ms)
                    stats["hits"] += 1
                elif msg.get("retry_count", 0) >= MAX_RETRIES:
                    stats["dlq"] += 1
                    stats["errors"] += 1
                else:
                    stats["retry"] += 1

                if stats["total"] % 100 == 0:
                    elapsed = time.time() - t_start
                    thr = stats["success"] / elapsed if elapsed > 0 else 0
                    logger.info(
                        "Progreso: total=%d ok=%d retry=%d dlq=%d thr=%.1f req/s",
                        stats["total"], stats["success"], stats["retry"], stats["dlq"], thr
                    )

        except Exception:
            pass
        finally:
            consumer.close()

        if experiment_active and stats["total"] > 0:
            logger.info("Sin mensajes nuevos por %.0fs — imprimiendo resumen...", IDLE_TIMEOUT_S)
            print_summary(stats, t_start)
            stats = {
                "total": 0, "success": 0, "retry": 0,
                "dlq": 0, "errors": 0, "hits": 0, "misses": 0,
                "latencies": [], "distribution": "",
            }
            t_start = time.time()
            experiment_active = False
            break  


if __name__ == "__main__":
    main()
