import time
from typing import Any

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

METRIC_HTTP_REQUESTS_TOTAL = Counter(
    "feedstream_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)

METRIC_EVENTS_INGESTED_TOTAL = Counter(
    "feedstream_events_ingested_total",
    "Total ingested events by source/type/status",
    ["source", "event_type", "status"],
)

METRIC_INGESTION_LATENCY_SECONDS = Histogram(
    "feedstream_ingestion_latency_seconds",
    "Latency for parsing and writing ingested events",
    ["source"],
)

METRIC_QUERY_LATENCY_SECONDS = Histogram(
    "feedstream_query_latency_seconds",
    "Latency for HTTP query endpoints",
    ["endpoint"],
)

METRIC_WORKER_STATE = Gauge(
    "feedstream_worker_state",
    "Worker state represented as one-hot labels",
    ["state"],
)

METRIC_CACHE_HITS_TOTAL = Counter(
    "feedstream_cache_hits_total",
    "Total cache hits",
)

METRIC_CACHE_MISSES_TOTAL = Counter(
    "feedstream_cache_misses_total",
    "Total cache misses",
)

METRIC_CACHE_INVALIDATIONS_TOTAL = Counter(
    "feedstream_cache_invalidations_total",
    "Total cache entries invalidated after writes",
)

METRIC_RETENTION_DELETES_TOTAL = Counter(
    "feedstream_retention_deletes_total",
    "Total events deleted by the retention job",
)

METRIC_DB_POOL_CHECKED_OUT = Gauge(
    "feedstream_db_pool_checked_out",
    "Checked out DB connections",
)

METRIC_DB_POOL_SIZE = Gauge(
    "feedstream_db_pool_size",
    "Current DB pool size",
)

METRIC_DB_POOL_OVERFLOW = Gauge(
    "feedstream_db_pool_overflow",
    "Current DB pool overflow count",
)

WORKER_STATES = ("connected", "disconnected", "retrying")
_current_worker_state = "disconnected"


def observe_query_latency(endpoint: str, started_at: float) -> None:
    METRIC_QUERY_LATENCY_SECONDS.labels(endpoint=endpoint).observe(time.perf_counter() - started_at)


def observe_ingestion_latency(source: str, started_at: float) -> None:
    METRIC_INGESTION_LATENCY_SECONDS.labels(source=source).observe(time.perf_counter() - started_at)


def set_worker_state(state: str) -> None:
    global _current_worker_state
    if state not in WORKER_STATES:
        return
    for worker_state in WORKER_STATES:
        METRIC_WORKER_STATE.labels(state=worker_state).set(1 if worker_state == state else 0)
    _current_worker_state = state


def observe_db_pool(pool_stats: dict[str, int]) -> None:
    METRIC_DB_POOL_CHECKED_OUT.set(pool_stats.get("checked_out", 0))
    METRIC_DB_POOL_SIZE.set(pool_stats.get("size", 0))
    METRIC_DB_POOL_OVERFLOW.set(pool_stats.get("overflow", 0))


def observe_cache_invalidation(count: int) -> None:
    METRIC_CACHE_INVALIDATIONS_TOTAL.inc(count)


def observe_retention_deletes(count: int) -> None:
    METRIC_RETENTION_DELETES_TOTAL.inc(count)


def get_metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST


def metrics_snapshot(db_pool_stats: dict[str, int], cache_stats: dict[str, int]) -> dict[str, Any]:
    return {
        "worker": {"state": _current_worker_state},
        "cache": cache_stats,
        "db_pool": db_pool_stats,
    }
