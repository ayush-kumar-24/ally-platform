# Ally Backend — Stack & Structure (onboarding)

Everything the backend is actually built on, and how the pieces fit. Read top to
bottom once; after that use it as a lookup table.

Where something is installed but **not actually in use**, it's marked so — you'll
otherwise waste time studying dead paths.

---

## 1. Language & runtime

| Thing | Version / note |
|---|---|
| Python | 3.11 (`Dockerfile` uses `python:3.11-slim`; local venvs may be 3.12) |
| Package manager | plain `pip` + pinned `requirements.txt` (no Poetry/uv) |
| Process | `uvicorn app.main:app` — ASGI, async-capable |

```bash
pip install -r requirements.txt
```

---

## 2. Core web framework

| Library | What we use it for |
|---|---|
| **FastAPI** `0.139` | The whole HTTP layer — routers, dependency injection (`Depends`), OpenAPI docs at `/docs` |
| **Starlette** | FastAPI's foundation. We touch it directly for `StaticFiles` (serving `/uploads`), `StarletteHTTPException`, and custom middleware |
| **Uvicorn** `0.51` | ASGI server (with `httptools` + `watchfiles` for dev reload, `websockets` extra) |
| **Pydantic v2** + **pydantic-settings** | Request/response schemas (`app/schemas`, `app/**/schemas.py`) and typed config (`app/core/config.py`) |
| **python-multipart** | File uploads (avatars, chat attachments) |
| **httpx** | Every outbound HTTP call we make — LLM providers, Gotenberg, and the test client |

**Entrypoint:** [app/main.py](../app/main.py) — loads `.env` (with `override=True`, deliberately),
configures logging + Sentry, builds the `FastAPI` app, adds middleware/error handlers,
mounts `/uploads`, includes the single root router.

**All routes hang off one router:** [app/api/v1/router.py](../app/api/v1/router.py), prefix `/api/v1`.
~25 feature routers are included there (auth, profile, diagnosis, discovery, dashboard,
reports, chat, admin, planning, consents, privacy, voice, plans, knowledge, intelligence,
notifications, feedback, webhooks, …) plus `GET /api/v1/health` which pings the DB.

---

## 3. Database layer

| Library | Role |
|---|---|
| **PostgreSQL, hosted on Supabase** | The database |
| **SQLAlchemy 2.0** | ORM + Core. **Sync** engine/session (`Session`, not `AsyncSession`) |
| **psycopg 3** (`psycopg` + `psycopg-binary`) | The Postgres driver — the URL must read `postgresql+psycopg://` |
| **psycopg2-binary** | ⚠️ Safety net only. Production's `DATABASE_URL` secret still lacks the `+psycopg` suffix, so SQLAlchemy falls back to psycopg2. Deploying without it crash-looped every task. Do not build anything new on it — see the comment in `requirements.txt` |
| **Alembic** `1.18` | All schema DDL. 44 revisions in `alembic/versions/`. **Alembic owns the schema — never hand-edit tables in Supabase** |
| **pgvector** `0.5` | Vector column type for embeddings / semantic retrieval |
| **greenlet**, **Mako**, **MarkupSafe** | Transitive deps of SQLAlchemy/Alembic, not used directly |

**Engine/session:** [app/db/session.py](../app/db/session.py) — one module-level `engine`,
`SessionLocal`, `Base`, and the `get_db()` FastAPI dependency (yield + close).

⚠️ Pool size is deliberately tiny (`DB_POOL_SIZE=2`, `DB_POOL_MAX_OVERFLOW=3`). Supabase's
session-mode pooler allows only **15 client connections total, shared by everything**.
Higher numbers caused a real outage with just two local processes. Context in `DEPLOY_AWS.md`.

⚠️ `app/db/session.py` and `app/core/auth/*` are treated as protected — ask before changing them.

**Models:** [app/models/](../app/models/) — grouped by domain, not one file per table:
`schema.py` (the large shared one), `auth.py`, `diagnosis.py`, `reasoning.py`, `scoring.py`,
`memory.py`, `llm.py`, `suggestions.py`, `partitioned.py`, `enums.py`. ~56 tables.

