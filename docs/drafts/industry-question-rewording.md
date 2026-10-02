# Industry questions that presume one kind of business

**For review before anything is written to the database.** Nothing here has
been applied; the migration that applies it reads this same list.

## The defect

A founder picks their industry at onboarding. The diagnosis then draws on that
industry's question bank. But an industry is not a business model, and some of
those questions were written as though it were -- they ask the founder about
operations they do not run.

Two real cases from a test diagnosis:

> **Ravi** sells booking software to physiotherapy clinics. He was asked
> *"Out of 100 patients, how many use you a second time?"* and *"How much of
> your week goes on clinical work?"* He has no patients and is not a clinician.
>
> **Priya** sells banana chips online. She was asked about *"cutting the menu"*
> and *"covers and waste"*. She has no restaurant.

## How big it actually is

**128 questions of 4,810** carry a role or premises word -- 2.7%. Concentrated:
Healthcare 39, Food & Beverage 29, Travel 14; ten industries have none at all.

Reading all 128 as the founder who sells *into* the industry rather than
operating *in* it:

| | Count | What happened |
|---|---|---|
| **Withhold** -- keep the vivid wording, don't ask the wrong founder | **76** | `b5d4e31a7c92` |
| Already fine -- flagged by the word, not actually broken | 37 | untouched |
| **Reword** -- the premise was a place or a role, not vocabulary | **15** | `a3f7b21c6d84` |
| | **128** | |

### This changed after the first attempt, and the correction matters

The first version of this review reworded **64** questions. 49 of those replaced
the industry's own vocabulary for its customers and its products -- *patients*,
*guests*, *dish*, *menu*, *shop*, *students* -- with *customers* and *items*.

That removed the premise and the specificity in one stroke, and **specificity is
the product.** A homestay owner reading *"Do you ask happy guests to leave a
review?"* is understood. Reading *"happy customers"* they could be any business
alive.

And the founder it was protecting is the **minority**. Most people who pick
Healthcare *are* a clinic. Most people who pick Travel *do* have guests.
Rewording for everybody protected the exception by flattening the majority.

So those 49 have their original wording back, and are **withheld** from founders
who do not run the operation -- together with the 27 that could never have been
reworded anyway. **15 rewordings stand**, the ones where the premise was a place
or a role (*kitchen*, *warehouse*, *factory*, *clinician*) and the industry's
vocabulary survived losing it.

## The test applied to each one

A question is **wrong** when it asks the founder about operations they do not
run or people they do not have -- *your kitchen*, *your drivers*, *your week on
clinical work*.

A question is **fine** when it names the industry's own reality -- who
ultimately pays, what the regulator requires, who the end beneficiary is, who
you are selling to. Those are as true for a supplier to the industry as for an
operator in it. *"Who actually hands over the money, the patient, an employer,
an insurer or the government?"* is a good question for Ravi.

This is why 37 of the 128 need no change: the flag found the word, not a defect.

---

## The 15 rewordings

Grouped by industry. The measure each question takes is unchanged in every case
-- repeat usage stays repeat usage, cost-to-serve stays cost-to-serve. Only the
noun moves.

### Food & Beverage (22)

**`S01-FNB-006`** · Validation / Prototype / Early Traction

- ❌ Is there a written recipe card in the kitchen, or is it from memory?
- ✅ Is there a written recipe or spec for what you make, or is it from memory?

**`S01-FNB-102-2`** · Validation / Prototype / Early Traction

- ❌ What is your food waste, and which dishes drive it?
- ✅ What is your food waste, and which items drive it?

**`S01-FNB-103-2`** · Validation / Prototype / Early Traction

- ❌ How is a new kitchen hire trained in their first week?
- ✅ How is a new hire on the food side trained in their first week?

**`S01-FNB-110-2`** · Validation / Prototype / Early Traction

- ❌ What does a new kitchen hire have to learn that nobody has written?
- ✅ What does someone new on the food side have to learn that nobody has written down?

**`S10-FNB-007`** · Growth / Expansion / Maturity

