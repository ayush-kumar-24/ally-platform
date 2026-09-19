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
| Honesty convention | A section with nothing true to put in it is **omitted and named** in `unpopulated_sections`; both renderers print *"Not included in this report: … Ally leaves a section out when it does not have enough to say something true there, rather than filling it in."* |
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
is the same mistake as handing them a sales CTA"); these sections follow that
rule, and on DISTRESS they are not named as "not included" either — they were
never in scope.

### Where and when they are computed

In `build_report_payload` — the reports layer only — via
`_capability_outputs(db, report)`, at **first narrative build**, then frozen
in the cached snapshot like every other section. `reasoning/service.py`'s
persistence path is untouched.

Contexts are built exactly as the diagnosis service builds them —
`FounderContext.from_founder(founder).with_session_facts(...)` and
`TargetStateContext.from_founder(founder)` — scoped by `report.founder_id`
and `report.session_id`, the same ids `_owned_report` already checks.

### No-state UX — the decision

The engines name several states in which there is nothing true for a founder
to read. Showing those as full sections with a raw `status` string was
inconsistent with the report's own convention, so the composition layer now
applies that convention — **the deterministic states are unchanged; only what
is rendered changed**:

| Engine state | What the founder gets | Why |
|---|---|---|
| `NO_TARGET_CONTEXT` | section omitted, named as *not included* | absent input (no stated destination), not diagnostic uncertainty |
| `AMBIGUOUS_REQUIREMENTS` | section omitted, named as *not included* | a curation error; the engine already logs it at warning for the people who can fix it — not a founder message |
| `NO_ACTIONABLE_TARGET`, zero gaps considered | section omitted, named as *not included* | nothing was diagnosed |
| `NO_ACTIONABLE_TARGET`, gaps considered > 0 | **kept, compact**: `gaps_identified: N`, `not_yet_addressable: [capability names]` | meaningful uncertainty — gaps found that the library cannot yet serve; codes and reason codes in `_provenance` |
| Resolved direction, trajectory empty, requirements unplaced | **kept, compact**: `required_but_not_yet_assessed: [names]` | the destination genuinely requires these; the founder should know what they are |
| Resolved direction, nothing to evolve, nothing unplaced | section omitted, named | nothing outstanding |
| A real target / a real trajectory | **kept** | content |

Raw enums and internal codes (`status`, `target_revenue_band`, `INT-` codes,
`necessity`, reason codes, `horizon_days`) are now **`_provenance`-only**.
Nothing deterministic is lost: every raw state remains in the JSON API and
the cached snapshot; only the founder-facing rows changed.

### Domain state vs system failure

| Situation | What happens |
|---|---|
| A named domain state | Rendered per the table above. Never hidden behind fallback prose, never turned into fake data. |
| Unexpected exception in an engine | Logged with `logger.exception` (an error, not a product state). That section is **omitted and named**; the rest of the report is unaffected. |

---

## Facts shape and provenance

