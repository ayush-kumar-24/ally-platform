# Deploying Ally

Frontend on Vercel, backend on a persistent host. **In that order — the frontend
is useless until the backend has a URL.**

## Why not both on Vercel

The API holds a SQLAlchemy connection pool against Supabase's pooler, which
allows 15 client connections in session mode. Vercel is serverless: every cold
start opens a fresh pool, so concurrent invocations exhaust it and the pooler
starts answering `(EMAXCONNSESSION) max clients reached`. That failure has
already happened once in development with only two processes running.

Use a persistent container for the API, never a serverless one.

---

## 1. Backend first

**Deployed via AWS App Runner** — see `backend/DEPLOY_AWS.md` for the full
walkthrough (Dockerfile, ECR, env vars, the Supabase pooler-mode change that
matters once real traffic arrives). Railway, Render and Fly also work from
this repo's `requirements.txt` + `backend/Dockerfile`, if App Runner ever
stops being the right fit.

Once it's live, confirm: `GET https://<backend>/` returns
`{"status": "running", ...}`, and that the migrations have run against the
production database.

**Migrations do NOT run automatically. You have to run them.** The Dockerfile's
`CMD` does start with `alembic upgrade head`, but the ECS task definition sets
an explicit `command`:

```
Dockerfile CMD:   sh -c "alembic upgrade head && uvicorn app.main:app ..."
task definition:  uvicorn app.main:app --host 0.0.0.0 --port 8000
```

A task definition `command` REPLACES the image's `CMD`, so the migration step is
dropped. This file previously claimed the opposite, which is the kind of wrong
that stays invisible until a deploy "ships" a migration, the schema silently
does not change, and the failures arrive later as missing-column errors nobody
connects back to the deploy.

Run them as a one-off task instead, which is the safer pattern anyway — the
service runs two tasks, and restoring the migration to their startup command
would have both racing the same `alembic upgrade head` on every deploy:

```bash
aws ecs run-task --region ap-south-1 \
  --cluster ally-backend-cluster --task-definition ally_backend_task:<rev> \
  --launch-type FARGATE --count 1 \
  --network-configuration "awsvpcConfiguration={subnets=[<subnet-a>,<subnet-b>],securityGroups=[<sg>],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides":[{"name":"Main","command":["alembic","upgrade","head"]}]}'
```

It reuses the service's own image and secrets, so it reaches RDS with the same
`DATABASE_URL` and needs no credentials of your own. Read the result from
CloudWatch (`/ecs/ally-backend-task`, stream `ecs/Main/<task-id>`) and check the
container's `exitCode` is 0 before updating the service.

The same mechanism runs any other one-off against production —
`scripts/reset_diagnosis_data.py`, for instance. RDS is not reachable from
outside the VPC (private address, 5432 closed), and this needs no bastion, no
VPN and no session-manager-plugin.

## 2. Frontend on Vercel

1. **Import the repo** in Vercel → New Project.
2. Set **Root Directory** to `frontend`. Everything else is read from
   `frontend/vercel.json`.
3. Edit `frontend/vercel.json` and replace `REPLACE-ME.awsapprunner.com` with
   the backend's actual App Runner domain from step 1.
4. Add environment variables (Project → Settings → Environment Variables):

| Variable | Value |
|---|---|
| `VITE_SUPABASE_URL` | Supabase → Settings → API → Project URL |
| `VITE_SUPABASE_ANON_KEY` | same page, anon/public key |

**Do not set `VITE_API_BASE_URL`.** Leaving it unset keeps
`services/api.js` on its relative `/api/v1` default, which the rewrite in
`vercel.json` proxies to the backend. That keeps the browser same-origin, so no
CORS entry is needed and no third-party-cookie rules apply.

**Do not set `VITE_DEV_FOUNDER_TOKEN`.** It exists so local development can mint
a session without Supabase. In production it would be a way to sign in as an
arbitrary founder by id.

