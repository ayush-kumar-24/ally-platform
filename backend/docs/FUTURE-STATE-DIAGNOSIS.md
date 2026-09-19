# Future-State Diagnosis — engineering design proposal

**Status: DESIGN ONLY. Nothing in this document is implemented.**
Read-only pass over the repository at `49966757`. Every claim about what exists
was checked against the code or the database and is marked accordingly.

Ally answers *"where is this founder today?"*. This proposes the layer that
answers *"where do they want to take the company, what must be true there, what
is missing, and what should they build next?"*

---

## 1. Current architecture (verified)

Deterministic eligibility first, LLM selection second. Five gates remove
questions; none of them ranks.

```
questions (3,460)
  └─ repository.list_candidate_questions   stage group + already-answered
     └─ _applicability_gated               tag preconditions      [Step 4, new]
        └─ _context_gated                  fundraising intent
           └─ _industry_gated              questions.industry_relevance
              └─ stage scope               category / pillar / dimension
                 └─ order_candidates       round-robin + _sort_key
                    └─ [:5]                ADAPTIVE_SHORTLIST_SIZE
                       └─ LLM advisor      picks exactly one
```

Reasoning runs once at the end, in this order (from `_log_stage` calls in
`app/api/v1/reasoning/service.py`):

`load_inputs → diagnosis (category scoring + stage_detection + symptom_detection)
→ distress_detection → psychological_state → root_cause (+ RAG enrichment) →
answer_consistency → confidence → recommendation → business_health → archetype →
report_generation`

Controlled vocabularies that already exist and are populated:

| Table | Rows | Note |
|---|---|---|
| `readiness_pillars` | 6 | Founder Readiness, Market Clarity, Revenue Maturity, Product & Execution, Team & Leadership, Strategic Clarity |
| `problems` | 273 | carries `industry_relevance` |
| `root_causes` | 2,009 | carries `industry_relevance` |
| `interventions` | 417 | carries `stage_relevance`, `industry_relevance`, `section`, `capability_domain` |
| `industries` | 30 | |
| `founder_stages` | 8 | |
| `questions` | 3,460 | carries `industry_relevance`, `primary_stage_group` |
| `business_dimensions` | **0** | table exists, never populated |

---

## 2. Step-4 implementation status — **complete**

| Requirement | Status |
|---|---|
| A. Question preconditions from real tags | Done. `question_tags.precondition_token` (migration `b7c2d94e5f10`), 3 tags curated, 91 questions |
| B. Three-valued applicability | Done. `FounderContext.verdict` → SATISFIED / UNKNOWN / CONTRADICTED |
| C. Team / business-model context | Done, generically — any `team:*`, `model:*`, `industry:*`, `stage:*` token resolves through the same family logic |
| D. N/A as a first-class state | Done. Advisor can now emit it; coverage/completion no longer count it |
| E. Session-learned context | Done. `session_context_facts` (migration `e3f81a6c5d47`) |
| F. Pool floor | Done. One rung (industry), explicit and logged; hard contradictions never relaxed |
| G. Round-robin after filtering | Already correct; now pinned by a test |
| H. Advisor contract returns N/A | Done |

Two things the brief assumed existed and did not:

- **`question_tags.precondition_token` had no column.** Added.
- **`ScoreLabel.NOT_APPLICABLE` was unreachable in production.** Every reasoning
  engine handled it correctly and the `answers` CHECK allowed it, but the
  advisor's `_VALID_LABELS` admitted only green/amber/red — and under the
  shipped `ANSWER_CLASSIFIER=stored` the advisor *is* the classifier.

One live defect fixed: coverage is 25% of the confidence score and counted N/A
answers, so a founder whose questions largely did not apply climbed toward
"confident" on evidence every engine had already discarded.

---

## 3. Future-State architecture

Four new stages, and **no new reasoning pipeline**. They slot into the existing
one rather than paralleling it.

