"""Shared enums (stored as plain strings so SQLite tests and Postgres agree)."""

CHANNELS = ("whatsapp", "messenger", "instagram")

ROLES = ("admin", "agent", "reviewer")

CONV_OPEN, CONV_RESOLVED = "OPEN", "RESOLVED"
MODE_BOT, MODE_HUMAN = "BOT", "HUMAN"

# messages.direction: "note" = internal, never sent (mode changes, assignments...)
DIR_IN, DIR_OUT, DIR_NOTE = "in", "out", "note"
SENDER_USER, SENDER_BOT, SENDER_AGENT, SENDER_SYSTEM = "user", "bot", "agent", "system"

# messages.status
MSG_RECEIVED, MSG_QUEUED, MSG_SENT, MSG_DELIVERED, MSG_READ, MSG_FAILED = (
    "received",
    "queued",
    "sent",
    "delivered",
    "read",
    "failed",
)
STATUS_ORDER = {MSG_QUEUED: 0, MSG_SENT: 1, MSG_DELIVERED: 2, MSG_READ: 3}

SEVERITIES = ("none", "low", "high", "emergency")
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}

CASE_OPEN, CASE_CLAIMED, CASE_RESOLVED = "OPEN", "CLAIMED", "RESOLVED"

WINDOW_HOURS = 24  # WhatsApp / Messenger / Instagram customer-service window
HUMAN_AGENT_DAYS = 7  # Messenger / Instagram HUMAN_AGENT tag


def max_severity(*levels: str | None) -> str:
    return max((lv or "none" for lv in levels), key=lambda s: SEVERITY_RANK.get(s, 0))


def at_least(level: str | None, threshold: str) -> bool:
    return SEVERITY_RANK.get(level or "none", 0) >= SEVERITY_RANK[threshold]
