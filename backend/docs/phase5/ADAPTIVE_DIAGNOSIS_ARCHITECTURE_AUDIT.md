# Adaptive Diagnosis Engine — Architecture Audit (Step 1)

Read-only. No code, config, catalogue, migration, DB or production state was
modified. Branch `reconcile/context-aware-diagnosis`; working tree carries the
previously-authorised E+B and stage-prior changes, uncommitted.

Evidence source for live thresholds: local eval DB `ally_e2e`
(socket `/tmp`, port 5433), table `scoring_rules WHERE is_active`.

---

## A. PHASE MAP — what the brief calls things vs. what the code calls them

The brief's flow is already the shipped flow. **No new phase is required, and
none should be inserted.** The mapping is stated verbatim in
`app/api/v1/diagnosis/service.py:266-270`:

> "The doc's three sections in order: Founder DNA, then the Current Problem
> symptom capture, then this — **the Business DNA interrogation**."

| Brief term | Code artefact | Gate |
|---|---|---|
| Onboarding | `founders.onboarding_completed_at` | — |
| Founder Diagnosis | Founder DNA phase, `founders.founder_dna_completed_at` | `FounderDnaNotCompleteError` (service.py:277) |
| Current Problem | `founders.current_problem_completed_at` | `CurrentProblemNotCompleteError` (service.py:279) |
| **Business DNA** | **the `/diagnosis` question loop** (`DiagnosisService` + `QuestionSelectionEngine`) | also requires `founders.stage_id` (service.py:284) |
| Report | reasoning pipeline, fired on session completion | `BackgroundTasks` → `notify_session_completed` (router.py:205) |

`app/api/v1/diagnosis/business_dna.py` is **not** a question phase. It is the
six-pillar / twenty-dimension **scope model** (a transcription of *GoXL Business
DNA — The Decoding Journey*, Parts 2–3) that drives pillar and category
filtering inside the selector. A second, unrelated use of the same name exists:
`founder_reports.business_dna`, a report **section** derived from
business_health (`reasoning/service.py:1072`). Three distinct meanings share one
word; the implementation must not conflate them.

## B. THE 18 TRACES

**1. Where question count is currently limited.**
`DiagnosisService._attach_question` (service.py:1012-1076). It is the single
completion point — "Completion lives here rather than in the engine so that 'no
questions left' has exactly one meaning across every entry point."

**2. Every max-question / question-budget variable.**

| Symbol | Location | Live value |
|---|---|---|
| `MAX_DIAGNOSIS_QUESTIONS` | config.py:287 | 30 (fallback only) |
| `founder_stages.question_budget` | schema.py:137 | per-stage; NULL as shipped |
| `Settings.question_budget(stage_budget)` | config.py:891-926 | the one resolver |
| `MIN_ANSWERS_BEFORE_COMPLETION` | incremental_confidence.py:52 | 8 |
| `CONFIDENCE_MIN_QUESTIONS_FLOOR` | scoring_rules | 12 |
| `MONITOR_MIN_COVERAGE` | scoring_rules | 0.75 |
| `MIN_ANSWERS_PER_PILLAR_SCORE` | config.py:305 | 3 |
| `ADAPTIVE_SHORTLIST_SIZE` | config.py:787 | 5 |

`question_budget()` is deliberately shared by **two** consumers that must never
disagree: the completion ceiling (`_attach_question`) and the coverage
*denominator* inside the confidence score (`confidence.py:494`). Raising or
removing the ceiling without the denominator makes coverage exceed 1.0; the code
clamps (`min(_ONE, …)`), so the failure is silent score saturation, not a crash.

**3–5. The four completion triggers** (service.py:1026-1029, verbatim):
1. `routing_state == generate_report` — confidence ≥ 80
2. `routing_state == monitor` — healthy-founder all-clear
3. budget spent
4. no eligible question left in the bank

(1) and (2) are *successes*, set by the incremental scorer. (3) and (4) are
exhaustion. Only (3) is a "fixed question count" in the brief's sense.

