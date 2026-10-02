"""AI summary for an agent taking over a conversation (staff-facing, never sent)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import llm
from app.constants import DIR_IN, DIR_NOTE
from app.models import Conversation, Message

SUMMARY_PROMPT = """Ringkas percakapan berikut untuk staf yayasan TBC yang akan mengambil alih chat dari bot.
Tulis dalam Bahasa Indonesia, 4-7 poin singkat (diawali "- "):
- siapa pengguna dan apa kekhawatiran utamanya,
- tanda bahaya atau flag keselamatan (jika ada) dan kapan muncul,
- apa yang sudah dijawab bot atau staf,
- pertanyaan yang belum terjawab,
- saran langkah berikutnya untuk staf (bukan diagnosis, bukan dosis obat).
Hanya berdasarkan isi percakapan; jangan menambah fakta."""

ROLE = {"user": "PENGGUNA", "bot": "BOT", "agent": "STAF", "system": "SISTEM"}


async def summarise(
    session: AsyncSession, conv: Conversation, model: str, max_messages: int = 40
) -> llm.LLMResult:
    rows = (
        (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.id.desc())
                .limit(max_messages)
            )
        )
        .scalars()
        .all()
    )
    lines = []
    for m in reversed(rows):
        if m.direction == DIR_NOTE:
            lines.append(f"(catatan sistem: {m.text})")
            continue
        who = ROLE["user"] if m.direction == DIR_IN else ROLE.get(m.sender_type, "BOT")
        flag = (
            f" [FLAG {m.flag_severity} {m.flag_category}]"
            if m.flag_severity not in (None, "none")
            else ""
        )
        lines.append(f"{who}: {' '.join((m.text or '').split())[:600]}{flag}")
    transcript = "\n".join(lines) or "(kosong)"
    return await llm.complete(
        purpose="summary",
        model=model,
        system=SUMMARY_PROMPT,
        messages=[{"role": "user", "content": f"Percakapan ({conv.channel}):\n{transcript}"}],
        max_tokens=400,
        temperature=0.2,
        conversation_id=conv.id,
    )