```bash
alembic upgrade head
```

(also runs automatically on container start — see `CMD` in the `Dockerfile`)

---

## 4. Auth

Pluggable behind our own interface — **no auth library** (no fastapi-users, no authlib).

- `app/core/auth/base.py` — the `AuthProvider` port
- `app/core/auth/factory.py` — picks the implementation from `AUTH_PROVIDER` (`dev` | `supabase`).
  `dev` hard-refuses to run when `ENVIRONMENT=production`; an unknown value raises rather than
  falling back
- `app/core/auth/supabase_provider.py` — **Supabase Auth** is the real one. Supabase signs user
  tokens with **ES256** and publishes the public key at `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`,
  so JWKS verification is the primary path. `SUPABASE_JWT_SECRET` (HS256) is a legacy fallback only
- `app/core/auth/dev_provider.py` — local development; accepts any request as a fixed test founder
- `app/core/auth/tokens.py`, `session_store.py` — our own refresh-token / session handling
- **python-jose** (+ `rsa`, `ecdsa`, `pyasn1`) — JWT signing/verification for our own tokens (`HS256`)
- Refresh token rides in an httpOnly cookie (`ally_refresh_token`)
- `app/api/v1/webhooks/supabase.py` — Supabase auth webhooks, verified with `SUPABASE_WEBHOOK_SECRET`

> **Not used:** AWS Cognito. Several comments in the codebase mention "Cognito later" — that's a
> possible future migration, not something running. Supabase Auth is the live identity provider.

---

## 5. LLM / AI stack

**There is no vendor SDK.** No `openai`, no `anthropic`, no Google GenAI package in
`requirements.txt`. Every provider is called over raw **httpx** against its REST API,
behind our own adapters. That was deliberate — small dependency surface, swappable and
easily mockable providers.

### What actually runs

| Path | Provider | Model |
|---|---|---|
| **Diagnosis** (answer classification, adaptive questioning, reasoning) | **Anthropic** | `claude-sonnet-5` |
| **Chat / Ally** (`/chat`, `/ally/chat`) | **OpenAI** | `gpt-4o-mini` |
| Chat fallback chain | OpenAI → Anthropic → offline `MockLLMProvider` | never fails closed |
| **Voice** transcription | OpenAI Whisper | `app/services/voice/openai_whisper.py` |

Task→model routing for the 7 named LLM tasks lives in the **database** (`model_task_routing`
table, seeded by Alembic), not in code.

> **⚠️ Google Gemini is NOT used.** `gemini_provider.py`, `GeminiAdapter`, the Gemini embeddings
> adapter, and the `GEMINI_*` settings all exist as a dormant third implementation of the provider
> interface. No `GEMINI_API_KEY` is ever set, so `routing.py` never registers it and `settings.py`
> skips it. Treat it as an unused reference implementation — ignore it when reading the LLM code,
> and don't assume anything routes through it.

### Where the code lives

Two provider stacks exist (both live, split by history and purpose):

**A. `app/integrations/llm/` — the chat/voice stack**
- `base.py` (`HttpLLMProvider`), `adapters.py` (per-vendor wire format)
- `openai_provider.py`, `anthropic_provider.py` (+ the unused `gemini_provider.py`)
- `routing.py` — `FailoverLLMProvider`, the OpenAI → Anthropic → Mock chain
- `health.py`, `errors.py` (`LLMAuthError`, …)
- `settings.py` — reads `os.environ` **directly**, by design ("no coupling to app settings").
  This is why `main.py` must call `load_dotenv(override=True)` before any other import

**B. `app/services/llm/` — the task-routed stack**
- `providers/` (openai, anthropic, + unused gemini), `registry.py`, `router.py`
- `tasks.py` — the 7 named LLM tasks · `telemetry.py` — token/cost logging

