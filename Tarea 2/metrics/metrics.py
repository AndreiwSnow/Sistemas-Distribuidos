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

DB_PATH               = os.getenv("DB_PATH", "/metrics/metrics.db")
REDIS_HOST            = os.getenv("REDIS_HOST", "redis")
REDIS_PORT            = int(os.getenv("REDIS_PORT", 6379))
KAFKA_SERVERS         = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
EVICTION_POLL_INTERVAL = int(os.getenv("EVICTION_POLL_INTERVAL", 15))


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                ts                 REAL NOT NULL,
                event              TEXT NOT NULL,
                cache_key          TEXT NOT NULL DEFAULT '',
                latency_ms         REAL NOT NULL,
                processing_time_ms REAL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kafka_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          REAL NOT NULL,
                event       TEXT NOT NULL,
                query_id    TEXT NOT NULL,
                latency_ms  REAL NOT NULL,
                consumer_id TEXT DEFAULT '1',
                retry_count INTEGER DEFAULT 0,
                source      TEXT DEFAULT '',
                error       TEXT DEFAULT ''
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kafka_sessions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ts            REAL NOT NULL,
                total         INTEGER,
                elapsed_s     REAL,
                distribution  TEXT,
                rate_per_s    REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_event ON events(event)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kafka_event ON kafka_events(event)")


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
_last_poll_ts   = 0.0


async def poll_evictions(redis_client):
    global _last_evictions, _last_poll_ts
    while True:
        await asyncio.sleep(EVICTION_POLL_INTERVAL)
        try:
            info  = await redis_client.info("stats")
            total = int(info.get("evicted_keys", 0))
            now   = time.time()
            delta = total - _last_evictions
            elapsed = now - _last_poll_ts if _last_poll_ts else EVICTION_POLL_INTERVAL
            rate  = (delta / elapsed) * 60 if elapsed > 0 else 0
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO eviction_samples (ts, total_evictions, delta_evictions, eviction_rate) "
                    "VALUES (?, ?, ?, ?)", (now, total, delta, rate),
                )
            if delta > 0:
                logger.info("Evictions: +%d (total=%d, rate=%.1f/min)", delta, total, rate)
            _last_evictions = total
            _last_poll_ts   = now
        except Exception as e:
            logger.warning("Error consultando Redis: %s", e)


async def poll_kafka_backlog():
    """Monitorea el backlog de mensajes pendientes en Kafka."""
    await asyncio.sleep(10)
    while True:
        try:
            from kafka import KafkaConsumer
            from kafka.admin import KafkaAdminClient
            logger.debug("Kafka backlog monitor activo")
        except Exception:
            pass
        await asyncio.sleep(15)


redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    init_db()
    redis_client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    asyncio.create_task(poll_evictions(redis_client))
    logger.info("Metricas iniciadas. DB: %s", DB_PATH)
    yield
    await redis_client.aclose()


app = FastAPI(title="Metrics Service", lifespan=lifespan)


class EventRecord(BaseModel):
    event: str
    cache_key: str = ""
    latency_ms: float
    processing_time_ms: float = 0.0


class KafkaEventRecord(BaseModel):
    event: str
    query_id: str
    latency_ms: float
    consumer_id: str = "1"
    retry_count: int = 0
    source: str = ""
    error: str = ""


class ExperimentRecord(BaseModel):
    distribution: Optional[str] = None
    total_requests: int = 0
    elapsed_s: float = 0.0
    hits: int = 0
    misses: int = 0
    errors: int = 0


class KafkaProducedRecord(BaseModel):
    total: int
    elapsed_s: float
    distribution: str = ""
    rate_per_s: float = 0.0


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


@app.post("/record_kafka", status_code=204)
def record_kafka_event(ev: KafkaEventRecord):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO kafka_events (ts, event, query_id, latency_ms, consumer_id, retry_count, source, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (time.time(), ev.event, ev.query_id, ev.latency_ms,
             ev.consumer_id, ev.retry_count, ev.source, ev.error),
        )


@app.post("/kafka_produced", status_code=204)
def kafka_produced(rec: KafkaProducedRecord):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO kafka_sessions (ts, total, elapsed_s, distribution, rate_per_s) "
            "VALUES (?, ?, ?, ?, ?)",
            (time.time(), rec.total, rec.elapsed_s, rec.distribution, rec.rate_per_s),
        )
    logger.info("Kafka: %d mensajes publicados (%.1f msg/s)", rec.total, rec.rate_per_s)


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


