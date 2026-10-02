"""Shared Meta (Graph API) helpers: webhook signatures and HTTP calls."""

import hashlib
import hmac
import logging

import httpx

from app.channels.base import SendError
from app.config import settings

log = logging.getLogger("onti.meta")


def verify_signature(raw_body: bytes, header: str | None, app_secret: str) -> bool:
    """X-Hub-Signature-256: "sha256=" + HMAC-SHA256(app secret, raw body)."""
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256=") :].strip())


def verify_subscription(params: dict, verify_token: str) -> str | None:
    """GET webhook handshake: return hub.challenge when the token matches."""
    if not verify_token:
        return None
    if params.get("hub.mode") != "subscribe":
        return None
    if not hmac.compare_digest(str(params.get("hub.verify_token", "")), verify_token):
        return None
    return str(params.get("hub.challenge", ""))


def graph_url(path: str) -> str:
    return f"{settings.graph_base_url.rstrip('/')}/{settings.wa_graph_version}/{path.lstrip('/')}"


def _error_text(r: httpx.Response) -> tuple[str, str | None]:
    try:
        err = r.json().get("error", {})
        code = err.get("code")
        detail = err.get("error_user_msg") or err.get("message") or r.text[:200]
        sub = (err.get("error_data") or {}).get("details")
        return (f"{detail} ({sub})" if sub else str(detail)), (str(code) if code else None)
    except ValueError:
        return r.text[:200], None


async def graph_request(method: str, path: str, token: str, *, json: dict | None = None,
                        params: dict | None = None) -> dict:  # fmt: skip
    """Call the Graph API with a Bearer token (never in the URL). Raises SendError."""
    if not token:
        raise SendError("missing access token", retryable=False, code="config")
    try:
        async with httpx.AsyncClient(timeout=20) as http:
            r = await http.request(
                method, graph_url(path), json=json, params=params,
                headers={"Authorization": f"Bearer {token}"},
            )  # fmt: skip
    except httpx.HTTPError as e:
        raise SendError(f"network error: {type(e).__name__}", retryable=True) from e
    if r.status_code >= 400:
        text, code = _error_text(r)
        retryable = r.status_code == 429 or r.status_code >= 500 or code in ("4", "80007", "130429")
        raise SendError(f"Graph API {r.status_code}: {text}", retryable=retryable, code=code)
    try:
        return r.json()
    except ValueError:
        return {}