```
TARGET-STATE CONTEXT        what the founder says about the destination
        ↓
TARGET-STATE PROFILE        that, normalised and bounded
        ↓  × TARGET-STATE KNOWLEDGE BASE
REQUIRED CAPABILITY MODEL   the capabilities that destination needs
        ↓
        ├──────→ question selection     (a sixth, additive axis)
        ↓
CURRENT CAPABILITY ASSESSMENT  evidence, per capability, from answers
        ↓
GAP ENGINE                  required − evidenced
        ↓
PRIORITIZED GAPS ──→ existing root_cause / recommendation / action_plan
```

**The invariant that makes this safe: the Gap Engine reads `capability_evidence`,
never `target_*`.** A target with no corresponding evidence produces a gap of
`UNASSESSED`, not a gap of `MISSING`. ₹1 Cr → ₹10 Cr can never become a "₹9 Cr
problem" because revenue is not a capability and the engine has no path from a
number to a gap.

---

## 4. New entities/tables required

| Table | Purpose | Rows (est.) |
|---|---|---|
| `capabilities` | the taxonomy (§7) | 40–60 |
| `target_state_profiles` | one per session: the normalised destination | 1/session |
| `capability_requirements` | knowledge base: context → required capability + level | 400–900 |
| `capability_evidence` | evidence per (session, capability), derived from answers | ~15/session |
| `detected_gaps` | the Gap Engine's output, mirroring `detected_root_causes` | ~8/session |
| `question_capability_mapping` | which capability a question provides evidence for | ~800 |
| `intervention_capability_mapping` | which capability an intervention builds | ~417 |

`detected_gaps` deliberately mirrors `detected_root_causes` — same shape, same
session scoping, same "written once by the pipeline" lifecycle — so the report
generator and the recommendation engine treat gaps the way they already treat
root causes.

---

## 5. New context fields

**`founders` (permanent, needs onboarding capture — none of these exist today):**

| Field | Type | Why |
|---|---|---|
| `target_revenue_band` | varchar, coded bands | Must be **bands**, matching `current_revenue`'s existing vocabulary, not free rupees. A band is comparable, dimensionless and cannot be mistaken for a diagnosis. |
| `target_time_horizon` | varchar (`6_months`/`12_months`/`24_months`/`36_months_plus`) | Horizon changes which capabilities are *reachable*, not which are required |
| `target_team_size` | varchar, reusing the `team_size` vocabulary | optional |
| `target_business_model` | varchar, reusing the `business_model` vocabulary | optional; a stated model shift is a major capability driver |

`vision_1_year` and `goal_90_day` **already exist** and are free text. They stay
free text and are interpreted by the LLM (§12) — they are not parsed into
requirements.

**`FounderContext` — new fields, same three-valued contract:**

```python
target_revenue_band: str | None
target_horizon: str | None
target_team_size: str | None
target_business_model: str | None
```

plus a new family `FAMILY_TARGET` and tokens `target:revenue:<band>`,
`target:horizon:<h>`. **A founder who has not stated a target is UNKNOWN on that
family, not "no ambition"** — and an UNKNOWN target must never produce a gap.

**`TargetStateContext`** is a separate frozen value object rather than more
fields on `FounderContext`, because it is session-scoped and derived (it carries
the *interpreted* destination, not the stated one). `FounderContext` stays the
profile view.

---

## 6. Target-State Knowledge Base design

One table, read like a rules table, never generated at runtime.

```sql
capability_requirements (
  requirement_id      serial primary key,
  capability_id       int not null references capabilities,
  -- context predicate; NULL means "applies to any value of this axis"
  industry_code       varchar(20) null,
  business_model      varchar(100) null,
  from_stage_order    int null,
  target_revenue_band varchar(50) null,
  target_horizon      varchar(30) null,
  -- what is required
  required_level      smallint not null,   -- 0..3, see §7
  necessity           varchar(16) not null, -- 'core' | 'contextual'
  rationale           text not null,        -- shown to the founder
  source_document     text
)
```

Resolution is **specificity-ordered**, exactly like a CSS cascade: the most
specific matching row wins per capability, NULLs are wildcards. That gives
"B2B SaaS × Early Traction × ₹1Cr→₹10Cr × 12 months" a deterministic answer
without a row per combination — the 30 × 6 × 6 × 6 × 4 space is covered by a few
hundred rows because most requirements are keyed on one or two axes.

