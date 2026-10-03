"""Turn model output into one WhatsApp-friendly message."""

import re


def to_whatsapp(text: str) -> str:
    t = text.replace("\r\n", "\n")
    t = re.sub(r"^#{1,6}\s*(.+?)\s*#*$", r"*\1*", t, flags=re.M)  # headings -> bold line
    t = re.sub(r"\*\*(.+?)\*\*", r"*\1*", t, flags=re.S)  # **bold** -> *bold*
    t = re.sub(r"__(.+?)__", r"_\1_", t, flags=re.S)
    t = re.sub(r"~~(.+?)~~", r"~\1~", t, flags=re.S)
    t = re.sub(r"^\s*[*•]\s+", "- ", t, flags=re.M)  # "* item" would read as bold
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1 (\2)", t)  # [text](url)
    t = re.sub(r"`{1,3}", "", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


SENTENCE_END = re.compile(r"[.!?…][*_~)\]\"'”’]*(?=\s|$)|\n\n")


def trim_incomplete(text: str) -> str:
    """Drop a trailing fragment when the model was cut off by max_tokens
    ("...tuntas. Jen" -> "...tuntas."). Keeps the text if no sentence end exists."""
    t = text.rstrip()
    ends = [m.end() for m in SENTENCE_END.finditer(t)]
    if not ends:
        return t
    return t[: ends[-1]].rstrip()


def clamp(text: str, limit: int) -> str:
    """At most `limit` characters, cut at a sentence (or word) boundary."""
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    floor = int(limit * 0.6)
    ends = [m.end() for m in re.finditer(r"[.!?](\s|$)|\n", cut) if m.end() >= floor]
    if ends:
        return cut[: ends[-1]].rstrip()
    return cut.rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
