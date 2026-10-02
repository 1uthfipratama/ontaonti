"""Safety layer: keyword rules (always on) + an LLM classifier.

Final severity = max(keyword, classifier). high / emergency -> the pipeline sends a
FIXED safety reply (from settings, never LLM-generated), opens a case and hands
the conversation to staff (app/services/cases.py).
"""

import json
import re
import unicodedata
from dataclasses import dataclass

from app import llm
from app.constants import SEVERITIES, SEVERITY_RANK

CATEGORIES = ("EMERGENCY", "SELF_HARM", "ADVERSE_DRUG", "ADHERENCE", "OTHER", "NONE")
SUFFIXES = ("", "nya", "lah", "kah", "ku", "mu", "pun", "an")
MAX_GAP = 2  # other words allowed between consecutive keyword words


@dataclass
class Flag:
    severity: str = "none"
    category: str | None = None
    reason: str = ""
    source: str = ""  # keyword | classifier

    @property
    def rank(self) -> int:
        return SEVERITY_RANK.get(self.severity, 0)


NONE = Flag()


def normalise(text: str) -> list[str]:
    """Lowercase, strip diacritics, punctuation -> spaces; returns words."""
    folded = "".join(
        c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c)
    )
    folded = folded.replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", " ", folded).split()


def _word_match(token: str, word: str) -> bool:
    return token.startswith(word) and token[len(word) :] in SUFFIXES


def phrase_in(tokens: list[str], phrase: list[str]) -> bool:
    """Keyword words in order, with at most MAX_GAP other words between them."""
    if not phrase:
        return False
    for start, tok in enumerate(tokens):
        if not _word_match(tok, phrase[0]):
            continue
        pos, ok = start, True
        for word in phrase[1:]:
            window = tokens[pos + 1 : pos + 2 + MAX_GAP]
            nxt = next((i for i, t in enumerate(window) if _word_match(t, word)), None)
            if nxt is None:
                ok = False
                break
            pos = pos + 1 + nxt
        if ok:
            return True
    return False


def validate_rules(rules: dict) -> dict:
    cats = rules.get("categories") if isinstance(rules, dict) else None
    if not isinstance(cats, dict) or not cats:
        raise ValueError("flag rules need a non-empty 'categories' mapping")
    clean: dict = {"categories": {}}
    for name, spec in cats.items():
        sev = (spec or {}).get("severity")
        if sev not in SEVERITIES or sev == "none":
            raise ValueError(f"{name}: severity must be low, high or emergency")
        words = [str(k).strip() for k in (spec.get("keywords") or []) if str(k).strip()]
        clean["categories"][str(name).upper()] = {"severity": sev, "keywords": words}
    return clean


def keyword_flag(text: str, rules: dict) -> Flag:
    tokens = normalise(text or "")
    if not tokens:
        return NONE
    best = NONE
    for name, spec in rules.get("categories", {}).items():
        sev = spec.get("severity", "high")
        if SEVERITY_RANK.get(sev, 0) <= best.rank:
            continue
        for kw in spec.get("keywords", []):
            if phrase_in(tokens, normalise(kw)):
                best = Flag(sev, name, f'keyword "{kw}"', "keyword")
                break
    return best


CLASSIFIER_PROMPT = """You are a safety triage classifier for a tuberculosis (TB) support chat in Indonesia. You read ONE message from a user (Bahasa Indonesia or English) and return ONLY a JSON object, nothing else:
{"severity": "none|low|high|emergency", "category": "EMERGENCY|SELF_HARM|ADVERSE_DRUG|ADHERENCE|OTHER|NONE", "reason": "<max 15 words, English>"}

Severity guide:
- emergency: danger to life now: coughing up a lot of blood, severe breathlessness, chest pain, fainting, blue lips, seizures (EMERGENCY); suicidal thoughts or intent to self-harm (SELF_HARM).
- high: needs a health worker soon: serious medicine side effects such as yellow eyes or skin, severe rash, persistent vomiting, blurred vision, severe tingling, hearing loss (ADVERSE_DRUG); stopping or wanting to stop TB treatment, medicine running out, missing doses for days (ADHERENCE); violence, abuse or another urgent social problem (OTHER).
- low: mild symptoms, mild side effects, worry, sadness or stigma without danger.
- none: general questions, greetings, thanks, questions about TB in general.

Judge the user's own current situation. Educational or hypothetical questions ("what are the danger signs of TB?") are none."""


def parse_classifier(text: str) -> Flag:
    """Strict parse of the classifier's JSON. Anything unreadable -> low."""
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        data = json.loads(m.group(0)) if m else None
    except ValueError:
        data = None
    if not isinstance(data, dict) or data.get("severity") not in SEVERITIES:
        return Flag("low", "OTHER", "classifier output could not be parsed", "classifier")
    category = str(data.get("category") or "OTHER").upper()
    if category not in CATEGORIES:
        category = "OTHER"
    sev = data["severity"]
    if sev == "none":
        category = None
    return Flag(sev, category, str(data.get("reason") or "")[:200], "classifier")


async def classify(text: str, model: str, conversation_id: int, message_id: int) -> Flag:
    try:
        res = await llm.complete(
            purpose="classifier",
            model=model,
            system=CLASSIFIER_PROMPT,
            messages=[{"role": "user", "content": f"Message:\n{text[:1000]}"}],
            max_tokens=120,
            temperature=0.0,
            json_mode=True,
            conversation_id=conversation_id,
            message_id=message_id,
        )
    except llm.LLMError as e:
        return Flag("low", "OTHER", f"classifier unavailable ({e})"[:200], "classifier")
    return parse_classifier(res.text)


def combine(*flags: Flag) -> Flag:
    """Highest severity wins; on a tie the keyword (explainable) result is kept."""
    best = NONE
    for f in flags:
        if f.rank > best.rank:
            best = f
    return best


def reply_key(flag: Flag) -> str:
    """Which fixed safety text to send."""
    if flag.category == "SELF_HARM":
        return "safety_self_harm"
    if flag.category == "EMERGENCY" or flag.severity == "emergency":
        return "safety_emergency"
    if flag.category == "ADVERSE_DRUG":
        return "safety_adverse_drug"
    if flag.category == "ADHERENCE":
        return "safety_adherence"
    return "safety_other"
