# Option E — Coverage-Relative RCCS: Implementation Report

Zero LLM (`llm_call_log` = 0 for the window). No production, no AWS, no commit,
no push. `ground_truth.json` MD5 `7fd06caed78e46bd585ac6e01b1d07f0` — unchanged.
Catalogue unmodified. Local eval DB only.

## 1. FILES CHANGED

| file | change |
|---|---|
| `app/api/v1/diagnosis/rccs.py` | coverage-relative primary signal; `askable` plumbing; coverage metadata on the score; docstring rewritten |
| `app/api/v1/diagnosis/rccs_store.py` | `askable_question_counts()`; `load_state` uses it |
| `app/api/v1/diagnosis/adaptive_loop.py` | gathers askable counts for every touched cause before scoring |
| `tests/test_rccs.py` | two semantics tests rewritten (see §4) |
| `tests/test_rccs_option_e.py` | **new** — validations A–M, plus the E1 regression |
| `docs/phase5/OPTION_E_IMPLEMENTATION.md` | this report |

Untouched: `completion.py`, `incremental_confidence.py`, `engine.py`,
`service.py`, `config.py`, the migration, E+B ordering, stage priors, question
selection, root-cause detection, the catalogue, ground truth.

## 2. THE FORMULA CHANGE

**Before** — absolute mass, saturating per pillar:
```
depth_p = mass_p / (mass_p + 1)          per (source, pillar) bucket
signal  = 1 - Π(1 - depth_p)             noisy-OR across pillars
```

**After** — primary evidence is relative to what was askable:
```
reach   = primary_mass / (askable_questions + 0.25)      clamped to 1
sibling = min(Σ-saturated sibling mass, 0.25)            unchanged
signal  = 1 - (1 - reach) * (1 - sibling)
RCCS    = support_signal * (1 - 0.2 * contra_signal)     unchanged
```

`_COVERAGE_PRIOR = 0.25` is the only new constant, and it is not arbitrary: it is
the value at which a cause whose **only** question comes back Red reaches
`1 / 1.25 = 0.8000` — exactly the threshold and not a hair more. Without a prior
that case would score 1.0000 (certainty from one sentence) and would be
indistinguishable from a cause probed five times and Red every time (0.9524).

The per-pillar noisy-OR no longer applies to primary evidence. That is a no-op in
production: all 1,997 catalogue causes have every question in one pillar.

`askable` comes from the live catalogue (`askable_question_counts`). When it is
unavailable the state falls back to the distinct questions actually answered —
"everything we knew to ask" — which degrades the score rather than breaking it.

## 3. WHY THIS SATISFIES OPTION E

| required property | how |
|---|---|
| supporting evidence increases RCCS | reach rises with primary mass |
| contradictory evidence decreases RCCS | attenuation, with sibling contradiction uncapped (§8) |
| direct > sibling | reach is uncapped to 1.0; sibling capped at 0.25 |
| sibling alone cannot create strength | hard cap 0.25, measured at exactly 0.2500 |
| evidence availability matters | it *is* the denominator |
| one-question cause not structurally capped | reaches 0.8000 on one Red |
| normalized [0,1] | reach clamped; attenuation multiplicative |
| deterministic | pure arithmetic, 3 identical runs |
| incremental per answer | unchanged `apply` |
| events inspectable | unchanged, plus `askable_questions` / `answered_questions` / `coverage` |

RCCS ≥ 0.80 means **evidence strength**, never diagnosis complete. The final
quality gate still owns sufficiency and is unchanged.

## 4. TESTS CHANGED — both deliberate semantic reversals

- `test_9_corroboration_across_pillars_beats_depth_in_one` →
  `test_9_corroboration_is_coverage_not_pillar_spread`. It asserted that a second
  *pillar* outscored more evidence in the first. Measured unreachable: no cause
  spans pillars. Corroboration now means coverage.
- `test_11_..._trajectory_is_pinned`. The old frozen trajectory
  (0.5000/0.6667/0.8333/0.7500/0.8000) came from the absolute model and a worked
  example assuming cross-pillar corroboration the catalogue cannot supply. Now
  pins a three-question cause: **0.3077 → 0.6154 → 0.9231**, then contradicted.

## 5. TEST RESULTS

| suite | result |
|---|---|
| `test_rccs.py` | **40 passed** |
| `test_rccs_option_e.py` (new, A–M) | **23 passed** |
| `test_adaptive_diagnosis_integration.py` | 13 passed |
| E+B ordering / focus | 19 + 4 passed |
| stage-prior | 28 passed |
| D1/D2 harness | 16 passed |
| question budget | 17 passed |
| **full deterministic suite** | **4,208 passed, 9 failed, 5 skipped, 2 xfailed** |

