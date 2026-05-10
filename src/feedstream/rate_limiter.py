from typing import Dict

import redis.asyncio as redis
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from feedstream.redis_client import get_redis_client


def get_identifier(request) -> str:
    """Get identifier for rate limiting (IP address)."""
    return get_remote_address(request)


async def get_redis_connection() -> redis.Redis:
    """Get Redis connection for rate limiting."""
    redis_client_instance = await get_redis_client()
    return await redis_client_instance.connect()


# Create rate limiter instance
limiter = Limiter(
    key_func=get_identifier,
    storage_uri="redis://localhost:6379/1",  # Use separate Redis DB for rate limiting
    default_limits=["1000/hour"]  # Default limit
)


# Rate limit configurations
RATE_LIMITS: Dict[str, str] = {
    "ops": "1000/hour",      # Health endpoints
    "events": "100/minute",  # Event querying endpoints
    "default": "1000/hour",  # Everything else
}


def get_rate_limit(tag: str) -> str:
    """Get rate limit for endpoint tag."""
    return RATE_LIMITS.get(tag, RATE_LIMITS["default"])


# Rate limit exception handler
async def rate_limit_exceeded_handler(request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded."""
    from fastapi import Request
    from fastapi.responses import JSONResponse
    
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "error": f"Too many requests. Limit: {exc.detail}",
            "retry_after": exc.detail.split(" ")[-1] if exc.detail else "60"
        },
        headers={"Retry-After": "60"}
    )
