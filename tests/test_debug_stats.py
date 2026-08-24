import pytest
from httpx import AsyncClient

from feedstream.settings import settings


@pytest.mark.asyncio
async def test_debug_stats_requires_auth(client: AsyncClient):
    response = await client.get("/debug/stats")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_debug_stats_with_token(client: AsyncClient):
    response = await client.get(
        "/debug/stats", headers={"X-Debug-Token": settings.debug_stats_token}
    )
    assert response.status_code == 200
    data = response.json()
    assert "worker" in data
    assert "cache" in data
    assert "db_pool" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_debug_stats_reports_real_cache_stats(client: AsyncClient):
    headers = {"X-Debug-Token": settings.debug_stats_token}
    # First request misses and populates the cache; the second request hits it.
    await client.get("/events?limit=10")
    await client.get("/events?limit=10")

    response = await client.get("/debug/stats", headers=headers)
    assert response.status_code == 200
    cache = response.json()["cache"]
    assert cache["hits"] >= 1
    assert cache["misses"] >= 1
