# Gap → intervention selection — Step 9B

PRIORITIZED CAPABILITY GAP (Step 9A) → EXISTING INTERVENTIONS. **Selection,
never creation.** This step returns intervention ids and content that already
exist in the library; it writes no intervention text, generates no prose, and
calls no model.

---

## Architecture: no new table

`app/api/v1/diagnosis/gap_intervention.py` is a pure function,
`select_interventions_for_gaps(gaps, interventions_by_capability, *, stage_id,
industry_code, relevance=None) -> GapInterventionSelection`, following the same
pattern as Steps 6, 7C, 8 and 9A. It holds no database handle, issues no query,
and performs no write.

```
PrioritizedCapabilityGap[]            [Step 9A, status == GAP only, ordered]
          |
          v
intervention_capabilities             curated map: 354 pairs over 328 of 417 interventions
          |
          v
eligibility (stage, industry)         the EXISTING relevance strategy, reused verbatim
          |
          v
InterventionCandidate[]  +  UncoveredGap[]
```

`DiagnosisRepository.intervention_candidates_for_session(session_id,
founder_context, target)` wires it up with exactly two bounded reads of its own
(`interventions_for_capabilities`, one `= ANY(:ids)` join; and
`stage_id_for_stage_order`, one row) on top of Step 9A's existing composition.
No N+1 regardless of how many capabilities are gapped.

---

## The capability → intervention relationship

`intervention_capabilities` is the only door this step uses: a curated junction
table (`intervention_id`, `capability_id`, composite PK) seeded by the Step 5
taxonomy migration from `interventions.capability_domain` via reviewed keyword
rules and then checked by hand. 354 pairs over 328 of 417 interventions. The
remaining 89 are deliberately unmapped — 75 are founder-psychology (out of
capability scope by design) and 14 are genuinely ambiguous. An unmapped
intervention is simply never selected; nothing infers a mapping for it.

**Step 9B is the first consumer of this table.** Nothing else in the codebase
queried it before, so there was no existing selection or ordering logic on this
path to duplicate or disturb.

---

## Intervention eligibility

Eligibility is **not reimplemented here**. `DefaultInterventionRelevance`
(`app/api/v1/reasoning/engines/recommendation.py`) is the repository's existing,
documented, injectable relevance test, and this module calls it rather than
copying it — so the two consumers of the intervention library can never drift
into disagreeing about what "relevant" means. A test
(`test_the_existing_recommendation_engine_is_not_replaced`) asserts the rule was
not copied, by checking that none of its internals (`_UNIVERSAL_INDUSTRY`,
`stage_ok`, `industry_ok`) appear in this module.

Its semantics, verified against the live library before any code was written:

| Field | Shape | Populated | Behaviour |
|---|---|---|---|
| `stage_relevance` | jsonb array of **stage_ids** | 417/417, 14 distinct arrays over stages 1–8 — genuinely discriminating | Fails **open**: an empty array, or an unknown founder stage, includes |
| `industry_relevance` | jsonb array of industry codes, or `["all"]` | 417/417, but `["all"]` on 412 of them | Fails **open** when the intervention is unrestricted; fails **closed** only when the intervention declares itself non-universal *and* the founder's industry is unknown |

### The one fail-closed case, stated plainly

