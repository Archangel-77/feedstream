import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from feedstream.database import Base, get_session
from feedstream.main import app


class MockRedisClient:
    """Mock Redis client for testing."""

    def __init__(self):
        self._cache = {}
        self._ttls = {}
        self._hits = 0
        self._misses = 0

    async def connect(self):
        return self

    async def disconnect(self):
        pass

    async def get(self, key):
        value = self._cache.get(key)
        if value is None:
            self._misses += 1
            return None
        self._hits += 1
        return value

    async def set(self, key, value, ttl=300):
        self._cache[key] = value
        self._ttls[key] = ttl
        return True

    async def delete(self, key):
        self._ttls.pop(key, None)
        return self._cache.pop(key, None) is not None

    async def delete_pattern(self, pattern):
        substring = pattern.replace("*", "")
        keys_to_delete = [k for k in self._cache if substring in k]
        for key in keys_to_delete:
            self._cache.pop(key, None)
            self._ttls.pop(key, None)
        return len(keys_to_delete)

    def generate_cache_key(self, prefix, **kwargs):
        sorted_params = sorted(kwargs.items())
        param_str = ":".join(f"{k}={v}" for k, v in sorted_params if v is not None)
        return f"{prefix}:{param_str}" if param_str else prefix

    def get_cache_stats(self):
        return {"hits": self._hits, "misses": self._misses}


@pytest_asyncio.fixture
async def mock_redis_client():
    return MockRedisClient()


@pytest_asyncio.fixture
async def patched_worker_redis(mock_redis_client, monkeypatch):
    """Point the worker's cache client at the in-memory mock Redis.

    Direct write tests call ``worker.write_event`` which performs cache
    invalidation; routing it through the mock keeps tests hermetic and avoids
    a real Redis connection tied to a short-lived event loop.
    """

    async def _mock_get_redis_client():
        return mock_redis_client

    monkeypatch.setattr("feedstream.worker.get_redis_client", _mock_get_redis_client)
    return mock_redis_client


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
