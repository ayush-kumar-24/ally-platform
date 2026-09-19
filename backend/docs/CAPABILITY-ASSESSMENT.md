# Capability assessment — Step 7C

CAPABILITY EVIDENCE → CURRENT CAPABILITY ASSESSMENT. Converts individual,
immutable observations (Step 7B) into a deterministic read of "what level does
Ally currently have evidence for, for this capability, in this session?"

This is an **assessment layer only**. No Gap Engine, no target-state
comparison, no recommendation, no root-cause change.

---

## Architecture: no new table

`app/api/v1/diagnosis/capability_assessment.py` is a **pure function** over
already-persisted `capability_evidence` rows — `assess_capability` /
`assess_capabilities` take rows in, return `CapabilityAssessment` dataclasses
out. Nothing is written, nothing is materialized.

This mirrors a decision the codebase already made once: `target_state.
resolve_requirements` computes the Required Capability Model as a pure
function over `capability_requirements` rows rather than a stored table.
The same reasoning applies here, with more force — `capability_evidence` rows
are already persisted, already immutable (nothing anywhere issues an `UPDATE`
against them), and a capability accumulates single digits of observations per
session, not thousands. A stored assessment table would need invalidation
logic every time a new observation lands; not storing anything makes that
problem not exist rather than solving it cleverly. This also directly answers
§17 of the step brief (performance): there is nothing to recompute *after*
every answer, because nothing is stored *from* any answer — the read is always
computed fresh, always cheap, always current.

The one piece of wiring is `DiagnosisRepository.current_capability_
assessments(session_id)`, which reads `capability_evidence_for_session`
(Step 7B's own method) and hands the rows to `assess_capabilities`. It is a
composition, not a new query.

---

## Why the 136 criteria needed no new rule (§10 resolved)

The step brief asks whether Step 5's taxonomy supports inferring a capability
level from its four evidence criteria, and to **stop and report** if it does
not. It does not need to — because that inference already happened, once, per
observation, in Step 7B. `capability_evidence.observed_level` is the
extractor's complete 0–3 judgment for **one answer**, grounded in whichever
criterion it cited (or none). `capability_evidence_criteria` carries no level
of its own by Step 5's design, and nothing in Step 7C reads the criteria table
at all.

So Step 7C's actual problem is narrower than "combine four criteria into a
level" — it is "combine several **already-levelled** observations into one
current reading", which is well-posed and has no ambiguity to report.

---

## UNASSESSED vs. Level 0

| State | `current_level` | `status` | Representation |
|---|---|---|---|
| **UNASSESSED** | `None` | `"unassessed"` | zero observations, or zero that clear the confidence floor |
| Level 0 | `CapabilityLevel.ABSENT` | `"assessed"` | evidence **explicitly** stated the capability is absent |
| Level 1–3 | the level | `"assessed"` | a confident observation |

`current_level is None` and `status == UNASSESSED` never disagree — by
construction, not by convention (`CapabilityAssessment.status` is a computed
property of `current_level`, there is no second field that could drift from
it).

Level 0 is **never invented** by this step. By the time a row exists in
`capability_evidence` with `observed_level = 0`, Step 7B's extractor has
already required the answer to *explicitly* state absence — "we don't have a
sales process" — as opposed to a founder simply not mentioning it (which
produces no row at all). Step 7C trusts that invariant rather than
re-interpreting it.

---

## N/A

Unchanged from Step 7B, restated at this layer: `ScoreLabel.NOT_APPLICABLE` is
excluded **before** the extractor is ever called, so an N/A answer produces no
`capability_evidence` row, which means it produces nothing for
`assess_capabilities` to aggregate. An N/A answer cannot move a capability
from UNASSESSED, cannot contribute to `excluded_evidence_ids`, and is
invisible to this layer entirely — verified end-to-end in
`test_not_applicable_produces_no_evidence_therefore_unassessed`.

---

## The aggregation rule: lowest confident reading

1. An observation **participates** only if `confidence >= MIN_CONFIDENCE`.
2. `current_level = min(observed_level for every participating observation)`.
3. Zero participating observations → UNASSESSED.

