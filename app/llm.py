"""One interface over the LLM providers: LLM_PROVIDER = groq | anthropic | fake.

Every call is logged (tokens, estimated cost in USD and IDR, latency) to the
llm_usage table and to the application log. API keys never appear in logs.

- anthropic: official SDK. Claude Sonnet 5.5 rejects `temperature` and
  `thinking: disabled`; the lowest thinking setting is `between_tools`, used here
  with low effort so the whole max_tokens budget goes to the reply. Refusals are
  routed server-side with `fallbacks: "default"`. Haiku 4.5 takes temperature,
  which anthropic 1.x only accepts through extra_body.
- groq: OpenAI-compatible chat completions over HTTPS.
- fake: deterministic, no network: tests and offline demos.
"""

import json
import logging
import re
import time
from dataclasses import dataclass

import httpx

from app.config import settings
from app.db import SessionLocal
from app.models import LlmUsage

log = logging.getLogger("onti.llm")

# USD per million tokens (input, output). Estimates for budgeting; longest prefix wins.
PRICES = {
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "fake": (0.0, 0.0),
}


class LLMError(Exception):
    """The provider failed (network, auth, rate limit, refusal)."""


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    cost_idr: float
    latency_ms: int
    stop_reason: str | None = None


def price_for(model: str) -> tuple[float, float]:
    match = max((k for k in PRICES if model.startswith(k)), key=len, default=None)
    return PRICES[match] if match else (0.0, 0.0)


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    p_in, p_out = price_for(model)
    return (tokens_in * p_in + tokens_out * p_out) / 1e6


# --- providers -------------------------------------------------------------------


async def _anthropic(model, system, messages, max_tokens, temperature, json_mode):
    import anthropic

    headers = {}
    if settings.anthropic_workspace_id:
        headers["anthropic-workspace-id"] = settings.anthropic_workspace_id
    client = anthropic.AsyncAnthropic(
        api_key=settings.llm_api_key or None,
        timeout=settings.llm_timeout_seconds,
        max_retries=2,
        default_headers=headers or None,
    )
    params: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        params["system"] = system
    try:
        if model.startswith("claude-sonnet-5-5") or model.startswith("claude-opus-5"):
            # Thinking can't be disabled on these; keep it minimal so max_tokens is
            # spent on the reply. Server-side fallback handles policy refusals.
            if model.startswith("claude-sonnet-5-5"):
                params["thinking"] = {"type": "between_tools"}
            params["output_config"] = {"effort": "low"}
            resp = await client.beta.messages.create(
                **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
            )
        else:
            if temperature is not None:
                params["extra_body"] = {"temperature": temperature}
            resp = await client.messages.create(**params)
    except anthropic.AuthenticationError as e:
        raise LLMError("anthropic: invalid API key (check LLM_API_KEY)") from e
    except anthropic.RateLimitError as e:
        raise LLMError("anthropic: rate limited") from e
    except anthropic.APIStatusError as e:
        detail = ""
        if isinstance(e.body, dict):
            detail = str(e.body.get("error", {}).get("message", ""))[:160]
        raise LLMError(f"anthropic: HTTP {e.status_code} {detail}".strip()) from e
    except anthropic.APIConnectionError as e:
        raise LLMError("anthropic: connection error") from e
    finally:
        await client.close()
    if resp.stop_reason == "refusal":
        raise LLMError("anthropic: request declined (refusal)")
    text = "".join(b.text for b in resp.content if b.type == "text")
    served = getattr(resp, "model", None) or model
    return text, served, resp.usage.input_tokens, resp.usage.output_tokens, resp.stop_reason


async def _groq(model, system, messages, max_tokens, temperature, json_mode):
    body: dict = {
        "model": model,
        "messages": ([{"role": "system", "content": system}] if system else []) + messages,
        "max_tokens": max_tokens,
        "temperature": 0.3 if temperature is None else temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    last: Exception | None = None
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as http:
        for attempt in range(3):
            try:
                r = await http.post(
                    "https://api.groq.com/openai/v1/chat/completions", json=body, headers=headers
                )
            except httpx.HTTPError as e:
                last = e
                continue
            if r.status_code == 429 or r.status_code >= 500:
                last = LLMError(f"groq: HTTP {r.status_code}")
                await _sleep(2**attempt)
                continue
            if r.status_code >= 400:
                raise LLMError(f"groq: HTTP {r.status_code}")
            data = r.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})
            return (
                choice["message"].get("content") or "",
                model,
                int(usage.get("prompt_tokens", 0)),
                int(usage.get("completion_tokens", 0)),
                choice.get("finish_reason"),
            )
    raise LLMError(f"groq: failed after retries ({type(last).__name__})")


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


