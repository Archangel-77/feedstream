import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from limits.storage import storage_from_string
from limits.strategies import FixedWindowRateLimiter

from feedstream.main import app, limiter


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_429():
    @app.get("/__test_rate_limit")
    @limiter.limit("2/minute")
    async def _rate_limited_endpoint(request: Request) -> dict[str, bool]:
        return {"ok": True}

    previous_storage = limiter._storage
    previous_storage_uri = limiter._storage_uri
    previous_limiter = limiter._limiter
    previous_enabled = limiter.enabled

    in_memory_storage = storage_from_string("memory://")
    limiter._storage = in_memory_storage
    limiter._storage_uri = "memory://"
    limiter._limiter = FixedWindowRateLimiter(in_memory_storage)
    limiter.enabled = True

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/__test_rate_limit")).status_code == 200
            assert (await client.get("/__test_rate_limit")).status_code == 200
            third_response = await client.get("/__test_rate_limit")
            assert third_response.status_code == 429
            assert third_response.json()["detail"] == "Rate limit exceeded"
            assert "Retry-After" in third_response.headers
    finally:
        limiter._storage = previous_storage
        limiter._storage_uri = previous_storage_uri
        limiter._limiter = previous_limiter
        limiter.enabled = previous_enabled
        app.router.routes = [route for route in app.router.routes if route.path != "/__test_rate_limit"]
