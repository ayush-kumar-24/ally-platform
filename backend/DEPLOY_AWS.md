# Deploying the backend to AWS

For a ~200-300 user beta. Frontend stays on Vercel (already live at
goxlally.ai) -- this covers the backend only. See `../DEPLOY.md` for how the
two connect.

**This document described App Runner and Supabase until 2026-09-16. Neither is
what runs.** The backend runs on **ECS Fargate** and the database is **RDS**.
The corrections are marked below where they matter; the authority for anything
about the deploy itself is `.github/workflows/backend-deploy.yml`, which is the
thing that actually does it.

## What actually runs

| | |
|---|---|
| Compute | ECS Fargate — cluster `ally-backend-cluster`, service `ally-backend-service` |
| Region | `ap-south-1` |
| Image | ECR repo `ally-backend`, tagged with the deploy SHA |
| Database | **RDS Postgres.** Not Supabase. |
| Public entry | `https://api.goxlally.ai`, TLS terminated ahead of the task |
| Deploy | `.github/workflows/backend-deploy.yml` (OIDC, no long-lived keys) |
| Migrations | a **separate one-off ECS task**, before the service is updated |

Supabase still exists and is kept seeded as a second copy of the reference
data. It is not what production reads.

## Migrations do NOT run when a task starts

This document previously said "the Dockerfile runs it on every start, so this
happens automatically". It does not, and the Dockerfile says so in a comment:

> Database migrations are NOT run automatically when each ECS task starts.
> The CI/CD deployment workflow will run Alembic once before updating ECS.
> This avoids multiple ECS tasks trying to migrate the database concurrently.

The container's `CMD` is uvicorn and nothing else. `backend-deploy.yml`
registers `ally_backend_migration_task` — a task definition identical to the
runtime one except that `DATABASE_URL` points at a privileged Secrets Manager
entry — runs it once, and only then updates the service. A migration that has
not been merged and deployed has not run.

`backend-deploy-preflight.yml` does a read-only Alembic state check against
production first, so a deploy whose migrations would not apply fails before it
touches anything.

## Connections: RDS, not a pooler

The old text here reasoned about Supabase's session pooler allowing **15
connections for the whole project**, and told you to move `DATABASE_URL` to
port 6543. Both are Supabase concepts and neither applies to RDS. Ignore any
6543 advice you find in older notes.

What carries over is the pool sizing, for a different reason. `app/db/session.py`
reads `DB_POOL_SIZE` / `DB_POOL_MAX_OVERFLOW` (default 2 + 3 = 5 per process),
so each Fargate task holds at most five connections. RDS's ceiling is
`max_connections`, which scales with instance class, and every task, every
one-off migration task and every developer's psql draws on the same number.
Five per task leaves room; raising it is a decision to make against the
instance's actual `max_connections`, not by feel.

```sql
-- what the instance actually allows, and what is in use right now
show max_connections;
select count(*) from pg_stat_activity;
```

Three behaviours worth knowing, all in `app/db/session.py`:

* **The Supabase pooler rewrite does not touch RDS.** A `*.pooler.supabase.com`
  host on port 5432 is moved to 6543 automatically; any other host, RDS
  included, is left exactly as written. An RDS endpoint on 5432 is correct and
  nothing will rewrite it.
* **Prepared statements stay ON.** `prepare_threshold` is disabled only for
  port 6543, where a transaction pooler cannot carry them. Against RDS they are
  a straight win and are left alone.
* **`pool_timeout=10`** means connection starvation surfaces as an error
  somebody can act on rather than a request hanging for thirty seconds.

If connection count ever becomes the constraint, the RDS answer is **RDS
Proxy**, not a smaller pool.

### Confirm these — they are not in the repository

The workflow pins the cluster, region, subnets and security group. These are
not recorded anywhere and someone should write them down here:

- [ ] RDS instance class, and the `max_connections` that follows from it
- [ ] Whether the instance is publicly accessible or reached inside the VPC
      (the ECS tasks run with `assignPublicIp=ENABLED`)
- [ ] Whether RDS Proxy is in front of it
- [ ] Whether automated backups / point-in-time recovery are on, and the
      retention window. `data/reference/` protects the *content*; founder
      answers and reports exist only in this database and backups are the only
      thing protecting them.
- [ ] **Whether the `ally_app` role exists.** Check this one first; it is the
      only item here that can have failed silently and permanently.

### The `ally_app` role, and the policies that depend on it

Eighteen migrations create RLS policies and function grants for a role named
`ally_app`. Each one checks whether the role exists and, when it does not,
logs a warning and **skips that step**:

