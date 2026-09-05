# Ally — MVP 1.0 Definition

- **Status** — Scope final. Blocked on the P0s in §6 and the decisions in §8.
- **Date** — 5 September 2026 · **Revision** — 4 (condensed; rev 3 in git history)
- **Product** — Ally, the Founder DNA Platform. Diagnoses the *founder*, then the business, then the root cause where they intersect.
- **Stack** — FastAPI + SQLAlchemy on Supabase Postgres · React 19 + Vite on Vercel · Razorpay (INR)

---

## 1. Decisions locked

| # | Decision |
|---|---|
| 1 | **Auto-renewing mandate.** Razorpay Subscriptions with a real mandate, working cancel, and a downgrade sweep. |
| 2 | **Coupons are the acquisition mechanism**, not a promo: percent off, flat off, or a 100% comp. |
| 3 | **Keep everything built, and every feature must work.** Nothing ships visible-but-unfinished. |
| 4 | **Waitlist-gated launch.** Approval-only; the gate is not lifted in 1.0. |
| 5 | **Nothing is free.** The Free trial tier is withdrawn. Every founder pays, or redeems a coupon. |

**What #5 changes:** the paywall moves from the end of the journey to the front. A trial converts on *proof* — the founder has seen the diagnosis be right about them before being asked for money. A coupon converts on *permission*. So the coupon slate **is** the funnel: a launch with no codes issued is a launch with no signups. Waitlist approval now means "you may sign up, and here is your code."

**What #3 changes:** 1.0 is a correctness release, not a feature-cut one. The bar is that every screen tells the truth and every rupee is charged correctly. That makes Know My Energy and the discovery-reminder scheduler required, not optional.

---

## 2. Scope

**In 1.0 — everything currently built, made correct:**
Waitlist-gated auth (email + OTP + password) · guided onboarding · the three-phase diagnosis (Founder DNA → Current Problem → adaptive business diagnosis) · Clarity Report, Founder/Business DNA, Next Steps · Ally Chat (grounded, streaming, attachments, voice) · Plan Your Day, Goals, Vision, Recommendations, Knowledge chat, Frameworks, Achievements, Journey, Notifications, Help · discovery calls on live Google Calendar · the three-tier paid ladder with credits, entitlements, subscriptions, coupons and top-up · the admin panel with RBAC and audit · GDPR export/restrict/withdraw/delete.

**Moves to post-launch:**

| Release | Items |
|---|---|
| 1.1 | Annual plans · recurring/multi-cycle coupon discounts · referrals · GST invoicing + receipts · mid-cycle plan change with proration · in-product paid call checkout · dunning emails |
| 1.2 | Repeat diagnosis with Clarity Score diffing · founder intelligence and benchmarking · memory smart-update · team seats · mobile/PWA · coach console · visual question bank |
| 1.3+ | Public API · Slack/WhatsApp surfaces · cohort and accelerator accounts (B2B2C) · continuous eval against live diagnoses · Cognito migration · model routing and cost optimisation |
| Never | A free tier of any kind. Lifting the waitlist (a GTM call, not an engineering one). Qdrant — pgvector is settled. |

---

## 3. Feature list

**Live:** auth + session rotation, waitlist gate, guided onboarding, consent ledger, all three diagnosis phases, stage-scoped pillar selection, per-stage question budget, confidence routing (continue <60 / validate 60–80 / report ≥80), Clarity Report, Founder DNA, Business DNA (6 pillars), Next Steps, dashboard, Ally Chat, Plan Your Day, Goals, Vision, Recommendations, Knowledge chat, Frameworks, Achievements, Journey, Notifications, Help assistant, profile/settings/feedback, discovery slots + booking, credit ledger with lazy settlement, daily token ceilings, server-side entitlements, unbilled-usage reconciliation, admin panel (RBAC, users, credits, flags, broadcasts, usage, audit), GDPR flows, Sentry.

**Live but LLM-gated:** the 19 reasoning engines. Nine flags decide whether each reasons by model or degrades deterministically — **all nine default off** (P0-11).

**Must finish for 1.0:** Know My Energy (sold on the pricing page, not built) · discovery reminder emails (code works, nothing schedules it).

**Must build for 1.0:** recurring subscriptions · coupons incl. comps · real Billing UI · top-up checkout · Free-tier withdrawal · the lapsed state.

---

## 4. User journey