**The LLM never writes this table.** It is reference data, dumped by
`scripts/dump_reference_data.py` and reviewed like the question bank. That is
requirement 10 ("the LLM must not be the sole source of truth"), enforced
structurally rather than by prompt.

---

## 7. Capability taxonomy proposal

**`interventions.capability_domain` cannot be reused as the taxonomy.** It exists
and is populated on all 417 rows, but it is free text with ~390 near-unique
values ("Opening Line Craft", "Reading the Damage Signal", "Sunk Cost
Psychology") — one label per intervention, not a vocabulary. It is a *mapping
source*, not a taxonomy.

The taxonomy should be new, small, and anchored on the two vocabularies that are
already controlled: `readiness_pillars` (6) and `interventions.section` (12).

```
capabilities (
  capability_id, capability_code, capability_name,
  pillar_id     references readiness_pillars,   -- reuse, do not invent
  domain        varchar,   -- GTM | ORG | FOUNDER | OPERATIONS | FINANCE | PRODUCT
  description   text
)
```

Six domains, ~8 capabilities each. Illustrative, not final:

| Domain | Capabilities |
|---|---|
| GTM | ICP clarity, repeatable acquisition, sales process, pipeline visibility, sales ownership, sales metrics |
| ORG | role ownership, delegation structure, decision rights, hiring plan, management cadence |
| FOUNDER | founder time allocation, strategic focus, operational independence, leadership capacity |
| OPERATIONS | repeatable processes, SOPs, operating cadence, quality control, monitoring |
| FINANCE | financial visibility, planning, unit economics, cash planning |
| PRODUCT | delivery predictability, feedback loops, roadmap discipline |

**Levels 0–3**, and the definitions matter more than the count:

| Level | Meaning |
|---|---|
| 0 | absent — the founder does it ad hoc or not at all |
| 1 | personal — it works because the founder does it |
| 2 | documented — it exists outside the founder's head |
| 3 | owned — someone other than the founder owns and improves it |

Level 1 → 2 → 3 *is* the founder-dependency axis, which is what makes this
taxonomy say something Ally could not already say.

---

## 8. How current evidence maps to capabilities

`question_capability_mapping (question_id, capability_id, evidence_weight)`.

The pipeline gains one stage, between `diagnosis` and `root_cause`:

```
answer + its ScoreLabel + the question's capability
    → capability_evidence(session, capability, observed_level, confidence)
```

Rules, all conservative:

- **`ScoreLabel.NOT_APPLICABLE` produces no evidence at all** — not level 0.
  This reuses the same `is_scored` check the other engines use.
- A capability with **no answered mapped question** is `UNASSESSED`, never 0.
  UNASSESSED is the capability-level equivalent of UNKNOWN, and it is the whole
  reason the Gap Engine cannot manufacture gaps.
- Level is derived from the score band plus the question's own level-probe
  metadata, and several answers on one capability take the **lowest confident
  observation**, not the mean — a founder with a documented process they still
  personally run is at level 1.

~800 of 3,460 questions need mapping. That is Arya's curation pass, and it is
incremental: an unmapped question simply produces no capability evidence.

---

## 9. How target requirements map to capabilities

Directly — `capability_requirements.capability_id`. The Required Capability
Model for a session is the resolved set:

```
{capability_id: (required_level, necessity, rationale)}
```

Nothing else in the design needs the target's *value* after this point. Revenue
band and horizon have done their work by selecting rows; the rest of the
pipeline sees capabilities and levels only. **That is the structural reason a
target cannot become a diagnosis.**

---

## 10. Gap Engine design

```python
for capability, (required_level, necessity, rationale) in required.items():
    evidence = capability_evidence.get(capability)
    if evidence is None:
        yield Gap(capability, status=UNASSESSED)        # never a finding
    elif evidence.observed_level >= required_level:
        yield Gap(capability, status=MET)
    else:
        yield Gap(capability, status=MISSING,
                  severity=(required_level - evidence.observed_level),
                  confidence=evidence.confidence)
```

Only `MISSING` gaps are findings. Prioritisation, in order:

1. `necessity == 'core'` before `contextual`
2. severity (the level delta)
3. evidence confidence
4. capability-level tie-break for determinism

Gap classes are the taxonomy's `domain` (founder / GTM / org / operations /
finance / product) — no second vocabulary.

