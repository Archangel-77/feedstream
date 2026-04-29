import asyncio
import logging
import signal

from feedstream.settings import settings

logger = logging.getLogger(__name__)

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
    """Connect to AIS stream and write events to Postgres."""
    while not _shutdown.is_set():
        try:
            await _connect_and_consume()
        except Exception as exc:
            logger.error("Ingestion error: %s — will retry", exc)
            await asyncio.sleep(5)


async def _connect_and_consume() -> None:
    """Placeholder: replaced in next step with real AIS WebSocket logic."""
    logger.info("Connecting to AIS stream...")
    await _shutdown.wait()


if __name__ == "__main__":
    logging.basicConfig(level=settings.log_level)
    asyncio.run(run())
