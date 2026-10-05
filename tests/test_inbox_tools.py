"""Saved replies, labels, internal notes, AI-suggested replies."""

from tests.conftest import simulate, thread


async def test_saved_replies_crud(admin):
    r = await admin.post("/saved-replies", json={"shortcut": "Jadwal Kontrol", "title": "Jadwal",
                                                 "body": "Jadwal kontrol setiap Senin."})  # fmt: skip
    assert r.status_code == 200 and r.json()["shortcut"] == "jadwal-kontrol"
    dup = await admin.post(
        "/saved-replies", json={"shortcut": "jadwal kontrol", "title": "x", "body": "y"}
    )
    assert dup.status_code == 409
    rid = r.json()["id"]
    r = await admin.put(
        f"/saved-replies/{rid}", json={"shortcut": "jadwal", "title": "Jadwal", "body": "Baru"}
    )
    assert r.json()["body"] == "Baru"
    assert [x["shortcut"] for x in (await admin.get("/saved-replies")).json()] == ["jadwal"]
    assert (await admin.delete(f"/saved-replies/{rid}")).status_code == 200
    assert (await admin.get("/saved-replies")).json() == []


async def test_labels_on_conversations_and_filter(admin):
    a = await simulate(admin, "Halo", user_id="a")
    await simulate(admin, "Halo juga", user_id="b")
    lb = (await admin.post("/labels", json={"name": "Perlu telepon"})).json()
    again = (await admin.post("/labels", json={"name": "Perlu  telepon"})).json()
    assert again["id"] == lb["id"]  # same name -> same label
    await admin.post(f"/conversations/{a['conversation_id']}/labels", json={"label_id": lb["id"]})
    conv = (await admin.get(f"/conversations/{a['conversation_id']}")).json()
    assert conv["labels"] == [{"id": lb["id"], "name": "Perlu telepon"}]
    filtered = (await admin.get("/conversations", params={"label": lb["id"]})).json()
    assert [c["id"] for c in filtered] == [a["conversation_id"]]
    await admin.delete(f"/conversations/{a['conversation_id']}/labels/{lb['id']}")
    assert (await admin.get(f"/conversations/{a['conversation_id']}")).json()["labels"] == []


async def test_internal_note_is_not_sent(admin):
    out = await simulate(admin, "Halo")
    r = await admin.post(
        f"/conversations/{out['conversation_id']}/notes",
        json={"text": "Pasien minta ditelepon sore."},
    )
    assert r.status_code == 200
    note = r.json()
    assert (
        note["direction"] == "note" and note["sender_type"] == "agent" and note["sender_staff_id"]
    )
    msgs = await thread(admin, out["conversation_id"])
    assert msgs[-1]["text"] == "Pasien minta ditelepon sore."
    conv = (await admin.get(f"/conversations/{out['conversation_id']}")).json()
    assert conv["mode"] == "BOT"  # a note doesn't take the chat over


async def test_ai_suggestion_is_a_draft(admin):
    out = await simulate(admin, "Berapa lama pengobatan TBC?")
    before = len(await thread(admin, out["conversation_id"]))
    r = await admin.post(f"/conversations/{out['conversation_id']}/suggest")
    assert r.status_code == 200, r.text
    assert r.json()["text"] and r.json()["sources"]
    assert len(await thread(admin, out["conversation_id"])) == before  # nothing sent
