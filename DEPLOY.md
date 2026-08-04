# Deploying Ally

Frontend on Vercel, backend on a persistent host. **In that order — the frontend
is useless until the backend has a URL.**

## Why not both on Vercel

The API holds a SQLAlchemy connection pool against Supabase's pooler, which
allows 15 client connections in session mode. Vercel is serverless: every cold
start opens a fresh pool, so concurrent invocations exhaust it and the pooler
starts answering `(EMAXCONNSESSION) max clients reached`. That failure has
already happened once in development with only two processes running.

Use a persistent container for the API — Railway, Render and Fly all work from
this repo's `requirements.txt`.

---

## 1. Backend first

Deploy `backend/` to Railway or Render with:

```
Start command:  python scripts/run_dev.py --port $PORT --host 0.0.0.0
```

(or `uvicorn app.main:app --host 0.0.0.0 --port $PORT` — `run_dev.py` only exists
to chdir so `.env` resolves, which a hosted env-var setup makes unnecessary.)

Environment variables — see `backend/.env.example` for the full list. The ones
that must change from their development values:

| Variable | Value | Why |
|---|---|---|
| `ENVIRONMENT` | `production` | `factory.py` refuses `AUTH_PROVIDER=dev` unless this is set |
| `AUTH_PROVIDER` | `supabase` | dev auth accepts any bearer as a founder id |
| `SUPABASE_JWT_SECRET` | from Supabase → Settings → API | verifies the token the browser presents |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` | signs our own tokens |
| `DATABASE_URL` | the Supabase pooler URI | |
| `CORS_ORIGINS` | not needed if using the Vercel rewrite below | the proxy keeps the browser same-origin |
| `ANTHROPIC_API_KEY` | | diagnosis reasoning + first impression |
| `OPENAI_API_KEY` | | chat + voice transcription |

Then run the migrations against the production database:

```bash
alembic upgrade head
```

Three are outstanding as of this writing: `customer_segment` → jsonb,
`first_impression`, and `diagnosis_rating`. The code will not work without them.

Confirm it is up: `GET https://<backend>/openapi.json` should return 200.

## 2. Frontend on Vercel

1. **Import the repo** in Vercel → New Project.
2. Set **Root Directory** to `frontend`. Everything else is read from
   `frontend/vercel.json`.
3. Edit `frontend/vercel.json` and replace `REPLACE-ME.up.railway.app` with the
   backend host from step 1.
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

## Before you call it done

- [ ] `GET /openapi.json` on the backend returns 200
- [ ] `alembic upgrade head` has run against the production database
- [ ] Google sign-in completes and lands on `/guided/welcome`
- [ ] A deep link (`/app/report`) survives a hard refresh
- [ ] The onboarding → diagnosis → report → tour → dashboard journey completes
- [ ] Sign out returns you to the landing page and a refresh does not restore
      the session
- [ ] 375px wide: no horizontal scroll on `/app`, `/app/report`, `/app/plan`
