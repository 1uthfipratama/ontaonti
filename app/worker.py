"""arq worker: `arq app.worker.WorkerSettings`.

Without REDIS_URL (tests), app.queue runs these same functions in-process.
"""

import asyncio
import logging

from app.config import settings
from app.logging_setup import setup_logging

log = logging.getLogger("onti.worker")


async def handle_inbound(ctx, message_id: int) -> None:
    from app.bot.pipeline import handle_inbound as run

    await run(message_id)


JOBS = {
    "handle_inbound": handle_inbound,
}


async def startup(ctx) -> None:
    setup_logging()
    log.info("worker starting (provider=%s)", settings.llm_provider)
    # Load the embedder and index once, so the first answer isn't slow.
    try:
        from app.bot import rag_service

        await asyncio.to_thread(rag_service.retrieve, "TBC", 1)
        log.info("knowledge-base index loaded")
    except Exception:
        log.exception("knowledge-base index not ready; run scripts/reindex_kb.py")


class WorkerSettings:
    functions = list(JOBS.values())
    on_startup = startup
    max_jobs = settings.worker_max_jobs
    job_timeout = 180
    keep_result = 3600  # arq keeps job ids this long: re-enqueues with the same id are dropped
    if settings.redis_url:
        from arq.connections import RedisSettings

        redis_settings = RedisSettings.from_dsn(settings.redis_url)
