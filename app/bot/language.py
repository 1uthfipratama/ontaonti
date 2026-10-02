"""Tiny language guess: Indonesian (default) or English. Used to pick fixed texts
(safety replies, consent notice) and to tell the model which language to use."""

import re

EN = frozenset(
    """the is are am was were what how why when where who which i my me you your can could do
    does did have has should would will not no yes please hello hi hey thanks thank and to of
    it for with this that about if feel feeling medicine medication pills cough taking take
    stop stopped want need help doctor sick today""".split()
)
ID = frozenset(
    """yang dan apa apakah saya aku kamu anda tidak ga gak nggak enggak bisa ini itu obat batuk
    kak kakak dong ya sudah udah belum berapa bagaimana gimana kenapa mengapa mau ingin halo
    terima kasih minum sakit dengan untuk di ke dari ada adalah juga lagi saja aja sih kok
    bulan hari minggu dokter puskesmas berobat""".split()
)


def detect(text: str) -> str:
    words = re.findall(r"[a-z']+", (text or "").lower())
    en = sum(w in EN for w in words)
    idn = sum(w in ID for w in words)
    return "en" if en > idn else "id"


LANG_NAME = {"id": "Bahasa Indonesia", "en": "English"}
