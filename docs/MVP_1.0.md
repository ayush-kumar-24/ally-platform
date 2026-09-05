# Ally — MVP 1.0 Definition

- **Status** — Finalized scope, pending build of the launch-critical fixes in §6
- **Date** — 5 September 2026
- **Product** — Ally, the Founder DNA Platform. An AI co-founder coach that diagnoses the *founder* first, then the business, then the root cause sitting at their intersection.
- **Stack** — FastAPI + SQLAlchemy + Alembic on Supabase Postgres · Vite + React 19 + Tailwind + react-router · Backend on AWS App Runner/ECS Fargate, frontend on Vercel · Razorpay (INR) · Supabase Auth

---

## 0. Decisions locked for 1.0

| # | Decision | Choice |
|---|---|---|
| 1 | Billing model | **Auto-renewing mandate.** Razorpay Subscriptions with a real mandate, a working cancel path, and a downgrade sweep on expiry. This is what the UI already promises the founder, so it is the model we make true rather than the promise we retract. |
| 2 | Coupons | **Simple launch codes in 1.0.** Admin-created codes, percent or flat off, one redemption per founder, an expiry date. Not a full promotions engine. |
| 3 | Feature scope | **Keep everything currently built.** Nothing shipped is pulled or flag-hidden. The work is to fix what is broken and finish what is mocked. |
| 4 | Access | **Waitlist-gated launch.** Signup stays approval-only; the gate is not lifted in 1.0. |

Consequence of #3: MVP 1.0 is a *quality and correctness* release, not a feature-cut release. The surface is already wide, so the launch bar is that **every screen a founder can reach tells the truth**, and every rupee charged is charged correctly.

---

## 1. Final feature list

Legend: **Live** = built and working · **Fix** = built but has a launch-critical defect (see §6) · **Finish** = partially built, must be completed for 1.0

### 1.1 Identity & access

| Feature | Status | Notes |
|---|---|---|
| Email + emailed OTP + password sign-in (Supabase) | Live | `frontend/src/services/auth.js` |
| Backend-issued session tokens (access + rotating refresh) | Live | `POST /auth/session`, `/resume`, `/refresh`, `/logout`, `GET /auth/me`, `/auth/status` |
| Waitlist gate — unapproved emails bounced to the waitlist | Live | Client-side courtesy; the real gate is waitlist approval in Supabase |
| Founder auto-provisioning on first login | Live | Behind `ENABLE_FOUNDER_PROVISIONING` |
| Session survives reload; refresh-token rotation | Live | A refresh token works exactly once |

### 1.2 Onboarding (the guided flow)

| Feature | Status |
|---|---|
| Expectation → Welcome → Ally intro (3 tabs: Founder-First, Root-Cause Chain, Clarity Method) | Live |
| Consent capture (terms + diagnosis consent), append-only ledger | Live |
| Profile build — 4-section, path-branching questionnaire | Live |
| Stage tour, summary, validate, problem statement | Live |
| Resume a partially completed onboarding | Live |
| Hand-off to the real backend diagnosis (no scripted fake sequence) | Live |

### 1.3 The diagnosis engine — the core product

| Feature | Status | Notes |
|---|---|---|
| Phase 1 — Founder DNA journey | Live | `/app/founder-dna-journey`; `/diagnosis/start` 409s until complete |
| Phase 2 — Current Problem | Live | `/app/current-problem` |
| Phase 3 — Adaptive business diagnosis | Live | `/app/diagnosis`; server-side session, resumable |
| Adaptive question selection over the seeded bank | Live | 330 questions, 807 root causes, 3,920 root-cause weights, 97 interventions, 124 problems |
| Stage-scoped pillars — never ask a pre-launch solo founder about revenue concentration | Live | `diagnosis/stage_scope.py` |
| Per-stage question budget | Live | `founder_stages.question_budget` |
| Confidence scoring + routing bands (Continue <60 · Validate 60–80 · Report ≥80) | Live | `reasoning/engines/confidence.py` |
| Voice input inside the diagnosis | Live | All tiers |
| Reasoning engines: archetype, business health, root cause, stage detection, psychological state, distress language, symptom detection, consistency, recommendation, action plan | Live | 19 engines under `reasoning/engines/` |
| Lifetime diagnosis cap enforced per plan | Live | Only *completed* diagnoses count |

