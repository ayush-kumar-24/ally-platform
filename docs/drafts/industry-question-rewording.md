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

| | Count |
|---|---|
| **Reword** -- the question is right, the noun is wrong | **64** |
| Already fine -- flagged by the word, not actually broken | 37 |
| Cannot be reworded -- needs a scoping rule instead | 27 |
| | **128** |

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

## The 64 rewordings

Grouped by industry. The measure each question takes is unchanged in every case
-- repeat usage stays repeat usage, cost-to-serve stays cost-to-serve. Only the
noun moves.

### Food & Beverage (22)

**`S0-FNB-102-1`** · Ideation

- ❌ How do you decide whether to add a dish to your menu?
- ✅ How do you decide whether to add a new item to what you sell?

**`S0-FNB-102-2`** · Ideation

- ❌ Have you ever removed a dish, and what made you decide?
- ✅ Have you ever removed something you sell, and what made you decide?

**`S0-FNB-104-1`** · Ideation

- ❌ When a dish goes out wrong, who owns putting it right?
- ✅ When an order goes out wrong, who owns putting it right?

**`S0-FNB-301-1`** · Ideation

- ❌ Do you know what your most popular dish costs you to make?
- ✅ Do you know what your most popular item costs you to make?

**`S0-FNB-303-2`** · Ideation

- ❌ Could someone else cook your signature dish the same way?
- ✅ Could someone else make your signature product the same way?

**`S0-FNB-306-2`** · Ideation

- ❌ Where did you find the last person you hired for the kitchen or for serving customers?
- ✅ Where did you find the last person you hired to make or to serve what you sell?

**`S01-FNB-006`** · Validation / Prototype / Early Traction

- ❌ Is there a written recipe card in the kitchen, or is it from memory?
- ✅ Is there a written recipe or spec for what you make, or is it from memory?

**`S01-FNB-019`** · Validation / Prototype / Early Traction

- ❌ When did you last recalculate what a dish costs you to make?
- ✅ When did you last recalculate what an item costs you to make?

**`S01-FNB-102-1`** · Validation / Prototype / Early Traction

- ❌ Which of your dishes sell least, and what do they cost you to keep on?
- ✅ Which of your items sell least, and what do they cost you to keep on?

**`S01-FNB-102-2`** · Validation / Prototype / Early Traction

- ❌ What is your food waste, and which dishes drive it?
- ✅ What is your food waste, and which items drive it?

**`S01-FNB-103-2`** · Validation / Prototype / Early Traction

- ❌ How is a new kitchen hire trained in their first week?
- ✅ How is a new hire on the food side trained in their first week?

**`S01-FNB-110-1`** · Validation / Prototype / Early Traction

- ❌ When something goes wrong in the kitchen, is the cause written down?
- ✅ When something goes wrong in production, is the cause written down?

**`S01-FNB-110-2`** · Validation / Prototype / Early Traction

- ❌ What does a new kitchen hire have to learn that nobody has written?
- ✅ What does someone new on the food side have to learn that nobody has written down?

**`S01-FNB-301-2`** · Validation / Prototype / Early Traction

- ❌ Which dish on your menu makes you the least money?
- ✅ Which item in your range makes you the least money?

**`S01-FNB-303-2`** · Validation / Prototype / Early Traction

- ❌ What happens to the menu when you are away for a week?
- ✅ What happens to your range when you are away for a week?

**`S10-FNB-007`** · Growth / Expansion / Maturity

- ❌ What food safety training does a new kitchen hire receive?
- ✅ What food safety training does a new hire receive?

**`S10-FNB-011`** · Growth / Expansion / Maturity

- ❌ How many kitchen staff have left in the last year?
- ✅ How many of the people who make your food have left in the last year?

**`S10-FNB-020`** · Growth / Expansion / Maturity

- ❌ How many items are on your menu now, and how many two years ago?
- ✅ How many items do you sell now, and how many two years ago?

**`S10-FNB-023`** · Growth / Expansion / Maturity

- ❌ Do you know which dishes actually make money and which lose it?
- ✅ Do you know which items actually make money and which lose it?

**`S10-FNB-101-1`** · Growth / Expansion / Maturity

- ❌ How do you measure variance between what the spec says and what leaves the kitchen?
- ✅ How do you measure the gap between what the spec says and what actually ships?

**`S10-FNB-102-1`** · Growth / Expansion / Maturity

- ❌ What is your rule for adding a new item to the menu?
- ✅ What is your rule for adding a new item to your range?

**`S10-FNB-102-2`** · Growth / Expansion / Maturity

- ❌ What happened to covers and waste the last time you cut the menu?
- ✅ What happened to sales and waste the last time you cut your range?

### Healthcare (14)

**`S0-HLT-003`** · Ideation

- ❌ Is your business a medical device, a clinic, a pharmacy or a consultation service? The rules are different for each.
- ✅ Is your business a medical device, a clinic, a pharmacy, a consultation service, or software used by any of those? The rules are different for each.

