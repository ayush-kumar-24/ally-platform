"""Overall Confidence Score strategy -- the approved CONFIDENCE_SCORE_METHODOLOGY.

Answers "how certain are we that we have identified this founder's real problem",
never "how healthy is the business" -- Business Health must never feed this score.

Structure (all weights and factors are loaded from scoring_rules by the caller and
handed to the constructor -- nothing here is hardcoded):

    base = ( sum of w_signal * signal_value over the AVAILABLE signals )
           / ( sum of w_signal over the AVAILABLE signals )        (each value 0..1)

The five signals are Category Signal, Evidence Coverage, Answer Consistency,
Confirmation Ratio and Separation. All are always available except Answer
Consistency, which is measured only when the contradiction detector exists. An
unavailable signal is EXCLUDED and the remaining weights renormalise to sum to
1.0 -- it is never defaulted to a perfect 1.0 (see compute). With every signal
available the denominator is 1.0 and this reduces to the plain weighted sum.

    score = round( base * reliability_factor * stage_coherence_factor * 100 )

The five weights measure WHAT the evidence says; the two multipliers measure
whether the evidence was gathered under conditions we can trust. `reliability_factor`
is the per-session session_state_bands value (resolved by the caller);
`stage_coherence_factor` is the CONFIDENCE_STAGE_COHERENCE_FACTOR constant.

Then CONFIDENCE_HARD_RULES are applied before routing. The routing vocabulary is
fixed (continue < CONTINUE_MAX <= validate < GENERATE_REPORT_MIN <= generate_report),
so each hard rule is expressed as the strongest downward score cap that yields the
required routing outcome; the rules only ever LOWER the score, never raise it:

  * floor_cap    = CONTINUE_MAX - 1      -> forces "continue"
  * no_report_cap = GENERATE_REPORT_MIN - 1 -> forces at most "validate"

Both caps are derived from the routing thresholds, not hardcoded, so they track
the DB. Behavioural consequences that a single number cannot express (the distress
*path*, stage re-confirmation, psychology-first narrative) are owned by the parts
of the system that already handle them -- the pipeline's distress handling and
report generation; here they are encoded to their nearest safe numeric effect.

Deterministic: given the same inputs and the same DB-loaded constants, the same
score results.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.api.v1.reasoning.config import ConfidenceInputs, ConfidenceScoreWeights

_ZERO = Decimal("0")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")
_MIN = Decimal("0")
_MAX = Decimal("100")


def _clamp01(value: Decimal) -> Decimal:
    return max(_ZERO, min(_ONE, value))


def _round_int(value: Decimal) -> Decimal:
    return value.quantize(_ONE, rounding=ROUND_HALF_UP)


class ConfidenceScoreStrategy:
    """Concrete OverallConfidenceStrategy implementing CONFIDENCE_SCORE_METHODOLOGY.

    Structurally satisfies the OverallConfidenceStrategy protocol (compute(inputs)
    -> Decimal). All numeric business values are injected from scoring_rules by the
    composition root; the class holds no literal weights or thresholds of its own.
    """

    def __init__(
        self,
        *,
        weights: ConfidenceScoreWeights,
        stage_coherence_factor: Decimal,
        min_questions_floor: int,
        multi_category_flag_threshold: int,
        continue_max: Decimal,
        generate_report_min: Decimal,
    ):
        weights.validate()  # fail closed if the five weights do not sum to 1.0
        self.weights = weights
        self.stage_coherence_factor = stage_coherence_factor
        self.min_questions_floor = min_questions_floor
        self.multi_category_flag_threshold = multi_category_flag_threshold
        # Routing-derived caps (not hardcoded -- they follow the DB thresholds).
        self._floor_cap = continue_max - _ONE
        self._no_report_cap = generate_report_min - _ONE

    def compute(self, inputs: ConfidenceInputs) -> Decimal:
        # Only signals that were actually measured contribute. An UNAVAILABLE
        # signal is excluded and the remaining weights are renormalised to sum to
        # 1.0 (the same treatment BusinessHealthScorer gives an unassessed pillar).
        # We deliberately do NOT substitute a perfect 1.0 for a signal we never
        # measured: that would award unearned certainty on a 20%-weighted input and
        # could tip routing on evidence that was never gathered. Excluding it is
        # neutral -- it neither rewards nor penalises the founder for missing
        # functionality; when the detector lands, the signal simply rejoins the sum
        # at its full weight and no renormalisation occurs.
        contributions: list[tuple[Decimal, Decimal]] = [
            (self.weights.category_signal, _clamp01(inputs.category_signal)),
            (self.weights.coverage, _clamp01(inputs.evidence_coverage)),
            (self.weights.confirmation, _clamp01(inputs.confirmation_ratio)),
            (self.weights.separation, _clamp01(inputs.separation)),
        ]
        if inputs.consistency_available and inputs.consistency_score is not None:
            contributions.append(
                (self.weights.consistency, _clamp01(inputs.consistency_score))
            )

        total_weight = sum((w for w, _ in contributions), _ZERO)
        if total_weight <= _ZERO:
            base = _ZERO
        else:
            base = sum((w * v for w, v in contributions), _ZERO) / total_weight

        # Reliability: None marks the High Distress band (no trustworthy evidence).
        # The distress hard rule handles routing; a null factor contributes 0.
        # Neutral, not zero. A missing multiplier means "we could not measure
        # how trustworthy the conditions were", which is not the same as "the
        # evidence is worthless" -- and zeroing here discards every signal that
        # WAS measured. High distress passes an explicit 0 when it wants that.
        reliability = inputs.reliability_factor if inputs.reliability_factor is not None else _ONE

        score = _round_int(base * reliability * self.stage_coherence_factor * _HUNDRED)
        score = self._apply_hard_rules(score, inputs)
        return max(_MIN, min(_MAX, score))

    def _apply_hard_rules(self, score: Decimal, inputs: ConfidenceInputs) -> Decimal:
        """CONFIDENCE_HARD_RULES, evaluated in order. Each only lowers the score.

        The order is preserved for faithfulness to the spec; because every rule is
        a downward cap the net effect equals the minimum applicable cap.
        """
        # 1. DISTRESS OVERRIDE -- wellbeing overrides diagnostic completeness. The
        #    distress *path* is owned by the pipeline (distress_mode / high_distress);
        #    numerically we guarantee a standard report is unreachable.
        if inputs.distress_override:
            score = min(score, self._floor_cap)

        # 2. SEVERE STAGE MISMATCH -- evidence >= 2 stages from the self-reported
        #    stage: re-confirm the stage before any report, so block generate_report.
        if inputs.stages_away is not None and inputs.stages_away >= 2:
            score = min(score, self._no_report_cap)

        # 3. MINIMUM QUESTION FLOOR -- generate_report unreachable below the floor.
        if inputs.questions_answered < self.min_questions_floor:
            score = min(score, self._floor_cap)

        # 4. NO CATEGORY ABOVE THRESHOLD -- do not force a diagnosis; monitor only.
        if not inputs.any_category_flagged:
            score = min(score, self._floor_cap)

        # 5. MULTI-CATEGORY CROSS-CHECK -- ADVISORY, not blocking. When many
        #    categories are flagged a consultant cross-check is advised, but that
        #    must not permanently cap the score: with 8 categories and easy
        #    flagging it made generate_report unreachable in practice. The advisory
        #    is surfaced downstream from inputs.flagged_category_count (the internal
        #    report already lists the flagged categories); the number is not capped.

        # 6. PSYCHOLOGY PRECEDENCE -- a report-narrative ordering rule
        #    (PSYCHOLOGY_NARRATIVE_PRECEDENCE), handled in report generation. It has
        #    no effect on the numeric score or routing, so there is nothing to do here.
        return score
