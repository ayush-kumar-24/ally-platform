# Gap prioritization — Step 9A

CAPABILITY GAPS (Step 8) → PRIORITY ORDER. "Among the capabilities already
known to be below the target state, which deserve attention first" — and
nothing past that.

---

## What prioritization means, and what it does not

Prioritization here means: take the `CapabilityGap` rows that are already
`status == GAP` (Step 8 already decided that), and put them in one
deterministic order using a small set of documented, defensible factors.

It does **not** mean:

- Selecting an intervention (Step 9B).
- Writing founder-facing recommendation prose ("you should…").
- Building a 90-day roadmap, milestones, deadlines, or a task sequence.
- Assigning a severity label (`LOW`/`MEDIUM`/`HIGH`) to anything.
- Inventing a business-impact score from data that doesn't measure it.
- Re-deciding which capabilities are gaps — that decision belongs entirely
  to Step 8 and is never re-examined here.

---

## Architecture: no new table

`app/api/v1/diagnosis/gap_priority.py` is a pure function,
`prioritize_capability_gaps(gaps: tuple[CapabilityGap, ...]) ->
tuple[PrioritizedCapabilityGap, ...]`, following the same pattern as Step 6,
7C, and 8: the input is already computed and small (a session's capability
gaps, at most 34), so recomputing the order on every read is cheap and never
goes stale.

`DiagnosisRepository.prioritized_capability_gaps_for_session(session_id,
founder_context, target)` composes it with Step 8's own
`capability_gaps_for_session` — no new query, no new table.

```
CapabilityGap[]  (Step 8, all four statuses)
        |
        v
  filter: status == GAP only
        |
        v
  prioritize_capability_gaps(...)          [Step 9A]
        |
        v
  PrioritizedCapabilityGap[]  (ordered)
```

---

## What was inspected and rejected

Before writing any prioritization logic, every plausible existing priority
signal in the codebase was inspected for a genuine, deterministic,
semantically-defensible join to `capability_id`. None was found:

| Signal | Where | Why it was rejected |
|---|---|---|
| Root-cause `detection_score` / `detection_confidence` / `rank` | `app/api/v1/reasoning/engines/root_cause.py`, `schemas.py`'s `ScoredRootCause` | Measures evidence severity/confidence for a diagnostic *cause* keyed by `root_cause_id`/category. **No deterministic join from any root cause to a `capability_id` exists anywhere in the codebase.** Borrowing it would require inventing a mapping the product does not have — exactly what the step brief forbids. |
| Business Health score | `app/api/v1/reasoning/engines/business_health.py` | A founder-answer score over `readiness_pillars`, joined to `question → problem → pillar`. Its only link to `Capability` is `Capability.pillar_id`, which the model's own comment calls out as **"contextual metadata only… nothing gates on it"** (`app/models/capability.py`). Using a signal the schema itself disclaims as non-authoritative would be worse than using none. |
| Recommendation `priority` | `app/api/v1/reasoning/engines/recommendation.py` | Inherited directly from the root cause's Confidence-Model rank (same objection as above — no capability join). It does confirm the codebase's existing pattern of "priority flows from an upstream ranked engine, never invented locally," which this step follows in spirit without borrowing the numbers. |
| `intervention_capabilities` | `app/models/capability.py` (`InterventionCapability`) | A bare junction table (`intervention_id`, `capability_id`, `created_at`) — no weight, priority, or ordering column exists to borrow. |
| `capability_domain` / `domain_order` | `app/models/capability.py` (`CapabilityDomain`) | `domain_order` is a display/sequencing ordinal assigned at taxonomy creation, not a validated importance ranking. The taxonomy's own docstring calls domains "a shared vocabulary" — nothing claims one domain outranks another. |
| `readiness_pillars.pillar_weightage` | `app/models/schema.py` | Weights pillars for the Business Health score, not capabilities — same rejection as Business Health above. |
| `Problems.severity_min/max`, symptom `severity`, `category_risk_score` | various, `app/api/v1/reasoning/` | All scoped to Problems/categories, none carry a `capability_id`. |

`gap_engine.py`'s own docstring already states the conclusion this inspection
confirms: "no severity, no priority… no such taxonomy exists anywhere in this
codebase to borrow, and inventing one is explicitly out of scope."

**What is genuinely reusable, and used:** Step 6's own `necessity` column
(`capability_requirements.necessity`) — its docstring already says it exists
so "a later step can prioritise gaps without inventing a severity of its
own." This is the one signal placed in the schema for exactly this purpose,
and using it is reading data, not inventing a rule.

---

## The exact algorithm

1. **Filter**: keep only `gap.status == STATUS_GAP`. `UNASSESSED`,
   `SATISFIED`, and `NOT_REQUIRED` never enter the sort at all — they are
   removed before `priority_key` is even computed for them.
2. **Sort key**, ascending, three integers:

   ```python
   priority_key = (necessity_rank, -gap_size, capability_id)
   ```

   - `necessity_rank`: `core → 0`, `contextual → 1`. **Primary** factor —
     `core` (the target is unreachable without this capability, per Step 6's
     own semantics) always outranks `contextual` (matters in this context,
     but the destination is reachable without it), regardless of gap size.
   - `-gap_size`: **secondary**, tie-break within the same necessity tier
     only. A larger numeric distance from the target sorts first *among
     gaps that are equally load-bearing for reachability* — it never
     overrides `necessity`.
   - `capability_id`: **final, stable tie-break**, ascending, exactly as the
     step brief recommends — the one field guaranteed present, immutable,
     and totally ordered for every gap.