**`S0-HLT-009`** · Ideation

- ❌ How much would an ordinary patient pay for this from their own pocket?
- ✅ How much would your buyer pay for this out of their own pocket, whether that is a patient, a clinic or an employer?

**`S0-HLT-302-1`** · Ideation

- ❌ How much of your week goes on clinical work, and how much on running the company?
- ✅ How much of your week goes on delivering the service itself, and how much on running the company?

**`S01-HLT-006`** · Validation / Prototype / Early Traction

- ❌ Out of 100 patients, how many use you a second time?
- ✅ Out of 100 customers, how many use you a second time?

**`S01-HLT-007`** · Validation / Prototype / Early Traction

- ❌ Does a patient hear from you after the first consult or test?
- ✅ Does a customer hear from you after the first time they use you?

**`S01-HLT-008`** · Validation / Prototype / Early Traction

- ❌ Is there any reason a patient would need you again?
- ✅ Is there any reason a customer would need you again?

**`S01-HLT-009`** · Validation / Prototype / Early Traction

- ❌ Do patients go back to their usual doctor or lab after trying you?
- ✅ Do customers go back to what they used before after trying you?

**`S01-HLT-010`** · Validation / Prototype / Early Traction

- ❌ Is your growth coming from new patients or returning ones?
- ✅ Is your growth coming from new customers or returning ones?

**`S01-HLT-011`** · Validation / Prototype / Early Traction

- ❌ What stops you serving twice as many patients tomorrow?
- ✅ What stops you serving twice as many customers tomorrow?

**`S01-HLT-016`** · Validation / Prototype / Early Traction

- ❌ What does it really cost you to serve one patient, counting every cost?
- ✅ What does it really cost you to serve one customer, counting every cost?

**`S10-HLT-002`** · Growth / Expansion / Maturity

- ❌ How many patients do you need in one area before a city pays for itself?
- ✅ How many customers do you need in one area before a city pays for itself?

**`S10-HLT-003`** · Growth / Expansion / Maturity

- ❌ Why does it cost more to serve a patient in a new city?
- ✅ Why does it cost more to serve a customer in a new city?

**`S10-HLT-015`** · Growth / Expansion / Maturity

- ❌ What share of your patients come through a few partner organisations, such as hospitals, insurers or employers?
- ✅ What share of your customers come through a few partner organisations, such as hospitals, insurers or employers?

**`S10-HLT-302-2`** · Growth / Expansion / Maturity

- ❌ How much of your week could a non-clinician handle?
- ✅ How much of your week could somebody without your specialist training handle?

### Travel & Hospitality (10)

**`S0-TRV-005`** · Ideation

- ❌ How will you get through the quiet season when few guests come?
- ✅ How will you get through the quiet season when few customers come?

**`S0-TRV-303-2`** · Ideation

- ❌ If you were not there, could someone else welcome your guests the way you do?
- ✅ If you were not there, could someone else look after your customers the way you do?

**`S01-TRV-004`** · Validation / Prototype / Early Traction

- ❌ Do you have contact details for guests who stayed with you?
- ✅ Do you have contact details for the customers you have served?

**`S01-TRV-010`** · Validation / Prototype / Early Traction

- ❌ Do you ask happy guests to leave a review?
- ✅ Do you ask happy customers to leave a review?

**`S01-TRV-012`** · Validation / Prototype / Early Traction

- ❌ Is there anything written down about how guests should be looked after?
- ✅ Is there anything written down about how customers should be looked after?

**`S01-TRV-016`** · Validation / Prototype / Early Traction

- ❌ Do you have a clear cancellation policy guests agree to?
- ✅ Do you have a clear cancellation policy customers agree to?

**`S01-TRV-302-1`** · Validation / Prototype / Early Traction

- ❌ What do guests complain about most?
- ✅ What do customers complain about most?

**`S10-TRV-013`** · Growth / Expansion / Maturity

- ❌ How many months could you cover costs with no guests at all?
- ✅ How many months could you cover costs with no customers at all?

**`S10-TRV-015`** · Growth / Expansion / Maturity

- ❌ Where do most of your guests come from, and is it one place?
- ✅ Where do most of your customers come from, and is it one place?

**`S10-TRV-305-1`** · Growth / Expansion / Maturity

- ❌ Which decisions about guests still have to wait for you?
- ✅ Which decisions about customers still have to wait for you?

### Retail (5)

**`S0-RTL-307-1`** · Ideation

- ❌ Where do you want your shop to be in three years?
- ✅ Where do you want the business to be in three years?

**`S01-RTL-008`** · Validation / Prototype / Early Traction

- ❌ Can you see a customer's full history across your shop and online in one place, or is it kept in two separate places?
- ✅ Can you see a customer's full history across everywhere you sell in one place, or is it kept in separate places?

