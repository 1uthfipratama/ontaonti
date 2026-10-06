"""Demo data: staff, contacts and conversations across channels, cases, consents,
a broadcast template, and the TB programme (patient stages, two weeks of medication
reminders, a screening, tasks, saved replies, labels, unanswered questions).
Idempotent (skips if the demo contacts exist).

    docker compose exec api python scripts/seed_demo.py
    python scripts/seed_demo.py            # outside Docker, with DATABASE_URL set

All demo identities are *simulated*: replies to them stay inside the app (the
simulator channel) and never reach Meta. Staff accounts use DEMO_STAFF_PASSWORD
from .env (skipped when it is empty). Test data only.
"""

import asyncio
import os
import sys
from datetime import datetime, time, timedelta
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
    ConversationLabel,
    DoseLog,
    KbGap,
    Label,
    Message,
    SavedReply,
    ScreeningSession,
    Setting,
    StaffUser,
    Task,
    WaTemplate,
)
from app.security import hash_password  # noqa: E402
from app.services import screening  # noqa: E402
from app.services.reminders import BUTTONS, _tz, local_today  # noqa: E402
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
        budi, _, _ = await thread(s, "Budi Santoso", "messenger", "sim-demo-budi", [
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
        andi_contact, andi_conv, andi = await thread(s, "Andi P.", "whatsapp", "sim-demo-andi", [
            (DIR_IN, "user", "tolong saya batuk darah banyak sejak tadi pagi", "emergency", "EMERGENCY"),
            (DIR_OUT, "bot", notice),
            (DIR_OUT, "bot", DEFAULTS["safety_emergency_id"]),
            (DIR_NOTE, "system", "Bot berhenti otomatis: darurat. Staf menangani."),
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
            (DIR_NOTE, "system", "Bot berhenti otomatis: pengobatan terhenti. Staf menangani."),
        ]  # fmt: skip
        if agent:
            turns.append((DIR_OUT, "agent", "Halo Bu Dewi, saya Agen dari yayasan. Boleh saya bantu "
                                            "jadwalkan ambil obat ke puskesmas besok pagi?"))  # fmt: skip
        dewi_contact, dewi_conv, dewi = await thread(
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
        await programme(s, agent, siti, budi, dewi_contact, dewi_conv, andi_contact, andi_conv)
        await s.commit()
    print("demo data created: 10 contacts, 8 conversations, 2 cases, 1 template, TB programme")


def local_at(day, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm), tzinfo=_tz())


async def add_turns(s, conv: Conversation, start: datetime, turns: list[tuple]) -> list[Message]:
    """Append (direction, sender, text, meta) turns a minute apart."""
    out = []
    for i, (direction, sender, text, meta) in enumerate(turns):
        t = start + timedelta(minutes=i)
        m = Message(conversation_id=conv.id, direction=direction, sender_type=sender, text=text,
                    status="received" if direction == DIR_IN else "sent", created_at=t, meta=meta)  # fmt: skip
        s.add(m)
        out.append(m)
        if direction == DIR_IN:
            conv.last_inbound_at, conv.window_expires_at = t, t + timedelta(hours=WINDOW_HOURS)
        conv.last_message_at, conv.last_preview = t, text[:200]
    await s.flush()
    return out


async def programme(s, agent, siti, budi, dewi, dewi_conv, andi, andi_conv) -> None:
    """Patients board, reminders, a screening, tasks, saved replies, labels, KB gaps."""
    today = local_today()
    titles = [t for _, t in BUTTONS]

    # Patient journey
    siti.journey_stage, siti.treatment_start = "treatment", today - timedelta(days=70)
    siti.puskesmas, siti.reminder_enabled, siti.reminder_time = "Puskesmas Menteng", True, "07:00"
    budi.journey_stage, budi.treatment_start = "treatment", today - timedelta(days=20)
    budi.puskesmas, budi.reminder_enabled, budi.reminder_time = "Puskesmas Tebet", True, "19:00"
    dewi.journey_stage, dewi.treatment_start = "treatment", today - timedelta(days=118)
    dewi.puskesmas = "Puskesmas Cilandak"
    andi.journey_stage, andi.puskesmas = "testing", "Puskesmas Menteng"
    for c in (siti, dewi, andi):
        c.kader_id = agent.id if agent else None
    for name, stage, start, pkm in [
        ("Hendra Gunawan", "completed", today - timedelta(days=200), "Puskesmas Tebet"),
        ("Sri Wahyuni", "lost", today - timedelta(days=95), "Puskesmas Cilandak"),
    ]:
        s.add(Contact(display_name=name, journey_stage=stage, treatment_start=start, puskesmas=pkm))

    # Two weeks of reminder answers (Siti: one slip; Budi: a shaky first month)
    siti_conv = (
        (await s.execute(select(Conversation).where(Conversation.contact_id == siti.id)))
        .scalars()
        .first()
    )
    budi_conv = (
        (await s.execute(select(Conversation).where(Conversation.contact_id == budi.id)))
        .scalars()
        .first()
    )
    for back in range(1, 15):
        day = today - timedelta(days=back)
        st = "missed" if back == 6 else "taken"
        s.add(DoseLog(contact_id=siti.id, day=day, status=st, conversation_id=siti_conv.id,
                      sent_at=local_at(day, 7), answered_at=local_at(day, 7, 12)))  # fmt: skip
        if back <= 7:
            st = "missed" if back in (2, 5) else "taken"
            s.add(DoseLog(contact_id=budi.id, day=day, status=st, conversation_id=budi_conv.id,
                          sent_at=local_at(day, 19), answered_at=local_at(day, 19, 20)))  # fmt: skip
    # Yesterday's reminder in Siti's chat
    await add_turns(s, siti_conv, local_at(today - timedelta(days=1), 7), [
        (DIR_OUT, "bot", "Halo Siti 👋 Sudah minum obat TBC hari ini?", {"reminder": "1", "buttons": titles}),
        (DIR_IN, "user", "Sudah ✅", {}),
        (DIR_OUT, "bot", DEFAULTS["reminder_taken_id"].replace("{nama}", "Siti"), {"dose": "taken"}),
    ])  # fmt: skip
    if agent:
        s.add(Message(conversation_id=siti_conv.id, direction=DIR_NOTE, sender_type="agent",
                      sender_staff_id=agent.id, status="sent",
                      text="PMO: suami. Kontrol berikutnya Senin depan.",
                      created_at=local_at(today - timedelta(days=1), 9)))  # fmt: skip

    # A finished screening that suggests testing
    spec = screening.spec()
    yusuf, yusuf_conv, _ = await thread(s, "Yusuf Hidayat", "whatsapp", "sim-demo-yusuf", [
        (DIR_IN, "user", "SKRINING"),
        (DIR_OUT, "bot", DEFAULTS["consent_notice_id"]),
    ], ago_hours=4)  # fmt: skip
    answers = {"cough_2w": True, "fever": True, "night_sweats": False, "weight_loss": True,
               "contact": False}  # fmt: skip
    sc = ScreeningSession(contact_id=yusuf.id, conversation_id=yusuf_conv.id, lang="id",
                          step=len(spec.questions), answers=answers, status="done",
                          result="presumptive", started_at=utcnow() - timedelta(hours=4),
                          finished_at=utcnow() - timedelta(hours=3, minutes=50))  # fmt: skip
    s.add(sc)
    await s.flush()
    turns = [(DIR_OUT, "bot", spec.text("intro", "id").replace("{n}", str(len(spec.questions))),
              {"screening": sc.id})]  # fmt: skip
    for i, q in enumerate(spec.questions):
        turns.append((DIR_OUT, "bot", f"({i + 1}/{len(spec.questions)}) {q['text_id']}",
                      {"screening": sc.id, "question": q["id"], "buttons": ["Ya", "Tidak"]}))  # fmt: skip
        turns.append((DIR_IN, "user", "Ya" if answers[q["id"]] else "Tidak", {}))
    turns.append((DIR_OUT, "bot", spec.text("result_positive", "id"),
                  {"screening": sc.id, "result": "presumptive"}))  # fmt: skip
    await add_turns(s, yusuf_conv, utcnow() - timedelta(hours=3, minutes=58), turns)
    yusuf.journey_stage = "suspect"

    # Tasks: one overdue, one for today, one from the screening
    kader = agent.id if agent else None
    s.add_all([
        Task(contact_id=andi.id, kind="call", title="Hubungi Andi: pastikan sudah ke IGD / puskesmas",
             due=today - timedelta(days=1), assigned_to=kader),
        Task(contact_id=dewi.id, kind="visit", title="Kunjungan rumah Bu Dewi: antar obat, cek PMO",
             due=today, assigned_to=kader),
        Task(contact_id=yusuf.id, kind="call", source="screening",
             title="Skrining TBC: Yusuf Hidayat disarankan periksa", assigned_to=kader),
    ])  # fmt: skip

    # Saved replies and labels
    for shortcut, title, body in [
        (
            "jadwal",
            "Jadwal kontrol",
            "Halo {nama}, jadwal kontrol berikutnya di puskesmas hari Senin pukul 08.00. "
            "Jangan lupa bawa kartu berobat ya 🙏",
        ),
        (
            "pmo",
            "Tentang PMO",
            "PMO (Pengawas Menelan Obat) adalah orang dekat yang membantu mengingatkan minum obat "
            "setiap hari. Bisa keluarga, teman, atau kader. Kakak sudah punya PMO?",
        ),
        (
            "terimakasih",
            "Terima kasih",
            "Terima kasih sudah menghubungi kami, {nama}. Semangat terus berobatnya ya 💪",
        ),
    ]:
        s.add(SavedReply(shortcut=shortcut, title=title, body=body))
    call, visit = Label(name="Perlu telepon"), Label(name="Kunjungan rumah")
    s.add_all([call, visit, Label(name="Pasien baru")])
    await s.flush()
    s.add_all([
        ConversationLabel(conversation_id=andi_conv.id, label_id=call.id),
        ConversationLabel(conversation_id=dewi_conv.id, label_id=visit.id),
    ])  # fmt: skip

    # Questions the knowledge base didn't cover
    s.add_all([
        KbGap(question="Apakah yayasan menyediakan bantuan uang transport ke puskesmas?",
              conversation_id=dewi_conv.id, created_at=utcnow() - timedelta(hours=20)),
        KbGap(question="Apakah boleh berpuasa saat minum obat TBC?",
              created_at=utcnow() - timedelta(hours=5)),
    ])  # fmt: skip

    # Medication reminders on (master switch in Settings)
    if await s.get(Setting, "reminder_enabled") is None:
        s.add(Setting(key="reminder_enabled", value=True))


if __name__ == "__main__":
    asyncio.run(main())