### 1.4 Outputs

| Feature | Status |
|---|---|
| Clarity Report (scored diagnosis + single Clarity Score) | Live |
| Founder DNA card — archetype and dimension profile | Live |
| Business DNA card — 6 readiness pillars (Founder Readiness 25 · Market Clarity 20 · Revenue Maturity 20 · Product & Execution 15 · Team & Leadership 10 · Strategic Clarity 10) | Live |
| Next Steps — server-generated recommendations | Live |
| Report document generation | Live |
| Honest empty states before any diagnosis exists | Live |

### 1.5 The ongoing workspace

| Feature | Status | Plan gate |
|---|---|---|
| Dashboard — greeting, health cards, plan badge, next call | Live | All |
| Ally Chat — grounded in the founder's own diagnosis, streaming, attachments + vision, suggestions, links, memory | Live | Plus+ |
| Voice in chat | Live | Plus+ |
| Plan Your Day — goals and tasks | Live | Plus+ |
| Goals | Live | Plus+ |
| Next Steps | Live | Plus+ |
| Vision | Live | Pro |
| Recommendations | Live | Pro |
| Knowledge-graph chat | Live | Pro |
| Email notifications | Live | Pro |
| Know My Energy | **Finish** | Pro — declared in the catalog, founder-facing implementation incomplete |
| Frameworks library + detail | Live | All |
| Achievements | Live | All |
| Journey timeline | Live | All |
| Notifications feed | Live | All |
| Help & Support assistant on every page | Live | All |
| Founder profile, settings, preferences | Live | All |
| Feedback capture | Live | All |

### 1.6 Discovery calls

| Feature | Status | Notes |
|---|---|---|
| Slot listing against live Google Calendar | Live | Pro sees slots from tomorrow (1-day lead); everyone else 3 days |
| Booking as a **request** the team confirms | Live | Deliberate: payment is collected offline, seam is `payment_reference` + `pending → confirmed` |
| Email confirmation + 24h / 1h reminders | **Finish** | Code works; **no scheduler runs it in production** |
| ₹300 per call once the free allowance is used | **Fix** | Every tier currently has `free_calls_per_month = 0` |

### 1.7 Money

| Feature | Status |
|---|---|
| Plan catalog — one source of truth for price, credits, ceilings, features | Live |
| Server-side entitlement checks (UI only mirrors them) | Live |
| Credit ledger, append-only, with lazy settlement (expiry + renewal without a cron) | Live |
| Daily token ceilings, metered separately per feature | Live |
| Unbilled-usage reconciliation queue | Live |
| Razorpay checkout for a paid plan | **Fix** — one-time order, not a mandate |
| Webhook-granted plans, idempotent, signature-verified | Live |
| Recurring renewal / cancel / downgrade on expiry | **Build** — §5 |
| Coupons | **Build** — §5 |
| ₹300 / 120-credit top-up | **Build** — advertised by the API, no checkout path exists |

### 1.8 Admin

Full detail in §4. Live today: RBAC (3 roles), user search and detail, credit adjustment and bulk grants, subscription patch, diagnosis/conversation resets, account suspension and deletion, privacy-request queue, feature flags, broadcasts, usage and cost metrics, founder feedback, report regeneration, conversation inspection, and an immutable audit log.

### 1.9 Trust, privacy, platform

| Feature | Status |
|---|---|
| Data export (JSON) | Live |
| Restrict processing (reversible) | Live |
| Withdraw consent | Live |
| Account deletion with 30-day scheduled erasure | Live — sweep endpoint exists, **needs a scheduler** |
| Terms of Service and Privacy Policy pages | Live |
| Error boundaries per route group | **Fix** — does not reset on navigation |
| Sentry error reporting | Live |
| Stale-chunk recovery after a deploy | Live |
| Mobile 375px verified across the main routes | Live |