```
WARNING [f7a3d5b1ef52]: role 'ally_app' does not exist on this database --
SKIPPING the founder-isolation RLS policy for founder_goals. EXPECTED on
Supabase (native RLS handles this instead ...). NOT expected on RDS.
```

That is the migrations' own wording, and the reason for it is that Supabase
has its own RLS machinery while RDS does not: on RDS these policies *are* the
founder-isolation boundary. Skipping is the right behaviour — creating a
policy for a role that does not exist would deny all access to the table —
but it is a warning in a log, not a failure, so a deploy where the role was
missing succeeded and looked fine.

Production is RDS. Run this against it:

```sql
select rolname from pg_roles where rolname = 'ally_app';

-- and, for the tables whose policies are conditional on it:
select tablename, policyname
  from pg_policies
 where schemaname = 'public'
   and tablename in ('founder_goals', 'achievements', 'vision',
                     'framework_usage')
 order by tablename;
```

Two further steps skip on the same condition and are worth checking in the
same pass: `8f6c2a1d9b7e` grants `ally_app` runtime access after the RLS
hardening in `4aa14aee3a4e` switched RLS on across thirty tables, and
`3c7e91b40d52` gives it unfiltered read of the two question banks. On RDS,
without the role, the first of those is the difference between the
application being able to read its own tables and not.

If the role is absent, those policies were never created, and every table
they cover is relying on application-level founder filtering alone. Create
the role, then re-run the migrations that reference it — they are written to
be idempotent, so a re-run creates what the first run skipped.

This was found by replaying every migration against an empty Postgres, which
is what `docs/RESTORE.md` does. It has not been checked against RDS, because
this session had no credentials for it.

## 1. Building and shipping the image

`backend-deploy.yml` does this on every merge: builds `backend/Dockerfile`,
tags it with the deploy SHA, pushes to the `ally-backend` ECR repo in
`ap-south-1`, and registers a new task definition from it. The manual commands
below are for a first-time setup or a break-glass deploy only -- the workflow
is the normal path, and it tags by SHA rather than `latest` so a rollback has
something to roll back to.

```bash
aws ecr get-login-password --region ap-south-1 \
  | docker login --username AWS --password-stdin <account-id>.dkr.ecr.ap-south-1.amazonaws.com

cd backend
docker build -t ally-backend .
docker tag ally-backend:latest <account-id>.dkr.ecr.ap-south-1.amazonaws.com/ally-backend:<sha>
docker push <account-id>.dkr.ecr.ap-south-1.amazonaws.com/ally-backend:<sha>
```

`ap-south-1` (Mumbai) matches the beta's users and the app's own
`DISCOVERY_TIMEZONE=Asia/Kolkata` default.

## 2. The ECS service

**Not App Runner.** The service is `ally-backend-service` on cluster
`ally-backend-cluster`, Fargate, with `awsvpcConfiguration` pinned in the
workflow (two subnets, one security group, `assignPublicIp=ENABLED`).

| Setting | Value |
|---|---|
| Container port | `8000` |
| Health check path | `/api/v1/health` — checks database connectivity and returns 503 when it is unreachable, so a broken task stops receiving traffic. `/` always returns 200 and checks nothing; pointing the health check there means a task with a dead database keeps serving. |
| Rollout | the workflow waits for the service to stabilise, then health-checks `https://api.goxlally.ai/api/v1/health`, and rolls back to the previous task definition if that fails |

Changing CPU, memory, desired count or networking means editing the task
definition and the workflow, not clicking in a console -- otherwise the next
deploy overwrites it.

## 3. Environment variables

Store secrets in **Secrets Manager** and reference them from the ECS task
definition rather
than pasting real values into the console — anyone with read access to the
service configuration can otherwise see them in plain text.

Values that must differ from `backend/.env.example`'s development defaults:

