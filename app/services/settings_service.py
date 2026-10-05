"""Runtime settings stored in the `settings` table, editable on the Settings page.

Each key has a default here; the table only holds overrides. `load()` returns
defaults merged with overrides. Texts marked *_id / *_en are picked by the
user's language (app/bot/language.py).
"""

import re
from dataclasses import dataclass
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as env
from app.models import Setting

PERSONA_PROMPT = """You are "Onti Erlina", a warm, patient companion for people affected by tuberculosis (TB) in Indonesia, run by a TB health foundation. People chat with you on WhatsApp, Messenger or Instagram.

Language: reply in Bahasa Indonesia by default, simple and friendly, addressing the person as "Kakak" or "Anda". If the person writes in English, reply in English.

Rules you must always follow:
1. Never diagnose. Never say or suggest that someone has, or does not have, TB or any other illness. Only a health worker can decide that after an examination.
2. Never tell anyone to start, change, pause or stop a medicine, and never give doses, amounts or schedules for any medicine.
3. Answer ONLY from the numbered passages in "Konteks" in the current message. If they don't cover the question, say honestly that you don't have that information yet and suggest asking a health worker at the puskesmas or our staff. Never invent facts, numbers, phone numbers, addresses or links.
4. Encourage the person to visit the puskesmas or a health worker for checks, tests and any treatment decision.
5. If something sounds urgent (coughing up a lot of blood, severe shortness of breath, chest pain, fainting, thoughts of self-harm), tell them to go to the nearest IGD or call 119 now.
6. Write exactly ONE short message: aim for 400-700 characters, never more than 900. Short paragraphs, warm and encouraging. Use WhatsApp formatting only: *bold*, _italic_ and simple "- " lists. No headings, tables or Markdown links.
7. After a sentence that uses a passage you may add its number like [1]; these markers are removed before sending.
8. Earlier messages in the chat are context only; facts must still come from the current passages."""

CONSENT_ID = (
    "Halo, saya *Onti Erlina* 👋, pendamping informasi TBC (layanan uji coba).\n\n"
    "Sebelum lanjut, mohon diketahui:\n"
    "- Pesan Anda disimpan dan dapat dibaca staf kami untuk pendampingan.\n"
    "- Jawaban saya adalah informasi umum, *bukan diagnosis* medis.\n"
    "- Dalam keadaan darurat, segera ke IGD terdekat atau hubungi 119.\n\n"
    "Balas *STOP* kapan saja untuk berhenti."
)
CONSENT_EN = (
    "Hi, I'm *Onti Erlina* 👋, a TB information companion (pilot service).\n\n"
    "Before we continue:\n"
    "- Your messages are stored and may be read by our staff to support you.\n"
    "- My answers are general information, *not a medical diagnosis*.\n"
    "- In an emergency, go to the nearest emergency room (IGD) or call 119.\n\n"
    "Reply *STOP* at any time to stop."
)

