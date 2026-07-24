# Ally Platform

**Ally** is an AI co-founder coach. Where most tools diagnose a *business*, Ally
diagnoses the **founder** first, then the business, then finds the root cause
sitting at their intersection — the Founder DNA Platform.

A guided flow walks a founder through:

1. **Founder DNA** — decision patterns, working style, blind spots
2. **Business DNA** — scored across 6 dimensions (Revenue & Growth, Product &
   Strategy, Team & Culture, Operations & Execution, Fundraising & Finance,
   Market & Positioning)
3. **Root Cause** — where founder-level patterns and business metrics intersect
4. **Clarity Report** — a scored diagnosis with a single Clarity Score
5. **Action Plan** — concrete next steps, plus optional 1:1 coaching calls

After onboarding, the founder lands in an ongoing dashboard: chat with Ally,
track a Clarity Score over time, review AI-detected patterns/insights, manage
daily goals, and book discovery calls with a human coach. Plans range from
Free to Max, gated by diagnosis volume, team seats, and coaching access.

Stack: FastAPI + SQLAlchemy on Supabase Postgres (backend), Vite + React 19 +
Tailwind (frontend).

## Structure

```
backend/    FastAPI + SQLAlchemy + Alembic API — see backend/README.md
frontend/   Vite + React 19 + Tailwind + react-router — see frontend/README.md
```

## Quick start

Backend:

```bash
cd backend
cp .env.example .env          # fill in DATABASE_URL and SECRET_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

See [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for details on auth, database migrations, and project layout.