- ❌ What food safety training does a new kitchen hire receive?
- ✅ What food safety training does a new hire receive?

**`S10-FNB-011`** · Growth / Expansion / Maturity

- ❌ How many kitchen staff have left in the last year?
- ✅ How many of the people who make your food have left in the last year?

**`S10-FNB-101-1`** · Growth / Expansion / Maturity

- ❌ How do you measure variance between what the spec says and what leaves the kitchen?
- ✅ How do you measure the gap between what the spec says and what actually ships?

### Healthcare (14)

**`S0-HLT-003`** · Ideation

- ❌ Is your business a medical device, a clinic, a pharmacy or a consultation service? The rules are different for each.
- ✅ Is your business a medical device, a clinic, a pharmacy, a consultation service, or software used by any of those? The rules are different for each.

**`S0-HLT-009`** · Ideation

- ❌ How much would an ordinary patient pay for this from their own pocket?
- ✅ How much would your buyer pay for this out of their own pocket, whether that is a patient, a clinic or an employer?

### Trading / Import-Export (4)

**`S0-TRD-006`** · Ideation

- ❌ What will one unit actually cost you by the time it reaches your warehouse?
- ✅ What will one unit actually cost you by the time it reaches you?

**`S0-TRD-007`** · Ideation

- ❌ In the cost of one unit reaching your warehouse, have you included customs duty?
- ✅ In the cost of one unit reaching you, have you included customs duty?

**`S0-TRD-008`** · Ideation

- ❌ In the cost of one unit reaching your warehouse, have you included freight (shipping charges) and insurance?
- ✅ In the cost of one unit reaching you, have you included freight (shipping charges) and insurance?

**`S0-TRD-009`** · Ideation

- ❌ In the cost of one unit reaching your warehouse, have you included customs clearing, port and agent charges?
- ✅ In the cost of one unit reaching you, have you included customs clearing, port and agent charges?

### Consumer Electronics (2)

**`S10-CEL-020`** · Growth / Expansion / Maturity

- ❌ If your factory stopped tomorrow, how long before you could produce anywhere else?
- ✅ If the place that makes your product stopped tomorrow, how long before you could produce anywhere else?

### Fashion (1)

**`S10-FSH-020`** · Growth / Expansion / Maturity

- ❌ If a buyer asked about your factory labour conditions, could you answer?
- ✅ If a buyer asked about labour conditions where your product is made, could you answer?

---

## The 37 that need no change

Each was read and judged to work as written for someone selling into the
industry. Three are plain false positives -- the word *covers* appears in
*"covers every legal duty"*, *"what each session covers"* and *"insurance still
covers"*.

| Code | Why it stays |
|---|---|
| `S0-AGR-006` | asks which farmer or crop you are BUILT FOR -- targeting, not operations |
| `S0-AGR-011` | the season you are TARGETING |
| `S0-AGR-012` | whether your idea accounts for crop cycles |
| `S0-AGR-208-1` | 'working on' is already neutral |
| `S01-AGR-017` | where your product has been tested |
| `S10-AGR-208-1` | the cost of spreading yourself, already neutral |
| `S10-AUT-009` | 'your vehicles on the road' = units you sold |
| `S10-DLV-010` | false positive: matched 'covers every legal duty' |
| `S10-EDU-304-2` | at-risk follow-ups are the outcome an edtech seller sells on |
| `S01-GAM-013` | 'store page' is the app store listing |
| `S0-HLT-006` | who ultimately pays -- true for a supplier to the industry too |
| `S0-HLT-008` | government scheme coverage, a regulatory fact |
| `S0-HLT-010` | whether you pitch the same thing to two buyers |
| `S0-HLT-015` | consent for health data -- a booking tool holds it too |
| `S0-HLT-307-1` | names the buyer, which is the point |
| `S0-HLT-307-2` | product/buyer fit |
| `S01-HLT-001` | serving while approval is pending applies to software too |
| `S10-HLT-007` | patient safety accountability reaches anyone in the pathway |
| `S10-HLT-010` | data breach detection -- squarely a software question |
| `S10-HLT-011` | 'every patient on your system' already fits a platform |
| `S10-HLT-012` | access logging, a software control |
| `S10-HLT-013` | data subject requests |
| `S10-HLT-014` | minors' records |
| `S10-HLT-016` | who sets rates -- the payer reality |
| `S10-HLT-017` | payer payment terms |
| `S10-HLT-019` | whether you can reach the patient directly: channel risk |
| `S10-HLT-024` | explicitly asks WHETHER you own capacity |
| `S10-HLT-025` | disintermediation risk, central for a supplier |
| `S10-LGL-011` | false positive: matched 'insurance still covers' |
| `S10-MFG-016` | a manufacturer has a factory |
| `S10-MFG-304-2` | same |
| `S0-PHM-014` | which buyer group you target |
| `S01-PHM-018` | 'patients using your product' already names the product |
| `S0-SPF-303-1` | false positive: matched 'what each session covers' |
| `S10-TEL-301-1` | 'sites' are cell sites, the unit of a telecom business |
| `S0-TRV-006` | which permissions you need: regulatory |
| `S0-TRV-011` | who the offering is for |

