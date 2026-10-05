"""TOTP (RFC 6238) for staff two-factor login: 6 digits, 30-second steps, SHA-1,
which is what authenticator apps (Google Authenticator, Authy, 1Password...) use."""

import base64
import hashlib
import hmac
import os
import re
import struct
import time
from urllib.parse import quote

import segno

STEP, DIGITS = 30, 6
ISSUER = "Onti Erlina"


def new_secret() -> str:
    return base64.b32encode(os.urandom(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    return base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))


def code_at(secret: str, step: int) -> str:
    mac = hmac.new(_key(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    number = (struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF) % 10**DIGITS
    return f"{number:0{DIGITS}d}"


def verify(
    secret: str, code: str | None, last_step: int | None = None, now: float | None = None
) -> int | None:
    """The matching time step (one step of clock drift either way), or None.
    A step at or before `last_step` was already used: rejected as a replay."""
    code = re.sub(r"\s", "", code or "")
    if not secret or not re.fullmatch(rf"\d{{{DIGITS}}}", code):
        return None
    current = int((time.time() if now is None else now) // STEP)
    for step in (current - 1, current, current + 1):
        if hmac.compare_digest(code_at(secret, step), code):
            return step if last_step is None or step > last_step else None
    return None


def uri(secret: str, account: str) -> str:
    label = quote(f"{ISSUER}:{account}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER)}&digits={DIGITS}&period={STEP}"


def qr_data_uri(data: str) -> str:
    return segno.make(data, error="m").svg_data_uri(scale=5, border=2)
