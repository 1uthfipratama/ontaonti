"""Cost controls: monthly AI budget and per-contact message limits.

Budget: spend = sum of llm_usage.cost_idr this month (Asia/Jakarta calendar).
- >= budget_alert_ratio (80%): one alert per month (SSE badge + email).
- >= 100%: budget_fallback_mode decides: "classifier_model" answers with the
  cheaper classifier model; "fixed_reply" sends the fixed "staf kami akan
  menghubungi" text and opens a case (no LLM calls at all).
monthly_budget_idr = 0 means no budget (never over).

Limits (per contact, inbound messages): rate_limit_count per
rate_limit_window_minutes, and daily_message_cap per day. The polite notice is
sent once, on the first message over the limit; later ones are stored silently.
Keyword safety rules run before any of this and are never limited.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import events, notify
from app.config import settings
from app.constants import DIR_IN
from app.db import utcnow
from app.models import Conversation, LlmUsage, Message
from app.services import settings_service
from app.services.settings_service import Config

log = logging.getLogger("onti.limits")


def local_now() -> datetime:
    return utcnow().astimezone(ZoneInfo(settings.timezone))


def day_start_utc(now: datetime | None = None) -> datetime:
    n = (now or local_now()).astimezone(ZoneInfo(settings.timezone))
    return n.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def month_start_utc(now: datetime | None = None) -> datetime:
    n = (now or local_now()).astimezone(ZoneInfo(settings.timezone))
    return n.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


# --- budget ---------------------------------------------------------------------------


@dataclass
class Budget:
    spent_idr: float
    budget_idr: float

    @property
    def ratio(self) -> float:
        return self.spent_idr / self.budget_idr if self.budget_idr > 0 else 0.0

    @property
    def over(self) -> bool:
        return self.budget_idr > 0 and self.spent_idr >= self.budget_idr


async def month_spend(session: AsyncSession) -> float:
    total = (
        await session.execute(
            select(func.coalesce(func.sum(LlmUsage.cost_idr), 0.0)).where(
                LlmUsage.created_at >= month_start_utc()
            )
        )
    ).scalar_one()
    return float(total or 0.0)


async def budget(session: AsyncSession, cfg: Config) -> Budget:
    return Budget(await month_spend(session), float(cfg["monthly_budget_idr"]))


async def maybe_alert(session: AsyncSession, cfg: Config, b: Budget) -> bool:
    """Alert once per month when spend crosses the alert ratio."""
    if b.budget_idr <= 0 or b.ratio < float(cfg["budget_alert_ratio"]):
        return False
    month = local_now().strftime("%Y-%m")
    if await settings_service.get_value(session, "budget_alert_month") == month:
        return False
    await settings_service.set_value(session, "budget_alert_month", month)
    await session.commit()
    pct = round(b.ratio * 100)
    log.warning("AI budget alert: %s%% of monthly budget used", pct)
    await events.publish("budget.alert", percent=pct, spent_idr=round(b.spent_idr),
                         budget_idr=round(b.budget_idr))  # fmt: skip
    await notify.email_staff(
        f"[Onti Erlina] AI budget at {pct}%",
        f"AI spend this month: Rp {b.spent_idr:,.0f} of Rp {b.budget_idr:,.0f} ({pct}%).\n"
        f"At 100% the bot switches to: {cfg['budget_fallback_mode']}.\n"
        f"Dashboard: {settings.web_base_url}/dashboard",
    )
    return True


# --- per-contact limits ------------------------------------------------------------------


async def inbound_since(session: AsyncSession, contact_id: int, since: datetime) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Conversation.contact_id == contact_id,
                Message.direction == DIR_IN,
                Message.created_at >= since,
            )
        )
    ).scalar_one()


@dataclass
class LimitResult:
    limited: bool = False
    notify: bool = False  # first message over the limit: send the polite notice
    kind: str = ""  # rate | daily


async def check(session: AsyncSession, contact_id: int, cfg: Config) -> LimitResult:
    """Counts include the current message."""
    window = timedelta(minutes=int(cfg["rate_limit_window_minutes"]))
    n_window = await inbound_since(session, contact_id, utcnow() - window)
    rate_max = int(cfg["rate_limit_count"])
    if rate_max and n_window > rate_max:
        return LimitResult(True, n_window == rate_max + 1, "rate")
    n_day = await inbound_since(session, contact_id, day_start_utc())
    day_max = int(cfg["daily_message_cap"])
    if day_max and n_day > day_max:
        return LimitResult(True, n_day == day_max + 1, "daily")
    return LimitResult()