---

## 2. User journey & process flow

```
                        ┌──────────────────────────┐
                        │  Waitlist (external)     │
                        │  approval granted        │
                        └────────────┬─────────────┘
                                     │
   ACQUIRE                           ▼
                        ┌──────────────────────────┐
                        │  Sign in                 │  email → OTP → password
                        │  /guided/login           │
                        └────────────┬─────────────┘
                                     │
   ORIENT                            ▼
        ┌────────────────────────────────────────────────────┐
        │  Expectation → Welcome → Consent → Ally intro      │
        │  → Profile build → Tour → Summary → Validate       │
        │  → Problem statement                               │
        └────────────────────────┬───────────────────────────┘
                                 │
   DIAGNOSE                      ▼
        ┌────────────────────────────────────────────────────┐
        │  Phase 1  Founder DNA journey    (who you are)      │
        │  Phase 2  Current Problem        (what hurts)       │
        │  Phase 3  Adaptive diagnosis     (why it hurts)     │
        │                                                     │
        │  Loop per question:                                 │
        │    stage-scope filter → rank → ask → classify       │
        │    → update confidence                              │
        │                                                     │
        │    confidence < 60   → keep gathering               │
        │    confidence 60–80  → confirm the hypothesis       │
        │    confidence ≥ 80   → generate the report          │
        │    (or question budget for the stage is exhausted)  │
        └────────────────────────┬───────────────────────────┘
                                 │
   REVEAL                        ▼
        ┌────────────────────────────────────────────────────┐
        │  Thinking → Clarity Report                          │
        │    · Clarity Score                                  │
        │    · Founder DNA (archetype + dimensions)           │
        │    · Business DNA (6 readiness pillars)             │
        │    · Root cause chain                               │
        │    · Next Steps                                     │
        └────────────────────────┬───────────────────────────┘
                                 │
   MONETISE                      ▼
        ┌────────────────────────────────────────────────────┐
        │  Free trial hits a wall  ─────────────┐             │
        │    · lifetime diagnosis cap reached   │             │
        │    · daily token ceiling (429)        ├─► Pricing   │
        │    · credit balance spent (402)       │   + coupon  │
        │    · a Pro-only surface (403)         │   → pay     │
        └───────────────────────────────────────┴─────────────┘
                                 │
   RETAIN                        ▼
        ┌────────────────────────────────────────────────────┐
        │  Dashboard · Ally Chat · Plan Your Day · Goals       │
        │  Vision · Recommendations · Frameworks · Journey     │
        │  Discovery call with a human coach                   │
        │  Clarity Score tracked over time                     │
        └────────────────────────────────────────────────────┘
```

**The monetisation logic.** Ally is deliberately not a free-forever product. The Free tier is a **one-month funded trial** — credits are granted once, never renewed, because a renewing free tier is an unbounded recurring cost per signup. The trial is sized to let a founder complete one full diagnosis, read the report it writes, and work in the product for a month. The upgrade moment is engineered: it arrives when the founder has already seen the diagnosis be right about them.

**The pricing ladder reads as three sentences:**

- **₹199 Starter** — "Buy the answer." One adaptive diagnosis and the Clarity Report it writes. Nothing else.
- **₹450 Plus** — "Buy somewhere to act on it." Adds Ally Chat, Next Steps, Goals, Plan Your Day.
- **₹999 Pro** — "Ally starts initiating." Adds Vision, Recommendations, knowledge-base reasoning, email outreach, and first pick of every call slot.

---

## 3. Step-by-step flow

### 3.1 First-run — signup to report

