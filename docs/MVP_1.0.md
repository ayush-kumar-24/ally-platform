# Ally — MVP 1.0 Definition

- **Status** — Finalized scope, pending build of the launch-critical fixes in §6
- **Revision** — 3. Rev 2 added Decision 5 (no free tier; coupons are the acquisition mechanism) and the open decisions it creates, in §9. Rev 3 adds P0-11/12/13: the diagnosis engine has never been run against a live model, and the defaults hide that rather than surface it.
- **Date** — 5 September 2026
- **Product** — Ally, the Founder DNA Platform. An AI co-founder coach that diagnoses the *founder* first, then the business, then the root cause sitting at their intersection.
- **Stack** — FastAPI + SQLAlchemy + Alembic on Supabase Postgres · Vite + React 19 + Tailwind + react-router · Backend on AWS App Runner/ECS Fargate, frontend on Vercel · Razorpay (INR) · Supabase Auth

---

## 0. Decisions locked for 1.0

| # | Decision | Choice |
|---|---|---|
| 1 | Billing model | **Auto-renewing mandate.** Razorpay Subscriptions with a real mandate, a working cancel path, and a downgrade sweep on expiry. This is what the UI already promises the founder, so it is the model we make true rather than the promise we retract. |
| 2 | Coupons | **Coupons are the acquisition mechanism, not a promo.** Admin-issued codes: percent off, flat off, or a 100% comp. One redemption per founder, an expiry, a redemption cap. Upgraded from "simple launch codes" by Decision 5 — see §5.3. |
| 3 | Feature scope | **Keep everything currently built, and every feature must work.** Nothing shipped is pulled or flag-hidden. Nothing half-built ships visible. |
| 4 | Access | **Waitlist-gated launch.** Signup stays approval-only; the gate is not lifted in 1.0. |
| 5 | Free tier | **Nothing is free. Every founder pays something.** The Free trial tier is withdrawn from the ladder. Access is obtained by paying, or by redeeming a coupon — including a 100% comp that grants a plan outright. The coupon, not a trial, is what lets a founder start without paying full price. |

Consequence of #3: MVP 1.0 is a *quality and correctness* release, not a feature-cut release. The surface is already wide, so the launch bar is that **every screen a founder can reach tells the truth**, every rupee charged is charged correctly, and **no feature a founder can see is unfinished** — that last clause makes Know My Energy (§1.5) and the discovery-call reminder scheduler (§1.6) required work, not optional.

Consequence of #5, and it is the larger one: **the paywall moves from the end of the journey to the front of it.** Today a founder is diagnosed, reads the report, and only then meets a wall — Ally has proved itself before it asks for money. With no free tier the ask comes *before* the proof, which is precisely what the coupon exists to soften. It also changes what the waitlist is: approval stops meaning "you may sign up" and starts meaning "you may sign up, and here is your code."

