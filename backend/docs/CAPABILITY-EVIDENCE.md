# Capability evidence — Step 7B

FOUNDER ANSWER → CAPABILITY EVIDENCE, and nothing past it. This preserves
observable evidence from existing diagnosis answers in a structured, traceable
form. It does not score a capability, does not assess a current state, does
not compute a gap, and does not touch recommendations.

```
Question → Answer → Answer Classification (existing) → Capability Evidence
    Extraction (NEW, additive) → Existing Diagnosis Pipeline continues
```

Migrations `e6b3f92a1c48` (the table) and `d1a4c8e2f907` (a prerequisite bug
fix, see below).

---

## Observation vs. assessment

`capability_evidence` holds **observations**, one row per answer. It never
holds a **current-state assessment** — the conservative "lowest confident
reading" combination of several observations into one current level per
capability is Step 7C, deliberately not built here.

```
Q1 → FND-DELEG → Level 1
Q2 → FND-DELEG → Level 2       three rows, stored independently,
Q3 → FND-DELEG → Level 1       never averaged, never reduced to one
```

The table is designed so Step 7C can read these rows unmodified. Nothing in
Step 7B aggregates, ranks, or picks a "final" level.

---

## UNASSESSED vs. Level 0

The distinction is structural, not a value:

| State | Meaning | Representation |
|---|---|---|
| **UNASSESSED** | no sufficient evidence exists | **no row** in `capability_evidence` |
| **Level 0** | evidence explicitly says the capability is absent | a stored row with `observed_level = 0` |
| Level 1 | founder-dependent / personal | a stored row |
| Level 2 | documented | a stored row |
| Level 3 | owned / organizational | a stored row |

`observed_level` is `NOT NULL` — every row that exists **is** evidence. There
is no hedge value, no "level unknown" row, no sentinel. `CapabilityLevel` (the
same 0–3 enum from Step 5/6) is reused; nothing new was invented.

Level 0 is never inferred from: an unanswered question, an unmapped question,
a failed extraction, low confidence, or a founder simply not mentioning the
capability. All of those produce **no row**, which is the correct, silent,
designed outcome — pinned by tests, not left to convention.

---

## N/A behaviour

`ScoreLabel.NOT_APPLICABLE` is excluded **before** the extractor is ever
invoked — `_extract_capability_evidence` checks `answer.score_label` and
returns immediately, so an N/A answer never reaches the LLM, never produces a
row, and cannot affect capability coverage or confidence. This mirrors Step
4's `_learn_session_facts`, which applies the identical gate for session
context facts.

---

## Only mapped questions

Extraction runs only when `question_capabilities` (Step 7A) has a row for the
question. 1,874 of 3,340 questions are unmapped by design and remain outside
capability evidence entirely — this step does not attempt to map them.

---

## Evidence criteria

