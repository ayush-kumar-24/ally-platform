# Ally Backend — Progress & Handoff

Living status doc so any new session (or teammate) can pick up instantly.
Read this + `README.md` + the persisted memory (`ally-backend-decisions.md`).

Stack: FastAPI + SQLAlchemy on Supabase Postgres. Run/test commands are in README.
Full test suite: **84 passing** (`pytest`) + `scripts/smoke_test.py`.

---

## ✅ Done (built + tested)

- **Auth** — pluggable providers (dev/supabase), backend-issued session tokens
  (issue/refresh-rotate/validate/logout), `/auth/session|resume|refresh|logout|me|status`,
  auto-provision founder on first real login.
- **Data layer** — Alembic (guarded, adopts existing schema), all 56 models
  (`app/models/schema.py` + `partitioned.py`), zero-drift verified. Repository layer.
- **Profile** — `/profile` (+ `/founder /business /goals`), `/progress`, `/validate`,
  `/context` (founder memory). Mapped to the 13 onboarding questions.
- **Discovery calls** — `/discovery/slots|book|calls` — **live Google Calendar** +
  email confirmation + 24h/1h reminders.
- **Settings** — `/settings` (+ `/account /notifications /security`).
- **Notifications feed** — `/notifications` (+ `/{id}/read`, `/read-all`).
- **Knowledge graph** — `/knowledge/problems|problems/{id}|root-causes/{id}` (traversal over seeded graph).
- **Retrieval (#5)** — pgvector cosine search helper + benchmark + ef_search sweep + `docs/retrieval_benchmark.md`.
- **Email** — SMTP service + stub fallback (`app/services/email.py`, `discovery_notifications.py`).

## Migrations applied to the live DB
- `5cbf7c8fea1e` — empty baseline (adopt existing schema)
- `b960b83ab79e` — onboarding fixes: stage→stage_id, `consents.updated_at`, `emotional_state`→jsonb multi-select
- `055fcff2b6b5` — RLS on 36 partition children + `alembic_version` + auto-RLS for future partitions

## Integrations status
- **Google Calendar**: LIVE (personal Gmail 14aarush9@gmail.com; service-account key file, git-ignored).
  Personal-Gmail limits → auto-Meet + attendee invites OFF; uses static `GOXL_MEETING_URL`.
  Workspace later = flip `GOOGLE_CALENDAR_CREATE_MEET` + `GOOGLE_CALENDAR_INVITE_ATTENDEES` to true, no code change.
- **Email**: SMTP configured (Gmail); works. Reminder job (`send_due_reminders`) needs a scheduler (deployment infra).
- **Vectors**: pgvector (NOT Qdrant — PRD says Qdrant; implementation diverged, treated as intentional).

---

## ❌ Not built — the big one: the DIAGNOSIS ENGINE

This is the core AI product and the main remaining work. A teammate is building it
(model = **Gemini Pro** per PRD). It unblocks all of these, which are schema-ready but logic-absent:
- **#3 Confidence scoring** — compute `sessions.overall_confidence_score` (0-100) → routing. See below.
- **#6 Business stage detection** — from diagnosis data (also needs the self-reported-vs-detect decision).
- **#5 retrieval end-to-end** — text→query-vector needs the embedding model.
- **Founder 7D dimension scoring** — rubrics COMPLETE; engine applies them → `founder_dimension_profile`.
- **Business Health scoring** — catalog is `readiness_pillars` (6 pillars, COMPLETE: weights sum to 100, score_bands, stage_behaviour, red_flag_threshold). Health score = weighted sum. Engine computes per-founder scores → needs a per-founder storage table (no equivalent of `founder_dimension_profile` exists for pillars yet). NOTE: the empty `business_dimensions` table is NOT the model — it appears vestigial/superseded by `readiness_pillars`.
- **Reports, chat AI replies, founder intelligence (#13), founder memory smart-update (#12)**.

### Confidence scoring — current state (IMPORTANT)
- Routing bands ARE live in `scoring_rules` (rows 19-22): Continue <60, Validate 60-80, Generate Report ≥80.
- Question scoring (0/1/2), category threshold 0.30, confirmation multipliers (1.5/1.0/0.5),
  root-cause ranking weights (0.40/0.25/0.20/0.15), distress rules (8/9/10/16) — all in `scoring_rules`.
- MISSING: the formula that COMPUTES the 0-100 score. "PRD Section 04 — Confidence Scoring Model"
  is cited by rows 19-22 but the doc with the formula is NOT found (the main PRD only has the bands).
- A **proposed 4-input formula** exists (evidence 0.35 + confirmation 0.25 + coverage 0.25 + separation 0.15,
  normalized 0-1 ×100, with distress pre-empt override + minimum-question floor + multi-category cross-check).
  **Provisional — needs Viraj sign-off.** Teammate can build it now reading weights from `scoring_rules`.

### Blocking decisions the PRODUCT side owes the engine teammate
1. **Viraj signs off** the confidence-formula weights.
2. **Define "core questions expected per stage"** + the minimum-question floor
   (`questions` has `question_type`, `priority`, `primary_stage_group` [3 groups; 208 NULL] — rule undefined).
3. Put the confirmed values into `scoring_rules` as rows (not hardcoded).
4. Locate or replace "PRD Section 04" as the written source of truth.

---

## Other engine-INDEPENDENT modules not yet built (buildable anytime)
Billing/Subscriptions · Plan Your Day (daily_actions) · Token usage/quota · Chat persistence
(conversations/messages storage, not AI) · Dashboard plumbing.

## Business Health model = `readiness_pillars` (CONFIRMED 2026-07-23)
- 6 pillars, weights sum to exactly 100: Founder Readiness 25, Market Clarity 20, Revenue Maturity 20,
  Product & Execution 15, Team & Leadership 10, Strategic Clarity 10.
- Each pillar seeded with score_bands, stage_behaviour, what_falls_under (8 sub-areas), red_flag_threshold.
- Business Health Score = weighted sum of the 6 pillar scores (each 0-100). Formula already defined — nothing to invent.
- The empty `business_dimensions` table is NOT this model — appears vestigial/superseded; team to confirm drop.
- OPEN: no per-founder pillar-score storage table yet (analogous to `founder_dimension_profile`).

## Data / content gaps (product to fill)
- `visual_question_bank` = empty.
- Two missing formulas for the engine: (1) overall_confidence_score computation ("PRD Section 04", not found);
  (2) Psychological State Scoring Table / Doc 10 (produces the session distress score for the =36 threshold).
  A teammate is chasing the source docs (PRD Section 04, Doc 10, Doc 7).

## Seeded & verified
330 questions, 807 root_causes, 3,920 root_cause_weights, 97 interventions, 124 problems,
13 founder_dimensions (7 categorical scored, rubrics COMPLETE), 8 founder_stages, 22 scoring_rules.

---

## Guardrails (do not break)
- **Never modify** `app/db/session.py`, `app/core/auth/base.py`, `app/core/auth/dev_provider.py` without asking.
- **Alembic owns all DDL.** Don't change schema via the Supabase SQL editor.
- **Don't change the DB (rows/schema) without the user's OK.** Test via rolled-back transactions.
- Secrets: `.env` + the service-account key are git-ignored. DB password + SECRET_KEY were rotated after a leak.
- Console is cp1252 — run Python with `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1` for emoji/`→`.

## To test manually with real data
Recreate a dev test founder mapped to the dev identity (uuid 000...0001) so dev-mode auth resolves to it,
then hit `/docs`. (Was created + cleaned up before; ask and it can be recreated in seconds.)
