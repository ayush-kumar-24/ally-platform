# Ally Question Bank Sufficiency Audit

**Type:** READ-ONLY structural audit. No database, question bank, mapping, migration,
application-code, scoring or diagnosis-logic change was made, and no question was added.
Every number below comes from `SELECT`-only queries against the live Supabase project
`wxggmjvyzuerjbhhtcab` (`founder-alley`), plus a read of the repository at
`claude/ally-question-bank-audit-mtt3vl`.

**Date of snapshot:** 2026-09-20. **Head commit:** `acaf46f` (industry batch C merged).

---

## 0. Read this first — the brief's taxonomy does not exist in Ally

The brief asks for coverage across **34 capabilities**, each with **4 evidence criteria**,
grouped into the domains **GTM / FOUNDER / ORG / OPS / FIN / PROD / STRAT**, joined through
tables named `capabilities`, `capability_domains`, `capability_evidence_criteria`,
`capability_requirements`, `capability_evidence`, `question_capabilities` and
`intervention_capabilities`.

**None of those tables exist, and neither does that taxonomy.** I inspected the schema
rather than assuming, and the full public-schema table list (138 tables) contains no table
whose name contains `capabilit`. The one place the word appears is a single free-text
column, `interventions.capability_domain`, which holds **450 distinct values**, **392 of
which are attached to exactly one intervention** (`Opening Line Craft`,
`Sunk Cost Psychology`, `Vendor Pricing Review`, …). It is a per-intervention output label,
not a controlled diagnostic axis, and nothing upstream of interventions references it.
There is also no `capability_evidence`, no evidence-criterion store of any kind, no
`business_model` axis on questions, and `business_dimensions` exists in the ORM
(`app/models/schema.py:98`) but **has no table in the live database**.

What Ally actually has, and what the diagnosis engine actually filters on, is the
**GoXL Business DNA** model, transcribed in `app/api/v1/diagnosis/business_dna.py`:

| Brief's concept | Ally's real equivalent | Where it lives |
|---|---|---|
| domain (7) | **readiness pillar (6)** | `readiness_pillars` |
| capability (34) | **Business DNA dimension (20)** | `business_dna.DIMENSIONS` (code only, no table) |
| evidence criterion (4/capability) | **no equivalent exists** | — |
| question → capability mapping | `questions.problem_id` → `problems.pillar_id` / `problems.dimension_code` | DB |
| intervention → capability | `interventions.problem_id` + `root_cause_ids` | DB |
| stage (n) | **8 `founder_stages`**, collapsed to **3 `primary_stage_group`s** for questions | DB + `engine.stage_groups_for` |

I have therefore run the audit the brief asks for against **6 pillars × 20 dimensions × 8
stages**, and I say explicitly wherever a requested figure cannot be produced because the
underlying concept is absent. Substituting a plausible-looking 34-row table would have
manufactured a finding rather than measured one.

---

## 1. Executive summary

**The answer to the closing question: Ally does NOT have a question-content shortage.
It has a mapping, embedding and downstream-layer shortage.** Adding questions today would
make the bank larger without making the diagnosis better, and would in several places make
it worse.

The bank holds **5,140 questions** across **723 problems** and **3,996 root causes**, with
**1,440 interventions**. Against a per-session question budget of **14–32**, every stage has
between **761 and 2,228 in-scope questions** — a surplus of **24× to 74×**. No pillar is
without questions at any stage where the architecture says it applies. There is no thin
stage measured by question volume, and the embedded portion of the bank is not redundant
(85% of sampled questions have no near-neighbour closer than cosine 0.25; **zero** pairs
below 0.05).

Six structural defects account for essentially all of the diagnostic weakness:

1. **15 of the 20 Business DNA dimensions are unreachable.** Only 5 dimensions carry any
   `problems.dimension_code`, covering **264 of 5,140 questions (5.1%)**. The other 15 —
   including all three Founder Readiness dimensions, all three Product & Execution, all
   three Team & Leadership, and Problem Definition, Market Sizing Reality, Demand Reality,
   Pricing Confidence, Revenue Concentration, Institutional Memory — have **zero** problems,
   **zero** questions and **zero** interventions reachable by dimension. This is the
   closest real analogue to "the taxonomy exists but the bank cannot measure it", and it is
   **pure data gap**: the questions plainly exist (Founder Readiness alone has 374), they
   are simply not labelled.
2. **The entire industry layer is unembedded.** All **1,800** industry-specific questions,
   **450** industry problems and **1,987** industry root causes were seeded with
   `embedding_model IS NULL` and a zero vector. Semantic retrieval, enrichment and
   similarity ranking are inoperative across 35% of the question bank, 62% of problems and
   50% of root causes.
3. **`questions.industry_relevance` is never read by the application.** It is populated on
   all 5,140 rows (`'all'` × 3,340; 30 industries × 60 = 1,800) but appears nowhere in
   `app/` outside the ORM definition. Only `interventions.industry_relevance` is consumed.
   Industry-specific questions are therefore served to every founder regardless of industry.
4. **That in turn makes 107 questions true in-session duplicates.** There are 47 exact
   duplicate texts (e.g. *"If your largest account left, how long could you continue?"* in
   3 industries; *"Did you set your price from your own cost or from competitors?"* in 6).
   They are correct as per-industry clones; they are defects only because the industry gate
   does not run.
5. **661 questions (12.9%) dead-end before an intervention**, because their root cause is
   not listed in any intervention's `root_cause_ids`; **181** sit under a problem with no
   intervention at all. Six problems carry 30–31 questions each and zero interventions
   (`FIN-152`, `FIN-153`, `MEX-102`, `MEX-103`, `SLX-196`, `TM-077`). Separately, **101
   root-cause codes referenced by interventions do not exist** in `root_causes`.
6. **Half the pipeline the brief describes has no implementation.** There is no evidence
   layer, no capability-assessment layer, no gap or gap-priority layer, no 20-day target and
   no strategic-direction layer anywhere in the schema or in `app/`. The live path is
   `question → answer (scored) → detected_root_causes → intervention recommendation →
   report section`. Any end-to-end path classification must be read against that, not
   against the nine-step chain in the brief.

**Verdict: 0 genuine content gaps at pillar level, 1 conditional content gap (Exit stage),
and 9 architecture/data gaps.** Full breakdown in §13–§14.

---

## 2. Database inventory

Tables the brief asked about, and what actually backs them.

| Brief's table | Exists? | Actual table / column |
|---|---|---|
| questions | ✅ | `questions` (21 cols): `question_id`, `question_code`, `category`, `question_text`, `problem_id`, `root_cause_id`, `question_type`, `difficulty_level`, `red_flag_pattern`, `green_flag_pattern`, `follow_up_question_id`, `priority`, `is_distress_tagged`, `embedding`, `primary_stage_group`, `embedding_model/_version/_dimension`, `industry_relevance` |
| question_tags | ✅ | `question_tags` (88 rows), `question_tag_mapping` (8,359 rows) |
| question_capabilities | ❌ | **absent.** Nearest: `questions.problem_id → problems.pillar_id` |
| capability_domains | ❌ | **absent.** Nearest: `readiness_pillars` (6 rows) |
| capabilities | ❌ | **absent.** Nearest: 20 dimension codes in `business_dna.py`, no table |
| capability_evidence_criteria | ❌ | **absent — no evidence-criterion concept exists anywhere** |
| capability_requirements | ❌ | **absent** |
| capability_evidence | ❌ | **absent** |
| problems | ✅ | `problems` (20 cols, 723 rows): incl. `pillar_id`, `category`, `dimension_code` (nullable), `layer`, `severity_min/max`, `symptoms`, `industry_relevance`, `embedding` |
| root causes | ✅ | `root_causes` (16 cols, 3,996 rows): `root_cause_code`, `problem_id`, `confidence_weight`, `primary_stage_group`, `industry_relevance` |
| interventions | ✅ | `interventions` (15 cols, 1,440 rows): `problem_id`, `root_cause_ids` (jsonb of **codes**, not ids), `secondary_root_cause_ids`, `capability_domain`, `section`, `framework_codes`, `immediate_next_steps`, `stage_relevance`, `industry_relevance` |
| intervention_capabilities | ❌ | **absent.** Only the free-text `interventions.capability_domain` |
| industry relevance | ⚠️ | `industries` (30 rows) + `industry_relevance` jsonb on `questions`, `problems`, `root_causes`, `interventions`. **Only the interventions one is read by code.** |
| stage eligibility | ✅ | `questions.primary_stage_group` (3 values) + `founder_stages` (8 rows, `question_budget`) + `problem_stage_mapping` (553 rows) + `root_cause_weights` + code-side `business_dna` / `stage_scope` / `context_scope` |
| business model applicability | ❌ | **absent from the question bank.** Only `founders.business_model` (free varchar; live data: 6× `B2B`, 41× NULL) |
| founder/session context | ✅ | `founders` (69 cols), `founder_context`, `sessions`, `answers`, `founder_dna_questions` (67), `founder_dna_answers`, `current_problem_questions` (12), `detected_root_causes`, `stage_assessments`, `founder_reports` |

Supporting: `readiness_pillars` (6), `founder_stages` (8), `industries` (30),
`industry_stage_thresholds` (32), `stage_diagnosis_logic` (3),
`visual_question_bank` (**0 rows — empty**), `frameworks`, `archetypes`, `blind_spots`.

---

## 3. Stage question coverage

Two independent stage axes exist and must not be conflated:

- **Axis A — `questions.primary_stage_group`**, the only stage tag a question carries. Three
  values. This is what `repository.list_candidate_questions` filters on.
- **Axis B — the 8 `founder_stages`**, mapped onto Axis A by `engine.stage_groups_for`
  (order 1 → `Stage 0`; orders 2–4 → `Stage 0→1`; orders 5–8 → `Stage 1→10+`), then further
  narrowed per stage by `stage_scope` (pillar set + withheld categories + excluded
  dimensions) and `context_scope` (preconditions).

### 3a. Axis A — the question bank's own stage tagging

