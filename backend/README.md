# Ally Platform — Backend

FastAPI + SQLAlchemy on Supabase Postgres.
(Frontend is Vite + React 19 with react-router, in `../frontend`.)

## Setup

```bash
cp .env.example .env          # then fill in DATABASE_URL and SECRET_KEY
pip install -r requirements.txt
python test_connection.py     # verify the database is reachable
```

`.env.example` also documents the optional integrations, all of which run in a
safe stub/off mode until configured: Supabase auth (`SUPABASE_JWT_SECRET`),
Google Calendar for discovery calls, and email/SMTP.

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

- http://localhost:8000/docs — interactive API docs, and the easiest way to test
- http://localhost:8000/api/v1/health — app + database status

## Auth

Pluggable via `AUTH_PROVIDER` in `.env`:

- `dev` — every request resolves to a fixed test founder, no token needed. Send
  any bearer token to use that string as the founder id instead. Refused at
  startup when `ENVIRONMENT=production`.
- `supabase` — verifies the JWT the frontend receives from Supabase Auth.
  Requires `SUPABASE_JWT_SECRET`.

**Email + one-time code + password.** A founder's email address IS their login
id; there is no separate username. Social login (Google/LinkedIn) is *supported*
by the provider but is not how founders sign in today.

Two token worlds, kept separate so the API never depends on the identity
provider:

- **Identity provider token** (Supabase now, Cognito on AWS later) proves who the
  user is, *once*, at `POST /auth/session`.
- **Backend session tokens** — the backend then issues its own access + refresh
  JWTs (signed with `SECRET_KEY`). Every later request carries the access token.

Login flow — two ways in, both ending in the same place:

**New founder, or forgot password**
1. `sendEmailOtp(email)` — Supabase emails a numeric code.
2. `verifyOtpAndSetPassword(email, code, password)` — verifies the code, stores
   the password they just chose, and yields a real Supabase session.
3. `POST /auth/session` with that token → backend returns `{access_token, refresh_token}`
   (and, on the first time, creates the founder row).

**Returning founder**
1. `signInWithPassword(email, password)` → a Supabase session.
2. `POST /auth/session` → the same backend tokens.

From there Supabase is irrelevant: every later request carries the backend
access token. `POST /auth/refresh` rotates it; `POST /auth/logout` revokes it.

Moving to AWS Cognito changes only step 1 — one new `AuthProvider` in
`app/core/auth/base.py` + `AUTH_PROVIDER=cognito`. Session tokens, routes, and
every other endpoint stay identical.

Endpoints: `POST /auth/session` (login), `POST /auth/resume` (restore from a
stored refresh token on reload), `POST /auth/refresh` (rotate tokens),
`POST /auth/logout`, `GET /auth/me`, `GET /auth/status`.

Per-request session validation is a FastAPI **dependency** (`get_current_founder`),
not middleware -- that is the idiomatic place for it, and it lets each route opt
in and receive the founder, which middleware cannot do cleanly.

Routes that touch founder data take `founder: Founder = Depends(get_founder_record)`,
which resolves the token to the founder row.

**LinkedIn / Google** can be enabled in the Supabase dashboard (Authentication →
Providers) without backend changes — the backend treats every provider
identically. They are not part of the shipped sign-in flow today.

**Provisioning** (creating a founder row on first login) is behind
`ENABLE_FOUNDER_PROVISIONING`, off by default, so no rows are written until it is
switched on. Real-user *auth* testing (login, refresh, logout) works without it;
only saving founder *data* needs it on.

## Database

The schema already exists — 56 logical tables (plus 36 monthly partitions),
created by Supabase migrations, with `founders` as the hub that 66 other tables
reference.

> ### 🔒 THE RULE — Alembic owns every schema change. No exceptions.
>
> **No schema change happens outside Alembic. No direct DDL — `CREATE`,
> `ALTER`, `DROP`, indexes, constraints, RLS — through the Supabase SQL
> editor, the Supabase MCP tool, `psql`, or any other path, by anyone
> (human or agent).** The only sanctioned way to change the schema is an
> Alembic revision that is reviewed and then applied with `alembic upgrade head`.
>
> Why this is non-negotiable: doing DDL out-of-band creates tables the
> migration chain has no record of, so `alembic upgrade` later tries to
> re-`CREATE` them and fails — the exact drift we had to reconcile (the live
> DB sat at `055fcff2b6b5` with ~19 tables Alembic never recorded, while head
> was `c3d1f0a2b7e4`). An empty migration history is indistinguishable from a
> correct one until the day it breaks a deploy.
>
> If you truly must adopt objects that already exist (e.g. created before this
> rule), do it deliberately: write/autogenerate a revision that represents them
> and `alembic stamp` the DB to it — never leave the two out of sync.