| Variable | Value | Why |
|---|---|---|
| `ENVIRONMENT` | `production` | `factory.py` refuses `AUTH_PROVIDER=dev` unless this is set |
| `AUTH_PROVIDER` | `supabase` | dev auth accepts any bearer as a founder id |
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` | **The database move did not change the identity provider.** Supabase Auth and Supabase Postgres are separate services; the app reads RDS and still verifies logins against Supabase. This is the setting that matters: user tokens are ES256 and are verified against the JWKS at `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`. |
| `SUPABASE_JWT_SECRET` | Supabase → Settings → API → JWT Secret | The LEGACY shared HS256 secret, kept as a fallback. A project on asymmetric signing never uses it for logins — verifying the anon key against it proves the secret is right and proves nothing about user tokens. |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` | signs this app's own tokens |
| `DATABASE_URL` | the RDS endpoint, `postgresql+psycopg://...@<rds-endpoint>:5432/<db>` | **Not a Supabase pooler URI.** 5432 is correct here and nothing rewrites it — the 6543 move in `app/db/session.py` fires only for `*.pooler.supabase.com`. Held in Secrets Manager; the migration task uses a separate, more privileged entry. |
| `CORS_ORIGINS` | `https://goxlally.ai,https://www.goxlally.ai` | belt-and-suspenders: the Vercel rewrite keeps normal browser traffic same-origin so this shouldn't matter day to day, but anything that calls the API directly (not through the rewrite) needs these two allowed |
| `ANTHROPIC_API_KEY` | | diagnosis reasoning + the founder's first impression |
| `OPENAI_API_KEY` | | chat + voice transcription |
| `SENTRY_DSN` | Sentry → Settings → Client Keys (DSN) | `app/main.py` only initializes Sentry `if settings.SENTRY_DSN` — leaving this unset means production error tracking is silently off with no other signal. Required for beta, not optional. |
| `PLAN_ENFORCEMENT_ENABLED` | `true` (now the code default too, as of 2026-08-16 — this row is a "don't override it to false" reminder, not an action item) | with it off, chat LLM usage is unbounded per user — see cost-controls note below |
| `ADAPTIVE_QUESTIONS` | `true` | **This table previously omitted this row and the one below, and that omission was the bug.** These two flags are coupled: `ADAPTIVE_QUESTIONS=true` is the only thing that writes `answers.score_label`, and `ANSWER_CLASSIFIER=llm` is the only thing that derives a band at report time. Set to `false` alongside `ANSWER_CLASSIFIER=stored` — which is what `.env.example` used to ship — and *every answer reaches the reasoning pipeline unscored*, every one is skipped, and each diagnosis produces a report with no root causes in it. Silently: 200 response, no error, a founder reading an empty report after thirty questions. |
| `ANSWER_CLASSIFIER` | `stored` | Keep it `stored` **with `ADAPTIVE_QUESTIONS=true`** — the advisor already scored each answer at submit time and the pipeline reuses the label. Setting this to `llm` as well is not broken, just wasteful: it re-derives all 30 labels from scratch, which measured as 161s of a 203s pipeline. |
| `GOTENBERG_URL` | the private URL of the Gotenberg service (see §3a) | Report PDFs are rendered by a **separate** Gotenberg container. Leave this at its `http://localhost:3000` default and nothing is listening there, so every export silently falls back to a plain reportlab PDF — 200 OK, a real file, and none of the founder's report design. See §3a; this is the single most invisible misconfiguration in this table. |

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

## 3a. Gotenberg (report PDFs)

`POST /reports/{id}/export` renders the founder's clarity report twice over:

```
print HTML (app/api/v1/reports/print_html.py) -> Gotenberg (headless Chromium) -> PDF
        |
        +-- GotenbergError -> reportlab (app/api/v1/reports/pdf.py)
```

The first path is the one that matches what the founder saw on screen: the
forest palette, the band cards, the embedded Montserrat/Inter/Fraunces, five
pages. The fallback is a plain two-page text document. Both return `200` with
`Content-Type: application/pdf`, so **a misconfigured deploy does not look
broken** -- it just quietly ships the wrong document to every founder who
downloads their report.

The response carries `X-PDF-Renderer: gotenberg | reportlab-fallback` precisely
so this is checkable. Check it.

### On ECS it CAN be a sidecar — which App Runner could not

This section used to say "App Runner is one image per service, so Gotenberg has
to be somewhere else". On **ECS that restriction is gone**: a task definition
holds multiple containers, they share a network namespace, and a sidecar is
reachable at `localhost` — which is exactly what `GOTENBERG_URL` already
defaults to.

