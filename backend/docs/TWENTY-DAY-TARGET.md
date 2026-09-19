# 20-Day Target — Step 10A

PRIORITIZED CAPABILITY GAPS (Step 9A) + ELIGIBLE INTERVENTIONS (Step 9B) →
**one** focused 20-day execution target.

It answers: *"What is the most useful concrete progress this founder should
make over the next 20 days, based on the diagnosis?"*

It is **not** a 90-day roadmap, not a generic to-do list, not a business
strategy, not a 3-year direction, and not a brainstorming exercise.

---

## Purpose and scope

One target. Depth over breadth. The pipeline already decided which gaps matter
most (Step 9A) and which of them the library can act on (Step 9B); this step
takes the first gap that is both and states what "done" looks like in 20 days.

It does **not** try to fix every diagnosed gap. Gaps that outranked the
selected one but had nothing to act on are preserved on the record as
`skipped_gaps` — they are never deleted and never fabricated around.

---

## Architecture: no new table

`app/api/v1/diagnosis/twenty_day_target.py` is a pure function,
`build_twenty_day_target(...) -> TwentyDayTargetResult`, plus a separate
`narrate_target(...)` for the optional generative edge. No database handle, no
write, no model call in the core. This follows Steps 7C, 8, 9A and 9B —
inspection established no persistence requirement, so nothing is stored.

`DiagnosisRepository.twenty_day_target_for_session(session_id,
founder_context, target, *, narrator=None)` composes the chain and adds three
bounded reads of its own (`capability_detail`, `capability_criteria`,
`intervention_steps`), all `= ANY(:ids)`, no N+1. Step 9B's own query and its
deliberately content-free `InterventionCandidate` are left untouched.

---

## Why every field is deterministic

The inspection question was whether the intervention library carries enough to
derive an objective, actions, an expected outcome and a measurement. It does —
across three tables — so **nothing in the core needs a model**:

| Part of the target | Source | Status |
|---|---|---|
| **Objective / outcome** | `capabilities.capability_name` + `.description` | verbatim reference data |
| **Actions** | `interventions.immediate_next_steps` | verbatim; populated on **417/417** rows, 1–4 steps each |
| **Success / measurement** | `capability_evidence_criteria` | verbatim; exactly **4 per capability**, 136 total |
| **Horizon** | fixed constant | 20 days |

Actions are copied exactly as the existing recommendation engine already
copies the same column into `Recommendation.next_actions`
(`engines/recommendation.py:236-238`) — this is the established pattern, not a
new one.

**What was missing:** interventions carry no duration, no success condition,
no measurement and no outcome-as-such field. All three of those gaps are
filled from *other* authoritative tables (capability, criteria) rather than by
generation.

---

## Target vs. action

The two are read from **different tables** so they cannot be conflated:

- **TARGET** = the capability outcome — `GTM-SALES`, *"Repeatable Sales
  System"*, *"A defined, teachable sales process rather than a series of
  improvisations."*
- **ACTIONS** = the selected intervention's steps toward it — *"Build one
  reusable proposal template…"*, *"Start tracking why each proposal is
  accepted or rejected…"*

"Create a document" is therefore never the strategic target unless
documentation genuinely is the capability outcome, because the outcome is
never read off an intervention.

---

## Primary-target selection

1. Walk Step 9A's ordering by `rank`.
2. **Actionable** = Step 9B produced at least one eligible intervention for
   that capability (`selection.covered_capability_ids`).
3. The first actionable gap becomes the primary target.
4. Every gap that outranked it and was *not* actionable is recorded as a
   `SkippedGap` carrying its rank, gap size, necessity, Step 9B's own reason
   (`no_mapped_intervention` vs `all_candidates_filtered`) and the excluded
   intervention ids.
5. Gaps *below* the selected one are not listed as skipped — they were never
   reached, because 20 days holds one target.

The intervention itself is the **first candidate serving the primary
capability in Step 9B's existing order** (`(best_gap_rank, intervention_id)`).
No new ordering signal is introduced, because there is none in the library to
introduce — the same finding Steps 9A and 9B already documented.

### The fallback, with real data

This is the step brief's own example, and it happens for real:

```
Priority 1  GTM-OWN    → NO_INTERVENTION_AVAILABLE   (its only 2 interventions,
                                                      INT-056 and INT-064, are
                                                      stage_relevance [5,6,7,8])
Priority 2  GTM-SALES  → eligible interventions       → 20-Day Target
```

At stage 3 the founder's most urgent gap cannot be acted on, so the target is
built on GTM-SALES — and GTM-OWN stays on the record with
`reason="all_candidates_filtered"` and `excluded_intervention_ids=(56, 64)`.
It did not disappear.

---

## Interventions remain authoritative