**6. Report trigger.** `router.py:205` schedules
`notify_session_completed(founder_id, session_id, founder_uuid)` as a
`BackgroundTask` **whenever `session.status == COMPLETED`** — regardless of
*why* it completed. The report layer then reads `routing_state` to know whether
the diagnosis was conclusive (`_attach_question` deliberately does *not* stamp
`generate_report` on a budget-exhausted session). Pipeline profiled at 203s.

**7. Is the loop already adaptive?** Yes, more than the brief presumes.
`incremental_confidence.recompute()` runs after **every** answer: diagnosis →
root-cause detection/ranking → confidence → `routing_state`. It deliberately
skips retrieval, recommendations, business health, archetype and report
generation. It uses the **stored** classifier for prior answers, so the
recompute is deterministic and adds **no** LLM call beyond the submit-time
advisor. This directly satisfies the brief's "do not add an LLM call per
stopping decision" — the existing design already meets it.

**8. Is selection already evidence-driven?** Partly.
`_sort_key_for` (engine.py:314-346) already switches behaviour by phase:
- below validate → **GATHER**: `_round_robin_key_for` — pillar round, then
  category round, then `_sort_key`, optionally with a capability tie-break.
- at/above validate → **CONFIRM**: questions whose `root_cause_id` is already
  detected sort first. It *reorders only, never filters*.

**9. `_sort_key`** (engine.py:129): `(category_rank, priority_rank,
difficulty_level, question_id)`. `question_id` decides 98.8% of blocks — the
finding of the prior tiebreak investigation; unchanged here.

**10. Stage partition.** `stage_groups_for` returns **exactly one** group
(`_STAGE_ORDER_TO_GROUP = ((1, STAGE_0), (4, STAGE_0_TO_1), (8,
STAGE_1_TO_10_PLUS))`). A hard partition, and the measured cause of 4 of 8
ground-truth primaries being unaskable. **The brief does not authorise touching
this** (H1 explicitly not being tested), so it stays.

**11. Pillar sufficiency.** `MIN_ANSWERS_PER_PILLAR_SCORE = 3`
(business_health.py:199). Below the floor a pillar reports score `None`, no
band, no red flag, and is excluded from the weighted overall, which renormalises
over what remains. `assessed_question_count` distinguishes never-asked (0) from
below-floor (1–2). **This is the only existing "pillar sufficiency" rule and it
is a reporting gate, not a stopping gate** — nothing currently keeps the loop
running until every in-scope pillar clears 3.

**12. Contradiction handling.** `LLMConsistencyDetector` (consistency.py)
returns a 0..1 signal plus a `contradictions` tuple; it is 20% of the confidence
score and **fails to `available=False`, never to a false 1.0**. So contradictory
evidence *already* moves the score dynamically. What does **not** exist: any
persistence of `contradictions`, and any per-answer revision of a previously
stored `answers.score_label`. The evidence trail the brief requires is not kept.

**13. Evidence trail persistence — GAP.**
`RootCauseEvidence` (reasoning/schemas.py:83) carries per-evidence
`contribution`, dimension and directness, and "the contributions of a
detection's evidence sum to its detection_score". **None of it is persisted.**
`detected_root_causes` stores only the aggregate:
`final_weighted_score, category_risk_score, confirmation_status,
confirmation_multiplier, stage_probability, industry_probability, rank,
is_top_finding`. No `question_id`, no `answer_id`, no per-factor contribution
rows. No `*_evidence` table exists for root causes (only `capability_evidence`,
which is a different subsystem). See **Blocker 1**.

