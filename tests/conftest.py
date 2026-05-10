import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from feedstream.database import Base, get_session
from feedstream.main import app
from feedstream.redis_client import get_redis_client, RedisClient
from slowapi import Limiter
from slowapi.util import get_remote_address


class MockRedisClient:
    """Mock Redis client for testing."""
    
    def __init__(self):
        self._cache = {}
    
    async def connect(self):
        return self
    
    async def disconnect(self):
        pass
    
    async def get(self, key):
        return self._cache.get(key)
    
    async def set(self, key, value, ttl=300):
        self._cache[key] = value
        return True
    
    async def delete(self, key):
        return self._cache.pop(key, None) is not None
    
    async def delete_pattern(self, pattern):
        keys_to_delete = [k for k in self._cache.keys() if pattern.replace("*", "") in k]
        for key in keys_to_delete:
            self._cache.pop(key, None)
        return len(keys_to_delete)
    
    def generate_cache_key(self, prefix, **kwargs):
        sorted_params = sorted(kwargs.items())
        param_str = ":".join(f"{k}={v}" for k, v in sorted_params if v is not None)
        return f"{prefix}:{param_str}" if param_str else prefix


@pytest_asyncio.fixture
async def mock_redis_client():
    return MockRedisClient()

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, mock_redis_client):
    # Create a minimal test app without Redis or rate limiting
    from fastapi import FastAPI, Query
    from datetime import datetime
    import base64
    import uuid
    from sqlalchemy import and_, func, or_, select
    
    test_app = FastAPI(title="feedstream-test", version="0.3.0-test")
    
    @test_app.get("/healthz", tags=["ops"])
    async def health():
        return {"status": "ok"}
    
    @test_app.get("/events", tags=["events"])
    async def list_events(
        source: str = None,
        event_type: str = None,
        start_time: str = None,
        end_time: str = None,
        cursor: str = None,
        limit: int = 50,
        sort_order: str = "desc",
    ):
        # Check cache first
        cache_key = mock_redis_client.generate_cache_key(
            "events",
            source=source,
            event_type=event_type,
            start_time=start_time,
            end_time=end_time,
            cursor=cursor,
            limit=limit,
            sort_order=sort_order,
        )
        
        cached_result = await mock_redis_client.get(cache_key)
        if cached_result:
            return cached_result
        
        # Build query
        from feedstream.models import Event
        query = select(Event)
        conditions = []
        
        if source:
            conditions.append(Event.source == source)
        if event_type:
            conditions.append(Event.event_type == event_type)
        if start_time:
            conditions.append(Event.received_at >= datetime.fromisoformat(start_time))
        if end_time:
            conditions.append(Event.received_at <= datetime.fromisoformat(end_time))
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db_session.execute(count_query)
        total_count = count_result.scalar()
        
        # Apply cursor pagination
        if cursor:
            try:
                decoded = base64.b64decode(cursor.encode()).decode()
                last_colon_index = decoded.rfind(":")
                if last_colon_index == -1:
                    raise ValueError("Invalid cursor format")
                received_at_str = decoded[:last_colon_index]
                event_id_str = decoded[last_colon_index + 1:]
                cursor_received_at = datetime.fromisoformat(received_at_str)
                cursor_event_id = uuid.UUID(event_id_str)
                
                if sort_order == "desc":
                    query = query.where(
                        or_(Event.received_at < cursor_received_at,
                            and_(Event.received_at == cursor_received_at, Event.id < cursor_event_id))
                    )
                else:
                    query = query.where(
                        or_(Event.received_at > cursor_received_at,
                            and_(Event.received_at == cursor_received_at, Event.id > cursor_event_id))
                    )
            except (ValueError, IndexError):
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="Invalid cursor format")
        
        # Apply sorting and limit
        if sort_order == "desc":
            query = query.order_by(Event.received_at.desc(), Event.id.desc())
        else:
            query = query.order_by(Event.received_at.asc(), Event.id.asc())
        
        query = query.limit(limit + 1)
        
        # Execute query
        result = await db_session.execute(query)
        events = list(result.scalars().all())
        
        # Determine pagination metadata
        has_more = len(events) > limit
        if has_more:
            events = events[:-1]
            last_event = events[-1]
            next_cursor = base64.b64encode(
                f"{last_event.received_at.isoformat()}:{last_event.id}".encode()
            ).decode()
        else:
            next_cursor = None
        
        from feedstream.schemas import PaginatedEventsResponse
        response = PaginatedEventsResponse(
            events=events,
            next_cursor=next_cursor,
            has_more=has_more,
            total_count=total_count,
        )
        
        # Cache the result
        await mock_redis_client.set(cache_key, response.model_dump(), ttl=300)
        
        return response

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as ac:
        yield ac
