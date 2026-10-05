"""Dashboard numbers. Days and months follow the TIMEZONE setting (Asia/Jakarta)."""

import statistics
from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import CASE_CLAIMED, CASE_OPEN, CHANNELS, DIR_IN, DIR_NOTE, DIR_OUT
from app.db import as_utc, get_session, utcnow
from app.deps import any_staff
from app.models import (
    BroadcastRecipient,
    Case,
    Contact,
    Conversation,
    LlmUsage,
    Message,
    StaffUser,
)
from app.services import limits, settings_service

router = APIRouter(tags=["dashboard"])


async def _active_by_channel(session: AsyncSession, since) -> dict[str, int]:
    """Conversations with at least one inbound message since `since`, per channel."""
    rows = (
        await session.execute(
            select(Conversation.channel, func.count(func.distinct(Message.conversation_id)))
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Message.direction == DIR_IN, Message.created_at >= since)
            .group_by(Conversation.channel)
        )
    ).all()
    out = {ch: 0 for ch in CHANNELS}
    out.update({ch: n for ch, n in rows})
    return out


async def daily_conversations(session: AsyncSession, days: int = 14) -> list[dict]:
    """Conversations with at least one inbound message, per local day, oldest first."""
    tz = ZoneInfo(limits.settings.timezone)
    today = limits.day_start_utc().astimezone(tz).date()
    start = limits.day_start_utc() - timedelta(days=days - 1)
    rows = (
        await session.execute(
            select(Message.conversation_id, Message.created_at).where(
                Message.direction == DIR_IN, Message.created_at >= start
            )
        )
    ).all()
    seen: dict = {}
    for conv_id, created in rows:
        seen.setdefault(as_utc(created).astimezone(tz).date(), set()).add(conv_id)
    out = []
    for i in range(days):
        day = today - timedelta(days=days - 1 - i)
        out.append({"day": day.isoformat(), "count": len(seen.get(day, ()))})
    return out


async def first_response_times(session: AsyncSession, days: int = 30) -> dict:
    """Median seconds from a user's (first unanswered) message to the next reply,
    split by who replied: bot or human staff."""
    rows = (
        await session.execute(
            select(
                Message.conversation_id, Message.direction, Message.sender_type, Message.created_at
            )
            .where(
                Message.created_at >= utcnow() - timedelta(days=days), Message.direction != DIR_NOTE
            )
            .order_by(Message.conversation_id, Message.created_at, Message.id)
            .limit(20000)
        )
    ).all()
    waiting: dict[int, object] = {}
    samples: dict[str, list[float]] = {"bot": [], "agent": []}
    for conv_id, direction, sender, created in rows:
        created = as_utc(created)
        if direction == DIR_IN:
            waiting.setdefault(conv_id, created)
        elif direction == DIR_OUT and sender in samples and conv_id in waiting:
            samples[sender].append((created - waiting.pop(conv_id)).total_seconds())

    def med(xs: list[float]) -> float | None:
        return round(statistics.median(xs), 1) if xs else None

    return {
        "bot_median_s": med(samples["bot"]),
        "human_median_s": med(samples["agent"]),
        "bot_samples": len(samples["bot"]),
        "human_samples": len(samples["agent"]),
        "days": days,
    }


@router.get("/dashboard")
async def dashboard(
    user: StaffUser = Depends(any_staff), session: AsyncSession = Depends(get_session)
):
    cfg = await settings_service.load(session)
    today, month = limits.day_start_utc(), limits.month_start_utc()

    cases = dict(
        (
            await session.execute(
                select(Case.severity, func.count())
                .where(Case.status.in_((CASE_OPEN, CASE_CLAIMED)))
                .group_by(Case.severity)
            )
        ).all()
    )

    budget = await limits.budget(session, cfg)
    by_purpose = dict(
        (
            await session.execute(
                select(LlmUsage.purpose, func.sum(LlmUsage.cost_idr))
                .where(LlmUsage.created_at >= month)
                .group_by(LlmUsage.purpose)
            )
        ).all()
    )
    llm_calls, llm_errors = (
        await session.execute(
            select(func.count(), func.count().filter(LlmUsage.ok.is_(False))).where(
                LlmUsage.created_at >= month
            )
        )
    ).one()

    wa_out = (
        await session.execute(
            select(func.count())
            .select_from(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Conversation.channel == "whatsapp",
                Conversation.simulated.is_(False),
                Message.direction == DIR_OUT,
                Message.created_at >= month,
            )
        )
    ).scalar_one()
    wa_templates = (
        await session.execute(
            select(func.count())
            .select_from(BroadcastRecipient)
            .where(BroadcastRecipient.sent_at >= month)
        )
    ).scalar_one()

    contacts_total, opted_out, subscribed = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(Contact.opted_out.is_(True)),
                func.count().filter(Contact.broadcast_opt_in.is_(True)),
            )
        )
    ).one()

    return {
        "timezone": limits.settings.timezone,
        "conversations": {
            "today": await _active_by_channel(session, today),
            "month": await _active_by_channel(session, month),
            "daily": await daily_conversations(session),
        },
        "open_cases": {s: cases.get(s, 0) for s in ("emergency", "high", "low")},
        "response_times": await first_response_times(session),
        "ai": {
            "spent_idr": round(budget.spent_idr, 2),
            "budget_idr": budget.budget_idr,
            "ratio": round(budget.ratio, 4),
            "alert_ratio": float(cfg["budget_alert_ratio"]),
            "over": budget.over,
            "fallback_mode": cfg["budget_fallback_mode"],
            "by_purpose": {k: round(v or 0, 2) for k, v in by_purpose.items()},
            "calls": llm_calls or 0,
            "errors": int(llm_errors or 0),
        },
        "whatsapp": {
            "messages_month": wa_out,
            "template_messages_month": wa_templates,
            "free_tier": int(cfg["wa_free_tier_messages"]),
        },
        "contacts": {"total": contacts_total, "opted_out": opted_out, "subscribed": subscribed},
    }
