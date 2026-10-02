"""Staff passwords (bcrypt) and signed session cookies (itsdangerous)."""

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

COOKIE_NAME = "onti_session"
_serializer = URLSafeTimedSerializer(settings.secret_key, salt="onti-session")


def hash_password(password: str) -> str:
    # bcrypt reads at most 72 bytes; longer passwords are rejected at the API.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode())
    except ValueError:
        return False


def make_session_token(user_id: int, epoch: int) -> str:
    return _serializer.dumps({"uid": user_id, "ep": epoch})


def read_session_token(token: str) -> tuple[int, int] | None:
    try:
        data = _serializer.loads(token, max_age=settings.session_hours * 3600)
    except (BadSignature, SignatureExpired):
        return None
    try:
        return int(data["uid"]), int(data["ep"])
    except (KeyError, TypeError, ValueError):
        return None


def cookie_kwargs() -> dict:
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "max_age": settings.session_hours * 3600,
        "path": "/",
    }
