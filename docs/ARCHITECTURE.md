# Architecture

```mermaid
flowchart LR
    subgraph Channels
        WA[WhatsApp Cloud API]
        MS[Messenger]
        IG[Instagram]
        SIM[Simulator page]
    end
    subgraph API["api (FastAPI)"]
        WH["/webhook/{channel}<br/>verify token + HMAC"]
        ADM[admin API<br/>cookie auth, roles, audit]
        SSE["/events (SSE)"]
    end
    subgraph Worker["worker (arq)"]
        PIPE[pipeline per message]
        BC[broadcast sender<br/>rate limit + retries]
    end
    R[(Redis<br/>queue + pub/sub)]
    PG[(PostgreSQL)]
    KB[(KB index<br/>SQLite FTS5 + sqlite-vec)]
    LLM[LLM provider<br/>Groq / Anthropic]
    WEB[web (Next.js)<br/>admin UI]

    WA & MS & IG -->|POST| WH
    SIM --> ADM
    WH -->|enqueue, 200 at once| R
    ADM -->|enqueue| R
    R --> PIPE & BC
    PIPE --> KB
    PIPE --> LLM
    PIPE -->|send via adapter| WA & MS & IG
    BC -->|templates| WA
    PIPE & BC & ADM --> PG
    PIPE & BC & ADM -->|publish| R
    R -->|subscribe| SSE --> WEB
    WEB --> ADM
```

Five containers (`docker compose`): `db` (Postgres 16), `redis`, `api` (uvicorn),
`worker` (arq; same image as `api`), `web` (Next.js standalone).

## Message pipeline (`app/bot/pipeline.py`)

Each inbound message runs as one worker job, under a per-conversation lock so
replies stay in order:

1. **Opt-out**: `STOP`/`BERHENTI` (the whole message) → opted out, one
   confirmation, then silence. `MULAI` → back in. An opted-out contact gets no
   replies, but emergency keywords still open a case.
2. **Keyword safety rules** (`config/flags.yaml`, editable in Settings). They are
   free and always run, even over budget or in HUMAN mode.
3. **First contact**: privacy/consent notice. `LANGGANAN` → broadcast consent.
4. **HUMAN mode**: store and notify staff only. A high/emergency keyword still
   opens a case. Non-text messages get a polite "text only" reply.
5. **Keyword high/emergency**: FIXED safety reply from settings (never
   LLM-generated: IGD / 119 / staff alerted), a case, conversation → HUMAN, a
   badge/toast for staff, and email if SMTP is set.
6. **Cost controls**: per-contact rate limit (20 / 10 min) and daily cap (30),
   with a polite notice once. Monthly AI budget: at 80% an alert (once a month); at
   100% either the cheaper classifier model, or a fixed reply + case with no LLM
   call.
7. **LLM classifier** → `{"severity","category","reason"}`. Unreadable output or an
   error counts as `low`. Final severity = max(keyword, classifier); high or above
   goes to step 5.
8. **RAG answer**: retrieve (fixed k) → persona prompt + last 6 messages → LLM
   (≤ 400 output tokens, input ≤ 500 chars) → citation markers stripped → WhatsApp
   formatting → one message ≤ 900 chars. An LLM error sends the fixed
   "staf kami akan menghubungi" reply and opens a low `BOT_ERROR` case.

## RAG (`rag/` + `app/bot/`)

`rag/` is the retrieval core of the thesis-rag project, vendored with small changes
(see `rag/VENDORED.md`):
- Hybrid search: BM25 (SQLite FTS5) + dense (sqlite-vec), fused with Reciprocal
  Rank Fusion.
- Neighbour expansion.
- Chunks sized in the embedder's own tokens.

The embedder is `intfloat/multilingual-e5-small` (ONNX via fastembed, CPU), so
Indonesian and English questions both find Indonesian passages. The knowledge base
is `kb/*.md`, converted to the RAG schema by `app/bot/kb.py` and indexed by
`scripts/reindex_kb.py`. The index is one SQLite file on the `kbdata` volume.

## Channels (`app/channels/`)

| Adapter | Inbound | Outbound |
|---|---|---|
| `simulator.py` | admin Simulator page | stored only, shown live |
| `whatsapp.py` | `messages` webhook: text, buttons, media (polite reply), statuses | `POST /{phone_number_id}/messages`: text, templates, mark-as-read |
| `meta.py` | Messenger / Instagram `messaging` events, delivery + read watermarks | `POST /{page_id}/messages`, `RESPONSE` or `MESSAGE_TAG`/`HUMAN_AGENT` |

All implement `parse_inbound(payload) -> list[InternalMessage]` and
`send(conversation, text)`. Graph tokens travel in the `Authorization` header,
never in URLs. Webhooks return 200 immediately; a redelivered payload is dropped
by the arq job id and by the unique `messages.external_id`.

## Data model

```mermaid
erDiagram
    staff_users ||--o{ audit_log : "acts"
    contacts ||--o{ contact_identities : "has"
    contacts ||--o{ conversations : "has"
    contact_identities ||--|| conversations : "thread per identity"
    conversations ||--o{ messages : "contains"
    conversations ||--o{ cases : "raises"
    cases ||--o{ case_notes : "has"
    contacts ||--o{ consents : "log"
    wa_templates ||--o{ broadcasts : "uses"
    broadcasts ||--o{ broadcast_recipients : "to"
    broadcast_recipients }o--|| messages : "sent as"
```

| Table | Key columns |
|---|---|
| `staff_users` | email, bcrypt hash, role (admin / agent / reviewer), session_epoch |
| `contacts` | display_name, phone, notes, opted_out, broadcast_opt_in |
| `contact_identities` | channel, external_id (unique per channel), simulated |
| `conversations` | channel, status OPEN/RESOLVED, mode BOT/HUMAN, assigned_to, window_expires_at, flag_severity |
| `messages` | direction in/out/note, sender_type user/bot/agent/system, text, media_url, external_id (unique), status, flag_severity/category/reason, tokens_in/out, cost_idr, meta |
| `cases` / `case_notes` | severity, category, status OPEN/CLAIMED/RESOLVED, assigned_to, trigger message |
| `consents` | append-only: privacy_notice / messaging / broadcast × notified / granted / revoked, source |
| `settings` | key → JSON overrides of the defaults in `app/services/settings_service.py` |
| `llm_usage` | provider, model, purpose, tokens, cost (USD + IDR), latency, ok/error |
| `audit_log` | actor, action, entity, details, ip |
| `wa_templates`, `broadcasts`, `broadcast_recipients` | template body/variables; campaign; per-recipient status and attempts |

Migrations: `alembic/versions/0001..0003`.

## Security notes

- Staff sessions: signed, httponly, SameSite=Lax cookie (`itsdangerous`, 12 h).
  `session_epoch` invalidates sessions on password change or deactivation. Failed
  logins are rate-limited per IP.
- CSRF: an Origin check on state-changing requests, CORS limited to `WEB_BASE_URL`.
- Every admin route requires auth (test enumerates the OpenAPI routes). Roles:
  reviewers are read-only; settings and broadcasts are admin-only.
- Audit: logins, conversation views, replies, mode/status changes, case actions,
  settings, merges, consents, broadcasts.
- Secrets live only in `.env`. A logging filter replaces any configured secret
  value with `***`.

## Not production-ready yet

- Prototype: test data only (banner on every page).
- The KB content and the fixed safety texts need clinical review.
- One API process, an in-process login limiter, no backups, no TLS termination
  (use a reverse proxy).
- WhatsApp pricing figures are editable estimates; Meta's pricing model changed in
  2024–2025.