```bash
alembic revision --autogenerate -m "what changed"   # review the file before applying
alembic upgrade head
alembic current
```

Baseline revision `5cbf7c8fea1e` is intentionally empty — it records that Alembic
adopted an already-populated schema rather than creating it.

Two limits to know:

- Alembic cannot see RLS policies, partition layouts, or database functions.
  Write those by hand inside a revision.
- Tables without a model in `app/models/` are ignored, not dropped
  (see the `include_object` guard in `alembic/env.py`). This is what keeps
  autogenerate from destroying the 56 existing tables.

## Discovery calls

A founder books a 30-minute discovery call (timezone `Asia/Kolkata`): the backend
reads real availability from Google Calendar, creates the event, and emails a
confirmation. Endpoints: `GET /discovery/slots`, `POST /discovery/book`,
`GET /discovery/calls`, `GET /discovery/calls/{id}`.

**Calendar** (`app/services/calendar.py`) — Google Calendar via a service
account. Runs in a stub (deterministic slots + placeholder link) until
`GOOGLE_CALENDAR_ID` and a service-account key are set; then it filters slots by
the host calendar's free/busy and creates real events. Supply the key as a file
(`GOOGLE_CALENDAR_CREDENTIALS_FILE`, recommended) or inline JSON. On a **personal
Gmail** calendar a service account cannot auto-create a Meet link or email
invites (needs Google Workspace + domain-wide delegation), so a static room link
`GOXL_MEETING_URL` is attached and `GOOGLE_CALENDAR_CREATE_MEET` /
`GOOGLE_CALENDAR_INVITE_ATTENDEES` stay off; on Workspace, flip both to `true`
with no code change.

**Email** (`app/services/email.py`, `app/services/discovery_notifications.py`) —
generic SMTP with a stub fallback (logs instead of sending until `EMAIL_HOST` is
set). Booking sends a confirmation as a background task (never blocks or breaks
the booking); `send_due_reminders()` sends a single 1-hour reminder and respects the founder's
`notification_preferences.email_reminders`. (A 24-hour reminder existed and was
cut on 2026-09-07: two emails for one 30-minute call is how a founder learns to
filter us.) Run it with `python -m app.jobs.discovery_reminders` — **hourly**,
because the window is "within the next hour" and a daily run would miss almost
every call. Scheduling it is deployment infra. Works with any SMTP provider; **AWS SES** later
is a config-only swap to its SMTP endpoint, no code change.

## Three rules that are not obvious, and each one has already bitten

### 🔴 1. Route handlers that touch the database must be `def`, never `async def`

FastAPI runs an `async def` handler **directly on the event loop**. A synchronous
SQLAlchemy call inside one blocks that loop -- so every other request in flight,
for every founder, stops until it finishes. A plain `def` handler is run in a
threadpool instead and is genuinely concurrent.

```python
# WRONG -- freezes the whole server for the length of the query
@router.get("/thing")
async def read_thing(db: Session = Depends(get_db)): ...

# RIGHT -- FastAPI runs this in its threadpool
@router.get("/thing")
def read_thing(db: Session = Depends(get_db)): ...
```

This is not a style preference. On 2026-09-07, 53 handlers and shared auth
dependencies were written this way and production served requests **one at a
time**: a page that fires 15 requests queued them all and the browser cancelled
them at its 20-second timeout. Founders saw a permanent loading spinner.
Measured after the fix: 12 concurrent requests went from 23.4s to 4.0s.

**If a handler genuinely needs `await`** (an LLM call, `request.body()`,
`file.read()`), keep it `async def` but push the blocking part into a thread:

```python
from starlette.concurrency import run_in_threadpool

async def handler(request: Request, db: Session = Depends(get_db)):
    body = await request.body()              # genuinely async
    return await run_in_threadpool(_work, db, body)   # everything else
```