| Stage group | Total | Active¹ | Universal | Industry-specific | Embedded | Mapped to ≥1 pillar² | Unmapped | % mapped | % unmapped | Dimension-mapped | % dim-mapped | Precondition-gated³ | RC→intervention path | % with path |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Stage 0 | 922 | 922 | 472 | 450 | 472 (51%) | 922 | 0 | 100% | 0% | 134 | 14.5% | 0 | 725 | 78.6% |
| Stage 0→1 | 1,990 | 1,990 | 1,390 | 600 | 1,390 (70%) | 1,990 | 0 | 100% | 0% | 51 | 2.6% | 15 | 1,839 | 92.4% |
| Stage 1→10+ | 2,228 | 2,228 | 1,478 | 750 | 1,478 (66%) | 2,228 | 0 | 100% | 0% | 79 | 3.5% | 72 | 1,915 | 86.0% |
| **Total** | **5,140** | **5,140** | **3,340** | **1,800** | **3,340 (65%)** | **5,140** | **0** | **100%** | **0%** | **264** | **5.1%** | **87** | **4,479** | **87.1%** |

¹ `questions` has **no `is_active` column**; every row is live. (`founder_dna_questions` and
`current_problem_questions` do have one, and all their rows are active.)
² "Mapped to ≥1 capability" is read as "resolves to a pillar via `problems.pillar_id`".
`problem_id` and `root_cause_id` are both `NOT NULL` with FKs, so **structural mapping is
100% by construction** — this metric cannot fail, and its passing is not evidence of health.
The meaningful mapping metric is the dimension column, at **5.1%**.
³ `context_scope.PROBLEM_PRECONDITIONS` gates 6 FND problems on `fundraising_intent`;
6 root causes under FND-005 are gated separately.

### 3b. Axis B — per-stage eligibility after the engine's real scope rules

| # | Stage | Group | Budget | Eligible questions | Surplus vs budget | Pillars in scope | Problems reached | Categories | Dims reached | Withheld at this stage |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Ideation | Stage 0 | 14 | **761** | 54× | 4 (1,2,4,6) | 119 | 9 | 4 | 161 q (8 categories, pillars 3+5, 11 dims) |
| 2 | Validation | Stage 0→1 | 20 | **1,990** | 100× | 6 | 300 | 19 | 4 | 2 dims |
| 3 | Prototype / MVP | Stage 0→1 | 24 | **1,990** | 83× | 6 | 300 | 19 | 4 | 2 dims |
| 4 | Early Traction | Stage 0→1 | 30 | **1,990** | 66× | 6 | 300 | 19 | 4 | 2 dims |
| 5 | Growth / Scaling | Stage 1→10+ | 30 | **2,228** | 74× | 6 | 338 | 17 | 3 | none |
| 6 | Expansion | Stage 1→10+ | 32 | **2,228** | 70× | 6 | 338 | 17 | 3 | none |
| 7 | Maturity | Stage 1→10+ | 32 | **2,228** | 70× | 6 | 338 | 17 | 3 | none |
| 8 | Exit | Stage 1→10+ | 30 | **2,228** | 74× | 6 | 338 | 17 | 3 | none |

**No stage is structurally thin on volume.** Stages 2–4 are byte-identical to each other,
as are 5–8: the bank has no way to distinguish Validation from Early Traction, or Growth
from Exit, because `primary_stage_group` is the only stage tag a question carries. The
per-stage differentiation that does exist comes from `problem_stage_mapping` prevalence,
and that is where Exit collapses — see §12.

---

## 4. Capability coverage

**Cannot be produced as specified.** There is no `capabilities` table, no
`capability_id`, no `capability_evidence_criteria`, no `capability_requirements` and no
HIGH/MEDIUM confidence field on any question→concept mapping. The nearest honest
substitutes are given below; the brief's instruction not to invent thresholds before
showing the distribution is observed — raw counts first, flags after.

### 4a. Coverage by readiness pillar (the 6-row domain axis)

| Pillar | Name | Weight | Questions | Distinct problems | Distinct RCs | RC→intervention | % | Problem has ≥1 intervention | No intervention at all | Stage-weighted RC | Problem stage-mapped | No red/green flag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Founder Readiness | 25% | 374 | 32 | 274 | 374 | **100%** | 374 | 0 | 147 (39%) | 364 (97%) | 87 (23%) |
| 2 | Market Clarity | 20% | 1,224 | 187 | 885 | 796 | **65%** | 1,164 | 60 | 617 (50%) | 360 (29%) | 863 (71%) |
| 3 | Revenue Maturity | 20% | 1,613 | 256 | 1,321 | 1,413 | **88%** | 1,523 | 90 | 839 (52%) | 183 (11%) | 962 (60%) |
| 4 | Product & Execution | 15% | 1,037 | 143 | 713 | 1,035 | **99.8%** | 1,037 | 0 | 487 (47%) | 462 (45%) | 804 (78%) |
| 5 | Team & Leadership | 10% | 431 | 42 | 267 | 400 | **93%** | 400 | 31 | 323 (75%) | 268 (62%) | 197 (46%) |
| 6 | Strategic Clarity | 10% | 461 | 62 | 310 | 461 | **100%** | 461 | 0 | 429 (93%) | 278 (60%) | 100 (22%) |
| | **Total** | 100% | **5,140** | **722** | **3,770** | **4,479** | **87%** | **4,959** | **181** | **2,842 (55%)** | **1,915 (37%)** | **3,013 (59%)** |

Distribution before flagging: per-pillar question counts run **374 … 1,613**, mean 857,
median 749. There is no pillar near zero, so no pillar-level CRITICAL or THIN flag is
warranted on volume. Intervention-path rates run **65% … 100%**, mean 87%.

**Flags (pillar level):**
- **HEALTHY** — Founder Readiness, Product & Execution, Strategic Clarity, Team &
  Leadership (≥93% intervention path, 100% pillar mapping).
- **PARTIAL** — **Market Clarity** (35% of its 1,224 questions reach no intervention; 60
  questions under problems with no intervention at all) and **Revenue Maturity** (12% no
  path; 90 questions under intervention-less problems). Questions exist; the downstream
  mapping does not.
- **CRITICAL** — none at pillar level.

### 4b. Coverage by Business DNA dimension (the 20-row "capability" axis)

This is the table that answers *"does the taxonomy exist but the bank cannot measure it?"*

| Pillar | Dimension code | Dimension name | Problems | Questions | S0 | S0→1 | S1→10+ | Interventions | Flag |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `skill_stage_fit` | Skill-Stage Fit | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |
| 1 | `time_allocation_reality` | Time Allocation Reality | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |
| 1 | `founder_dependency` | Founder Dependency / Bus Factor | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |
| 2 | `problem_definition` | Problem Definition | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |
| 2 | `customer_definition` | Customer Definition (ICP) | 5 | 37 | 25 | 6 | 6 | 7 | HEALTHY |
| 2 | `competitive_awareness` | Competitive Awareness | 5 | 44 | 19 | 8 | 17 | 5 | HEALTHY |
| 2 | `market_sizing_reality` | Market Sizing Reality | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |
| 3 | `demand_reality` | Demand Reality | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |
| 3 | `revenue_model_clarity` | Revenue Model Clarity | 5 | 31 | 12 | 19 | **0** | 5 | PARTIAL (no S1→10+) |
| 3 | `revenue_concentration` | Revenue Concentration | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |
| 3 | `pricing_confidence` | Pricing Confidence | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |
| 4 | `build_demand_alignment` | Build-Demand Alignment | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |
| 4 | `execution_velocity` | Execution Velocity | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |
| 4 | `reliability_real_world` | Reliability in the Real World | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |
| 5 | `team_structure_role_clarity` | Team Structure & Role Clarity | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |
| 5 | `decision_rights` | Decision Rights | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |
| 5 | `hiring_repeatability` | Hiring Repeatability | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |
| 6 | `plan_to_vision_alignment` | Plan-to-Vision Alignment | 5 | 71 | 53 | 18 | **0** | 5 | PARTIAL (no S1→10+) |
| 6 | `prioritization_discipline` | Prioritization Discipline | 5 | 81 | 25 | **0** | 56 | 5 | PARTIAL (no S0→1) |
| 6 | `institutional_memory` | Institutional Memory | **0** | **0** | 0 | 0 | 0 | **0** | **UNREACHABLE** |

**15 of 20 dimensions (75%) are unreachable. 5 are reachable, covering 264 questions
(5.1% of the bank).** Every reachable dimension has exactly 5 problems and 5 interventions —
the signature of a single backfill pass (migration `c3f7b28d5e91`, whose own comment records
this as deliberate and incomplete: *"NULL means 'not yet known', never 'out of scope'"*).

**This is an architecture/data gap, not a content gap.** Founder Readiness has 374
questions and 32 problems; none carries a `dimension_code`, so all three of its dimensions
read as zero. The measurement instrument exists; the label that would let Ally report on it
does not.

---

## 5. Evidence criteria coverage

**Cannot be produced. There is no evidence-criterion concept in Ally at any level.**

The brief states "there are 4 evidence criteria per capability". I searched the schema
(138 tables, no `capability_*` or `evidence_*` table), the ORM (`app/models/`), and the
reasoning package. What exists under the word "evidence" is unrelated:

- `reasoning/config.py` — **five confidence signals** (`evidence_coverage`,
  `evidence_breadth`, …) that score *how much of the session was answered*, not what a
  question can prove about a capability.
- `reasoning/enrichment.py` / `services/retrieval/evidence.py` — `RetrievalEvidence`,
  semantic retrieval hits attached to a detected root cause. Also runtime, also not a
  criterion catalogue.

There is therefore **no criterion_id, no criterion description, and no question→criterion
mapping** to count. Zero-question criteria, one-question criteria, concentration and
independent-path analysis are all undefined here.

The nearest measurable proxy for "can this question generate evidence at all" is whether it
carries a scoring signal. Measured:

| Signal | Questions | % of bank |
|---|---|---|
| Has `red_flag_pattern` | 2,127 | 41.4% |
| Has `green_flag_pattern` | 122 | 2.4% |
| **Has neither** | **3,013** | **58.6%** |
| Reaches an intervention via its root cause | 4,479 | 87.1% |
| Root cause carries a stage weight | 2,842 | 55.3% |
| Problem carries a stage mapping | 1,915 | 37.3% |

**Closest true statement to the brief's fear:** *"The dimension exists in the taxonomy but
the question bank cannot measure it"* is **true for 15 of 20 Business DNA dimensions** —
not because questions are missing, but because `problems.dimension_code` is NULL for 459 of
723 problems.

