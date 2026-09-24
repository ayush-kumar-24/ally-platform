# Set A2 — Frozen Scenario Expectation Sets

**Status: FROZEN. Written before any execution, against no results.**

Drafted locally: no cloud access, no LLM calls, no code changes, no database
writes, no commit. `ground_truth.json` untouched (MD5
`7fd06caed78e46bd585ac6e01b1d07f0`) — this file is a *separate* artefact and does
not amend it.

Grounded in the live catalogue (`ally_e2e`, read-only): 23 category→pillar pairs,
8 founder stages, real `problem_code` values.

---

## METHOD, AND WHY IT IS BUILT THIS WAY

**Expectations are stated at PROBLEM and CATEGORY level, not `root_cause_id`.**
Measured earlier in this programme: a session collects ~1 answer per root cause
(88.0% of cases; observed max 2), and 80.3% of causes have exactly one question.
Predicting specific root-cause IDs would test the selector's luck rather than the
engine's reasoning. Problem-level scoring is the primary metric — consistent with
the Option B decision taken for the earlier four-persona run.

**Answers are a fixed text bank, not generated per run.** Under production
pairing the submit-time advisor *is* the classifier, so the free text is the
input under test. Each scenario declares, per category, one canonical answer
string for each intended band. The same question category always receives the
same text. That makes the input deterministic while leaving the classification
genuinely under test.

**Every scenario carries negative controls.** A scenario that only lists what
*should* appear cannot fail informatively. Each one names themes that must NOT
reach the top 3, so over-diagnosis is detectable.

**Stage is fixed per scenario and chosen deliberately.** Stage decides pillar
scope (`stage_order` 1 → pillars 1,2,4,6; order ≥4 → all six) and the question
budget. Most scenarios use **Early Traction (stage_order 4, budget 30)** so all
six pillars are in scope and results are comparable across scenarios. Deviations
are stated and justified.

### Canonical answer bank

| Band | Shape of the answer text |
|---|---|
| GREEN | names a specific mechanism, cadence and owner ("we run X weekly, Y owns it, last review was Tuesday") |
| AMBER | names an intention without a mechanism ("we know we should, we've started, it's inconsistent") |
| RED | names absence plus a consequence ("we don't have that; last month it cost us Z") |
| N/A | states the thing does not exist yet for structural reasons ("we have no employees, so onboarding doesn't apply") |

**N/A is a first-class expectation, not an accident.** `ScoreLabel.is_scored` is
False for `not_applicable`; it must never become negative evidence. Scenarios 01,
07 and 10 test this deliberately.

### Pass criteria per scenario
1. Every expected primary theme appears in the top 3, **or** is recorded as
   NOT_ASKED (never silently as a miss).
2. No negative-control theme appears in the top 3.
3. Every top-3 cause traces to at least one non-GREEN answer in its own category.
4. N/A answers contribute no negative evidence.
5. The session completes, and the completion reason is recorded.

---

## SCENARIO 01 — HEALTHY / LOW-RISK

**Stage:** Early Traction (4) · **Current Problem:** "Things are going well and I
want a check-up before we scale."

