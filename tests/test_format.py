"""Reply formatting: WhatsApp markup, length clamp, cut-off answers."""

from app.bot.format import clamp, to_whatsapp, trim_incomplete


def test_trim_incomplete_drops_cut_off_fragment():
    text = "Minum obat setiap hari sampai tuntas.\n\nJangan berhenti walau sudah sehat ya.\n\nJen"
    assert trim_incomplete(text).endswith("sudah sehat ya.")


def test_trim_incomplete_keeps_bold_sentence_end():
    assert (
        trim_incomplete("Obatnya *gratis di puskesmas.* Kalau ad")
        == "Obatnya *gratis di puskesmas.*"
    )


def test_trim_incomplete_without_sentence_end_keeps_text():
    assert trim_incomplete("halo kak") == "halo kak"


def test_markdown_becomes_whatsapp():
    assert (
        to_whatsapp("## Judul\n**tebal** dan [link](https://x.id)")
        == "*Judul*\n*tebal* dan link (https://x.id)"
    )


def test_clamp_cuts_at_sentence():
    text = "Kalimat satu. " * 100
    out = clamp(text, 900)
    assert len(out) <= 900 and out.endswith(".")


async def test_cut_off_answer_is_trimmed(admin, monkeypatch):
    from app import llm
    from tests.conftest import simulate, thread

    real = llm.complete

    async def fake_complete(**kw):
        res = await real(**kw)
        if kw["purpose"] == "answer":
            res.text, res.stop_reason = (
                "Pengobatan minimal 6 bulan [1].\n\nObatnya gratis di pusk",
                "max_tokens",
            )
        return res

    monkeypatch.setattr(llm, "complete", fake_complete)
    out = await simulate(admin, "Berapa lama pengobatan TBC?")
    bot = [m for m in await thread(admin, out["conversation_id"]) if m["sender_type"] == "bot"]
    assert bot[-1]["text"] == "Pengobatan minimal 6 bulan."