---

## 6. Domain coverage

Reported over the **6 readiness pillars**, Ally's real domain axis. The brief's seven
(GTM/FOUNDER/ORG/OPS/FIN/PROD/STRAT) are not an axis in this system — `GTM` is a
problem-code prefix and a `questions.category` value, not a domain. Structural only, no
ranking.

| Pillar (domain) | Capabilities (dimensions) | Reachable dimensions | Mapped questions | Avg q/dimension¹ | Min | Max | Zero-coverage dimensions | Thin dimensions | Evidence-criterion coverage |
|---|---|---|---|---|---|---|---|---|---|
| Founder Readiness | 3 | **0** | 374 | 0.0 | 0 | 0 | **3 of 3** | — | n/a — no criterion store |
| Market Clarity | 4 | 2 | 1,224 | 20.3 | 0 | 44 | **2 of 4** (`problem_definition`, `market_sizing_reality`) | — | n/a |
| Revenue Maturity | 4 | 1 | 1,613 | 7.8 | 0 | 31 | **3 of 4** (`demand_reality`, `revenue_concentration`, `pricing_confidence`) | `revenue_model_clarity` (31) | n/a |
| Product & Execution | 3 | **0** | 1,037 | 0.0 | 0 | 0 | **3 of 3** | — | n/a |
| Team & Leadership | 3 | **0** | 431 | 0.0 | 0 | 0 | **3 of 3** | — | n/a |
| Strategic Clarity | 3 | 2 | 461 | 50.7 | 0 | 81 | **1 of 3** (`institutional_memory`) | — | n/a |
| **Total** | **20** | **5** | **5,140** | **13.2** | **0** | **81** | **15 of 20** | — | **n/a across the board** |

¹ Questions reachable *by dimension code*, divided by the pillar's dimension count. The
"mapped questions" column is the pillar total and is large everywhere; the avg/min/max
columns are the dimension-level view, and that is where the structure is hollow.

---

## 7. Stage × capability matrix

