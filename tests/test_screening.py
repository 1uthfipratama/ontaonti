"""TB symptom screening over chat."""

from app.services import screening
from tests.conftest import simulate, thread


async def run(admin, *answers: str, user_id: str = "skrin") -> tuple[dict, list[dict]]:
    out = await simulate(admin, "SKRINING", user_id=user_id)
    for a in answers:
        await simulate(admin, a, user_id=user_id)
    conv = (await admin.get(f"/conversations/{out['conversation_id']}")).json()
    return conv, await thread(admin, out["conversation_id"])


def test_evaluate():
    assert screening.evaluate({"cough_2w": True}) == "presumptive"  # major symptom
    assert screening.evaluate({"fever": True, "night_sweats": True}) == "presumptive"
    assert screening.evaluate({"fever": True}) == "negative"
    assert screening.evaluate({"contact": True, "weight_loss": True}) == "presumptive"
    assert screening.evaluate({"contact": True}) == "negative"


def test_parse_yes_no():
    assert screening.parse_yes_no("Ya") is True
    assert screening.parse_yes_no("tidak pernah") is False
    assert screening.parse_yes_no("ya tapi cuma kadang kadang kalau malam saja") is None


async def test_screening_suggests_testing(admin):
    conv, msgs = await run(admin, "Ya", "Tidak", "Tidak", "Tidak", "Tidak")
    bot = [m for m in msgs if m["sender_type"] == "bot"]
    questions = [m for m in bot if m["meta"].get("question")]
    assert len(questions) == len(screening.spec().questions)
    assert questions[0]["meta"]["buttons"] == ["Ya", "Tidak"] and questions[0]["text"].startswith(
        "(1/5)"
    )
    assert bot[-1]["meta"]["result"] == "presumptive" and "disarankan periksa" in bot[-1]["text"]
    assert conv["contact"]["journey_stage"] == "suspect"
    tasks = (await admin.get("/tasks")).json()
    assert len(tasks) == 1 and tasks[0]["source"] == "screening"


async def test_screening_negative(admin):
    conv, msgs = await run(admin, "tidak", "ya", "tidak", "tidak", "tidak", user_id="sehat")
    assert msgs[-1]["meta"]["result"] == "negative"
    assert conv["contact"]["journey_stage"] is None
    assert (await admin.get("/tasks")).json() == []


async def test_other_reply_ends_screening_and_goes_to_the_bot(admin):
    _, msgs = await run(admin, "Ya", "Berapa lama pengobatan TBC?", user_id="tanya")
    assert msgs[-1]["sender_type"] == "bot" and "6 bulan" in msgs[-1]["text"]  # the bot answered
    # The screening is over: "Ya" now is just a message.
    await simulate(admin, "Ya", user_id="tanya")


async def test_no_screening_while_staff_handle_the_chat(admin):
    out = await simulate(admin, "Halo", user_id="staf")
    await admin.post(f"/conversations/{out['conversation_id']}/mode", json={"mode": "HUMAN"})
    await simulate(admin, "SKRINING", user_id="staf")
    msgs = await thread(admin, out["conversation_id"])
    assert not any(m["meta"].get("screening") for m in msgs)