@app.get("/metrics/summary")
def get_summary():
    with get_conn() as conn:
        total  = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        hits   = conn.execute("SELECT COUNT(*) FROM events WHERE event='hit'").fetchone()[0]
        misses = conn.execute("SELECT COUNT(*) FROM events WHERE event='miss'").fetchone()[0]

        k_total    = conn.execute("SELECT COUNT(*) FROM kafka_events").fetchone()[0]
        k_success  = conn.execute("SELECT COUNT(*) FROM kafka_events WHERE event='success'").fetchone()[0]
        k_retry    = conn.execute("SELECT COUNT(*) FROM kafka_events WHERE event='retry'").fetchone()[0]
        k_dlq      = conn.execute("SELECT COUNT(*) FROM kafka_events WHERE event='dlq'").fetchone()[0]

        lat_all  = [r[0] for r in conn.execute("SELECT latency_ms FROM kafka_events WHERE event='success' ORDER BY latency_ms").fetchall()]

        ev_row = conn.execute("SELECT AVG(eviction_rate), SUM(delta_evictions) FROM eviction_samples").fetchone()
        avg_eviction_rate = ev_row[0] or 0.0
        total_evictions   = ev_row[1] or 0

        exp_row = conn.execute(
            "SELECT total_requests, elapsed_s FROM experiments ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        throughput = (exp_row[0] / exp_row[1]) if exp_row and exp_row[1] > 0 else 0

        experiments = [dict(r) for r in conn.execute(
            "SELECT * FROM experiments ORDER BY ts DESC LIMIT 5"
        ).fetchall()]

    def pct(data, p):
        if not data:
            return None
        return round(data[int(len(data) * p / 100)], 3)

    hit_rate = hits / total if total > 0 else 0
    retry_rate = k_retry / k_total if k_total > 0 else 0
    dlq_rate   = k_dlq   / k_total if k_total > 0 else 0
    recovery_rate = k_success / k_total if k_total > 0 else 0

    return {
        "sincrono": {
            "total_events": total,
            "hits": hits,
            "misses": misses,
            "hit_rate": round(hit_rate, 4),
            "throughput_rps": round(throughput, 2),
        },
        "kafka": {
            "total_procesados": k_total,
            "success": k_success,
            "retry": k_retry,
            "dlq": k_dlq,
            "retry_rate": round(retry_rate, 4),
            "dlq_rate": round(dlq_rate, 4),
            "recovery_rate": round(recovery_rate, 4),
            "latency": {
                "p50": pct(lat_all, 50),
                "p95": pct(lat_all, 95),
            },
        },
        "cache": {
            "eviction_rate_per_min": round(avg_eviction_rate, 2),
            "total_evictions": total_evictions,
        },
        "recent_experiments": experiments,
    }


@app.get("/metrics/kafka")
def get_kafka_metrics(limit: int = 200):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM kafka_events ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/metrics/backlog")
def get_backlog():
    """Consulta el backlog actual de mensajes en Kafka."""
    try:
        from kafka import KafkaConsumer, TopicPartition
        consumer = KafkaConsumer(bootstrap_servers=KAFKA_SERVERS)
        backlog = {}
        for topic in ["queries", "queries-retry", "queries-dlq"]:
            try:
                partitions = consumer.partitions_for_topic(topic)
                if partitions:
                    tps = [TopicPartition(topic, p) for p in partitions]
                    end_offsets = consumer.end_offsets(tps)
                    backlog[topic] = sum(end_offsets.values())
                else:
                    backlog[topic] = 0
            except Exception:
                backlog[topic] = 0
        consumer.close()
        return {"backlog": backlog, "ts": time.time()}
    except Exception as e:
        return {"backlog": {}, "error": str(e)}


@app.delete("/metrics/reset", status_code=204)
def reset_metrics():
    with get_conn() as conn:
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM kafka_events")
        conn.execute("DELETE FROM experiments")
        conn.execute("DELETE FROM eviction_samples")
        conn.execute("DELETE FROM kafka_sessions")
    logger.info("Metricas reiniciadas.")
