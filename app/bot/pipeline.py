"""What happens to each inbound message (runs in the worker).

Phase 1: HUMAN mode -> store + notify only; BOT mode -> RAG answer.
"""

import logging

from app import events
from app.bot import answer
from app.bot.language import detect
from app.constants import MODE_HUMAN, SENDER_BOT
from app.db import SessionLocal
from app.llm import LLMError
from app.locks import conversation_lock
from app.models import Conversation, Message
from app.services import outbound, settings_service

log = logging.getLogger("onti.pipeline")


async def handle_inbound(message_id: int) -> None:
    async with SessionLocal() as session:
        msg = await session.get(Message, message_id)
        if msg is None:
            log.warning("message %s not found", message_id)
            return
        async with conversation_lock(msg.conversation_id):
            conv = await session.get(Conversation, msg.conversation_id, populate_existing=True)
            await _handle(session, conv, msg)


async def _handle(session, conv: Conversation, msg: Message) -> None:
    cfg = await settings_service.load(session)
    lang = detect(msg.text)

    if conv.mode == MODE_HUMAN:
        await events.publish("conversation.needs_human", conversation_id=conv.id, message_id=msg.id)
        return

    try:
        ans = await answer.generate(session, conv, msg, cfg, cfg.answer_model)
    except LLMError as e:
        log.warning("answer failed for message %s: %s", msg.id, e)
        await outbound.send_text(
            session, conv, cfg.text("budget_fallback_reply", lang), sender_type=SENDER_BOT,
            meta={"fallback": "llm_error"},
        )  # fmt: skip
        return
    await outbound.send_text(
        session,
        conv,
        ans.text,
        sender_type=SENDER_BOT,
        meta={"sources": ans.sources, "model": ans.model},
        tokens_in=ans.tokens_in,
        tokens_out=ans.tokens_out,
        cost_idr=ans.cost_idr,
    )
