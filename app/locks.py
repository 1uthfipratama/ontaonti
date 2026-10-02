"""Per-conversation lock so two quick messages from one person are answered in order."""

import asyncio
import logging
from collections import defaultdict
from contextlib import asynccontextmanager

from app.redis_client import get_redis

log = logging.getLogger("onti.locks")
_local: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


@asynccontextmanager
async def conversation_lock(conversation_id: int):
    redis = get_redis()
    if redis is None:
        async with _local[conversation_id]:
            yield
        return
    lock = redis.lock(f"onti:lock:conv:{conversation_id}", timeout=180, blocking_timeout=150)
    acquired = await lock.acquire()
    if not acquired:
        log.warning("conversation %s lock timed out; continuing unlocked", conversation_id)
    try:
        yield
    finally:
        if acquired:
            try:
                await lock.release()
            except Exception:
                log.debug("lock release failed (expired?)", exc_info=True)