**Embeddings & retrieval**
- `app/services/embeddings/` — provider registry (OpenAI; the Gemini one is unused)
- `app/services/retrieval/` + `app/api/v1/ally/rag/` — pgvector-backed semantic search
- `RETRIEVAL_ENABLED=false` today — it stays off until the embedded tables actually have vectors

**The Ally AI layer** — `app/ai_chat/` and `app/api/v1/ally/`:
`context/`, `memory/`, `kg/` (knowledge graph), `rag/`, `prompts/` + `prompts/grounding/`,
`orchestrator/`, `execution/`; `ai_chat/` adds `streaming/` (SSE), `attachments/`,
`suggestions/`, `links/`, `builders/`.

**Feature flags:** every LLM-powered path is behind an off-by-default boolean in
`app/core/config.py` — `ARCHETYPE_LLM`, `REPORT_NARRATIVE_LLM`, `ANSWER_CONSISTENCY_LLM`,
`DISTRESS_LLM`, `ADAPTIVE_QUESTIONS`, `RETRIEVAL_ENABLED`, `RECOMMENDATION_FALLBACK_LLM`,
plus `ANSWER_CLASSIFIER=stored`. Enable per-test, not globally.

---

## 6. Documents, reports & files

| Library | Use |
|---|---|
| **Gotenberg** (external headless-Chromium sidecar, called over httpx) | **Primary** report PDF renderer. We POST self-contained print HTML to `/forms/chromium/convert/html` with `preferCssPageSize` + `printBackground` so the PDF matches the screen exactly. Fonts are base64-embedded so Gotenberg needs no network. `GOTENBERG_URL`, code in `app/api/v1/reports/gotenberg.py` + `print_html.py` |
| **reportlab** `5.0` | **Fallback only** — `routes.py` catches `GotenbergError` and re-renders with reportlab, tagging the response `renderer="reportlab-fallback"` |
| **pypdf** | Reading/merging uploaded PDF attachments |
| **python-docx** + **lxml** | Reading `.docx` chat attachments |
| **StaticFiles** → `./uploads` | Avatar storage. **Local disk only — there is no S3 upload code and no boto3.** Files do not survive a container replacement. Swapping to a bucket is scoped to one function in `app/api/v1/profile/routes.py` |

---

## 7. AWS — how we actually use it

AWS is **infrastructure, not a Python dependency**. There is no `boto3` in
`requirements.txt` and no AWS SDK call anywhere in `app/`. Everything below is
configured in the console / GitHub Actions, and the app only sees plain env vars.

| Service | Role |
|---|---|
| **ECR** | Container registry — `ally-backend` image, region `ap-south-1` (Mumbai) |
| **ECS** | Where the backend actually runs today. Live task-definition revisions are referenced in the `Dockerfile` and `requirements.txt` comments (rev 55 = the psycopg2 crash, rev 56 = the `/app/uploads` permission crash). Both fixes are in the image now |
| **App Runner** | What `DEPLOY_AWS.md` documents, and the originally chosen target. Chosen over **Lambda** specifically because this API holds a long-lived SQLAlchemy pool against Supabase's 15-connection pooler, which serverless cold starts would exhaust. 1 vCPU / 2 GB, 1–2 instances, port 8000 |
| **Secrets Manager** | All production secrets (`DATABASE_URL`, `SUPABASE_*`, `SECRET_KEY`, LLM API keys) — referenced by the service, never baked into the image |
| **CloudWatch Logs** | Container logs. First thing to check on a deploy; watch for repeated `EMAXCONNSESSION` (pool exhaustion) |
| **S3** | Hosts the built **frontend** (`frontend/dist`), synced by `.github/workflows/deploy-frontend.yml` using the AWS CLI + `aws-actions/configure-aws-credentials@v4`. Not used by the backend |
| **SES** | Possible SMTP provider for `EMAIL_HOST` — the email code is provider-agnostic stdlib SMTP |

> Ambiguity worth knowing: the docs say App Runner, the live crash notes say ECS.
> Confirm which one your account is actually serving from before you deploy.

Deploy shape:

