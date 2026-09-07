# Ally Platform — Backend

FastAPI + SQLAlchemy on Postgres. Frontend is Vite + React 19 in `../frontend`.

Two databases, and which one you are on changes what you can see:

| | |
|---|---|
| **Development** | Supabase, connected as a superuser |
| **Production** | AWS RDS (`ap-south-1`), connected as the restricted `ally_app` role |

That difference is not a detail. Read [Row-level security](#row-level-security)
before writing anything that reads founder data — it is the single most common
source of bugs in this codebase, and none of them reproduce locally.

## Setup

```bash
cp .env.example .env          # then fill in DATABASE_URL and SECRET_KEY
pip install -r requirements.txt
python test_connection.py     # verify the database is reachable
```

`.env.example` documents every optional integration. All of them run in a safe
stub/off mode until configured: Supabase auth, Google Calendar, SMTP email,
object storage, payments, and each LLM provider.

**Point `DATABASE_URL` at port `6543`, not `5432`.** Supabase's session-mode
pooler on 5432 allows fifteen connections for the whole project, and this app
alone can ask for fifteen — so a second process starves and requests block
waiting for a connection that is not coming. That is felt as "the app is slow",
not as an error. Port 6543 is the transaction-mode pooler; the code sets
`prepare_threshold=0` for it automatically.

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

- http://localhost:8000/docs — interactive API docs
- http://localhost:8000/api/v1/health — app + database status

## Auth

**Email, a one-time code, and a password.** Not social login — Google and
LinkedIn are not wired, and a `README` that said otherwise sent people looking
for OAuth code that does not exist.

Supabase Auth owns the credential; the backend issues its own session tokens.
Two ways in, both ending in the same place:

**New founder, or forgotten password**

1. `sendEmailOtp(email)` — Supabase emails an 8-digit code
2. `verifyOtpAndSetPassword(email, code, password)` — verifies the code, stores
   the chosen password, then `POST /auth/session` exchanges the Supabase token
   for ours (and creates the founder row on first sign-in)

**Returning founder**

`signInWithPassword(email, password)` → `POST /auth/session`

The founder's email **is** their login id. The OTP is 8 digits — a Supabase
project setting, not a constant; the frontend accepts the whole configurable
range rather than hardcoding a length.

After the exchange nothing about Supabase matters. Every later request carries
our access token, verified by signature.

`AUTH_PROVIDER` selects the verifier:

- `dev` — every request resolves to a fixed test founder, no token needed.
  Refused at startup when `ENVIRONMENT=production`.
- `supabase` — verifies the JWT. Needs `SUPABASE_JWT_SECRET`.

Moving to Cognito changes only that one class. Session tokens, routes and every
endpoint stay identical.

Endpoints: `POST /auth/session`, `/auth/resume` (restore from a stored refresh
token on reload), `/auth/refresh` (rotate), `/auth/logout`, `GET /auth/me`,
`GET /auth/status`.

Per-request validation is a FastAPI **dependency** (`get_current_founder`), not
middleware — so each route opts in and receives the founder, which middleware
cannot do cleanly. Routes touching founder data take
`founder: Founder = Depends(get_founder_record)`.

**Consent is enforced, not just recorded.** Sign-up captures three things: terms
acceptance (required), an 18-or-over confirmation (required), and an optional
opt-in to diagnosis processing. All three go to `founder_consents`, which is
append-only and server-stamped. The diagnosis routes refuse to run without that
third one — see `require_diagnosis_consent`.

## Row-level security

**Read this before writing any query that touches founder data.**

Every founder-scoped table carries this policy, granted to `ally_app`:

```sql
founder_id = public.get_founder_id() OR app.current_admin
```

`get_founder_id()` resolves from `app.current_founder_uuid`, set per
transaction. So a connection that declares **neither** a founder nor admin
context sees **zero rows** — silently. No error, no warning. A query returns
nothing and the code concludes there is nothing there.

Four separate bugs of exactly this shape were found and fixed on 2026-09-07:

| Where | What it looked like |
|---|---|
| Admin panel | Every queue appeared empty |
| Public report share links | Every link said "This shared report is not available" |
| Internal job endpoints | Erasures, report recovery and reminders all swept nothing and reported success |
| Discovery reminder job | Found zero calls every hour, exited 0 |

**None of them reproduce in development**, which connects as a `BYPASSRLS`
superuser and never exercises the policy. They only appear in production.

The rules:

- **A request with a signed-in founder** — `get_founder_record` already calls
  `set_founder_rls_context`. Nothing to do.
- **A request with no founder that legitimately spans founders** — an admin
  panel read, a public share link, a webhook, a scheduled job — must call
  `set_admin_rls_context(db)`, *after* whatever authorises it. Both are
  transaction-local and die with the request.
- **A background job** (`app/jobs/*`) has no founder by definition. It must set
  admin context or it will find nothing and look like it worked.

## Database

Ninety-two migrations; head is `f1c8d3a26b47`. Around 56 logical tables plus monthly
partitions, with `founders` as the hub.

> ### 🔒 THE RULE — Alembic owns every schema change. No exceptions.
>
> **No `CREATE`, `ALTER`, `DROP`, index, constraint or RLS change outside an
> Alembic revision** — not through the Supabase SQL editor, the Supabase MCP
> tool, `psql`, or any other path, by anyone, human or agent.
>
> Out-of-band DDL creates objects the migration chain has no record of, so a
> later `alembic upgrade` tries to re-create them and fails. That drift has
> already had to be reconciled once.
>
> To adopt objects that already exist, write a revision representing them and
> `alembic stamp` to it — never leave the two out of sync.

```bash
alembic revision --autogenerate -m "what changed"   # review before applying
alembic upgrade head
alembic current
```

Baseline `5cbf7c8fea1e` is intentionally empty: it records that Alembic adopted
an already-populated schema rather than creating it.

Two limits:

- Alembic cannot see RLS policies, partitions or database functions. Write those
  by hand inside a revision — see `d91c6e4b72aa` for the pattern.
- Tables with no model in `app/models/` are ignored, not dropped (the
  `include_object` guard in `alembic/env.py`).

**CI blocks a branched migration graph** — exactly one head, or the deploy stops.

## Async and blocking

FastAPI runs an `async def` handler directly on the event loop. A synchronous
database call inside one **blocks the entire server** until it returns, so
concurrent requests queue instead of overlapping.

That was the state of 53 handlers until 2026-09-07. A page firing fifteen
requests saw them serialise and the browser cancelled them at its 20-second
timeout. Measured after the fix: twelve concurrent requests went from 23.4s to
4.0s.

**So: if a handler uses a synchronous `Session`, declare it `def`, not
`async def`.** FastAPI then runs it in a threadpool and requests are genuinely
concurrent. Only use `async def` when the body actually `await`s something — and
if it also does blocking work, push that through
`starlette.concurrency.run_in_threadpool` (see the Razorpay webhook and the
avatar upload).

Six handlers in the AI pipeline are still `async def` with blocking calls
interleaved between awaits. They are not on the page-load path but will stall
under load; fixing them means restructuring the service layer.

## Modules

One folder per feature area under `app/api/v1/`, mounted by `router.py`:

`achievements · admin · auth · calendar · chat · consents · current_problem ·
dashboard · diagnosis · discovery · feedback · founder_dna · founder_goals ·
framework_usage · frontend_errors · impression · intelligence · knowledge ·
notifications · payments · planning · plans · privacy · profile · reference ·
reports · settings · support · vision · voice · webhooks`

Domain logic lives outside the API layer, in its own package: `app/credits/`,
`app/coupons/`, `app/planning/`, `app/plans/`, `app/privacy/`, `app/consents/`,
`app/support_bot/`, `app/notifications/`, `app/vision/`, `app/admin/`.

```
app/
  api/deps.py          shared route dependencies (founder resolution + RLS)
  api/v1/router.py     mounts every module's sub-router
  core/auth/           provider contract, dev/supabase providers, factory
  core/                config, container, cors, logging
  db/session.py        engine, session, RLS context helpers
  jobs/                runnable background jobs (python -m app.jobs.<name>)
  models/              SQLAlchemy models — must be imported in __init__.py
  repositories/        generic CRUD base + per-model repositories
  schemas/             Pydantic request/response shapes
  services/            email, calendar, LLM providers, object storage
  middleware/          request logging, error handling
```

## Background jobs

Run with `python -m app.jobs.<name>`. Each is idempotent and reports through its
exit code, which is what a scheduler actually reads:

| Job | Cadence | Exit codes |
|---|---|---|
| `discovery_reminders` | **hourly** | `0` ok · `1` failed · `2` email not configured |
| `notification_sweep` | every 4 hours | `0` ok · `1` failed |
| `verify_notifications` | on demand | preflight for email + calendar; `--send-to ADDRESS` sends a real test |

`discovery_reminders` must be hourly: it looks for calls in the next 60 minutes,
so a daily run would miss nearly every call.

There are also HTTP-triggered sweeps under `/internal/jobs/*`, authenticated by
`X-Internal-Secret` and called by an external scheduler — account erasure,
report reconciliation, PDF backfill, health check, call reminders.

## Email

`app/services/email.py` — generic SMTP, stub fallback that logs instead of
sending until `EMAIL_HOST` is set. Works with any provider.

Production sends through Resend from `info@goxlally.ai`, with `EMAIL_REPLY_TO`
pointing at a real monitored mailbox — the From address invites replies, and
without a Reply-To they would bounce.

What the backend sends:

- Discovery call confirmation, and one reminder an hour before
- New-device sign-in alert (new devices only, and never the first one)

Founder feedback, support messages and privacy requests deliberately send **no**
team email — they are reviewed in the admin panel instead.

## Discovery calls

A founder books a slot; the backend reads real availability from Google
Calendar, creates the event, and emails a confirmation.
`GET /discovery/slots`, `POST /discovery/book`, `GET /discovery/calls`.

`app/services/calendar.py` uses a service account, running as a stub until
`GOOGLE_CALENDAR_ID` and a key are set. On a **personal Gmail** calendar a
service account cannot create a Meet link or invite attendees — that needs
Google Workspace plus domain-wide delegation and
`GOOGLE_CALENDAR_DELEGATED_USER`. Until then bookings attach the shared
`GOXL_MEETING_URL` room.

## Tests

```bash
pytest                       # 2,104 tests across 154 files
python scripts/smoke_test.py # end-to-end smoke check
```

Most are hermetic — in-memory repositories and dependency overrides, no database
and no auth backend. A handful are DB-backed and will error locally on a
`create_founder_on_signup: missing authenticated user context` fixture problem
that is unrelated to whatever you are changing.

**What tests cannot catch here:** row-level security, because development
bypasses it. If a change touches who can see which rows, it has to be verified
in production.

## Deployment

Pushing to `main` runs CI, and a green CI triggers `backend-deploy.yml`, which:

1. blocks a branched migration graph
2. checks a one-off task can reach the production database
3. runs `alembic upgrade head` on a **privileged migration-only** task
   definition — stopping the deploy if it fails
4. only then updates the ECS service, which keeps its restricted `ally_app`
   credentials

So migrations apply themselves. Watch the *"Run Alembic migration once"* step;
it prints the container's own logs on failure.

`app.goxlally.ai` is Vercel. `api.goxlally.ai` is this service. `frontend/vercel.json`
is load-bearing — the `/api/*` proxy, the `/r/:token` share rewrite and the SPA
fallback all live there.
