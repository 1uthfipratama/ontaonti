"""One shared async Redis client per process (None when REDIS_URL is empty)."""

import redis.asyncio as aioredis

from app.config import settings

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis | None:
    global _client
    if not settings.redis_url:
        return None
    if _client is None:
        _client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _client