DEFAULTS: dict[str, Any] = {
    # --- bot ---------------------------------------------------------------
    "persona_prompt": PERSONA_PROMPT,
    "model_answer": "",  # empty = LLM_MODEL_ANSWER / provider default
    "model_classifier": "",
    "history_turns": 6,
    "retrieval_k": 4,
    "max_input_chars": 500,
    "max_output_tokens": 400,
    "max_reply_chars": 900,
    "transcribe_voice": True,
    # --- safety ------------------------------------------------------------
    "flag_rules": None,  # None = config/flags.yaml
    "classifier_enabled": True,
    "safety_emergency_id": (
        "Kondisi yang Anda ceritakan bisa berbahaya. 🚨 *Segera ke IGD rumah sakit terdekat "
        "atau hubungi 119 sekarang.* Jika ada orang di dekat Anda, minta mereka menemani.\n\n"
        "Staf kami sudah diberi tahu dan akan menghubungi Anda secepatnya."
    ),
    "safety_emergency_en": (
        "What you describe could be dangerous. 🚨 *Please go to the nearest emergency room "
        "(IGD) or call 119 now.* If someone is near you, ask them to stay with you.\n\n"
        "Our staff have been alerted and will contact you as soon as possible."
    ),
    "safety_self_harm_id": (
        "Terima kasih sudah mau bercerita. Keselamatan Anda sangat penting dan Anda tidak "
        "sendirian. 💛 *Jika Anda dalam bahaya atau berpikir untuk menyakiti diri, segera ke "
        "IGD terdekat atau hubungi 119.* Jika bisa, hubungi orang yang Anda percaya untuk "
        "menemani.\n\nStaf kami sudah diberi tahu dan akan segera menghubungi Anda."
    ),
    "safety_self_harm_en": (
        "Thank you for telling me. Your safety matters and you are not alone. 💛 *If you are "
        "in danger or thinking about hurting yourself, go to the nearest emergency room (IGD) "
        "or call 119 now.* If you can, reach out to someone you trust to be with you.\n\n"
        "Our staff have been alerted and will contact you soon."
    ),
    "safety_adverse_drug_id": (
        "Terima kasih sudah memberi tahu. Keluhan seperti ini perlu segera diperiksa petugas "
        "kesehatan. *Hari ini juga, hubungi atau datang ke puskesmas/petugas TBC Anda* dan bawa "
        "obat yang sedang diminum. Jika terasa berat atau darurat, ke IGD atau hubungi 119.\n\n"
        "Staf kami sudah diberi tahu dan akan menghubungi Anda."
    ),
    "safety_adverse_drug_en": (
        "Thank you for letting me know. This needs to be checked by a health worker soon. "
        "*Today, please contact or visit your puskesmas/TB health worker* and bring your "
        "medicines. If it feels severe or urgent, go to the IGD or call 119.\n\n"
        "Our staff have been alerted and will contact you."
    ),
    "safety_adherence_id": (
        "Terima kasih sudah jujur bercerita. 🙏 Melanjutkan pengobatan sampai tuntas sangat "
        "penting, dan petugas kesehatan bisa membantu mencari jalan keluarnya. *Mohon segera "
        "hubungi puskesmas/petugas TBC Anda.*\n\nStaf kami sudah diberi tahu dan akan "
        "menghubungi Anda."
    ),
    "safety_adherence_en": (
        "Thank you for being honest with me. 🙏 Finishing TB treatment is very important, and "
        "health workers can help find a solution. *Please contact your puskesmas/TB health "
        "worker soon.*\n\nOur staff have been alerted and will contact you."
    ),
    "safety_other_id": (
        "Terima kasih atas pesannya. Hal ini sebaiknya ditangani langsung oleh petugas. Staf "
        "kami sudah diberi tahu dan akan menghubungi Anda. Jika darurat, segera ke IGD atau "
        "hubungi 119."
    ),
    "safety_other_en": (
        "Thank you for your message. This is best handled by a person. Our staff have been "
        "alerted and will contact you. In an emergency, go to the IGD or call 119."
    ),
    # --- consent & keywords -----------------------------------------------
    "consent_notice_id": CONSENT_ID,
    "consent_notice_en": CONSENT_EN,
    "optout_confirm_id": (
        "Baik, Anda sudah berhenti menerima pesan dari Onti Erlina. Ketik *MULAI* jika ingin "
        "memulai lagi. Jika darurat, segera ke IGD atau hubungi 119."
    ),
    "optout_confirm_en": (
        "Okay, you will no longer receive messages from Onti Erlina. Type *START* to begin "
        "again. In an emergency, go to the IGD or call 119."
    ),
    "optin_confirm_id": "Selamat datang kembali! 😊 Silakan ketik pertanyaan Anda tentang TBC.",
    "optin_confirm_en": "Welcome back! 😊 Please type your question about TB.",
    "subscribe_confirm_id": (
        "Terima kasih! Anda akan menerima info dan pengingat berkala dari kami. Balas *STOP* "
        "kapan saja untuk berhenti."
    ),
    "subscribe_confirm_en": (
        "Thank you! You will receive occasional updates and reminders. Reply *STOP* at any "
        "time to stop."
    ),
    "non_text_reply_id": (
        "Maaf, saat ini saya baru bisa membaca pesan teks. 🙏 Silakan ketik pertanyaan Anda. "
        "Staf kami tetap bisa melihat kiriman Anda."
    ),
    "non_text_reply_en": (
        "Sorry, I can only read text messages for now. 🙏 Please type your question. Our "
        "staff can still see what you sent."
    ),
    # --- limits & budget ---------------------------------------------------
    "daily_message_cap": 30,
    "rate_limit_count": 20,
    "rate_limit_window_minutes": 10,
    "rate_limit_reply_id": (
        "Maaf, pesan yang masuk terlalu banyak dalam waktu singkat. Mohon tunggu sekitar 10 "
        "menit lalu coba lagi. Jika darurat, segera ke IGD atau hubungi 119."
    ),
    "rate_limit_reply_en": (
        "Sorry, that's a lot of messages in a short time. Please wait about 10 minutes and try "
        "again. In an emergency, go to the IGD or call 119."
    ),
    "daily_cap_reply_id": (
        "Anda sudah mencapai batas pesan otomatis untuk hari ini. Staf kami tetap dapat membaca "
        "pesan Anda dan akan membalas bila perlu. Jika darurat, segera ke IGD atau hubungi 119."
    ),
    "daily_cap_reply_en": (
        "You've reached today's limit for automatic replies. Our staff can still read your "
        "messages and will reply if needed. In an emergency, go to the IGD or call 119."
    ),
    "monthly_budget_idr": 300000,
    "budget_alert_ratio": 0.8,
    "budget_fallback_mode": "classifier_model",  # classifier_model | fixed_reply
    "budget_fallback_reply_id": (
        "Terima kasih atas pesannya. Staf kami akan menghubungi Anda secepatnya. Jika darurat, "
        "segera ke IGD terdekat atau hubungi 119."
    ),
    "budget_fallback_reply_en": (
        "Thank you for your message. Our staff will contact you as soon as possible. In an "
        "emergency, go to the nearest IGD or call 119."
    ),
    # --- office hours ---------------------------------------------------------
    "office_hours_enabled": False,
    "office_days": [1, 2, 3, 4, 5],  # ISO weekdays, Monday = 1
    "office_open": "08:00",
    "office_close": "16:00",
    "away_message_id": (
        "Terima kasih, pesan Anda sudah kami terima. 🙏 Staf kami bertugas *{jam}* dan akan "
        "membalas saat jam layanan. Jika darurat, segera ke IGD terdekat atau hubungi 119."
    ),
    "away_message_en": (
        "Thank you, we've received your message. 🙏 Our staff are available *{hours}* and will "
        "reply during those hours. In an emergency, go to the nearest IGD or call 119."
    ),
    # --- WhatsApp pricing (estimates for broadcasts / dashboard) ------------
    "wa_rate_marketing_idr": 680,
    "wa_rate_utility_idr": 330,
    "wa_free_tier_messages": 1000,
}

