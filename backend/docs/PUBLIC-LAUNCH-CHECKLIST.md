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

  That sentence was aspirational when it was written, and wrong. It is true of
  features that HAVE a gate, and until the entitlement-gates change three did
  not: DIAGNOSIS, REPORTS and GOALS had no `require_feature` call anywhere in
  the backend, so flipping this switch redirected a plan-less founder to
  billing in the UI while those endpoints still answered a direct API call.
  They are gated now (`app/api/v1/entitlement_gates.py`), and
  `tests/test_entitlement_gates.py` asserts the routers still carry the
  dependency so it cannot silently come off again.

  Two things remain deliberately open, and should stay that way:
  `/reports/shared/{token}` (a share link is read by someone with no account at
  all) and CALL_BOOKING (booking is sold beside the plans, paid per call).
  KNOW_MY_ENERGY has no backend endpoint to gate -- it is a client-only page.
* **sends a founder with no plan to the plans page** as soon as they sign in,
  instead of letting them meet a series of locked pages and 402s one feature at
  a time.

It can be put back inside a minute if something is wrong.

---

## BEFORE you flip it — move the testers onto a plan

**This is the step that will hurt if it is missed.** Every current tester is on
`plan_type = 'free'`. The moment Free empties, they lose the product along with
everyone else.

> **Done for the team's own accounts by migration `c7e4b19d5a20`**, which runs
> in the deploy alongside the flip rather than waiting for someone to open a
> psql session in the window between the two. The eighteen addresses are listed
> in that file. It reports any that had no `founders` row into the deploy log
> and leaves them alone — those need an approval in the panel and a plan set by
> hand. Anyone added to the team later needs the same treatment; the SQL below
> is still the recipe, and a migration in the shape of `c7e4b19d5a20` is the
> durable version of it.

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

## Was open when this was written — now closed

* **Is Rs 199 monthly or one-time?** Settled: **one-time**. Starter is a single
  diagnosis and the report it writes, not a month of service. `Plan.one_time`
  in the catalog carries it, `GET /plans` returns it, the billing page reads it
  instead of printing "/mo" over a single charge, and a captured payment records
  `billing_cycle='one_time'` with no expiry.
* **Checkout.** Razorpay **is** wired — `app/payments/` plus
  `POST /payments/checkout`, `POST /payments/confirm` and the signed
  `payment.captured` webhook at `app/api/v1/webhooks/razorpay.py`. A founder can
  move themselves off the empty Free tier without anyone touching the database,
  so launch day does not need a person on the other end of the plans page.
  Nothing recurring is created: each purchase is a single auto-captured order,
  never a Razorpay subscription mandate.

## Still open

* **The annual option.** Plus and Pro are sold as "pay for twelve months, get
  two free", and there is no way to actually buy that — no annual price, no
  annual tier, nothing that writes `billing_cycle='annual'` (the column already
  accepts it). Today the offer exists only in the help answers and on the plans
  page.

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