async def _fake(model, system, messages, max_tokens, temperature, json_mode):
    """Deterministic stand-in. Classifier: keyword heuristics returning JSON.
    Answer: quotes the first passage. Summary: lists the last user messages."""
    last = messages[-1]["content"] if messages else ""
    if "[fake-llm-error]" in last:
        raise LLMError("fake: simulated provider failure")
    if json_mode:
        if "[fake-invalid-json]" in last:
            text = "I think this is fine, no JSON here"
        elif re.search(r"\b(sesak|darah|pingsan)\b", last, re.I):
            text = json.dumps({"severity": "high", "category": "EMERGENCY", "reason": "fake"})
        else:
            text = json.dumps({"severity": "none", "category": "NONE", "reason": "fake"})
    elif "Ringkas percakapan" in (system or "") or "Summarise" in (system or ""):
        users = re.findall(r"^PENGGUNA: (.+)$", last, re.M)
        text = "Ringkasan (demo): " + " | ".join(u[:80] for u in users[-3:])
    else:
        m = re.search(r"^\[(\d+)\][^\n]*\n(.+?)(?:\n\n|\Z)", last, re.S | re.M)
        if m:
            first = re.split(r"(?<=[.!?])\s", " ".join(m.group(2).split()), maxsplit=1)[0]
            text = f"(Mode demo) Menurut materi kami: {first[:400]} [{m.group(1)}]"
        else:
            text = "(Mode demo) Maaf, saya belum punya informasi tentang itu."
    t_in = sum(len(str(x.get("content", ""))) for x in messages) // 4 + len(system or "") // 4
    return text, model, t_in, len(text) // 4, "end_turn"


PROVIDERS = {"anthropic": _anthropic, "groq": _groq, "fake": _fake}


# --- public API --------------------------------------------------------------------


async def complete(
    *,
    purpose: str,
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float | None = None,
    json_mode: bool = False,
    conversation_id: int | None = None,
    message_id: int | None = None,
) -> LLMResult:
    provider = settings.llm_provider
    fn = PROVIDERS.get(provider)
    if fn is None:
        raise LLMError(f"unknown LLM_PROVIDER {provider!r}")
    if provider != "fake" and not settings.llm_api_key and provider == "groq":
        raise LLMError("groq: LLM_API_KEY is not set")
    t0 = time.perf_counter()
    error: str | None = None
    try:
        text, served, t_in, t_out, stop = await fn(
            model, system, messages, max_tokens, temperature, json_mode
        )
    except LLMError as e:
        error = str(e)
        text, served, t_in, t_out, stop = "", model, 0, 0, None
    latency = int((time.perf_counter() - t0) * 1000)
    usd = cost_usd(served, t_in, t_out)
    idr = usd * settings.usd_to_idr
    log.info(
        "llm purpose=%s provider=%s model=%s in=%d out=%d cost_usd=%.6f cost_idr=%.2f "
        "latency_ms=%d ok=%s",
        purpose, provider, served, t_in, t_out, usd, idr, latency, error is None,
    )  # fmt: skip
    await _record(
        provider,
        served,
        purpose,
        t_in,
        t_out,
        usd,
        idr,
        latency,
        error,
        conversation_id,
        message_id,
    )
    if error:
        raise LLMError(error)
    return LLMResult(text.strip(), provider, served, t_in, t_out, usd, idr, latency, stop)


async def _record(provider, model, purpose, t_in, t_out, usd, idr, latency, error, conv_id, msg_id):
    # Own session: usage is recorded even if the caller's transaction rolls back.
    try:
        async with SessionLocal() as s:
            s.add(
                LlmUsage(
                    provider=provider,
                    model=model,
                    purpose=purpose,
                    tokens_in=t_in,
                    tokens_out=t_out,
                    cost_usd=usd,
                    cost_idr=idr,
                    latency_ms=latency,
                    ok=error is None,
                    error=error,
                    conversation_id=conv_id,
                    message_id=msg_id,
                )  # fmt: skip
            )
            await s.commit()
    except Exception:
        log.exception("could not record llm usage")
