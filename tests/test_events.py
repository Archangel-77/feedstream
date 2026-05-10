import json
import uuid
from datetime import datetime, timedelta

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
    data = response.json()
    assert data["events"] == []
    assert data["total_count"] == 0
    assert data["has_more"] is False
    assert data["next_cursor"] is None


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
    assert len(data["events"]) == 1
    assert data["total_count"] == 1
    assert data["events"][0]["event_type"] == "PositionReport"
    assert data["events"][0]["source"] == "aisstream"


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
    data = response.json()
    assert len(data["events"]) == 3
    assert data["total_count"] == 5
    assert data["has_more"] is True
    assert data["next_cursor"] is not None


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


@pytest.mark.asyncio
async def test_events_filter_by_source(client: AsyncClient, db_session: AsyncSession):
    """Test filtering events by source."""
    # Insert events from different sources
    await db_session.execute(
        insert(Event).values(
            id=uuid.uuid4(),
            source="aisstream",
            event_type="PositionReport",
            payload={"test": True},
            dedup_key="mmsi:1",
        )
    )
    await db_session.execute(
        insert(Event).values(
            id=uuid.uuid4(),
            source="other_source",
            event_type="PositionReport",
            payload={"test": True},
            dedup_key="mmsi:2",
        )
    )
    await db_session.commit()

    # Test filtering by source
    response = await client.get("/events?source=aisstream")
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 1
    assert data["total_count"] == 1
    assert data["events"][0]["source"] == "aisstream"


@pytest.mark.asyncio
async def test_events_filter_by_event_type(client: AsyncClient, db_session: AsyncSession):
    """Test filtering events by event type."""
    # Insert events with different types
    await db_session.execute(
        insert(Event).values(
            id=uuid.uuid4(),
            source="aisstream",
            event_type="PositionReport",
            payload={"test": True},
            dedup_key="mmsi:1",
        )
    )
    await db_session.execute(
        insert(Event).values(
            id=uuid.uuid4(),
            source="aisstream",
            event_type="VesselInfo",
            payload={"test": True},
            dedup_key="mmsi:2",
        )
    )
    await db_session.commit()

    # Test filtering by event type
    response = await client.get("/events?event_type=PositionReport")
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 1
    assert data["total_count"] == 1
    assert data["events"][0]["event_type"] == "PositionReport"


@pytest.mark.asyncio
async def test_events_filter_by_time_range(client: AsyncClient, db_session: AsyncSession):
    """Test filtering events by time range."""
    base_time = datetime.utcnow()
    
    # Insert events at different times
    await db_session.execute(
        insert(Event).values(
            id=uuid.uuid4(),
            source="aisstream",
            event_type="PositionReport",
            payload={"test": True},
            dedup_key="mmsi:1",
            received_at=base_time - timedelta(hours=2),
        )
    )
    await db_session.execute(
        insert(Event).values(
            id=uuid.uuid4(),
            source="aisstream",
            event_type="PositionReport",
            payload={"test": True},
            dedup_key="mmsi:2",
            received_at=base_time,
        )
    )
    await db_session.commit()

    # Test filtering by time range
    start_time = (base_time - timedelta(hours=1)).isoformat()
    response = await client.get(f"/events?start_time={start_time}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 1
    assert data["total_count"] == 1


@pytest.mark.asyncio
async def test_cursor_pagination(client: AsyncClient, db_session: AsyncSession):
    """Test cursor-based pagination."""
    # Insert multiple events with different timestamps
    base_time = datetime.utcnow()
    event_ids = []
    for i in range(5):
        event_id = uuid.uuid4()
        event_ids.append(event_id)
        await db_session.execute(
            insert(Event).values(
                id=event_id,
                source="aisstream",
                event_type="PositionReport",
                payload={"seq": i},
                dedup_key=f"mmsi:{i}",
                received_at=base_time - timedelta(minutes=i),  # Different timestamps
            )
        )
    await db_session.commit()

    # Get first page
    response = await client.get("/events?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 2
    assert data["has_more"] is True
    assert data["next_cursor"] is not None
    
    # Get second page using cursor
    cursor = data["next_cursor"]
    response = await client.get(f"/events?limit=2&cursor={cursor}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 2
    assert data["has_more"] is True
    
    # Get final page
    cursor = data["next_cursor"]
    response = await client.get(f"/events?limit=2&cursor={cursor}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 1
    assert data["has_more"] is False
    assert data["next_cursor"] is None


@pytest.mark.asyncio
async def test_sort_order(client: AsyncClient, db_session: AsyncSession):
    """Test sorting functionality."""
    base_time = datetime.utcnow()
    
    # Insert events at different times
    for i in range(3):
        await db_session.execute(
            insert(Event).values(
                id=uuid.uuid4(),
                source="aisstream",
                event_type="PositionReport",
                payload={"seq": i},
                dedup_key=f"mmsi:{i}",
                received_at=base_time - timedelta(hours=i),
            )
        )
    await db_session.commit()

    # Test descending order (default)
    response = await client.get("/events?sort_order=desc")
    assert response.status_code == 200
    data = response.json()
    times_desc = [event["received_at"] for event in data["events"]]
    assert times_desc == sorted(times_desc, reverse=True)
    
    # Test ascending order
    response = await client.get("/events?sort_order=asc")
    assert response.status_code == 200
    data = response.json()
    times_asc = [event["received_at"] for event in data["events"]]
    assert times_asc == sorted(times_asc)