3. Sort ascending by that tuple; assign `rank` (1-based) in the resulting
   order.

### Why `gap_size` is not business impact

`gap_size = required_level - current_level` is a fact about the *distance
between two measurements* — how far the founder's current evidence is from
what the target state specifies. It says nothing about what breaks in the
business if that gap stays open. The step brief's own example makes this
explicit: current=0/required=3 is not automatically more important than
current=2/required=3. This module reflects that directly — `gap_size` never
outranks `necessity`, and is used only as the narrower, defensible claim
"among equally load-bearing gaps, the larger numeric distance is looked at
first," never as a stand-in for "this hurts the business more."

### Why there is no numeric priority score

`priority_key` is a plain 3-tuple of small integers — `(0 or 1, a negative
integer, a capability id)` — not a blended 0–100 score. There are no
weights to document because there is no weighted formula: the three factors
are applied in strict lexicographic order (necessity always decides first;
gap_size only breaks a necessity tie; capability_id only breaks a
gap_size tie), never combined arithmetically. Nothing here is presented, or
could be mistaken for, a "Founder Score" — `priority_reasons` exists
specifically to make the ordering legible as three named facts, not a
mystery number.

---

## Unknown handling

Every `CapabilityGap` with `status == GAP` was built by `gap_engine.py`'s
`_compare` from a real `RequiredCapability` (so `necessity` is always one of
`core`/`contextual` — enforced by the Step 6 migration's `CHECK
(necessity IN ('core', 'contextual'))`) and a real numeric `current_level`
(so `gap_size` is always a concrete integer). **Neither factor can be
missing for a GAP row, by construction** — there is no live case in which
this module would need to substitute a default for an absent signal. If a
`necessity` value outside the known two ever appeared (a future schema
change, not possible today), `_priority_key` raises `ValueError` rather than
defaulting it into an arbitrary sort position — the same "never turn unknown
into zero" discipline the rest of this system already applies, expressed as
"never turn unknown into a silent default" here since there is no unknown
case in the data today to actually default.

No other candidate signal (business impact, root-cause linkage) is used at
all — see "What was inspected and rejected" above — so there is nothing else
that could be silently defaulted.

---

## Why UNASSESSED is excluded, restated

An `UNASSESSED` capability means "insufficient evidence," not "this is
fine" and not "this is a problem." Including it in a priority list — even at
the bottom — would imply the system has an opinion about how urgent an
*unknown* is, which it does not and must not claim to have. It is simply
absent from this function's output, exactly as it is absent from Step 8's
"this is a problem" framing.

---

## Separation from intervention selection (Step 9B)

`gap_priority.py` never queries `interventions` or `intervention_capabilities`
and never imports anything from a future intervention-selection module — it
answers "in what order to look at these gaps," not "what to do about them."
`PrioritizedCapabilityGap` has no `intervention_id`, no recommendation text,
no roadmap field. Verified structurally by
`test_no_intervention_is_selected`, `test_no_recommendation_prose_is_generated`,
and `test_no_roadmap_is_generated` in `tests/test_gap_priority.py`.

---

## Determinism

Pure Python over an already-deterministic input tuple: a total order over
three integers has exactly one sorted result regardless of input order,
verified by `test_insertion_order_does_not_change_the_result` (forward,
reversed, shuffled). No LLM, no embeddings, no RAG, no randomness anywhere in
this module — verified by `test_no_llm_is_imported`.

---

## Traceability

`PrioritizedCapabilityGap` carries `requirement_id` and
`supporting_evidence_ids` straight through from the input `CapabilityGap` —
unchanged, not re-derived — so "why is this gap here, and why does it rank
where it does" is answerable from the object alone: `priority_reasons` names
the three factors, and the two traceability fields point back into Step 6
and Step 7B/7C exactly as they already did in Step 8.

---

## Isolation from existing diagnosis

Nothing in this step touches question selection, the Top-5, applicability,
diagnosis scores, stage detection, root-cause ranking, the recommendation
engine, business health, archetype, or report generation. Verified
structurally: none of `diagnostic.py`, `root_cause.py`, `recommendation.py`,
`business_health.py`, `engine.py`, or `advisor.py` reference `gap_priority`,
`prioritize_capability_gaps`, or `PrioritizedCapabilityGap` anywhere in their
source. `gap_engine.py` itself is also unchanged by this step — the
dependency runs one way only, `gap_priority.py → gap_engine.py`.

---

## Intentionally not implemented (Step 9B+)

- Intervention selection or `intervention_capabilities` queries
- Founder-facing recommendation prose
- A 90-day roadmap, milestones, deadlines, or task sequencing
- Severity labels (`LOW`/`MEDIUM`/`HIGH`) anywhere
- A numeric 0–100 "priority score" or any presentation of one as a
  "Founder Score"
- A persisted priority table (deliberately not built — see "Architecture"
  above)
