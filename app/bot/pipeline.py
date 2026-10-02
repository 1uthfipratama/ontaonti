"""What happens to each inbound message (runs in the worker).

Order matters:
0. STOP / BERHENTI -> opted out (confirm once, then silence); MULAI -> back in.
   An opted-out contact gets no replies, but keyword flags still alert staff.
1. keyword safety flags (always, even over budget or in HUMAN mode)
   + first contact: privacy/consent notice; LANGGANAN -> broadcast opt-in
2. HUMAN mode -> store + notify only (a high/emergency keyword still opens a case)
   + non-text messages get a polite "text only" reply
3. keyword high/emergency -> fixed safety reply + case + HUMAN
   then cost controls: per-contact rate limit and daily cap (polite notice once);
   AI budget (80% -> alert once a month; 100% -> classifier model, or a fixed
   reply + case with no LLM call at all)
4. LLM classifier; final severity = max(keyword, classifier); high+ -> step 3
5. RAG answer (last N turns, fixed k, capped input/output)
"""

import logging

from app import events
from app.bot import answer, safety
from app.bot.language import detect
from app.constants import MODE_HUMAN, SENDER_BOT, at_least
from app.db import SessionLocal
from app.llm import LLMError
from app.locks import conversation_lock
from app.models import Conversation, Message
from app.services import cases, consent, limits, outbound, settings_service
from app.services.settings_service import Config

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
    text = msg.text or ""
    lang = detect(text)
    is_text = msg.kind == "text"
    contact = conv.contact
    cmd = consent.command(text) if is_text else None

    # 0. opt-out / opt-in
    if cmd == "stop":
        already = contact.opted_out
        consent.opt_out(session, contact, conv.channel)
        await outbound.add_note(session, conv, "Kontak membalas STOP: berhenti menerima pesan")
        await session.commit()
        if not already:
            await outbound.send_text(session, conv, cfg.text("optout_confirm", lang),
                                     sender_type=SENDER_BOT, meta={"consent": "opt_out"})  # fmt: skip
        return
    if contact.opted_out:
        if cmd == "start":
            consent.opt_in(session, contact, conv.channel)
            await outbound.add_note(session, conv, "Kontak membalas MULAI: aktif kembali")
            await session.commit()
            await outbound.send_text(session, conv, cfg.text("optin_confirm", lang),
                                     sender_type=SENDER_BOT, meta={"consent": "opt_in"})  # fmt: skip
            return
        kw = safety.keyword_flag(text, cfg.flag_rules) if is_text else safety.NONE
        if at_least(kw.severity, "high"):  # no reply (they said STOP), but staff must know
            cases.flag_message(conv, msg, kw)
            await cases.open_case(session, conv, msg, kw.severity, kw.category or "OTHER",
                                  f"{kw.reason} (contact opted out)", to_human=False)  # fmt: skip
        await events.publish("conversation.needs_human", conversation_id=conv.id, message_id=msg.id)
        return

    # 1. keyword rules: free, always on
    kw = safety.keyword_flag(text, cfg.flag_rules) if is_text else safety.NONE
    if kw.severity != "none":
        cases.flag_message(conv, msg, kw)
        await session.commit()

    # first contact: privacy / consent notice before anything else
    if not await consent.notice_sent(session, contact.id):
        consent.record(session, contact, "privacy_notice", "notified", "system", conv.channel)
        await session.commit()
        await outbound.send_text(session, conv, cfg.text("consent_notice", lang),
                                 sender_type=SENDER_BOT, meta={"consent": "notice"})  # fmt: skip

    if cmd == "subscribe":
        consent.subscribe(session, contact, True, conv.channel, "keyword")
        await session.commit()
        await outbound.send_text(session, conv, cfg.text("subscribe_confirm", lang),
                                 sender_type=SENDER_BOT, meta={"consent": "broadcast"})  # fmt: skip
        await events.publish("contact.updated", contact_id=contact.id)
        return

    # 2. staff have the conversation: no automated replies
    if conv.mode == MODE_HUMAN:
        if at_least(kw.severity, "high"):
            await cases.open_case(session, conv, msg, kw.severity, kw.category or "OTHER",
                                  kw.reason, to_human=True)  # fmt: skip
        await events.publish("conversation.needs_human", conversation_id=conv.id, message_id=msg.id)
        return

    if not is_text:
        await outbound.send_text(session, conv, cfg.text("non_text_reply", lang),
                                 sender_type=SENDER_BOT, meta={"non_text": msg.kind})  # fmt: skip
        return

    # 3. keyword emergency / high
    if at_least(kw.severity, "high"):
        await safety_reply(session, conv, msg, kw, cfg, lang)
        return

    # cost controls (safety keywords have already run)
    lim = await limits.check(session, contact.id, cfg)
    if lim.limited:
        if lim.notify:
            key = "rate_limit_reply" if lim.kind == "rate" else "daily_cap_reply"
            await outbound.send_text(session, conv, cfg.text(key, lang), sender_type=SENDER_BOT,
                                     meta={"limit": lim.kind})  # fmt: skip
        await events.publish("conversation.updated", conversation_id=conv.id)
        return
    budget = await limits.budget(session, cfg)
    await limits.maybe_alert(session, cfg, budget)
    if budget.over and cfg["budget_fallback_mode"] == "fixed_reply":
        await outbound.send_text(session, conv, cfg.text("budget_fallback_reply", lang),
                                 sender_type=SENDER_BOT, meta={"fallback": "budget"})  # fmt: skip
        await cases.open_case(session, conv, msg, "low", "BUDGET",
                              "AI budget exhausted: fixed reply sent", to_human=False)  # fmt: skip
        return
    answer_model = cfg.classifier_model if budget.over else cfg.answer_model

    # 4. classifier
    if is_text and cfg["classifier_enabled"]:
        cls = await safety.classify(
            text[: cfg["max_input_chars"]], cfg.classifier_model, conv.id, msg.id
        )
        final = safety.combine(kw, cls)
        if final.severity != "none":
            cases.flag_message(conv, msg, final)
            await session.commit()
        if at_least(final.severity, "high"):
            await safety_reply(session, conv, msg, final, cfg, lang)
            return

    # 5. answer
    await bot_answer(session, conv, msg, cfg, lang, answer_model)


async def safety_reply(session, conv, msg, flag: safety.Flag, cfg: Config, lang: str) -> None:
    """FIXED text from settings (never LLM-generated), then a case + HUMAN mode."""
    await outbound.send_text(
        session, conv, cfg.text(safety.reply_key(flag), lang), sender_type=SENDER_BOT,
        meta={"safety_reply": flag.category, "severity": flag.severity},
    )  # fmt: skip
    await cases.open_case(session, conv, msg, flag.severity, flag.category or "OTHER",
                          flag.reason, to_human=True)  # fmt: skip


async def bot_answer(session, conv, msg, cfg: Config, lang: str, model: str) -> None:
    try:
        ans = await answer.generate(session, conv, msg, cfg, model)
    except LLMError as e:
        log.warning("answer failed for message %s: %s", msg.id, e)
        await outbound.send_text(
            session, conv, cfg.text("budget_fallback_reply", lang), sender_type=SENDER_BOT,
            meta={"fallback": "llm_error"},
        )  # fmt: skip
        # The reply promises a staff follow-up: make sure someone sees it.
        await cases.open_case(session, conv, msg, "low", "BOT_ERROR", f"LLM error: {e}",
                              to_human=False)  # fmt: skip
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
