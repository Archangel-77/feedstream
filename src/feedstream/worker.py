import asyncio
import json
import logging
import signal
import uuid
from collections import defaultdict

import tenacity
import websockets
from pythonjsonlogger import jsonlogger
from sqlalchemy.dialects.postgresql import insert  # fix 2: use pg dialect for on_conflict_do_nothing
from sqlalchemy.ext.asyncio import AsyncSession

from feedstream.database import AsyncSessionLocal
from feedstream.models import Event
from feedstream.settings import settings

logger = logging.getLogger(__name__)

AIS_WS_URL = "wss://stream.aisstream.io/v0/stream"

_shutdown = asyncio.Event()

# Simple circuit breaker implementation
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker logic."""
        if self.state == "OPEN":
            if self.last_failure_time and (asyncio.get_event_loop().time() - self.last_failure_time) > self.timeout:
                self.state = "HALF_OPEN"
                # In half-open state, allow one call to proceed
                try:
                    result = func(*args, **kwargs)
                    self._success()  # If successful, reset circuit
                    return result
                except Exception:
                    self._failure()  # If failed, stay open
                    raise
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._success()
            return result
        except Exception as e:
            self._failure()
            raise e
    
    def _success(self):
        self.failure_count = 0
        self.state = "CLOSED"
        
    def _failure(self):
        self.failure_count += 1
        self.last_failure_time = asyncio.get_event_loop().time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

# Global circuit breaker instance
ais_circuit_breaker = CircuitBreaker()


def _handle_signal() -> None:
    logger.info("Shutdown signal received, stopping worker...")
    _shutdown.set()
    
    # Cancel any pending tasks
    for task in asyncio.all_tasks():
        if task != asyncio.current_task():
            task.cancel()


async def run() -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    logger.info("Worker started", extra={"env": settings.app_env})
    await ingest_loop()
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
            await _connect_and_consume_with_retry()
        except Exception as exc:
            logger.error("Ingestion error after retries: %s", exc)
            # If we've exhausted retries, wait before trying again
            await asyncio.sleep(10)


async def _connect_and_consume() -> None:
    subscribe_msg = json.dumps(
        {
            "APIKey": settings.ais_api_key,
            "BoundingBoxes": [[[-90, -180], [90, 180]]],
        }
    )

    logger.info("Connecting to AIS stream at %s", AIS_WS_URL)

    # Use circuit breaker for connection
    def connect_func():
        return websockets.connect(AIS_WS_URL)
    
    try:
        ws = ais_circuit_breaker.call(connect_func)
        async with ws as ws_conn:
            await ws_conn.send(subscribe_msg)
            logger.info("Subscribed to global AIS feed")

            async for message in ws_conn:
                if _shutdown.is_set():
                    break
                # fix 1: memoryview has no .decode(); convert to bytes first
                if isinstance(message, str):
                    raw = message
                elif isinstance(message, memoryview):
                    raw = bytes(message).decode()
                else:
                    raw = message.decode()
                event_dict = parse_ais_message(raw)
                if event_dict:
                    async with AsyncSessionLocal() as session:
                        await write_event(session, event_dict)
    except Exception as e:
        logger.error("Connection failed: %s", e)
        # Reset circuit breaker on successful connection
        ais_circuit_breaker._success()
        raise


def parse_ais_message(raw: str) -> dict | None:
    """Parse a raw AIS JSON string into an event dict ready for DB insert."""
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


async def write_event(session: AsyncSession, event_dict: dict) -> None:
    """Insert a single event dict into the DB with idempotent insert."""
    stmt = (
        insert(Event)
        .values(**event_dict)
        .on_conflict_do_nothing(index_elements=["dedup_key"])
    )
    await session.execute(stmt)
    await session.commit()
    logger.debug("Ingested event type=%s", event_dict.get("event_type"))  # fix 3: removed duplicate log line


if __name__ == "__main__":
    # Set up structured logging
    # Use basic logging for now, but ensure we have proper structured logging capability
    logging.basicConfig(level=settings.log_level)
    asyncio.run(run())