**`S10-RTL-303-2`** · Growth / Expansion / Maturity

- ❌ What knowledge about running your shop is still only in your head?
- ✅ What knowledge about running the business is still only in your head?

**`S10-RTL-304-1`** · Growth / Expansion / Maturity

- ❌ Which job in your shop still has no one clearly responsible for it?
- ✅ Which job in the business still has no one clearly responsible for it?

**`S10-RTL-304-2`** · Growth / Expansion / Maturity

- ❌ Do your shop's standards change depending on which staff are working?
- ✅ Do your standards change depending on which staff are working?

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

**`S10-CEL-005`** · Growth / Expansion / Maturity

- ❌ How do you usually find out about a quality problem, from your factory or from customers?
- ✅ How do you usually find out about a quality problem, from your own checks or from customers?

**`S10-CEL-020`** · Growth / Expansion / Maturity

- ❌ If your factory stopped tomorrow, how long before you could produce anywhere else?
- ✅ If the place that makes your product stopped tomorrow, how long before you could produce anywhere else?

### Delivery (2)

**`S0-DLV-304-1`** · Ideation

- ❌ Who is responsible for how well your riders do their job?
- ✅ Who is responsible for how well your deliveries actually get done?

**`S01-DLV-006`** · Validation / Prototype / Early Traction

- ❌ Is knowledge of your routes written down, or is it only in your drivers' heads?
- ✅ Is knowledge of your routes written down, or is it only in people's heads?

### E-commerce (2)

**`S0-ECM-006`** · Ideation

- ❌ If your store went live today, how would the very first stranger find it?
- ✅ If you went live today, how would the very first stranger find you?

**`S0-ECM-009`** · Ideation

- ❌ Do you have any idea what it costs to get one person to visit your store?
- ✅ Do you have any idea what it costs to get one new person to look at what you sell?

### Education (2)

**`S0-EDU-304-1`** · Ideation

- ❌ Who is responsible for whether students finish the course?
- ✅ Who is responsible for whether learners finish what they start?

**`S10-EDU-307-1`** · Growth / Expansion / Maturity

- ❌ Last year, did your work improve the institute, or did it only fill batches with students?
- ✅ Last year, did your work make the business stronger, or did it only fill more seats?

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

## The 27 that wording cannot fix

These are not badly worded. The subject really is a kitchen, a fleet, a clinical
rota or a second location, and there is no neutral noun that keeps the question
meaningful. *"Is there a maintenance calendar for your fleet?"* cannot be
rewritten for a founder with no vehicles -- it can only be withheld from them.

**They need a scoping rule, which does not exist yet.** Three conditions would
cover all 27:

- **owns production** -- a kitchen, a factory line, a workshop
- **owns a fleet or premises** -- vehicles, a warehouse, a shop floor
- **operates more than one location** -- 5 of the 27 are *"your sites"* questions

That is the same shape as the team-size and revenue axes already built, and it
is a separate piece of work. **Listed here, not changed.**

| Code | What it really needs |
|---|---|
| `S01-DLV-010` | fleet |
| `S01-DLV-013` | fleet |
| `S10-DLV-306-1` | employs riders |
| `S10-ECM-003` | own warehouse |
| `S0-FNB-006` | own commercial kitchen |
| `S0-FNB-104-2` | restaurant floor + kitchen |
| `S01-FNB-104-2` | restaurant floor + kitchen |
| `S01-FNB-302-2` | own kitchen |
| `S10-FNB-004` | more than one site |
| `S10-FNB-006` | own kitchens, hygiene inspection |
| `S10-FNB-307-2` | more than one outlet |
| `S01-HLT-014` | employs clinicians |
| `S01-HLT-015` | hires clinicians |
| `S01-HLT-017` | clinician time as a cost line |
| `S01-HLT-018` | home collection / travel |
| `S10-HLT-005` | clinical case review |
| `S10-HLT-303-1` | clinical conversations |
| `S10-HLT-305-1` | clinical decisions |
| `S01-LOG-009` | fleet |
| `S01-LOG-012` | fleet |
| `S10-LOG-011` | own warehouse |
| `S10-LOG-306-1` | employs drivers |
| `S10-PRP-203-1` | construction sites |
| `S10-PRP-206-2` | construction sites |
| `S10-RTL-301-1` | physical shop, cost per open hour |
| `S0-TRV-007` | lets out property |
| `S10-TRV-004` | more than one site |

---

## What is not covered by any of this

The 128 were found by looking for questions that name a role or a place. There
is a quieter class this cannot find: a question whose wording is neutral but
whose assumed commercial relationship is not -- a B2C framing put to a founder
selling B2B. I cannot put a number on that one.

A hand-check says the 128 is close for what it does cover: 18 random Healthcare
questions were read as Ravi and 6 were wrong for him, which is 33% against the
34% the count gives for that bank.
