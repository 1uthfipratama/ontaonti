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


async def process_webhook(ctx, channel: str, payload: dict) -> None:
    """Statuses first, then new messages: store, mark read, run the bot."""
    from app.bot.pipeline import handle_inbound as run
    from app.channels.base import SendError
    from app.channels.registry import adapter_for_channel
    from app.db import SessionLocal
    from app.services import statuses
    from app.services.inbound import ingest

    adapter = adapter_for_channel(channel)
    new_ids: list[int] = []
    async with SessionLocal() as s:
        for st in adapter.parse_statuses(payload):
            await statuses.apply_status(s, st)
        if hasattr(adapter, "parse_reads"):
            for user_id, watermark in adapter.parse_reads(payload):
                await statuses.apply_read_watermark(s, channel, user_id, watermark)
        for im in adapter.parse_inbound(payload):
            res = await ingest(s, im)
            if res is None:
                continue  # duplicate delivery
            new_ids.append(res.message.id)
            try:
                await adapter.mark_read(im.external_message_id)
            except SendError as e:
                log.warning("mark read failed: %s", e)
    for message_id in new_ids:
        await run(message_id)


async def send_broadcast_recipient(ctx, recipient_id: int) -> None:
    """One template message. Retryable failures (429/5xx/network) back off and retry."""
    from app.services.broadcasts import RetryLater, send_one

    for _ in range(settings.broadcast_max_attempts):
        try:
            await send_one(recipient_id)
            return
        except RetryLater as e:
            if settings.redis_url:
                from arq import Retry

                raise Retry(defer=e.delay) from e
            # in-process (tests): retry straight away


async def reindex_kb(ctx) -> None:
    from app.services import knowledge

    await knowledge.reindex()


JOBS = {
    "handle_inbound": handle_inbound,
    "reindex_kb": reindex_kb,
    "process_webhook": process_webhook,
    "send_broadcast_recipient": send_broadcast_recipient,
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
    job_timeout = 600  # a knowledge-base re-index embeds every passage
    max_tries = 6  # arq-level retries (broadcast backoff); other jobs don't raise Retry
    keep_result = 3600  # arq keeps job ids this long: re-enqueues with the same id are dropped
    if settings.redis_url:
        from arq.connections import RedisSettings

        redis_settings = RedisSettings.from_dsn(settings.redis_url)
