import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from feedstream.models import Event
from feedstream.worker import parse_ais_message, write_event


@pytest.mark.asyncio
async def test_list_events_empty(client: AsyncClient):
    response = await client.get("/events")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_events_returns_rows(client: AsyncClient, db_session: AsyncSession):
    await db_session.execute(
        insert(Event).values(
            id=uuid.uuid4(),
            source="aisstream",
            event_type="PositionReport",
            payload={"test": True},
            dedup_key="mmsi:PositionReport:2024-01-01T00:00:00",
        )
    )
    await db_session.commit()

    response = await client.get("/events?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["event_type"] == "PositionReport"
    assert data[0]["source"] == "aisstream"


@pytest.mark.asyncio
async def test_list_events_limit(client: AsyncClient, db_session: AsyncSession):
    for i in range(5):
        await db_session.execute(
            insert(Event).values(
                id=uuid.uuid4(),
                source="aisstream",
                event_type="PositionReport",
                payload={"seq": i},
                dedup_key=f"mmsi:{i}",
            )
        )
    await db_session.commit()

    response = await client.get("/events?limit=3")
    assert response.status_code == 200
    assert len(response.json()) == 3


@pytest.mark.asyncio
async def test_fake_event_lands_in_db(db_session: AsyncSession):
    """Feed a fake AIS message through parse + write and assert it lands in the DB."""
    raw = json.dumps(
        {
            "MessageType": "PositionReport",
            "MetaData": {"MMSI": 123456789, "time_utc": "2024-01-01 00:00:00"},
            "Message": {"Latitude": 37.9, "Longitude": 23.7},
        }
    )

    event_dict = parse_ais_message(raw)
    assert event_dict is not None
    await write_event(db_session, event_dict)

    result = await db_session.execute(select(Event).where(Event.event_type == "PositionReport"))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].source == "aisstream"
    assert rows[0].payload["MetaData"]["MMSI"] == 123456789