When an intervention declares itself non-universal (5 rows today: `INT-376`,
`INT-378`, `INT-379` → `["saas"]`; `INT-062`, `INT-063` →
`["manufacturing","saas","services","ngo"]`) **and** the founder's industry is
unknown, the existing strategy withholds it. That is a deliberate product
decision the recommendation engine made after a B2B logistics founder was
handed SaaS-presupposing steps ("set up usage tracking for your next feature
launch") as his first action.

Reusing the strategy means **inheriting that decision** rather than writing a
second, quietly different industry rule. It is asserted explicitly in
`test_a_restricted_intervention_with_unknown_industry_is_withheld` rather than
left implicit. The dominant case is unaffected: 412 of 417 rows are universal,
so an un-onboarded founder loses nothing they would otherwise get — only rows
that were never meant to be universal.

### `stage_id` is looked up, not assumed

`interventions.stage_relevance` holds `founder_stages.stage_id`, while
`FounderContext` carries `stage_order`. The two coincide 1:1 in today's seed
data, and that coincidence is **not** relied on:
`DiagnosisRepository.stage_id_for_stage_order` performs a real lookup, so a
stage inserted or reordered later cannot silently mis-filter every
intervention. An unresolvable stage yields `None`, which fails open.

---

## What is *not* filtered on, and why

| Signal | Why not |
|---|---|
| **Business model** | **`interventions` has no business-model column at all** — verified column by column against the live schema. In this system `business_model` exists only on `founders` and on `capability_requirements`, which means business-model context already acted **upstream**, deciding which capability is required at all (Step 6's resolver). It has no authoritative expression at the intervention layer, so this step applies no business-model test: an unknown business model admits nothing extra, and a known one excludes nothing, because no metadata could justify either. Reported, not papered over. `test_the_intervention_library_still_has_no_business_model_column` asserts the column's absence, so the day someone adds it the test fails and forces a deliberate decision rather than a silent no-op. |
| **Question-level industry eligibility** | `questions.industry_relevance` is authoritative for whether a **question may be asked** (`industry_scope.py`); it says nothing about whether an **action applies**. Nothing crosses over. An intervention's own metadata is the only thing consulted. |
| **Root causes** | There is still no `capability_id ↔ root_cause_id` relationship anywhere in this codebase. None is invented here. |
| **`capability_domain`, `section`, `design_principles`, `framework_codes`** | Descriptive free text (`capability_domain` is ~390 near-unique labels across 417 rows). Never used as a filter anywhere in the codebase, and not made one here. |
| **`readiness_pillars` / `capabilities.pillar_id`** | `Capability.pillar_id` is explicitly documented as *"contextual metadata only… nothing gates on it"*. Pillar equality is not intervention applicability, and no new pillar scoring model is created. |

---

## Multi-capability interventions

26 of the 328 mapped interventions build exactly two capabilities each (the
maximum in the library is 2; a test asserts it stays ≤ 3, because an
intervention spread across many unrelated capabilities would make selection
meaningless).

When both of an intervention's capabilities are live gaps, the result is **one
`InterventionCandidate` carrying both supporting gaps** — never the same
intervention returned twice as two unrelated objects, which would lose exactly
the relationship worth surfacing.

```
INT-060  →  supports  FIN-PLAN (gap rank 1, size 3, core)
                      GTM-PIPE (gap rank 2, size 1, contextual)
```

Each `SupportedGap` keeps its **own** rank, `gap_size` and `necessity`, so
neither gap's priority is collapsed into the other's. Eligibility is evaluated
once per intervention (it depends only on the founder and the intervention, not
on the gap), so a shared row necessarily gets the same verdict on both paths —
and if it is filtered out, **both** gaps become uncovered rather than one
silently inheriting the other's coverage.

---

## No-intervention behaviour

A gap the library cannot currently serve returns `NO_INTERVENTION_AVAILABLE`
with enough metadata for content-gap analysis. **It never returns a generated
suggestion.** Two distinguishable reasons, because a library gap and a fit gap
are different problems:

| Reason | Meaning | `excluded_intervention_ids` |
|---|---|---|
| `no_mapped_intervention` | nothing in `intervention_capabilities` for this capability — a **library/mapping** gap | empty |
| `all_candidates_filtered` | content exists but none of it applies to this founder — a **fit** gap | the ids that were excluded |

This also covers section 17's cases B (a capability whose only interventions are
among the 89 unmapped ones presents identically to case A — nothing is mapped,
so nothing is selected) and D (metadata insufficient for an optional filter
never excludes; see "Unknown context" below).

---

## Unknown context behaviour

**A missing context signal means UNKNOWN, not CONTRADICTED.** An intervention
with an empty, `NULL` or absent `stage_relevance`/`industry_relevance` is
included, not excluded. An unknown founder stage filters nothing. An unknown
founder industry removes nothing from the 412 universal rows. The single
exception — a *restricted* intervention plus an unknown founder industry — is
the inherited fail-closed case documented above, and it is the intervention's
own declaration that triggers it, not an absence of data on our side.

Missing metadata never silently becomes `False`:
`test_missing_stage_metadata_does_not_silently_become_false` covers the empty
array, the `None`, and the unknown-founder cases explicitly.

---

## Deterministic ordering

No defensible ordering signal exists among the interventions for a single
capability: the library has **no priority, weight or severity column**;
`section` and `capability_domain` are descriptive; and the recommendation
engine's own ordering is derived from root-cause rank, which has no capability
join to borrow. So:

```python
candidates.sort(key=lambda c: (c.best_gap_rank, c.intervention_id))
```

- **`best_gap_rank`** — the rank of the highest-priority gap this intervention
  serves. Gap priority is **inherited**, never recomputed; intervention
  priority is not gap priority, and no second scoring system is introduced.
- **`intervention_id`** — a stable identifier, not an invented weight. This is
  the documented fallback the step brief asks for when no defensible ordering
  signal exists.

There is no numeric intervention score anywhere on the output
(`test_no_arbitrary_intervention_score_exists` asserts the absence of `score`,
`weight`, `confidence`, `severity`, `relevance_score`).

Determinism is otherwise structural: pure Python over already-fetched rows, no
model call, no embedding, no retrieval, no randomness.

---

## Relationship with the existing recommendation engine

**Step 9B does not replace it, and does not feed it.** The two reach the same
library through different doors:

| | Existing recommendation engine | Step 9B |
|---|---|---|
| Entry point | ranked root causes | prioritized capability gaps |
| Join | `interventions.root_cause_ids @> [code]` (jsonb codes) | `intervention_capabilities` |
| Priority | root-cause rank (Confidence Model) | inherited gap rank |
| Output | `Recommendation` (founder-facing, with prose rationale and `next_actions`) | `InterventionCandidate` (internal, no prose) |
| Shared | `DefaultInterventionRelevance`, and the `interventions` rows themselves | |

They coexist cleanly: 9B rewrites neither the engine nor its relevance
strategy, and nothing in the engine references 9B. Whether capability-driven
selection should eventually *feed* founder-facing recommendation generation is a
real integration question — and it is deliberately **not** answered here. Until
that integration is designed, the recommendation engine, report generation, the
roadmap and the UI must remain untouched.

---

## Intervention coverage (section 20)

Printed by `test_intervention_coverage_report` on every run:

```
intervention coverage: 34 capabilities, 354 mappings
zero coverage: none
thin (<=3): GTM-OWN 2, FND-INDEP 3, PRD-DELIVERY 3
broad (>=20): FIN-UNIT 20, GTM-SALES 23, GTM-ACQ 30
```

- **Zero coverage: none.** Every one of the 34 capabilities has at least one
  mapped intervention, so `no_mapped_intervention` cannot occur from the live
  library today. The test asserts this, so the day a capability is added
  without interventions it fails loudly.
- **Thin coverage persists.** `GTM-OWN` (2), `FND-INDEP` (3),
  `PRD-DELIVERY` (3), `OPS-QUALITY` (4) — the content gap
  `docs/CAPABILITY-TAXONOMY.md` already reported at Step 5 is still real, and
  now has a runtime consequence: **`GTM-OWN`'s only two interventions
  (`INT-056`, `INT-064`) are both `stage_relevance = [5,6,7,8]`**, so a founder
  below Growth with a `GTM-OWN` gap gets `NO_INTERVENTION_AVAILABLE` from real
  data. That is the honest answer, and it is the strongest argument yet for the
  content brief the taxonomy doc asked for.
- **Broad coverage** at the other end: `GTM-ACQ` (30), `GTM-SALES` (23),
  `FIN-UNIT` (20). Selection returns all eligible rows; nothing truncates them,
  because truncation would be prioritization, which is not this step's job.
- **No intervention is spread thin across unrelated capabilities**: the maximum
  is 2 capabilities per intervention, asserted at ≤ 3.

---

## Isolation

Nothing in this step touches question selection, the question budget, the
Top-5, applicability, diagnosis scores, stage detection, root-cause ranking,
the recommendation engine, business health, archetype, report generation, the
roadmap, or the UI. Verified structurally: none of `diagnostic.py`,
`root_cause.py`, `recommendation.py`, `business_health.py`, `engine.py`,
`advisor.py`, `gap_engine.py` or `gap_priority.py` references `gap_intervention`,
`select_interventions_for_gaps` or `InterventionCandidate`. The dependency runs
one way only.

Founder and session isolation is structural: the pure function has no founder
or session parameter at all, so it cannot mix two founders' data. Scoping is
guaranteed upstream by Step 8's session-scoped gap computation, exactly as it
already is for Steps 7C and 9A.

---

## Explicit non-goals (Step 9C+)

- Founder-facing recommendation prose, or any change to report generation
- Generating, rewriting or summarising intervention content
- A 90-day roadmap, milestones, deadlines or action sequencing
- An intervention score, severity band, or any re-prioritization of gaps
- Integration into the existing recommendation engine
- A persisted candidate table (deliberately not built — see "Architecture")
