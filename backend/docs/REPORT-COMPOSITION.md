# Founder Report composition — Steps 10A and 10B as report sections

The 20-Day Target (Step 10A) and the 3-Year Strategic Direction (Step 10B)
enter the Founder Report as **two additive sections on the existing
mechanism**. Nothing about the report's schema, serialisation, persistence,
cache, renderers, or existing sections changes.

```
Existing Diagnosis  +  Capability State  +  Gap State  +  20-Day Target  +  Strategic Direction
                                        = Founder Report
```

The engines are parallel diagnostic views. Neither depends on the other, and
neither depends on root causes; root causes and Business Health do not depend
on them. That is the existing architecture, and it is preserved.

---

## What was found (the audit)

| | Finding |
|---|---|
| Generation | `ReasoningService.analyze_session` → `FounderReport` DTO → one `founder_reports` row (`insights`, `business_dna`, `founder_dna`, actions). Background task on diagnosis completion. |
| Narrative | Built on **first read** from DB columns by `build_report_payload` → `ReportNarrativeGenerator` → `Section{key, heading, prose, facts}` → cached **forever** in `founder_reports.narrative_snapshot`. No version field. |
| Schema | `ReportView.sections: list[SectionOut]`, `SectionOut.facts: dict` — an **open dict by design**. |
| Consumers | Plain-JS frontend, no schema validation, sections iterated generically; primary view is the server-rendered HTML (`/document`), which renders **unknown section keys generically** (heading from key, prose + facts). Same renderer for the PDF. No generated client. |
| Entitlement | `_visible_to()` strips section keys into `unpopulated_sections` **"at READ, not at generation"** using `EntitlementService.has_feature(founder.plan_type, Feature.X)`. Previously gated one section (`priority_actions` ↔ `RECOMMENDATIONS`). |
| Capability content | Appeared **nowhere** in either report layer before this change. |

Two things were materially different from the brief's expectations and were
decided explicitly before any code was written:

1. **No existing `Feature` meant "strategic direction".** `_WORKSPACE`
   (the ₹499 boundary) held only chat/workspace features; reusing one would
   change an existing enum's meaning. → `Feature.STRATEGIC_DIRECTION` was
   **added to the existing catalog's `_WORKSPACE` set** — one enum member,
   one set entry, the existing `EntitlementService` reused unchanged. The
   20-Day Target needs **no** feature: the reports router already requires
   `Feature.REPORTS`, which is exactly every paid tier.
2. **`_visible_to` was applied on only two of the founder-facing doors.**
   `/insights` and `/export` (PDF) returned gated `priority_actions` ungated —
   a pre-existing leak. → Both doors are now gated through the same seam, which
   fixes the existing leak as a side effect (documented, deliberate).

---

## The two new sections

Both ride `Section{key, heading, prose, facts}`:

| key | heading | source |
|---|---|---|
| `twenty_day_target` | Your 20-day target | `DiagnosisRepository.twenty_day_target_for_session` (Step 10A, unchanged) |
| `strategic_direction` | Where this is heading | `DiagnosisRepository.strategic_direction_for_session` (Step 10B, unchanged) |

