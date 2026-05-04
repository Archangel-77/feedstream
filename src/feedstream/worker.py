import asyncio
import json
import logging
import signal
import uuid

import tenacity
import websockets
from sqlalchemy.dialects.postgresql import insert  # fix 2: use pg dialect for on_conflict_do_nothing
from sqlalchemy.ext.asyncio import AsyncSession

from feedstream.database import AsyncSessionLocal
from feedstream.models import Event
from feedstream.settings import settings

logger = logging.getLogger(__name__)

AIS_WS_URL = "wss://stream.aisstream.io/v0/stream"

_shutdown = asyncio.Event()


def _handle_signal() -> None:
    logger.info("Shutdown signal received, stopping worker...")
    _shutdown.set()


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

    async with websockets.connect(AIS_WS_URL) as ws:
        await ws.send(subscribe_msg)
        logger.info("Subscribed to global AIS feed")

        async for message in ws:
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
    logging.basicConfig(level=settings.log_level)
    asyncio.run(run())