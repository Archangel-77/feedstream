import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from feedstream.database import Base, get_session
from feedstream.main import app


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
async def client(db_session: AsyncSession, mock_redis_client, monkeypatch):
    async def _override_get_session():
        yield db_session

    async def _mock_get_redis_client():
        return mock_redis_client

    app.dependency_overrides[get_session] = _override_get_session
    # Use fake Redis in API and worker modules.
    monkeypatch.setattr("feedstream.main.get_redis_client", _mock_get_redis_client)
    monkeypatch.setattr("feedstream.worker.get_redis_client", _mock_get_redis_client)
    # Disable rate limiting for general endpoint tests.
    app.state.limiter.enabled = False

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    app.state.limiter.enabled = True
