import json
from typing import Any

import redis.asyncio as redis
from redis.asyncio import Redis

from feedstream.observability.metrics import (
    METRIC_CACHE_HITS_TOTAL,
    METRIC_CACHE_MISSES_TOTAL,
    observe_cache_invalidation,
)
from feedstream.settings import Settings


class RedisClient:
    """Async Redis client with caching utilities."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Redis | None = None
        self._hits = 0
        self._misses = 0

    async def connect(self) -> Redis:
        """Initialize Redis connection."""
        if self._client is None:
            self._client = redis.from_url(
                self.settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None

    async def get(self, key: str) -> Any | None:
        """Get value from Redis cache."""
        client = await self.connect()
        try:
            value = await client.get(key)
            if value is None:
                self._misses += 1
                METRIC_CACHE_MISSES_TOTAL.inc()
                return None
            self._hits += 1
            METRIC_CACHE_HITS_TOTAL.inc()
            return json.loads(value)
        except (json.JSONDecodeError, redis.RedisError):
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in Redis cache with TTL."""
        client = await self.connect()
        try:
            serialized = json.dumps(value, default=str)
            return await client.setex(key, ttl, serialized)
        except (TypeError, ValueError, redis.RedisError):
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from Redis cache."""
        client = await self.connect()
        try:
            return bool(await client.delete(key))
        except redis.RedisError:
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern."""
        client = await self.connect()
        try:
            keys = await client.keys(pattern)
            if keys:
                deleted = await client.delete(*keys)
                observe_cache_invalidation(int(deleted or 0))
                return int(deleted or 0)
            return 0
        except redis.RedisError:
            return 0

    def generate_cache_key(self, prefix: str, **kwargs) -> str:
        """Generate cache key from parameters."""
        # Sort kwargs for consistent keys
        sorted_params = sorted(kwargs.items())
        param_str = ":".join(f"{k}={v}" for k, v in sorted_params if v is not None)
        return f"{prefix}:{param_str}" if param_str else prefix

    def get_cache_stats(self) -> dict[str, int]:
        return {
            "hits": self._hits,
            "misses": self._misses,
        }


# Global Redis client instance
redis_client: RedisClient | None = None


async def get_redis_client() -> RedisClient:
    """Get or create Redis client instance."""
    global redis_client
    if redis_client is None:
        from feedstream.settings import get_settings

        settings = get_settings()
        redis_client = RedisClient(settings)
    return redis_client