**UNASSESSED is a first-class output, not a hole.** It is what feeds §13: a
required capability with no evidence is precisely the thing Ally should ask
about next.

---

## 11. Integration with the existing engines

| Engine | Change | Kind |
|---|---|---|
| `diagnosis` | none | — |
| `distress_detection`, `psychological_state`, `answer_consistency`, `archetype`, `business_health` | none | — |
| **new: `capability_assessment`** | derives `capability_evidence` | NEW, after `diagnosis` |
| **new: `gap_detection`** | required vs evidenced | NEW, after `capability_assessment` |
| `root_cause` | unchanged detection; gaps become an **additional ranking input** | EXTEND |
| `confidence` | add a sixth signal: *target-state coverage* — how many required capabilities are assessed | EXTEND |
| `recommendation` | match on `intervention_capability_mapping` in addition to root cause | EXTEND |
| `action_plan` | sequence by gap priority and horizon | EXTEND |
| `report_generation` | new sections: Target State, Key Gaps, 90-Day Roadmap | EXTEND |

**No engine is duplicated.** Two are added because they compute something that
does not exist today; the rest are conditioned. A root cause is still *why the
current state is what it is*; a gap is *what the destination needs that is not
there*. They are different questions and both are useful, which is why gaps
inform root-cause ranking rather than replacing it.

---

## 12. Deterministic vs LLM

| Deterministic | LLM |
|---|---|
| resolving `capability_requirements` | interpreting `vision_1_year` / `goal_90_day` into a `target_state_profile` |
| which questions are eligible | which eligible question to ask next |
| capability level from score bands | reading one answer into a level observation |
| gap detection and prioritisation | writing the gap's explanation in the report |
| intervention matching | phrasing the recommendation |

The LLM interprets **intent** and writes **prose**. It never decides what is
required, what is eligible, or what is a gap. Its interpretation of the vision
lands in `target_state_profiles` where it is stored, auditable and overridable —
not consumed inline.

---

## 13. Question-selection integration

A **sixth axis, and it ranks rather than removes.**

Applicability, stage, industry and context remove questions. Target-state
relevance must not: a question that is not tied to a required capability is
still a perfectly good diagnostic question, and removing it would narrow the
diagnosis to the founder's ambition — the exact failure mode the "target is not
a diagnosis" rule exists to prevent.

So it enters `_sort_key_for` as a bias, not `_in_scope` as a filter:

> a question mapped to a required capability that is currently **UNASSESSED**
> sorts earlier.

This is the loop that closes the design — target-state requirements generate
the questions that produce the evidence that the Gap Engine needs — and it
changes no existing gate.

---

## 14. Data flow

```
onboarding ──→ founders.target_*            (permanent, stated)
                     │
                     ├─→ FounderContext (+ FAMILY_TARGET)
                     │
vision_1_year ──LLM──→ target_state_profiles (session, interpreted, stored)
                     │
                     ├─× capability_requirements ──→ Required Capability Model
                     │                                      │
                     │                                      ├─→ question ranking bias
                     │                                      │
answers ──→ ScoreLabel ──→ capability_evidence ─────────────┤
                                                            ↓
                                                        GAP ENGINE
                                                            ↓
                                                    detected_gaps
                                          ┌─────────────────┼─────────────────┐
                                    root_cause         recommendation     action_plan
                                      ranking            matching          sequencing
                                                            ↓
                                                    FOUNDER CLARITY REPORT
```

---

## 15. Migration requirements

Seven additive migrations, in dependency order. **No destructive change, no
backfill of founder data, every new column nullable.**

1. `capabilities` + seed the taxonomy
2. `capability_requirements` + seed the knowledge base
3. `question_capability_mapping`
4. `intervention_capability_mapping` (seeded by curating the 417 existing
   `capability_domain` labels onto the taxonomy — a mapping pass, not a rewrite)
5. `founders.target_*` columns, nullable, **no backfill** — absent means UNKNOWN
6. `target_state_profiles`, `capability_evidence`, `detected_gaps`
7. reference dump re-run

