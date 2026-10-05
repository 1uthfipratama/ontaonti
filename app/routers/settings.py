"""Settings: editable runtime settings (stored in the DB) and channel status."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import audit
from app.channels.base import SendError
from app.config import settings
from app.db import get_session
from app.deps import admin_only, client_ip
from app.models import Setting, StaffUser
from app.services import settings_service
from app.services.settings_service import (
    BOOL_KEYS,
    CHOICES,
    DAYS_KEYS,
    DEFAULTS,
    GROUPS,
    NUMBER_KEYS,
    TIME_KEYS,
)

router = APIRouter(prefix="/settings", tags=["settings"])

LABELS = {
    "persona_prompt": "Persona prompt (system prompt for answers)",
    "model_answer": "Answer model (empty = LLM_MODEL_ANSWER / provider default)",
    "model_classifier": "Classifier model (empty = LLM_MODEL_CLASSIFIER / provider default)",
    "history_turns": "Context: last N messages",
    "retrieval_k": "Passages retrieved per answer (fixed k)",
    "max_input_chars": "Max user input sent to the LLM (chars)",
    "max_output_tokens": "Max answer length (tokens)",
    "max_reply_chars": "Max reply length (chars)",
    "classifier_enabled": "LLM safety classifier on",
    "monthly_budget_idr": "Monthly AI budget (IDR, 0 = no limit)",
    "budget_alert_ratio": "Alert at (fraction of budget, e.g. 0.8)",
    "budget_fallback_mode": "At 100% of budget",
    "daily_message_cap": "Per-contact daily message cap",
    "rate_limit_count": "Rate limit: messages per window",
    "rate_limit_window_minutes": "Rate limit window (minutes)",
    "wa_rate_marketing_idr": "WhatsApp marketing template rate (IDR / message, estimate)",
    "wa_rate_utility_idr": "WhatsApp utility template rate (IDR / message, estimate)",
    "wa_free_tier_messages": "WhatsApp free-tier allowance shown on the dashboard",
}


TEXT_LABELS = {
    "safety_emergency": "Safety reply: emergency",
    "safety_self_harm": "Safety reply: self-harm",
    "safety_adverse_drug": "Safety reply: medicine side effects",
    "safety_adherence": "Safety reply: stopping / missing treatment",
    "safety_other": "Safety reply: other high-risk",
    "consent_notice": "Privacy / consent notice (first message)",
    "optout_confirm": "STOP / BERHENTI confirmation",
    "optin_confirm": "MULAI confirmation",
    "subscribe_confirm": "LANGGANAN confirmation",
    "non_text_reply": "Reply to photos, voice notes, stickers",
    "budget_fallback_reply": "Fixed reply (budget exhausted or bot error)",
    "daily_cap_reply": "Daily cap reached reply",
    "rate_limit_reply": "Rate limit reply",
    "away_message": "Out-of-hours message ({jam} / {hours} = the hours)",
}
LANG_SUFFIX = {"_id": " · Bahasa Indonesia", "_en": " · English"}


def _label(key: str) -> str:
    if key in LABELS:
        return LABELS[key]
    base, suffix = key[:-3], key[-3:]
    if base in TEXT_LABELS and suffix in LANG_SUFFIX:
        return TEXT_LABELS[base] + LANG_SUFFIX[suffix]
    return key.replace("_", " ").capitalize()


def _field(key: str, value: Any, overridden: bool) -> dict:
    if key in BOOL_KEYS:
        kind = "bool"
    elif key in NUMBER_KEYS:
        kind = "number"
    elif key in CHOICES:
        kind = "select"
    elif key in TIME_KEYS:
        kind = "time"
    elif key in DAYS_KEYS:
        kind = "days"
    elif key.endswith(("_id", "_en")) or key == "persona_prompt":
        kind = "textarea"
    else:
        kind = "text"
    return {
        "key": key,
        "label": _label(key),
        "type": kind,
        "value": value,
        "default": DEFAULTS[key],
        "choices": list(CHOICES.get(key, ())),
        "overridden": overridden,
    }


@router.get("")
async def get_settings(
    user: StaffUser = Depends(admin_only), session: AsyncSession = Depends(get_session)
):
    cfg = await settings_service.load(session)
    stored = (await session.execute(select(Setting.key))).scalars().all()
    overridden = set(stored) & set(DEFAULTS)
    return {
        "groups": [
            {"name": name, "fields": [_field(k, cfg[k], k in overridden) for k in keys]}
            for name, keys in GROUPS
        ],
        "flag_rules": cfg.flag_rules,
        "flag_rules_overridden": cfg["flag_rules"] is not None,
    }


class SettingsIn(BaseModel):
    values: dict[str, Any]


@router.put("")
async def update_settings(
    body: SettingsIn,
    request: Request,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    clean: dict[str, Any] = {}
    errors = []
    for key, value in body.values.items():
        try:
            clean[key] = settings_service.coerce(key, value)
        except (ValueError, TypeError) as e:
            errors.append(f"{key}: {e}")
    if errors:
        raise HTTPException(422, "; ".join(errors))
    for key, value in clean.items():
        if value == DEFAULTS[key]:
            await session.execute(delete(Setting).where(Setting.key == key))
        else:
            await settings_service.set_value(session, key, value, user.id)
    # Audit which keys changed (values can be long texts; numbers are logged).
    audit(session, user, "settings.update", "settings", "", {
        "keys": sorted(clean),
        "numbers": {k: v for k, v in clean.items() if k in NUMBER_KEYS or k in CHOICES},
    }, client_ip(request))  # fmt: skip
    await session.commit()
    return await get_settings(user, session)


class ResetIn(BaseModel):
    keys: list[str]


@router.post("/reset")
async def reset_settings(
    body: ResetIn,
    request: Request,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    keys = [k for k in body.keys if k in DEFAULTS]
    await session.execute(delete(Setting).where(Setting.key.in_(keys)))
    audit(session, user, "settings.reset", "settings", "", {"keys": keys}, client_ip(request))
    await session.commit()
    return await get_settings(user, session)


def _mask(value: str) -> str:
    return "set" if value else "missing"


@router.get("/channels")
async def channels(
    user: StaffUser = Depends(admin_only), session: AsyncSession = Depends(get_session)
):
    base = settings.api_base_url.rstrip("/")
    last = {
        ch: await settings_service.get_value(session, f"last_webhook_{ch}")
        for ch in ("whatsapp", "messenger", "instagram")
    }
    detected_phone = await settings_service.get_value(session, "wa_detected_phone_number_id")
    detected_waba = await settings_service.get_value(session, "wa_detected_waba_id")

    def id_check(env_value: str, detected) -> str:
        return "set" if env_value else (f"detected {detected}" if detected else "missing")

    wa_ready = bool(settings.wa_access_token and settings.wa_app_secret and settings.wa_verify_token
                    and (settings.wa_phone_number_id or detected_phone))  # fmt: skip
    return {
        "whatsapp": {
            "enabled": True,
            "configured": wa_ready,
            "webhook_url": f"{base}/webhook/whatsapp",
            "graph_version": settings.wa_graph_version,
            "checks": {
                "WA_ACCESS_TOKEN": _mask(settings.wa_access_token),
                "WA_PHONE_NUMBER_ID": id_check(settings.wa_phone_number_id, detected_phone),
                "WA_BUSINESS_ACCOUNT_ID": id_check(settings.wa_business_account_id, detected_waba),
                "WA_APP_SECRET": _mask(settings.wa_app_secret),
                "WA_VERIFY_TOKEN": _mask(settings.wa_verify_token),
            },
            "last_webhook_at": last["whatsapp"],
        },
        "messenger": {
            "enabled": settings.enable_messenger,
            "configured": bool(settings.meta_page_id and settings.meta_page_access_token),
            "webhook_url": f"{base}/webhook/messenger",
            "checks": {
                "META_PAGE_ID": _mask(settings.meta_page_id),
                "META_PAGE_ACCESS_TOKEN": _mask(settings.meta_page_access_token),
                "app secret": _mask(settings.app_secret_meta),
                "verify token": _mask(settings.verify_token_meta),
            },
            "last_webhook_at": last["messenger"],
        },
        "instagram": {
            "enabled": settings.enable_instagram,
            "configured": bool(settings.meta_page_id and settings.meta_page_access_token),
            "webhook_url": f"{base}/webhook/instagram",
            "checks": {
                "META_PAGE_ID": _mask(settings.meta_page_id),
                "META_IG_ACCOUNT_ID": _mask(settings.meta_ig_account_id),
                "META_PAGE_ACCESS_TOKEN": _mask(settings.meta_page_access_token),
            },
            "last_webhook_at": last["instagram"],
        },
        "llm": {
            "provider": settings.llm_provider,
            "key": _mask(settings.llm_api_key) if settings.llm_provider != "fake" else "n/a",
            "answer_model": settings.answer_model,
            "classifier_model": settings.classifier_model,
        },
        "email_alerts": bool(settings.smtp_host),
    }


@router.post("/channels/whatsapp/check")
async def check_whatsapp(
    request: Request,
    user: StaffUser = Depends(admin_only),
    session: AsyncSession = Depends(get_session),
):
    """Live check: ask the Graph API about the phone number (token validity)."""
    from app.channels.whatsapp import WhatsAppAdapter

    audit(session, user, "settings.channel_check", "channel", "whatsapp", ip=client_ip(request))
    await session.commit()
    try:
        info = await WhatsAppAdapter().phone_info()
    except SendError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "phone": info}