---

## How the 76 are withheld

There is no column that states a founder's business model. `founders.business_model`
sounds like it would and does not -- it is constrained to B2B / B2C / D2C, which
is the *sales* model, and a clinic and a clinic-software company are both B2B.

So the filter reads `founders.product_description`, which every founder fills in
(25 of 25 rows, averaging 121 characters). It looks for one thing: **the
founder's customer is a business of the trade.** You do not sell *to* clinics if
you *are* the clinic.

That signal was found the hard way. The first version looked for product-category
words -- *SaaS*, *software*, *app*, *platform* -- and missed the very founder it
was built for, whose description reads:

> *"Appointment booking and reminders for small clinics"*

Not one category word in it. **Most founders write what their product does, not
which category it belongs to.** The customer is the reliable signal; the product
noun is not.

### What is deliberately NOT treated as a trade business

*manufacturer*, *distributor*, *brand*, *developer*, *seller*. One real
description reads:

> *"B2B line-haul and warehousing for manufacturers and distributors across four cities"*

That is a logistics operator who owns trucks and warehouses. Treating
*manufacturers* as a trade business would strip their fleet and warehouse
questions -- the same harm this fix exists to prevent, inflicted from the other
direction.

### Two flags, not one

| Flag | Count | Why separate |
|---|---|---|
| `requires_operating_role` | 71 | The subject is the operation: a kitchen, a clinical rota, a fleet, patients, guests |
| `requires_multiple_locations` | 5 | The subject is a *second site* |

The second is withheld on the same signal today, because a software company has
no sites at all — but **that signal is a stand-in, not the real fact.** A
single-outlet restaurant runs the operation and still has no second site. Keeping
the flag separate means that the day a location count is collected, those five
can be gated properly without disturbing the other 71. One flag would have hidden
the distinction, and it would have been found by a founder rather than by us.

### What this does not catch

It cannot reliably tell a **packaged-food maker from a restaurant**. Both say
they make food. One real description reads *"Home-style North Indian tiffin
meals: 14 dishes"* — where *dish* and *menu* are exactly right — and another
reads *"hand-made Indian sweets and bars"*, where *menu* is wrong. No keyword
separates them, and keyword screening over this bank has already been wrong in
both directions twice. So a packaged-food founder still sees a few questions
written for a venue, and that is stated here rather than discovered later.


## What is not covered by any of this

The 128 were found by looking for questions that name a role or a place. There
is a quieter class this cannot find: a question whose wording is neutral but
whose assumed commercial relationship is not -- a B2C framing put to a founder
selling B2B. I cannot put a number on that one.

A hand-check says the 128 is close for what it does cover: 18 random Healthcare
questions were read as Ravi and 6 were wrong for him, which is 33% against the
34% the count gives for that bank.
