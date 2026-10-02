"""Logging with secret redaction.

Every configured secret (tokens, API keys, passwords) is replaced by "***" in any
log record before it is written, whatever logger produced it. httpx request
logging is turned down: URLs are fine, but there's no reason to keep it chatty.
"""

import logging
import sys

from app.config import settings


class RedactSecrets(logging.Filter):
    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        self.secrets = sorted(set(secrets), key=len, reverse=True)

    def _clean(self, text: str) -> str:
        for s in self.secrets:
            if s in text:
                text = text.replace(s, "***")
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if not self.secrets:
            return True
        try:
            msg = record.getMessage()
        except Exception:
            return True
        cleaned = self._clean(msg)
        if record.exc_info and record.exc_text is None:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = self._clean(record.exc_text)
        record.msg, record.args = cleaned, None
        return True


_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    _configured = True
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactSecrets(settings.secret_values()))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(settings.log_level.upper())
    for noisy in ("httpx", "httpcore", "httpx2", "httpcore2", "anthropic", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # uvicorn/arq install their own handlers; route them through ours.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "arq", "arq.worker"):
        lg = logging.getLogger(name)
        lg.handlers[:] = []
        lg.propagate = True