```
  Waitlist approval + coupon code issued
        │
        ▼   Sign in (email → OTP → password)
        │
        ├╌╌ PAYWALL position A?
        │
        ▼   Onboarding: consent → profile → stage → problem statement
        │
        ├╌╌ PAYWALL position B?
        │
        ▼   PAY OR REDEEM   ₹199 Starter · ₹450 Plus · ₹999 Pro
        │     coupon → discount ─► Razorpay mandate
        │     coupon → 100% comp ─► server-side grant, gateway never called
        │
        ▼   DIAGNOSE   Founder DNA → Current Problem → adaptive diagnosis
        │     per question: stage-scope → rank → ask → classify → confidence
        │
        ├╌╌ PAYWALL position C?
        │
        ▼   REVEAL   Clarity Report · Founder DNA · Business DNA · Next Steps
        │
        ▼   RETAIN   chat, planning, goals, calls; ceilings drive upgrade/top-up
        │
        ▼   LAPSE    subscription or comp ends → no active plan
```

Exactly one paywall position becomes real (§8-1). Everything below it must fail closed **server-side**, not merely be hidden in the UI.

**Step-by-step:** land → sign in → *(A)* → consent → profile build → stage tour → problem statement → *(B)* → Founder DNA journey (`/diagnosis/start` 409s until complete) → Current Problem → adaptive diagnosis (server-side session, resumable) → *(C)* → report. Steady state: resume session → dashboard → chat/plan/goals, where a wall is **429** daily limit, **402** credits spent, **403** higher tier — all routing to billing.

---

## 5. Subscription & coupon flow

**Subscription.** Checkout creates a Razorpay subscription; the founder authorises the mandate; the **signed webhook is the only path that grants anything** — `activated` grants plan + credits, `charged` extends and renews, `failed` marks retrying, `halted` lapses, `cancelled` marks cancel-at-period-end. A nightly sweep lapses anything past its period end.

Rules: grants only from a verified webhook, never a redirect · every handler idempotent · cancellation at period end, never immediate · downgrade narrows entitlements but **never deletes data** · credits expire before they renew at a boundary · a credit-grant failure never rolls back a committed plan grant.

**Coupons.** Admin-issued only. A code carries a type, value, optional tier restriction, optional email binding, expiry, redemption cap, one-per-founder.

| Type | Effect | Path |
|---|---|---|
| `percent` / `flat` | Discount on the first charge | Gateway — discounted mandate |
| `comp` | 100%, plan granted for a stated period | **Server-side grant; gateway never called** |

**Razorpay cannot create a ₹0 order or mandate**, so a comp can never be a discounted checkout — it is a direct grant, which makes it the most abusable surface in the product: capped, expiring, audited to the issuing admin, never self-serve.

Rules: discount computed server-side at checkout, client price ignored · redemption written in the same transaction as the grant · discounts apply to the first charge only in 1.0 · a ₹0 total routes to the comp path · every comp carries an explicit end date · codes stored uppercase.

**A comped founder never authorises a mandate**, so nothing auto-charges at period end — every comp is a manual re-conversion unless §8-3 says otherwise.

**Withdrawing Free — redefine, don't delete.** `get_plan()` already resolves any unknown `plan_type` to `free`, failing *closed*. Redefining `free` as "no active subscription, no access" makes that fallback genuinely safe and avoids migrating every founder row and the CHECK constraint on two tables. Set its features and credits to zero, remove the Free column and all "free/trial" copy, and point the expiry sweep at it.

---

## 6. Launch-critical fixes

### P0 — blocks launch

| # | Issue | Evidence |
|---|---|---|
| P0-1 | **No recurring billing.** One-time order; `subscriptions.expires_at` is written and never read, so a paid tier never lapses. | `payments/service.py:139` |
| P0-2 | **Billing page is mock.** Hardcoded "Next renewal: August 1, 2026"; Cancel confirm only closes the modal; status view reads `MOCK_PLANS`. | `Billing.jsx:566,581,599,617` |
| P0-3 | **No coupon system exists** — and under Decision 5 it is the funnel. | — |
| P0-4 | **Top-up advertised, unpurchasable.** `/payments/checkout` takes only a `PlanTier`. | `plans/router.py:48` |
| P0-5 | **Free tier must be withdrawn** (§5). Currently a testing-phase trial at 8,000 tokens/day — above Plus, level with Pro, carrying three ₹999 surfaces. | `catalog.py:222-260` |
| P0-6 | **No scheduler in production.** Discovery reminders, deletion sweep, report reconciliation, partition creation are endpoints nothing calls. | `webhooks/internal_jobs.py` |
| P0-7 | **`RAZORPAY_*` keys absent from `.env.example`** — a deploy that omits them silently disables payments. | `.env.example` |
| P0-8 | **No comp grant path**, so "some get a plan free" is currently unimplementable. | — |
| P0-9 | **No lapsed state.** Downgrade targets Free, which today grants a full trial. Undecided (§8-2). | `catalog.py` |
| P0-10 | **Paywall position undecided** (§8-1), gating the onboarding build. | — |
| P0-11 | **The diagnosis engine has never run against a live model.** Nine reasoning flags gate it, all default off — and nothing fails when they are: engines degrade, the API returns 200s. A green run is not evidence a model was called. | `config.py:124,149,156,169,411,430,448,453` |
| P0-12 | **Chat silently answers from the mock.** `ALLY_LLM_PROVIDER` defaults to `"mock"` and routing falls back to it when a key is missing, without raising. **Already happened once** — chat replied "Grounded answer from mock-standard" and reported success. | `llm/settings.py:8,36-43,109,131` |
| P0-13 | **`diagnosis_scoring_configured` is false by default**, so no answer is banded and every report has no evidence behind it. Startup logs the error, then starts anyway. | `config.py:500-517`, `main.py:176` |