| # | Step | Route | Key API | What must be true |
|---|---|---|---|---|
| 1 | Land, redirected if no session | `/` | `POST /auth/resume` | No session → waitlist site. Never a white screen. |
| 2 | Enter email | `/guided/login` | Supabase `signInWithOtp` | Unapproved email → the waitlist message, not a generic failure |
| 3 | Enter emailed code, choose a password | `/guided/login` | Supabase `verifyOtp` + `updateUser` | A password Supabase rejects stops the step — never "saved" falsely |
| 4 | Exchange for a backend session | — | `POST /auth/session` | Returns `{access_token, refresh_token, founder, provisioned:true}` |
| 5 | See what Ally does | `/guided/expectation` → `/ally-intro` | — | — |
| 6 | Accept terms + diagnosis consent | `/guided/welcome` | `POST /consents` | Append-only; a double-submit does not duplicate the row |
| 7 | Build the profile | `/guided/profile` | `PATCH /profile` | 4 sections, branching by path |
| 8 | Stage tour, summary, validate | `/guided/tour`, `/summary`, `/validate` | `GET /profile`, `/progress` | Real stage label, never a fallback |
| 9 | State the problem | `/guided/problem` | — | Hands off to the real engine |
| 10 | **Phase 1 — Founder DNA** | `/app/founder-dna-journey` | `POST /diagnosis/*` | `/diagnosis/start` 409s until this completes |
| 11 | **Phase 2 — Current Problem** | `/app/current-problem` | — | Reached from Phase 1, not linked directly |
| 12 | **Phase 3 — Diagnosis** | `/app/diagnosis` | `POST /diagnosis/start`, `/answer`, `GET /current` | Resumable across reloads; server holds the session |
| 13 | Generation | `/app/thinking` | `POST /internal/jobs/reconcile-reports` as backstop | A killed container must not strand a COMPLETED session |
| 14 | Read the report | `/app/report` | `GET /intelligence/reports/latest` | 404 before any diagnosis is a legitimate empty state |
| 15 | Founder DNA / Business DNA / Next Steps | `/app/founder-dna`, `/business-dna`, `/next-steps` | `GET /reports/{id}/*` | Never a hardcoded archetype; never `[object Object]` |

### 3.2 Steady state — a returning founder

1. `/` → `POST /auth/resume` → `/app` dashboard.
2. Dashboard renders the real plan badge, real Clarity Score, real next call — never a placeholder.
3. Ally Chat answers grounded in that founder's own diagnosis; a message is metered against the daily chat ceiling and the credit balance.
4. Plan Your Day auto-creates today's plan on first visit; tasks persist server-side.
5. Hitting a ceiling produces an honest, actionable wall: **429** daily limit, **402** credits spent *or trial lapsed* (the two are distinguished by date and worded differently), **403** the feature is on a higher tier.
6. Every wall routes to `/app/billing`.

### 3.3 Upgrade — the paid path (target state, §5)

| # | Step | API |
|---|---|---|
| 1 | Open pricing, see live catalog + strike-through MRP | `GET /plans` |
| 2 | Enter a coupon code, see the discounted total | `POST /coupons/validate` |
| 3 | Start checkout | `POST /payments/checkout` → Razorpay subscription |
| 4 | Authorise the mandate in the Razorpay modal | Razorpay |
| 5 | Backend grants the plan **from the signed webhook only** | `POST /webhooks/razorpay` |
| 6 | Credits granted, entitlements widen immediately | — |
| 7 | Month 2 onward: auto-charge, credits renew, ledger row appended | `subscription.charged` |
| 8 | Cancel → access continues to period end, then downgrades to Free | `POST /payments/subscription/cancel` + expiry sweep |

### 3.4 Discovery call

1. `GET /discovery/slots?days=7` — Pro sees from tomorrow, others from day 3.
2. `POST /discovery/book` creates a **pending request**.
3. Team confirms; the row moves `pending → confirmed`; Google Calendar event created; confirmation email sent.
4. Reminders fire at 24h and 1h **(requires the scheduler in §6)**.
5. Payment beyond the free allowance is collected offline against `payment_reference`.

---

## 4. Admin requirements

### 4.1 Roles

Three roles, server-enforced, capability-counted: **super_admin (13) · admin (6) · support (3)**. Everything below is checked server-side; the panel only mirrors it.

### 4.2 Capabilities — live today

