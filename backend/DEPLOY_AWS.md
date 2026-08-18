# Deploying the backend to AWS App Runner

For a ~200–300 user beta. Frontend stays on Vercel (already live at
goxlally.ai) — this covers the backend only. See `../DEPLOY.md` for how the
two connect.

## Why App Runner, not Lambda

This API holds a SQLAlchemy connection pool against Supabase's pooler, which
allows **15 client connections in session mode, shared by everything that
talks to it**. Lambda's serverless model opens a fresh pool on every cold
start; under real concurrent traffic that exhausts the pooler almost
immediately. App Runner runs a small number of long-lived instances instead,
each holding one stable pool — the same shape as running it on a normal
server, just managed.

## Why the Dockerfile changed the pool size

`app/db/session.py` now reads `DB_POOL_SIZE` / `DB_POOL_MAX_OVERFLOW` from
config (default 2 + 3 = 5 per process) instead of the higher numbers used
earlier in development. That earlier setting (5 + 10 = 15 in one process
alone) caused a real outage with just two local processes running — at
App Runner's default of up to 2 instances, 5 per instance keeps the total at
10, leaving headroom for `alembic upgrade head` and anything else that
connects alongside the API.

**Do this too, before real traffic arrives:** switch `DATABASE_URL` to
Supabase's **transaction-mode pooler** (port 6543, not 5432). It's built for
many concurrent short-lived connections rather than a fixed pool of long-lived
ones, and is the actual fix — the pool-size tuning above is a safety margin on
top of it, not a replacement for it.

## 1. Push the image to ECR

```bash
aws ecr create-repository --repository-name ally-backend --region ap-south-1

aws ecr get-login-password --region ap-south-1 \
  | docker login --username AWS --password-stdin <account-id>.dkr.ecr.ap-south-1.amazonaws.com

cd backend
docker build -t ally-backend .
docker tag ally-backend:latest <account-id>.dkr.ecr.ap-south-1.amazonaws.com/ally-backend:latest
docker push <account-id>.dkr.ecr.ap-south-1.amazonaws.com/ally-backend:latest
```

Pick a region close to your beta users; `ap-south-1` (Mumbai) if they're
mostly in India, matching `DISCOVERY_TIMEZONE=Asia/Kolkata` in the app's own
defaults.

## 2. Create the App Runner service

Console → App Runner → Create service → **Container registry** → pick the ECR
image just pushed.

| Setting | Value |
|---|---|
| Port | `8000` |
| CPU / Memory | 1 vCPU / 2 GB |
| Min / Max instances | 1 / 2 |
| Health check path | `/api/v1/health` (checks DB connectivity; returns 503 when the database is unreachable so App Runner actually stops routing to a broken instance — `/` always returns 200 and does not check anything, do not point the health check there) |

Auto deployments: on, so a new image push redeploys automatically.

## 3. Environment variables

Store secrets in **Secrets Manager** and reference them from App Runner rather
than pasting real values into the console — anyone with read access to the
service configuration can otherwise see them in plain text.

Values that must differ from `backend/.env.example`'s development defaults:

| Variable | Value | Why |
|---|---|---|
| `ENVIRONMENT` | `production` | `factory.py` refuses `AUTH_PROVIDER=dev` unless this is set |
| `AUTH_PROVIDER` | `supabase` | dev auth accepts any bearer as a founder id |
| `SUPABASE_JWT_SECRET` | Supabase → Settings → API → JWT Secret | verifies the token the browser presents |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` | signs this app's own tokens |
| `DATABASE_URL` | the **6543** transaction-pooler URI, not 5432 | see above |
| `CORS_ORIGINS` | `https://goxlally.ai,https://www.goxlally.ai` | belt-and-suspenders: the Vercel rewrite keeps normal browser traffic same-origin so this shouldn't matter day to day, but anything that calls the API directly (not through the rewrite) needs these two allowed |
| `ANTHROPIC_API_KEY` | | diagnosis reasoning + the founder's first impression |
| `OPENAI_API_KEY` | | chat + voice transcription |
| `SENTRY_DSN` | Sentry → Settings → Client Keys (DSN) | `app/main.py` only initializes Sentry `if settings.SENTRY_DSN` — leaving this unset means production error tracking is silently off with no other signal. Required for beta, not optional. |
| `PLAN_ENFORCEMENT_ENABLED` | `true` (now the code default too, as of 2026-08-16 — this row is a "don't override it to false" reminder, not an action item) | with it off, chat LLM usage is unbounded per user — see cost-controls note below |
| `ADAPTIVE_QUESTIONS` | `true` | **This table previously omitted this row and the one below, and that omission was the bug.** These two flags are coupled: `ADAPTIVE_QUESTIONS=true` is the only thing that writes `answers.score_label`, and `ANSWER_CLASSIFIER=llm` is the only thing that derives a band at report time. Set to `false` alongside `ANSWER_CLASSIFIER=stored` — which is what `.env.example` used to ship — and *every answer reaches the reasoning pipeline unscored*, every one is skipped, and each diagnosis produces a report with no root causes in it. Silently: 200 response, no error, a founder reading an empty report after thirty questions. |
| `ANSWER_CLASSIFIER` | `stored` | Keep it `stored` **with `ADAPTIVE_QUESTIONS=true`** — the advisor already scored each answer at submit time and the pipeline reuses the label. Setting this to `llm` as well is not broken, just wasteful: it re-derives all 30 labels from scratch, which measured as 161s of a 203s pipeline. |

