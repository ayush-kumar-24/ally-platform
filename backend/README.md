# Ally Platform — Backend

FastAPI + SQLAlchemy on Supabase Postgres.
(Frontend is Vite + React 19 with react-router, in `../frontend`.)

## Setup

```bash
cp .env.example .env          # then fill in DATABASE_URL and SECRET_KEY
pip install -r requirements.txt
python test_connection.py     # verify the database is reachable
```

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

Social login only — Google and LinkedIn, no passwords. Two token worlds, kept
separate so the API never depends on the identity provider:

- **Identity provider token** (Supabase now, Cognito on AWS later) proves who the
  user is, *once*, at `POST /auth/session`.
- **Backend session tokens** — the backend then issues its own access + refresh
  JWTs (signed with `SECRET_KEY`). Every later request carries the access token.

Login flow:

1. Frontend runs Google/LinkedIn login via Supabase, gets a Supabase token.
2. `POST /auth/session` with that token → backend returns `{access_token, refresh_token}`.
3. Requests send the access token; `POST /auth/refresh` rotates it; `POST /auth/logout` revokes it.

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

**LinkedIn / Google** are enabled in the Supabase dashboard (Authentication →
Providers), not in backend code — the backend treats both identically.

**Provisioning** (creating a founder row on first login) is behind
`ENABLE_FOUNDER_PROVISIONING`, off by default, so no rows are written until it is
switched on. Real-user *auth* testing (login, refresh, logout) works without it;
only saving founder *data* needs it on.

## Database

The schema already exists — 56 logical tables (plus 36 monthly partitions),
created by Supabase migrations, with `founders` as the hub that 66 other tables
reference.

**Alembic owns all schema changes from here on.** Do not alter schema through the
Supabase SQL editor, or the two will drift.

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
  schemas/             Pydantic request/response shapes
  middleware/          request logging, error handling
```

## Tests

```bash
pytest                       # auth integration suite (tests/)
python scripts/smoke_test.py # end-to-end smoke check, PASS/FAIL summary
```

Both are hermetic for auth (dev mode, provisioning off) and never write to the
database.

## Status

- Foundation, Alembic — done
- Auth — done: Google/LinkedIn via Supabase, backend-issued session tokens
  (issue / refresh / validate / logout), session revocation scaffold
- Models — all 56 logical tables mapped in `app/models/`, verified zero-drift
  against the live schema (`schema.py` generated + curated, `partitioned.py` by hand)
- `profile` — done
- `ai`, `dashboard`, `diagnosis`, `discovery`, `planning`, `reports`, `settings` — stubs
- Founder provisioning on signup — scaffolded, disabled (needs DB signup-bug fix + sign-off)
