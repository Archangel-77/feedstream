import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from feedstream.models import Event
from feedstream.retention import run_retention_once


@pytest.mark.asyncio
async def test_retention_deletes_old_events_only(db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(days=10)
    recent_time = now - timedelta(days=1)

    await db_session.execute(
        insert(Event).values(
            id=uuid.uuid4(),
            source="aisstream",
            event_type="PositionReport",
            payload={"age": "old"},
            dedup_key="retention-old",
            received_at=old_time,
        )
    )
    await db_session.execute(
        insert(Event).values(
            id=uuid.uuid4(),
            source="aisstream",
            event_type="PositionReport",
            payload={"age": "recent"},
            dedup_key="retention-recent",
            received_at=recent_time,
        )
    )
    await db_session.commit()

    deleted = await run_retention_once(db_session, retention_days=7, batch_size=100)
    assert deleted == 1

    rows = await db_session.execute(select(Event).order_by(Event.received_at.asc()))
    events = rows.scalars().all()
    assert len(events) == 1
    assert events[0].payload["age"] == "recent"


@pytest.mark.asyncio
async def test_retention_respects_batch_size(db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(days=30)

    for i in range(3):
        await db_session.execute(
            insert(Event).values(
                id=uuid.uuid4(),
                source="aisstream",
                event_type="PositionReport",
                payload={"idx": i},
                dedup_key=f"retention-batch-{i}",
                received_at=old_time,
            )
        )
    await db_session.commit()

    deleted = await run_retention_once(db_session, retention_days=7, batch_size=2)
    assert deleted == 3