| Area | Capability | super_admin | admin | support |
|---|---|:--:|:--:|:--:|
| Users | Search / list (name, email, phone, business, ID), paginate, sort | ✅ | ✅ | ✅ |
| Users | Founder detail — profile, credits, timeline | ✅ | ✅ | ✅ |
| Users | Edit founder record | ✅ | ✅ | ❌ |
| Users | Suspend / restore account status | ✅ | ✅ | ❌ |
| Users | Reset diagnosis · reset conversations | ✅ | ✅ | ❌ |
| Users | Delete account · cancel a scheduled deletion | ✅ | ❌ | ❌ |
| Money | View credit ledger | ✅ | ✅ | ✅ |
| Money | Adjust credits | ✅ | ❌ | ❌ |
| Money | Bulk credit grant | ✅ | ❌ | ❌ |
| Money | Patch a subscription | ✅ | ❌ | ❌ |
| Support | Inspect a founder's conversations | ✅ | ✅ | ❌ |
| Support | Regenerate a report | ✅ | ✅ | ❌ |
| Support | Founder feedback + stats | ✅ | ✅ | ✅ |
| Privacy | Privacy-request queue, mark handled | ✅ | ✅ | ❌ |
| System | Feature flags — global and per-founder | ✅ | ❌ | ❌ |
| System | Broadcasts — create, list, delete | ✅ | ❌ | ❌ |
| System | Usage + estimated cost, system-wide and per-founder | ✅ | ✅ | ❌ |
| System | Reconcile unbilled usage | ✅ | ❌ | ❌ |
| System | Health report | ✅ | ✅ | ✅ |
| Audit | Immutable audit log, newest first | ✅ | ✅ | ✅ |

Every write above appends an audit row. The audit log is append-only and cannot be edited from the panel.

### 4.3 Admin requirements **added** for MVP 1.0

| Requirement | Why |
|---|---|
| **Coupon CRUD** — create, list, disable; type (percent / flat), value, expiry, max redemptions, per-founder limit | Launch promos and partner codes are run by the team, not by a deploy |
| **Coupon redemption report** — who redeemed what, discount given, revenue impact | A code with no reporting is a discount you cannot measure |
| **Subscription view** — mandate state, next charge date, last charge, failures | Support cannot answer "why was I charged" without it |
| **Cancel / refund a subscription from the panel** | Today the only cancel path is Razorpay's own dashboard |
| **Failed-payment queue** — subscriptions in `halted` or retrying | A silent dunning failure is churn nobody saw |
| **Waitlist approval view** (read-only is acceptable for 1.0) | Approval currently happens outside the product |

### 4.4 Operational requirements

| Requirement | Status |
|---|---|
| Scheduler (EventBridge / pg_cron) calling the internal job endpoints | **Missing — blocking** |
| Migration runbook — migrations do **not** run on deploy; the ECS task definition's `command` replaces the image `CMD` | Documented in `DEPLOY.md`, must be in the release checklist |
| Monthly partition creation | Endpoint exists, unscheduled |
| Sentry alerting on `ally.usage.reconciliation` | Logger namespace exists for exactly this |

---

## 5. Subscription & coupon flow

### 5.1 Where we are

A founder pays through `POST /payments/checkout`, which creates a **one-time Razorpay order**. On `payment.captured`, the signed webhook grants the plan, writes a `subscriptions` row with `expires_at = now + 30 days`, and grants the month's credits. The grant is idempotent and never trusts the browser redirect — that part is right and stays.

**What is wrong:** nothing ever reads `expires_at` back. There is no mandate, no second charge, and no downgrade. A founder who pays ₹999 once holds Pro permanently. Meanwhile the Billing page tells them their subscription renews on a hardcoded date and offers a Cancel button that closes a modal and does nothing.

### 5.2 Target subscription flow

