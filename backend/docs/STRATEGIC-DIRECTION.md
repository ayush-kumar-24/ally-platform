# 3-Year Strategic Direction — Step 10B

CURRENT CAPABILITY STATE (Step 7C) + TARGET-STATE REQUIREMENTS (Step 6) →
an **ordered capability trajectory**.

It answers: *"Given where this founder is today and what they are trying to
become, what capability evolution should they build toward?"*

---

## It is not a three-year plan

The product calls this the "3-Year Strategic Direction" because that is the
horizon a founder thinks on. **The engine attaches no time to anything.**

There is no year, quarter, month, date, milestone or schedule anywhere in the
module, and no field on its output could hold one — asserted structurally.
This is deliberate: the only horizon values this system holds are
`target_time_horizon` (6 or 12 months — a Step 6 requirement *lookup key*) and
Step 10A's fixed 20-day execution window. Neither is three years, so any
three-year schedule would be invented. That is the single largest fabrication
risk in this step, and the guard against it is that a schedule is not
representable.

It also does **not** produce: year-by-year task lists, quarterly milestones,
36-month execution plans, intervention schedules, arbitrary dates, fabricated
KPIs, invented capabilities, or invented strategic requirements.

---

## Architecture: no new table

`app/api/v1/diagnosis/strategic_direction.py` is a pure function,
`build_strategic_direction(gaps, requirements, capability_detail, target) ->
StrategicDirection`, plus a guarded `narrate_direction(...)`. No database
handle, no write, no model call in the core — following Steps 7C, 8, 9A, 9B
and 10A. Inspection established no persistence requirement.

`DiagnosisRepository.strategic_direction_for_session(session_id,
founder_context, target, *, narrator=None)` composes the chain and reuses
`capability_detail` (added for Step 10A) — no new query type.

```
FounderContext + TargetStateContext
        |
resolve_requirements(...)        [Step 6, called — never duplicated]
        |
compute_capability_gaps(...)     [Step 8, consumed]
        |
prioritize_capability_gaps(...)  [Step 9A, called for its ordering]
        |
        v
  StrategicDirection
```

---

## Deterministic inputs — every word is reference data

Nothing is composed, phrased or inferred:

| Part | Source | Note |
|---|---|---|
| What the capability is | `capabilities.capability_name` + `.description` | verbatim |
| Where the founder is | `CapabilityLevel.label` for the assessed level | existing code constant |
| Where they need to be | `CapabilityLevel.label` for the required level | existing code constant |
| **Why the destination needs it** | `capability_requirements.rationale` | verbatim — **55 rows, 55 distinct hand-authored explanations**, one per requirement |

That last row is why no generation is required. The strategic argument was
already written by a curator:

> *"The sales process has to be owned and improved by someone whose job it is,
> not maintained by the founder between other things."*

### The direction is the level transition

The capability scale measures exactly one axis — **founder dependence**:

```
0 absent → 1 founder-dependent → 2 documented → 3 owned by someone else
```

So "what must change" is fully expressed by the move from the current label to
the required one. `transition_label` joins two existing labels with an arrow
(`"founder-dependent -> owned by someone else"`). It asserts nothing the scale
does not already assert. `leaves_founder_dependence` reads the scale's own
`is_founder_dependent` property rather than inventing a threshold.

### Sources inspected and rejected

- **`founders.vision_1_year` / `goal_90_day`** — free-text onboarding answers.
  Founder prose, not canonical requirements, and unvalidated. The brief
  requires the direction to derive from canonical capabilities and
  target-state requirements, so these are not read.
- **`capability_domains.domain_order`** — Step 9A already established this is a
  display ordinal, not an importance ranking. Using it as the sequence
  tie-break would also put two contradicting orders in one product.
- **Root-cause rank / intervention priority** — explicitly not strategic
  capability importance; neither is referenced (guarded structurally).

---

## Target-state resolution

Step 6's resolver is **called, never duplicated**. The specificity cascade,
wildcard handling and tie-breaks all stay where they are; this module restates
none of them (guarded: `specificity`, `_pick(`, `_applies(`,
`from_stage_order` must not appear).

`target_revenue_band` and `target_time_horizon` decide **which** requirements
apply and are carried on the output so a reader knows which destination was
computed for. They are **never** turned into a number to hit or a date to hit
it by. A band of `5Cr_25Cr` selects requirements; it does not mean *"reach
₹10Cr by month 18"*, and no code path could say so.

### Unknown target context

Preserved exactly as Step 6 defines it. A measured consequence worth knowing:
**every one of the 55 seeded requirement rows constrains at least the revenue
band**, so a founder who has not stated a destination resolves *zero*
requirements and the result is `NO_TARGET_CONTEXT` — no trajectory, and
honestly so. A generic direction for an unstated destination would be invented.

### Ambiguity is preserved, not resolved

When two equally specific requirement rows disagree, Step 6 raises
`AmbiguousRequirementError` rather than picking one — and that raise aborts the
whole resolution. Step 10B **catches it at its own call site** (Step 6 is not
modified) and returns:

```python
StrategicDirection(status=AMBIGUOUS_REQUIREMENTS, trajectory=(), unplaced=(),
                   ambiguity="<the resolver's own message, verbatim>")
```

It never falls back to a guess, never silently drops the capability, and never
lets one undecidable row take a founder's whole diagnosis down.

---

## Output structure

