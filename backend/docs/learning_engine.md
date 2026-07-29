# Learning Engine — continuous improvement loop

The loop that turns real usage into a better engine over time. It **proposes**
calibrations from evidence; **humans approve**; only then does configuration
(`scoring_rules` / prompts) change. Nothing in this module mutates config — weight
changes are sign-off-gated (Viraj owns confidence-weight sign-off).

Code: `app/learning/` (`engine.py`, `feedback.py`, `schemas.py`),
`scripts/run_learning.py`. Consumes the [Evaluation Framework](evaluation_framework.md).

---

## The loop

```
   ┌──────────────┐   diagnosis sessions, reports,
   │  1. CAPTURE  │   detected_root_causes, founder_feedback
   └──────┬───────┘   (+ data_quality_status / reviewed_by / training_notes)
          │
   ┌──────▼───────┐   app/eval  → quality metrics
   │ 2. EVALUATE  │   app/learning/feedback → feedback summary
   └──────┬───────┘
          │
   ┌──────▼───────┐   LearningEngine.analyze() → ImprovementSignals
   │ 3. ANALYSE / │   each: observation + proposed_action + target + evidence
   │    PROPOSE   │   (deterministic, testable — this module)
   └──────┬───────┘
          │
   ┌──────▼───────┐   *** HUMAN GATE ***  a reviewer (product/Viraj) accepts or
   │ 4. REVIEW +  │   rejects each ACTION proposal. SAFETY signals go to review,
   │   SIGN-OFF   │   never auto-tuned.
   └──────┬───────┘
          │
   ┌──────▼───────┐   approved weight/threshold changes are written to scoring_rules
   │  5. APPLY    │   (rows, not code); prompt changes to prompt_library.
   └──────┬───────┘
          │
   ┌──────▼───────┐   re-run app/eval on the next cohort; did the metric move the
   │ 6. RE-MEASURE│   right way? keep or revert. Loop.
   └──────────────┘
```

Stages 1–3 are built here (deterministic). Stages 4–6 are **deliberately
out-of-band**: applying calibration is a governed change, so the engine stops at
"here is the evidence and the proposal."

## Signals it produces

`LearningEngine.analyze(eval_report, feedback_summary) -> LearningReport`. Each
`ImprovementSignal` has a severity and a concrete target:

| code | severity | trigger | proposes |
|---|---|---|---|
| `confidence_miscalibrated` | ACTION | confidence doesn't track founder ratings (low Pearson, or high-conf rated ≤ low-conf) | recalibrate `CONFIDENCE_WEIGHT_*` / routing thresholds |
| `recommendations_unhelpful` | ACTION | founders mark < 50% of recommendations helpful | review ranking `WEIGHT_*` + intervention mapping |
| `low_report_coverage` | WATCH | completed sessions not producing reports | fix silent pipeline failures (ops, not a rule) |
| `routing_skew` | WATCH | >90% of sessions in one routing state | review routing thresholds / min-question floor |
| `distress_review` | SAFETY | any distress-mode sessions | **human review** — never tune thresholds to reduce the rate |

Severities: `INFO` < `WATCH` < `ACTION` < `SAFETY`. `report.has_actions` gates
whether a review cycle is warranted.

## Design principles

- **Propose, don't apply.** Config changes are governed; the loop produces evidence
  + a proposal, not a mutation.
- **Safety is never optimised away.** A high distress rate is a review signal, not a
  threshold to lower. Wellbeing overrides diagnostic metrics.
- **Traceable.** Every proposal carries its `evidence` (the metrics/feedback it came
  from) so a reviewer can check it.
- **Deterministic + tunable.** Thresholds are constructor args (`min_pearson`,
  `min_coverage`, …); tests pin the behaviour.

## Run it

```bash
python scripts/run_learning.py     # prints signals; empty until data + feedback exist
```

## What's next (when data + LLM usage accrue)

- Wire `founder_feedback` capture into the product (report_rating,
  recommendation_helpful, outcome_30/60/90day) so the loop has signal.
- Add prompt/LLM signals once the golden-set eval (see evaluation_framework.md) is
  in place — e.g. classifier-accuracy drift after a prompt change.
- A lightweight review UI/record for stage 4 (accept/reject with the evidence
  attached) — could reuse `sessions.reviewed_by` / a small proposals table.
