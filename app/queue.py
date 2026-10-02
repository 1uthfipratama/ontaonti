"""Background jobs: arq on Redis in Docker; in-process tasks without Redis (tests).

enqueue("handle_inbound", message_id) runs app.worker.<name>(ctx, *args).
"""

import asyncio
import logging

from app.config import settings

log = logging.getLogger("onti.queue")
_pool = None
_inline_tasks: set[asyncio.Task] = set()


async def _get_pool():
    global _pool
    if _pool is None:
        from arq import create_pool
        from arq.connections import RedisSettings

        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool


async def enqueue(name: str, *args, _job_id: str | None = None, _defer_by: float | None = None):
    if settings.redis_url:
        pool = await _get_pool()
        return await pool.enqueue_job(name, *args, _job_id=_job_id, _defer_by=_defer_by)
    from app import worker

    fn = worker.JOBS[name]

    async def run() -> None:
        try:
            await fn({"job_try": 1}, *args)
        except Exception:
            log.exception("inline job %s failed", name)

    task = asyncio.create_task(run())
    _inline_tasks.add(task)
    task.add_done_callback(_inline_tasks.discard)
    return task


async def drain() -> None:
    """Wait for in-process jobs (and the jobs they enqueue) to finish. Tests only."""
    while _inline_tasks:
        await asyncio.gather(*list(_inline_tasks), return_exceptions=True)
