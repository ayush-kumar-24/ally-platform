# Ally Backend — Progress & Handoff

Living status doc, so a new session or teammate can pick up without guessing.
Read this alongside `README.md`.

**Last rewritten: 2026-09-07.** The previous version said the diagnosis engine
was unbuilt, that billing and Plan Your Day did not exist, that the model was
Gemini Pro, and that there were 84 tests. All four were wrong by a wide margin,
and anyone onboarding from it started in the wrong place.

---

## Where things actually stand

Stack: FastAPI + SQLAlchemy on Postgres (Supabase in development, AWS RDS in
production). **2,104 tests** across 154 files. **92 migrations**, head
`f1c8d3a26b47`. Around 30 mounted API modules.

**The product is built and live at `app.goxlally.ai`.** What remains is not
construction — it is verification, scheduling, and a small number of things
that were built but never connected to anything.

## ✅ Built and in production

- **Auth** — email + 8-digit OTP + password via Supabase, backend-issued session
  tokens with single-use rotating refresh, cross-tab refresh lock.
  Auto-provisions the founder row on first sign-in.
- **Consent** — append-only, server-stamped, version-tagged ledger. Terms, an
  18-or-over confirmation, and an unbundled diagnosis opt-in that is now
  **enforced**, not merely recorded.
- **Diagnosis engine** — adaptive questioning, answer interpretation, confidence
  scoring and routing (continue / validate / generate), distress detection.
  Runs on `claude-sonnet-5` via `model_task_routing`, which is a database table:
  the model per task can be changed without a deploy.
- **Founder DNA / Current Problem / Vision** — the pre-diagnosis capture flows.
- **Reports** — generation, narrative, PDF via a Gotenberg sidecar, and public
  share links with expiry and revocation.
- **Ally chat** — conversation persistence, suggestions, attachments, voice.
- **Plans, credits, payments** — Razorpay, subscriptions, daily token allowance
  (resets at midnight IST, keyed by date — no cron), credit expiry, coupons.
- **Plan Your Day / goals / tasks** — planning module with calendar sync.
- **Knowledge graph, frameworks, achievements, intelligence reports.**
- **Privacy Center** — export, portability export, data summary, restriction,
  consent withdrawal, account erasure with a 30-day grace period, correction
  requests, email-change requests, and DPDP grievances.
- **Admin panel** — users, usage, discovery calls, privacy queue, feedback
  queue, coupons, audit log, system health. RBAC by capability, audited.
- **Support bot** — 277 published answers in `support_bot_answers`, editable in
  the database with no deploy. Model-routed retrieval with keyword fallback.
  Questions it cannot answer are recorded in `support_bot_misses`.
- **Notifications** — 48 types in a lookup table, each with an `is_active` kill
  switch. Standing conditions evaluated by 13 rules, run both on a schedule and
  whenever a founder opens the bell; one-off events written where they happen.
- **Email** — Resend SMTP. Discovery confirmation, a 1-hour reminder, new-device
  sign-in alerts.

## 🔧 Fixed on 2026-09-07 — the pattern worth knowing

Six things were found that were **built, looked finished, and did nothing**.
Every one had a working backend and no caller, or a caller that could not see
its own data. None of them failed loudly.

| What | Why it did nothing |
|---|---|
| Admin privacy queue | Backend + RBAC + audit existed; **no UI called it**. Requests sat unread for 34 days |
| Admin feedback queue | Same — support messages unread since 20 August |
| Notification bell | Table, API and frontend all present; **nothing ever wrote a row** |
| Discovery reminder job | Endpoints existed; **nothing invoked them** |
| Account erasure sweep | Ran with no RLS context — found **zero** founders, reported success daily |
| Public share links | Same cause — the row was saved, the public route could not see it |

**Two root causes, both silent:**

1. **Missing row-level-security context.** A request or job with no founder
   identity that never declared itself a system actor sees zero rows and
   concludes there is nothing there. Four separate instances. Invisible in
   development, which bypasses RLS entirely.
2. **A built backend with no caller.** The reading half shipped and the writing
   half did not, or the reverse.

