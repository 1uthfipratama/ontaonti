"""Demo data: staff, contacts and conversations across channels, cases, consents,
and a broadcast template. Idempotent (skips if the demo contacts exist).

    docker compose exec api python scripts/seed_demo.py
    python scripts/seed_demo.py            # outside Docker, with DATABASE_URL set

All demo identities are *simulated*: replies to them stay inside the app (the
simulator channel) and never reach Meta. Staff accounts use DEMO_STAFF_PASSWORD
from .env (skipped when it is empty). Test data only.
"""

import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.constants import (  # noqa: E402
    CASE_CLAIMED,
    CASE_OPEN,
    DIR_IN,
    DIR_NOTE,
    DIR_OUT,
    MODE_HUMAN,
    WINDOW_HOURS,
)
from app.db import SessionLocal, utcnow  # noqa: E402
from app.models import (  # noqa: E402
    Case,
    CaseNote,
    Consent,
    Contact,
    ContactIdentity,
    Conversation,
    Message,
    StaffUser,
    WaTemplate,
)
from app.security import hash_password  # noqa: E402
from app.services.settings_service import DEFAULTS  # noqa: E402

MARKER = "sim-demo-siti"

ANSWER_DURATION = (
    "Pengobatan TBC sensitif obat umumnya berlangsung *minimal 6 bulan*, dibagi menjadi tahap "
    "awal sekitar 2 bulan dan tahap lanjutan sekitar 4 bulan. Obatnya gratis di puskesmas. 💪\n\n"
    "Yang terpenting, minum obat setiap hari sampai tuntas sesuai petunjuk petugas kesehatan ya, "
    "Kak. Kalau ada keluhan, ceritakan ke petugas di puskesmas."
)
ANSWER_URINE = (
    "Air kencing yang berwarna kemerahan atau oranye adalah efek dari salah satu obat TBC dan "
    "umumnya *tidak berbahaya*. Tetap ceritakan ke petugas saat kontrol ya. Jika muncul mata atau "
    "kulit kuning, ruam parah, atau muntah terus, segera ke puskesmas hari itu juga."
)
ANSWER_EN = (
    "TB is *not* spread by sharing plates, glasses, clothes or by shaking hands. It spreads "
    "through the air when someone with untreated lung TB coughs or sneezes. Opening windows, "
    "covering coughs, and getting household contacts checked at the puskesmas all help."
)


def demo_password() -> str:
    pw = os.environ.get("DEMO_STAFF_PASSWORD", "")
    if not pw:
        env = Path(__file__).resolve().parent.parent / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("DEMO_STAFF_PASSWORD="):
                    pw = line.split("=", 1)[1].strip()
    return pw


async def staff(s, email: str, name: str, role: str, pw: str) -> StaffUser:
    u = (await s.execute(select(StaffUser).where(StaffUser.email == email))).scalar_one_or_none()
    if u is None:
        u = StaffUser(email=email, name=name, role=role, password_hash=hash_password(pw))
        s.add(u)
        await s.flush()
    return u


async def thread(s, name: str, channel: str, ext: str, turns: list[tuple], *, ago_hours: float,
                 notice: bool = True) -> tuple[Contact, Conversation, list[Message]]:  # fmt: skip
    """turns: (direction, sender_type, text[, flag_severity, flag_category]) spaced 1-3 min apart."""
    contact = Contact(display_name=name)
    s.add(contact)
    await s.flush()
    ident = ContactIdentity(contact_id=contact.id, channel=channel, external_id=ext,
                            display_name=name, simulated=True)  # fmt: skip
    s.add(ident)
    await s.flush()
    conv = Conversation(
        contact_id=contact.id, identity_id=ident.id, channel=channel, simulated=True
    )
    s.add(conv)
    await s.flush()
    t = utcnow() - timedelta(hours=ago_hours)
    msgs: list[Message] = []
    if notice:
        s.add(Consent(contact_id=contact.id, kind="privacy_notice", status="notified",
                      source="system", channel=channel, created_at=t))  # fmt: skip
    for i, turn in enumerate(turns):
        direction, sender, text = turn[:3]
        t = t + timedelta(seconds=4 if direction == DIR_OUT and sender == "bot" else 70 + 40 * i)
        m = Message(conversation_id=conv.id, direction=direction, sender_type=sender, text=text,
                    status="received" if direction == DIR_IN else "sent", created_at=t,
                    external_id=f"{ext}-{i}")  # fmt: skip
        if len(turn) > 3:
            m.flag_severity, m.flag_category = turn[3], turn[4]
            m.flag_reason = f"keyword: {turn[4].lower()}"
        if sender == "bot" and direction == DIR_OUT and len(text) > 200:
            m.tokens_in, m.tokens_out, m.cost_idr = 1450, 180, 77.6
        s.add(m)
        msgs.append(m)
        if direction == DIR_IN:
            conv.last_inbound_at = t
            conv.window_expires_at = t + timedelta(hours=WINDOW_HOURS)
    conv.last_message_at, conv.last_preview = t, turns[-1][2][:200]
    conv.unread_count = 1 if turns[-1][0] == DIR_IN else 0
    await s.flush()
    return contact, conv, msgs


