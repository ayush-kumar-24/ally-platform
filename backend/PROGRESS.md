# Ally Backend — Progress & Handoff

Living status doc so a new session (or teammate) can pick up quickly.
Read this + `README.md`.

Stack: FastAPI + SQLAlchemy on Postgres (Supabase in development, AWS RDS in
production). Run and test commands are in the README.

**Last verified against the code: 2026-09-07.** If you are reading this much
later, trust the code over this file — and please correct it.

---

## Where the product actually is

Ally is **live in production** at `app.goxlally.ai`, with real founders using it.
This is not a project waiting on a core piece to be built; it is a shipped
product being hardened.

> ⚠️ Everything below this line in the previous version of this file was wrong.
> It described the diagnosis engine as unbuilt and "the main remaining work",
> listed billing, Plan Your Day, token metering, chat persistence and dashboard
> as not started, said the model was Gemini Pro, and put the test suite at 84.
> All of those had been true months earlier. A new engineer onboarding off that
> file would have started rebuilding things that already existed.

## Built and in production

**Diagnosis engine** — built, and it is the core of the product. Adaptive
question selection, answer interpretation, confidence scoring and routing
(continue / validate / generate report), distress detection, root-cause
detection, and report generation for both screen and PDF.

Model routing lives in the **`model_task_routing` table**, not in code — seven
tasks, all currently pointed at `claude-sonnet-5` on Anthropic. Changing which
model serves a task is a database update, not a deploy.

**Auth** — email + one-time code + password via Supabase; backend-issued session
tokens with single-use rotating refresh; new-device sign-in alerts.

**Founder-facing** — profile, Founder DNA, Business DNA, Vision, Goals, Plan
Your Day, Next Steps, Recommendations, Frameworks, Achievements, Journey, Ally
Chat, Report, Discovery calls, Billing, Privacy Center, Help & Support.

**Commercial** — plans and entitlements, subscriptions, Razorpay payments and
webhooks, credits with expiry, coupons, daily token metering (resets at midnight
`USAGE_RESET_TIMEZONE`, default Asia/Kolkata — no cron needed, the counter is
keyed by date).

**Team-facing** — admin panel: users, usage, discovery calls, the privacy
request queue, feedback and unanswered help-bot questions, coupons, audit log,
system health.

**Notifications** — in-app bell, 48 types, each switchable from the
`notification_types` table without a deploy.

**Support bot** — answers from `support_bot_answers` (~277 published answers,
edited in the database so the team can correct one without shipping code).
Questions it cannot answer land in `support_bot_misses`.

**Data layer** — 90 Alembic revisions, 56 logical tables + 36 monthly
partitions, repository layer, RLS on every founder-scoped table.

**Tests** — ~2,100 across 154 files.

---

## Business Health model = `readiness_pillars`

Six pillars, weights summing to 100: Founder Readiness 25, Market Clarity 20,
Revenue Maturity 20, Product & Execution 15, Team & Leadership 10, Strategic
Clarity 10. Each seeded with score bands, stage behaviour, sub-areas and a
red-flag threshold. Health score is the weighted sum.

The empty `business_dimensions` table is **not** the model — it is vestigial,
superseded by `readiness_pillars`.

---

## Open work

### Should be done next
- **Six handlers still block the event loop** — `diagnosis/router.py`,
  `founder_dna/router.py`, `impression/router.py` and `service.py`,
  `incremental_confidence.py`. Their blocking calls are interleaved with LLM
  awaits inside async service methods, so fixing them means restructuring the
  service layer rather than the one-word change the other 53 needed. Not on the
  page-load path, but they still stall the server in bursts. See rule 1 in the
  README.
- **Two jobs need scheduling in AWS** — `app.jobs.discovery_reminders`
  (**hourly**; the window is "within the next hour", so a daily run misses
  nearly every call) and `app.jobs.notification_sweep` (every few hours).
- **Public status page (PRD-09)** — does not exist. Today every "what if
  something breaks" answer ends in "write to us", which turns one outage into a
  hundred separate support conversations.

### Watch
- **Email is on a single Resend account, free tier** — 100/day shared between
  Supabase login codes and product notifications. Running out means **founders
  cannot sign in**. Check Resend → Metrics weekly; upgrade before ~60/day.
- **Report shares** — the URL-building bug (links pointed at the marketing site)
  is fixed. Whether rows persist correctly in production was never conclusively
  answered; an earlier "0 rows" reading may itself have been RLS hiding rows
  from a non-admin connection.

---

## How to change things safely

- **Schema:** Alembic owns every DDL change, no exceptions. See the boxed rule
  in the README.
- **Which model serves a task:** update `model_task_routing`. No deploy.
- **A help answer:** update `support_bot_answers`. No deploy.
- **Silence a notification type:** `UPDATE notification_types SET is_active =
  false WHERE type = '...'`. No deploy.
- **Anything touching the database in a request handler:** read the three rules
  in the README first. Each one has already caused a production incident.