5. Add the Vercel domain as a redirect URL in Supabase → Authentication →
   URL Configuration: `https://<your-domain>/guided/login`. Without it Google
   sign-in returns to a URL Supabase refuses.

## What the rewrite does

`vercel.json` has two rewrites, and the order matters:

1. `/api/:path*` → the backend. Same-origin API calls, no CORS.
2. `/((?!.*\..*).*)` → `/index.html`. The SPA catch-all. Without it every deep
   link 404s on refresh — react-router owns `/app/report`, but Vercel looks for
   a file there and finds none. The negative lookahead leaves anything
   containing a dot alone so real assets still resolve.

The cost of routing API traffic through Vercel is one extra network hop and the
bandwidth counting against your Vercel plan. The alternative is pointing
`VITE_API_BASE_URL` at the backend directly and adding the Vercel domain to
`CORS_ORIGINS` — fewer hops, more moving parts.

## The existing S3 workflow

`.github/workflows/deploy-frontend.yml` pushes `frontend/dist` to S3 on every
push to `main`. It passes only `NODE_ENV`, so its builds have no Supabase keys
and no API URL — a site that loads and does nothing. Once Vercel is live,
delete that workflow or it will keep publishing a broken copy alongside.

It also gates on nothing but a successful build. If you keep any CI, add:

```yaml
      - run: npm ci && npm run lint
        working-directory: frontend
```

Several bugs found in development built cleanly and failed at runtime — a
missing import, buttons with no handler. `no-undef` is enabled in
`.oxlintrc.json` and catches the first class.

## Report PDFs need a second container

The report PDF is rendered by **Gotenberg** (headless Chromium), which renders
the exact HTML document the founder reads on screen. That is the whole reason
the PDF matches the page — there is one builder, not two.

Gotenberg is **not optional and not bundled**. Without it, every
`POST /reports/{id}/export` returns 503 with "still being prepared…" *forever*,
because nothing will ever render it. The message is written for a momentary
outage; a permanently missing sidecar makes it a lie.

Add it as a **second container in the same ECS task definition** as the backend:

| | |
|---|---|
| Image | `gotenberg/gotenberg:8` |
| Container port | `3000` |
| Backend env `GOTENBERG_URL` | `http://localhost:3000` |
| Task memory | **+1 GB** over the backend's own (Chromium) |

`localhost` is correct because containers in one Fargate task share a network
namespace. Do NOT put Gotenberg behind a load balancer or a public route — it
converts arbitrary HTML to PDF for anyone who can reach it.

Two related settings:

- **`ATTACHMENT_S3_BUCKET`** also stores rendered PDFs. Empty means storage
  no-ops and every download re-renders (~2–4s of Chromium per click). It works,
  it is just wasteful.
- **`PUBLIC_APP_URL`** (e.g. `https://goxlally.ai`) is the origin used to build
  share links. Left empty they are built from the request's own host, which
  behind the Vercel proxy is the API domain — a working link, but not one a
  founder wants to send to an investor.

Verify after deploy: `GET /reports/{id}/document` returns HTML, then
`POST /reports/{id}/export` returns `application/pdf` with header
`X-PDF-Renderer: gotenberg`. Anything else in that header means a second
renderer has grown back.

## Before you call it done

- [ ] `GET /openapi.json` on the backend returns 200
- [ ] The Gotenberg sidecar is in the task definition, and
      `POST /reports/{id}/export` returns a real PDF (not 503)
- [ ] A share link (`/r/<token>`) opens the report for a signed-OUT browser
- [ ] `alembic upgrade head` has been RUN as a one-off task (see §1 — the task
      definition's `command` means it does not happen on its own)
- [ ] Google sign-in completes and lands on `/guided/welcome`
- [ ] A deep link (`/app/report`) survives a hard refresh
- [ ] The onboarding → diagnosis → report → tour → dashboard journey completes
- [ ] Sign out returns you to the landing page and a refresh does not restore
      the session
- [ ] 375px wide: no horizontal scroll on `/app`, `/app/report`, `/app/plan`