### The confidence threshold, justified rather than invented

`MIN_CONFIDENCE = 0.6` is **the same constant** Step 7B's extractor already
uses to decide whether to store an observation at all (promoted from a
private `_MIN_CONFIDENCE` to a public name in `capability_evidence.py` so
Step 7C imports the identical number rather than declaring a second one). In
today's single-writer system every stored row already cleared this bar at
write time, so the check at aggregation time is a **belt, not the buckle**: it
guards against a future or alternate writer inserting something weaker
(there is no database `CHECK` requiring ≥ 0.6, only ≥ 0), not against
anything that can happen today.

### Min, not average, not majority, not most-recent

Maturity is not a statistic. "You have a documented process" (level 2) and
"you personally do it" (level 1) about the *same* capability are not two data
points to blend — the second directly contradicts the first, and the
conservative reading never credits more independence than the weakest
confirmed observation shows.

This single rule is also what makes two of the step brief's other
requirements true **by construction**, with no extra logic:

- **§4 "a weak observation cannot downgrade strong evidence"** — an
  observation below the floor never enters the `min()` at all, so it cannot
  pull the result down regardless of its level. There is no separate
  "outlier rejection" step layered on top.
- **§11 "more evidence does not mean a higher level"** — ten Level-1
  observations `min` to Level 1, exactly as one does; one strong Level-3
  observation `min`s to Level 3 on its own, exactly as the brief's own
  example requires.

### The two worked examples from the step brief, verified verbatim

```
Level 3 @ .95, Level 2 @ .90, Level 3 @ .92  →  Level 2   (all three confident; min wins)
Level 3 @ .95, Level 0 @ .31                 →  Level 3   (.31 excluded; never entered the min)
```

Both are asserted directly in `test_the_briefs_own_worked_example_level_3_2_3_resolves_to_2`
and `test_a_weak_contradictory_observation_below_threshold_does_not_downgrade`.

---

## Determinism

`min()` over a set of integers has exactly one answer regardless of insertion
order. Ties among observations at the winning level are broken by sorting
`evidence_id` ascending — never by recency or magnitude. No LLM participates
in aggregation; the whole module is pure Python over already-judged rows.
Verified by `test_insertion_order_does_not_change_the_assessment` (forward,
reversed, and shuffled inputs produce byte-identical results).

---

## Traceability

`CapabilityAssessment` carries three evidence-id tuples on the object itself:

- `supporting_evidence_ids` — the rows whose level **equals** the result; "why
  is this founder Level 1 for FND-DELEG" points here directly.
- `considered_evidence_ids` — every observation that cleared the floor, a
  superset of the above whenever more than one level was confidently
  observed (so a contradicting-but-outvoted reading stays visible, not
  silently discarded).
- `excluded_evidence_ids` — observations that existed but were too weak to
  participate, so "was there contradicting evidence that got overridden, or
  none at all" is answerable without a second query.

From any `evidence_id`, `capability_evidence.answer_id` /
`.question_id` complete the chain to the exact founder answer — one row
lookup, not a chain of joins through tables that could themselves change.

---

## Isolation from existing diagnosis

Nothing in this step touches question selection, the Top-5, stage detection,
category scores, root-cause ranking, distress detection, psychological state,
the recommendation engine, business health, archetype, report generation, or
target-state requirements. Verified structurally: `test_existing_module_has_
no_dependency_on_the_assessment` asserts none of those modules' source files
mention `capability_assessment` at all.

---

## Intentionally not implemented (Step 8+)

- Comparing `current_level` against `capability_requirements.required_level`
  (the Gap Engine)
- Any `MISSING` / gap / severity / deficit state
- Recommendations or interventions conditioned on the assessment
- Founder-lifetime aggregation across multiple sessions (this step is
  session-scoped, matching how the rest of the diagnosis pipeline — confidence,
  root-cause detection — is already session-scoped)
- A persisted assessment table (deliberately not built — see "Architecture"
  above)