```
  Founder picks a tier
          │
          ▼
  POST /payments/checkout  ──► Razorpay Subscriptions API
          │                    create subscription (plan_id, customer, notes)
          ▼
  Razorpay modal — founder authorises the MANDATE
          │
          ▼
  POST /webhooks/razorpay   (signed, idempotent, the ONLY granting path)
          │
          ├─ subscription.activated ─► grant plan · grant credits · set current_period_end
          ├─ subscription.charged   ─► extend period · renew credits · append ledger row
          ├─ payment.failed         ─► mark retrying · notify founder · admin queue
          ├─ subscription.halted    ─► dunning exhausted → downgrade to Free
          └─ subscription.cancelled ─► mark cancel_at_period_end
          │
          ▼
  Nightly sweep  POST /internal/jobs/expire-subscriptions
          │
          └─ every subscription past current_period_end and not renewed
             ─► founders.plan_type = 'free' · entitlements narrow · founder emailed
```

**Rules that must hold:**

1. A plan is granted **only** from a signature-verified webhook. Never from a redirect, never from a client call.
2. Every webhook handler is idempotent — Razorpay retries anything that is not a 2xx, and a double grant is a double month.
3. Cancellation is **at period end**, never immediate. The founder paid for the month.
4. Downgrade narrows entitlements but **never deletes data**. A founder who returns finds their reports, goals and history intact.
5. Credits expire before they renew at a period boundary — an unused allowance must not roll over.
6. A credit-grant failure must not roll back a plan grant already committed; it is logged loudly and reconciled.

### 5.3 Coupon flow — launch codes

**Model.** A coupon is: a code, a type (`percent` or `flat`), a value, an optional tier restriction, an expiry date, a maximum total redemption count, and a one-redemption-per-founder rule. Redemptions are recorded in their own append-only table.

```
  Founder enters a code on the pricing page
          │
          ▼
  POST /coupons/validate  { code, tier }
          │
          ├─ unknown code            ─► 404  "That code isn't valid."
          ├─ expired                 ─► 410  "That code has expired."
          ├─ redemption cap reached  ─► 409  "That code has been fully claimed."
          ├─ already used by this founder ─► 409 "You've already used this code."
          ├─ wrong tier              ─► 422  "That code doesn't apply to this plan."
          └─ valid ─► { discount_inr, final_inr, label }
          │
          ▼
  POST /payments/checkout  { tier, coupon_code }
          │
          ▼
  Server RE-VALIDATES the coupon and recomputes the price.
  The browser's number is never trusted.
          │
          ▼
  Razorpay subscription created with the discounted amount
          │
          ▼
  On subscription.activated: redemption row written, atomically with the grant
```

**Rules that must hold:**

1. The discount is computed **server-side at checkout**, re-validated at the moment the order is created. A client-supplied price is ignored entirely.
2. The redemption is written in the same transaction as the grant, so a code cannot be spent twice by two concurrent checkouts.
3. A coupon applies to the **first charge only** in 1.0. Recurring discounts are post-launch — they need Razorpay plan-level offers and a different model.
4. A code that would make the total ₹0 is rejected at creation. Free access is granted by admin, not by checkout.
5. Codes are case-insensitive on input, stored uppercase.

### 5.4 Top-up

`GET /plans` already advertises a **₹300 / 120-credit** top-up. There is no way to buy it — `/payments/checkout` accepts only a `PlanTier`. For 1.0 either build the top-up checkout path or stop advertising it. **Recommendation: build it.** It is the Free tier's natural exit and the smallest possible first payment.

---

## 6. Launch-critical fixes

### P0 — blocks a paid launch

