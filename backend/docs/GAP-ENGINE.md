# Gap Engine — Step 8

CURRENT CAPABILITY ASSESSMENT (Step 7C) + TARGET-STATE REQUIREMENTS (Step 6)
→ a factual, four-state comparison per capability. A comparison, not a
verdict: no severity, no priority, no recommendation, no intervention.

---

## Architecture: no new table

`app/api/v1/diagnosis/gap_engine.py` is a **pure function**,
`compute_capability_gaps(requirements, assessments, capability_names)`, over
the already-computed outputs of the two upstream resolvers. Nothing is
written, nothing is materialized — the same decision Step 6
(`resolve_requirements`) and Step 7C (`assess_capabilities`) already made,
for the same reason: both inputs are cheap to recompute (bounded rows, small
per-founder/per-session cardinality), so a stored `detected_gaps` table would
only add invalidation problems neither existing layer has.

```
FounderContext + TargetStateContext
          |
          v
resolve_requirements(capability_requirement_rows, ...)   [Step 6, untouched]
          |
current_capability_assessments(session_id)                [Step 7C, untouched]
          |
          v
   compute_capability_gaps(...)                            [Step 8]
          |
          v
   tuple[CapabilityGap, ...]
```

`DiagnosisRepository.capability_gaps_for_session(session_id, founder_context,
target)` is the one piece of wiring: it calls `capability_requirement_rows()`
(a bounded, unfiltered `SELECT * FROM capability_requirements`, already used
by Step 6's own callers), passes it and the founder's context into
`resolve_requirements`, calls `current_capability_assessments(session_id)`
(Step 7C's own method, itself built on Step 7B's
`capability_evidence_for_session`), fetches `capability_names()` (one bounded
`SELECT capability_id, capability_name FROM capabilities`), and hands all
three straight to `compute_capability_gaps`. No logic from either resolver is
reimplemented in the repository method or in `gap_engine.py` — this is
enforced structurally by `test_specificity_comes_exclusively_from_the_step_6_resolver`
and `test_current_state_comes_exclusively_from_the_step_7c_resolver`, which
grep the module's actual code (its docstring stripped, so explanatory prose
about what the module does *not* do cannot false-positive the check) for
`specificity`/`_applies(`/`_pick(`/`from_stage_order` and for
`MIN_CONFIDENCE`/`observed_level`/`min(` respectively.

---

## The four states

| Status | Meaning | `required_level` | `current_level` |
|---|---|---|---|
| `UNASSESSED` | insufficient evidence to say anything about current state | set (a requirement exists) | `None` |
| `GAP` | founder's current level is below what the target state requires | set | set, `<` required |
| `SATISFIED` | founder's current level meets or exceeds the requirement | set | set, `>=` required |
| `NOT_REQUIRED` | no applicable requirement for this founder's target context | `None` | whatever it is (or `None`) |

`STATUS_UNASSESSED` is literally the same string as
`capability_levels.UNASSESSED` (`"unassessed"`) — the sentinel is imported,
not redeclared, so a caller checking `gap.status == UNASSESSED` (from either
module) never has to know which layer produced the value.

### UNASSESSED is never a Gap

This is the one rule the whole module protects. In `_compare`, the check

```python
if current_level is None:
    return CapabilityGap(..., status=STATUS_UNASSESSED, ...)
```

runs **before** the `current_level < required_level` comparison is ever
reached — not after it, not as a special case inside it. There is no code
path in this module where `None < required_level` is evaluated. A founder
with no confident evidence for GTM-ACQ is told "insufficient evidence",
never "you are missing GTM-ACQ" — the second is a claim about capability the
system has no evidence to support, and conflating "we don't know" with "you
don't have it" would be a false, and worse, unfalsifiable, diagnosis.

### `required_level = 0` is a real requirement, not "nothing required"

A `RequiredCapability` row with `required_level = 0` still runs through the
normal UNASSESSED/GAP/SATISFIED comparison exactly like `required_level = 3`
would. `current_level = 0 >= required_level = 0` is `SATISFIED` (with
`surplus_level = None`, since there's no surplus) — not a free pass, not
"no requirement". A *different* capability that has **no row at all** in
`resolve_requirements`'s output is what becomes `NOT_REQUIRED`. The two
cannot be confused because they arrive through entirely different code
paths: a present `RequiredCapability` object vs. its complete absence from
`required_by_id`.

### Exceeding the requirement is SATISFIED, never a "reverse gap"

`current_level > required_level` is `SATISFIED` with an optional
`surplus_level = current_level - required_level` (informational only — no
new scoring rides on it, and it is `None`, not `0`, when there's no
surplus). There is no negative `gap_size` anywhere in this module.

### `gap_size` — plain integer, no severity

`gap_size = required_level - current_level`, set only when `status == GAP`,
always positive. There is no low/medium/high bucketing anywhere — the step
brief is explicit that identifying a gap and prioritizing it are different
problems, and only the first is this step's job. No such severity taxonomy
exists elsewhere in the codebase to borrow from, and none is invented here.

---

## Requirement and assessment resolvers are reused, not duplicated

`compute_capability_gaps` takes `requirements: tuple[RequiredCapability, ...]`
and `assessments: tuple[CapabilityAssessment, ...]` as plain arguments — it
never calls `resolve_requirements` or `assess_capabilities`/
`current_capability_assessments` itself, and never re-derives anything they
already computed (no re-application of the specificity cascade, no
re-aggregation of `observed_level`/`confidence`). It reads only the two
dataclasses' public fields (`RequiredCapability.required_level`,
`CapabilityAssessment.current_level`, `.supporting_evidence_ids`, etc.).

