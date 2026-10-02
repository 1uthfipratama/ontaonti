"""Phase 4: templates, consent filtering, cost estimate, sending with retries, statuses."""

import json

import httpx
import pytest
import respx
from sqlalchemy import select, update

from app import queue
from app.db import SessionLocal
from app.models import BroadcastRecipient, Contact, Conversation
from app.services.inbound import get_or_create_identity
from tests.meta_payloads import dumps, sign, wa_status

GRAPH_WA = "https://graph.test/v25.0/1111111111/messages"
GRAPH_TEMPLATES = "https://graph.test/v25.0/2222222222/message_templates"


async def make_contact(name: str, wa_id: str, opted_in: bool, opted_out: bool = False) -> int:
    async with SessionLocal() as s:
        ident, _ = await get_or_create_identity(s, "whatsapp", wa_id, name, simulated=False)
        await s.execute(
            update(Contact)
            .where(Contact.id == ident.contact_id)
            .values(broadcast_opt_in=opted_in, opted_out=opted_out)
        )
        await s.commit()
        return ident.contact_id


async def make_template(
    admin, body="Halo {{1}}, jangan lupa kontrol ke puskesmas {{2}}.", cat="UTILITY"
):
    r = await admin.post(
        "/templates",
        json={"name": "pengingat_kontrol", "language": "id", "category": cat, "body_text": body},
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_only_consenting_contacts_are_recipients(admin):
    await make_contact("Ani", "628111", opted_in=True)
    await make_contact("Budi", "628222", opted_in=False)
    await make_contact("Cici", "628333", opted_in=True, opted_out=True)  # STOP wins
    t = await make_template(admin)
    r = await admin.post(
        "/broadcasts/estimate",
        json={"template_id": t["id"], "variables": ["{{name}}", "minggu ini"]},
    )
    est = r.json()
    assert est["recipients"] == 1 and est["sample"] == ["Ani"]
    assert est["preview"] == "Halo Ani, jangan lupa kontrol ke puskesmas minggu ini."


async def test_cost_estimate_uses_category_rate(admin):
    for i in range(3):
        await make_contact(f"P{i}", f"62900{i}", opted_in=True)
    t = await make_template(admin, body="Info {{1}}", cat="MARKETING")
    est = (
        await admin.post("/broadcasts/estimate", json={"template_id": t["id"], "variables": ["x"]})
    ).json()
    assert est["rate_idr"] == 680 and est["total_idr"] == 3 * 680


async def test_variable_count_is_enforced(admin):
    t = await make_template(admin)
    r = await admin.post(
        "/broadcasts/estimate", json={"template_id": t["id"], "variables": ["only one"]}
    )
    assert r.status_code == 422


async def test_send_broadcast_with_retry_and_delivery_statuses(admin, client):
    await make_contact("Ani", "628111", opted_in=True)
    await make_contact("Dedi", "628444", opted_in=True)
    t = await make_template(admin)
    calls: list[dict] = []
    fail_once = {"628444": True}

    def graph(request: httpx.Request):
        body = json.loads(request.content)
        calls.append(body)
        if fail_once.pop(body.get("to"), False):
            return httpx.Response(
                503, json={"error": {"message": "temporarily unavailable", "code": 2}}
            )
        return httpx.Response(200, json={"messages": [{"id": f"wamid.BC{len(calls)}"}]})

    with respx.mock(assert_all_called=False) as mock:
        mock.post(GRAPH_WA).mock(side_effect=graph)
        bc = (await admin.post("/broadcasts", json={"template_id": t["id"],
                                                    "variables": ["{{name}}", "Senin"]})).json()  # fmt: skip
        assert bc["status"] == "draft" and bc["recipient_count"] == 2
        r = await admin.post(f"/broadcasts/{bc['id']}/send")
        assert r.status_code == 200 and r.json()["queued"] == 2
        await queue.drain()

    templates = [c for c in calls if c.get("type") == "template"]
    assert {c["to"] for c in templates} == {"628111", "628444"}
    assert templates[0]["template"]["name"] == "pengingat_kontrol"
    assert templates[0]["template"]["components"][0]["parameters"][0]["text"] in ("Ani", "Dedi")
    detail = (await admin.get(f"/broadcasts/{bc['id']}")).json()
    assert detail["status"] == "done"
    by_name = {r["contact_name"]: r for r in detail["recipients"]}
    assert by_name["Dedi"]["attempts"] == 2 and by_name["Dedi"]["status"] == "sent"

    # Delivery and read receipts arrive through the WhatsApp webhook.
    async with SessionLocal() as s:
        ani = (await s.execute(
            select(BroadcastRecipient).join(Contact).where(Contact.display_name == "Ani")
        )).scalar_one()  # fmt: skip
    for state in ("delivered", "read"):
        body = dumps(wa_status(ani.external_id, state, "628111"))
        await client.post(
            "/webhook/whatsapp", content=body, headers={"X-Hub-Signature-256": sign(body)}
        )
        await queue.drain()
    stats = (await admin.get(f"/broadcasts/{bc['id']}")).json()["stats"]
    assert stats["sent"] == 2 and stats["delivered"] == 1 and stats["read"] == 1
    # The template message shows up in the contact's thread.
    async with SessionLocal() as s:
        assert (await s.execute(select(Conversation))).scalars().all()


async def test_permanent_failure_is_recorded(admin):
    await make_contact("Ani", "628111", opted_in=True)
    t = await make_template(admin)
    with respx.mock() as mock:
        mock.post(GRAPH_WA).mock(return_value=httpx.Response(
            400, json={"error": {"message": "Template name does not exist", "code": 132001}}
        ))  # fmt: skip
        bc = (
            await admin.post("/broadcasts", json={"template_id": t["id"], "variables": ["a", "b"]})
        ).json()
        await admin.post(f"/broadcasts/{bc['id']}/send")
        await queue.drain()
    detail = (await admin.get(f"/broadcasts/{bc['id']}")).json()
    assert detail["recipients"][0]["status"] == "failed"
    assert "does not exist" in detail["recipients"][0]["error"]
    assert detail["recipients"][0]["attempts"] == 1  # 4xx: no retry


async def test_consent_withdrawn_after_draft_is_skipped(admin):
    cid = await make_contact("Ani", "628111", opted_in=True)
    t = await make_template(admin)
    bc = (
        await admin.post("/broadcasts", json={"template_id": t["id"], "variables": ["a", "b"]})
    ).json()
    async with SessionLocal() as s:
        await s.execute(update(Contact).where(Contact.id == cid).values(opted_out=True))
        await s.commit()
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(GRAPH_WA).mock(
            return_value=httpx.Response(200, json={"messages": [{"id": "x"}]})
        )
        await admin.post(f"/broadcasts/{bc['id']}/send")
        await queue.drain()
        assert not route.called
    assert (await admin.get(f"/broadcasts/{bc['id']}")).json()["recipients"][0][
        "status"
    ] == "skipped"


async def test_simulated_contacts_receive_broadcast_without_meta(admin):
    async with SessionLocal() as s:
        ident, _ = await get_or_create_identity(s, "whatsapp", "sim-demo", "Demo", simulated=True)
        await s.execute(
            update(Contact).where(Contact.id == ident.contact_id).values(broadcast_opt_in=True)
        )
        await s.commit()
    t = await make_template(admin)
    bc = (
        await admin.post(
            "/broadcasts", json={"template_id": t["id"], "variables": ["{{name}}", "Senin"]}
        )
    ).json()
    await admin.post(f"/broadcasts/{bc['id']}/send")
    await queue.drain()
    detail = (await admin.get(f"/broadcasts/{bc['id']}")).json()
    assert detail["recipients"][0]["status"] == "sent"


async def test_template_sync(admin):
    payload = {
        "data": [
            {"name": "hello_world", "language": "en_US", "status": "APPROVED", "category": "UTILITY",
             "components": [{"type": "BODY", "text": "Hello World"}]},
            {"name": "reminder", "language": "id", "status": "APPROVED", "category": "UTILITY",
             "components": [{"type": "BODY", "text": "Halo {{1}}, kontrol {{2}}"}]},
        ],
        "paging": {"cursors": {"after": "x"}},
    }  # fmt: skip
    with respx.mock() as mock:
        mock.get(GRAPH_TEMPLATES).mock(return_value=httpx.Response(200, json=payload))
        r = await admin.post("/templates/sync")
    assert r.json() == {"synced": 2}
    templates = {t["name"]: t for t in (await admin.get("/templates")).json()}
    assert (
        templates["reminder"]["variable_count"] == 2
        and templates["hello_world"]["status"] == "APPROVED"
    )


@pytest.mark.parametrize("path", ["/broadcasts", "/templates", "/broadcasts/estimate"])
async def test_agents_cannot_create_broadcasts(admin, client, path):
    await admin.post(
        "/staff", json={"email": "agent@test.local", "role": "agent", "password": "agent-pass-123"}
    )
    await client.post("/auth/logout")
    await client.post(
        "/auth/login", json={"email": "agent@test.local", "password": "agent-pass-123"}
    )
    r = await client.post(
        path, json={"template_id": 1, "variables": [], "name": "x", "body_text": "x"}
    )
    assert r.status_code == 403
