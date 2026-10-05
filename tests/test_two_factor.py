"""Two-factor login (TOTP) and password change."""

import time

from app import totp

LOGIN = {"email": "admin@test.local", "password": "test-password-123"}


def code(secret: str, offset_steps: int = 0) -> str:
    return totp.code_at(secret, int(time.time() // totp.STEP) + offset_steps)


async def enable(admin) -> str:
    setup = (await admin.post("/auth/2fa/setup")).json()
    assert setup["uri"].startswith("otpauth://totp/") and setup["qr"].startswith("data:image/svg")
    r = await admin.post("/auth/2fa/enable", json={"code": code(setup["secret"])})
    assert r.status_code == 200 and r.json()["totp_enabled"] is True
    return setup["secret"]


async def test_setup_needs_a_valid_code(admin):
    setup = (await admin.post("/auth/2fa/setup")).json()
    bad = await admin.post("/auth/2fa/enable", json={"code": "000000"})
    assert bad.status_code == 400
    assert (await admin.get("/auth/me")).json()["totp_enabled"] is False
    ok = await admin.post("/auth/2fa/enable", json={"code": code(setup["secret"])})
    assert ok.status_code == 200


async def test_login_asks_for_the_code(admin, client):
    secret = await enable(admin)
    await client.post("/auth/logout")
    r = await client.post("/auth/login", json=LOGIN)
    assert r.status_code == 401 and r.json()["detail"] == "Two-factor code required"
    r = await client.post("/auth/login", json={**LOGIN, "code": "123456"})
    assert r.status_code == 401 and r.json()["detail"] == "Invalid code"
    r = await client.post("/auth/login", json={**LOGIN, "code": code(secret, 1)})  # clock drift ok
    assert r.status_code == 200
    # The same code can't be used twice.
    await client.post("/auth/logout")
    r = await client.post("/auth/login", json={**LOGIN, "code": code(secret, 1)})
    assert r.status_code == 401


async def test_disable_needs_the_password(admin):
    await enable(admin)
    assert (await admin.post("/auth/2fa/disable", json={"password": "nope"})).status_code == 400
    r = await admin.post("/auth/2fa/disable", json={"password": LOGIN["password"]})
    assert r.status_code == 200 and r.json()["totp_enabled"] is False


async def test_admin_can_reset_someone_elses_2fa(admin, client):
    await admin.post("/staff", json={"email": "ag@test.local", "role": "agent",
                                     "password": "agent-pass-123"})  # fmt: skip
    await client.post("/auth/logout")
    await client.post("/auth/login", json={"email": "ag@test.local", "password": "agent-pass-123"})
    await enable(client)
    staff = {s["email"]: s for s in (await client.get("/staff")).json()}
    assert staff["ag@test.local"]["totp_enabled"] is True

    await client.post("/auth/logout")
    await client.post("/auth/login", json=LOGIN)
    r = await client.patch(f"/staff/{staff['ag@test.local']['id']}", json={"reset_2fa": True})
    assert r.status_code == 200 and r.json()["totp_enabled"] is False
    await client.post("/auth/logout")
    r = await client.post(
        "/auth/login", json={"email": "ag@test.local", "password": "agent-pass-123"}
    )
    assert r.status_code == 200


async def test_change_password_keeps_this_session(admin, client):
    bad = await admin.post("/auth/password", json={"current": "wrong", "new": "a-new-password-1"})
    assert bad.status_code == 400
    r = await admin.post(
        "/auth/password", json={"current": LOGIN["password"], "new": "a-new-password-1"}
    )
    assert r.status_code == 200
    assert (await admin.get("/auth/me")).status_code == 200  # new cookie set
    await admin.post("/auth/logout")
    assert (await admin.post("/auth/login", json=LOGIN)).status_code == 401
    ok = await admin.post("/auth/login", json={**LOGIN, "password": "a-new-password-1"})
    assert ok.status_code == 200