**Answers:** GREEN for every category except Financial Management and Scaling &
Operational Maturity, which are AMBER. N/A for Fundraising ("bootstrapped, not
raising").

**Expected:** *No* strongly-supported root cause. Business health reports mostly
healthy bands. Routing should reach the healthy-founder path
(`monitor`) rather than a forced diagnosis.

**Negative controls (must NOT appear in top 3):** OPS-002 Founder Doing
Everything · TCI-001 Customer Discovery Skipped · SAL-001 Weak Pipeline.

**This scenario fails if** any cause is presented as strong on GREEN-dominant
evidence, or if the Fundraising N/A produces negative evidence.

---

## SCENARIO 02 — FOUNDER DEPENDENCY

**Stage:** Early Traction (4) · **Current Problem:** "Everything waits for me. I
approve every decision and the team stalls when I'm unavailable."

**Answers:** RED for Founder Psychology, Team & Leadership, Operations & Systems.
AMBER for Scaling & Operational Maturity. GREEN for Product, Sales Execution,
Target Customer & ICP.

**Expected primary themes:** OPS-002 *Founder Doing Everything — Failure to
Delegate* (pillar 4) · Team & Leadership decision-rights/delegation (pillar 5) ·
Founder Psychology control/centralisation (pillar 1).

**Negative controls:** TCI-001 · BMD-001 Unit Economics · Product prioritisation.

---

## SCENARIO 03 — SALES / GTM

**Stage:** Early Traction (4) · **Current Problem:** "People want the product but
I close deals inconsistently and can't predict revenue."

**Answers:** RED for Sales Execution, Sales & Revenue, Go-To-Market. AMBER for
Marketing Execution. GREEN for Product, Operations & Systems, Team & Leadership.

**Expected primary themes:** SAL-001 *Weak Pipeline and No Deals* (pillar 3) ·
GTM-006 *Ignoring the Sales Motion* (pillar 2) · Sales Execution process
(pillar 3).

**Negative controls:** OPS-002 · TM-046 Training · Financial Management.

*Note:* founder-led-sales dependency counts as SUPPORTED **only** if a
Founder-Psychology or Team answer evidences it. It is not expected from the sales
answers alone, and crediting it without that evidence would be scoring the
narrative rather than the engine.

---

## SCENARIO 04 — CUSTOMER DISCOVERY / MARKET

**Stage:** Validation (2, budget 20) — deliberately earlier, because discovery
weakness is a pre-traction pathology and stage scope should still admit
pillars 1, 2, 4, 6.

**Current Problem:** "I'm confident about who the customer is but I haven't
really tested it."

**Answers:** RED for Target Customer & ICP, Idea & Validation, Competitive
Awareness. AMBER for Marketing Execution. GREEN for Founder Psychology, Product.
N/A for Sales & Revenue ("no paying customers yet").

**Expected primary themes:** TCI-001 *Customer Discovery Skipped or Superficial*
(pillar 2) · Idea & Validation weakness (pillar 2) · Competitive Awareness gap
(pillar 2).

**Negative controls:** OPS-002 · TM-046 · any Revenue Maturity cause driven by
the N/A answer.

*Secondary check:* at stage 2 the report must not claim assessment of pillars
outside scope.

---

## SCENARIO 05 — FINANCIAL / BUSINESS MODEL

**Stage:** Early Traction (4) · **Current Problem:** "Money comes in but I don't
know which parts of the business actually make money."

**Answers:** RED for Financial Management, Business Model Design. AMBER for Sales
& Revenue. GREEN for Product, Operations & Systems, Team & Leadership, Target
Customer & ICP.

**Expected primary themes:** BMD-001 *Unit Economics Never Calculated* (pillar 3)
· BMD-016 *Cost Structure Not Mapped to Revenue Model* (pillar 3) · Financial
Management visibility (pillar 3).

**Negative controls:** OPS-002 · TCI-001 · Product prioritisation.

---

## SCENARIO 06 — OPERATIONS / SYSTEMS

**Stage:** Growth / Scaling (5, budget 30) — manual-process strain is a
growth-stage pathology.

**Current Problem:** "We're growing but everything is held together manually."

**Answers:** RED for Operations & Systems, Scaling & Operational Maturity. AMBER
for Team & Leadership. GREEN for Sales Execution, Product, Target Customer & ICP,
Financial Management.

**Expected primary themes:** OPS-021 *No Practice of Creating or Maintaining
SOPs* (pillar 4) · OPS-005 *Lack of Metrics or KPIs* (pillar 4) · Scaling &
Operational Maturity process gap (pillars 5/6).

**Negative controls:** TCI-001 · BMD-001 · SAL-001.

*Note:* OPS-003 *Scaling Prematurely* is **acceptable but not required** —
plausible at this stage, so it counts as PARTIALLY_SUPPORTED rather than a miss
or a bonus.

---

## SCENARIO 07 — TEAM / TRAINING

**Stage:** Early Traction (4) · **Current Problem:** "I've hired people but
getting them productive takes forever and it all lives in my head."

**Answers:** RED for Team & Leadership. AMBER for Operations & Systems. GREEN for
Sales Execution, Product, Financial Management, Target Customer & ICP. **N/A for
Fundraising and for any question presupposing a formal HR function.**

**Expected primary themes:** TM-046 *No Structured Training on How to Actually
Perform the Role* (pillar 5) · onboarding/knowledge-transfer (pillar 5) ·
documentation/SOP concentration (pillar 4, via OPS-021).

**Negative controls:** TCI-001 · BMD-001 · GTM-006.

*N/A check:* the HR-function N/A answers must not create Team & Leadership
negative evidence. If TM-046 is supported, it must be supported by the RED
answers, not the N/A ones.

---

## SCENARIO 08 — PRODUCT / EXECUTION

**Stage:** Early Traction (4) · **Current Problem:** "We ship constantly but I
can't tell if we're building the right things."

**Answers:** RED for Product. AMBER for Operations & Systems, Scaling &
Operational Maturity. GREEN for Sales Execution, Financial Management, Team &
Leadership, Target Customer & ICP.

**Expected primary themes:** Product prioritisation (pillar 4) · product process
/ execution discipline (pillar 4) · Operations & Systems process weakness
(pillar 4, secondary).

**Negative controls:** TCI-001 · BMD-001 · OPS-002.

*Discrimination check:* Product is the largest category in the bank (385
questions). If Product causes dominate every scenario's top 3 regardless of
answers, that is a selector-bias finding, not a Scenario-08 success. Compare
against 02/04/05.

---

## SCENARIO 09 — MULTI-ROOT-CAUSE

**Stage:** Growth / Scaling (5) · **Current Problem:** "Several things are wrong
at once and I don't know which to fix first."

**Answers:** RED for Operations & Systems, Financial Management, Team &
Leadership. AMBER for Sales Execution, Product. GREEN for Target Customer & ICP.

**Expected:** three *distinct* supported causes spanning **at least two different
pillars**, drawn from: OPS-021/OPS-005 (pillar 4), Financial Management/BMD
(pillar 3), TM-046 (pillar 5).

**Negative controls:** TCI-001 (the one GREEN category).

**This scenario fails if** all three top causes come from a single pillar while
three pillars carry RED evidence — that would indicate the ranking collapses onto
whichever category was probed most, rather than reflecting breadth.

---

## SCENARIO 10 — MIXED / EDGE CASE

**Stage:** Early Traction (4) · **Current Problem:** "Some things work, some
don't, and I'm not sure what's actually broken."

**Answers, deliberately mixed:**
- Operations & Systems: **RED, then a contradicting GREEN** in the same category
  ("we have no process" … later "we run a documented weekly ops review").
- Team & Leadership: single AMBER, no corroboration.
- Financial Management: **N/A** ("my accountant handles all of it; I don't see it").
- Sales Execution: GREEN.
- Product: one RED, one N/A.

**Expected:**
- **Nothing reaches strong confidence.** Contradiction plus thin evidence should
  keep every cause below the strong bar.
- The Operations contradiction must be visible in the evidence trail — both
  answers retained, not the later overwriting the earlier.
- Financial Management N/A must produce **no** Revenue Maturity cause.
- Confidence must be *lower* than Scenario 02's, on strictly weaker evidence.

**Negative controls:** any Financial Management cause · any cause resting solely
on N/A answers.

**This scenario is the most diagnostic of the ten.** It is the one where a system
that pattern-matches rather than reasons will over-diagnose.

---

## CROSS-SESSION ISOLATION TEST (Section 5)

Not a scenario — a dedicated adversarial check, to run **interleaved**, because
sequential runs would not detect state bleed.

1. Start Scenario 02 (founder dependency). Answer 5 questions. **Do not finish.**
2. Start Scenario 05 (financial) as a different founder. Answer 5 questions.
3. Return to 02, answer 5 more. Alternate to completion.
4. Then verify, per session: questions asked appear in no other session's history;
   answers map only to their own `session_id`; detected causes and the report
   reference only that session's answers; no `answer_id` appears twice.

**Contamination is indicated by** any Financial Management cause surfacing in
Scenario 02's report, or any delegation cause in Scenario 05's — neither has
supporting evidence in its own session.

---

## WHAT THIS RUN CAN AND CANNOT VALIDATE

Recorded now, so it is not discovered afterwards: the deployed backend runs
`origin/main`. The Phase 5 RCCS work is committed locally at `1e81952c` and has
**never been pushed or deployed**. A cloud run today therefore exercises the
**pre-Phase-5** engine — no RCCS, no coverage-relative scoring, no completion
gate, no `root_cause_evidence_events`.

That is still worth doing as a **baseline**, and these expectation sets remain
valid for it. But no result from this run can confirm or refute the Option E
semantics. Comparing a later post-deployment run against this baseline is where
that evidence would come from.

## COST ESTIMATE (for authorisation, not yet incurred)

10 sessions × ~30 answers under production pairing, one advisor/classifier call
per scored answer plus report generation. The earlier four-persona run measured
**201 calls at $1.4254**. Scaling: **~300–350 calls, roughly $2.10–$2.50**, plus
10 report generations. Nothing has been spent.
