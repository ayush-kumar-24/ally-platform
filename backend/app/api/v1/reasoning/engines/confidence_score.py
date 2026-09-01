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
from app.core.logger import logger

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
        min_measurable_inputs: int = 3,
    ):
        weights.validate()  # fail closed if the five weights do not sum to 1.0
        self.weights = weights
        #: CONFIDENCE_UNAVAILABLE_INPUT_HANDLING's rule_value -- the minimum number
        #: of the five signals that must be measurable for the score to mean
        #: anything. Defaulted rather than required so an unseeded database still
        #: builds a strategy; the DB row is the authority.
        self.min_measurable_inputs = min_measurable_inputs
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
        #
        # Every signal is gated on its own availability, not just consistency. The
        # rule says so in as many words: it "applies to all five inputs, not only
        # Answer Consistency". Confirmation and separation used to be included
        # unconditionally, which meant a session with NO ranked root cause scored
        # them 0 -- the one thing the rule forbids outright ("never defaulted to
        # 1.0 and never defaulted to 0"). Nothing had been checked and found
        # clean; there had been nothing to check. A healthy founder therefore
        # carried two zeroes worth 25% of their score for having no problems.
        #
        # Coverage is not gated: answered-over-budget is always computable.
        contributions: list[tuple[Decimal, Decimal]] = []
        if inputs.category_signal_available:
            contributions.append(
                (self.weights.category_signal, _clamp01(inputs.category_signal))
            )
        contributions.append((self.weights.coverage, _clamp01(inputs.evidence_coverage)))
        if inputs.confirmation_available:
            contributions.append(
                (self.weights.confirmation, _clamp01(inputs.confirmation_ratio))
            )
        if inputs.separation_available:
            contributions.append((self.weights.separation, _clamp01(inputs.separation)))
        if inputs.consistency_available and inputs.consistency_score is not None:
            contributions.append(
                (self.weights.consistency, _clamp01(inputs.consistency_score))
            )
        measured_inputs = len(contributions)

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
        pre_rules = score
        score = self._apply_hard_rules(score, inputs, measured_inputs)

        # Why this is logged: a founder's report showed "0/100 confidence" after
        # 30 answered questions and 8 ranked root causes, and nothing in the
        # logs said which input collapsed. Every component is emitted here so a
        # zero is attributable to the term that produced it rather than needing
        # a reconstruction from the database afterwards. Same reasoning as the
        # distress-decision log, which made that bug diagnosable in one line.
        logger.info(
            "confidence components",
            extra={
                "stage": "confidence_components",
                "category_signal": str(_clamp01(inputs.category_signal)),
                "evidence_coverage": str(_clamp01(inputs.evidence_coverage)),
                "confirmation_ratio": str(_clamp01(inputs.confirmation_ratio)),
                "separation": str(_clamp01(inputs.separation)),
                "consistency_available": inputs.consistency_available,
                "measured_inputs": measured_inputs,
                "consistency_score": str(inputs.consistency_score),
                "base": str(base),
                "reliability_factor": str(reliability),
                "stage_coherence_factor": str(self.stage_coherence_factor),
                "score_before_hard_rules": str(pre_rules),
                "score_after_hard_rules": str(score),
                "distress_override": inputs.distress_override,
                "any_category_flagged": inputs.any_category_flagged,
                "questions_answered": inputs.questions_answered,
                "stages_away": inputs.stages_away,
            },
        )
        return max(_MIN, min(_MAX, score))

    def _apply_hard_rules(
        self, score: Decimal, inputs: ConfidenceInputs, measured_inputs: int = 5
    ) -> Decimal:
        """CONFIDENCE_HARD_RULES, evaluated in order. Each only lowers the score.

        The order is preserved for faithfulness to the spec; because every rule is
        a downward cap the net effect equals the minimum applicable cap.
        """
        # 1. DISTRESS OVERRIDE -- REMOVED as a numeric cap (product decision,
        #    2026-08-20). It used to force `score = min(score, floor_cap)`, which
        #    made a standard report unreachable for any distressed founder.
        #
        #    Measured on a real session: evidence base 0.83676 (84%) with 30
        #    answers and 8 ranked root causes was reported as 59, because
        #    distress applied a 0.70 reliability multiplier AND this cap on top
        #    of it. The founder saw "0/100" on their report in an earlier run of
        #    the same journey.
        #
        #    Confidence answers "how sure are we of this diagnosis"; distress
        #    answers "how is this founder doing". They are independent, and
        #    collapsing one into the other corrupts both -- it discards evidence
        #    that was gathered correctly and tells the founder their diagnosis is
        #    worthless because they were honest about struggling. Distress is
        #    still detected, still recorded on the session, still routes to the
        #    support path, and is still surfaced in the report; it simply no
        #    longer rewrites the diagnostic number.

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

        # 4b. TOO FEW MEASURED INPUTS -- CONFIDENCE_UNAVAILABLE_INPUT_HANDLING's
        #     own guard, whose rule_value IS this minimum count. Excluding an
        #     unmeasured signal and renormalising is right, but it has a floor:
        #     renormalising onto one or two signals does not produce a confidence
        #     measure, it produces a number that looks like one. Below the floor
        #     the score is capped so routing stays on `continue` and the diagnosis
        #     keeps gathering, which is the honest outcome when most of the model
        #     could not be evaluated.
        if measured_inputs < self.min_measurable_inputs:
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
