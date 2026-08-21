"""Confidence Scoring Model -- the four-factor ranking formula and the outer-layer
session confidence / routing decision.

Formula (all weights and multipliers read from the configuration layer, which
loads them from scoring_rules -- nothing here is hardcoded):

    final_weighted_score =
          W_category_risk        * category_risk_score      (risk 0..1)
        + W_confirmation_status   * confirmation_multiplier  (0.5 / 1.0 / 1.5)
        + W_stage_probability     * stage_probability        (prior 0..1)
        + W_industry_probability  * industry_probability     (prior 0..1)

The four weights are validated to sum to 1.0 (WEIGHT_FACTORS_SUM_CHECK) before any
scoring runs. Each factor's contribution (weight * value) is retained on the
result, and the contributions sum to final_weighted_score, so every score is
fully auditable.

Absence policy: a factor whose source datum is missing (no category risk, no
stage weight for this cause, no configured industry strategy) contributes the
neutral value 0 and is flagged `available=False` in the audit -- absence is
recorded, never invented. Probability factors are clamped to [0, 1]; the
confirmation multiplier is used as configured.

Deterministic and independent of Retrieval and LLM providers: given the same
detections and the same database/config state, the same scores and ranks result.

The 0-100 overall confidence formula is not defined in scoring_rules (only its
routing thresholds are), so it is delegated to the injected
OverallConfidenceStrategy; routing is a pure threshold lookup over the result.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal

from app.api.v1.reasoning.config import ConfidenceInputs, ConfirmationMultipliers
from app.api.v1.reasoning.interfaces import ConfidenceModel, ReasoningContext
from app.api.v1.reasoning.repository import ReasoningRepository
from app.core.config import settings
from app.core.logger import logger
from app.api.v1.reasoning.schemas import (
    DiagnosisResult,
    RootCauseDetection,
    ScoreComponent,
    ScoredRootCause,
)
from app.models.enums import ConfirmationStatus

_QUANT = Decimal("0.0001")
_ZERO = Decimal("0")
_ONE = Decimal("1")

# High Distress reliability. session_state_bands stores NULL for this band, and
# that NULL used to become 0 here -- which, since reliability multiplies the
# whole model, reported 0/100 confidence for a completed 30-question session
# whose root causes had ranked cleanly. Live-reproduced: a founder answering
# candidly ("it stings", "I felt sick for an evening") tripped the language
# detector and had every measured signal thrown away.
#
# The band's own text asks for "diagnostic accuracy is low" and "report is
# de-prioritised" -- low and de-prioritised, not void. The other three bands
# step 1.00 -> 0.95 -> 0.85, so a cliff to 0.00 also breaks a gradient the
# source table clearly intends. 0.70 continues that curve: a heavy discount
# that still lets a real diagnosis through.
_CONFIDENCE_MIN = Decimal("0")
_CONFIDENCE_MAX = Decimal("100")

_FACTOR_CATEGORY_RISK = "category_risk"
_FACTOR_CONFIRMATION = "confirmation"
_FACTOR_STAGE_PROBABILITY = "stage_probability"
_FACTOR_INDUSTRY_PROBABILITY = "industry_probability"


def _q(value: Decimal) -> Decimal:
    return value.quantize(_QUANT, rounding=ROUND_HALF_UP)


def _clamp(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    return max(low, min(high, value))


class WeightedConfidenceModel(ConfidenceModel):
    def __init__(self, repository: ReasoningRepository):
        self.repository = repository

    # --- Inner layer: four-factor scoring + ranking -----------------------

    def score_and_rank(
        self,
        detections: list[RootCauseDetection],
        context: ReasoningContext,
    ) -> list[ScoredRootCause]:
        weights = context.config.ranking_weights
        weights.validate()  # requirement: weights must sum to 1.0 before scoring

        if not detections:
            return []

        multipliers = context.config.confirmation_multipliers

        # Load the priors once (avoid N+1). Missing sources degrade to neutral 0.
        stage_weights: Mapping[int, Decimal] = (
            self.repository.get_stage_weights(context.stage_id)
            if context.stage_id is not None
            else {}
        )
        industry_weights = self._load_industry_weights(context)

        scored: list[tuple[RootCauseDetection, ScoredRootCause]] = []
        for detection in detections:
            scored.append(
                (detection, self._score_one(detection, context, multipliers, stage_weights, industry_weights))
            )

        return self._rank(scored, context)

    def _score_one(
        self,
        detection: RootCauseDetection,
        context: ReasoningContext,
        multipliers: ConfirmationMultipliers,
        stage_weights: Mapping[int, Decimal],
        industry_weights: Mapping[str, object] | None,
    ) -> ScoredRootCause:
        weights = context.config.ranking_weights

        # 1. Category risk (already normalised 0..1 by the diagnostic layer).
        cat_available = detection.category_risk_score is not None
        cat_value = _clamp(detection.category_risk_score or _ZERO, _ZERO, _ONE)

        # 2. Confirmation multiplier (0.5 / 1.0 / 1.5) -- always available.
        conf_multiplier = self._multiplier(detection.confirmation_status, multipliers)

        # 3. Stage-adjusted prior from root_cause_weights.
        stage_raw = stage_weights.get(detection.root_cause_id)
        stage_available = stage_raw is not None
        stage_value = _clamp(stage_raw if stage_available else _ZERO, _ZERO, _ONE)

        # 4. Industry-adjusted prior via the injected strategy.
        industry_value, industry_available = self._industry_probability(
            context, industry_weights, detection.root_cause_id
        )

        components = (
            ScoreComponent(
                _FACTOR_CATEGORY_RISK,
                weights.category_risk,
                cat_value,
                _q(weights.category_risk * cat_value),
                cat_available,
            ),
            ScoreComponent(
                _FACTOR_CONFIRMATION,
                weights.confirmation_status,
                conf_multiplier,
                _q(weights.confirmation_status * conf_multiplier),
                True,
            ),
            ScoreComponent(
                _FACTOR_STAGE_PROBABILITY,
                weights.stage_probability,
                stage_value,
                _q(weights.stage_probability * stage_value),
                stage_available,
            ),
            ScoreComponent(
                _FACTOR_INDUSTRY_PROBABILITY,
                weights.industry_probability,
                industry_value,
                _q(weights.industry_probability * industry_value),
                industry_available,
            ),
        )
        final = _q(sum((c.contribution for c in components), _ZERO))

        return ScoredRootCause(
            root_cause_id=detection.root_cause_id,
            category_risk_score=cat_value,
            confirmation_status=detection.confirmation_status,
            confirmation_multiplier=conf_multiplier,
            stage_probability=stage_value,
            industry_probability=industry_value,
            final_weighted_score=final,
            rank=0,            # assigned in _rank
            is_top_finding=False,
            components=components,
        )

    def _rank(
        self,
        scored: list[tuple[RootCauseDetection, ScoredRootCause]],
        context: ReasoningContext,
    ) -> list[ScoredRootCause]:
        """Rank by final score, with a fully deterministic tiebreak so equal
        scores never reorder between runs: confirmed first, then stronger
        detection evidence, then lowest root_cause_id."""
        confirmed_rank = {
            ConfirmationStatus.CONFIRMED: 0,
            ConfirmationStatus.UNCONFIRMED: 1,
            ConfirmationStatus.NOT_TESTED: 2,
        }

        ordered = sorted(
            scored,
            key=lambda pair: (
                -pair[1].final_weighted_score,
                confirmed_rank.get(pair[1].confirmation_status, 9),
                -pair[0].detection_score,
                pair[1].root_cause_id,
            ),
        )

        top_n = context.config.branching.top_root_causes_report
        result: list[ScoredRootCause] = []
        for index, (_detection, sc) in enumerate(ordered):
            rank = index + 1
            result.append(
                ScoredRootCause(
                    root_cause_id=sc.root_cause_id,
                    category_risk_score=sc.category_risk_score,
                    confirmation_status=sc.confirmation_status,
                    confirmation_multiplier=sc.confirmation_multiplier,
                    stage_probability=sc.stage_probability,
                    industry_probability=sc.industry_probability,
                    final_weighted_score=sc.final_weighted_score,
                    rank=rank,
                    is_top_finding=rank <= top_n,
                    components=sc.components,
                )
            )
        return result

    # --- Outer layer: assemble confidence inputs --------------------------

    def build_confidence_inputs(
        self,
        *,
        diagnosis: DiagnosisResult,
        scored: list[ScoredRootCause],
        questions_answered: int,
        context: ReasoningContext,
        consistency=None,
    ) -> ConfidenceInputs:
        """Resolve the five evidence signals, the reliability modifier and the
        hard-rule facts (CONFIDENCE_SCORE_METHODOLOGY). This is where the DB reads
        live, so the strategy's compute stays a pure function of the result."""
        cfg = context.config

        # (a) CATEGORY SIGNAL -- strongest normalised category risk (already
        # category_risk_score / category_max, 0..1). Raw risk, not the ranked
        # score, so confirmation is not counted twice.
        category_signal = max(
            (c.normalised_risk for c in diagnosis.category_risks), default=_ZERO
        )

        # (b) EVIDENCE COVERAGE -- how much of THIS diagnosis is done: answered
        # questions over the diagnosis budget, capped at 1.0.
        #
        # This divided by the founder's whole in-scope bank until the 30-question
        # cap existed, and that made the score's own target unreachable. A Stage
        # 0->1 founder has 569 in-scope questions, so 30 answers scored
        # 30/569 = 0.05 on a 25%-weight input, capping the achievable total at 76
        # -- below the 80 required to generate a report. A founder could answer
        # every question flawlessly and still never finish. The cap and the
        # threshold were mutually exclusive, and nothing failed loudly to say so:
        # diagnoses would simply always end short.
        #
        # "Coverage" now means what the diagnosis actually measures. A founder
        # answering strongly crosses 80 around question 10-15 and finishes early;
        # a weaker run continues toward the cap.
        budget = max(1, settings.MAX_DIAGNOSIS_QUESTIONS)
        coverage = min(_ONE, Decimal(questions_answered) / Decimal(budget))

        # (c) ANSWER CONSISTENCY -- measured by the semantic contradiction detector
        # (LLMConsistencyDetector). A measured `ConsistencyResult` is passed in when
        # the detector ran; if it is absent or the detector FAILED (available=False),
        # the signal stays UNAVAILABLE so the strategy excludes it and renormalises
        # the remaining weights -- an unmeasured signal never rewards or penalises.
        if consistency is not None and getattr(consistency, "available", False):
            consistency_available = True
            consistency_score = consistency.score
        else:
            consistency_available = False
            consistency_score = None

        # (d) CONFIRMATION RATIO -- top causes' confirmation status rescaled to 0..1.
        confirmation_ratio = self._confirmation_ratio(
            [s for s in scored if s.is_top_finding], cfg.confirmation_multipliers
        )

        # (e) SEPARATION -- gap between the top two ranked scores.
        separation = self._separation(scored)

        # Reliability modifier: band for the session's distress score. None (High
        # Distress) or a distress trigger routes through the distress hard rule.
        distress_score = context.session.session_distress_score
        distress_override = bool(diagnosis.distress_mode) or (
            distress_score is not None
            and Decimal(distress_score) >= cfg.distress.high_distress_score
        )
        # `None` used to mean two different things here -- "high distress, so
        # discount this entirely" and "the lookup returned nothing" -- and the
        # strategy treated both as zero, which multiplies the whole score to 0.
        # A session with distress 0.00 and five ranked root causes scored 0
        # because a config lookup came back empty. Nothing failed loudly; the
        # diagnosis simply reported no confidence, forever.
        #
        # Distress now says so explicitly with a zero, and an unresolvable factor
        # degrades to NEUTRAL. Absence must not be able to destroy every measured
        # signal -- the rest of this model already excludes an unavailable input
        # and renormalises rather than scoring it zero.
        # Distress no longer discounts reliability either (product decision,
        # 2026-08-20; see the DISTRESS OVERRIDE note in confidence_score.py).
        # _DISTRESS_RELIABILITY (0.70) was the second half of a double penalty:
        # combined with the now-removed hard cap it turned an 84% evidence base
        # into a reported 59. A founder being candid about stress is not evidence
        # that their answers are 30% less true -- and the honest, self-aware
        # founders this product is for are exactly the ones who trip it.
        #
        # Distress remains fully measured and is surfaced to the founder through
        # the support path; it is simply no longer allowed to silently rewrite
        # the diagnostic score.
        measured = self.repository.get_reliability_factor(distress_score)
        if measured is None:
            logger.warning(
                "No reliability factor resolved; treating it as neutral",
                extra={"distress_score": str(distress_score)},
            )
        reliability_factor = measured if measured is not None else _ONE

        flagged = [c for c in diagnosis.category_risks if c.is_flagged]
        return ConfidenceInputs(
            category_signal=category_signal,
            evidence_coverage=coverage,
            consistency_available=consistency_available,
            consistency_score=consistency_score,
            confirmation_ratio=confirmation_ratio,
            separation=separation,
            reliability_factor=reliability_factor,
            questions_answered=questions_answered,
            flagged_category_count=len(flagged),
            any_category_flagged=bool(flagged),
            distress_override=distress_override,
            stages_away=self._stages_away(context),
        )

    def _confirmation_ratio(
        self, top_findings, multipliers: ConfirmationMultipliers
    ) -> Decimal:
        """Mean confirmation of the top-ranked causes, each mapped via the
        confirmation multipliers and rescaled (value - not_tested) / range to 0..1
        (Confirmed 1.5 -> 1.0, Unconfirmed 1.0 -> 0.5, Not Tested 0.5 -> 0.0)."""
        if not top_findings:
            return _ZERO
        low = multipliers.not_tested
        span = multipliers.confirmed - low
        if span <= 0:
            return _ZERO
        by_status = {
            ConfirmationStatus.CONFIRMED: multipliers.confirmed,
            ConfirmationStatus.UNCONFIRMED: multipliers.unconfirmed,
            ConfirmationStatus.NOT_TESTED: multipliers.not_tested,
        }
        values = [
            _clamp((by_status[s.confirmation_status] - low) / span, _ZERO, _ONE)
            for s in top_findings
        ]
        return _q(sum(values, _ZERO) / Decimal(len(values)))

    def _separation(self, scored: list[ScoredRootCause]) -> Decimal:
        """(top - second) / top over the ranked scores, capped at 1.0; 0 when the
        top score is 0 or the top two are tied. Guards against a decisive-sounding
        report built on a near-tie."""
        ranked = sorted(scored, key=lambda s: s.rank)
        if not ranked:
            return _ZERO
        top = ranked[0].final_weighted_score
        if top <= _ZERO:
            return _ZERO
        second = ranked[1].final_weighted_score if len(ranked) > 1 else _ZERO
        if top == second:
            return _ZERO
        return min(_ONE, _q((top - second) / top))

    def _stages_away(self, context: ReasoningContext) -> int | None:
        """How many stages the evidence-detected stage sits from the self-reported
        stage, by founder_stages.stage_order. None when either stage is unknown."""
        self_reported = context.founder.stage_id
        detected = context.stage_id
        if self_reported is None or detected is None:
            return None
        reported_order = self.repository.get_stage_order(self_reported)
        detected_order = self.repository.get_stage_order(detected)
        if reported_order is None or detected_order is None:
            return None
        return abs(reported_order - detected_order)

    # --- Outer layer: session confidence + routing ------------------------

    def overall_confidence(
        self,
        inputs: ConfidenceInputs,
        context: ReasoningContext,
    ) -> Decimal:
        """Delegate to the injected 0-100 strategy (formula not in scoring_rules),
        then clamp to the [0, 100] range the sessions table enforces."""
        strategy = context.config.require_confidence_strategy()
        raw = strategy.compute(inputs)
        return _q(_clamp(Decimal(raw), _CONFIDENCE_MIN, _CONFIDENCE_MAX))

    def routing_decision(self, overall_confidence_score: Decimal, context: ReasoningContext) -> str:
        """Continue / Validate / Generate Report, from the configured thresholds."""
        return context.config.confidence.routing_state_for(overall_confidence_score)

    # --- Helpers ----------------------------------------------------------

    def _multiplier(
        self, status: ConfirmationStatus, multipliers: ConfirmationMultipliers
    ) -> Decimal:
        return {
            ConfirmationStatus.CONFIRMED: multipliers.confirmed,
            ConfirmationStatus.UNCONFIRMED: multipliers.unconfirmed,
            ConfirmationStatus.NOT_TESTED: multipliers.not_tested,
        }[status]

    def _load_industry_weights(
        self, context: ReasoningContext
    ) -> Mapping[str, object] | None:
        if context.industry_id is None:
            return None
        industry = self.repository.get_industry(context.industry_id)
        return industry.top_pain_point_weights if industry is not None else None

    def _industry_probability(
        self,
        context: ReasoningContext,
        industry_weights: Mapping[str, object] | None,
        root_cause_id: int,
    ) -> tuple[Decimal, bool]:
        """Resolve the industry prior via the injected strategy. Returns
        (value, available). Unavailable -> neutral 0, recorded as such; the
        industry term activates automatically once a strategy is configured."""
        strategy = context.config.industry_probability
        if industry_weights is None or strategy is None:
            return _ZERO, False
        value = _clamp(Decimal(strategy.probability(industry_weights, root_cause_id)), _ZERO, _ONE)
        return value, True