The extractor is shown **only** the criteria of the **one** capability the
question maps to (Step 7A's own invariant: a question maps to at most one
capability). It may cite one existing `criterion_id`, or none — never a
criterion it invents. A returned `criterion_id` is checked against the
criteria actually **offered** for that call; anything else is dropped, not
trusted. At the database, a composite foreign key
`(capability_id, criterion_id)` enforces the same rule independently of the
application code, using a new `UNIQUE (capability_id, criterion_id)` on
`capability_evidence_criteria` (harmless — that pair was already unique via
`criterion_id`'s own primary key; this only makes the pair referenceable).

---

## Extraction architecture

`CapabilityEvidenceExtractor` (abstract) / `LLMCapabilityEvidenceExtractor`
(concrete), in `app/api/v1/diagnosis/capability_evidence.py` — the same shape
as `advisor.py`'s `NextQuestionAdvisor` / `LLMNextQuestionAdvisor`. The LLM's
contract is exactly the four fields the step brief specifies:

```json
{"evidence_present": true|false, "criterion_id": <id>|null,
 "observed_level": 0|1|2|3|null, "evidence_text": "...", "confidence": 0.0-1.0}
```

It is never told about other capabilities, never asked to invent a criterion,
never asked to combine multiple answers, and never asked about a target, a
gap, or a recommendation. **A confidence below 0.6 stores nothing** — a hedge
is not evidence, even when it names a plausible level.

Fail-open at two layers, matching `advisor.py` / `submit_answer`'s existing
shape: `LLMCapabilityEvidenceExtractor.extract` itself catches
`LLMProviderError` / timeout and returns `None`; a second, outer
`except Exception` in `DiagnosisService._extract_capability_evidence` catches
anything else, so a genuinely broken extractor can never put a founder's
answer at risk.

**Off by default.** `CAPABILITY_EVIDENCE_EXTRACTION: bool = False`. Every
existing caller of `DiagnosisService` passes no
`capability_evidence_extractor`, so its default of `None` makes this step's
code path a pure no-op unless explicitly enabled — verified by
`test_no_extractor_wired_is_a_pure_no_op`. When enabled, it is wired through
`get_capability_evidence_extractor` (`deps.py`) using
`get_provider(settings.LLM_PROVIDER)` directly — **not**
`provider_for_task` / `model_task_routing` — because this is a new, separate
concern from next-question selection or answer classification, and
`test_llm_routing.py::test_every_task_is_registered_in_the_enum` is already a
known pre-existing failure; adding a task there was avoidable and was
avoided.

---

## Traceability

Every row carries `capability_id`, `question_id`, `answer_id` and
`criterion_id` (nullable) directly — not a join chain. `question_id` is
technically derivable from `answer_id → answers.question_id`, but the step
brief asks for the full chain on the row itself, so "why did Ally think this
capability was Level X" is one `SELECT`, not several joins through tables that
could themselves change later.

---

## Idempotency

`UNIQUE (answer_id)` at the database. Reprocessing the same answer is a
`ON CONFLICT (answer_id) DO NOTHING` — silently skipped, not an error, and the
**first** write wins. This is also the direct expression of Step 7A's own
invariant that a question maps to at most one capability: one answer, at most
one observation.

---

## Pipeline placement

Inside `DiagnosisService.submit_answer`, immediately after `_apply_insight`
and `_learn_session_facts`, in the branch where the advisor produced a real
(non-fallback) score. Nothing about root-cause detection, diagnosis scoring,
stage detection, the question budget, or industry eligibility was reordered
or touched — each has its own regression test in
`test_capability_evidence_pipeline.py` asserting the relevant source file has
no dependency on `capability_evidence` or `question_capabilities` at all.

---

## A bug this step found and fixed

Migration `c7d18a3f420b` (a previous step) widened
`answers_score_label_check` to allow `'not_applicable'` but never widened the
**column**, which was `varchar(10)`. `'not_applicable'` is 14 characters.
Reproduced directly against the database before writing any Step 7B code:

```
INSERT INTO answers (...) VALUES (..., 'not_applicable')
ERROR:  value too long for type character varying(10)
```

This meant Step 4's entire purpose — persisting a NOT_APPLICABLE answer via
the advisor's read — silently failed at the database layer, and Step 7B's own
N/A test fixtures could not be constructed without it. Fixed by
`d1a4c8e2f907` (widens the column to `varchar(20)`, matching the
`confirmation_status`-at-`varchar(15)` convention for headroom). This is a
capacity fix, not a semantic change: the values `green` / `amber` / `red` /
`not_applicable` mean exactly what they meant before.

---

## Intentionally not implemented yet

- Aggregating multiple observations into one current-state level (Step 7C)
- Comparing current state against `capability_requirements` (the Gap Engine, Step 8)
- Any `MISSING` / gap / severity state
- Recommendations or roadmap conditioned on evidence
- Curating the 1,874 unmapped questions
- Routing the extractor through `provider_for_task` / cost telemetry (a later,
  separate decision once usage volume justifies it)
