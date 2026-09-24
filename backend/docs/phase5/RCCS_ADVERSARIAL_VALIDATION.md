# Phase 5 — RCCS Adversarial Validation

Zero LLM (confirmed: 0 rows in `llm_call_log` for the window). Read-only against
the implementation; no production, AWS, ground truth, catalogue, commit, push,
branch switch, reset, stash or clean. Local eval DB `ally_e2e` only.

## OVERALL RESULT: **FAIL** — one blocker

51 of 51 scripted assertions passed. The blocker was found by probing *beyond*
the scripted assertions, which is what Test 7 asked for.

---

## F1 — BLOCKER: 80.3% of root causes can never reach 0.80

**Observed.** A root cause with exactly one question has a hard maximum RCCS of
**0.6250** and can never be strong, at any evidence strength, ever.

```
one RED on its only question           -> 0.5000
+ 198 saturated sibling events         -> 0.6250   (the ceiling)
theoretical max = 1-(1-0.5)(1-0.25)    =  0.625
reaches 0.80?                             False
```

Because a cause has exactly one primary edge per question, one question means at
most **one** primary event, and one event in one pillar gives `1/(1+1) = 0.5000`.
The sibling channel is capped at `SIBLING_WEIGHT` (0.25) — the cap added to fix
the earlier 0.9375 defect — so noisy-OR tops out at 0.625.

**Expected.** Brief §10 / Test 7: *"The new RCCS must not make one-question root
causes structurally incapable of becoming strong."*

**Catalogue impact** (`ally_e2e`, 1,997 causes with questions):

| questions per cause | causes | share | max RCCS | can be strong? |
|---|---|---|---|---|
| 1 | **1,603** | **80.3%** | 0.6250 | **never** |
| 2 | 151 | 7.6% | 0.8125 | only with sibling help |
| 3+ | 243 | 12.2% | 0.8750+ | yes |

**Consequence.** For four founders in five, the diagnosis can never reach
`problem_explained`. Every such session falls through to `bank_exhausted` or
`safety_ceiling` — neither of which is a diagnostic success — so the report layer
correctly refuses to call it conclusive. This is precisely the failure mode the
audit warned about for options (b) and (d) of UPD-1, now reproduced in the
shipped model.

**File/function.** `rccs.py` — `_K_WITHIN` (=1) with `_signal`/`_noisy_or`, and
`_SIBLING_SIGNAL_CAP`.

**Likely cause.** `_K_WITHIN = 1` was chosen to reproduce the frozen worked
example's trajectory (0.50 / 0.67 / 0.83 …). That example implicitly assumes a
cause with several questions. No constraint tied the constant to the catalogue's
actual question-per-cause distribution.

**Severity: BLOCKER.** Not patched — §24 forbids changing the implementation to
make a test pass, and the fix is a product-shaped choice (lower `_K_WITHIN`,
raise the sibling cap, or make the threshold question-count-aware), not a typo.

---

## F2 — MEDIUM: the module's documented rationale is false

`rccs.py` states, twice, that reaching 0.80 requires corroboration from a second
pillar:

> "a pillar alone cannot carry a cause to the threshold — reaching 0.80 needs a
> second pillar. That is the intended shape, not a tuning artefact."

**It does not.** Four RED answers in a *single* pillar reach exactly 0.8000:

```
1 RED, one pillar -> 0.5000    3 RED -> 0.7500
2 RED             -> 0.6667    4 RED -> 0.8000   strong
```

The prose is wrong, and the test `test_11_...` that "pins" the property only
exercises a sequence that happens to switch pillars. **Severity: MEDIUM** — no
wrong number is produced, but the stated invariant is load-bearing in review and
is not true. I wrote this comment; it is my error, not a pre-existing one.

---

## F3 — MEDIUM: eight AMBERs in one pillar produce a strong cause

```
7 AMBER, one pillar -> 0.7778    8 AMBER -> 0.8000  strong
```

AMBER is *partial* support. Eight partial signals about one subject, with no
corroboration from any other pillar and not one RED, yields a strong root cause.
Direct consequence of F2. **Severity: MEDIUM** — it weakens "repeated identical
evidence must not artificially inflate the score", though the within-pillar
saturation does slow it.

---

## PASSING VALIDATIONS