| # | Issue | Evidence | Fix |
|---|---|---|---|
| P0-1 | **No recurring billing.** One-time order; `subscriptions.expires_at` written and never read. Paid tiers never lapse. | `app/payments/service.py:139-145` | Razorpay Subscriptions + the four webhook events + nightly expiry sweep (§5.2) |
| P0-2 | **Billing page states a false renewal date and a fake cancel.** Hardcoded "August 1, 2026"; Cancel confirm handler is `setCancelModal(false)`. Status view reads `MOCK_PLANS`. | `frontend/src/pages/Billing.jsx:566, 599, 617, 581` | Wire to the real subscription API; real cancel; delete the mock fallback from the status view |
| P0-3 | **No coupon system exists.** Zero occurrences repo-wide. | — | Build §5.3 |
| P0-4 | **Top-up advertised, unpurchasable.** | `app/api/v1/plans/router.py:48` vs `payments/router.py` | Add the top-up checkout path |
| P0-5 | **Free tier is sized for internal testing, not launch.** 8,000 tokens/day — *above* Plus (3,500) and level with Pro. Free also carries Vision, Recommendations and Knowledge chat, all ₹999 features. | `app/plans/catalog.py:222-260`, flagged in the file's own comments | Resize Free to the launch ladder and narrow its feature set, in one change, before the gate opens |
| P0-6 | **No scheduler in production.** Discovery reminders, the account-deletion sweep, report reconciliation and partition creation are all endpoints nothing calls. | `webhooks/internal_jobs.py` | EventBridge (or pg_cron) hitting the internal endpoints with `INTERNAL_JOBS_SECRET` |
| P0-7 | **`RAZORPAY_*` keys absent from `.env.example`.** A deploy that forgets them silently disables payments — `payments_configured` returns false and checkout 500s. | `backend/.env.example` | Document all three keys; assert at startup in production |

### P1 — must be right at launch

| # | Issue | Evidence | Fix |
|---|---|---|---|
| P1-1 | **Every tier has `free_calls_per_month = 0`**, so no plan includes a call, yet Pro is positioned on coaching access and the QA sheet expects Pro to have two. | `catalog.py:241, 275, 291, 303` | Decide the allowance per tier and set it — or remove the free-call language from Pro's positioning |
| P1-2 | **Paid calls have no payment path.** Booking is a request; ₹300 is collected offline. | `discovery/routes.py:108-132` | Acceptable for 1.0 **if** the ops process is written down and the UI says "the team will confirm and share payment details" — not "pay ₹300" |
| P1-3 | **Error boundary does not reset on navigation.** One crash keeps sibling routes broken until a manual reload. | `MANUAL_QA_CHECKLIST.md §12` | Key the boundary on the route |
| P1-4 | **Know My Energy is sold but not finished.** Declared in Pro's feature set. | `catalog.py:300` | Finish it, or remove it from the advertised set until it ships |
| P1-5 | **Docs contradict the product.** `backend/README.md` says "social login only — Google and LinkedIn, no passwords"; the product ships email + OTP + password. `backend/PROGRESS.md` says the diagnosis engine is unbuilt; it is built. | `backend/README.md`, `backend/PROGRESS.md` | Rewrite both. A new engineer onboarding off these docs starts wrong. |
| P1-6 | **Build artefacts and scratch files are committed.** `frontend.zip` (1.6 MB), `backend/_tmp_diag.py`, `_tmp_run_diagnosis.py`, `cur.json`, `sum.json`. | `git ls-files` | Delete and gitignore |

### P2 — do it in the launch window if it fits

| # | Issue |
|---|---|
| P2-1 | GST handling — the success screen says "+ GST" but no tax line is computed or stored anywhere |
| P2-2 | Invoice / receipt generation — Razorpay's email is the only record a founder gets |
| P2-3 | Dunning emails on a failed charge (currently only an admin-side signal) |
| P2-4 | Full 375px pass over the newer routes (frameworks, achievements, journey, help) |

### Exit criteria — 1.0 ships when all of these are true

- [ ] A real card is charged, renews on the second cycle, and can be cancelled from inside the product
- [ ] A cancelled subscription downgrades to Free at period end, automatically, with data intact
- [ ] A launch code applies a server-computed discount and cannot be redeemed twice
- [ ] Free's ladder is resized and no free founder holds a Pro-only surface
- [ ] The scheduler is live and every internal job has run successfully at least once in production
- [ ] `MANUAL_QA_CHECKLIST.md` passes end to end on production, on desktop and at 375px
- [ ] Zero console errors and zero 5xx across a full founder journey
- [ ] Every screen a founder can reach shows real data or an honest empty state — no mock, no hardcoded date, no fabricated name

---

## 7. What is included in MVP 1.0

**Everything currently built, made correct** — per Decision #3. Concretely:

