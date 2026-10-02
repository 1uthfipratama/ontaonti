"""Builders for Meta webhook payloads (shapes as documented by Meta)."""

import hashlib
import hmac
import json
import time
import uuid

PHONE_ID = "1111111111"
APP_SECRET = "test-app-secret"


def sign(body: bytes, secret: str = APP_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def wa_text(
    text: str, wa_id: str = "6281234567890", name: str = "Siti", msg_id: str | None = None
) -> dict:
    return wa_message({"type": "text", "text": {"body": text}}, wa_id, name, msg_id)


def wa_message(content: dict, wa_id: str = "6281234567890", name: str = "Siti",
               msg_id: str | None = None) -> dict:  # fmt: skip
    message = {
        "from": wa_id,
        "id": msg_id or f"wamid.IN{uuid.uuid4().hex[:20]}",
        "timestamp": str(int(time.time())),
        **content,
    }
    return _envelope({
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "15550001111", "phone_number_id": PHONE_ID},
        "contacts": [{"profile": {"name": name}, "wa_id": wa_id}],
        "messages": [message],
    })  # fmt: skip


def wa_status(wamid: str, status: str, wa_id: str = "6281234567890") -> dict:
    return _envelope({
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "15550001111", "phone_number_id": PHONE_ID},
        "statuses": [{"id": wamid, "status": status, "timestamp": str(int(time.time())),
                      "recipient_id": wa_id}],
    })  # fmt: skip


def _envelope(value: dict) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "2222222222", "changes": [{"field": "messages", "value": value}]}],
    }


def messenger_text(
    text: str, psid: str = "PSID123", obj: str = "page", mid: str | None = None
) -> dict:
    return {
        "object": obj,
        "entry": [{
            "id": "3333333333",
            "time": int(time.time() * 1000),
            "messaging": [{
                "sender": {"id": psid},
                "recipient": {"id": "3333333333"},
                "timestamp": int(time.time() * 1000),
                "message": {"mid": mid or f"m_{uuid.uuid4().hex[:16]}", "text": text},
            }],
        }],
    }  # fmt: skip


def dumps(payload: dict) -> bytes:
    return json.dumps(payload).encode()
