# RCCS Semantics — Candidate Modelling Against the Real Catalogue

Zero LLM. Read-only: no implementation change, no production, no catalogue or
ground-truth edit (`ground_truth.json` MD5 `7fd06caed78e46bd585ac6e01b1d07f0`,
unmodified). Local eval DB `ally_e2e` only.

---

## TWO STRUCTURAL FACTS THAT DECIDE THIS

Both measured, not assumed. Together they mean the choice is **not** a constant.

**S1 — every root cause's questions sit in exactly ONE pillar.**

| distinct pillars per cause | causes | share |
|---|---|---|
| 1 | **1,997** | **100.0%** |

Max pillars for any cause, at any question count up to 25: **1**. So the
cross-pillar noisy-OR — the mechanism the whole model is built around, and the
only way RCCS rewards corroboration — **can never fire for primary evidence**.
Sibling evidence does not rescue it either: siblings share `problem_id`, and
`problem → pillar` is 1:1, so sibling evidence is in the same pillar too.

**S2 — a real session collects about one answer per cause.**

| answers on one cause, per session | occurrences | share |
|---|---|---|
| 1 | 703 | **88.0%** |
| 2 | 95 | 11.9% |
| 3 | 1 | 0.1% |

Sibling evidence available: mean **0.88** events, max **4**, and **54.3%** of
causes get **zero**. Every observed session: 30 answers across 26 causes.

**Consequence.** The evidence a founder actually produces for one cause is
1 answer, sometimes 2, with 0–1 sibling answers. No accumulation model can call
that "strong" on absolute mass, because there is no more mass to accumulate.

---

## THE CANDIDATES

| | within-pillar K | sibling cap | idea |
|---|---|---|---|
| **A** | 1.00 | 0.25 | current implementation |
| **B** | 0.45 | 0.25 | lower the saturation constant |
| **C** | 1.00 | 0.60 | let problem-level evidence carry more |
| **D** | 1.00 | 0.70 / 0.50 / 0.25 by question count | scarcity-aware: fewer questions ⇒ siblings count more |
| **E** | — | — | **different family**: strength relative to what was *askable*, not absolute mass |

### Catalogue reach (% of 1,997 causes that can hit 0.80)

| scenario | A | B | C | D |
|---|---|---|---|---|
| **measured typical** (1 RED, 0 siblings — 54% of cases) | 0.0% | 0.0% | 0.0% | 0.0% |
| **measured typical** (1 RED, 1 sibling — the mean) | 0.0% | 0.0% | 0.0% | 0.0% |
| **measured ceiling** (2 RED, 4 siblings — best ever seen) | 0.0% | 19.7% | 19.7% | 7.6% |
| hypothetical (3 RED, 3 siblings) | 12.2% | 19.7% | 19.7% | 19.7% |
| theoretical best (all questions RED, saturated siblings) | 12.2% | 19.7% | 100.0% | 100.0% |

C and D reach 100% only in a scenario requiring ~40 sibling answers. The observed
maximum is 4.

### The four Set A2 personas — all 12 primaries

Every one of the 12 frozen primaries is a **one-question** root cause.

| persona | primaries | questions each | A | B | C | D |
|---|---|---|---|---|---|---|
| desi_bar | RC-1023, RC-1000, RC-155 | 1 | 0.60 | 0.77 | 0.60 | 0.60 |
| siddharth_saas | RC-132, RC-482, RC-447 | 1 | 0.60 | 0.77 | 0.60 | 0.60 |
| vikram_logistics | RC-493, RC-445, RC-1036 | 1 | 0.60 | 0.77 | 0.60 | 0.60 |
| arya_parlour | RC-1316, RC-1836, RC-450 | 1 | 0.60 | 0.77 | 0.60 | 0.60 |
| **reaching 0.80 (typical)** | | | **0/12** | **0/12** | **0/12** | **0/12** |
| **reaching 0.80 (observed ceiling)** | | | **0/12** | **0/12** | **0/12** | **0/12** |

**No variation of A/B/C/D makes a single ground-truth primary reachable.**

---

## OPTION E — coverage-relative strength

`RCCS = severity × reach`, where reach is `answered / (askable + 0.25)` combined
with the sibling signal. "Strong" means *we collected the evidence that exists,
and it was bad* — rather than *we collected a lot of evidence*.

| situation | E |
|---|---|
| 1-question cause, 1 RED, 0 siblings | **0.8000** |
| 1-question cause, 1 RED, 1 sibling | **0.8400** |
| 1-question cause, 1 AMBER | 0.4000 |
| 5-question cause, 1 of 5 RED | 0.3524 |
| 5-question cause, 3 of 5 RED | 0.6571 |
| 5-question cause, 5 of 5 RED | 0.9619 |

