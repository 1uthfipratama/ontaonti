"""Programme figures and CSV exports."""

from app.services import reminders
from tests.conftest import simulate
from tests.test_journey import at, enrol


async def test_programme_figures(admin):
    p = await enrol(admin)
    await reminders.tick(at(7, 1))
    await simulate(admin, "Sudah", user_id=p["user_id"])
    await simulate(admin, "SKRINING", user_id="skr")
    for a in ("Ya", "Tidak", "Tidak", "Tidak", "Tidak"):
        await simulate(admin, a, user_id="skr")
    await simulate(admin, "Saya batuk darah banyak dan sesak napas berat", user_id="sos")

    r = (await admin.get("/reports/programme")).json()
    assert r["stages"]["treatment"] == 1 and r["stages"]["suspect"] == 1
    assert r["adherence"]["taken"] == 1 and r["reminders_on"] == 1
    assert r["screenings"] == {"total": 1, "presumptive": 1}
    assert len(r["flags_weekly"]) == 8 and r["flags_weekly"][-1]["emergency"] >= 1


async def test_csv_exports(admin, client):
    p = await enrol(admin)
    await reminders.tick(at(7, 1))
    r = await admin.get("/reports/export/patients.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    lines = r.text.lstrip("\ufeff").splitlines()
    assert lines[0].startswith("contact_id,name,phone,stage") and len(lines) == 2
    doses = (await admin.get("/reports/export/doses.csv")).text.splitlines()
    assert len(doses) == 2 and ",pending," in doses[1]
    assert (await admin.get("/reports/export/nope.csv")).status_code == 404
    audit = (await admin.get("/audit", params={"action": "report.export"})).json()
    assert len(audit) == 2

    await admin.post(
        "/staff", json={"email": "ag@test.local", "role": "agent", "password": "agent-pass-123"}
    )
    await client.post("/auth/logout")
    await client.post("/auth/login", json={"email": "ag@test.local", "password": "agent-pass-123"})
    assert (await client.get("/reports/export/patients.csv")).status_code == 403
    assert p
