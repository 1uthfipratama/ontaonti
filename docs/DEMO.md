# Demo script (about 15 minutes)

Works fully offline with the Simulator. Use a real LLM key for real answers, or
`LLM_PROVIDER=fake` for canned ones. Optional: `docker compose exec api python
scripts/seed_demo.py` first, so the inbox, cases and dashboard aren't empty.

Keep two browser windows side by side: **Simulator** (you play the patient) and
**Inbox** (you play staff). Updates arrive live (SSE); no refresh needed.

## 1. Normal question
Simulator → channel **WhatsApp**, fake user id `demo1`, name "Budi".
Send: **Halo kak, berapa lama pengobatan TBC?**

- First message → the privacy/consent notice (stored, read by staff, not a
  diagnosis, reply STOP to end).
- Then one answer in Bahasa Indonesia from the knowledge base (≈ 6 months, two
  phases, free at the puskesmas). No diagnosis and no doses.
- Inbox: the bot bubble shows the sources used, tokens and cost in IDR.

Also try **Is TB contagious through sharing plates?**: the answer comes back in English.

## 2. Risky message → flag → case
Send: **Saya batuk darah banyak dan sesak napas berat**

- The bot sends the **fixed** emergency text (IGD / 119 / staff alerted), not an
  LLM answer.
- The message is flagged EMERGENCY; the conversation switches to **Human** mode.
- A red toast appears and the **Cases** badge counts it.

Other flags to show: *mata saya jadi kuning sejak minum obat* (ADVERSE_DRUG, high),
*obat saya habis, mau berhenti pengobatan* (ADHERENCE, high), *rasanya ingin mati
saja* (SELF_HARM, emergency).

## 3. Staff takeover
Inbox → open the conversation:
- **AI summary** gives the agent a briefing (staff-only, never sent).
- Reply as staff: the reply appears in the simulator as "Staf". Messages from the
  user now get **no bot reply** (Human mode). In the Simulator, send another message
  to show it.

## 4. Resolve → bot resumes
Cases → open the case → **Claim** → add a note → **Resolve & return to bot**.
The conversation goes back to **Bot** mode and the flag clears. In the Simulator,
ask *Apa efek samping obat TBC?* and the bot answers again.

## 5. Consent keywords
- **LANGGANAN**: subscribes to broadcasts (Contacts page shows "subscribed").
- **STOP**: opted out, one confirmation, then silence. Staff can't message them either.
- **MULAI**: back in.

## 6. Broadcast
Broadcasts → template **pengingat_kontrol** (from the seed, or register one by
hand) → variables `{{name}}` and `hari Senin` → **Estimate cost**:
- recipients = only contacts with broadcast consent who haven't sent STOP
- the cost uses the per-message rate from Settings, with a preview

**Send**. Simulated contacts receive it in the Simulator thread. Real WhatsApp
contacts receive the approved template, and the campaign page fills in
sent → delivered → read from Meta's status webhooks.

## 7. Dashboard and settings
- **Dashboard**: conversations by channel, open cases by severity, median first
  response (bot vs human), AI spend vs budget, WhatsApp template messages vs the
  free tier.
- **Settings**: edit the persona, safety texts, keyword rules, models, monthly
  budget and the daily cap. To show the budget fallback, set the budget to `1`
  and the fallback to `fixed_reply`, then ask a question: the bot sends the fixed
  reply and opens a BUDGET case. Emergency keywords still work over budget.
- **Audit log** shows every view, reply, toggle and setting change.

## 8. Voice note
Simulator → tap the **microphone**, say a question (e.g. "berapa lama pengobatan TBC?"),
tap again to send. In the Inbox the bubble has a player and the **Transkrip**; the
bot answers it like a typed question.

## 9. TB screening
Simulator → quick message **Skrining TBC**. Answer the five questions with the
**Ya / Tidak** buttons (say *Ya* to the first). The result suggests testing; the
contact appears under **Terduga** on **Pasien**, with a follow-up task in **Tugas**.

## 10. Medication reminder
In the Inbox contact panel set **Tahap** to *Pengobatan*, switch on **Pengingat obat**
and set its time to a minute ago. Switch on reminders in Settings → Bot, keamanan &
biaya → **Pengingat obat**. Within a minute the Simulator shows "Sudah minum obat hari
ini?" with **Sudah / Belum**. Tap one: the bot thanks the patient and the dose dots
in the contact panel update. Saying *Belum* on consecutive days (2 by default) opens
an adherence case and a call task for the kader.

## 11. Knowledge gaps
Ask something the knowledge base doesn't cover (e.g. "apakah ada bantuan uang
transport?"). The bot says honestly it doesn't know, and the question appears under
**Pengetahuan → Belum terjawab**. Add the answer to an article, **Terbitkan**, ask
again: the bot now answers and cites the article.