```python
StrategicDirection
├── status            resolved | no_target_context | ambiguous_requirements
├── trajectory        tuple[CapabilityTrajectory, ...]   ordered
├── unplaced          tuple[UnplacedRequirement, ...]
├── target            the TargetStateContext this was computed for
├── ambiguity         the resolver's message, or None
└── narration         optional phrasing, or None

CapabilityTrajectory
├── capability_id / _code / _name / _description
├── current_level, required_level, gap_size, necessity
├── rationale                       the authored "why", verbatim
├── sequence                        reading order — NOT a dependency
├── requirement_id                  → Step 6
└── supporting_evidence_ids         → Step 7B/7C
   properties: current_level_label, required_level_label,
               transition_label, leaves_founder_dependence
```

Fields were kept to what the brief's chain actually needs. No
`already_at_target` collection exists, because a satisfied capability has no
evolution to describe and listing it would be a field added for how it sounds.

---

## Which capabilities appear

| Step 8 status | Result |
|---|---|
| `GAP` (current < required) | a `CapabilityTrajectory` entry |
| `UNASSESSED` (required, no confident reading) | an `UnplacedRequirement` — **named, never placed** |
| `SATISFIED` (equal **or** above required) | nothing — there is no evolution to describe |
| `NOT_REQUIRED` | nothing |

**UNASSESSED is never placed on the trajectory.** Stating a direction for it
would require asserting a current level nobody measured — the same rule Steps
7C, 8, 9A and 10A already hold: UNKNOWN is not a value. It is named instead, so
the capability does not silently vanish from the strategic picture.

**Exceeding a requirement is never a reverse trajectory.**

`required_level = 0` is a real, satisfiable requirement — not an absence of
one. With no evidence it is still `UNASSESSED`, never auto-satisfied.

---

## Sequencing rules — order, not dependency

**This is the rule the module guards hardest.** There is **no capability
dependency, prerequisite or causal-relationship data anywhere in this
codebase** — no such table, column or mapping. So `sequence` is a
deterministic reading order and nothing more, and must never be read as *"A
must happen before B"*.

`CapabilityTrajectory` deliberately carries no `depends_on`, `prerequisite`,
`blocks`, `blocked_by`, `unlocks` or `phase` field, so a dependency claim is
not representable here even by accident.

The ordering itself is **Step 9A's, reused by calling it**:

1. `necessity` — `core` before `contextual`
2. gap magnitude — larger gap first, within a necessity tier
3. `capability_id` — stable tie-break

That is items 1 and 2 of the brief's permitted ordering list, already
implemented, already tested, already documented — so no new scoring model was
introduced.

---

## Deterministic / LLM boundary

**Layer A** (`build_strategic_direction`) decides everything: which
capabilities, current and required levels, gaps, sequence, requirements,
evidence and target context. Its output is complete and usable on its own,
because every word in it is reference data.

**Layer B** (`narrate_direction` + a `DirectionNarrator`) may only rephrase.
The guarantee is **structural**: `DirectionNarration` carries `summary` and
`trajectory_lines` and **no identifier of any kind** — no capability id, no
level, no sequence, no requirement id. There is nothing in it capable of
changing a selection. On top of that, `narrate_direction`:

- catches every exception → the deterministic direction stands unchanged;
- treats `None` as a no-op;
- **discards** a narration whose line count differs from the trajectory length.

No narrator is wired by default, and none is required — there is no genuine
generation requirement here.

---

## Relationship to Step 10A

They are **siblings, not stages**. Both read the same capability state; neither
depends on the other.

| | Step 10A | Step 10B |
|---|---|---|
| Question | what to do in the next 20 days | what capabilities must evolve |
| Scope | **one** gap, with actions | **all** gapped capabilities, ordered |
| Uses interventions | yes (Step 9B) | **no** — never touches the library |
| Time | fixed 20-day window | **none at all** |
| Output | `TwentyDayTarget` | `StrategicDirection` |

Nothing in 10B reads, writes or waits on a 20-day target, and completing one
changes nothing here — asserted behaviourally by computing a direction,
building a 20-day target, and computing the direction again unchanged.

---

## Relationship to Steps 6–9

- **Step 6** — called for requirement resolution and each row's authored
  `rationale`. Not modified; its ambiguity is caught, not bypassed.
- **Step 7C** — consumed through Step 8's gaps; no aggregation logic restated.
- **Step 8** — consumed directly, all four statuses.
- **Step 9A** — called for ordering. No new scoring model.
- **Step 9B** — **not used at all.** Intervention priority is not strategic
  capability importance, and the module references no intervention concept.

Verified structurally across twelve modules: none of them references
`strategic_direction`, `StrategicDirection`, `build_strategic_direction` or
`CapabilityTrajectory`. The dependency runs one way only.

---

## Billing separation

The engine references no plan, tier, price, feature, subscription or
entitlement. Entitlement in this codebase is enforced at the router by a
FastAPI dependency (`app/api/v1/entitlement_gates.py` — *"APPLIED AT THE
ROUTER, NOT PER ENDPOINT"*), and no diagnosis engine checks it itself.

All plans that are shown a direction are shown one computed exactly this way;
whether to show it is a product/output-layer decision.

---

## Explicit non-goals

- Any time dimension: years, quarters, months, dates, milestones, schedules
- Task lists, intervention schedules, or a 36-month execution plan
- Causal dependency claims between capabilities
- Fabricated KPIs or numeric milestones derived from the revenue band
- Invented capabilities or invented strategic requirements
- Reading founder free-text vision fields as strategic requirements
- Persisting the direction
- Any founder-facing report, narrative or UI change
