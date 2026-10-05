"""Voice notes -> text.

TRANSCRIBE_PROVIDER:
  local  faster-whisper on the worker's CPU. Free; the model (WHISPER_MODEL) is
         downloaded to WHISPER_DIR on first use.
  groq   Groq's hosted Whisper (whisper-large-v3-turbo); needs TRANSCRIBE_API_KEY.
  fake   fixed text (tests, offline demo).
  ""     off.
Returns None when off or on failure; the caller then treats the voice note as
a non-text message.
"""

import asyncio
import logging
from functools import lru_cache
from pathlib import Path

import httpx

from app.config import settings

log = logging.getLogger("onti.transcribe")

FAKE_TEXT = "Halo kak, berapa lama pengobatan TBC?"
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def available() -> bool:
    p = settings.transcribe_provider
    return p in ("fake", "groq", "local") and (p != "groq" or bool(settings.transcribe_api_key))


@lru_cache(maxsize=1)
def _local_model():
    from faster_whisper import WhisperModel  # heavy import, only when used

    settings.whisper_dir.mkdir(parents=True, exist_ok=True)
    log.info("loading whisper model %s (first use downloads it)", settings.whisper_model)
    return WhisperModel(
        settings.whisper_model, device="cpu", compute_type="int8",
        download_root=str(settings.whisper_dir),
    )  # fmt: skip


def _local(path: Path) -> str:
    segments, _info = _local_model().transcribe(
        str(path), beam_size=1, vad_filter=True, condition_on_previous_text=False
    )
    return " ".join(s.text.strip() for s in segments).strip()


async def _groq(path: Path) -> str:
    async with httpx.AsyncClient(timeout=60) as http:
        r = await http.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {settings.transcribe_api_key}"},
            data={"model": "whisper-large-v3-turbo", "response_format": "json"},
            files={"file": (path.name, path.read_bytes())},
        )
    r.raise_for_status()
    return (r.json().get("text") or "").strip()


async def transcribe(path: Path | None) -> str | None:
    provider = settings.transcribe_provider
    if not available():
        return None
    if provider == "fake":
        return FAKE_TEXT
    if path is None:
        return None
    try:
        if provider == "groq":
            text = await _groq(path)
        else:
            text = await asyncio.to_thread(_local, path)
    except Exception as e:  # missing package, model download, network, bad audio
        log.warning("transcription failed (%s): %s", provider, e)
        return None
    return text or None