**14. CONFIRMED path.** Still structurally unreachable, unchanged:
`resolve_follow_up` returns `None` (engine.py:902, "inert until scoring
exists"); `answers.triggered_follow_up_id` has no writer; `is_follow_up` is
hardcoded `False` at the sole answer-creation site (service.py:516). Therefore
`confirmation_status` is `unconfirmed` for essentially every candidate, and the
0.25-weight confirmation factor contributes a **constant** 0.25 to every score.

**15. Hidden hard budgets in the API layer.** Two, neither a question count:
`founder_rate_limit(key="diagnosis-answer", limit=20, window_seconds=60)` and
`require_ai_processing_allowed` / `require_diagnosis_consent` (router.py:153).
The rate limit is documented as "the only backstop against a single account
driving unbounded LLM spend here" — the diagnosis path has **no credit or plan
gate at all**. Removing the question ceiling makes that rate limit the *sole*
cost bound. See **Unresolved Decision 3**.

**16. Lifetime allowance.** `_check_diagnosis_allowance` (service.py:202) bounds
*new* diagnoses, never a resume. Not a per-session question bound.

**17. Scoring-configured predicate.** `settings.diagnosis_scoring_configured`
= `ADAPTIVE_QUESTIONS or ANSWER_CLASSIFIER == "llm"` (config.py:889). Shipped
defaults are `ADAPTIVE_QUESTIONS=False`, `ANSWER_CLASSIFIER="stored"` →
**False** → every answer unscored → empty report. `main.py:207` logs this at
boot. Production pairing must remain `ADAPTIVE_QUESTIONS=true` +
`ANSWER_CLASSIFIER=stored` + `ARCHETYPE_LLM=true`.

**18. Determinism.** `select_next_question` is `min(candidates, key=…)` with a
total order; `_rank` sorts with `root_cause_id` as the terminal anchor. Given
identical DB state and detections, output is byte-identical. Both must survive.

## C. SCORE TAXONOMY — required by the brief's "do not confuse score types"

| Score | Where | Range | Semantics |
|---|---|---|---|
| `answers.score` (band) | ScoreLabel | {0,1,2} or `None` | **RISK**, higher is worse. N/A is `None`, never 0. |
| `category_risk_score` | diagnosis engine | [0,1] | founder-facing mean over a category |
| `ranking_category_risk` | detection | [0,1] | smoothed, ranking-facing |
| `detection_score` | root_cause.py | [0,1] | **saturates at 1.0000** for any all-RED cause |
| `detection_confidence` | root_cause.py | [0,1] | `intensity × corroboration`; corroboration = n/(n+1) |
| `evidence_mass` | root_cause.py | unbounded ≥0 | Σ negative band scores |
| `evidence_breadth` | confidence.py | [0,1] | clamped |
| `stage_probability` | confidence.py | [0,1] | normalised `(w−0.5)/1.5` from the stored ordinal |
| `confirmation_multiplier` | scoring_rules | **{0.5, 1.0, 1.5}** | **not** [0,1] |
| **`final_weighted_score`** | confidence.py:332 | **[0.125, 1.125]** | see below |
| `overall_confidence_score` | confidence_score.py | **[0, 100]** | session-level |

### The `final_weighted_score` range is NOT [0,1]

Weights (live): category_risk 0.40, confirmation_status 0.25, stage_probability
0.20, evidence_breadth 0.15, industry_probability 0.00 — sum 1.00
(`WEIGHT_FACTORS_SUM_CHECK`). But the confirmation **factor is a multiplier on
{0.5, 1.0, 1.5}, not a probability on [0,1]**. Therefore:

```
theoretical max = 0.40(1) + 0.25(1.5) + 0.20(1) + 0.15(1) + 0.00 = 1.125
theoretical min = 0.40(0) + 0.25(0.5) + 0.20(0) + 0.15(0) + 0.00 = 0.125
```

Measured on the 272 stored rows in `detected_root_causes`:
**min 0.3167, max 0.8500, mean 0.6197, 21 distinct values.**
Because CONFIRMED is unreachable (trace 14), the confirmation term is a constant
0.25 in practice, making the *achievable* range **[0.25, 1.00]** and the
observed ceiling 0.85.

**`root_causes.confidence_weight`** — Numeric(5,2), [0,1], 20 distinct values
0.58–0.90 — is declared in `schema.py` and read by **no engine**. It is the only
unused ordinal signal in the catalogue. Flagged, not interpreted.

---

# D. BLOCKERS AND UNRESOLVED PRODUCT DECISIONS

Per the brief: "Where the implementation requires an undefined product policy,
STOP and report it." Four items qualify. I have not implemented around any of
them.

### UNRESOLVED PRODUCT DECISION 1 — what is "80–100% root-cause strength"?

**Question.** The brief's report trigger is "root-cause strength 80–100% **plus**
supporting evidence". No score in this system is a root-cause strength on
[0,100] or [0,1].

**Current implementation options.**
- (a) `overall_confidence_score ≥ 80`. This is a **session** confidence over five
  signals (category 30%, coverage 25%, consistency 20%, confirmation 15%,
  separation 10%) — it is *not* a statement about any one root cause. It is what
  `CONFIDENCE_GENERATE_REPORT_MIN = 80` already means, and it is already the
  shipped report trigger.
- (b) `final_weighted_score ≥ 0.80`. Per-cause, but on a **[0.125, 1.125]** scale
  whose observed max is 0.85 and whose mean is 0.62. Only a handful of the 272
  stored detections would ever clear 0.80, and a CONFIRMED cause is arithmetically
  favoured by a fixed +0.125 it can never currently earn.
- (c) `detection_score ≥ 0.80`. Per-cause and on a clean [0,1] — but it
  **saturates at exactly 1.0000 for any cause whose every probe came back RED**,
  including a cause probed exactly once. Using it as the stop trigger would end
  a diagnosis on a single red answer. This is the precise defect E+B was
  authorised to work around, and adopting (c) would re-enter it through the front
  door.
- (d) `detection_confidence ≥ 0.80`. Per-cause, [0,1], and it does **not**
  saturate — but `corroboration = n/(n+1)` caps it at 0.875 for n=7 and 0.889 for
  n=8, so ≥0.80 demands ≥4 probes *all* RED *and* near-maximal intensity. With
  `ROOT_CAUSE_MIN_DETECTION_CONFIDENCE = 0.20` as the live floor, 0.80 is roughly
  the 99th percentile. **80% of root causes in the catalogue have exactly one
  question**, for which `detection_confidence` maxes out at 0.5000 — those causes
  could *never* trigger a report under (d).

**Real-product consequence.** Under (a) nothing changes and the brief's
"evidence-driven, per-root-cause" intent is not delivered. Under (b) or (d) the
1,603 single-question root causes (80% of the catalogue) become structurally
incapable of ever triggering a report, so the diagnosis would run to budget
exhaustion for most founders — the exact failure the budget was introduced to
stop. Under (c) a founder who answers one question RED gets a report.

### UNRESOLVED PRODUCT DECISION 2 — what counts as "supporting evidence validation"?

**Question.** The brief requires the 80% trigger to be gated on evidence
validation, and separately requires "do not stop at the first 80%". Neither the
validation predicate nor the stopping rule after the first 80% is specified.

**Current implementation options.**
- (a) `independent_signal_count ≥ N` — distinct categories. With the single-group
  stage partition and ~1–2 slots per category, N=2 is reachable, N=3 is rare.
- (b) `len(members) ≥ N` probes on the cause, regardless of dimension. Cheap, but
  repetition then counts as corroboration — which `evidence_breadth` was
  explicitly designed *not* to allow ("six answers on one subject score zero
  here").
- (c) `confirmation_status == CONFIRMED`. **Structurally unreachable today**
  (trace 14). Choosing this makes the report trigger unreachable, full stop.
- (d) Pillar-based: every in-scope pillar has ≥ `MIN_ANSWERS_PER_PILLAR_SCORE`
  (3) answers. This is the only sufficiency rule that already exists, but it is a
  *reporting* gate, and at Stage 0 four pillars × 3 = 12 answers, versus
  Stage 1→10+ six × 3 = 18 — so it silently becomes a per-stage minimum.

**Real-product consequence.** Getting this wrong in the permissive direction
produces a confident report off two answers. In the strict direction it makes the
early-stop unreachable and every founder answers to the budget ceiling, which is
today's behaviour with extra machinery. And "do not stop at the first 80%" needs
a concrete continuation rule — *how many* more questions, or *until what*? Without
it, "keep going" has no terminating condition other than the budget the brief
asks to remove.

### UNRESOLVED PRODUCT DECISION 3 — what bounds cost once the fixed count is gone?

**Question.** DECISION 1 removes the fixed question count. `MAX_DIAGNOSIS_QUESTIONS`
is currently the only hard bound on a diagnosis, and every answer costs one LLM
call (the submit-time advisor *is* the classifier under production pairing).

**Current implementation options.**
- (a) Keep `question_budget()` as a **safety ceiling** rather than a target,
  exactly as `MAX_FOUNDER_DNA_QUESTIONS` already is for the Founder DNA phase
  (config.py:310: "Unlike MAX_DIAGNOSIS_QUESTIONS this is not a target to reach").
  This is the one option with precedent in this codebase.
- (b) Remove it entirely. The Stage 0→1 bank holds **569** questions; the
  per-founder rate limit (20/min) then permits ~569 LLM calls per diagnosis
  against no credit or plan gate. The code's own comment: before the cap existed,
  "every session simply ran until abandoned, which is why no diagnosis had ever
  completed."
- (c) A cost budget rather than a count budget. No such meter exists in the
  diagnosis path today.

**Real-product consequence.** Under (b), a single founder can drive unbounded
spend, and the historical failure mode (no diagnosis ever completing) returns.
Under (a) the brief's "no fixed question count" is satisfied in spirit — the
engine stops on evidence, not on a number — while the ceiling remains as a
backstop. **I recommend (a), but it is a product call, not mine.**

There is a second, non-obvious consequence: `question_budget()` is *also* the
**coverage denominator**, 25% of the confidence score (config.py:900-906). If the
ceiling is removed or raised, coverage either can never reach 1.0 or saturates
immediately, and the 80-point report threshold moves underneath the new logic.
Any change to the ceiling must state what the coverage denominator becomes.

### BLOCKER 1 — the required report metadata needs a table that cannot be created

**What the brief requires.** "The report must retain question ID / answer ID /
contribution / pillar / reasoning metadata," and "contradictory evidence must
dynamically update scores **and preserve the evidence trail**."

**What exists.** `RootCauseEvidence` holds per-evidence contribution, dimension
and directness *in memory during a single run* and is then discarded.
`detected_root_causes` persists only the aggregate (trace 13). `answers` holds
`score`/`score_label` but has no link to which root cause an answer supported, or
by how much. `ScoreComponent` contributions are likewise computed and dropped.

**Why this is blocking.** Satisfying the requirement means a new table (e.g.
`detected_root_cause_evidence`: detection_id, question_id, answer_id, pillar_id,
contribution, dimension, directness, superseded_at) plus, for the contradiction
trail, either revision rows on `answers` or an append-only score-revision table.
Both require an **Alembic migration**, and the brief states: *"DO NOT run Alembic
migrations."*

**What I can do without authorisation.** Author the migration file without
applying it, and build the engine-side plumbing behind a flag that no-ops when the
table is absent. That leaves the requirement demonstrably unmet in any live
database until someone runs the migration, so it would be dishonest to report it
as delivered.

**What I need.** Either (i) authorisation to author *and apply* the migration on
the local eval DB only (`ally_e2e`, never production), or (ii) an explicit
instruction to author-but-not-apply and accept the feature as inert, or (iii) a
narrower metadata requirement that fits the existing columns.

---

## E. WHAT I HAVE NOT TOUCHED

No file was modified in this step. The pre-existing uncommitted changes (E+B
ordering in `root_cause.py` / `confidence.py`, stage-prior normalisation, and the
capability-taxonomy work from earlier sessions) are exactly as they were.
No commit, no push, no migration, no production access, no LLM spend.