### Verifying the scoring pair is right

Two checks, both cheap:

- **On boot** — `app/main.py` logs `diagnosis_scoring_disabled` at ERROR if neither flag scores answers. Grep the startup log for it; absence is the pass.
- **After a real diagnosis** — the report should have non-empty `detected_root_causes`. If the pair is wrong the pipeline now raises `NoClassifiableAnswersError` and refuses to persist an empty report, so you get a missing report and a loud log rather than a hollow one.

### Reconciliation sweep (required)

`POST /api/v1/internal/jobs/reconcile-reports` — same shared-secret auth as
`process-deletions` (`X-Internal-Secret` / `INTERNAL_JOBS_SECRET`). **Schedule it
every 5–10 minutes.**

Reasoning no longer runs inside the founder's final `POST /diagnosis/answer` — it
was a 203-second pipeline on a request the load balancer cuts off long before
that, which left `COMPLETED` sessions with no report and no way back short of an
admin. It now runs as a background task after the response is sent. A background
task still dies with its container, so **this sweep is the durability
guarantee**, not the background task. It finds completed sessions with no active
report and re-runs them; idempotent, so running it often costs a lookup.

Without it scheduled, the P0 is only half fixed.

Everything else can keep its `.env.example` default.

### Cost controls (LLM spend)

Two different mechanisms bound per-founder LLM cost, deliberately different
because chat and diagnosis have different shapes:

- **Chat** — token-metered via `PLAN_ENFORCEMENT_ENABLED` (see above): a
  daily token ceiling per plan tier plus a credit balance check, both
  enforced pre-flight by `chat_gate` (`app/api/v1/plans/dependencies.py`).
- **Diagnosis** — deliberately NOT token-metered (`app/plans/catalog.py`'s
  own docstring: "a founder must never hit a wall mid-assessment"). Bounded
  instead by (a) `diagnosis_lifetime_limit` — how many diagnoses a founder
  may ever *complete* — and (b) a fixed 30-question cap per session
  (`MAX_DIAGNOSIS_QUESTIONS`). This is a deliberate product decision, not a
  gap to "fix" by bolting token-metering onto it.
- **Both** are additionally backstopped by the per-founder request-rate
  limiter (`app/middleware/rate_limit.py`, wired on `/chat/message`,
  `/chat/stream`, `/diagnosis/start`, `/diagnosis/answer`) — this is what
  actually closes the "unbounded" gap the pre-beta audit flagged: without
  it, nothing stopped a script from hammering `/diagnosis/answer` far faster
  than a real founder ever would, racking up real LLM calls regardless of
  the count-based lifetime cap (which only checks once, at session start).

## 4. Point Vercel at it

Edit `frontend/vercel.json`, replace `REPLACE-ME.awsapprunner.com` with the
service's actual domain (Console → your service → **Default domain**), commit,
push. Vercel redeploys on push and the rewrite takes over immediately — no
DNS change needed, since the browser only ever talks to `www.goxlally.ai`.

## 5. Custom API domain (optional)

App Runner → Custom domains → add e.g. `api.goxlally.ai`, then add the CNAME
it gives you at Hostinger (same DNS panel as before — do not touch the MX or
`_domainkey` records there, that's email). Not required if you're using the
Vercel rewrite from step 4; useful mainly if something needs to call the API
directly rather than through the frontend's proxy.

## Before you call it done

- [ ] `alembic upgrade head` has run against the production database (the
      Dockerfile runs it on every start, so this happens automatically once
      the service is live — confirm it in the App Runner logs on first deploy)
- [ ] `DATABASE_URL` points at the 6543 transaction pooler, not 5432
- [ ] `GET https://<app-runner-domain>/` returns `{"status": "running", ...}`
- [ ] `GET https://<app-runner-domain>/api/v1/health` returns `{"status": "healthy", "database": "connected"}` (503 + `"degraded"` if the DB is unreachable — confirm the App Runner health check is actually pointed here, not at `/`)
- [ ] `SENTRY_DSN` is set and a manually-triggered test error shows up in Sentry
- [ ] `frontend/vercel.json`'s rewrite destination matches the real App Runner
      domain, committed and pushed
- [ ] Full journey works end to end through `www.goxlally.ai`: sign in →
      onboarding → diagnosis → report → tour → dashboard
- [ ] CloudWatch Logs show no repeated `EMAXCONNSESSION` — if they do, the pool
      is still too large for the pooler mode in use