Both renderers print only scalars and lists of scalars, and both skip
`_`-prefixed keys by documented convention ("for the machinery, not the
founder"). The sections use that convention:

- **Plain keys** — founder-facing: capability names, the library's own action
  steps, Step 5's own criteria, level labels, verbatim rationale. Never
  composed prose, never a raw enum, never a number the engines did not emit.
- **`_provenance`** — machine-facing: every id and every raw state the engines
  carry. Hidden from the document and the frontend, **kept in the JSON API
  and the cached snapshot**, so any section traces back to its rows.

### `twenty_day_target` — provenance of every field

| field | source | transformation | deterministic | persisted | founder-facing |
|---|---|---|---|---|---|
| `focus` | `capabilities.capability_name` via 10A | none | yes | snapshot | yes |
| `outcome` | `capabilities.description` via 10A | none | yes | snapshot | yes |
| `current_level` / `required_level` | `CapabilityLevel.label` | enum → label | yes | snapshot | yes |
| `focus_area` | `interventions.section` via 9B | none | yes | snapshot | yes |
| `actions` | `interventions.immediate_next_steps` via 10A | list of strings | yes | snapshot | yes |
| `success_after_20_days` | `capability_evidence_criteria.criterion_text` via 10A | list of strings | yes | snapshot | yes |
| `not_yet_addressable` | `SkippedGap.capability_id` → `capabilities.capability_name` | id → name | yes | snapshot | yes |
| `gaps_identified` | `TwentyDayTargetResult.considered_gap_count` | none | yes | snapshot | yes |
| `_provenance.*` | status, horizon, necessity, capability/intervention/requirement/criterion/evidence ids, ranks, sizes, integer levels, skipped-gap codes and reasons | none | yes | snapshot | **no** (API only) |

### `strategic_direction` — provenance of every field

| field | source | transformation | deterministic | persisted | founder-facing |
|---|---|---|---|---|---|
| `trajectory` | `capability_name`, `transition_label` (two `CapabilityLevel.label`s) | `"N. name: a -> b"` join | yes | snapshot | yes |
| `why_each_matters` | `capability_requirements.rationale` via Step 6 | `"N. rationale"` | yes | snapshot | yes |
| `required_but_not_yet_assessed` | `UnplacedRequirement` (10B) | `"name (needs: label)"` | yes | snapshot | yes |
| `_provenance.*` | status, target band/horizon (**never a milestone**), capability/requirement/evidence ids, integer levels, gap sizes, necessity, sequence | none | yes | snapshot | **no** (API only) |

No field is derived from intuition, an LLM, a constant the engines don't own,
or a hard-coded business assumption.

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
asserts the facts are byte-identical and the prose empty.

---

## Entitlement handling

`_visible_to` consults one table, `_GATED_SECTIONS`:

| Feature | withholds |
|---|---|
| `RECOMMENDATIONS` | `priority_actions` (unchanged) |
| `STRATEGIC_DIRECTION` | `strategic_direction` — **the sole feature gate for the new sections** |

The gates are independent. An entitled founder gets the cached narrative
object itself back — no copy, no recomputation. Applied at `/reports/{id}`,
`/document`, `/insights`, and `/export`. A section both omitted (no state)
and withheld is named once.

Verified against the catalog: **BASIC/₹199** → report + 20-day target;
**STARTER/₹499** and **PRO/₹999** → both. The engines contain no plan, tier,
price or feature reference (guarded structurally).

**`/export` never stores a plan-filtered PDF.** For a founder with withheld
sections the PDF is rendered for that download only, touching neither the
storage key nor the pending state.

### `/intelligence/reports/*` — classification

`GET /intelligence/reports/latest` and `/intelligence/reports/{id}` return
`ReportDetail` from `founder_reports` columns: `insights`, `founder_dna`,
`business_dna`, `top_root_causes`, `recommended_interventions`,
`confirm_actions`, `solve_actions`. Gated by `require_reports` only.

- **The new strategic-direction section cannot leak here.** It lives only in
  `narrative_snapshot`, which these endpoints never return (asserted by test).
- **Pre-existing exposure**: `confirm_actions` / `solve_actions` /
  `recommended_interventions` / `insights.priority_actions` carry the same
  recommendation content `_visible_to` withholds from `priority_actions`, so a
  BASIC or STARTER founder can read recommendations here that the report page
  refuses to show. **Severity: moderate** — a paid-tier boundary, but today
  FREE holds `RECOMMENDATIONS` pre-launch, so the practical exposure is
  founders on ₹199/₹499 seeing ₹999 content. Unrelated to this integration
  and **not made worse by it**. Left unchanged.
- **Follow-up recommendation**: apply the same `RECOMMENDATIONS` check to
  `ReportDetail` assembly (strip `confirm_actions`, `solve_actions`,
  `recommended_interventions`, and `insights.priority_actions` for founders
  lacking the feature), in its own change with its own tests.

---

## Snapshot / cache lifecycle

```
diagnosis completes
  → analyze_session (force=True on regeneration)
  → deactivate_existing_reports(session_id)        prior rows: is_active = False, snapshots untouched
  → _persist: NEW founder_reports row               narrative_snapshot NULL
  → _warm_report_narrative (best-effort) or first read
  → build_report_payload → _capability_outputs      10A/10B on the CURRENT diagnosis state
  → ReportNarrativeGenerator → sections + unpopulated_sections
  → narrative_snapshot written, cached forever for that report_id
```

- Existing snapshots are **not backfilled**; production data is not modified.
- Regeneration creates a **new** row and therefore a new snapshot.
- Unchanged diagnosis → equivalent deterministic output; changed diagnosis →
  changed output (asserted live by mutating evidence between two builds).
- Entitlement is evaluated **at read**: a downgrade hides the gated section;
  an upgrade reveals a section already present in the snapshot. No
  plan-specific persistence exists.

---

## Founder isolation

The pure engines take no founder or session; scoping happens once, in
`_capability_outputs`, from `report.founder_id` / `report.session_id`. A live
test gives two founders genuinely different destinations and their own
evidence on different capabilities, then asserts each direction's evidence
ids resolve only to that founder's own session. The narrative cache is per
`report_id`.

---

## Performance

Measured, not assumed: a live test counts SQL statements issued by
`_capability_outputs` for a founder with no destination and again for one
whose destination activates twenty requirements, and asserts the count is
bounded (≤ 24) and that the twenty requirements add no per-row loop (≤ 6
additional statements — the engines' own bounded `= ANY(:ids)` reads).

Because both entry points are reused as-is rather than re-wired, requirement
resolution and the evidence read each run twice — once per engine — **once
per report lifetime** (the narrative is cached). Accepted deliberately in
exchange for leaving Steps 10A and 10B untouched.

---

## What was not done, and why

- **No migration, no new table, no new column.**
- **No change to any engine** (Steps 5–10B), scoring, root-cause ranking,
  Business Health, stage semantics, industry relevance, or question selection.
- **No frontend change.** Every consumer renders the new sections and the
  "not included" note through its existing generic path.
- **No backfill of existing reports.**
- **No fix to `/intelligence/reports/*`** — pre-existing, classified above,
  recommended as a separate change.

---

## Existing tests edited (each strengthened, none weakened)

1. `test_all_three_founder_facing_routes_filter` pins the literal count of
   gated doors and did its job when `/export` became a third: 2 → 3, with a
   comment.
2. Steps 10A's and 10B's isolation guards dropped `reports/generator.py` from
   their lists because the composition layer is the intended consumer; the
   reverse direction (no engine imports the report layer) is now pinned in
   `test_report_capability_sections`.
