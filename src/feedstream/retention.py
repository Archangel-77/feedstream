import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from feedstream.database import AsyncSessionLocal
from feedstream.logging_config import configure_logging
from feedstream.models import Event
from feedstream.observability.metrics import observe_retention_deletes
from feedstream.settings import settings

logger = logging.getLogger(__name__)


async def run_retention_once(
    session: AsyncSession,
    *,
    retention_days: int,
    batch_size: int,
) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    total_deleted = 0

    while True:
        ids = (
            select(Event.id)
            .where(Event.received_at < cutoff)
            .order_by(Event.received_at.asc())
            .limit(batch_size)
        )
        result = await session.execute(ids)
        batch_ids = list(result.scalars().all())
        if not batch_ids:
            break

        stmt = delete(Event).where(Event.id.in_(batch_ids))
        delete_result = await session.execute(stmt)
        await session.commit()
        deleted = int(cast(CursorResult, delete_result).rowcount or 0)
        total_deleted += deleted
        observe_retention_deletes(deleted)

        if deleted < batch_size:
            break

    return total_deleted


async def retention_loop() -> None:
    interval_seconds = max(settings.retention_interval_minutes, 1) * 60
    logger.info(
        "Starting retention loop",
        extra={
            "retention_days": settings.retention_days,
            "retention_batch_size": settings.retention_batch_size,
            "retention_interval_minutes": settings.retention_interval_minutes,
        },
    )
    while True:
        try:
            async with AsyncSessionLocal() as session:
                deleted = await run_retention_once(
                    session,
                    retention_days=settings.retention_days,
                    batch_size=settings.retention_batch_size,
                )
                logger.info("Retention run complete", extra={"deleted_events": deleted})
        except Exception:
            logger.exception("Retention run failed")

        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    configure_logging(settings.log_level)
    asyncio.run(retention_loop())