**Also fixed the same day:** 53 handlers were `async def` while making blocking
database calls, so the server processed requests one at a time. Twelve
concurrent requests went from 23.4s to 4.0s.

**The lesson, written down because it kept repeating: "it is built" and
"someone watched it work" are different states.** Treat anything on a checklist
as unverified until observed in production.

## ⚠️ Open — verification, not construction

**Blocking a public launch:**

1. **No email has been proven to arrive.** Credentials authenticate; nothing has
   landed in an inbox. `verify_notifications --send-to <address>` settles it.
2. **Nobody has walked the full journey on production** with a fresh account:
   signup → diagnosis → report → share → book a call.
3. **Were founders owed a deletion?** The erasure sweep found nobody for weeks
   while reporting success. Run `/internal/jobs/process-deletions` and read
   `due_count`. If it is above zero, those people asked to be deleted, were told
   it was scheduled, and were not.

**Soon after:**

4. **The erasure job is on GitHub's scheduler**, which disables itself after 60
   days of repo inactivity. Move it to EventBridge.
5. **Resend is on the free tier** — 100 emails/day shared with login codes.
   Exhausting it stops sign-in for everyone.
6. **Six AI-pipeline handlers still block the event loop.** Not on the page-load
   path; will bite under real load. Fixing them means restructuring the service
   layer, not a one-word change.
7. **The production database region has never been verified.** We publish "your
   data is stored in India"; compute and secrets are confirmed `ap-south-1`, RDS
   is not.

## 📋 Known gaps, deliberate or awaiting a decision

- **No retention enforcement.** `founders.data_retention_expires_at` exists and
  nothing reads or writes it. No purge job. The only deletion path in the
  product is founder-initiated. The policy discloses this; it is still a
  purpose-limitation question.
- **Expired `founder_memory` rows are filtered on read, never deleted.**
- **`data_deletion_requests`** — a full OTP-confirmed deletion flow implied by
  the schema, never built. The live flow uses columns on `founders` plus
  `privacy_requests`.
- **`needs_reconsent()` is implemented and the frontend never calls it.**
  Bumping the terms version would change nothing anyone sees.
- **"7 days' notice of material changes"** is promised in the Privacy Policy
  with no mechanism behind it.
- **Restriction/withdrawal does not gate everything.** Diagnosis, Founder DNA
  and chat are gated; Current Problem and the first-impression generator are
  not.
- **`internal_intelligence_reports`** is excluded from the founder's data export
  and its existence is disclosed nowhere. It is hard-deleted on erasure, so we
  already treat it as founder data. Needs a legal decision.
- **The Terms name Bangalore courts** while the registered office is Vadodara.
- **No public status page** (PRD-09).
- **Google Workspace not purchased**, so discovery calls use a shared meeting
  room rather than a per-call Meet link.

## Where the bodies are buried

Things that will cost you an afternoon if you do not know them:

- **Development bypasses row-level security.** Anything about who-sees-what must
  be verified in production. Four bugs hid here.
- **`DATABASE_URL` on port 5432 starves the connection pool.** Use 6543.
- **`frontend/vercel.json` is load-bearing** — `/api/*` proxy, `/r/:token` share
  rewrite, SPA fallback. Deleting it takes the app down.
- **`PUBLIC_APP_URL` points at the marketing site, not the app.** Share links
  deliberately no longer read it; the calendar OAuth callback still does and is
  still wrong.
- **Two Resend accounts existed** to double a free-tier limit. Consolidated onto
  one; verifying the root domain on the wrong account would revoke the one that
  sends login codes and lock every founder out.
- **Alembic owns all DDL.** See the rule in `README.md`.
- **CI enforces a single migration head.** A branched graph stops the deploy.

## Conventions

- Domain logic lives outside `app/api/`, in its own package.
- Routes depend on repositories and services, not raw SQLAlchemy.
- Notifications are written only through `app/notifications/writer.py`.
- A handler using a synchronous `Session` is `def`, not `async def`.
- A job or public route that reads founder data calls
  `set_admin_rls_context(db)` after whatever authorises it.
- Comments explain **why**, especially where the obvious approach was tried and
  failed. Much of what is written down here was learned the expensive way.