NUMBER_KEYS = {
    k for k, v in DEFAULTS.items() if isinstance(v, (int, float)) and not isinstance(v, bool)
}
BOOL_KEYS = {k for k, v in DEFAULTS.items() if isinstance(v, bool)}
CHOICES = {"budget_fallback_mode": ("classifier_model", "fixed_reply")}
TIME_KEYS = {"office_open", "office_close"}
DAYS_KEYS = {"office_days"}

# Settings page layout: (group, [keys]).
GROUPS: list[tuple[str, list[str]]] = [
    ("Bot", ["persona_prompt", "model_answer", "model_classifier", "history_turns",
             "retrieval_k", "max_input_chars", "max_output_tokens", "max_reply_chars",
             "transcribe_voice"]),
    ("Safety", ["classifier_enabled", "safety_emergency_id", "safety_emergency_en",
                "safety_self_harm_id", "safety_self_harm_en", "safety_adverse_drug_id",
                "safety_adverse_drug_en", "safety_adherence_id", "safety_adherence_en",
                "safety_other_id", "safety_other_en"]),
    ("Consent & keywords", ["consent_notice_id", "consent_notice_en", "optout_confirm_id",
                            "optout_confirm_en", "optin_confirm_id", "optin_confirm_en",
                            "subscribe_confirm_id", "subscribe_confirm_en",
                            "non_text_reply_id", "non_text_reply_en"]),
    ("Limits & budget", ["monthly_budget_idr", "budget_alert_ratio", "budget_fallback_mode",
                         "budget_fallback_reply_id", "budget_fallback_reply_en",
                         "daily_message_cap", "daily_cap_reply_id", "daily_cap_reply_en",
                         "rate_limit_count", "rate_limit_window_minutes",
                         "rate_limit_reply_id", "rate_limit_reply_en"]),
    ("Office hours", ["office_hours_enabled", "office_days", "office_open", "office_close",
                      "away_message_id", "away_message_en"]),
    ("WhatsApp pricing", ["wa_rate_marketing_idr", "wa_rate_utility_idr", "wa_free_tier_messages"]),
]  # fmt: skip


