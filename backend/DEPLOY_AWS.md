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
| Health check path | `/` (already returns 200 with a status payload — no new endpoint needed) |

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

Everything else can keep its `.env.example` default.

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
- [ ] `frontend/vercel.json`'s rewrite destination matches the real App Runner
      domain, committed and pushed
- [ ] Full journey works end to end through `www.goxlally.ai`: sign in →
      onboarding → diagnosis → report → tour → dashboard
- [ ] CloudWatch Logs show no repeated `EMAXCONNSESSION` — if they do, the pool
      is still too large for the pooler mode in use
