import asyncio
import json
import logging
import signal
import uuid

import websockets
from sqlalchemy import insert

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
    while not _shutdown.is_set():
        try:
            await _connect_and_consume()
        except Exception as exc:
            logger.error("Ingestion error: %s — will retry in 5s", exc)
            await asyncio.sleep(5)


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

        async for raw in ws:
            if _shutdown.is_set():
                break
            await _handle_message(raw)


async def _handle_message(raw: str) -> None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Received non-JSON message, skipping")
        return

    message_type = data.get("MessageType", "unknown")
    mmsi = str(data.get("MetaData", {}).get("MMSI", ""))
    time_utc = data.get("MetaData", {}).get("time_utc", "")

    dedup_key = f"{mmsi}:{message_type}:{time_utc}" if mmsi and time_utc else None

    event = {
        "id": uuid.uuid4(),
        "source": "aisstream",
        "event_type": message_type,
        "payload": data,
        "dedup_key": dedup_key,
    }

    async with AsyncSessionLocal() as session:
        await session.execute(insert(Event).values(**event))
        await session.commit()

    logger.debug("Ingested event type=%s mmsi=%s", message_type, mmsi)


if __name__ == "__main__":
    logging.basicConfig(level=settings.log_level)
    asyncio.run(run())