`backend/Dockerfile` deliberately does not ship Chromium (it would roughly
triple the image and put a browser inside the API's blast radius), so Gotenberg
stays a separate container either way. The question is only where it runs.

1. **A sidecar in the same task definition** (preferred now). Add a second
   container from `gotenberg/gotenberg:8` on port `3000` and set
   `GOTENBERG_URL=http://localhost:3000`, which is the default — so the
   setting that is most often wrong becomes the setting you do not touch. It
   is not publicly reachable, it scales with the API, and it cannot drift out
   of sync with it.
2. **A separate service behind a private load balancer**, if you would rather
   scale or restart it independently.

Either way it must **not** be publicly reachable: Gotenberg converts arbitrary
HTML that is POSTed to it, so an open instance is a free rendering service and
an SSRF surface. A sidecar is private by construction; a standalone service
needs an ingress rule admitting only the API's security group.

| Image | `gotenberg/gotenberg:8` |
| Port | `3000` |
| CPU / Memory | 1 vCPU / **2 GB** |
| Health check path | `/health` |

The memory line is not padding. Gotenberg runs headless Chromium per request;
under 1 GB it starts failing conversions under any concurrency, and every one of
those failures lands as a silent fallback rather than an error.

### Confirming it actually works

Once both services are up, export a real report and read the header -- the
status code tells you nothing:

```bash
curl -sD - -o /dev/null -X POST   https://api.goxlally.ai/api/v1/reports/<id>/export   -H "Authorization: Bearer <token>" | grep -i x-pdf-renderer
```

`x-pdf-renderer: gotenberg` is correct. `reportlab-fallback` means founders are
getting the plain document.

### Alert on it

Add a CloudWatch metric filter for `reportlab-fallback` and alarm on it. Nothing
else in the system reports this: the founder gets a file, the request succeeds,
Sentry sees nothing. The only other symptom is a founder mentioning their report
"looks like a text file", which is not a monitoring strategy.

## 4. Vercel

Already done and committed. `frontend/vercel.json` rewrites
`/api/:path*` to `https://api.goxlally.ai/api/:path*`, so the browser only ever
talks to `www.goxlally.ai` and the calls are same-origin. The older instruction
here — replace `REPLACE-ME.awsapprunner.com` with the service's default domain —
describes a placeholder that no longer exists in the file.

What still needs checking after a domain or load-balancer change: that both
rewrite destinations in `vercel.json` still resolve, including the
share-token one (`/r/:token` → the public report view), which is the route
people outside the product hit.

## 5. The API domain

`api.goxlally.ai` is live and is where the ECS service is reached; TLS
terminates in front of the task, not in it — which is why the container runs
uvicorn with `--proxy-headers`, and why a trailing-slash redirect once came
back pointing at `http://origin-api.goxlally.ai` (the Dockerfile records that
incident).

The old text here told you to add a custom domain through the App Runner
console. That is not how this is wired, and nobody should follow it. **Whoever
set up the current DNS and certificate should write the real arrangement
down here** — which record points where, where the certificate lives, and what
has to change if the service moves.

## Before you call it done

- [ ] The **migration task** ran and succeeded in this deploy's workflow run.
      It is a separate one-off ECS task, not something a starting container
      does — a green service does not mean the migrations applied
- [ ] `backend-deploy-preflight.yml` passed its read-only Alembic state check
- [ ] `DATABASE_URL` is the **RDS endpoint on 5432**. Any 6543 pooler URI here
      is left over from Supabase and points at the wrong database
- [ ] `GET https://api.goxlally.ai/` returns `{"status": "running", ...}`
- [ ] `GET https://api.goxlally.ai/api/v1/health` returns
      `{"status": "healthy", "database": "connected"}` — 503 + `"degraded"`
      when the database is unreachable. Confirm the load balancer's health
      check points here and not at `/`, which checks nothing
- [ ] `SENTRY_DSN` is set and a manually-triggered test error reaches Sentry
- [ ] A report export returns `X-PDF-Renderer: gotenberg`, **not**
      `reportlab-fallback` (see §3a — the fallback is a 200 with a real PDF
      attached, so a successful download does not confirm this)
- [ ] The Gotenberg service is not reachable from the public internet
- [ ] `frontend/vercel.json`'s rewrite destination matches `api.goxlally.ai`,
      committed and pushed
- [ ] Full journey works end to end through `www.goxlally.ai`: sign in →
      onboarding → diagnosis → report → tour → dashboard
- [ ] `select count(*) from pg_stat_activity` is comfortably under the
      instance's `max_connections` with all tasks running. The old
      `EMAXCONNSESSION` check on this list was a Supabase pooler error and
      cannot occur on RDS — this is its replacement
- [ ] RDS automated backups are on, with a retention window someone has
      actually chosen. `data/reference/` can rebuild the product's content;
      nothing but backups can rebuild a founder's answers

## Rebuilding the database from nothing

`docs/RESTORE.md`. Tested end to end: empty Postgres, five steps, every
reference table back at production's row count and the reasoning engine
booting on the result.

Two things it depends on staying true:

* `data/reference/` is a snapshot, not a live mirror. Re-run
  `python -m scripts.dump_reference_data --database-url "$DATABASE_URL" --write`
  whenever the question bank, root causes, weights or scoring rules change,
  and commit the diff. `--check` exits non-zero when the committed dump and
  the database disagree, which is a cheap thing for CI to run.
* The snapshot was generated from the Supabase copy. If Supabase and RDS ever
  diverge, `--check` against RDS is what will say so.