1. **Access** — waitlist-gated email + OTP + password auth, backend session tokens, rotation, logout.
2. **Onboarding** — the full guided flow through consent, profile, stage and problem statement.
3. **The three-phase diagnosis** — Founder DNA, Current Problem, and the adaptive stage-scoped business diagnosis with confidence-based routing.
4. **The outputs** — Clarity Report with a Clarity Score, Founder DNA, Business DNA across six readiness pillars, root-cause chain, Next Steps.
5. **The workspace** — Dashboard, Ally Chat (grounded, streaming, attachments, voice), Plan Your Day, Goals, Next Steps, Vision, Recommendations, Knowledge chat, Frameworks, Achievements, Journey, Notifications, Help assistant, Profile, Settings, Feedback.
6. **Discovery calls** — live Google Calendar slots, request-and-confirm booking, priority lead time for Pro, confirmation and reminder emails.
7. **Money** — the four-tier ladder (Free trial · ₹199 Starter · ₹450 Plus · ₹999 Pro), credits with lazy settlement, daily token ceilings, server-side entitlements, **auto-renewing Razorpay subscriptions**, **launch coupon codes**, and the ₹300 top-up.
8. **Admin** — the full panel with three-role RBAC, plus the coupon, subscription and failed-payment additions in §4.3, all audited.
9. **Trust** — export, restrict, withdraw, 30-day scheduled deletion, Terms, Privacy, Sentry.
10. **Operations** — a live scheduler, a written migration runbook, and reconciliation alerting.

---

## 8. Post-launch roadmap

### 8.1 Release 1.1 — the first month after launch

| Item | Why it waits |
|---|---|
| Annual plans and annual pricing | Needs the monthly mandate proven first |
| Recurring / multi-cycle coupon discounts | Needs Razorpay plan-level offers, a different model from launch codes |
| Referral programme | Depends on the coupon primitives landing in 1.0 |
| GST invoicing and downloadable receipts | Compliance follow-through on P2-1 / P2-2 |
| Self-serve plan change (upgrade/downgrade mid-cycle with proration) | 1.0 supports upgrade at renewal only |
| Paid discovery calls checked out in-product | Removes the manual ops step in P1-2 |
| Dunning email sequence | Reduces involuntary churn once there is churn to measure |

### 8.2 Release 1.2 — deepening the product

| Item |
|---|
| Repeat / periodic diagnosis — re-run the assessment and diff the Clarity Score over time |
| Founder intelligence: cross-founder pattern detection and benchmarking |
| Founder memory smart-update — memory that revises itself as the founder changes |
| Team seats and multi-founder accounts |
| Native mobile or PWA |
| Coach-side console for the human coaching layer |
| Visual question bank (`visual_question_bank` is seeded empty) |

### 8.3 Release 1.3+ — platform

| Item |
|---|
| Public API / integrations |
| Slack and WhatsApp surfaces for Ally |
| Cohort and accelerator accounts (B2B2C) |
| Evaluation framework running continuously against live diagnoses |
| Migration from Supabase to AWS Cognito (already a one-provider swap by design) |
| Model routing and cost optimisation across providers |

### 8.4 Explicitly **not** on the roadmap

- Lifting the waitlist to open public signup — a separate go-to-market decision, not an engineering one.
- A permanently free tier. Free is a funded one-month trial and stays one.
- Qdrant. The implementation uses pgvector and that divergence from the original PRD is treated as intentional and settled.

---

## 9. Open decisions the product side still owes

| # | Decision | Owner | Blocks |
|---|---|---|---|
| 1 | Free-tier launch sizing — exact daily ceiling, credit grant and feature set | Product | P0-5 |
| 2 | Free discovery calls per tier — or drop the claim from Pro's positioning | Product | P1-1 |
| 3 | Launch coupon slate — which codes, what discount, what expiry | Product / GTM | P0-3 |
| 4 | Sign-off on the confidence-formula weights | Viraj | Engine calibration |
| 5 | "Core questions expected per stage" and the minimum-question floor | Product | Confidence coverage denominator |
| 6 | Whether `business_dimensions` (empty, superseded by `readiness_pillars`) is dropped | Team | Schema hygiene |