`app/api/v1/webhooks/razorpay.py` and `profile/routes.py::upload_avatar` are the
worked examples.

### 🔴 2. Row-level security hides rows from code that has not identified itself

Every founder-scoped table carries the policy
`founder_id = public.get_founder_id() OR app.current_admin`. A session with
neither set sees **zero rows** -- silently, with no error.

- A **request** gets founder context from `get_founder_record` automatically.
- A **job or admin path** that legitimately works across founders must call
  `set_admin_rls_context(db)` itself, inside the transaction.

This is invisible in local development, which connects as a BYPASSRLS superuser
and never exercises the policy. It only appears in production. Two things had
already been built without it: the whole admin panel (every queue would have
shown an admin only their own rows) and the notification sweep.

### 🔴 3. `DATABASE_URL` must use the transaction-mode pooler, port **6543**

Port 5432 is *session* mode: the whole project shares 15 connections and this
app can demand 15 by itself, so a second process starves and requests block
waiting for a connection that is not coming. Port 6543 borrows a connection per
transaction and hands it straight back. The engine sets `prepare_threshold=0`
automatically when it sees that port.

## Layout

```
app/
  api/deps.py          shared route dependencies (founder resolution)
  api/v1/router.py     mounts every module's sub-router
  api/v1/<module>/     one folder per feature area
  core/auth/           provider contract, dev/supabase providers, factory
  core/                config, cors, logging
  db/session.py        engine + session (do not modify)
  models/              SQLAlchemy models — must be imported in __init__.py
  repositories/        generic CRUD base + per-model repositories
  schemas/             Pydantic request/response shapes
  middleware/          request logging, error handling
```

## Tests

```bash
pytest                       # ~2,100 tests across 154 files
python scripts/smoke_test.py # end-to-end smoke check, PASS/FAIL summary
```

Most are hermetic -- they fake the session and the auth provider rather than
touching a database. A subset genuinely does hit the configured database; those
are the ones that fail on a machine whose `DATABASE_URL` is not reachable, and
they are not a signal that your change broke something.

## Status

Everything below is built and in production unless it says otherwise.

**Foundation** — Alembic (90 revisions), 56 logical tables + 36 monthly
partitions, repository layer, RLS on every founder-scoped table.

**Auth** — email + OTP + password via Supabase, backend-issued session tokens
(issue / rotate / revoke), single-use rotating refresh tokens, new-device
sign-in alerts.

**Diagnosis engine** — built. Adaptive question selection, answer
interpretation, confidence scoring and routing, distress detection, root-cause
detection, report generation (screen + PDF via a Gotenberg sidecar). Model
routing lives in the `model_task_routing` table, not in code -- all tasks
currently point at `claude-sonnet-5` on Anthropic.

**Founder-facing** — profile, Founder DNA, Business DNA, Vision, Goals, Plan
Your Day, Next Steps, Recommendations, Frameworks, Achievements, Journey,
Ally Chat, Report, Discovery calls, Billing, Privacy Center, Help & Support.

**Commercial** — plans and entitlements, subscriptions, Razorpay payments and
webhooks, credits with expiry, coupons, daily token metering (resets at
midnight `USAGE_RESET_TIMEZONE`, default Asia/Kolkata).

**Team-facing** — admin panel: users, usage, discovery calls, privacy request
queue, feedback and unanswered help-bot questions, coupons, audit log, system
health.

**Notifications** — in-app bell with 48 types, each switchable from the
`notification_types` table with no deploy. Written by `app/notifications/`,
generated both by a sweep job and when a founder opens the bell.

**Support bot** — answers from `support_bot_answers` (~277 published answers
edited in the database, not in code). Questions it cannot answer are recorded in
`support_bot_misses`.

### Known gaps

- Six handlers in the AI pipeline still make blocking calls on the event loop
  (`diagnosis/router.py`, `founder_dna/router.py`, `impression/`,
  `incremental_confidence.py`) -- see the concurrency rule above. They are not
  on the page-load path but should be reworked.
- The public status page (PRD-09) does not exist.
- Two scheduled jobs need a scheduler in AWS: `app.jobs.discovery_reminders`
  (hourly) and `app.jobs.notification_sweep` (every few hours).
