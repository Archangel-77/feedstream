import json
import uuid
from typing import Any, Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from feedstream.settings import Settings


class RedisClient:
    """Async Redis client with caching utilities."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Optional[Redis] = None
    
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
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache."""
        client = await self.connect()
        try:
            value = await client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except (json.JSONDecodeError, redis.RedisError):
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in Redis cache with TTL."""
        client = await self.connect()
        try:
            serialized = json.dumps(value, default=str)
            return await client.setex(key, ttl, serialized)
        except (json.JSONEncodeError, redis.RedisError):
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
                return await client.delete(*keys)
            return 0
        except redis.RedisError:
            return 0
    
    def generate_cache_key(self, prefix: str, **kwargs) -> str:
        """Generate cache key from parameters."""
        # Sort kwargs for consistent keys
        sorted_params = sorted(kwargs.items())
        param_str = ":".join(f"{k}={v}" for k, v in sorted_params if v is not None)
        return f"{prefix}:{param_str}" if param_str else prefix


# Global Redis client instance
redis_client: Optional[RedisClient] = None


async def get_redis_client() -> RedisClient:
    """Get or create Redis client instance."""
    global redis_client
    if redis_client is None:
        from feedstream.settings import get_settings
        settings = get_settings()
        redis_client = RedisClient(settings)
    return redis_client
