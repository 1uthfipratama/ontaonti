"""TB symptom screening over chat (config/screening.yaml).

"SKRINING" starts a session; each Ya / Tidak answer moves to the next question;
the last one gives the result. A reply that isn't yes/no ends the session quietly
and goes to the bot as usual, so nobody gets stuck in a questionnaire.
"""

import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import events
from app.config import ROOT
from app.constants import SENDER_BOT
from app.db import as_utc, utcnow
from app.models import Conversation, Message, ScreeningSession, Task
from app.services import outbound

log = logging.getLogger("onti.screening")

SPEC_FILE = ROOT / "config" / "screening.yaml"
BUTTONS = {"id": [("yes", "Ya"), ("no", "Tidak")], "en": [("yes", "Yes"), ("no", "No")]}
EXPIRES = timedelta(hours=24)

_YES = re.compile(r"^(ya|iya|iyaa|yes|y|yup|betul|benar|pernah|ada|sering)\b")
_NO = re.compile(r"^(tidak|tdk|gak|nggak|ngga|enggak|engga|no|n|nope|belum|bukan|jarang)\b")


@dataclass
class Spec:
    keywords: set[str]
    questions: list[dict]
    min_symptoms: int
    texts: dict[str, str]

    def text(self, key: str, lang: str) -> str:
        return self.texts.get(f"{key}_{lang}") or self.texts[f"{key}_id"]


@lru_cache(maxsize=1)
def spec() -> Spec:
    raw = yaml.safe_load(SPEC_FILE.read_text(encoding="utf-8"))
    return Spec(
        keywords={k.lower() for k in raw["start_keywords"]},
        questions=raw["questions"],
        min_symptoms=int(raw.get("min_symptoms", 2)),
        texts={k: v for k, v in raw.items() if isinstance(v, str)},
    )


def _norm(text: str | None) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", (text or "").lower()).split())


def parse_yes_no(text: str | None) -> bool | None:
    t = _norm(text)
    if len(t.split()) > 4:  # a sentence: let the bot read it
        return None
    if _YES.match(t):
        return True
    if _NO.match(t):
        return False
    return None


def evaluate(answers: dict[str, bool], s: Spec | None = None) -> str:
    """'presumptive' (suggest testing) or 'negative'."""
    s = s or spec()
    symptoms = [q for q in s.questions if not q.get("contact")]
    if any(answers.get(q["id"]) for q in symptoms if q.get("major")):
        return "presumptive"
    n_yes = sum(1 for q in symptoms if answers.get(q["id"]))
    contact = any(answers.get(q["id"]) for q in s.questions if q.get("contact"))
    if n_yes >= s.min_symptoms or (contact and n_yes >= 1):
        return "presumptive"
    return "negative"


async def _active(session: AsyncSession, conv: Conversation) -> ScreeningSession | None:
    row = (
        await session.execute(
            select(ScreeningSession)
            .where(ScreeningSession.conversation_id == conv.id, ScreeningSession.status == "active")
            .order_by(ScreeningSession.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is not None and as_utc(row.started_at) < utcnow() - EXPIRES:
        row.status = "abandoned"
        await session.commit()
        return None
    return row


async def _ask(session: AsyncSession, conv: Conversation, sc: ScreeningSession) -> None:
    q = spec().questions[sc.step]
    text = f"({sc.step + 1}/{len(spec().questions)}) " + (q.get(f"text_{sc.lang}") or q["text_id"])
    await outbound.send_text(session, conv, text, sender_type=SENDER_BOT,
                             buttons=BUTTONS.get(sc.lang, BUTTONS["id"]),
                             meta={"screening": sc.id, "question": q["id"]})  # fmt: skip


async def _finish(session: AsyncSession, conv: Conversation, sc: ScreeningSession) -> None:
    sc.result = evaluate(sc.answers)
    sc.status, sc.finished_at = "done", utcnow()
    contact = conv.contact
    if sc.result == "presumptive":
        if contact.journey_stage is None:
            contact.journey_stage = "suspect"
        session.add(Task(
            contact_id=contact.id, kind="call", source="screening", assigned_to=contact.kader_id,
            title=f"Skrining TBC: {contact.display_name} disarankan periksa",
            due=None,
        ))  # fmt: skip
    await session.commit()
    key = "result_positive" if sc.result == "presumptive" else "result_negative"
    await outbound.send_text(session, conv, spec().text(key, sc.lang), sender_type=SENDER_BOT,
                             meta={"screening": sc.id, "result": sc.result})  # fmt: skip
    await events.publish("contact.updated", contact_id=contact.id)
    await events.publish("task.created", contact_id=contact.id)


async def maybe_handle(session: AsyncSession, conv: Conversation, msg: Message, lang: str) -> bool:
    """Start, continue or finish a screening. True when this message was handled."""
    text = _norm(msg.text)
    sc = await _active(session, conv)
    if sc is None:
        if text not in spec().keywords:
            return False
        sc = ScreeningSession(contact_id=conv.contact_id, conversation_id=conv.id,
                              lang=lang if lang in ("id", "en") else "id", answers={})  # fmt: skip
        session.add(sc)
        await session.commit()
        intro = spec().text("intro", sc.lang).replace("{n}", str(len(spec().questions)))
        await outbound.send_text(session, conv, intro, sender_type=SENDER_BOT,
                                 meta={"screening": sc.id})  # fmt: skip
        await _ask(session, conv, sc)
        return True

    answer = parse_yes_no(msg.text)
    if answer is None:  # a question or anything else: stop asking, let the bot answer
        sc.status = "abandoned"
        await session.commit()
        return False
    q = spec().questions[sc.step]
    sc.answers = {**sc.answers, q["id"]: answer}
    sc.step += 1
    await session.commit()
    if sc.step < len(spec().questions):
        await _ask(session, conv, sc)
    else:
        await _finish(session, conv, sc)
    return True
