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
from app.api.v1.reasoning.schemas import (
    RootCauseDetection,
    ScoreComponent,
    ScoredRootCause,
)
from app.models.enums import ConfirmationStatus

_QUANT = Decimal("0.0001")
_ZERO = Decimal("0")
_ONE = Decimal("1")
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
