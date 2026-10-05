"""Patient journey, medication reminders (answers, follow-ups, escalation) and tasks."""

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Case, DoseLog
from app.routers.journey import treatment_month
from app.services import reminders
from tests.conftest import simulate, thread


def at(hour: int, minute: int = 0, days: int = 0) -> datetime:
    """Today (local) at hh:mm, as UTC."""
    day = reminders.local_today() + timedelta(days=days)
    return datetime.combine(day, time(hour, minute), tzinfo=reminders._tz()).astimezone(UTC)


async def enrol(admin, user_id: str = "pasien", **settings) -> dict:
    out = await simulate(admin, "Halo kak", user_id=user_id)
    conv = (await admin.get(f"/conversations/{out['conversation_id']}")).json()
    await admin.put("/settings", json={"values": {"reminder_enabled": True, **settings}})
    r = await admin.patch(f"/contacts/{conv['contact_id']}/journey",
                          json={"stage": "treatment", "reminder_enabled": True,
                                "reminder_time": "07:00"})  # fmt: skip
    assert r.status_code == 200, r.text
    return {"contact_id": conv["contact_id"], "conversation_id": conv["id"], "user_id": user_id}


async def dose_logs(contact_id: int) -> list[DoseLog]:
    async with SessionLocal() as s:
        q = select(DoseLog).where(DoseLog.contact_id == contact_id).order_by(DoseLog.day)
        return (await s.execute(q)).scalars().all()


def test_treatment_month():
    assert treatment_month(date(2026, 1, 15), date(2026, 1, 15)) == 1
    assert treatment_month(date(2026, 1, 15), date(2026, 2, 14)) == 1
    assert treatment_month(date(2026, 1, 15), date(2026, 2, 15)) == 2
    assert treatment_month(None, date(2026, 2, 15)) is None


def test_parse_answer():
    assert reminders.parse_answer("Sudah ✅") == "taken"
    assert reminders.parse_answer("udah minum obat") == "taken"
    assert reminders.parse_answer("Belum") == "missed"
    assert reminders.parse_answer("belum, obat saya habis dan saya mau berhenti") is None


async def test_journey_board_and_rules(admin):
    out = await simulate(admin, "Halo", user_id="board")
    cid = (await admin.get(f"/conversations/{out['conversation_id']}")).json()["contact_id"]
    r = await admin.patch(f"/contacts/{cid}/journey", json={"reminder_enabled": True})
    assert r.status_code == 409  # not on treatment yet
    await admin.patch(
        f"/contacts/{cid}/journey", json={"stage": "treatment", "puskesmas": "PKM Menteng"}
    )
    board = (await admin.get("/journey")).json()
    row = next(c for c in board["contacts"] if c["id"] == cid)
    assert row["journey_stage"] == "treatment" and row["treatment_month"] == 1
    assert row["treatment_start"] == reminders.local_today().isoformat()
    await admin.patch(f"/contacts/{cid}/journey", json={"stage": "completed"})
    assert (await admin.get("/journey")).json()["contacts"][0]["journey_stage"] == "completed"
    await admin.patch(f"/contacts/{cid}/journey", json={"clear_stage": True})
    assert (await admin.get("/journey")).json()["contacts"] == []


async def test_reminder_sent_once_and_answered(admin):
    p = await enrol(admin)
    assert (await reminders.tick(at(6, 59)))["sent"] == 0  # not yet
    assert (await reminders.tick(at(7, 1)))["sent"] == 1
    assert (await reminders.tick(at(7, 2)))["sent"] == 0  # once a day
    msgs = await thread(admin, p["conversation_id"])
    assert msgs[-1]["meta"]["buttons"] == ["Sudah ✅", "Belum"] and "minum obat" in msgs[-1]["text"]

    await simulate(admin, "Sudah ✅", user_id=p["user_id"])
    logs = await dose_logs(p["contact_id"])
    assert [(log.status, log.answered_at is not None) for log in logs] == [("taken", True)]
    last = (await thread(admin, p["conversation_id"]))[-1]
    assert last["meta"].get("dose") == "taken" and "Hebat" in last["text"]
    # "Sudah" with nothing pending is just a message for the bot again.
    await simulate(admin, "Sudah", user_id=p["user_id"])
    assert (await thread(admin, p["conversation_id"]))[-1]["meta"].get("dose") is None


async def test_no_answer_gets_one_followup_then_escalates(admin):
    p = await enrol(admin, missed_case_after=2, missed_followup_hours=3)
    async with SessionLocal() as s:  # yesterday was missed too
        s.add(DoseLog(contact_id=p["contact_id"], day=reminders.local_today() - timedelta(days=1),
                      status="missed"))  # fmt: skip
        await s.commit()
    await reminders.tick(at(7, 1))
    assert (await reminders.tick(at(9, 0)))["followups"] == 0  # too early
    assert (await reminders.tick(at(10, 30)))["followups"] == 1
    assert (await reminders.tick(at(11, 0)))["followups"] == 0  # only once
    assert [log.status for log in await dose_logs(p["contact_id"])] == ["missed", "missed"]

    async with SessionLocal() as s:
        case = (await s.execute(select(Case))).scalar_one()
    assert case.category == "ADHERENCE" and case.severity == "low"
    tasks = (await admin.get("/tasks")).json()
    assert len(tasks) == 1 and tasks[0]["source"] == "missed_doses" and tasks[0]["kind"] == "call"
    # A late "Sudah" still counts.
    await simulate(admin, "sudah", user_id=p["user_id"])
    assert (await dose_logs(p["contact_id"]))[-1].status == "taken"


async def test_saying_not_yet_escalates_at_threshold(admin):
    p = await enrol(admin, missed_case_after=1)
    await reminders.tick(at(7, 1))
    await simulate(admin, "Belum", user_id=p["user_id"])
    assert (await dose_logs(p["contact_id"]))[0].status == "missed"
    assert "jujur" in (await thread(admin, p["conversation_id"]))[-1]["text"]
    assert len((await admin.get("/tasks")).json()) == 1


async def test_reminders_off_globally(admin):
    p = await enrol(admin)
    await admin.put("/settings", json={"values": {"reminder_enabled": False}})
    assert (await reminders.tick(at(7, 1)))["sent"] == 0
    assert await dose_logs(p["contact_id"]) == []


async def test_tasks_crud(admin):
    out = await simulate(admin, "Halo", user_id="tugas")
    cid = (await admin.get(f"/conversations/{out['conversation_id']}")).json()["contact_id"]
    me = (await admin.get("/auth/me")).json()
    r = await admin.post("/tasks", json={"contact_id": cid, "kind": "visit", "title": "Kunjungan rumah",
                                         "due": "2026-10-10", "assigned_to": me["id"]})  # fmt: skip
    assert r.status_code == 200 and r.json()["contact_name"] and r.json()["assigned_name"]
    tid = r.json()["id"]
    assert [t["id"] for t in (await admin.get("/tasks", params={"scope": "mine"})).json()] == [tid]
    done = await admin.patch(f"/tasks/{tid}", json={"status": "done", "outcome": "Pasien sehat"})
    assert done.json()["status"] == "done" and done.json()["done_at"]
    assert (await admin.get("/tasks")).json() == []
    assert (await admin.get("/tasks", params={"status": "done"})).json()[0][
        "outcome"
    ] == "Pasien sehat"
