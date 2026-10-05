"""RAG answer: retrieve (thesis-rag) -> persona prompt -> LLM -> one WhatsApp message."""

import asyncio
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import llm
from app.bot import rag_service
from app.bot.format import clamp, to_whatsapp, trim_incomplete
from app.bot.language import LANG_NAME, detect
from app.constants import DIR_IN, DIR_OUT, MSG_FAILED
from app.models import Conversation, Message
from app.services.settings_service import Config


@dataclass
class Answer:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_idr: float
    sources: list[dict] = field(default_factory=list)
    unanswered: bool = False  # the knowledge base didn't cover the question


# Fixed (not editable): lets the hub list questions the knowledge base can't answer.
NOINFO = "[NOINFO]"
NOINFO_INSTRUCTION = (
    "If the Konteks passages do not contain the information needed to answer the "
    f"question, reply as instructed and put the tag {NOINFO} at the very end."
)


async def recent_turns(
    session: AsyncSession, conv: Conversation, before_id: int, n: int
) -> list[dict]:
    """Last n user/assistant messages before this one, oldest first."""
    rows = (
        (
            await session.execute(
                select(Message)
                .where(
                    Message.conversation_id == conv.id,
                    Message.id < before_id,
                    Message.direction.in_((DIR_IN, DIR_OUT)),
                    Message.status != MSG_FAILED,
                )
                .order_by(Message.id.desc())
                .limit(n)
            )
        )
        .scalars()
        .all()
    )
    return [
        {"role": "user" if m.direction == DIR_IN else "assistant", "content": m.text}
        for m in reversed(rows)
        if m.kind == "text" and m.text
    ]


def search_query(text: str, turns: list[dict]) -> str:
    """Short follow-ups ("kalau anak?", "why?") carry little to search on: add the
    previous user message (the fallback idea from thesis-rag's rag.chat)."""
    if len(re.findall(r"\w+", text)) <= 4:
        prev = next((t["content"] for t in reversed(turns) if t["role"] == "user"), "")
        if prev:
            return f"{prev} {text}"
    return text


async def generate(
    session: AsyncSession,
    conv: Conversation,
    msg: Message,
    cfg: Config,
    model: str,
    *,
    purpose: str = "answer",
    extra_system: str = "",
) -> Answer:
    from rag.generate import history_messages, strip_markers, validate_citations

    text = (msg.text or "")[: cfg["max_input_chars"]]
    turns = await recent_turns(session, conv, msg.id, cfg["history_turns"])
    snippets = await asyncio.to_thread(
        rag_service.retrieve, search_query(text, turns), cfg["retrieval_k"]
    )
    lang = detect(text)
    user_content = (
        f"Konteks:\n\n{rag_service.format_context(snippets)}\n\n"
        f"Bahasa balasan: {LANG_NAME[lang]}\n\n"
        f"Pesan pengguna:\n{text}"
    )
    messages = history_messages(turns) + [{"role": "user", "content": user_content}]
    system = "\n\n".join(x for x in (cfg["persona_prompt"], NOINFO_INSTRUCTION, extra_system) if x)
    result = await llm.complete(
        purpose=purpose,
        model=model,
        system=system,
        messages=messages,
        max_tokens=cfg["max_output_tokens"],
        temperature=0.3,
        conversation_id=conv.id,
        message_id=msg.id,
    )
    unanswered = NOINFO in result.text or not snippets
    clean, cited, _ = validate_citations(result.text.replace(NOINFO, ""), len(snippets))
    reply = to_whatsapp(strip_markers(clean))
    if result.stop_reason in ("max_tokens", "length"):  # cut off mid-sentence
        reply = trim_incomplete(reply)
    reply = clamp(reply, cfg["max_reply_chars"])
    if not reply:
        raise llm.LLMError("empty answer")
    by_n = {s.n: s for s in snippets}
    sources = [
        {"n": n, "doc": by_n[n].doc_id, "title": by_n[n].title, "heading": by_n[n].heading}
        for n in cited
        if n in by_n
    ]
    return Answer(
        reply, result.model, result.tokens_in, result.tokens_out, result.cost_idr, sources,
        unanswered,
    )  # fmt: skip
