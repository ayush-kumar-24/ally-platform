# Public launch: turning off "everything is free"

Today Free carries almost the whole product. That is deliberate — the people
using it are our own testers, and gating them out mid-test would be worse than
leaving it open.

At launch nothing is free. This is the switch and the two things that must
happen either side of it.

---

## The switch

```
PUBLIC_LAUNCH=true
```

One deploy setting, no release. Flipping it:

* **empties the Free tier.** Free stops being a plan anyone uses and becomes the
  state a founder is in before they have chosen one. Every feature gate reads
  the same feature set, so this closes all of them at once rather than leaving
  one route open because somebody forgot it.
* **sends a founder with no plan to the plans page** as soon as they sign in,
  instead of letting them meet a series of locked pages and 402s one feature at
  a time.

It can be put back inside a minute if something is wrong.

---

## BEFORE you flip it — move the testers onto a plan

**This is the step that will hurt if it is missed.** Every current tester is on
`plan_type = 'free'`. The moment Free empties, they lose the product along with
everyone else.

Check who that affects:

```sql
select founder_id, email, plan_type, created_at
from founders
where coalesce(plan_type, 'free') = 'free'
order by created_at;
```

Then put the real testers on a paid tier. `pro` gives the full product:

```sql
update founders
   set plan_type = 'pro'
 where email in (
   -- the testing accounts, listed explicitly
   'someone@example.com',
   'someone-else@example.com'
 );
```

Listed explicitly rather than by a pattern on purpose: a `like '%@goxl%'` would
quietly sweep in anyone who signs up with a company address afterwards, and the
whole point of this step is knowing exactly who has been granted the product for
free.

Verify before flipping:

```sql
select plan_type, count(*) from founders group by plan_type order by 2 desc;
```

Anyone still on `free` after this will be sent to the plans page.

---

## AFTER you flip it — check these four

1. **A tester can still use the product.** Sign in as one and open Ally chat.
   If they are bounced to the plans page, their `plan_type` did not get set.
2. **A founder with no plan lands on the plans page** and can still reach it —
   the gate deliberately never redirects away from billing, or it would loop.
3. **The three plans show the right prices.** They render from the catalog, so
   they cannot drift from what the gate enforces.
4. **Discovery calls still work.** They are Rs 199 each on every plan, with no
   included allowance, so nothing about them changes at launch — but it is worth
   confirming the request flow still reaches the team queue.

---

## What does NOT change at launch

* **Discovery call pricing.** Flat Rs 199 per call, however many are booked, on
  every plan. No tier includes one.
* **The diagnosis limit.** One per account, on every plan.
* **Feature gating itself.** It is already enforced server-side and has been for
  some time. Launch only changes what the Free tier contains.

## Billing — settled

* **Is Rs 199 monthly or one-time?** Answered: **one-time**. `PlanTier.BASIC`
  carries `one_time=True`, and `PaymentService.start_checkout` is the only path
  that sells it. Every surface that prints the price reads that flag rather
  than assuming "/mo".
* **Checkout.** Wired, both halves. Starter is a Razorpay **Order**; Plus and
  Pro are Razorpay **Subscriptions** — a mandate Razorpay charges monthly until
  cancelled. `start_checkout` refuses a renewing tier outright, because selling
  one as a single order charges the founder once and gives them the plan
  forever, which is what it did before.
* **Cancellation, invoices, expiry.** Cancel at period end (the founder keeps
  the month they paid for); invoices index Razorpay's own documents; and
  `subscriptions.access_until` is enforced by the expire-subscriptions sweep.

### Before Live Mode — the steps that are NOT code

These are operational and nobody can do them from here:

1. **Create the Live Mode Razorpay Plans.** `POST /admin/billing/razorpay-plans`
   with `{"tier": "starter"}` and `{"tier": "pro"}` creates each plan at
   Razorpay for the catalog price and registers its id, or pass an existing
   `razorpay_plan_id` to adopt one. Until a plan id is registered for a tier,
   subscribing to it returns 503 rather than guessing an id — the amount a
   founder is charged every month is decided by the Razorpay Plan, and a
   guessed one charges a number nobody chose.
2. **Configure the Live webhook endpoint and its secret.** The events to
   subscribe to are `payment.captured`, `payment.failed`,
   `subscription.authenticated`, `subscription.activated`,
   `subscription.charged`, `subscription.pending`, `subscription.halted`,
   `subscription.cancelled`, `subscription.completed` and `invoice.paid`.
   `RAZORPAY_WEBHOOK_SECRET` is separate from the key secret; with it unset,
   signature verification fails closed and nothing is ever granted.
3. **Schedule the expiry sweep.** `POST /internal/jobs/expire-subscriptions`,
   daily. `.github/workflows/internal-job-sweeps.yml` already calls it at 18:30
   UTC. Without it, paid access never ends: cancellation, the grace window and
   the billing period are all dates that nothing reads.
4. **Have the CA validate the GST treatment and the invoice format.** The
   backend collects and validates the inputs (legal name, GSTIN, place of
   supply) and stores whatever tax figure Razorpay reports. It computes no tax
   and asserts nothing about whether a Razorpay invoice is a compliant tax
   invoice for this business. That is not a gap to be closed in code.
5. **Run one controlled production transaction and reconcile it** against
   `payments`, `invoices` and the Razorpay dashboard before enabling the public
   payment buttons.

## Still open when this was written

* **Annual billing.** "Pay for twelve months, get two free" is described in the
  help answers and is not implemented. It needs a second Razorpay Plan per tier
  at ten months' price and a billing-cycle field on the subscription.
* **Plan changes.** Moving between Plus and Pro is refused with a 409 telling
  the founder to cancel first. Doing it properly means cancelling one mandate
  and starting another with a defensible answer for the overlap they already
  paid for, which is a pricing decision rather than a coding one. Support can
  cancel and resubscribe on request in the meantime.

---

## AT THE SAME TIME — publish the six held support answers

Six answers describe the product **as it will be once Free is empty**. They are
written, checked and loaded, but deliberately not published: showing them today
would give a tester still on Free a wrong answer.

They carry `status = 'answered_pending_product_change'`, so the bot skips them.

Run this in the same sitting as the switch:

```sql
-- Publish the answers that only become true once Free is gone.
UPDATE support_bot_answers
   SET status       = 'answered',
       is_published = true,
       verified_on  = current_date
 WHERE status = 'answered_pending_product_change';

-- Should return 6.
SELECT count(*) FROM support_bot_answers
 WHERE is_published AND verified_on = current_date;
```

The six are: **5** (is this going to sell me something), **152** (why pay if Free
gives me the report), **153** (why does Free get more chat than Starter), **154**
(how long does Free last), **155** (what happens at the end of my free month) and
**169** (do I get credits again next month).

**If you roll the launch back**, put them back too:

```sql
UPDATE support_bot_answers
   SET status = 'answered_pending_product_change', is_published = false
 WHERE question_id IN (5, 152, 153, 154, 155, 169);
```