Preserving Step 6's own semantics for an unknown target context is
therefore automatic: if the founder's revenue band or time horizon is
unknown, `resolve_requirements` already returns no row for anything gated on
that unknown dimension (Step 6's own wildcard/specificity rules, untouched),
so those capabilities simply never appear as `required_by_id` entries here —
Case F below.

---

## Only relevant capabilities appear in the output

`compute_capability_gaps` returns one `CapabilityGap` per capability in the
**union** of "has an applicable requirement" and "has at least one
observation" (participating or not) — not one row per all 34 taxonomy
capabilities. Most founders are never asked about most capabilities, and
most target contexts don't require most of them; manufacturing a row saying
"neither required nor assessed" for each would be noise, not information.
This union is exactly what makes `NOT_REQUIRED` (assessed but not required)
and `UNASSESSED` (required but not assessed) both surface correctly without
a third bookkeeping structure.

Output is sorted by `capability_code`, matching the ordering discipline
`resolve_requirements` and `assess_capabilities` already apply to their own
output.

---

## Traceability

Every `CapabilityGap` carries:

- `requirement_id`, `necessity` — the exact `capability_requirements` row
  Step 6's resolver selected (`None` exactly when `status == NOT_REQUIRED`);
  "why is this required" needs no re-resolution.
- `supporting_evidence_ids` — the `capability_evidence` row IDs that
  determined `current_level`, taken directly from
  `CapabilityAssessment.supporting_evidence_ids` (Step 7C); empty exactly
  when `status == UNASSESSED` or the capability was never assessed at all.

From either, the existing Step 7B/7C and Step 6 chains (`evidence_id` →
`answer_id`/`question_id`; `requirement_id` → the requirement row's own
stage/band/model/industry columns) complete the trace — nothing new is
introduced here.

---

## Determinism

Pure Python over two already-deterministic tuples: no randomness, no
insertion-order sensitivity (dict construction by `capability_id` key,
`set` union, final sort by `capability_code`), no LLM call anywhere in this
module. Verified directly against a matrix of real Step 6 requirement rows
across multiple revenue bands, business models, industries, stages, and time
horizons (`test_live_requirement_data_resolves_deterministically_across_a_context_matrix`),
and end-to-end through `DiagnosisRepository.capability_gaps_for_session`
against a real session (`test_live_data_end_to_end_through_the_repository`).

---

## Two worked examples (verbatim from the step brief)

**GTM-OWN: current = 1 (PERSONAL), required = 3 (OWNED) → GAP, size 2**

```python
requirement = RequiredCapability(capability_id=7, capability_code="GTM-OWN",
                                  required_level=CapabilityLevel.OWNED,       # 3
                                  necessity="required", rationale="stage requires owned sales motion",
                                  requirement_id=101, specificity=2, matched_on=("stage",))
assessment  = CapabilityAssessment(capability_id=7, capability_code="GTM-OWN",
                                    current_level=CapabilityLevel.PERSONAL,   # 1
                                    supporting_evidence_ids=(42,), considered_evidence_ids=(42,),
                                    excluded_evidence_ids=())

gap = compute_capability_gaps((requirement,), (assessment,), {7: "Sales Ownership"})[0]
# gap.status          == STATUS_GAP
# gap.required_level  == CapabilityLevel.OWNED       (3)
# gap.current_level   == CapabilityLevel.PERSONAL    (1)
# gap.gap_size        == 2
# gap.requirement_id  == 101
# gap.supporting_evidence_ids == (42,)
```

**FIN-UNIT: current = UNASSESSED, required = 2 (DOCUMENTED) → UNASSESSED, not a gap**

```python
requirement = RequiredCapability(capability_id=12, capability_code="FIN-UNIT",
                                  required_level=CapabilityLevel.DOCUMENTED,  # 2
                                  necessity="required", rationale="required at this revenue band",
                                  requirement_id=205, specificity=1, matched_on=("revenue_band",))
# no CapabilityAssessment for capability_id=12 at all -- no evidence was ever observed

gap = compute_capability_gaps((requirement,), (), {12: "Unit Economics"})[0]
# gap.status          == STATUS_UNASSESSED   (== capability_levels.UNASSESSED, "unassessed")
# gap.required_level  == CapabilityLevel.DOCUMENTED  (2)
# gap.current_level   is None
# gap.gap_size        is None   -- never computed; UNASSESSED is not a numeric comparison
# gap.requirement_id  == 205
# gap.supporting_evidence_ids == ()
```

Both are asserted directly in `test_gap_engine.py`'s golden-case section.

---

## Isolation from existing diagnosis

Nothing in this step touches question selection, the Top-5, applicability,
N/A handling, diagnosis scores, stage detection, root-cause ranking,
recommendations, business health, archetype, or report generation.
Verified structurally: `test_existing_module_has_no_dependency_on_the_gap_engine`
asserts that `app/api/v1/reasoning/engines/diagnostic.py`,
`app/api/v1/reasoning/engines/root_cause.py`, `app/api/v1/diagnosis/engine.py`,
and `app/api/v1/diagnosis/advisor.py` contain no reference to
`gap_engine`/`compute_capability_gaps`/`CapabilityGap` anywhere in their
actual code.

Both of Step 7B's and Step 7C's own boundary-guard tests
(`test_there_is_no_gap_table_yet`, `test_no_gap_is_generated_by_this_step`)
required **zero changes** for Step 8 to exist — confirming, the same way it
did after Step 7C, that the "no new table" design is what those tests were
actually guarding against, and it still holds.

---

## Intentionally not implemented (Step 9+)

- Gap prioritization or severity bucketing (low/medium/high)
- Recommendations or intervention selection conditioned on a gap
- Action plans or a 90-day roadmap
- Any founder-facing report change
- A persisted `detected_gaps` table (deliberately not built — see
  "Architecture" above)
