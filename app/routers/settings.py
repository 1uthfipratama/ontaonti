"""Settings: channel connection status (phase 3); editable runtime settings (phase 5)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import audit
from app.channels.base import SendError
from app.config import settings
from app.db import get_session
from app.deps import admin_only, client_ip
from app.models import StaffUser
from app.services import settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


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
    return {
        "whatsapp": {
            "enabled": True,
            "configured": settings.whatsapp_configured and bool(settings.wa_verify_token),
            "webhook_url": f"{base}/webhook/whatsapp",
            "graph_version": settings.wa_graph_version,
            "checks": {
                "WA_ACCESS_TOKEN": _mask(settings.wa_access_token),
                "WA_PHONE_NUMBER_ID": _mask(settings.wa_phone_number_id),
                "WA_BUSINESS_ACCOUNT_ID": _mask(settings.wa_business_account_id),
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