```bash
docker build -t ally-backend .
```

then tag + push to ECR and roll the service. The container's start command is
`alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000` — **migrations
apply on every deploy**. It runs as a non-root `ally` user, and `/app` is `chown`ed at
build time because `main.py` creates `./uploads` at import.

Read `DEPLOY_AWS.md` and `../DEPLOY.md` before touching infra.

---

## 8. Other external integrations

- **Supabase** — Postgres + Auth + auth webhooks
- **Google Calendar** — `google-api-python-client` + `google-auth`, service-account credentials,
  for discovery-call booking (`app/services/calendar.py`). Runs in **stub mode** with deterministic
  slots when unconfigured. This is the *only* Google service we use — see the Gemini note above
- **SMTP email** — stdlib `smtplib`, no library (`app/services/email.py`), sends as
  `GoXL <no-reply@goxl.in>`. Stub mode (logs instead of sends) when `EMAIL_HOST` is blank
- **Sentry** — `sentry-sdk[fastapi]`, optional (a no-op without `SENTRY_DSN`),
  `send_default_pii=False`, 10% trace sampling in production

---

## 9. Cross-cutting app plumbing

| File | What it does |
|---|---|
| `app/core/config.py` | One `Settings` object (pydantic-settings) — ~90 typed env vars. **All config goes here** |
| `app/core/logger.py` | `configure_logging()`, `LOG_LEVEL` |
| `app/core/cors.py` | `setup_cors(app)` from `CORS_ORIGINS` |
| `app/core/container.py` | **Composition root** — the only place the AI stack is wired. Swapping a repository or provider is a one-file change |
| `app/middleware/request_logging.py` | Per-request logging middleware |
| `app/middleware/error_handler.py` | `AppError` + 4 global handlers (app / HTTP / validation / unhandled) — one consistent JSON error shape |
| `app/repositories/` | Repository pattern over SQLAlchemy |
| `app/schemas/` | Pydantic request/response models |

**Layering to respect:** `api/v1/<feature>/routes.py` → `services` → `repositories` → `models`.
Routers should not touch the ORM directly.

---

## 10. Testing & tooling

| Tool | Note |
|---|---|
| **pytest** `9.1` | 95 test files in `tests/`. `pytest.ini`: `testpaths=tests`, `addopts=-q` |
| **httpx** | Test transport for the FastAPI app |
| **black** | Formatter |
| **isort** | Import ordering |
| `scripts/` | `run_dev.py`, `seed_dev_founder.py`, `smoke_test.py`, `benchmark_retrieval.py`, `run_evaluation.py`, `run_learning.py`, `verify_seed_data.py`, `send_test_email.py`, `embedding_migration/` |

```bash
pytest
```

There is **no** mypy/ruff/pre-commit config and **no CI for the backend** — the only
GitHub Actions workflow deploys the frontend to S3. Backend tests run locally.

---

## 11. Fast orientation for a new dev

1. `app/main.py` → `app/api/v1/router.py` — every feature that exists.
2. `app/core/config.py` — every knob and feature flag.
3. `.env.example` — the annotated version of the above; it explains which LLM runs where.
4. `app/models/schema.py` — the data model.
5. `app/core/container.py` — how the AI stack is assembled.
6. Follow one feature end to end (`app/api/v1/diagnosis/` is representative):
   route → service → repository → model.
7. `docs/` has deeper notes: `PROVIDERS.md`, `learning_engine.md`,
   `founder_memory_integration.md`, `evaluation_framework.md`, `retrieval_benchmark.md`,
   `query_performance.md`, `frontend_integration_mapping.md`.

### House rules
- Alembic owns all DDL.
- `app/db/session.py` and `app/core/auth/*` — ask before changing.
- New config → `app/core/config.py`, never `os.environ` scattered through code
  (the one intentional exception is `app/integrations/llm/settings.py`).
- New LLM feature → behind an off-by-default flag.
- Keep DB pool sizes small.
- Don't add a vendor AI SDK; follow the existing httpx adapter pattern.
