# Ally backend

FastAPI + SQLAlchemy + Alembic on Supabase Postgres. Serves the founder
journey (Founder DNA → Current Problem → Diagnosis → Clarity Report), the
dashboard behind it, and the admin panel.

This file covers the four things that are not obvious from the code: where
configuration comes from, how auth resolves, how migrations run, and how to
prove the diagnosis actually works end to end. For what the product *is*, see
the [root README](../README.md).

## Layout

```
app/
  main.py            app assembly, boot-time warnings, middleware
  api/v1/            one package per feature; router.py mounts them all
  core/              config, paths, auth, logging
  db/session.py      the engine, the pool, and RLS context
  models/            SQLAlchemy models (schema.py is generated from the DB)
  services/          LLM providers, retrieval, embeddings
  repositories/      data access shared across services
alembic/versions/    migrations, one file per revision
scripts/             operational and diagnostic scripts (see below)
tests/               pytest; `pytest` from this directory runs them
docs/                deeper notes on providers, launch, RDS, retrieval
```

## Configuration: exactly one `.env`

**This backend reads one environment file: `backend/.env`.** It is found from
the code's own location (`app/core/paths.py`), so it is the same file whether
you start uvicorn from `backend/`, from the repository root, or from inside a
container. That was not always true — both readers were given the bare relative
name `".env"`, which resolves against the working directory, so starting from
the repo root read a different file with no error and no log line.

Any other `.env.*` beside it — `.env.rds`, `.env.local`, `.env.bak` — is
**inert**. Nothing here opens them; they are not fallbacks and not profiles.
Boot logs an `env_files_ignored` warning naming every one it finds, so a stale
alternate cannot quietly look like live configuration. `.env.example` is the
exception: it is committed as documentation of every supported variable and is
never loaded.

```bash
cp .env.example .env     # then fill in DATABASE_URL and SECRET_KEY
```

Start it with `python scripts/run_dev.py --reload`, which changes into this
directory first so the launcher can live anywhere.

### DATABASE_URL and the two pooler ports

Supabase's pooler runs two modes on two ports, and which one this points at
decides whether the app can breathe:

| Port | Mode | What it means here |
| --- | --- | --- |
| 5432 | session | A connection is held for the life of a client session. The **whole project** gets fifteen, shared by every process. |
| 6543 | transaction | A connection is borrowed per transaction and handed straight back. This is the mode this workload wants. |

Use **6543**. Session mode dropped three of ten end-to-end runs mid-request
("server closed the connection unexpectedly", one of them 582 seconds in,
mid-COMMIT). If `DATABASE_URL` names a `*.pooler.supabase.com` host on 5432,
the app moves it to 6543 for its own engine at startup and logs
`database_url_moved_to_transaction_pooler` — fix the port in `.env` so it stops
needing to, or set `DB_SESSION_POOLER_OK=true` to keep session mode
deliberately. Only pooler hosts are touched: on a direct Supabase endpoint, an
RDS instance or a local postgres, 5432 is the only port there is.

psycopg3 prepares statements by default and a transaction pooler cannot carry
them across the connections it hands out, so preparation is disabled
(`prepare_threshold=None`) automatically whenever the URL names 6543. Note the
value: psycopg reads `0` as *prepare everything on first execution*, and only
`None` turns preparation off. Getting that backwards fails as
`InvalidSqlStatementName: prepared statement "_pg3_N" does not exist`, part-way
through a session rather than at connect time. Alembic is deliberately left on whatever `.env`
says, because session mode is what Supabase wants for DDL.

### The setting pair that empties reports

`ADAPTIVE_QUESTIONS` and `ANSWER_CLASSIFIER` are independent flags, and **with
both at their defaults no answer ever gets a Green/Amber/Red band**:
`ADAPTIVE_QUESTIONS` is the only thing that writes `answers.score_label` at
submit time, and `ANSWER_CLASSIFIER="llm"` is the only thing that derives a band
at report time. Neither on means every answer reaches the reasoning pipeline
unscored, every one is skipped as unclassifiable, and the diagnosis produces a
report with no evidence behind it. `settings.diagnosis_scoring_configured` is
that coupling, named once; the journey check below refuses to run when it is
false.

Scoring also needs `LLM_PROVIDER` (`anthropic` | `openai` | `gemini`) and the
matching key. Semantic retrieval needs `OPENAI_API_KEY` for embeddings
(`text-embedding-3-small`, 1536 dimensions). `scripts/_verify_llm_keys.py`
checks both keys directly, without booting the app.

## Auth

`AUTH_PROVIDER` picks one of two providers (`app/core/auth/factory.py`):

