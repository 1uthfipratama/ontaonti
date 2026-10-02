"""WhatsApp Cloud API adapter (Meta Graph API).

Inbound: webhook "messages" field. Outbound: POST /{phone_number_id}/messages.
Docs: developers.facebook.com/docs/whatsapp/cloud-api
"""

import logging
from datetime import UTC, datetime

from app.channels.base import ChannelAdapter, InternalMessage, SendError, StatusUpdate
from app.channels.meta_common import graph_request
from app.config import settings

log = logging.getLogger("onti.whatsapp")

MEDIA_KINDS = ("image", "video", "audio", "document", "sticker")
TRACKED_STATUSES = ("delivered", "read", "failed")  # "sent" is ignored (we record it on send)


def _ts(value) -> datetime:
    try:
        return datetime.fromtimestamp(int(value), UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


class WhatsAppAdapter(ChannelAdapter):
    channel = "whatsapp"

    # --- inbound -------------------------------------------------------------

    @staticmethod
    def _values(payload: dict):
        if payload.get("object") != "whatsapp_business_account":
            return
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                if change.get("field") == "messages":
                    yield change.get("value") or {}

    def parse_inbound(self, payload: dict) -> list[InternalMessage]:
        out: list[InternalMessage] = []
        for value in self._values(payload):
            names = {
                c.get("wa_id"): (c.get("profile") or {}).get("name", "")
                for c in value.get("contacts") or []
            }
            for m in value.get("messages") or []:
                kind = m.get("type", "unsupported")
                text, media = "", None
                if kind == "text":
                    text = (m.get("text") or {}).get("body", "")
                elif kind == "button":  # quick-reply button on a template
                    kind, text = "text", (m.get("button") or {}).get("text", "")
                elif kind == "interactive":
                    i = m.get("interactive") or {}
                    reply = i.get("button_reply") or i.get("list_reply") or {}
                    kind, text = "text", reply.get("title", "")
                elif kind in MEDIA_KINDS:
                    body = m.get(kind) or {}
                    text = body.get("caption", "")
                    media = f"wa-media:{body.get('id', '')}"
                elif kind == "location":
                    loc = m.get("location") or {}
                    text = loc.get("name") or loc.get("address") or ""
                elif kind == "reaction":
                    continue  # an emoji on an earlier message: nothing to answer
                else:
                    kind = "unsupported"
                if not m.get("id") or not m.get("from"):
                    continue
                out.append(
                    InternalMessage(
                        channel="whatsapp",
                        external_user_id=m["from"],
                        external_message_id=m["id"],
                        text=text,
                        kind=kind,
                        user_name=names.get(m["from"], ""),
                        media_url=media,
                        timestamp=_ts(m.get("timestamp")),
                        raw=m,
                    )
                )
        return out

    def parse_statuses(self, payload: dict) -> list[StatusUpdate]:
        out = []
        for value in self._values(payload):
            for s in value.get("statuses") or []:
                status = s.get("status")
                if status not in TRACKED_STATUSES or not s.get("id"):
                    continue
                error = None
                if status == "failed" and s.get("errors"):
                    e = s["errors"][0]
                    error = f"{e.get('code', '')} {e.get('title') or e.get('message', '')}".strip()
                out.append(StatusUpdate(s["id"], status, _ts(s.get("timestamp")), error))
        return out

    # --- outbound ------------------------------------------------------------

    async def _post(self, body: dict) -> dict:
        if not settings.wa_phone_number_id:
            raise SendError("WA_PHONE_NUMBER_ID is not set", code="config")
        return await graph_request(
            "POST", f"{settings.wa_phone_number_id}/messages", settings.wa_access_token, json=body
        )

    async def send(self, conversation, text: str, *, human_agent: bool = False) -> str | None:
        data = await self._post(
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": conversation.identity.external_id,
                "type": "text",
                "text": {"preview_url": False, "body": text[:4096]},
            }
        )
        return ((data.get("messages") or [{}])[0]).get("id")

    async def send_template(
        self, to: str, name: str, language: str, body_params: list[str]
    ) -> str | None:
        template: dict = {"name": name, "language": {"code": language}}
        if body_params:
            template["components"] = [
                {"type": "body", "parameters": [{"type": "text", "text": p} for p in body_params]}
            ]
        data = await self._post(
            {"messaging_product": "whatsapp", "to": to, "type": "template", "template": template}
        )
        return ((data.get("messages") or [{}])[0]).get("id")

    async def mark_read(self, external_message_id: str) -> None:
        await self._post(
            {"messaging_product": "whatsapp", "status": "read", "message_id": external_message_id}
        )

    # --- account -------------------------------------------------------------

    async def phone_info(self) -> dict:
        return await graph_request(
            "GET",
            settings.wa_phone_number_id,
            settings.wa_access_token,
            params={"fields": "display_phone_number,verified_name,quality_rating"},
        )

    async def list_templates(self) -> list[dict]:
        if not settings.wa_business_account_id:
            raise SendError("WA_BUSINESS_ACCOUNT_ID is not set", code="config")
        out: list[dict] = []
        params = {"limit": 100, "fields": "name,language,status,category,components"}
        path = f"{settings.wa_business_account_id}/message_templates"
        for _ in range(10):  # pagination guard
            data = await graph_request("GET", path, settings.wa_access_token, params=params)
            out += data.get("data") or []
            after = ((data.get("paging") or {}).get("cursors") or {}).get("after")
            if not after or not (data.get("paging") or {}).get("next"):
                break
            params = {**params, "after": after}
        return out