**Exactly where that paywall sits is not yet decided** (§9, Decision 1). The three candidate positions are marked in the journey diagram in §2, and the rest of this document is written to hold for any of them.

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
| Reasoning engines: archetype, business health, root cause, stage detection, psychological state, distress language, symptom detection, consistency, recommendation, action plan | Live, **but LLM-gated** | 19 engines under `reasoning/engines/`. Nine independent flags decide whether each reasons by model or degrades to a deterministic path, and **all nine default to off** — see P0-11 |
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
| Know My Energy | **Finish** | Pro — declared in the catalog, founder-facing implementation incomplete. **Required for 1.0** under Decision 3: it is sold on the pricing page, so it must work. |
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
| Coupons — percent, flat, and 100% comp | **Build** — §5.3 |
| Withdraw the Free trial from the sold ladder | **Build** — §5.5. `free` is *retained* as the internal no-access identifier, not deleted |
| Comp grant path — a ₹0 redemption that never touches the gateway | **Build** — §5.3. Razorpay cannot create a ₹0 order or mandate, so this cannot be a discounted checkout |
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
                        │  + coupon code issued    │
                        └────────────┬─────────────┘
                                     │
   ACQUIRE                           ▼
                        ┌──────────────────────────┐
                        │  Sign in                 │  email → OTP → password
                        │  /guided/login           │
                        └────────────┬─────────────┘
                                     │
                        ┄┄┄┄┄ PAYWALL — position A? ┄┄┄┄┄
                                     │
   ORIENT                            ▼
        ┌─────────────────────────────────────────────────────┐
        │  Expectation → Welcome → Consent → Ally intro       │
        │  → Profile build → Tour → Summary → Validate        │
        │  → Problem statement                                │
        └────────────────────────┬────────────────────────────┘
                                 │
                ┄┄┄┄┄┄┄ PAYWALL — position B? ┄┄┄┄┄┄┄
                                 │
   PAY OR REDEEM                 ▼
        ┌─────────────────────────────────────────────────────┐
        │  Pick a plan:  ₹199 Starter · ₹450 Plus · ₹999 Pro  │
        │                                                     │
        │  Enter a coupon ─┬─ percent / flat off              │
        │                  │    ─► Razorpay mandate           │
        │                  │                                  │
        │                  └─ 100% comp                       │
        │                       ─► server-side grant; the     │
        │                          gateway is never called    │
        │                          (₹0 orders are impossible) │
        │                                                     │
        │  NOTHING IS FREE. No plan is reachable without      │
        │  a payment or a comp redemption.                    │
        └────────────────────────┬────────────────────────────┘
                                 │
   DIAGNOSE                      ▼
        ┌─────────────────────────────────────────────────────┐
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
        │    (or the stage's question budget is exhausted)    │
        └────────────────────────┬────────────────────────────┘
                                 │
                ┄┄┄┄┄┄┄ PAYWALL — position C? ┄┄┄┄┄┄┄
                                 │
   REVEAL                        ▼
        ┌─────────────────────────────────────────────────────┐
        │  Thinking → Clarity Report                          │
        │    · Clarity Score                                  │
        │    · Founder DNA (archetype + dimensions)           │
        │    · Business DNA (6 readiness pillars)             │
        │    · Root cause chain                               │
        │    · Next Steps                                     │
        └────────────────────────┬────────────────────────────┘
                                 │
   EXPAND                        ▼
        ┌─────────────────────────────────────────────────────┐
        │  A paying founder still meets ceilings ┐            │
        │    · lifetime diagnosis cap reached    │            │
        │    · daily token ceiling      (429)    ├─► upgrade  │
        │    · credit balance spent     (402)    │   or top-up│
        │    · a higher-tier surface    (403)    ┘            │
        └────────────────────────┬────────────────────────────┘
                                 │
   RETAIN                        ▼
        ┌─────────────────────────────────────────────────────┐
        │  Dashboard · Ally Chat · Plan Your Day · Goals      │
        │  Vision · Recommendations · Frameworks · Journey    │
        │  Discovery call with a human coach                  │
        │  Clarity Score tracked over time                    │
        └────────────────────────┬────────────────────────────┘
                                 │
   LAPSE                         ▼
        ┌─────────────────────────────────────────────────────┐
        │  A subscription ends, or a comp period expires      │
        │  ─► no active plan                                  │
        │                                                     │
        │  WHAT THEY STILL SEE IS UNDECIDED — §9, Decision 2  │
        └─────────────────────────────────────────────────────┘
```

**Reading the diagram.** The three `PAYWALL — position ?` markers are the open decision in §9. Exactly one becomes real and the other two disappear: everything above the chosen marker is reachable without paying, everything below it is not. The rest of this document is written to hold whichever is chosen.

**The monetisation logic.** Ally is not a free product and no longer has a trial. Every founder pays, and the only route to a plan without paying full price is a coupon — a discount, or a 100% comp that grants the plan outright. This is a deliberate trade: a trial converts on *proof* (the founder has seen the diagnosis be right about them before they are asked for money), whereas a coupon converts on *permission* (the founder is asked before Ally has shown anything, and the code is what makes that ask reasonable). The consequence is that the coupon slate is no longer a marketing lever — it **is** the funnel, and a launch with no codes issued is a launch with no signups.

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
| **P** | **Pay, or redeem a coupon** | `/app/billing` | `POST /coupons/validate`, `POST /payments/checkout` *or* `POST /coupons/redeem` | **Step position not yet decided (§9-1).** It sits at A (before step 5), B (here), or C (before step 14). Everything after it is unreachable without an active plan. |
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

### 3.3 Getting a plan — the two paths (target state, §5)

**Path 1 — pay (with or without a discount code)**

| # | Step | API |
|---|---|---|
| 1 | Open pricing, see live catalog + strike-through MRP | `GET /plans` |
| 2 | Enter a coupon code, see the discounted total | `POST /coupons/validate` |
| 3 | Start checkout | `POST /payments/checkout` → Razorpay subscription |
| 4 | Authorise the mandate in the Razorpay modal | Razorpay |
| 5 | Backend grants the plan **from the signed webhook only** | `POST /webhooks/razorpay` |
| 6 | Credits granted, entitlements widen immediately | — |
| 7 | Month 2 onward: auto-charge, credits renew, ledger row appended | `subscription.charged` |
| 8 | Cancel → access continues to period end, then the plan lapses | `POST /payments/subscription/cancel` + expiry sweep |

**Path 2 — redeem a 100% comp**

| # | Step | API |
|---|---|---|
| 1 | Enter the comp code | `POST /coupons/validate` → `{ final_inr: 0, comp: true }` |
| 2 | Redeem — **the gateway is never called** | `POST /coupons/redeem` |
| 3 | Server grants the plan directly, writes the redemption row and an audit entry, in one transaction | — |
| 4 | Comp period is stamped with an explicit end date | — |
| 5 | At period end the founder lapses — **no mandate exists, so nothing auto-charges** | expiry sweep |

The asymmetry in step 5 is the whole risk of this model: a comped founder is a **manual re-conversion**, not a renewal. See §9, Decision 3.

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
          ├─ subscription.halted    ─► dunning exhausted → lapse (§9-2)
          └─ subscription.cancelled ─► mark cancel_at_period_end
          │
          ▼
  Nightly sweep  POST /internal/jobs/expire-subscriptions
          │
          └─ every subscription past current_period_end and not renewed
             ─► plan_type = 'free', which now means NO ACCESS (§5.5)
                · entitlements narrow · data retained · founder emailed
```

**Rules that must hold:**

1. A plan is granted **only** from a signature-verified webhook. Never from a redirect, never from a client call.
2. Every webhook handler is idempotent — Razorpay retries anything that is not a 2xx, and a double grant is a double month.
3. Cancellation is **at period end**, never immediate. The founder paid for the month.
4. Downgrade narrows entitlements but **never deletes data**. A founder who returns finds their reports, goals and history intact. Under Decision 5 the downgrade target is the no-access state, not a trial — see §5.5 and §9-2.
5. Credits expire before they renew at a period boundary — an unused allowance must not roll over.
6. A credit-grant failure must not roll back a plan grant already committed; it is logged loudly and reconciled.

### 5.3 Coupon flow — the acquisition mechanism

Decision 5 makes this the way founders get in, not a discount on the way in. Every code is admin-issued; nothing self-serve generates one.

**Model.** A coupon is: a code, a type, a value, an optional tier restriction, an optional binding to a single email, an expiry date, a maximum total redemption count, and a one-redemption-per-founder rule. Redemptions are recorded in their own append-only table.

| Type | Effect | Path |
|---|---|---|
| `percent` | N% off the first charge | Gateway — discounted mandate |
| `flat` | ₹N off the first charge | Gateway — discounted mandate |
| `comp` | **100% — the plan is granted outright for a stated period** | **Server-side grant; the gateway is never called** |

**Why `comp` is a different code path, not a 100% discount.** Razorpay cannot create an order or a mandate for ₹0. A comp therefore cannot be expressed as a discounted checkout — it has to be a direct grant. That makes it the most sensitive surface in the product: it hands out paid plans with no payment. It is admin-issued only, always capped, always expiring, always audited, and never generated by anything a founder controls.

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
  Server RE-VALIDATES and recomputes. The browser's number is never trusted.
          │
          ├─ final > ₹0  ──► POST /payments/checkout { tier, coupon_code }
          │                     │
          │                     ▼
          │                  Razorpay subscription at the discounted amount
          │                     │
          │                     ▼
          │                  subscription.activated ─► grant + redemption row,
          │                                            in one transaction
          │
          └─ final = ₹0  ──► POST /coupons/redeem { code }
                                │   (gateway NOT called — ₹0 is impossible)
                                ▼
                             grant plan + redemption row + audit row,
                             in one transaction, with an explicit
                             comp_expires_at
                                │
                                ▼
                             NO MANDATE EXISTS. Nothing will auto-charge.
```

**Rules that must hold:**

1. The discount is computed **server-side at checkout**, re-validated at the moment the order is created. A client-supplied price is ignored entirely.
2. The redemption is written in the same transaction as the grant, so a code cannot be spent twice by two concurrent checkouts.
3. A discount coupon applies to the **first charge only** in 1.0. Recurring discounts are post-launch — they need Razorpay plan-level offers and a different model.
4. **A ₹0 total never reaches the gateway.** It routes to the comp grant path instead. (This reverses the rule written before Decision 5, which rejected ₹0 codes outright — comps are now a product requirement.)
5. Codes are case-insensitive on input, stored uppercase.
6. A comp grant carries an explicit end date from the moment it is issued. A comp with no end date is not issuable except through the indefinite-comp path, if §9 Decision 3 authorises one.
7. Comp issuance and redemption both write to the admin audit log, with the issuing admin named. Every free plan in the system must be traceable to a person who authorised it.
8. A code bound to an email may be redeemed only by that email's founder account. This is what makes waitlist-approval issuance safe at scale.

### 5.4 Top-up

`GET /plans` already advertises a **₹300 / 120-credit** top-up. There is no way to buy it — `/payments/checkout` accepts only a `PlanTier`. For 1.0 either build the top-up checkout path or stop advertising it. **Recommendation: build it.** Under Decision 5 it is the smallest possible first payment in the product — the cheapest way for a founder to pay *something* — and the natural landing spot for anyone who exhausts a comped month.

---

### 5.5 Withdrawing the Free tier

**Do not delete the tier. Redefine it.**

`get_plan()` already resolves any unknown, missing or malformed `plan_type` to `free`, deliberately failing *closed* so that a typo grants the least rather than the most. If `free` is redefined from "trial tier" to "**no active subscription, no access**", that existing fallback becomes genuinely safe instead of accidentally generous, and every call site keeps working while granting less.

Deleting the tier instead would mean migrating every `founders.plan_type` row, changing the CHECK constraint on two tables, and finding a new fallback for `get_plan()` — a large, risky change that buys nothing a redefinition does not.

So:

| Change | Detail |
|---|---|
| `PLANS[FREE].features` | → empty, or whatever §9 Decision 2 settles for the lapsed state |
| `signup_credits` | 1,431 → 0 |
| `monthly_credits`, both daily ceilings | → 0 |
| `sold_plans()` | Free already excluded — no change |
| Pricing page | Free column removed; three paid tiers plus the coupon field |
| Copy everywhere | No "free", "trial", or "one month free" language survives. `PLANS[FREE].tagline` currently reads "One month free. See what Ally finds." |
| Expiry sweep target | A lapsed subscription lands on `free`, which now means no access |

**This also resolves P0-5.** The problem was never that Free was mis-sized; it is that Free was a funded trial at all. Decision 5 removes the tier from the ladder, so there is no ceiling left to rebalance — only a lapsed state to define.

---

## 6. Launch-critical fixes

### P0 — blocks a paid launch

| # | Issue | Evidence | Fix |
|---|---|---|---|
| P0-1 | **No recurring billing.** One-time order; `subscriptions.expires_at` written and never read. Paid tiers never lapse. | `app/payments/service.py:139-145` | Razorpay Subscriptions + the four webhook events + nightly expiry sweep (§5.2) |
| P0-2 | **Billing page states a false renewal date and a fake cancel.** Hardcoded "August 1, 2026"; Cancel confirm handler is `setCancelModal(false)`. Status view reads `MOCK_PLANS`. | `frontend/src/pages/Billing.jsx:566, 599, 617, 581` | Wire to the real subscription API; real cancel; delete the mock fallback from the status view |
| P0-3 | **No coupon system exists.** Zero occurrences repo-wide. Under Decision 5 this is no longer a promo feature — it is the only way a founder gets in without paying full price, so **it is the funnel**. | — | Build §5.3, including the `comp` grant path |
| P0-4 | **Top-up advertised, unpurchasable.** | `app/api/v1/plans/router.py:48` vs `payments/router.py` | Add the top-up checkout path |
| P0-5 | **The Free tier must be withdrawn** (Decision 5). It is currently a funded trial sized for internal testing — 8,000 tokens/day, *above* Plus (3,500) and level with Pro, carrying three ₹999 surfaces. | `app/plans/catalog.py:222-260`, flagged in the file's own comments | §5.5 — redefine `free` as the no-access state rather than deleting the tier. Supersedes the earlier "resize it" fix. |
| P0-6 | **No scheduler in production.** Discovery reminders, the account-deletion sweep, report reconciliation and partition creation are all endpoints nothing calls. | `webhooks/internal_jobs.py` | EventBridge (or pg_cron) hitting the internal endpoints with `INTERNAL_JOBS_SECRET` |
| P0-11 | **The diagnosis engine has never been run against a live model.** Nine reasoning flags gate whether a model is involved at all, and every one defaults off. Worse, nothing fails when they are: the engines degrade to deterministic paths and the API keeps returning 200s, so a green run is not evidence a model was ever called. | `app/core/config.py:124,149,156,169,411,430,448,453`; `scripts/verify_llm_integration.py` | Configure a key, turn the flags on, run the preflight, then drive a full diagnosis end-to-end and read the report by hand |
| P0-12 | **Chat silently answers from the mock when unconfigured.** `ALLY_LLM_PROVIDER` defaults to `"mock"`, and `build_routing_policy` falls back to the mock whenever the selected provider has no key — without raising. `FailoverLLMProvider` also keeps mock as the last link by design, so a provider outage fabricates an answer rather than failing. **This has already happened once**: the module's own docstring records chat replying "Grounded answer from mock-standard" and reporting success, with whether it happened depending on import order. | `app/integrations/llm/settings.py:8,36-43,109,131` | Assert at startup that production never resolves to `mock`, and drop `mock` from any production fallback chain |
| P0-13 | **`diagnosis_scoring_configured` is false by default.** `ADAPTIVE_QUESTIONS=False` and `ANSWER_CLASSIFIER="stored"` together mean no answer is ever banded, so every diagnosis yields a report with no evidence behind it. The code names this as the direct cause of a past P0 and logs an error at startup — but only logs it. | `app/core/config.py:500-517`, `app/main.py:176` | Set `ADAPTIVE_QUESTIONS=true` (preferred) or `ANSWER_CLASSIFIER=llm`, and make it a startup refusal in production rather than a log line |
| P0-8 | **No comp grant path.** A ₹0 redemption cannot go through Razorpay, so "some founders get a plan free" is currently unimplementable by any route. | — | §5.3 — `POST /coupons/redeem`, transactional grant + redemption + audit, admin-issued codes only |
| P0-9 | **No lapsed state exists.** Today "downgrade" means moving to Free, which grants a full trial's worth of access. Once Free means no-access, every expiry, cancellation and comp exit lands there — and what a lapsed founder can still see is **undecided** (§9-2). | `app/plans/catalog.py`, expiry sweep | Define the state, then build it. Blocking: the sweep in P0-1 has nowhere correct to land until this is settled |
| P0-10 | **Paywall position is undecided** (§9-1) and gates the onboarding build. Positions A, B and C imply different screens, different drop-off, and different LLM cost exposure for non-payers. | §2 diagram | Product decision required before the onboarding and billing work can be sequenced |
| P0-7 | **`RAZORPAY_*` keys absent from `.env.example`.** A deploy that forgets them silently disables payments — `payments_configured` returns false and checkout 500s. | `backend/.env.example` | Document all three keys; assert at startup in production |

#### Verifying the engine — the order to do it in

`scripts/verify_llm_integration.py` is the preflight. It needs no database, writes nothing, and uses the app's own resolution code rather than reimplementing it, so it reports what the product will actually do. It exists because a passing test run cannot tell you a model was involved:

```
python scripts/verify_llm_integration.py
```

It checks all nine reasoning flags and what each degrades to, whether the classifier has a vendor and a key, **what the chat path resolves to — failing if that is the mock**, a real probe call to every configured provider (asserting the response is stamped with that vendor, not `mock`), and the retrieval/embedding configuration. Exit 0 means genuinely wired; non-zero names the flag or key responsible.

Then, in order:

1. **Preflight** — green, with a real provider probed and no mock resolution.
2. **Drive one full diagnosis end-to-end**, using the harness promoted per P1-7. It answers as a realistic Stage-0 founder, so the output is judgeable.
3. **Read the report by hand.** This is the step no script replaces. Confidence scores, root-cause ranking, the archetype and the narrative prose are all now model-produced, and the only way to know whether they are *right* — rather than merely present — is for someone who knows the product to read one and say so.
4. **Check `narrator_provenance` on every report section.** Sections that fell back to template prose record it, so a report that looks written may still be half-generated. If provenance says template where it should say model, the flag or the call is failing silently.
5. **Re-run with each flag toggled off in turn**, to confirm the degraded paths still produce a coherent report. Every one of these is a live production failure mode, not a hypothetical.

Budget for it: a diagnosis is roughly 24,400 tokens and answers are classified six at a time, so a full run is inexpensive but not instant.

### P1 — must be right at launch

| # | Issue | Evidence | Fix |
|---|---|---|---|
| P1-1 | **Every tier has `free_calls_per_month = 0`**, so no plan includes a call, yet Pro is positioned on coaching access and the QA sheet expects Pro to have two. | `catalog.py:241, 275, 291, 303` | Decide the allowance per tier and set it — or remove the free-call language from Pro's positioning |
| P1-2 | **Paid calls have no payment path.** Booking is a request; ₹300 is collected offline. | `discovery/routes.py:108-132` | Acceptable for 1.0 **if** the ops process is written down and the UI says "the team will confirm and share payment details" — not "pay ₹300" |
| P1-3 | **Error boundary does not reset on navigation.** One crash keeps sibling routes broken until a manual reload. | `MANUAL_QA_CHECKLIST.md §12` | Key the boundary on the route |
| P1-4 | **Know My Energy is sold but not finished.** Declared in Pro's feature set. | `catalog.py:300` | Finish it, or remove it from the advertised set until it ships |
| P1-5 | **Docs contradict the product.** `backend/README.md` says "social login only — Google and LinkedIn, no passwords"; the product ships email + OTP + password. `backend/PROGRESS.md` says the diagnosis engine is unbuilt; it is built. | `backend/README.md`, `backend/PROGRESS.md` | Rewrite both. A new engineer onboarding off these docs starts wrong. |
| P1-6 | **Build artefacts committed.** `frontend.zip` (1.6 MB), and the captured API responses `backend/cur.json` / `sum.json`. | `git ls-files` | Delete and gitignore |
| P1-7 | **Two real diagnosis harnesses are sitting in scratch files.** `_tmp_run_diagnosis.py` drives a full diagnosis over HTTP and `_tmp_diag.py` does it in-process via `TestClient`, both answering as a realistic Stage-0 founder from a hand-written bank of 20+ in-character answers. That is most of the end-to-end test P0-11 needs. | `backend/_tmp_*.py` | **Promote, do not delete** — move into `scripts/` as the diagnosis E2E harness |

### P2 — do it in the launch window if it fits

| # | Issue |
|---|---|
| P2-1 | GST handling — the success screen says "+ GST" but no tax line is computed or stored anywhere |
| P2-2 | Invoice / receipt generation — Razorpay's email is the only record a founder gets |
| P2-3 | Dunning emails on a failed charge (currently only an admin-side signal) |
| P2-4 | Full 375px pass over the newer routes (frameworks, achievements, journey, help) |

### Exit criteria — 1.0 ships when all of these are true

- [ ] A real card is charged, renews on the second cycle, and can be cancelled from inside the product
- [ ] A cancelled subscription lapses at period end, automatically, with data intact
- [ ] A launch code applies a server-computed discount and cannot be redeemed twice
- [ ] A 100% comp code grants a plan without touching the gateway, is capped, expires, and appears in the audit log naming the admin who issued it
- [ ] No route into the product is reachable without an active plan, from whichever paywall position §9-1 settles on
- [ ] The Free tier is withdrawn: no "free" or "trial" copy survives anywhere in the product, and a lapsed founder lands in the defined state rather than on a trial's worth of access
- [ ] The scheduler is live and every internal job has run successfully at least once in production
- [ ] `MANUAL_QA_CHECKLIST.md` passes end to end on production, on desktop and at 375px
- [ ] `scripts/verify_llm_integration.py` exits 0 against production configuration, with a real provider probed and nothing resolving to the mock
- [ ] At least one complete diagnosis has been run against a live model and its report read end to end by a person, with `narrator_provenance` confirming the sections were model-written
- [ ] Zero console errors and zero 5xx across a full founder journey
- [ ] Every screen a founder can reach shows real data or an honest empty state — no mock, no hardcoded date, no fabricated name

---

## 7. What is included in MVP 1.0

**Everything currently built, made correct, and every feature working** — per Decision #3. Nothing ships visible-but-unfinished, which makes Know My Energy and the discovery-reminder scheduler required rather than optional. Concretely:

1. **Access** — waitlist-gated email + OTP + password auth, backend session tokens, rotation, logout.
2. **Onboarding** — the full guided flow through consent, profile, stage and problem statement.
3. **The three-phase diagnosis** — Founder DNA, Current Problem, and the adaptive stage-scoped business diagnosis with confidence-based routing.
4. **The outputs** — Clarity Report with a Clarity Score, Founder DNA, Business DNA across six readiness pillars, root-cause chain, Next Steps.
5. **The workspace** — Dashboard, Ally Chat (grounded, streaming, attachments, voice), Plan Your Day, Goals, Next Steps, Vision, Recommendations, Knowledge chat, Frameworks, Achievements, Journey, Notifications, Help assistant, Profile, Settings, Feedback.
6. **Discovery calls** — live Google Calendar slots, request-and-confirm booking, priority lead time for Pro, confirmation and reminder emails.
7. **Money** — the three-tier paid ladder (₹199 Starter · ₹450 Plus · ₹999 Pro) with **no free tier**, credits with lazy settlement, daily token ceilings, server-side entitlements, **auto-renewing Razorpay subscriptions**, the **coupon system including 100% comps**, and the ₹300 top-up.
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
- A free tier of any kind, permanent or trial. Decision 5 withdrew it; the coupon is the only route to a plan below list price.
- Qdrant. The implementation uses pgvector and that divergence from the original PRD is treated as intentional and settled.

---

## 9. Open decisions

Decision 5 (no free tier) is locked. Four consequences of it are **deliberately not yet decided** and are recorded here with their options, so the build can proceed on everything that does not depend on them. Decisions 1–3 are on the critical path: the onboarding, billing and expiry work cannot be finished without them.

### 9-1. Where the paywall sits — **blocks P0-10**

The candidate positions are marked in the §2 diagram.

| Option | What it means | For | Against |
|---|---|---|---|
| **A — at signup** | Pay or redeem immediately after waitlist approval, before onboarding | Simplest to build and explain; zero free compute given away | The coldest possible ask; onboarding drop-off becomes revenue drop-off |
| **B — after onboarding, before diagnosis** | Founder completes profile, stage and problem statement, sees what Ally will do, then pays | They have invested effort and understand the offer; the expensive part (~24,400 unmetered tokens per diagnosis) is never spent on a non-payer | Some drop-off is simply deferred, not recovered |
| **C — after diagnosis, before the report** | Answer everything, then pay to unlock the Clarity Report | Highest conversion — the founder wants the answer they can already feel is coming | Funds every non-payer's full diagnosis; reads as bait-and-switch to some founders |

**Owner:** Product · **Note:** whichever is chosen, every route below it must fail closed server-side, not merely be hidden in the UI.

### 9-2. What a founder with no active plan can see — **blocks P0-9**

Applies to three populations at once: never paid, lapsed after paying, and a comp that ended.

| Option | What it means | For | Against |
|---|---|---|---|
| **Past reports read-only** | Keep what they already paid for; everything else paywalled | Best reason to come back; never destroys purchased work | More surface to keep correct in a state nobody tests often |
| **Full lockout** | Nothing until they pay again | Strongest renewal pressure | A founder who paid ₹999 loses access to their own diagnosis — reads as punitive |
| **Dashboard + report, no AI surfaces** | Shell, Clarity Score and report stay; anything costing a model call is locked | More product visible, so upgrade prompts land better | The largest of the three to build and keep honest |

**Owner:** Product · **Note:** whatever is chosen, **no founder data is ever deleted on lapse.** Access narrows; the record stays.

### 9-3. What happens when a 100% comp ends — **blocks P0-1's sweep semantics**

A comped founder never authorised a mandate, because no charge ever happened. There is nothing to auto-renew.

| Option | What it means | For | Against |
|---|---|---|---|
| **Lapse, then prompt to pay** | Comp runs N cycles, founder lapses, must actively pay | Honest; no billing surprise; no mandate needed | Every comp renewal is a manual conversion you have to earn |
| **Take a mandate at redemption** | Authorise a mandate even at ₹0 (via a ₹1 authorisation and refund) so cycle N+1 charges automatically | Far better retention; turns comps into real subscriptions | A genuine e-mandate compliance path, and a founder who may not expect the charge |
| **Indefinite comp** | Some codes never expire; revocable from the panel | Necessary for advisors, partners and design partners | Dangerous as anything other than a small, named list |

**Owner:** Product / Finance · **Note:** these are not exclusive — the likely answer is a default plus a small indefinite list, but the default must be chosen.

### 9-4. Existing Free-tier founders — **no action taken pending this**

Today's testers hold `plan_type='free'` with the testing-phase allowance. When Free is redefined to no-access (§5.5) they lose access **at that moment** unless something is done first.

| Option | For | Against |
|---|---|---|
| **Issue comp codes before the switch** | Nobody loses access unannounced; doubles as the first live test of the comp path | Requires the coupon system to ship before the ladder flips — an ordering constraint on the release |
| **Grandfather them** | Simplest for the testers | A permanent second class of account to reason about in every gate, forever |
| **Lapse them with everyone else** | Cleanest model | May cost you the testers currently giving feedback |

**Owner:** Product · **Status:** explicitly deferred — **do nothing until this is decided.** The ordering constraint is the thing to watch: if comp codes are the answer, the coupon system must ship before Free is withdrawn, not with it.

### 9-5. Carried over from before Decision 5

| # | Decision | Owner | Blocks |
|---|---|---|---|
| a | Free discovery calls per tier — or drop the claim from Pro's positioning | Product | P1-1 |
| b | Launch coupon slate — which codes, what discount, how many comps, what expiry | Product / GTM | P0-3 |
| c | Sign-off on the confidence-formula weights | Viraj | Engine calibration |
| d | "Core questions expected per stage" and the minimum-question floor | Product | Confidence coverage denominator |
| e | Whether `business_dimensions` (empty, superseded by `readiness_pillars`) is dropped | Team | Schema hygiene |
| f | Which provider and model the diagnosis engine runs on in production, and the monthly token budget that implies | Product / Eng | P0-11 |
| g | Which of the nine reasoning flags are on at launch — each one off is a surface running deterministically, which is a product choice, not only a config one | Product | P0-11 |

*(The former Decision 1, "Free-tier launch sizing", is closed: Decision 5 withdraws the tier, so there is no ladder left to size — only the lapsed state in 9-2 to define.)*
