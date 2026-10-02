"""Live updates for the admin UI: publish small events, stream them over SSE.

The worker and the API are separate processes, so events go through Redis
pub/sub. Without Redis (tests, single-process dev) an in-memory broker is used.
Events carry ids only; the UI refetches what changed.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from app.redis_client import get_redis

log = logging.getLogger("onti.events")
CHANNEL = "onti:events"
_local_subscribers: set[asyncio.Queue] = set()


async def publish(event_type: str, **data) -> None:
    event = {"type": event_type, **data}
    redis = get_redis()
    if redis is not None:
        try:
            await redis.publish(CHANNEL, json.dumps(event, default=str))
        except Exception:  # live updates are best effort, never break the caller
            log.warning("publish failed for %s", event_type, exc_info=True)
        return
    for q in list(_local_subscribers):
        q.put_nowait(event)


async def subscribe() -> AsyncIterator[dict]:
    redis = get_redis()
    if redis is None:
        q: asyncio.Queue = asyncio.Queue()
        _local_subscribers.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            _local_subscribers.discard(q)
        return
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL)
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg.get("type") == "message":
                try:
                    yield json.loads(msg["data"])
                except ValueError:
                    continue
    finally:
        await pubsub.unsubscribe(CHANNEL)
        await pubsub.aclose()