| # | Test | Result |
|---|---|---|
| 1 | Normal support — monotone, bounded, applied once, deterministic | PASS |
| 2 | Corroboration (0.8750 across 3 pillars vs 0.7500 in 1); 200 answers → 0.9950, never >1 | PASS |
| 3 | Contradiction trajectory 0.8333 → 0.7500 → 0.8000; not locked | PASS |
| 4 | Boundary: 0.7999 not strong, 0.8000 strong, 0.8001 strong; ≥0.80 with no evidence rejected | PASS |
| 5 | One answer → RC-A +1.0 primary, RC-B +0.25 sibling, RC-C −1.0; independent, traceable | PASS |
| 6 | **Sibling ceiling regression**: 24 sibling events → 0.2500 (was 0.9375) | PASS |
| 7 | Single-question cause scores 0.5000 (meaningful, non-zero) | see **F1** |
| 8 | Duplicate replay: 2 applied then 0; score unchanged | PASS |
| 9 | Strong-but-unrelated cause (0.8333, wrong problem) does **not** complete | PASS |
| 10 | RC-A 0.8333 + RC-B 0.5000, two anchors → continues; both strong → completes | PASS |
| 11 | 0.8333 → contradiction → 0.7083; completion flips True → False | PASS |
| 12 | High-value unanswered question blocks; `failed_checks() == ('no_high_value_question',)` | PASS |
| 13 | No strong cause → no report, bounded, no invented confidence | PASS |
| 14 | Exhaustion → `bank_exhausted`, `is_diagnostic_success` False — **defined, not a gap** | PASS |
| 15 | Ceiling 120 vs denominator 30; ≥ denominator at every stage budget; success never mislabelled | PASS |
| 16 | Post-report: `_assert_active` raises; selector yields no contenders in `generate_report` | PASS |
| 17 | Stage scope differs: order 1 → pillars [1,2,4,6] (9 dims); orders 4/8 → all six (18/20 dims) | PASS |
| 18 | 200/200 edges resolve to real `questions` rows; 3 stage groups; no synthetic `question_text` writer | PASS |
| 19 | Determinism — scores, events, ordering and decision identical across 3 runs | PASS |

Evidence persistence: table carries answer_id / question_id / root_cause_id /
direction / magnitude / pillar_id / source / sequence; `uq_rc_evidence_answer_rootcause`
enforces dedupe at the database; trail replay reproduces scores exactly.

## FROZEN DECISION MATRIX

| Frozen Decision | Implemented? | Test | Result |
|---|---|---|---|
| No fixed question count | Yes | 15, unit `test_1` | PASS |
| Evidence-driven investigation | Yes | 1, 9 | PASS |
| Hybrid Business DNA | Yes | 17 | PASS |
| Stage-dependent pillars | Yes | 17 | PASS |
| Database-grounded questions | Yes | 18 | PASS |
| Adaptive pillar questioning | Yes | selector ext. | PASS |
| Scoring-based sufficiency | Yes | 9, 13 | **PASS, undermined by F1** |
| Hybrid pillar handling | Yes | gate check 5 | PASS |
| Hybrid pillar prioritization | Yes | selector ext. | PASS |
| New normalized RCCS | Yes | 1, 4 | PASS |
| Evidence + corroboration + contradiction | Yes | 1, 2, 3 | PASS |
| Existing valid metadata respected | Yes | ScoreLabel only; `confidence_weight` untouched | PASS |
| Incremental RCCS | Yes | 1, 8 | PASS |
| Directional multi-RC effects | Yes | 5, 6 | PASS |
| Problem-driven completion | Yes | 9, 10 | **PASS, unreachable for 80% of causes (F1)** |
| 80% + supporting evidence | Yes | 4 | PASS |
| Contradiction re-evaluation | Yes | 3, 11 | PASS |
| Evidence retained | Yes | persistence | PASS (migration pending) |
| Final hybrid quality gate | Yes | 12, 13 | PASS |
| No post-report diagnosis | Yes | 16 | PASS |

## TEST TOTALS

- Adversarial harness: **51/51** assertions passed (42 + 9)
- RCCS + adaptive integration: **53 passed**
- E+B / stage-prior / focus / D1-D2 / budget / coverage: **111 passed**
- Full deterministic suite: **4,185 passed, 9 failed, 5 skipped, 2 xfailed**

The 9 failures match the known baseline exactly: `test_credit_settlement` (1),
`test_credit_settlement_pg` (2), `test_email` (1), `test_industry_mapping` (2),
`test_llm_routing` (1), `test_migration_graph` (2). None references changed code.

**Migration graph:** still **2 heads**, as before this work. Removing my file and
re-running gave heads `['f7b2c48d9e31','a3f7d92c1e58']`; with it, `['a3f7d92c1e58',
'c3f8a91d4e72']`. My revision chains onto one pre-existing head and adds none.
Pre-existing, out of scope.

## ANOTHER IMPLEMENTATION PASS REQUIRED: **YES**

F1 alone. F2 and F3 are corrections to the same constant's rationale and
behaviour, so all three are one decision about `_K_WITHIN` and the sibling cap —
a decision with product consequences, which is why I have not made it.