- **`dev`** — no token at all resolves to a fixed founder
  (`00000000-0000-0000-0000-000000000001`), so any protected route works from
  `/docs` or curl. Passing any bearer token uses that string as the founder id,
  which is how you exercise multi-founder behaviour. **The factory refuses to
  build it when `ENVIRONMENT=production`.**
- **`supabase`** — verifies the JWT the frontend receives from Supabase Auth.
  Supabase signs user tokens with **ES256** and publishes the public key at
  `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, so `SUPABASE_URL` is the
  setting that matters. `SUPABASE_JWT_SECRET` is the legacy shared HS256 secret,
  kept as a fallback for older projects; verifying the anon key against it proves
  the secret is right and proves nothing about user tokens, which are signed by a
  different key entirely.

Row Level Security is enforced in the database, not in the query. Every session
sets `app.current_founder_uuid` transaction-locally (`set_founder_rls_context`),
and a session with neither that nor `app.current_admin` sees **zero rows** on
every founder-scoped table rather than failing loudly. Server-initiated jobs
that legitimately work across founders use `set_admin_rls_context`; a request
path should never reach for it.

## Migrations

```bash
alembic upgrade head                      # apply
alembic revision --autogenerate -m "..."  # create
alembic downgrade -1                      # step back
```

The URL comes from `.env`, never from `alembic.ini` — `alembic.ini` is
committed and `.env` is not. Supabase's own schemas (`auth`, `storage`,
`realtime`, `vault`, `cron`, …) are on an ignore list in `alembic/env.py`;
autogenerate must never emit DDL against them, and an autogenerated revision
that touches one is a bug in that list.

Migrations run against **session mode or a direct connection**, which is why
the 6543 rewrite above is scoped to the runtime engine only.

## Tests

```bash
pytest                       # from this directory
pytest tests/test_x.py -q
```

No database is required for the unit tests. The diagnosis question bank lives
only in the live Supabase project — migration `63340a6e5fdb` asserts
`MAX(question_id) = 2129` — so a fresh local Postgres cannot host a full
journey. Run the journey check against the real database instead.

## Proving the journey works

`scripts/e2e_journey_check.py` walks onboarding → Founder DNA → Current Problem
→ Diagnosis → Report over the real HTTP API, with real model calls, and counts
rows in `llm_call_log` before and after. **Zero calls means nothing reached a
model** — usually the failover chain falling through to `MockLLMProvider` after
an auth error, which otherwise looks like a successful run.

```bash
python -m scripts.e2e_journey_check --database-url "..." --founder-id 3704 \
    --persona strong --confirm-writes
python -m scripts.e2e_journey_check --database-url "..." --cleanup-founder-id 3704
```

Two personas answer the same question bank: `weak` (vague, evasive) and
`strong` (specific, evidenced). They are the discrimination test — the same
engine should separate them, and does: 20 business health against 92, eight root
causes against two.

Reading the output:

- **"N matched on topic"** — answers are matched to questions by topic, and one
  that matches nothing falls back to a generic line. The fallback does *not*
  read as neutral to the classifier; it reads as evasion and scores red for
  either persona, which on a category holding a single question is enough to
  manufacture a top finding. Bands are reported split by this for that reason.
  A run that mostly fell back is measuring the fallback, not the persona.
- **"stopped after N answers"** — the two personas do **not** answer the same
  number of questions. The engine ends the session as soon as
  `overall_confidence_score` clears the `routing_state` threshold (>80 →
  `generate_report`), so a persona that answers clearly gets asked less. Band
  shares, not counts, are what compare across runs.

Cleanup clears the answers *and* the completion timestamps on `founders`
(`founder_dna_completed_at`, `current_problem_completed_at`). Leaving those set
is what once made both phases answer "already complete", serve nothing, and
report success.

## Other scripts

| Script | What it does |
| --- | --- |
| `run_dev.py` | Start the API from any working directory |
| `_verify_llm_keys.py` | Check `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` without booting |
| `_conn_probe.py` | Throwaway connection, to separate a bad password from a bad URL |
| `seed_dev_founder.py` | Three seeded personas for local work |
| `reset_diagnosis_data.py` | Clear a founder's diagnosis state |
| `smoke_test.py` | Fast check that the app boots and core routes answer |
| `run_evaluation.py`, `calibration/` | Scoring evaluation and confidence calibration |
| `embedding_migration/` | Generate and verify question embeddings |

## Further reading

`docs/` holds the deeper notes: `PROVIDERS.md` (LLM and email providers),
`PRODUCTION-RDS-CHECKS.md`, `PUBLIC-LAUNCH-CHECKLIST.md`,
`evaluation_framework.md`, `learning_engine.md`, `retrieval_benchmark.md`.
Deployment is in `DEPLOY_AWS.md` and the `Dockerfile`.