They are placed after the existing action sections and before the CTA, on
every **non-DISTRESS** variant. The DISTRESS variant deliberately carries no
execution content ("handing a founder in distress a sequenced execution plan
is the same mistake as handing them a sales CTA"), and these sections follow
that existing rule.

### Where and when they are computed

In `build_report_payload` — the reports layer only — via
`_capability_outputs(db, report)`, at **first narrative build**, then frozen
in the cached snapshot like every other section. `reasoning/service.py`'s
persistence path is untouched.

Contexts are built exactly as the diagnosis service builds them —
`FounderContext.from_founder(founder).with_session_facts(...)` and
`TargetStateContext.from_founder(founder)` — scoped by `report.founder_id`
and `report.session_id`, the same ids `_owned_report` already checks.

**Already-generated reports do not gain the sections** (their snapshot is
cached, and production data is not modified). The existing admin regeneration
path writes a fresh report row that will carry them.

### Domain state vs system failure

| Situation | What happens |
|---|---|
| `NO_ACTIONABLE_TARGET`, `NO_TARGET_CONTEXT`, `AMBIGUOUS_REQUIREMENTS`, unplaced requirements | **Expected domain states**, returned by the engines inside a populated result. Shown as an explicit `status` fact (and the resolver's own `ambiguity` message). Never hidden behind fallback prose. |
| Unexpected exception in an engine | Logged with `logger.exception` (an error, not a product state). That section is **omitted**; the rest of the report is unaffected. |
| Engine did not run | `None` → the facts builder returns `{}` → the section is omitted, never invented. |

---

## Facts shape and provenance

Both renderers print only scalars and lists of scalars, and both skip
`_`-prefixed keys by documented convention ("for the machinery, not the
founder"). The sections use that convention:

- **Plain keys** — founder-facing: capability names, the library's own action
  steps, Step 5's own criteria, level labels, verbatim rationale. Never
  composed prose, never a number the engines did not emit.
- **`_provenance`** — machine-facing: every id the engines carry. Hidden from
  the document and the frontend, **kept in the JSON API and the cached
  snapshot**, so any section traces back to its rows.

### `twenty_day_target` — provenance of every field

| field | source | transformation | deterministic | persisted | founder-facing |
|---|---|---|---|---|---|
| `status` | `TwentyDayTargetResult.status` | none | yes | snapshot | yes |
| `horizon_days` | `TwentyDayTarget.horizon_days` (`HORIZON_DAYS = 20`) | none | yes | snapshot | yes |
| `focus` | `capabilities.capability_name` via 10A | none | yes | snapshot | yes |
| `outcome` | `capabilities.description` via 10A | none | yes | snapshot | yes |
| `current_level` / `required_level` | `CapabilityLevel.label` | enum → label | yes | snapshot | yes |
| `necessity` | `capability_requirements.necessity` via Step 6 | none | yes | snapshot | yes |
| `intervention` / `intervention_section` | `interventions.intervention_code` / `.section` via 9B | none | yes | snapshot | yes |
| `actions` | `interventions.immediate_next_steps` via 10A | list of strings | yes | snapshot | yes |
| `success_after_20_days` | `capability_evidence_criteria.criterion_text` via 10A | list of strings | yes | snapshot | yes |
| `skipped_higher_priority_gaps` / `why_no_target` | `SkippedGap.capability_code` + `.reason` | `"CODE: reason"` join | yes | snapshot | yes |
| `gaps_considered` | `TwentyDayTargetResult.considered_gap_count` | none | yes | snapshot | yes |
| `_provenance.*` | capability/intervention/requirement/criterion/evidence ids, ranks, sizes, integer levels | none | yes | snapshot | **no** (API only) |

### `strategic_direction` — provenance of every field

| field | source | transformation | deterministic | persisted | founder-facing |
|---|---|---|---|---|---|
| `status` | `StrategicDirection.status` | none | yes | snapshot | yes |
| `target_revenue_band` / `target_time_horizon` | `founders.*` via `TargetStateContext` | none — **never a milestone** | yes | snapshot | yes |
| `trajectory` | `capability_name`, `transition_label` (two `CapabilityLevel.label`s), `necessity` | `"N. name: a -> b (necessity)"` join | yes | snapshot | yes |
| `why_each_matters` | `capability_requirements.rationale` via Step 6 | `"N. rationale"` | yes | snapshot | yes |
| `required_but_not_yet_assessed` | `UnplacedRequirement` (10B) | `"name (needs: label)"` | yes | snapshot | yes |
| `ambiguity` | `AmbiguousRequirementError` message via 10B | none | yes | snapshot | yes |
| `_provenance.*` | capability/requirement/evidence ids, integer levels, gap sizes, sequence | none | yes | snapshot | **no** (API only) |

No field is derived from intuition, an LLM, a constant the engines don't own,
or a hard-coded business assumption. No field without an authoritative source
was added.

---

## UNASSESSED safety

Step 10B's `unplaced` requirements land under `required_but_not_yet_assessed`
— never in `trajectory`, never counted as gaps, never described as a
weakness. `_provenance.unplaced` is kept separate from `_provenance.trajectory`.
A test asserts no founder-facing key for this section contains the word "gap".

---

## LLM boundary

The sections are emitted with **empty slots**, so neither the template
narrator nor an LLM narrator writes a word for them (`prose` is `""`). A
narrator only ever returns prose — it has no path to `facts` — so the
deterministic fields are unreachable by construction. A test drives
`LLMSectionNarrator` with an LLM that returns an invented revenue claim and
asserts the facts are byte-identical and the prose empty. No LLM was
introduced to make the report sound better.

---

## Entitlement handling

`_visible_to` now consults one table, `_GATED_SECTIONS`:

| Feature | withholds |
|---|---|
| `RECOMMENDATIONS` | `priority_actions` (unchanged) |
| `STRATEGIC_DIRECTION` | `strategic_direction` |

The gates are independent (a founder may hold either without the other). An
entitled founder gets the cached narrative object itself back — no copy, no
recomputation. Applied at `/reports/{id}`, `/document`, `/insights`, and
`/export`.

**`/export` never stores a plan-filtered PDF.** The stored copy is per report,
not per plan; the backfill sweep renders it full with no founder in scope, and
the route serves the stored copy first. Storing a filtered one would hand a
founder who later upgrades a stale, truncated document. So for a founder with
withheld sections the PDF is rendered for that download only, touching
neither the storage key nor the pending state.

Tier outcome, from the existing catalog: **BASIC/₹199** → report + 20-day
target; **STARTER/₹499** and **PRO/₹999** → both. The engines contain no
plan, tier, price or feature reference (guarded structurally).

Share views (`/reports/shared/{token}`) are unchanged: they already serve
prose only, and these sections have no prose.

---

## Founder isolation

The pure engines take no founder or session; scoping happens once, in
`_capability_outputs`, from `report.founder_id` / `report.session_id`. A live
test gives founder A a stated destination and confident evidence and founder
B neither, and asserts B's sections show none of A's state. No cache is
shared across founders: the narrative cache is per `report_id`.

---

## Performance

No N+1. Each engine entry point is the existing repository composition
(bounded `= ANY(:ids)` reads). Because both entry points are reused as-is
rather than re-wired, requirement resolution and the evidence read each run
twice — once per engine — **once per report lifetime** (the narrative is
cached). That is a bounded, one-time cost accepted deliberately in exchange
for leaving Steps 10A and 10B untouched.

---

## What was not done, and why

- **No migration, no new table, no new column.** Sections persist through
  the existing snapshot.
- **No change to any engine** (Steps 5–10B), scoring, root-cause ranking,
  Business Health, stage semantics, industry relevance, or question selection.
- **No frontend change.** Every consumer renders the new sections through
  its existing generic path.
- **No backfill of existing reports.** Production data is not modified.

---

## Known risks and product notes

1. **Most reports will show explicit no-state sections today.** With
   `CAPABILITY_EVIDENCE_EXTRACTION` off by default and most founders having
   no `target_revenue_band`, the sections read "status: no_actionable_target"
   / "status: no_target_context" for most founders. That is the correct,
   honest state — but the product layer may prefer to hide a section whose
   status is a no-state. That is a product decision, not made here.
2. **`/intelligence/reports/*`** returns raw `confirm_actions`/`solve_actions`
   without `_visible_to`. Pre-existing; not touched; noted for the entitlement
   owner.
3. **One existing test was edited**: `test_all_three_founder_facing_routes_filter`
   pins the literal count of gated doors and did its job when `/export` became
   a third. The count was updated from 2 to 3 with a comment; the guard is
   stronger, not weaker.