Existing founders are unaffected: no target means no Required Capability Model,
no gaps, and the diagnosis they get today.

---

## 16. API changes

- `PATCH /api/v1/profile/business` — accept the four `target_*` fields
- `GET /api/v1/diagnosis/session/{id}/target-state` — the profile and required
  capabilities (new)
- `GET /api/v1/reports/{id}` — response gains `target_state`, `gaps`,
  `roadmap_90_day`; **additive**, existing keys unchanged
- No breaking change to any existing endpoint.

---

## 17. Frontend / onboarding changes

`frontend/src/data/onboardingQuestions.js` gains one screen after Q3
(stage/experience/revenue), following the pattern `teamSize` and `businessModel`
already use:

- *"Where do you want the business to be?"* → `target_revenue_band` (bands, same
  vocabulary as `current_revenue`)
- *"By when?"* → `target_time_horizon`

Both **skippable**. A skipped target is UNKNOWN, and UNKNOWN produces no gaps —
so skipping costs the founder the future-state layer and nothing else. Owners
must be registered in `frontend/src/services/profile.js` `BUSINESS`, or
`saveProfileEdits` throws (a guard added in the Step-2 work).

---

## 18. Testing strategy

Mirrors Step 4: mechanism tested synthetically, data tested separately.

- **Requirement resolution** — specificity cascade, wildcard NULLs, ties
- **`target = ₹10 Cr`, no evidence → zero MISSING gaps, all UNASSESSED.** The
  single most important test in the layer
- **N/A answer → no capability evidence** (not level 0)
- **Unknown target → no Required Capability Model, no gaps, diagnosis unchanged**
- **Capability with partial evidence → lowest confident observation wins**
- **Gap prioritisation is deterministic** — same inputs, same order
- **Unmapped question → no evidence, no crash** (incremental curation)
- **Regression: a founder with no target gets a byte-identical report** to today
- **Knowledge-base integrity**: every `capability_id` resolves, no orphan
  requirement, every capability reachable by at least one question

---

## 19. Risks / edge cases

| Risk | Mitigation |
|---|---|
| **Target becomes a diagnosis** | Structural: the Gap Engine reads `capability_evidence` only. Revenue never reaches it. Pinned by test |
| **Knowledge base becomes an LLM prompt** | It is reference data, reviewed and dumped. The LLM has no write path |
| **Requirement explosion** (30 × 6 × 6 × 6 × 4) | NULL wildcards + specificity cascade; most rows key on one or two axes |
| **Unmapped capabilities silently produce no gaps** | Integrity test asserts every capability is reachable from at least one question |
| **Ambitious founder is told everything is a gap** | `necessity`, severity ordering, and a cap on reported gaps |
| **Horizon is ignored** | Horizon selects requirements; it must not scale severity — a capability is required or it is not |
| **Curation cost** (~800 questions, 417 interventions) | Incremental and fail-open at every step |
| **Two "why" answers in one report** (root cause vs gap) | Report presents them as different sections with different questions, not as a merged list |
| **A founder changes their target mid-session** | `target_state_profiles` is session-scoped and versioned; the profile carries the stated value |

---

## 20. Recommended implementation order

Each step ships independently and is useful on its own.

| # | Step | Ships |
|---|---|---|
| 5 | Capability taxonomy + `question_capability_mapping` | Capability coverage reporting — **no founder-visible change** |
| 6 | Target capture (onboarding + `founders.target_*` + `FounderContext`) | Target shown in the report; no reasoning change |
| 7 | `capability_requirements` + resolution | Required Capability Model, logged only |
| 8 | `capability_evidence` (`capability_assessment` stage) | Current capability levels in the report |
| 9 | **Gap Engine** + `detected_gaps` | Gaps in the report — the first real payoff |
| 10 | Question-selection ranking bias | Ally starts asking toward the target |
| 11 | Recommendation + action-plan conditioning | 90-day roadmap driven by gaps |

**Step 5 first, deliberately.** It is the largest curation task, it has no
founder-visible risk, and every later step depends on it. Building the Gap
Engine before the taxonomy would mean designing the taxonomy under deadline.
