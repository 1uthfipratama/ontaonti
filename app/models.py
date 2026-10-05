"""Database models. Types are kept portable (strings for enums, JSON) so the test
suite can run on SQLite while production runs on PostgreSQL."""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import CASE_OPEN, CONV_OPEN, MODE_BOT
from app.db import Base, utcnow

TS = DateTime(timezone=True)


class StaffUser(Base):
    __tablename__ = "staff_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="agent")  # admin | agent | reviewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Bumped on password change / deactivation: invalidates every existing session.
    session_epoch: Mapped[int] = mapped_column(Integer, default=0)
    # Two-factor login (app/totp.py). The secret is set at setup, enabled once confirmed.
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_last_step: Mapped[int | None] = mapped_column(Integer)  # replay guard
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(TS)


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str] = mapped_column(Text, default="")
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    opted_out_at: Mapped[datetime | None] = mapped_column(TS)
    # Denormalised from the consents log for fast broadcast filtering.
    broadcast_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    # TB programme: where the person is in their care (app/services/journey.py).
    journey_stage: Mapped[str | None] = mapped_column(String(12), index=True)
    treatment_start: Mapped[date | None] = mapped_column(Date)
    treatment_months: Mapped[int] = mapped_column(Integer, default=6)
    puskesmas: Mapped[str] = mapped_column(String(120), default="")
    kader_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id", ondelete="SET NULL"))
    # Daily medication reminder (app/services/reminders.py); staff switch it on.
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_time: Mapped[str] = mapped_column(String(5), default="07:00")  # local HH:MM
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow)

    identities: Mapped[list["ContactIdentity"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan", lazy="selectin"
    )


class ContactIdentity(Base):
    __tablename__ = "contact_identities"
    __table_args__ = (UniqueConstraint("channel", "external_id", name="uq_identity_channel_ext"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str] = mapped_column(String(128))  # wa_id / PSID / IGSID / sim-...
    display_name: Mapped[str] = mapped_column(String(200), default="")
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(TS)

    contact: Mapped[Contact] = relationship(back_populates="identities")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_status_last", "status", "last_message_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), index=True)
    identity_id: Mapped[int] = mapped_column(ForeignKey("contact_identities.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(10), default=CONV_OPEN)  # OPEN | RESOLVED
    mode: Mapped[str] = mapped_column(String(10), default=MODE_BOT)  # BOT | HUMAN
    assigned_to: Mapped[int | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    window_expires_at: Mapped[datetime | None] = mapped_column(TS)
    last_message_at: Mapped[datetime | None] = mapped_column(TS)
    last_inbound_at: Mapped[datetime | None] = mapped_column(TS)
    last_preview: Mapped[str] = mapped_column(String(200), default="")
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    # Highest flag since the last resolve; drives the inbox flag filter.
    flag_severity: Mapped[str] = mapped_column(String(12), default="none")
    flag_category: Mapped[str | None] = mapped_column(String(30))
    # Last out-of-hours away message: at most one per closed period.
    away_sent_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow)

    identity: Mapped[ContactIdentity] = relationship(lazy="joined")
    contact: Mapped[Contact] = relationship(lazy="joined")
    labels: Mapped[list["Label"]] = relationship(
        secondary="conversation_labels", lazy="selectin", order_by="Label.name"
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conv_created", "conversation_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(String(4))  # in | out | note
    sender_type: Mapped[str] = mapped_column(String(10))  # user | bot | agent | system
    sender_staff_id: Mapped[int | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    text: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(20), default="text")  # text | image | audio | ...
    media_url: Mapped[str | None] = mapped_column(String(500))
    # Channel message id (wamid, mid). Unique: a redelivered webhook can't insert twice.
    external_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    status: Mapped[str] = mapped_column(String(12), default="received")
    error: Mapped[str | None] = mapped_column(Text)
    flag_severity: Mapped[str | None] = mapped_column(String(12))
    flag_category: Mapped[str | None] = mapped_column(String(30))
    flag_reason: Mapped[str | None] = mapped_column(Text)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_idr: Mapped[float] = mapped_column(Float, default=0.0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), index=True)
    severity: Mapped[str] = mapped_column(String(12))
    category: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(12), default=CASE_OPEN)  # OPEN | CLAIMED | RESOLVED
    assigned_to: Mapped[int | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    trigger_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    claimed_at: Mapped[datetime | None] = mapped_column(TS)
    resolved_at: Mapped[datetime | None] = mapped_column(TS)
    resolved_by: Mapped[int | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )


class Consent(Base):
    """Append-only log of consent events per contact."""

    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))  # privacy_notice | broadcast | messaging
    status: Mapped[str] = mapped_column(String(12))  # notified | granted | revoked
    source: Mapped[str] = mapped_column(String(20))  # keyword | staff | system
    channel: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[object] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow)
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )


class LlmUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    purpose: Mapped[str] = mapped_column(String(20))  # answer | classifier | summary
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    cost_idr: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text)
    conversation_id: Mapped[int | None] = mapped_column(Integer)
    message_id: Mapped[int | None] = mapped_column(Integer)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id", ondelete="SET NULL"))
    actor_email: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")


class CaseNote(Base):
    __tablename__ = "case_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id", ondelete="SET NULL"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class WaTemplate(Base):
    """WhatsApp message template (synced from the WABA or registered by hand)."""

    __tablename__ = "wa_templates"
    __table_args__ = (UniqueConstraint("name", "language", name="uq_template_name_lang"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    language: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(30), default="UTILITY")
    status: Mapped[str] = mapped_column(String(20), default="MANUAL")  # APPROVED | PENDING | ...
    body_text: Mapped[str] = mapped_column(Text, default="")
    variable_count: Mapped[int] = mapped_column(Integer, default=0)
    components: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(10), default="manual")  # sync | manual
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow)


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    template_id: Mapped[int] = mapped_column(ForeignKey("wa_templates.id"))
    # One entry per {{n}}: a literal, or "{{name}}" for the contact's name.
    variables: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(12), default="draft")  # draft|sending|done|cancelled
    recipient_count: Mapped[int] = mapped_column(Integer, default=0)
    rate_idr: Mapped[float] = mapped_column(Float, default=0.0)
    est_cost_idr: Mapped[float] = mapped_column(Float, default=0.0)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(TS)
    finished_at: Mapped[datetime | None] = mapped_column(TS)


class BroadcastRecipient(Base):
    __tablename__ = "broadcast_recipients"
    __table_args__ = (UniqueConstraint("broadcast_id", "contact_id", name="uq_bc_recipient"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    broadcast_id: Mapped[int] = mapped_column(
        ForeignKey("broadcasts.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    identity_id: Mapped[int] = mapped_column(
        ForeignKey("contact_identities.id", ondelete="CASCADE")
    )
    # pending | sent | delivered | read | failed | skipped
    status: Mapped[str] = mapped_column(String(12), default="pending")
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    external_id: Mapped[str | None] = mapped_column(String(160), index=True)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(TS)
    delivered_at: Mapped[datetime | None] = mapped_column(TS)
    read_at: Mapped[datetime | None] = mapped_column(TS)


class SavedReply(Base):
    """Canned reply staff insert with "/" in the reply box."""

    __tablename__ = "saved_replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    shortcut: Mapped[str] = mapped_column(String(40), unique=True)  # e.g. "jadwal"
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow)


class DoseLog(Base):
    """One medication reminder and its answer, per contact per (local) day."""

    __tablename__ = "dose_logs"
    __table_args__ = (UniqueConstraint("contact_id", "day", name="uq_dose_contact_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date] = mapped_column(Date)
    # pending (asked) | taken | missed (said not yet, or no answer) | skipped (couldn't ask)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    note: Mapped[str] = mapped_column(String(200), default="")
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    sent_at: Mapped[datetime | None] = mapped_column(TS)
    answered_at: Mapped[datetime | None] = mapped_column(TS)
    followup_sent: Mapped[bool] = mapped_column(Boolean, default=False)


class ScreeningSession(Base):
    """TB symptom screening over chat (app/services/screening.py)."""

    __tablename__ = "screenings"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    lang: Mapped[str] = mapped_column(String(2), default="id")
    step: Mapped[int] = mapped_column(Integer, default=0)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)  # question id -> yes (true) / no
    status: Mapped[str] = mapped_column(String(10), default="active")  # active | done | abandoned
    result: Mapped[str | None] = mapped_column(String(12))  # presumptive | negative
    started_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(TS)


class Task(Base):
    """Follow-up work for staff and kader: a call, a home visit, anything else."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10), default="call")  # call | visit | other
    title: Mapped[str] = mapped_column(String(200))
    note: Mapped[str] = mapped_column(Text, default="")
    due: Mapped[date | None] = mapped_column(Date, index=True)
    assigned_to: Mapped[int | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(8), default="open")  # open | done
    outcome: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20), default="staff")  # staff | missed_doses
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    done_at: Mapped[datetime | None] = mapped_column(TS)


class KbArticle(Base):
    """Knowledge-base article, edited on the Knowledge page. Published articles are
    exported as Markdown and indexed for the bot (app/services/knowledge.py)."""

    __tablename__ = "kb_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(40), unique=True)  # cited as the source, e.g. "p05"
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")  # Markdown: intro, then "## " sections
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TS, default=utcnow, onupdate=utcnow)


class KbGap(Base):
    """A question the bot couldn't answer from the knowledge base."""

    __tablename__ = "kb_gaps"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), index=True
    )
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | done | ignored
    handled_by: Mapped[int | None] = mapped_column(
        ForeignKey("staff_users.id", ondelete="SET NULL")
    )
    handled_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow, index=True)


class Label(Base):
    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class ConversationLabel(Base):
    __tablename__ = "conversation_labels"

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    label_id: Mapped[int] = mapped_column(
        ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True
    )