Catalogue reach: **80.3%** typical, **87.8%** at the observed ceiling.
All 12 persona primaries reach **0.84**.

**Its cost, stated plainly:** one RED answer on a one-question cause *is* strong.
That is the "maximum confidence from one sentence" property that
`detection_confidence`'s corroboration factor was specifically added to prevent.
E also *reverses* a property: a 5-question cause with 1 RED scores 0.35, lower
than today — asking more makes a cause harder to prove, which is defensible
(we looked harder and found less) but is a real behavioural change.

---

## YOUR NINE QUESTIONS, ANSWERED

1. **% of catalogue that can reach 80%** — A: 0% typical / 12.2% theoretical.
   B: 0% / 19.7%. C and D: 0% typical, 19.7% at the observed evidence ceiling,
   100% only under unreachable sibling saturation. E: **80.3% typical**.
2. **Minimum evidence required** — A: 3 direct REDs (impossible for 87.9% of
   causes, which have ≤2 questions). B: 2 REDs. C/D: 2–3 REDs. E: 1 RED, if it
   is the cause's only question.
3. **Can a one-question cause reach 80%?** — A **no** (max 0.625). B **no**
   (max 0.767). C **only** with ~40 sibling answers (max 0.80 exactly). D **only**
   with saturation (max 0.85). **E yes, by design.**
4. **Can AMBER-only reach 80%?** — A **yes** (0.944 best case; 8 AMBERs in one
   pillar = exactly 0.80 — this is defect F3 and it survives in B, C and D).
   **E no** (AMBER caps a cause at 0.50 × reach).
5. **Can sibling-only reach 80%?** — **No, under every candidate.** A 0.25,
   B 0.25, C 0.60, D 0.70 — all below threshold. The ceiling added after the
   0.9375 defect holds in all four.
6. **Does contradiction reliably reduce strong status?** — It always lowers the
   score, but it only *changes status* where the cause was above 0.80 to begin
   with. Under A/C/D that essentially never happens in a real session, so
   contradiction handling is **untestable in production conditions**. Under B
   (3 RED → 0.870, then 2 GREEN → 0.728) and under E it demotes correctly.
7. **Does cross-pillar corroboration matter more than same-pillar repetition?** —
   In the model, yes. **In production, the question does not arise**: S1 means a
   cause's evidence is always in one pillar. The mechanism is inert, and the
   implementation's docstring claiming 0.80 "needs a second pillar" is wrong
   twice over — it is both achievable without one (defect F2) and impossible
   with one.
8. **What happens to the four Set A2 personas?** — Under A, B, C and D: **0 of 12
   primaries can ever be strong**, so all four personas end in
   `bank_exhausted`/`safety_ceiling`, never `problem_explained`. Under E: all 12
   reach 0.84.
9. **Does the completion gate become realistically reachable?** — **A: no. B: no.
   C: no. D: no. E: yes.** The gate requires a strong cause that explains an
   anchor problem; with zero strong causes it cannot pass, so no production
   diagnosis would ever complete successfully under A–D.

---

## WHAT THIS MEANS FOR THE CHOICE

A, B, C and D are one family — *accumulate absolute evidence mass* — and the data
says that family cannot work here, because the catalogue gives 80.3% of causes a
single question and sessions ask each cause roughly once. Tuning the constant
moves the theoretical ceiling and changes nothing a founder would experience.

That leaves three genuinely different levers, and they are product decisions:

- **Change what "strong" means** (option E): strength relative to askable
  evidence. Makes the gate reachable and the personas work. Costs the
  one-answer-is-enough property.
- **Change the threshold**: for typical sessions it would have to fall to ≤0.60
  under A/C/D, or ≤0.77 under B. 0.60 is not defensible as "strong" to a founder.
- **Change question selection**: concentrate probes so a candidate cause gets
  3–4 answers. This fights the pillar round-robin that exists to stop a single
  category eating the budget, and the catalogue caps it anyway — 87.9% of causes
  have at most 2 questions to ask.

A fourth combination is available and is what I would put forward if asked:
**E for the score, with the corroboration requirement moved to the gate** — let a
one-question cause reach 0.80 on its own evidence, but require the *quality gate*
(which already checks pillar sufficiency and high-value unanswered questions) to
carry the "don't conclude from one sentence" guarantee that the score can no
longer provide. That keeps both properties, at the cost of a more complex gate.

I have not implemented any of this. The decision is yours.
