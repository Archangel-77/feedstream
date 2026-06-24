import asyncio
import json
import logging
import signal
import time
import uuid

import tenacity
import websockets
from pythonjsonlogger import jsonlogger
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from feedstream.database import AsyncSessionLocal
from feedstream.models import Event
from feedstream.observability.metrics import (
    METRIC_EVENTS_INGESTED_TOTAL,
    observe_ingestion_latency,
    set_worker_state,
)
from feedstream.observability.tracing import get_ingestion_trace_id, new_trace_id, set_ingestion_trace_id
from feedstream.redis_client import get_redis_client
from feedstream.settings import settings

logger = logging.getLogger(__name__)

AIS_WS_URL = "wss://stream.aisstream.io/v0/stream"

_shutdown = asyncio.Event()


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = "CLOSED"

    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._success()
            return result
        except Exception as exc:
            self._failure()
            if self.state == "OPEN":
                raise Exception("Circuit breaker is OPEN")
            raise exc

    def _success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def _failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def check_state(self):
        if self.state == "OPEN" and self.last_failure_time:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
        return self.state


ais_circuit_breaker = CircuitBreaker()


def _handle_signal() -> None:
    logger.info("Shutdown signal received, stopping worker...")
    _shutdown.set()


async def run() -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    set_worker_state("retrying")
    logger.info("Worker started", extra={"env": settings.app_env})
    await ingest_loop()
    set_worker_state("disconnected")
    logger.info("Worker stopped cleanly")


async def ingest_loop() -> None:
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(10),
        wait=tenacity.wait_random_exponential(multiplier=1, max=60),
        retry=tenacity.retry_if_exception_type(websockets.exceptions.ConnectionClosed),
        reraise=True,
    )
    async def _connect_and_consume_with_retry():
        await _connect_and_consume()

    while not _shutdown.is_set():
        try:
            set_worker_state("retrying")
            await _connect_and_consume_with_retry()
        except Exception as exc:
            set_worker_state("disconnected")
            logger.error("Ingestion error after retries: %s", exc)
            await asyncio.sleep(10)


async def _connect_and_consume() -> None:
    subscribe_msg = json.dumps(
        {
            "APIKey": settings.ais_api_key,
            "BoundingBoxes": [[[-90, -180], [90, 180]]],
        }
    )

    logger.info("Connecting to AIS stream at %s", AIS_WS_URL)

    def connect_func():
        return websockets.connect(AIS_WS_URL)

    ws = ais_circuit_breaker.call(connect_func)
    async with ws as ws_conn:
        set_worker_state("connected")
        await ws_conn.send(subscribe_msg)
        logger.info("Subscribed to global AIS feed")

        async for message in ws_conn:
            if _shutdown.is_set():
                break

            started_at = time.perf_counter()
            trace_id = new_trace_id()
            set_ingestion_trace_id(trace_id)

            if isinstance(message, str):
                raw = message
            elif isinstance(message, memoryview):
                raw = bytes(message).decode()
            else:
                raw = message.decode()

            event_dict = parse_ais_message(raw)
            if event_dict:
                async with AsyncSessionLocal() as session:
                    status = await write_event(session, event_dict)
                    METRIC_EVENTS_INGESTED_TOTAL.labels(
                        source=event_dict["source"],
                        event_type=event_dict["event_type"],
                        status=status,
                    ).inc()
                    observe_ingestion_latency(event_dict["source"], started_at)


def parse_ais_message(raw: str) -> dict | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Received non-JSON message, skipping")
        return None

    message_type = data.get("MessageType", "unknown")
    mmsi = str(data.get("MetaData", {}).get("MMSI", ""))
    time_utc = data.get("MetaData", {}).get("time_utc", "")
    dedup_key = f"{mmsi}:{message_type}:{time_utc}" if mmsi and time_utc else None

    return {
        "id": uuid.uuid4(),
        "source": "aisstream",
        "event_type": message_type,
        "payload": data,
        "dedup_key": dedup_key,
    }


async def write_event(session: AsyncSession, event_dict: dict) -> str:
    stmt = insert(Event).values(**event_dict).on_conflict_do_nothing(index_elements=["dedup_key"])
    result = await session.execute(stmt)
    await session.commit()

    trace_id = get_ingestion_trace_id()
    if result.rowcount > 0:
        redis_client_instance = await get_redis_client()
        await redis_client_instance.delete_pattern("events:*")
        logger.debug(
            "Ingested event and invalidated cache",
            extra={"event_type": event_dict.get("event_type"), "ingestion_trace_id": trace_id},
        )
        return "inserted"

    logger.debug(
        "Duplicate event skipped",
        extra={"event_type": event_dict.get("event_type"), "ingestion_trace_id": trace_id},
    )
    return "duplicate"


if __name__ == "__main__":
    handler = logging.StreamHandler()
    handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.setLevel(settings.log_level)
    logger.addHandler(handler)
    asyncio.run(run())