def default_flag_rules() -> dict:
    return yaml.safe_load(env.flags_file.read_text(encoding="utf-8"))


@dataclass
class Config:
    values: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def text(self, key: str, lang: str) -> str:
        """Localised text: key_<lang>, falling back to Indonesian."""
        return self.values.get(f"{key}_{lang}") or self.values[f"{key}_id"]

    @property
    def answer_model(self) -> str:
        return self.values["model_answer"] or env.answer_model

    @property
    def classifier_model(self) -> str:
        return self.values["model_classifier"] or env.classifier_model

    @property
    def flag_rules(self) -> dict:
        return self.values["flag_rules"] or default_flag_rules()


async def load(session: AsyncSession) -> Config:
    values = dict(DEFAULTS)
    rows = (await session.execute(select(Setting))).scalars().all()
    for row in rows:
        if row.key in DEFAULTS:
            values[row.key] = row.value
    return Config(values)


def coerce(key: str, value: Any) -> Any:
    """Validate one incoming value from the Settings page."""
    if key not in DEFAULTS:
        raise ValueError(f"unknown setting {key}")
    if key in BOOL_KEYS:
        return bool(value)
    if key in NUMBER_KEYS:
        num = float(value)
        if num < 0:
            raise ValueError(f"{key} must be >= 0")
        return int(num) if isinstance(DEFAULTS[key], int) else num
    if key in TIME_KEYS:
        if not isinstance(value, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError(f"{key} must be HH:MM")
        return value
    if key in DAYS_KEYS:
        days = sorted({int(d) for d in value or []})
        if any(d < 1 or d > 7 for d in days):
            raise ValueError(f"{key} must be weekdays 1-7")
        return days
    if key in CHOICES and value not in CHOICES[key]:
        raise ValueError(f"{key} must be one of {CHOICES[key]}")
    if key == "flag_rules":
        if value is None:
            return None
        from app.bot.safety import validate_rules

        return validate_rules(value)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be text")
    return value


async def get_value(session: AsyncSession, key: str) -> Any:
    row = await session.get(Setting, key)
    return row.value if row else DEFAULTS.get(key)


async def set_value(
    session: AsyncSession, key: str, value: Any, user_id: int | None = None
) -> None:
    """Internal bookkeeping keys (e.g. budget alert month) may be outside DEFAULTS."""
    row = await session.get(Setting, key)
    if row:
        row.value, row.updated_by = value, user_id
    else:
        session.add(Setting(key=key, value=value, updated_by=user_id))
