# Paid trial + Razorpay autopay: setup

A founder can start any paid plan as a **10-day trial** for a small fee. Paying
the fee and setting up autopay (card mandate or UPI AutoPay) happen in one
Razorpay step. Unless they cancel, autopay charges on **day 11**, and that charge
is the plan price **less the trial fee** they already paid.

| Plan (internal tier) | Trial fee | Day-11 charge | After that |
|---|---|---|---|
| Starter (`basic`) | ₹19 | ₹180 | nothing (Starter is one month) |
| Plus (`starter`) | ₹29 | ₹470 | ₹499 every month until cancelled |
| Pro (`pro`) | ₹49 | ₹950 | ₹999 every month until cancelled |

Each founder gets **one trial, ever**. The prices live in
`app/plans/catalog.py` (`trial_price_inr`, `TRIAL_DAYS`). The flow lives in
`app/payments/subscriptions.py`.

**Until a plan's Razorpay plan ID and offer ID are both set, that plan offers no
trial.** The pricing page simply doesn't show the trial button for it. Nothing
breaks, and buying the plan outright keeps working.

## 1. Razorpay Dashboard (do it in Test mode first)

1. **Enable Subscriptions** on the account (Subscriptions → get started). UPI
   AutoPay and card mandates may need Razorpay to activate them for your account.
2. **Create three Plans** (Subscriptions → Plans), each billed **every 1 month**
   at the plan's **full** price:
   - Starter ₹199 → `RAZORPAY_PLAN_ID_BASIC`
   - Plus ₹499 → `RAZORPAY_PLAN_ID_STARTER`
   - Pro ₹999 → `RAZORPAY_PLAN_ID_PRO`
3. **Create three subscription Offers** (Offers → create offer, applied to
   subscriptions). Each is a **flat discount equal to the trial fee**, applied to
   the **first payment only**:
   - ₹19 off → `RAZORPAY_TRIAL_OFFER_ID_BASIC`
   - ₹29 off → `RAZORPAY_TRIAL_OFFER_ID_STARTER`
   - ₹49 off → `RAZORPAY_TRIAL_OFFER_ID_PRO`

   The offer is what makes day 11 charge ₹950 instead of ₹999. Without it,
   founders would pay the trial fee on top of the full price. That's why the
   code refuses to start a trial when the offer ID is missing.
4. **Webhook** (Settings → Webhooks, the existing `/api/v1/webhooks/razorpay`
   URL). In addition to `payment.captured` and `payment.failed`, enable:
   `subscription.authenticated`, `subscription.activated`,
   `subscription.charged`, `subscription.pending`, `subscription.halted`,
   `subscription.cancelled`, `subscription.completed`.

## 2. Environment variables (backend)

```
RAZORPAY_PLAN_ID_BASIC=plan_...
RAZORPAY_PLAN_ID_STARTER=plan_...
RAZORPAY_PLAN_ID_PRO=plan_...
RAZORPAY_TRIAL_OFFER_ID_BASIC=offer_...
RAZORPAY_TRIAL_OFFER_ID_STARTER=offer_...
RAZORPAY_TRIAL_OFFER_ID_PRO=offer_...
```

These are in addition to the existing `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`
and `RAZORPAY_WEBHOOK_SECRET`. Test-mode IDs go with test keys, and live IDs go
with live keys.

## 3. Migration and sweep

- Run `alembic upgrade head` (revision `e3a7c41b9d26`). It allows a `pending`
  subscription status and adds a unique index on
  `subscriptions.gateway_subscription_id`.
- `POST /api/v1/internal/jobs/expire-subscriptions` moves founders back to Free
  once a cancelled or failed autopay's period ends. It's scheduled every 10
  minutes in `.github/workflows/internal-job-sweeps.yml`. **Without it, a
  founder who cancels the trial keeps the plan forever.**

## 4. Verify in Test mode before going live

1. On Billing, click **Try 10 days for ₹49** on Pro and pay with a test card or
   UPI. Check that the payment window shows ₹49, and that afterwards you're on
   Pro with 80 credits.
2. In the Dashboard, open the subscription. Check that its start date is 10 days
   out **and that the first charge shows ₹950**. This checks that the offer is
   applied to the day-11 charge, not to today's ₹49. If it shows ₹999, fix the
   offer before going live.
3. Bring the first charge forward from the Dashboard (or wait). Check that the
   founder's subscription row turns `active` and 240 credits are added.
4. Start a second test founder's trial and cancel it from **My Subscription**.
   Check that no day-11 charge happens and that the plan ends when the trial
   ends (after the sweep runs).

## What happens when

| Event | Effect |
|---|---|
| Founder clicks "Try 10 days" | Razorpay subscription created; row `pending`. Nothing granted yet. |
| Mandate authorised + trial fee paid (`subscription.authenticated` or the founder's `/payments/trial/confirm`) | Row `trial`; plan granted; trial credits (Plus 35, Pro 80). |
| Day 11 charge (`subscription.charged`) | Row `active`; paid period set; monthly credits. |
| Founder cancels during trial | Autopay cancelled at once, so no day-11 charge. Plan kept until trial end, then Free. |
| Founder cancels after paying | Cancelled at cycle end. Plan kept until the paid month ends, then Free. |
| Autopay fails every retry (`subscription.halted`) | Row `expired`; plan revoked at once. |