Rows are the 20 dimensions (Ally's capability analogue), columns the 8 stages. Cell = number
of **usable** questions connecting that stage to that dimension, where usable means: correct
`primary_stage_group`, pillar in the stage's scope, category not withheld, dimension not
excluded at that stage, and the problem carries the dimension code. `—` means the
architecture does not expect this dimension at this stage (Part 3 exclusion), not a hole.

| Dimension | 1 Ideation | 2 Valid. | 3 Proto | 4 EarlyTr | 5 Growth | 6 Expan. | 7 Matur. | 8 Exit |
|---|---|---|---|---|---|---|---|---|
| skill_stage_fit | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| time_allocation_reality | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| founder_dependency | — | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| problem_definition | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| customer_definition | 25 | 6 | 6 | 6 | 6 | 6 | 6 | 6 |
| competitive_awareness | 19 | 8 | 8 | 8 | 17 | 17 | 17 | 17 |
| market_sizing_reality | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| demand_reality | — | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| revenue_model_clarity | — | 19 | 19 | 19 | **0** | **0** | **0** | **0** |
| revenue_concentration | — | — | — | — | **0** | **0** | **0** | **0** |
| pricing_confidence | — | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| build_demand_alignment | — | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| execution_velocity | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| reliability_real_world | — | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| team_structure_role_clarity | — | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| decision_rights | — | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| hiring_repeatability | — | — | — | — | **0** | **0** | **0** | **0** |
| plan_to_vision_alignment | 53 | 18 | 18 | 18 | **0** | **0** | **0** | **0** |
| prioritization_discipline | 25 | **0** | **0** | **0** | 56 | 56 | 56 | 56 |
| institutional_memory | — | **0** | **0** | **0** | **0** | **0** | **0** | **0** |

**Stage → dimensions with zero coverage** (in-scope only):

| Stage | In scope | Zero-coverage | Covered |
|---|---|---|---|
| 1 Ideation | 9 | **5** (skill_stage_fit, time_allocation_reality, problem_definition, market_sizing_reality, execution_velocity) | 4 |
| 2–4 Validation / Proto / Early Traction | 18 | **14** | 4 (customer_definition, competitive_awareness, revenue_model_clarity, plan_to_vision_alignment) |
| 5–8 Growth / Expansion / Maturity / Exit | 20 | **18** | 2 (customer_definition, competitive_awareness, prioritization_discipline → 3) |

**Capability → stages with zero coverage:** 15 dimensions have zero at **every** stage.
`revenue_model_clarity` and `plan_to_vision_alignment` are zero at all four late stages;
`prioritization_discipline` is zero across Validation→Early Traction.

**Read this correctly.** Zero here does not mean "the founder is asked nothing about
prioritisation at Early Traction". Pillar 6 has 71 eligible questions at that stage. It
means Ally cannot *attribute* any of them to the dimension, so it cannot report a
dimension-level finding, and `stage_scope`'s dimension filter degrades to a no-op for 95%
of the bank. The engine is explicitly written to admit unmapped problems rather than drop
them (`business_dna.py`, `engine._in_scope`), so nothing breaks — the reporting resolution
is simply coarser than the architecture intends.

---

## 8. Stage × domain matrix

Rows are the 6 pillars, columns the 8 stages. Each cell is `eligible / with-intervention-path`.

| Pillar | 1 Ideation | 2 Validation | 3 Proto | 4 EarlyTr | 5 Growth | 6 Expansion | 7 Maturity | 8 Exit |
|---|---|---|---|---|---|---|---|---|
| 1 Founder Readiness | 105 / 105 | 145 / 145 | 145 / 145 | 145 / 145 | 124 / 124 | 124 / 124 | 124 / 124 | 124 / 124 |
| 2 Market Clarity | 421 / **224** | 308 / **218** | 308 / **218** | 308 / **218** | 495 / **354** | 495 / **354** | 495 / **354** | 495 / **354** |
| 3 Revenue Maturity | — | 804 / 743 | 804 / 743 | 804 / 743 | 658 / **519** | 658 / **519** | 658 / **519** | 658 / **519** |
| 4 Product & Execution | 150 / 150 | 512 / 512 | 512 / 512 | 512 / 512 | 375 / 373 | 375 / 373 | 375 / 373 | 375 / 373 |
| 5 Team & Leadership | — | 150 / 150 | 150 / 150 | 150 / 150 | 271 / **240** | 271 / **240** | 271 / **240** | 271 / **240** |
| 6 Strategic Clarity | 85 / 85 | 71 / 71 | 71 / 71 | 71 / 71 | 305 / 305 | 305 / 305 | 305 / 305 | 305 / 305 |
| **Stage total** | **761 / 564** | **1,990 / 1,839** | **1,990 / 1,839** | **1,990 / 1,839** | **2,228 / 1,915** | **2,228 / 1,915** | **2,228 / 1,915** | **2,228 / 1,915** |

`—` = pillar correctly out of scope at Ideation per Business DNA Part 3.

**Structural holes: none at this resolution.** Every in-scope pillar has ≥71 eligible
questions at every stage, against budgets of 14–32. The bold cells are the intervention-path
leak, concentrated in Market Clarity (47% loss at Ideation, 29% at Validation) and Revenue
Maturity (21% at Growth+).

**The real hole is one level down (§7) and one axis over: stage differentiation.** Stages
2/3/4 are identical and 5/6/7/8 are identical, because only three stage tags exist for eight
stages.

---

## 9. Industry coverage

**The canonical 30-industry catalogue is fully present in the local database.** The brief's
caution about a temporary 16-industry production state does not apply to this snapshot —
`industries` holds 30 rows, and industry batches A, B and C are merged at `acaf46f`. **No
industry is absent.**

Per-industry question coverage is perfectly uniform: **60 questions each** (15 Stage 0, 20
Stage 0→1, 25 Stage 1→10+), **15 problems each**, all 3 stage groups.

| Industry | Specific q | Universal q available | Pillars reached | Categories | Problems | Stage groups | Industry interventions | Industry problems | Stage thresholds | Embedded? |
|---|---|---|---|---|---|---|---|---|---|---|
| adtech_marketing | 60 | 3,340 | 4 | 6 | 15 | 3 | 34 | 15 | **0** | **no** |
| agritech | 60 | 3,340 | **1** | **1** | 15 | 3 | 34 | 15 | **0** | **no** |
| automotive | 60 | 3,340 | **1** | **1** | 15 | 3 | 34 | 15 | **0** | **no** |
| beauty_personal_care | 60 | 3,340 | **1** | **1** | 15 | 3 | 34 | 15 | **0** | **no** |
| cleantech_energy | 60 | 3,340 | 3 | 5 | 15 | 3 | 34 | 15 | **0** | **no** |
| consumer_electronics | 60 | 3,340 | 3 | 5 | 15 | 3 | 34 | 15 | **0** | **no** |
| ecommerce_d2c | 60 | 3,340 | 3 | 5 | 15 | 3 | 34 | 15 | **0** | **no** |
| edtech | 60 | 3,340 | 3 | 4 | 15 | 3 | 34 | 15 | **0** | **no** |
| fashion_apparel | 60 | 3,340 | 3 | 5 | 15 | 3 | 34 | 15 | **0** | **no** |
| fintech | 60 | 3,340 | **1** | **1** | 15 | 3 | 34 | 15 | **0** | **no** |
| foodtech | 60 | 3,340 | 3 | 5 | 15 | 3 | 34 | 15 | **0** | **no** |
| gaming | 60 | 3,340 | 4 | 6 | 15 | 3 | 34 | 15 | **0** | **no** |
| healthtech | 60 | 3,340 | 4 | 6 | 14 | 3 | 34 | 15 | **0** | **no** |
| hrtech | 60 | 3,340 | 4 | 4 | 15 | 3 | 34 | 15 | **0** | **no** |
| legaltech | 60 | 3,340 | 4 | 6 | 15 | 3 | 34 | 15 | **0** | **no** |
| logistics | 60 | 3,340 | 4 | 6 | 15 | 3 | 34 | 15 | **0** | **no** |
| manufacturing | 60 | 3,340 | 4 | 5 | 15 | 3 | 37 | 15 | 8 | **no** |
| media_entertainment | 60 | 3,340 | 4 | 5 | 15 | 3 | 35 | 15 | **0** | **no** |
| ngo | 60 | 3,340 | 4 | 6 | 15 | 3 | 36 | 15 | 8 | **no** |
| pharma_biotech | 60 | 3,340 | 3 | 5 | 15 | 3 | 34 | 15 | **0** | **no** |
| proptech | 60 | 3,340 | **1** | **1** | 15 | 3 | 34 | 15 | **0** | **no** |
| retail | 60 | 3,340 | 3 | 6 | 15 | 3 | 34 | 15 | **0** | **no** |
| saas | 60 | 3,340 | 5 | 5 | 15 | 3 | 38 | 15 | 8 | **no** |
| services | 60 | 3,340 | 4 | 6 | 15 | 3 | 36 | 15 | 8 | **no** |
| sports_fitness | 60 | 3,340 | 3 | 6 | 15 | 3 | 34 | 15 | **0** | **no** |
| telecom | 60 | 3,340 | 3 | 5 | 15 | 3 | 34 | 15 | **0** | **no** |
| textiles | 60 | 3,340 | 3 | 6 | 15 | 3 | 34 | 15 | **0** | **no** |
| trade_import_export | 60 | 3,340 | 2 | 4 | 15 | 3 | 34 | 15 | **0** | **no** |
| transport_delivery | 60 | 3,340 | 3 | 6 | 15 | 3 | 34 | 15 | **0** | **no** |
| travel_hospitality | 60 | 3,340 | 4 | 6 | 15 | 3 | 34 | 15 | **0** | **no** |

**Evidence criteria reachable: n/a** — no criterion store exists (§5).

Three findings, all architectural:

1. **`questions.industry_relevance` is dead weight at runtime.** `grep -rn industry_relevance
   app/` returns hits only in `reasoning/engines/recommendation.py` (which reads
   `intervention.industry_relevance`) and `models/schema.py`. The question-level column is
   populated on all 5,140 rows and read by nothing. Every founder is a candidate for every
   industry's 60 questions.
2. **Five industries are single-pillar, single-category.** `agritech`, `automotive`,
   `beauty_personal_care`, `fintech` and `proptech` have all 60 industry questions landing
   in **one** pillar and **one** category. `trade_import_export` reaches 2. If and when the
   industry gate is switched on, those founders' industry-specific signal would be confined
   to a single pillar. Contrast `saas` (5 pillars) and the ten industries reaching 4.
3. **26 of 30 industries have zero `industry_stage_thresholds` rows.** Only `manufacturing`,
   `ngo`, `saas` and `services` have the full 8. The table holds 32 of a possible 240 rows
   (13%), so industry-adjusted stage classification is unavailable for 87% of the catalogue.

---

## 10. Business model coverage

| Business model | Total questions | Applicable questions | Mapped questions | Capabilities reachable | Domains reachable |
|---|---|---|---|---|---|
| B2B | 5,140 | 5,140 | 5,140 | 5 dimensions | 6 pillars |
| B2C | 5,140 | 5,140 | 5,140 | 5 dimensions | 6 pillars |
| B2B2C | 5,140 | 5,140 | 5,140 | 5 dimensions | 6 pillars |
| marketplace | 5,140 | 5,140 | 5,140 | 5 dimensions | 6 pillars |
| D2C | 5,140 | 5,140 | 5,140 | 5 dimensions | 6 pillars |
| other | 5,140 | 5,140 | 5,140 | 5 dimensions | 6 pillars |

**Every row is identical because business model is not an axis anywhere in the question
bank.** There is no `business_model` column on `questions`, `problems`, `root_causes` or
`interventions`; no applicability table; and no reference to business model in
`stage_scope`, `context_scope` or `engine`. The only storage is
`founders.business_model` — a free-text varchar with no CHECK constraint, and in live data
it takes exactly two values: `B2B` (6 founders) and NULL (41).

Per the brief, not every capability needs a business-model-specific question, and I am not
flagging this as a content gap. It is recorded as an architecture observation: **Ally
currently cannot distinguish any diagnostic capability by business model**, and the
onboarding value it collects is unconstrained and unused downstream.

`context_scope.py` is the one place a situational axis of this kind is implemented
(`fundraising_intent`, gating 6 FND problems). It is the pattern a business-model gate would
follow if one were ever wanted.

---

## 11. Question quality / redundancy scan

Both mechanisms were used: the **existing pgvector embeddings** (`text-embedding-3-small`,
1536-dim, cosine, HNSW index) for semantic similarity, and a deterministic lexical/structural
scan for the rest.

| Check | Result | Assessment |
|---|---|---|
| Duplicate `question_code` | **0** | clean (unique constraint holds) |
| Exact duplicate `question_text` (lowercased, trimmed) | **47 groups, 107 questions** | see below |
| Duplicate text within the same problem | **0** | clean |
| Duplicate text across different problems | **47** | all 47 groups |
| Questions with no problem FK | **0** | `NOT NULL` + FK |
| Questions with no root-cause FK | **0** | `NOT NULL` + FK |
| **Question's root cause belongs to a different problem** | **14** | `S01-FIN-017` … `S01-FIN-030`, all on `FIN-001` pointing at `RC-1281`–`RC-1287` |
| Questions with NULL `primary_stage_group` | **0** | clean |
| Questions with no tag mapping | **0** | clean (8,359 mappings) |
| Questions with no capability/pillar mapping | **0** structurally; **4,876 (94.9%)** with no *dimension* | see §4b |
| Questions with no intervention pathway | **661 (12.9%)** | 181 of them under a problem with no intervention at all |
| Problems with 0 questions | **1** | |
| Problems with 0 interventions | **6** (carrying 181 questions) | `FIN-152`, `FIN-153`, `MEX-102`, `MEX-103`, `SLX-196`, `TM-077` |
| Root causes with 0 questions | **226** | unanswerable causes |
| Intervention root-cause codes that don't exist | **101** | dangling references |
| Interventions with no `framework_codes` | **1,411 of 1,440 (98%)** | |
| Largest single problem | **157 questions** (`PRD-002`) | |
| Problems with >50 questions | **10** | |

### 11a. Exact duplicates — suspicious cases

All 47 groups sit inside the industry batches and are deliberate per-industry clones. They
become genuine redundancy **only because the industry gate does not run** (§9.1).

| Question text | Copies | Codes / problems |
|---|---|---|
| *"Did you set your price from your own cost or from competitors?"* | **6** | `S0-LOG-010`/LOG-002, `S0-RTL-010`/RTL-002, `S0-SPF-009`/SPF-002, `S0-TEL-009`/TEL-002, `S0-TXT-009`/TXT-002, `S0-DLV-009`/DLV-002 |
| *"If the person who tracks compliance left, what would happen?"* | **5** | `S10-LOG-016`, `S10-NGO-013`, `S10-PHM-016`, `S10-TEL-012`, `S10-DLV-012` |
| *"Is there anything written down that a new site could run from?"* | **4** | `S10-FNB-002`, `S10-TRV-002`, `S10-RTL-006`, `S10-SPF-006` |
| *"If your largest account left, how long could you continue?"* | 3 | `S10-SPF-003`, `S10-TEL-003`, `S10-DLV-003` |
| *"If your largest buyer left, how long could you continue?"* | 3 | `S10-MFG-004`, `S10-PHM-003`, `S10-TXT-003` |
| *"If your largest client left, how long could you continue?"* | 3 | `S10-LGL-008`, `S10-MKT-004`, `S10-SVC-003` |
| *"Who decides your payment terms?"* | 3 | `S10-MFG-003`, `S10-LGL-007`, `S10-LOG-003` |

Note the last three rows are also **near**-duplicates of each other — *account* / *buyer* /
*client* is the only difference across 9 questions asking one thing.

### 11b. Semantic near-duplicate scan

Nearest-neighbour cosine distance, 1-in-7 deterministic sample of the **3,340 embedded**
questions (n = 477). **The 1,800 industry questions could not be scanned — they have no
embeddings** (§11d).

| Nearest-neighbour distance | Questions | % | Nearest sits in a different problem |
|---|---|---|---|
| < 0.05 (near-identical) | **0** | 0.0% | — |
| 0.05 – 0.10 (very similar) | 6 | 1.3% | 3 |
| 0.10 – 0.15 (similar) | 8 | 1.7% | 3 |
| 0.15 – 0.25 (related) | 56 | 11.7% | 22 |
| ≥ 0.25 (distinct) | 407 | 85.3% | 258 |

**The universal bank is not redundant.** No near-identical pairs at all, and 85% of
questions have no close neighbour anywhere.

### 11c. Same question mapped to unrelated concepts

The 14 `FIN-001` questions whose root cause belongs to a different problem are the clearest
case: a question filed under one problem and scored through another problem's root cause.
Beyond those, the 47 duplicate texts each map to 2–6 different problems by design.

### 11d. Questions whose answer cannot materially affect diagnosis

| Population | Count | Why it cannot move the diagnosis |
|---|---|---|
| Root cause reaches no intervention | **661** | can raise a finding, cannot produce a recommendation |
| Under a problem with zero interventions | **181** | same, at problem level; 6 problems, 30–31 questions each |
| Root cause has no `root_cause_weights` row | **2,298 (44.7%)** | no stage weighting applied to its contribution |
| Problem has no `problem_stage_mapping` | **3,225 (62.7%)** | no stage-prevalence signal |
| Neither red nor green flag pattern | **3,013 (58.6%)** | no deterministic scoring cue |
| **Zero-vector embedding** | **1,800 (35.0%)** | invisible to retrieval, enrichment and semantic ranking |

**The embedding finding is the largest single defect in the bank:**

| Table | Rows | Unembedded | % | All industry-specific? |
|---|---|---|---|---|
| `questions` | 5,140 | **1,800** | 35.0% | yes, exactly |
| `problems` | 723 | **450** | 62.2% | yes, exactly |
| `root_causes` | 3,996 | **1,987** | 49.7% | yes, exactly |

Every unembedded row is an industry row, and every industry row is unembedded — `embedding`
is `NOT NULL` on all three tables, so the seed scripts wrote zero vectors with
`embedding_model IS NULL`. Cosine distance against a zero vector is NaN, which is what a
full-bank similarity scan hits.

---

## 12. Diagnostic path coverage

The brief's intended pipeline is:
`Question → Answer → Evidence → Capability Assessment → Gap → Gap Priority → Intervention →
20-day target → Strategic Direction`.

**Four of those nine layers have no implementation.** Verified against the schema and
`app/`:

| Layer | Status |
|---|---|
| Question | ✅ `questions` |
| Answer | ✅ `answers` (`score`, `score_label`, `confirmation_status`) |
| **Evidence** | ❌ no store. `evidence_*` in `reasoning/` means confidence signals and retrieval hits, not capability evidence |
| **Capability Assessment** | ⚠️ partial — `stage_assessments` + `detected_root_causes` assess at **pillar** level, never at capability/dimension level |
| **Gap** | ❌ no `gap` table, class or field anywhere (`grep -rn 'gap_priority\|class .*Gap' app/` → nothing) |
| **Gap Priority** | ❌ absent |
| Intervention | ✅ `interventions` + `reasoning/engines/recommendation.py` |
| **20-day target** | ❌ absent (`grep -rn '20-day\|20 day\|twenty.day' app/` → nothing) |
| **Strategic Direction** | ❌ absent (`grep -rln 'strategic_direction\|StrategicDirection' app/` → nothing) |

The path that actually runs is:
`question → answer (scored) → detected_root_causes → recommendation (intervention) →
report section` (`reasoning/reporting/generator.py`: founder stage, business health,
executive summary, next steps).

Per-dimension classification against the **implemented** path:

| Classification | Dimensions | Which |
|---|---|---|
| **COMPLETE** (question → assessment → intervention, at dimension resolution) | **2** | `customer_definition` (37 q, 7 iv), `competitive_awareness` (44 q, 5 iv) |
| **PARTIAL** (path exists but breaks at one or more stages) | **3** | `revenue_model_clarity` (nothing at Stage 1→10+), `plan_to_vision_alignment` (nothing at Stage 1→10+), `prioritization_discipline` (nothing at Stage 0→1) |
| **UNMEASURABLE** (no question reachable by dimension) | **15** | all of pillars 1, 4, 5, plus `problem_definition`, `market_sizing_reality`, `demand_reality`, `revenue_concentration`, `pricing_confidence`, `institutional_memory` |
| **NO_INTERVENTION** | **0** | every reachable dimension has 5 interventions |
| **NOT_REQUIRED** | **0** at the all-stages level | exclusions are per-stage only (Part 3), never global |

At **pillar** resolution — which is what Ally actually reports on today — the picture is far
better: **4 of 6 pillars are COMPLETE** (Founder Readiness, Product & Execution, Team &
Leadership, Strategic Clarity: ≥93% of questions reach an intervention) and **2 are
PARTIAL** (Market Clarity 65%, Revenue Maturity 88%). **No pillar is UNMEASURABLE.**

**The 15 UNMEASURABLE dimensions are unmeasurable for want of a label, not for want of a
question.** Every one of them sits under a pillar holding 374–1,613 questions.

---

## 13. Stage output sufficiency

| # | Stage | Status | Reasons (measured) | Missing coverage |
|---|---|---|---|---|
| 1 | Ideation | **HEALTHY** | 761 eligible vs budget 14 (54×); 4/4 in-scope pillars covered (105/421/150/85); 564 (74%) reach an intervention; 4 of 9 in-scope dimensions reachable — the best dimension coverage of any stage | 5 in-scope dimensions unreachable; Market Clarity loses 47% of its questions to missing intervention mappings (421→224) |
| 2 | Validation | **HEALTHY** | 1,990 eligible vs budget 20 (100×); all 6 pillars ≥71; 1,839 (92%) reach an intervention | 14 of 18 in-scope dimensions unreachable; indistinguishable from stages 3 and 4 |
| 3 | Prototype / MVP | **HEALTHY** | identical to Validation; budget 24 (83×) | as above |
| 4 | Early Traction | **HEALTHY** | identical to Validation; budget 30 (66×) | as above |
| 5 | Growth / Scaling | **HEALTHY** | 2,228 eligible vs budget 30 (74×); all 6 pillars ≥124; 1,915 (86%) reach an intervention; 121 problems stage-mapped — the richest stage-prevalence signal in the bank | 18 of 20 dimensions unreachable; Revenue Maturity loses 21% (658→519) |
| 6 | Expansion | **HEALTHY** | same bank; 110 problems stage-mapped; budget 32 (70×) | as above |
| 7 | Maturity | **THIN** (downstream, not questions) | same 2,228 questions, but only **80** problems and **789** questions carry a stage mapping for it, and **646** root-cause stage weights — roughly a third of Growth's | stage-specific prevalence signal is materially weaker than 5/6 |
| 8 | **Exit** | **STRUCTURAL GAP** | 2,228 questions eligible, but only **8 problems** map to this stage (vs 121 at Growth), spanning **3 of 6 pillars**, reaching **50 questions** and **42 root-cause stage weights** (2.4% of Growth's 1,767). The stage shares its entire question bank with Growth and has no tagging that distinguishes an exit-stage founder from a scaling one | Exit-specific problems across pillars 1, 2, 4, 5, 6; exit-stage root-cause weighting; any exit-specific question wording |

**Sufficiency was judged on usable question count, pillar coverage, intervention coverage and
stage-prevalence signal together — not on raw question count.** On raw count alone every
stage would read HEALTHY, including Exit.

---

## 14. Question bank sufficiency verdict

### A. NO ACTION REQUIRED — coverage is sufficient

1. **Overall question volume.** 5,140 questions against per-session budgets of 14–32. Every
   stage has 24×–74× its budget available.
2. **Pillar coverage at every stage.** No in-scope pillar has fewer than 71 eligible
   questions at any stage.
3. **Redundancy in the universal bank.** Zero near-identical pairs; 85% of sampled questions
   have no neighbour closer than 0.25.
4. **Per-industry question volume.** All 30 canonical industries carry exactly 60 questions
   across all 3 stage groups. The catalogue is complete.
5. **Business-model coverage.** Not an axis, and per the brief not every capability needs
   one. No questions required.
6. **Question tagging and referential integrity.** 100% tagged, zero orphans, zero duplicate
   codes, zero NULL stage groups.

### B. CONTENT GAP — questions should probably be added

**One, and it is conditional.**

1. **Exit stage (stage_order 8).** 8 problems, 3 pillars, 50 questions, 42 root-cause stage
   weights. Exit has no diagnostic identity of its own — it borrows Growth's entire bank.
   **This is only a content gap if Exit is a product commitment.** If Exit founders are not
   a served segment today, reclassify as NOT_REQUIRED and close it. See §15.

**Everything else that looks like a content gap is not one.** The 15 unreachable dimensions,
the 661 intervention-less questions, the 5 single-pillar industries and the 26 industries
without stage thresholds are all cases where the questions already exist and a mapping,
label or embedding is missing. Adding questions to any of them would add rows without adding
diagnostic reach.

### C. ARCHITECTURE / DATA GAP — questions exist, the surrounding data does not

Ordered by diagnostic impact.

| # | Gap | Scale | Effect | Fix shape |
|---|---|---|---|---|
| 1 | `problems.dimension_code` NULL | **459 of 723 problems**; 4,876 of 5,140 questions | 15 of 20 Business DNA dimensions unreportable; `stage_scope`'s dimension filter is a no-op for 95% of the bank | content pass over `problems`, per migration `c3f7b28d5e91` and `scripts/backfill_problem_dimensions.py` |
| 2 | Industry layer unembedded | **1,800 q + 450 problems + 1,987 RCs** | semantic retrieval, enrichment and similarity ranking inoperative across the whole industry layer; NaN distances | run the embedding backfill over industry rows |
| 3 | `questions.industry_relevance` not read by code | 5,140 rows populated, 0 reads | industry questions served to every founder; 107 exact duplicates become live in-session repeats | add the filter in `diagnosis/repository.list_candidate_questions`, mirroring `recommendation.py` |
| 4 | Missing root-cause → intervention mappings | **661 questions (12.9%)**, incl. 181 under 6 intervention-less problems | questions produce findings that cannot produce recommendations | add `interventions` rows / extend `root_cause_ids` for `FIN-152`, `FIN-153`, `MEX-102`, `MEX-103`, `SLX-196`, `TM-077` |
| 5 | Evidence / Gap / Gap-Priority / 20-day / Strategic-Direction layers absent | 5 of 9 pipeline stages | the pipeline in the brief cannot be traced end to end because it is not built | product/architecture decision, not data |
| 6 | 101 dangling root-cause codes in `interventions.root_cause_ids` | 101 codes | silently unmatchable mappings | reconcile codes against `root_causes` |
| 7 | 26 of 30 industries have no `industry_stage_thresholds` | 32 of 240 rows (13%) | no industry-adjusted stage classification for 87% of the catalogue | seed the remaining 208 rows |
| 8 | 14 questions whose root cause belongs to another problem | `S01-FIN-017`…`S01-FIN-030` | scored through the wrong problem's cause | repoint `problem_id` or `root_cause_id` |
| 9 | 3 question categories unknown to `business_dna.PILLAR_BY_CATEGORY` | `Strategy & Planning` (128), `Product Development` (15), `Marketing & Growth` (5) | category scope cannot reason about them; safe today only because the list is a deny-list and none appear at Stage 0 | add to the category map |

Minor, recorded without a flag: `visual_question_bank` is empty (0 rows);
`business_dimensions` exists in the ORM but has no table; 1,411 of 1,440 interventions carry
no `framework_codes`; 226 root causes have no question.

---

## 15. Question addition recommendation

Per the brief, questions are recommended **only** where the audit demonstrates a genuine
content gap. That is **one candidate**, and it is conditional.

### Proposed content gap 1 — Exit stage differentiation

| Field | Value |
|---|---|
| **Stage** | Exit (`stage_order` 8, `stage_id` 8) |
| **Capability** | No Business DNA dimension is exit-specific. In pillar terms: Strategic Clarity (institutional memory, succession), Revenue Maturity (revenue concentration, valuation-grade reporting), Founder Readiness (founder dependency / bus factor), Team & Leadership (succession, decision rights) |
| **Evidence criterion** | n/a — no criterion store exists (§5) |
| **Current usable question count** | 2,228 eligible, but **50** reachable via `problem_stage_mapping` for this stage, across **8 problems** and **3 of 6 pillars** |
| **Why existing questions are insufficient** | Not a wording problem — a tagging problem that is also a content problem. Exit shares its entire bank with Growth/Expansion/Maturity because `primary_stage_group` has only three values. Even the finer `problem_stage_mapping` axis gives Exit 8 problems against Growth's 121 and 42 root-cause stage weights against 1,767. Ally cannot currently distinguish a founder preparing to exit from one scaling, and none of the 2,228 available questions asks about due diligence readiness, buyer/acquirer fit, founder-dependency-at-exit, or valuation-grade financial hygiene |
| **What type of question is missing** | Exit-readiness diagnostics: transferability of the business without the founder; diligence-grade financial and legal record quality; buyer/acquirer landscape awareness; succession and key-person risk; revenue concentration seen through an acquirer's eyes; the founder's own post-exit intent and its effect on decisions |
| **Approximate number required** | **25–40**, sized to the stage's budget of 30. Roughly 6–8 each across Founder Readiness, Revenue Maturity, Team & Leadership and Strategic Clarity, plus 4–6 in Product & Execution on process transferability |
| **Universal or context-specific** | **Universal**, gated by a **new `context_scope` precondition** (`exit_intent`), following the existing `fundraising_intent` pattern exactly. Not industry-specific: exit readiness is structural. A `problem_stage_mapping` entry at `stage_id = 8` is required for each new problem, or the questions will be as invisible as the current bank is |

**Precondition on acting:** confirm Exit is a served segment. If it is not, this is
`NOT_REQUIRED`, and the correct action is to record that decision rather than write
questions.

**No question is recommended for anything else in this audit.** In particular, do not add
questions for the 15 unreachable dimensions — 374 to 1,613 questions already exist under
each of those pillars, and what is missing is `problems.dimension_code`.

---

## 16. Exact queries used

All queries are `SELECT`-only, run via the Supabase MCP `execute_sql` tool against project
`wxggmjvyzuerjbhhtcab`. No DDL, no DML, no transaction wrote anything.

```sql
-- 1. Schema inventory: does a capability layer exist?
SELECT table_name,
       (SELECT count(*) FROM information_schema.columns c
         WHERE c.table_name = t.table_name AND c.table_schema = 'public') AS cols
FROM information_schema.tables t
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- 2. Column inventory for the tables the audit depends on
SELECT table_name, ordinal_position, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('questions','question_tags','question_tag_mapping','problems',
                     'root_causes','interventions','readiness_pillars','founder_stages',
                     'industries','problem_stage_mapping','industry_stage_thresholds',
                     'stage_diagnosis_logic','founder_context','founders','answers',
                     'sessions','founder_dna_questions','current_problem_questions',
                     'visual_question_bank')
ORDER BY table_name, ordinal_position;

-- 3. Reference-data inventory (stages, pillars, row counts)
SELECT 'stages' AS k, stage_id::text AS a, stage_name AS b,
       stage_order::text AS c, question_budget::text AS d FROM founder_stages
UNION ALL SELECT 'pillars', pillar_id::text, pillar_name,
       pillar_weightage::text, pillar_order::text FROM readiness_pillars
UNION ALL SELECT 'counts','questions',count(*)::text,'','' FROM questions
UNION ALL SELECT 'counts','problems',count(*)::text,'','' FROM problems
UNION ALL SELECT 'counts','root_causes',count(*)::text,'','' FROM root_causes
UNION ALL SELECT 'counts','interventions',count(*)::text,'','' FROM interventions
UNION ALL SELECT 'counts','industries',count(*)::text,'','' FROM industries
UNION ALL SELECT 'counts','question_tags',count(*)::text,'','' FROM question_tags
UNION ALL SELECT 'counts','question_tag_mapping',count(*)::text,'','' FROM question_tag_mapping
UNION ALL SELECT 'counts','problem_stage_mapping',count(*)::text,'','' FROM problem_stage_mapping
UNION ALL SELECT 'counts','founder_dna_questions',count(*)::text,'','' FROM founder_dna_questions
UNION ALL SELECT 'counts','current_problem_questions',count(*)::text,'','' FROM current_problem_questions
UNION ALL SELECT 'counts','visual_question_bank',count(*)::text,'','' FROM visual_question_bank
UNION ALL SELECT 'counts','industry_stage_thresholds',count(*)::text,'','' FROM industry_stage_thresholds
UNION ALL SELECT 'counts','stage_diagnosis_logic',count(*)::text,'','' FROM stage_diagnosis_logic
ORDER BY 1, 2;

-- 4. Is interventions.capability_domain a controlled 34-item taxonomy?  (No: 450 values)
SELECT capability_domain, count(*) AS interventions, count(DISTINCT problem_id) AS problems
FROM interventions GROUP BY 1 ORDER BY 1;

-- 5. §3a Stage-group coverage
SELECT q.primary_stage_group AS grp,
  count(*) AS total,
  count(*) FILTER (WHERE q.industry_relevance ? 'all') AS universal,
  count(*) FILTER (WHERE NOT (q.industry_relevance ? 'all')) AS industry_specific,
  count(*) FILTER (WHERE q.embedding_model IS NOT NULL) AS embedded,
  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM interventions i
      WHERE i.problem_id = q.problem_id AND i.root_cause_ids ? rc.root_cause_code)) AS rc_to_intervention,
  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM problem_stage_mapping m
      WHERE m.problem_id = q.problem_id)) AS problem_stage_mapped,
  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM root_cause_weights w
      WHERE w.root_cause_id = q.root_cause_id)) AS rc_stage_weighted,
  count(*) FILTER (WHERE p.dimension_code IS NOT NULL) AS dimension_mapped
FROM questions q
JOIN problems p ON p.problem_id = q.problem_id
JOIN root_causes rc ON rc.root_cause_id = q.root_cause_id
GROUP BY 1 ORDER BY 1;

-- 6. §3b + §8 Stage x pillar matrix, applying the engine's real scope rules.
--    The literal arrays transcribe app/api/v1/diagnosis/business_dna.py
--    (STAGE_0_EXCLUDED / STAGE_0_TO_1_EXCLUDED) through stage_scope.pillars,
--    .withheld_categories and .excluded_dimensions.
WITH stage AS (
  SELECT s.stage_order, s.stage_name,
    CASE WHEN s.stage_order <= 1 THEN 'Stage 0'
         WHEN s.stage_order <= 4 THEN 'Stage 0→1'
         ELSE 'Stage 1→10+' END AS grp,
    CASE WHEN s.stage_order <= 1 THEN ARRAY[1,2,4,6]
         ELSE ARRAY[1,2,3,4,5,6] END AS pillars,
    CASE WHEN s.stage_order <= 1 THEN ARRAY['Financial Management','Fundraising','Go-To-Market',
           'Marketing Execution','Sales & Revenue','Sales Execution',
           'Scaling & Operational Maturity','Team & Leadership']
         ELSE ARRAY[]::text[] END AS withheld,
    CASE WHEN s.stage_order <= 1 THEN ARRAY['build_demand_alignment','decision_rights',
           'demand_reality','founder_dependency','hiring_repeatability','institutional_memory',
           'pricing_confidence','reliability_real_world','revenue_concentration',
           'revenue_model_clarity','team_structure_role_clarity']
         WHEN s.stage_order <= 4 THEN ARRAY['hiring_repeatability','revenue_concentration']
         ELSE ARRAY[]::text[] END AS excl
  FROM founder_stages s),
q AS (
  SELECT q.question_id, q.primary_stage_group AS grp, q.category AS q_cat,
         p.pillar_id, p.category AS p_cat, p.dimension_code,
         EXISTS (SELECT 1 FROM interventions i
                  WHERE i.problem_id = p.problem_id
                    AND i.root_cause_ids ? rc.root_cause_code) AS rc_int
  FROM questions q
  JOIN problems p ON p.problem_id = q.problem_id
  JOIN root_causes rc ON rc.root_cause_id = q.root_cause_id)
SELECT st.stage_order, st.stage_name, q.pillar_id,
       count(*) AS eligible,
       count(*) FILTER (WHERE q.rc_int) AS usable_with_intervention
FROM stage st
JOIN q ON q.grp = st.grp
  AND q.pillar_id = ANY (st.pillars)
  AND NOT (q.q_cat = ANY (st.withheld))
  AND NOT (q.p_cat = ANY (st.withheld))
  AND (q.dimension_code IS NULL OR NOT (q.dimension_code = ANY (st.excl)))
GROUP BY 1, 2, 3 ORDER BY 1, 3;

-- 7. §4a Pillar coverage and downstream path completeness
WITH qpath AS (
  SELECT q.question_id, q.red_flag_pattern, q.green_flag_pattern,
         p.problem_id, p.pillar_id, rc.root_cause_id, rc.root_cause_code,
         EXISTS (SELECT 1 FROM interventions i WHERE i.problem_id = p.problem_id
                   AND i.root_cause_ids ? rc.root_cause_code) AS rc_int,
         EXISTS (SELECT 1 FROM interventions i WHERE i.problem_id = p.problem_id
                   AND i.secondary_root_cause_ids ? rc.root_cause_code) AS rc_int_sec,
         EXISTS (SELECT 1 FROM interventions i WHERE i.problem_id = p.problem_id) AS prob_int,
         EXISTS (SELECT 1 FROM root_cause_weights w WHERE w.root_cause_id = rc.root_cause_id) AS rc_weighted,
         EXISTS (SELECT 1 FROM problem_stage_mapping m WHERE m.problem_id = p.problem_id) AS prob_staged
  FROM questions q
  JOIN problems p ON p.problem_id = q.problem_id
  JOIN root_causes rc ON rc.root_cause_id = q.root_cause_id)
SELECT 'PILLAR ' || pillar_id AS scope, count(*) AS questions,
       count(*) FILTER (WHERE rc_int)                AS q_rc_primary_intervention,
       count(*) FILTER (WHERE rc_int OR rc_int_sec)  AS q_rc_any_intervention,
       count(*) FILTER (WHERE prob_int)              AS q_problem_intervention,
       count(*) FILTER (WHERE NOT prob_int)          AS q_no_intervention_at_all,
       count(*) FILTER (WHERE rc_weighted)           AS q_rc_stage_weighted,
       count(*) FILTER (WHERE prob_staged)           AS q_problem_stage_mapped,
       count(*) FILTER (WHERE red_flag_pattern IS NULL AND green_flag_pattern IS NULL) AS q_no_flag_pattern,
       count(DISTINCT root_cause_id) AS distinct_rcs, count(DISTINCT problem_id) AS distinct_problems
FROM qpath GROUP BY pillar_id ORDER BY 1;
-- (the same query with 'TOTAL' and no GROUP BY produces the total row)

-- 8. §4b + §7 Dimension ("capability") coverage. The 20-row VALUES list transcribes
--    business_dna.DIMENSIONS verbatim.
WITH dims(pillar_id, code) AS (VALUES
 (1,'skill_stage_fit'),(1,'time_allocation_reality'),(1,'founder_dependency'),
 (2,'problem_definition'),(2,'customer_definition'),(2,'competitive_awareness'),(2,'market_sizing_reality'),
 (3,'demand_reality'),(3,'revenue_model_clarity'),(3,'revenue_concentration'),(3,'pricing_confidence'),
 (4,'build_demand_alignment'),(4,'execution_velocity'),(4,'reliability_real_world'),
 (5,'team_structure_role_clarity'),(5,'decision_rights'),(5,'hiring_repeatability'),
 (6,'plan_to_vision_alignment'),(6,'prioritization_discipline'),(6,'institutional_memory'))
SELECT d.pillar_id, d.code,
  (SELECT count(*) FROM problems p WHERE p.dimension_code = d.code) AS problems,
  (SELECT count(*) FROM questions q JOIN problems p ON p.problem_id = q.problem_id
     WHERE p.dimension_code = d.code) AS questions,
  (SELECT count(*) FROM questions q JOIN problems p ON p.problem_id = q.problem_id
     WHERE p.dimension_code = d.code AND q.primary_stage_group = 'Stage 0') AS s0,
  (SELECT count(*) FROM questions q JOIN problems p ON p.problem_id = q.problem_id
     WHERE p.dimension_code = d.code AND q.primary_stage_group = 'Stage 0→1') AS s01,
  (SELECT count(*) FROM questions q JOIN problems p ON p.problem_id = q.problem_id
     WHERE p.dimension_code = d.code AND q.primary_stage_group = 'Stage 1→10+') AS s110,
  (SELECT count(*) FROM interventions i JOIN problems p ON p.problem_id = i.problem_id
     WHERE p.dimension_code = d.code) AS interventions
FROM dims d ORDER BY d.pillar_id, d.code;

-- 9. §8 Category x pillar x stage-group breakdown
SELECT p.pillar_id, q.category,
  count(*) FILTER (WHERE q.primary_stage_group = 'Stage 0')      AS s0,
  count(*) FILTER (WHERE q.primary_stage_group = 'Stage 0→1')    AS s01,
  count(*) FILTER (WHERE q.primary_stage_group = 'Stage 1→10+')  AS s110,
  count(*) AS total,
  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM interventions i
      WHERE i.problem_id = p.problem_id AND i.root_cause_ids ? rc.root_cause_code)) AS with_intervention
FROM questions q
JOIN problems p ON p.problem_id = q.problem_id
JOIN root_causes rc ON rc.root_cause_id = q.root_cause_id
GROUP BY 1, 2 ORDER BY 1, 2;

-- 10. §9 Industry coverage against the canonical 30-industry catalogue
WITH ind AS (SELECT i.industry_code, i.industry_name FROM industries i)
SELECT ind.industry_code,
  (SELECT count(*) FROM questions q WHERE q.industry_relevance ? ind.industry_code) AS specific_q,
  (SELECT count(DISTINCT p.pillar_id) FROM questions q JOIN problems p ON p.problem_id = q.problem_id
     WHERE q.industry_relevance ? ind.industry_code) AS pillars,
  (SELECT count(DISTINCT p.category) FROM questions q JOIN problems p ON p.problem_id = q.problem_id
     WHERE q.industry_relevance ? ind.industry_code) AS categories,
  (SELECT count(DISTINCT q.problem_id) FROM questions q WHERE q.industry_relevance ? ind.industry_code) AS problems,
  (SELECT count(DISTINCT q.primary_stage_group) FROM questions q WHERE q.industry_relevance ? ind.industry_code) AS stage_groups,
  (SELECT count(*) FROM interventions iv WHERE iv.industry_relevance ? ind.industry_code) AS ind_interventions,
  (SELECT count(*) FROM problems p WHERE p.industry_relevance ? ind.industry_code) AS ind_problems,
  (SELECT count(*) FROM industry_stage_thresholds t JOIN industries i2 ON i2.industry_id = t.industry_id
     WHERE i2.industry_code = ind.industry_code) AS stage_thresholds
FROM ind ORDER BY 1;

-- 11. §9 industry_relevance value distribution ('all' x 3340 + 30 industries x 60)
SELECT v.val, count(*) FROM questions q,
  LATERAL jsonb_array_elements_text(q.industry_relevance) AS v(val)
GROUP BY 1 ORDER BY 2 DESC;

-- 12. §10 Business-model axis: the only storage anywhere
SELECT coalesce(business_model, '(null)') AS business_model, count(*) FROM founders GROUP BY 1;

-- 13. §11 Structural quality / redundancy scan
SELECT 'exact_dup_text' AS check, count(*)::text AS n
  FROM (SELECT lower(btrim(question_text)) t FROM questions GROUP BY 1 HAVING count(*) > 1) x
UNION ALL SELECT 'questions_in_exact_dup_groups', sum(c)::text
  FROM (SELECT count(*) c FROM questions GROUP BY lower(btrim(question_text)) HAVING count(*) > 1) y
UNION ALL SELECT 'dup_question_code', count(*)::text
  FROM (SELECT question_code FROM questions GROUP BY 1 HAVING count(*) > 1) z
UNION ALL SELECT 'dup_text_same_problem', count(*)::text
  FROM (SELECT problem_id, lower(btrim(question_text)) FROM questions GROUP BY 1,2 HAVING count(*) > 1) a
UNION ALL SELECT 'dup_text_across_problems', count(*)::text
  FROM (SELECT lower(btrim(question_text)) FROM questions GROUP BY 1 HAVING count(DISTINCT problem_id) > 1) b
UNION ALL SELECT 'q_orphan_problem', count(*)::text
  FROM questions q LEFT JOIN problems p ON p.problem_id = q.problem_id WHERE p.problem_id IS NULL
UNION ALL SELECT 'q_orphan_root_cause', count(*)::text
  FROM questions q LEFT JOIN root_causes rc ON rc.root_cause_id = q.root_cause_id WHERE rc.root_cause_id IS NULL
UNION ALL SELECT 'q_rc_problem_mismatch', count(*)::text
  FROM questions q JOIN root_causes rc ON rc.root_cause_id = q.root_cause_id WHERE rc.problem_id <> q.problem_id
UNION ALL SELECT 'q_null_stage_group', count(*)::text FROM questions WHERE primary_stage_group IS NULL
UNION ALL SELECT 'problems_zero_questions', count(*)::text
  FROM problems p WHERE NOT EXISTS (SELECT 1 FROM questions q WHERE q.problem_id = p.problem_id)
UNION ALL SELECT 'root_causes_zero_questions', count(*)::text
  FROM root_causes rc WHERE NOT EXISTS (SELECT 1 FROM questions q WHERE q.root_cause_id = rc.root_cause_id)
UNION ALL SELECT 'problems_zero_interventions', count(*)::text
  FROM problems p WHERE NOT EXISTS (SELECT 1 FROM interventions i WHERE i.problem_id = p.problem_id)
UNION ALL SELECT 'questions_untagged', count(*)::text
  FROM questions q WHERE NOT EXISTS (SELECT 1 FROM question_tag_mapping m WHERE m.question_id = q.question_id)
UNION ALL SELECT 'max_questions_per_problem', max(c)::text
  FROM (SELECT count(*) c FROM questions GROUP BY problem_id) d
UNION ALL SELECT 'problems_over_50_questions', count(*)::text
  FROM (SELECT problem_id FROM questions GROUP BY 1 HAVING count(*) > 50) e;

-- 14. §11a Exact duplicate examples
SELECT lower(btrim(q.question_text)) AS text, count(*) AS n,
       string_agg(q.question_code || ' [' || p.problem_code || '/' || q.primary_stage_group || ']',
                  ' | ' ORDER BY q.question_id) AS occurrences
FROM questions q JOIN problems p ON p.problem_id = q.problem_id
GROUP BY 1 HAVING count(*) > 1 ORDER BY 2 DESC, 1;

-- 15. §11 Very large mixed problems
SELECT p.problem_code, p.problem_name, p.category, p.pillar_id,
       count(q.question_id) AS questions, count(DISTINCT q.root_cause_id) AS rcs,
       (SELECT count(*) FROM interventions i WHERE i.problem_id = p.problem_id) AS interventions
FROM problems p JOIN questions q ON q.problem_id = p.problem_id
GROUP BY 1, 2, 3, 4, p.problem_id HAVING count(q.question_id) > 50 ORDER BY 5 DESC;

-- 16. §11d Embedding health (this is what makes a full similarity scan return NaN)
SELECT embedding_model, embedding_dimension, count(*) AS n,
       count(*) FILTER (WHERE embedding = array_fill(0, ARRAY[vector_dims(embedding)])::vector) AS zero_vectors
FROM questions GROUP BY 1, 2 ORDER BY 3 DESC;

SELECT 'questions' AS t, count(*) FILTER (WHERE embedding_model IS NULL) AS unembedded, count(*) AS total,
       count(*) FILTER (WHERE embedding_model IS NULL AND NOT (industry_relevance ? 'all')) AS unembedded_and_industry_specific
FROM questions
UNION ALL SELECT 'problems', count(*) FILTER (WHERE embedding_model IS NULL), count(*),
       count(*) FILTER (WHERE embedding_model IS NULL AND industry_relevance IS NOT NULL
                          AND NOT (industry_relevance ? 'all')) FROM problems
UNION ALL SELECT 'root_causes', count(*) FILTER (WHERE embedding_model IS NULL), count(*),
       count(*) FILTER (WHERE embedding_model IS NULL AND industry_relevance IS NOT NULL
                          AND NOT (industry_relevance ? 'all')) FROM root_causes;

-- 17. §11b Semantic near-duplicate scan, over the embedded subset only.
--     1-in-7 deterministic sample: the full 3,340 x 3,340 scan exceeds the tool's 60s limit.
WITH emb AS (SELECT question_id, problem_id, embedding FROM questions WHERE embedding_model IS NOT NULL),
samp AS (SELECT * FROM emb WHERE question_id % 7 = 0),
nn AS (SELECT s.question_id, s.problem_id, n.dist, n.problem_id AS near_problem
       FROM samp s CROSS JOIN LATERAL (
         SELECT e2.problem_id, s.embedding <=> e2.embedding AS dist
         FROM emb e2 WHERE e2.question_id <> s.question_id
         ORDER BY s.embedding <=> e2.embedding LIMIT 1) n)
SELECT CASE WHEN dist < 0.05 THEN 'a <0.05 near-identical'
            WHEN dist < 0.10 THEN 'b 0.05-0.10 very similar'
            WHEN dist < 0.15 THEN 'c 0.10-0.15 similar'
            WHEN dist < 0.25 THEN 'd 0.15-0.25 related'
            ELSE 'e >=0.25 distinct' END AS band,
       count(*) AS questions,
       count(*) FILTER (WHERE problem_id <> near_problem) AS nearest_in_other_problem
FROM nn GROUP BY 1 ORDER BY 1;

-- 18. §11c + §13 Defect detail: intervention-less problems, cross-problem root causes,
--     and question categories unknown to business_dna.PILLAR_BY_CATEGORY
SELECT 'zero_intervention_problem' AS k, p.problem_code AS a, p.problem_name AS b, p.category AS c,
       (SELECT count(*) FROM questions q WHERE q.problem_id = p.problem_id)::text AS d
FROM problems p WHERE NOT EXISTS (SELECT 1 FROM interventions i WHERE i.problem_id = p.problem_id)
UNION ALL
SELECT 'q_rc_problem_mismatch', q.question_code, p.problem_code, rc.root_cause_code, q.primary_stage_group
FROM questions q JOIN problems p ON p.problem_id = q.problem_id
JOIN root_causes rc ON rc.root_cause_id = q.root_cause_id
WHERE rc.problem_id <> q.problem_id
UNION ALL
SELECT 'category_not_in_dna_map', q.category, count(*)::text, '', ''
FROM questions q
WHERE q.category NOT IN ('Founder Psychology','Idea & Validation','Competitive Awareness',
  'Target Customer & ICP','Marketing Execution','Go-To-Market','Sales Execution','Sales & Revenue',
  'Business Model Design','Financial Management','Fundraising','Product','Operations & Systems',
  'Team & Leadership','Opportunity Evaluation','Business Planning','Risk Identification',
  'Scaling & Operational Maturity')
GROUP BY q.category
ORDER BY 1, 2;

-- 19. §13 Per-stage prevalence signal -- the axis on which Exit collapses
SELECT s.stage_id, s.stage_name,
  count(DISTINCT m.problem_id) AS problems_mapped_to_stage,
  count(DISTINCT p.pillar_id)  AS pillars,
  (SELECT count(*) FROM questions q JOIN problem_stage_mapping m2 ON m2.problem_id = q.problem_id
     WHERE m2.stage_id = s.stage_id) AS questions_via_stage_mapping,
  (SELECT count(*) FROM root_cause_weights w WHERE w.stage_id = s.stage_id) AS rc_weights
FROM founder_stages s
LEFT JOIN problem_stage_mapping m ON m.stage_id = s.stage_id
LEFT JOIN problems p ON p.problem_id = m.problem_id
GROUP BY 1, 2 ORDER BY 1;

-- 20. §11 + §13 Intervention-layer integrity
SELECT 'interventions_stage_relevance_empty' AS k, count(*)::text AS v
  FROM interventions WHERE stage_relevance IS NULL OR jsonb_array_length(stage_relevance) = 0
UNION ALL SELECT 'interventions_industry_relevance_empty', count(*)::text
  FROM interventions WHERE industry_relevance IS NULL OR jsonb_array_length(industry_relevance) = 0
UNION ALL SELECT 'interventions_no_next_steps', count(*)::text
  FROM interventions WHERE immediate_next_steps IS NULL OR jsonb_array_length(immediate_next_steps) = 0
UNION ALL SELECT 'interventions_no_frameworks', count(*)::text
  FROM interventions WHERE framework_codes IS NULL OR jsonb_array_length(framework_codes) = 0
UNION ALL SELECT 'distinct_capability_domains', count(DISTINCT capability_domain)::text FROM interventions
UNION ALL SELECT 'capability_domains_with_1_intervention', count(*)::text
  FROM (SELECT capability_domain FROM interventions GROUP BY 1 HAVING count(*) = 1) x
UNION ALL SELECT 'interventions_rc_ids_empty', count(*)::text
  FROM interventions WHERE jsonb_array_length(root_cause_ids) = 0
UNION ALL SELECT 'rc_codes_referenced_but_missing', count(*)::text
  FROM (SELECT DISTINCT c.code FROM interventions i, LATERAL jsonb_array_elements_text(i.root_cause_ids) c(code)
        WHERE NOT EXISTS (SELECT 1 FROM root_causes rc WHERE rc.root_cause_code = c.code)) y;

-- 21. §2 Founder DNA / current-problem banks and the canonical industry list
SELECT 'founder_dna_dim' AS k, dimension_code AS a, stage_group AS b, count(*)::text AS c
  FROM founder_dna_questions GROUP BY 1, 2, 3
UNION ALL SELECT 'cpq', stage_group, is_active::text, count(*)::text
  FROM current_problem_questions GROUP BY 2, 3
UNION ALL SELECT 'industries_list', industry_code, industry_name, industry_id::text FROM industries
ORDER BY 1, 2;
```

Repository reads used to establish the architecture (no file was modified):

```
app/models/schema.py                        ORM; confirms no capability tables
app/api/v1/diagnosis/business_dna.py        6 pillars, 20 dimensions, Part 3 stage exclusions
app/api/v1/diagnosis/stage_scope.py         SCOPE_BY_STAGE_ORDER; pillar/category/dimension filters
app/api/v1/diagnosis/context_scope.py       PROBLEM_PRECONDITIONS (fundraising_intent)
app/api/v1/diagnosis/engine.py              stage_groups_for, _in_scope, resolve_stage_groups
app/api/v1/diagnosis/repository.py          list_candidate_questions; confirms industry_relevance unused
app/api/v1/reasoning/engines/recommendation.py   the one consumer of industry_relevance
app/api/v1/reasoning/reporting/generator.py      report sections; confirms no gap/20-day/direction layer

grep -rn "industry_relevance" --include=*.py app/        -> 2 files only
grep -rn "20-day\|20 day\|twenty.day" --include=*.py app/ -> no matches
grep -rln "strategic_direction\|StrategicDirection" app/  -> no matches
grep -rn "gap_priority\|class .*Gap" --include=*.py app/  -> no matches
```

---

## 17. Limitations of the audit

1. **The brief's taxonomy does not exist**, so §4 (capability coverage with confidence
   bands), §5 (evidence criteria) and §7 (stage × capability) could not be answered as
   written. The 20 Business DNA dimensions are the substitute and are a genuine analogue of
   "capability", but they are 20 not 34, they carry no evidence criteria, and they exist
   only in Python — `business_dna.DIMENSIONS` — with no table to join against.
2. **No HIGH/MEDIUM confidence distinction exists** on any question→concept mapping, so the
   requested confidence split is unanswerable. Question→problem is a single `NOT NULL` FK.
3. **"Questions mapped to ≥1 capability" is 100% by construction** and carries no
   information: `problem_id` and `root_cause_id` are both `NOT NULL` with foreign keys. The
   informative version of that metric is dimension mapping, at 5.1%, and I have reported
   both so the 100% is not mistaken for health.
4. **The semantic scan covers 65% of the bank.** The 1,800 industry questions have zero
   vectors and cannot be compared. Their redundancy is assessed lexically only, so
   *paraphrased* industry duplicates beyond the 47 exact groups are not detected. The
   embedded-subset scan is a deterministic 1-in-7 sample (n = 477); a full 3,340 × 3,340
   scan exceeded the 60-second tool limit. Sampling error on the reported percentages is
   roughly ±1.5pp at the 95% level, which does not change any conclusion — the near-identical
   count is 0.
5. **Stage scope was reproduced in SQL, not executed.** The pillar/category/dimension arrays
   in query 6 transcribe `business_dna.py` and `stage_scope.py` as of commit `acaf46f`. They
   are faithful to that source but they are a second implementation; if either module
   changes, the §3b and §8 figures must be recomputed. The `context_scope` precondition gate
   and the round-robin's own degrade paths (`_in_scope` never returns empty) are **not**
   modelled, so per-stage eligible counts are a slight upper bound — by at most 87 questions,
   the size of the precondition-gated set.
6. **Static analysis only.** No session was run, no founder was diagnosed, and answer
   distributions, actual question selection and real report output were not observed. The
   audit measures what the bank *can* support, not what it *does* produce. "Questions whose
   answer cannot materially affect diagnosis" is inferred from missing downstream links, not
   from observed scoring behaviour.
7. **Live production database.** Figures are a point-in-time snapshot at 2026-09-20 and will
   drift as content is seeded. Industry batches A, B and C landed within the preceding 24
   hours, which is very likely why the industry embedding backfill has not yet run — that
   finding in particular should be re-checked before it is actioned.
8. **Expected applicability came from the architecture, not from judgement.** Stage ×
   dimension exclusions are Business DNA Part 3's, transcribed in `business_dna.py`. Where a
   stage is not expected to diagnose a dimension it is marked `—`, never zero. No claim is
   made that every capability should appear at every stage.
9. **Two figures could not be verified independently.** Whether `problems.dimension_code`
   NULLs are "not yet known" versus "not applicable" rests on the migration comment
   (`c3f7b28d5e91`), not on a data test; and whether Exit is a served segment is a product
   question the database cannot answer, which is why §15's single recommendation is
   conditional on it.