**Verifying the engine.** `python scripts/verify_llm_integration.py` — no database, writes nothing, uses the app's own resolution code. It reports the nine flags and what each degrades to, whether chat resolves to the mock (failing if so), and probes every configured provider, asserting the response is stamped with that vendor. Then: run a full diagnosis on the harness in P1-7, **read the report by hand** (no script judges whether scores are *right* rather than merely present), check `narrator_provenance` on each section, and re-run with flags toggled off to confirm the degraded paths stay coherent.

### P1

| # | Issue |
|---|---|
| P1-1 | Every tier has `free_calls_per_month = 0`, yet Pro is sold on coaching access. |
| P1-2 | Paid calls have no payment path — booking is a request, ₹300 collected offline. Acceptable if the UI says so and the ops process is written down. |
| P1-3 | Error boundary doesn't reset on navigation — one crash breaks sibling routes until reload. |
| P1-4 | Know My Energy is sold but unfinished. |
| P1-5 | Docs contradict the product: `backend/README.md` claims social-login-only; `PROGRESS.md` says the diagnosis engine is unbuilt. Both wrong. |
| P1-6 | `frontend.zip` (1.6 MB) and captured responses `cur.json`/`sum.json` are committed. |
| P1-7 | **Promote, don't delete:** `_tmp_run_diagnosis.py` (HTTP) and `_tmp_diag.py` (in-process) drive a full diagnosis as a realistic Stage-0 founder. That is most of the P0-11 test. |

**P2 if it fits:** GST computation (the success screen says "+ GST" and nothing computes it) · invoices/receipts · dunning emails · 375px pass over the newer routes.

---

## 7. Exit criteria

- [ ] A real card is charged, renews on the second cycle, and cancels from inside the product
- [ ] A cancelled subscription lapses at period end, automatically, data intact
- [ ] A comp code grants a plan without touching the gateway — capped, expiring, audited to the issuing admin
- [ ] No route is reachable without an active plan, from whichever paywall position is chosen
- [ ] Free is withdrawn: no "free" or "trial" copy survives anywhere
- [ ] `verify_llm_integration.py` exits 0 against production config, nothing resolving to the mock
- [ ] One complete diagnosis run against a live model, report read end to end by a person, `narrator_provenance` confirming model-written sections
- [ ] The scheduler is live and every internal job has run successfully in production at least once
- [ ] `MANUAL_QA_CHECKLIST.md` passes on production, desktop and 375px
- [ ] Zero console errors, zero 5xx, across a full founder journey
- [ ] Every screen shows real data or an honest empty state — no mock, no hardcoded date, no fabricated name

---

## 8. Open decisions

| # | Decision | Options | Blocks |
|---|---|---|---|
| 1 | **Where the paywall sits** | **A** at signup — cleanest, coldest ask · **B** after onboarding, before diagnosis — effort invested, and the ~24,400-token diagnosis is never spent on a non-payer · **C** after diagnosis, before the report — highest conversion, but funds every non-payer and reads as bait-and-switch | P0-10 |
| 2 | **What a founder with no active plan sees** (never paid, lapsed, or comp ended) | Past reports read-only · full lockout · dashboard + report but no AI surfaces. **No founder data is ever deleted on lapse** — access narrows, the record stays | P0-9 |
| 3 | **What happens when a comp ends** | Lapse and re-ask (honest, manual) · take a mandate at redemption via ₹1 auth + refund (retention, but an e-mandate compliance path) · indefinite comp for advisors/partners. Likely a default plus a small named list | P0-1 sweep |
| 4 | **Existing Free testers** | Comp codes before the switch · grandfather · lapse with everyone. **Deferred — do nothing yet.** Note the ordering constraint: if comps are the answer, coupons must ship *before* Free is withdrawn | — |
| 5 | Free discovery calls per tier — or drop the claim from Pro | — | P1-1 |
| 6 | Launch coupon slate: which codes, what discount, how many comps, what expiry | — | P0-3 |
| 7 | Provider, model and monthly token budget for the engine in production | — | P0-11 |
| 8 | Which of the nine reasoning flags are on at launch — each one off is a product choice, not just config | — | P0-11 |
| 9 | Confidence-formula weights sign-off (Viraj) · "core questions per stage" + minimum floor · whether `business_dimensions` is dropped | — | Engine calibration |
