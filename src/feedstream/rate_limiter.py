from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from feedstream.settings import settings


def get_identifier(request) -> str:
    """Get identifier for rate limiting (IP address)."""
    return get_remote_address(request)


def _rate_limit_storage_uri(redis_url: str) -> str:
    """Derive the rate-limit storage URI from the configured Redis URL (DB 1).

    Rate limits are stored in Redis database 1 so they are shared across API
    replicas, while the response cache lives in DB 0.
    """
    base, _, _db = redis_url.rpartition("/")
    if base.startswith("redis"):
        return f"{base}/1"
    # Fallback if the configured URL is malformed.
    return "redis://localhost:6379/1"


# Create rate limiter instance. Storage URI is derived from settings so that
# production replicas share the same Redis backend.
limiter = Limiter(
    key_func=get_identifier,
    storage_uri=_rate_limit_storage_uri(settings.redis_url),
    default_limits=["1000/hour"],  # Default limit
)


# Rate limit configurations
RATE_LIMITS: dict[str, str] = {
    "ops": "1000/hour",  # Health endpoints
    "events": "100/minute",  # Event querying endpoints
    "default": "1000/hour",  # Everything else
}


def get_rate_limit(tag: str) -> str:
    """Get rate limit for endpoint tag."""
    return RATE_LIMITS.get(tag, RATE_LIMITS["default"])


# Rate limit exception handler
async def rate_limit_exceeded_handler(request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded."""
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "error": f"Too many requests. Limit: {exc.detail}",
            "retry_after": exc.detail.split(" ")[-1] if exc.detail else "60",
        },
        headers={"Retry-After": "60"},
    )