async def main() -> None:
    async with SessionLocal() as s:
        if (
            await s.execute(select(ContactIdentity).where(ContactIdentity.external_id == MARKER))
        ).first():
            print("demo data already present; nothing to do")
            return
        pw = demo_password()
        agent = None
        if pw and len(pw) >= 10:
            agent = await staff(s, "agent@demo.local", "Agen Demo", "agent", pw)
            await staff(s, "reviewer@demo.local", "Reviewer Demo", "reviewer", pw)
            print(
                "demo staff: agent@demo.local, reviewer@demo.local (password: DEMO_STAFF_PASSWORD in .env)"
            )
        else:
            print("DEMO_STAFF_PASSWORD not set (10+ chars): demo staff skipped")

        notice = DEFAULTS["consent_notice_id"]
        # 1. Normal Q&A on WhatsApp, subscribed to broadcasts
        siti, _, _ = await thread(s, "Siti Rahma", "whatsapp", MARKER, [
            (DIR_IN, "user", "Halo kak, berapa lama sih pengobatan TBC?"),
            (DIR_OUT, "bot", notice),
            (DIR_OUT, "bot", ANSWER_DURATION),
            (DIR_IN, "user", "LANGGANAN"),
            (DIR_OUT, "bot", DEFAULTS["subscribe_confirm_id"]),
        ], ago_hours=30)  # fmt: skip
        siti.broadcast_opt_in = True
        s.add(Consent(contact_id=siti.id, kind="broadcast", status="granted", source="keyword",
                      channel="whatsapp"))  # fmt: skip

        # 2. Same person on Instagram, not merged yet (demo of contact merge)
        await thread(s, "siti.rahma (IG)", "instagram", "sim-demo-siti-ig", [
            (DIR_IN, "user", "Kak, aku yang kemarin chat di WhatsApp. Obatnya diminum pagi atau malam?"),
            (DIR_OUT, "bot", notice),
            (DIR_OUT, "bot", "Waktu minum obat ditentukan oleh petugas kesehatan yang merawat Kakak, "
                             "jadi saya tidak bisa menentukannya. Sebaiknya minum pada jam yang sama "
                             "setiap hari, dan tanyakan jadwal yang tepat ke petugas di puskesmas ya."),
        ], ago_hours=6)  # fmt: skip

        # 3. Messenger, low-severity side-effect question answered by the bot
        await thread(s, "Budi Santoso", "messenger", "sim-demo-budi", [
            (DIR_IN, "user", "Kenapa air kencing saya jadi oranye setelah minum obat?", "low", "OTHER"),
            (DIR_OUT, "bot", notice),
            (DIR_OUT, "bot", ANSWER_URINE),
        ], ago_hours=20)  # fmt: skip

        # 4. English on Instagram
        await thread(s, "Rina W.", "instagram", "sim-demo-rina", [
            (DIR_IN, "user", "Hi! Is TB contagious through sharing plates?"),
            (DIR_OUT, "bot", DEFAULTS["consent_notice_en"]),
            (DIR_OUT, "bot", ANSWER_EN),
        ], ago_hours=3)  # fmt: skip

        # 5. Emergency: fixed safety reply, case open, conversation handed to staff
        _, andi_conv, andi = await thread(s, "Andi P.", "whatsapp", "sim-demo-andi", [
            (DIR_IN, "user", "tolong saya batuk darah banyak sejak tadi pagi", "emergency", "EMERGENCY"),
            (DIR_OUT, "bot", notice),
            (DIR_OUT, "bot", DEFAULTS["safety_emergency_id"]),
            (DIR_NOTE, "system", "Mode → HUMAN (otomatis: EMERGENCY emergency)"),
        ], ago_hours=0.5)  # fmt: skip
        andi_conv.mode, andi_conv.flag_severity, andi_conv.flag_category = (
            MODE_HUMAN,
            "emergency",
            "EMERGENCY",
        )
        andi_conv.unread_count = 1
        s.add(Case(conversation_id=andi_conv.id, contact_id=andi_conv.contact_id, severity="emergency",
                   category="EMERGENCY", reason='keyword "batuk darah banyak"',
                   trigger_message_id=andi[0].id, status=CASE_OPEN))  # fmt: skip

        # 6. Adherence: case claimed by the agent, staff replied
        turns = [
            (DIR_IN, "user", "Kak obat saya habis dan saya capek, mau berhenti pengobatan aja", "high", "ADHERENCE"),
            (DIR_OUT, "bot", notice),
            (DIR_OUT, "bot", DEFAULTS["safety_adherence_id"]),
            (DIR_NOTE, "system", "Mode → HUMAN (otomatis: ADHERENCE high)"),
        ]  # fmt: skip
        if agent:
            turns.append((DIR_OUT, "agent", "Halo Bu Dewi, saya Agen dari yayasan. Boleh saya bantu "
                                            "jadwalkan ambil obat ke puskesmas besok pagi?"))  # fmt: skip
        _, dewi_conv, dewi = await thread(
            s, "Dewi Lestari", "whatsapp", "sim-demo-dewi", turns, ago_hours=26
        )
        dewi_conv.mode, dewi_conv.flag_severity, dewi_conv.flag_category = (
            MODE_HUMAN,
            "high",
            "ADHERENCE",
        )
        case = Case(conversation_id=dewi_conv.id, contact_id=dewi_conv.contact_id, severity="high",
                    category="ADHERENCE", reason='keyword "obat habis"', trigger_message_id=dewi[0].id,
                    status=CASE_CLAIMED if agent else CASE_OPEN,
                    assigned_to=agent.id if agent else None,
                    claimed_at=utcnow() - timedelta(hours=25) if agent else None)  # fmt: skip
        s.add(case)
        if agent:
            dewi_conv.assigned_to = agent.id
            dewi[-1].sender_staff_id = agent.id
            await s.flush()
            s.add(CaseNote(case_id=case.id, author_id=agent.id,
                           text="Sudah ditelepon. Pasien bosan & ongkos transport. Koordinasi dengan PMO."))  # fmt: skip

        # 7. Opted out
        wati, _, _ = await thread(s, "Wati", "whatsapp", "sim-demo-wati", [
            (DIR_IN, "user", "Apa itu TBC?"),
            (DIR_OUT, "bot", notice),
            (DIR_IN, "user", "STOP"),
            (DIR_OUT, "bot", DEFAULTS["optout_confirm_id"]),
        ], ago_hours=50)  # fmt: skip
        wati.opted_out, wati.opted_out_at = True, utcnow() - timedelta(hours=49)
        s.add(Consent(contact_id=wati.id, kind="messaging", status="revoked", source="keyword",
                      channel="whatsapp"))  # fmt: skip

        # Broadcast template (manual: register the same one in WhatsApp Manager for real sends)
        if not (
            await s.execute(select(WaTemplate).where(WaTemplate.name == "pengingat_kontrol"))
        ).first():
            body = ("Halo {{1}}, ini pengingat dari Onti Erlina: jadwal kontrol TBC Anda {{2}}. "
                    "Balas STOP untuk berhenti menerima pesan.")  # fmt: skip
            s.add(WaTemplate(name="pengingat_kontrol", language="id", category="UTILITY",
                             status="MANUAL", source="manual", body_text=body, variable_count=2,
                             components=[{"type": "BODY", "text": body}]))  # fmt: skip
        await s.commit()
    print("demo data created: 7 contacts, 7 conversations, 2 cases, 1 template")


if __name__ == "__main__":
    asyncio.run(main())
