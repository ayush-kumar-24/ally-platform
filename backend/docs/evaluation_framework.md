# Evaluation Framework — AI output quality

Metrics + tooling to measure the quality of the diagnosis engine's output. Two
layers:

1. **Deterministic metrics** (built) — computed from the engine's *persisted*
   outputs (`sessions`, `detected_root_causes`, `founder_reports`,
   `founder_feedback`). No LLM, no API key. This is what ships now.
2. **LLM-judged / golden-set metrics** (extension) — for the generative layer
   (answer classification, chat, grounded prompts). Needs a labelled golden set +
   a provider key. Design below; not built yet.

Run it:

```bash
python scripts/run_evaluation.py     # prints a JSON quality snapshot
```

Code: `app/eval/metrics.py` (pure functions), `app/eval/harness.py` (pulls data +
assembles the report), `tests/test_eval_metrics.py`.

---

## 1. Metrics (deterministic)

| Metric | What it answers | Read from | Healthy signal |
|---|---|---|---|
| `routing_distribution` | Are sessions spread across continue/validate/generate_report/distress_support, or piled in one bucket? | `sessions.routing_state` | a spread, not 100% in one state |
| `confidence` | Distribution of `overall_confidence_score` (mean/median/min/max, %<60) | `sessions` | not saturated at 0 or 100 |
| `distress` | How often distress mode / high-distress fired (a **safety** signal, not a KPI) | `sessions` | no *missed* distress (cross-check with review) |
| `root_causes` | Detections per session + top-finding focus | `detected_root_causes` | avg detections bounded (focusing rule; ≤ ~8) |
| `business_health` | Overall-score distribution + red-flag frequency by pillar | `founder_reports.business_dna` | plausible spread; red-flags fire |
| `report_coverage` | Of completed sessions, how many produced a report | `sessions` + `founder_reports` | ~1.0 — a low ratio = **silent pipeline failures** |
| `confidence_calibration` | Does higher engine confidence track higher founder satisfaction? | `founder_feedback.rating` (report_rating) vs session confidence | positive gap (high-conf rated higher) + positive Pearson |

`confidence_calibration` is the key **learning signal**: if confidence doesn't
predict founder satisfaction, the confidence weights are miscalibrated → feeds the
[Learning Engine](learning_engine.md).

### Suggested targets (calibrate post-launch)

These are starting lines, not hard gates — tune against real data:

- `report_coverage.coverage` ≥ 0.98 (below → investigate pipeline failures).
- `root_causes.max_detections` ≤ 8 (the focusing cap).
- `confidence_calibration.pearson` ≥ 0.3 (weak-but-real positive).
- No completed session with a State-D distress signal routed to `continue`
  (safety — verify via review, not just this aggregate).

---

## 2. LLM-judged / golden-set layer (extension — not built)

For the generative components now present (`app/integrations/llm`,
`app/api/v1/ally/orchestrator`, grounded prompts):

- **Golden set:** a fixed set of founder answers with expert Green/Amber/Red labels
  → measure answer-classifier accuracy / agreement (κ) against it.
- **Grounding / faithfulness:** check chat/report claims are supported by the
  retrieved evidence (no hallucinated root causes/interventions) — an LLM-judge or
  rule-based citation check over `rag_retrieval_log`.
- **Regression:** re-run the golden set on every prompt/model change; alert on drops.
- **Cost/latency:** per-call token + latency from the provider layer.

These need a labelled dataset + a provider key, so they're scoped as the next
increment; the deterministic layer above runs today with neither.

---

## Notes

- Every metric function is **pure** (records in → JSON out) and unit-tested, so the
  definitions are auditable and the harness is thin.
- With no diagnosis data yet, the harness prints the **empty/zero baseline** — that
  is the current expected output; the numbers populate as sessions accrue.