Passing count rose 4,185 → 4,208 (+23 new). The 9 failures are the **identical
known baseline** — credit settlement (3), email (1), industry mapping (2), llm
routing (1), migration graph (2). None new, none touching changed code.

Adversarial battery: **11 of 11 break-attempts held.**

## 6. CATALOGUE MEASUREMENTS

| | |
|---|---|
| root causes total / with questions | 2,009 / 1,997 |
| exactly one question | 1,603 (80.3%) |
| exactly two | 151 (7.6%) |
| three or more | 243 (12.2%) |
| max questions per cause | 25 |

One-question causes: RED **0.8000** (strong) · AMBER **0.4000** ·
RED + 3 siblings **0.8500** · sibling-only **0.2500**.

Catalogue reaching ≥0.80: **100%** at full coverage all-RED · **80.3%** on a
single RED answer · **0.0%** on AMBER-only, at any coverage.

## 7. GROUND-TRUTH STRUCTURAL CHECK

All 12 frozen primaries, one RED on their single question:

| persona | primaries | rc_id / q_id | #q | RCCS | sup | con | gate |
|---|---|---|---|---|---|---|---|
| desi_bar | RC-1023 / RC-1000 / RC-155 | 1023·347, 1000·332, 155·68 | 1 | 0.8000 | 1 | 0 | PASS |
| siddharth_saas | RC-132 / RC-482 / RC-447 | 132·66, 482·1702, 447·1675 | 1 | 0.8000 | 1 | 0 | PASS |
| vikram_logistics | RC-493 / RC-445 / RC-1036 | 493·1683, 445·1674, 1036·364 | 1 | 0.8000 | 1 | 0 | PASS |
| arya_parlour | RC-1316 / RC-1836 / RC-450 | 1316·536, 1836·832, 450·1677 | 1 | 0.8000 | 1 | 0 | PASS |

**12/12 reach ≥0.80** (was 0/12 under every A/B/C/D parameterisation).
This is a **structural/semantic** validation, not an accuracy evaluation — it
shows the causes are now *reachable*, not that the engine would *find* them.

## 8. DEFECT E1 — FOUND AND FIXED

**Sibling contradiction was subject to the sibling SUPPORT cap.**

`_SIBLING_SUPPORT_CAP` (0.25) was being applied to the contradiction signal as
well. The two ceilings serve opposite purposes: the support cap stops indirect
evidence **manufacturing** a strong cause; applying it to contradiction stopped
indirect evidence **challenging** one, and a diagnosis has to stay reversible.

Fixed by making the ceiling direction-dependent — support capped at 0.25,
contradiction bounded only by the saturation itself (approaches 1.0, never
reaches it; `_CONTRA_WEIGHT` still bounds the total effect at a ×0.80
attenuation, so contradiction can never zero a cause).

| askable | fully probed | before fix | after fix |
|---|---|---|---|
| 1 | 0.8000 | 0.7600 | 0.6462 |
| 2 | 0.8889 | 0.8445 (stuck) | **0.7180** |
| 3 | 0.9231 | 0.8769 (stuck) | **0.7456** |
| 5 | 0.9524 | 0.9048 (stuck) | **0.7693** |

The gradient is gradual, not a cliff — one sibling contradiction costs a
fully-probed two-question cause 0.036, and it takes five to demote it:

```
0 -> 0.8889   1 -> 0.8533   2 -> 0.8296   3 -> 0.8127
4 -> 0.8000 (exactly on the bar, still qualifies)   5 -> 0.7901
```

That boundary is now pinned explicitly in `test_J`: four contradictions land on
0.8000 and `>= 0.80` still qualifies; the fifth demotes. Both sides are asserted,
because an off-by-one there silently changes when a diagnosis may conclude.

The two tests that were `xfail(strict=True)` while the defect stood now assert
the fixed behaviour directly.

## 9. PRE-EXISTING FAILURES (not fixed, not mine)

Credit settlement (3), email (1), industry mapping (2), llm routing (1),
migration graph (2). The migration graph has been at 2 heads since before this
work; my revision chains onto one pre-existing head and adds none.

## 10. CONFIRMATION

0 LLM calls · 0 production writes · 0 AWS changes · `ground_truth.json` unchanged
(MD5 verified before and after) · catalogue unchanged · no commit · no push ·
no branch switch · nothing stashed, reset or cleaned.