The selected intervention is the action strategy. This engine may structure,
sequence and (optionally) rephrase it. It may never replace it or silently
substitute a different one. Every `TargetAction` carries
`source_intervention_id`, so no action can exist without a library row behind
it — which is what makes generic advice ("improve marketing", "talk to more
customers") structurally impossible here.

---

## Deterministic core, optional generative edge

**Layer A — deterministic** (`build_twenty_day_target`) decides: which gap,
which capability, which intervention, why, which higher-priority gaps were
skipped and why, which evidence criteria apply, and the 20-day horizon. Its
output is already complete and usable, with real text throughout.

**Layer B — optional** (`narrate_target` + a `TargetNarrator`) may only
rephrase into founder-friendly wording.

The guarantee is **structural, not procedural**: `TargetNarration` carries
`focus`, `why_now`, `actions` and `success` — and **no identifier of any
kind**. No capability id, no intervention id, no level, no criterion id. There
is literally nothing in it that could redirect the target. On top of that,
`narrate_target`:

- catches every exception → the structured target stands unchanged;
- treats `None` as a no-op;
- **discards** a narration whose action count differs from the target's, since
  dropping or adding steps is rewriting the intervention — Layer A's decision,
  not the narrator's.

No narrator is wired by default. Layer A alone is the product behaviour.

---

## Success and evidence semantics

Success criteria **are** Step 5's evidence criteria, carried with their
`criterion_id`s. No second evidence taxonomy was created, because one already
existed and it is written exactly right for this purpose — observable
statements that answer *"did this happen?"*:

```
GTM-SALES — Repeatable Sales System
  [9]  A sales process exists and is written down
  [10] The same steps are followed across deals
  [11] Objections have prepared responses
  [12] A new seller could follow the process without the founder
```

**No fabricated numeric KPIs.** All 136 seeded criteria are qualitative — a
test asserts none contains a digit, so a target built from them cannot promise
"increase revenue by 30%" even in principle.

### The loop this closes

Carrying `criterion_id` is the strategic point:

```
Diagnosis → 20-Day Target (collect evidence for criteria 9-12)
          → founder executes
          → next answers
          → Step 7B extractor cites those same criterion_ids
          → Step 7C may read a higher level
          → re-diagnosis
```

One vocabulary end to end.

### Completion is **not** evidence

Finishing the 20 days does **not** mutate `current_level` and does **not**
write `capability_evidence`. Only a later founder answer, read by Step 7B, can
establish improvement. The engine has no writable path to either — asserted
structurally, and live by comparing row counts before and after a call.

Likewise, the target never promises *"you will reach Level 2 in 20 days."*
`current_level` and `required_level` are carried for context; the target moves
toward the requirement, and only later evidence can say whether it arrived.

---

## Multi-capability interventions

26 of the 328 mapped interventions build two capabilities. When the selected
intervention genuinely serves two live gaps, the target retains both in
`supporting_capability_ids` (and `is_joint` is true) — **but one capability
remains the primary rationale**, chosen by gap rank.

Unrelated gaps served by *different* interventions are never bundled: a target
built on capability A with its own intervention carries
`supporting_capability_ids == (A,)`, even when capability B is also gapped.
Breadth is never manufactured to make the output look comprehensive.

---

## `NO_ACTIONABLE_TARGET`

When no prioritized gap has an eligible intervention, the result is:

```python
TwentyDayTargetResult(
    status=NO_ACTIONABLE_TARGET,
    target=None,
    skipped_gaps=(...every gap considered, each with its reason...),
    considered_gap_count=N,
)
```

Nothing is asked to make something up. The skipped gaps carry Step 9B's own
reasons, which is exactly the content-gap signal worth escalating.

---

## Traceability

Two chains, both complete from the target object alone:

```
Target → source_intervention_id      → intervention
       → primary_capability_id, gap_rank, gap_size, necessity, current_level
                                      → gap (Step 8/9A)
       → supporting_evidence_ids      → capability_evidence (Step 7B/7C)

Target → requirement_id               → capability_requirements (Step 6)
```

---

## The horizon is 20 days, and is not configurable

No plan object in this codebase carries a duration field: `app/planning/` dates
individual goals and tasks, and the report's *"Your next 2 weeks"* is a literal
heading string, not a duration. So nothing in the existing architecture asks
for a generic horizon here, and `HORIZON_DAYS = 20` is a module constant — not
a setting.

**`target_time_horizon` is a different concept entirely.** That is the
founder's 6/12-month *ambition*, used by Step 6 as a lookup key for which
requirements apply. It is never an execution window, and the two must not be
conflated.

---

## Plan independence

The engine contains **no** reference to plans, tiers, prices, features or
entitlement. That is the codebase's own convention: entitlement is enforced at
the router by a FastAPI dependency (`app/api/v1/entitlement_gates.py` —
*"APPLIED AT THE ROUTER, NOT PER ENDPOINT"*), and no diagnosis or reasoning
engine checks it itself.

All three paid plans (₹199 / ₹499 / ₹999) consume this same engine unchanged.
Composition — which plan sees what — belongs at the product/output layer, and a
future router-level gate (most plausibly `Feature.NEXT_STEPS` or
`Feature.RECOMMENDATIONS`) is where it would go.

---

## Separation from the 3-Year Strategic Direction (Step 10B)

Step 10B is **not implemented**. Nothing here produces, references or reserves
a multi-year direction; a test asserts the engine's code mentions no
year/quarter/month/roadmap/milestone concept at all, and that
`TwentyDayTarget` has no field that could hold one. The 20-Day Target is a
core diagnosis output for all three paid plans; the 3-Year Direction is a
separate output for ₹499 and ₹999, to be built separately.

---

## Isolation

Nothing in this step touches question selection, the question budget,
applicability, diagnosis scores, stage detection, root-cause ranking, the
recommendation engine, business health, archetype, report generation, the
planning domain, or the UI. Verified structurally across ten modules including
`gap_engine.py`, `gap_priority.py`, `gap_intervention.py` and both report
generators — the dependency runs one way only.

---

## Explicit non-goals (Step 10B+)

- The 3-Year Strategic Direction
- Any founder-facing report, narrative or UI change
- A 30/60/90-day plan, milestones, deadlines or task sequencing
- Writing into `app/planning/` (Plan/Goal/Task) — a possible future seam, not
  this step
- Plan/tier entitlement inside the engine
- Persisting the target
