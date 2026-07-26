"""Configuration layer for the reasoning engines.

Design goals (per the approved plan):
  * Business rules that EXIST in the database (scoring_rules) are loaded into
    typed, validated config objects -- never hardcoded in engine code.
  * Business rules that DO NOT yet exist in the database (the 0-100 confidence
    formula, per-category maximum scores, the distress-signal scoring table,
    the industry-probability read shape) are expressed as injectable strategy
    interfaces, so they can be supplied/replaced without touching engines.

Nothing here computes a diagnosis. It holds parameters, validates them, and
declares the strategy contracts the engines depend on. The numeric values live
in Postgres; this module only gives them names and types.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Mapping, Protocol, runtime_checkable

from app.api.v1.reasoning.errors import FeatureDisabledError, ReasoningConfigError

# Weights are floating business values; this tolerance guards the sum==1 check
# against representation noise without masking a real misconfiguration.
_WEIGHT_SUM_TOLERANCE = Decimal("0.0001")


class RuleCode(str, Enum):
    """Every rule_code the reasoning layer consumes from `scoring_rules`.

    Centralising them here means a renamed or missing rule fails fast at load
    with a clear message, instead of a stray string typo deep in an engine.
    """

    QUESTION_SCORE_GREEN = "QUESTION_SCORE_GREEN"
    QUESTION_SCORE_AMBER = "QUESTION_SCORE_AMBER"
    QUESTION_SCORE_RED = "QUESTION_SCORE_RED"

    CONFIRMED_MULTIPLIER = "CONFIRMED_MULTIPLIER"
    UNCONFIRMED_MULTIPLIER = "UNCONFIRMED_MULTIPLIER"
    NOT_TESTED_MULTIPLIER = "NOT_TESTED_MULTIPLIER"

    WEIGHT_CATEGORY_RISK = "WEIGHT_CATEGORY_RISK"
    WEIGHT_CONFIRMATION_STATUS = "WEIGHT_CONFIRMATION_STATUS"
    WEIGHT_STAGE_PROBABILITY = "WEIGHT_STAGE_PROBABILITY"
    WEIGHT_INDUSTRY_PROBABILITY = "WEIGHT_INDUSTRY_PROBABILITY"
    WEIGHT_FACTORS_SUM_CHECK = "WEIGHT_FACTORS_SUM_CHECK"

    CAT_RISK_THRESHOLD = "CAT_RISK_THRESHOLD"
    AMBER_CLUSTER_TRIGGER = "AMBER_CLUSTER_TRIGGER"
    MULTI_CATEGORY_FLAG_THRESHOLD = "MULTI_CATEGORY_FLAG_THRESHOLD"
    TOP_ROOT_CAUSES_REPORT = "TOP_ROOT_CAUSES_REPORT"

    DISTRESS_SCORE_RED = "DISTRESS_SCORE_RED"
    DISTRESS_QUESTIONS_TRIGGER = "DISTRESS_QUESTIONS_TRIGGER"
    SESSION_STATE_HIGH_DISTRESS_THRESHOLD = "SESSION_STATE_HIGH_DISTRESS_THRESHOLD"

    CONFIDENCE_CONTINUE_MAX = "CONFIDENCE_CONTINUE_MAX"
    CONFIDENCE_VALIDATE_MIN = "CONFIDENCE_VALIDATE_MIN"
    CONFIDENCE_VALIDATE_MAX = "CONFIDENCE_VALIDATE_MAX"
    CONFIDENCE_GENERATE_REPORT_MIN = "CONFIDENCE_GENERATE_REPORT_MIN"


# ---------------------------------------------------------------------------
# Typed value objects loaded from scoring_rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuestionScores:
    """Numeric score for each Green/Amber/Red band (0 / 1 / 2)."""

    green: Decimal
    amber: Decimal
    red: Decimal


@dataclass(frozen=True)
class ConfirmationMultipliers:
    """Weight multiplier applied by root-cause confirmation status."""

    confirmed: Decimal
    unconfirmed: Decimal
    not_tested: Decimal


@dataclass(frozen=True)
class RankingWeights:
    """The four weights of the final root-cause ranking formula.

    Validated to sum to `expected_sum` (WEIGHT_FACTORS_SUM_CHECK, normally 1.0);
    the engine that applies them is written elsewhere -- this only guarantees the
    weights are internally consistent before any ranking runs.
    """

    category_risk: Decimal
    confirmation_status: Decimal
    stage_probability: Decimal
    industry_probability: Decimal
    expected_sum: Decimal = Decimal("1")

    def validate(self) -> None:
        total = (
            self.category_risk
            + self.confirmation_status
            + self.stage_probability
            + self.industry_probability
        )
        if abs(total - self.expected_sum) > _WEIGHT_SUM_TOLERANCE:
            raise ReasoningConfigError(
                f"Ranking weights sum to {total}, expected {self.expected_sum} "
                "(WEIGHT_FACTORS_SUM_CHECK). Adjust the scoring_rules so the four "
                "weight factors sum to exactly the check value."
            )


@dataclass(frozen=True)
class BranchingThresholds:
    """Inner-layer branching parameters."""

    category_risk_threshold: Decimal  # fraction of category max that flags deep-dive
    amber_cluster_trigger: int
    multi_category_flag_threshold: int
    top_root_causes_report: int


@dataclass(frozen=True)
class DistressThresholds:
    """Distress-mode triggers. The cumulative session distress SCORE that feeds
    `high_distress_score` is produced by an injected DistressSignalScorer -- only
    the thresholds live here."""

    distress_score_red: Decimal
    distress_questions_trigger: int
    high_distress_score: Decimal


@dataclass(frozen=True)
class ConfidenceThresholds:
    """Outer-layer routing thresholds over sessions.overall_confidence_score."""

    continue_max: Decimal
    validate_min: Decimal
    validate_max: Decimal
    generate_report_min: Decimal

    def routing_state_for(self, score: Decimal) -> str:
        """Map a 0-100 confidence score to a routing_state value.

        Pure threshold lookup encoding the CONFIDENCE_* rules; it applies the
        configured thresholds, it does not compute the score (that is the
        OverallConfidenceStrategy's job).
        """
        if score >= self.generate_report_min:
            return "generate_report"
        if score >= self.validate_min:
            return "validate"
        return "continue"


# ---------------------------------------------------------------------------
# Strategy contracts for business rules NOT yet in the database
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfidenceInputs:
    """Everything the confidence formula may draw on. Fields are intentionally
    generous so a strategy can use as much or as little as its formula needs
    without changing this contract."""

    questions_answered: int
    ranked_root_cause_scores: tuple[Decimal, ...]
    flagged_category_count: int
    distress_mode: bool


@runtime_checkable
class OverallConfidenceStrategy(Protocol):
    """Computes sessions.overall_confidence_score (0-100).

    The generating formula is not defined in scoring_rules (only its routing
    thresholds are), so it is injected. No default implementation is provided;
    a deployment must supply one.
    """

    def compute(self, inputs: ConfidenceInputs) -> Decimal: ...


@runtime_checkable
class CategoryMaxScoreProvider(Protocol):
    """Supplies the maximum possible score for a diagnostic category -- the
    denominator that normalises category risk to 0..1. Not in the database yet
    (Doc 12 Part 2), so it is injected."""

    def max_score(self, category: str) -> Decimal: ...


@runtime_checkable
class DistressSignalScorer(Protocol):
    """Produces the cumulative session-level distress score compared against
    DistressThresholds.high_distress_score. The underlying scoring table
    (Doc 10) is not in the database, so this is injected."""

    def session_distress_score(self, signals: Mapping[str, object]) -> Decimal: ...


@runtime_checkable
class IndustryProbabilityStrategy(Protocol):
    """Reads a root cause's industry-adjusted probability out of
    industries.top_pain_point_weights (jsonb, shape not yet formalised), so the
    read shape is injected rather than assumed."""

    def probability(self, top_pain_point_weights: Mapping[str, object], root_cause_id: int) -> Decimal: ...


class NotImplementedOverallConfidenceStrategy:
    """Fail-closed default for the 0-100 confidence formula.

    The real formula (PRD Section 04) is a business rule that is not yet defined.
    Until it is supplied, this strategy raises rather than inventing a score --
    routing decisions must never depend on placeholder business logic. The
    orchestration is complete; it activates the moment a real strategy is
    injected in its place.
    """

    def compute(self, inputs: "ConfidenceInputs") -> Decimal:
        raise FeatureDisabledError(
            "The overall confidence formula (PRD Section 04) is not implemented; "
            "the confidence/routing feature is disabled until it is supplied."
        )


class StaticCategoryMaxScoreProvider:
    """A CategoryMaxScoreProvider backed by a supplied mapping.

    Holds no business values of its own -- the caller provides the mapping from
    config/env/DB. This is a container, not a hardcoded rule.
    """

    def __init__(self, max_scores: Mapping[str, Decimal]):
        self._max_scores = dict(max_scores)

    def max_score(self, category: str) -> Decimal:
        try:
            return self._max_scores[category]
        except KeyError:
            raise ReasoningConfigError(
                f"No maximum score configured for category {category!r}."
            )


# ---------------------------------------------------------------------------
# Aggregate config + loader
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReasoningConfig:
    """All reasoning parameters, assembled and validated.

    The value objects come from `scoring_rules`; the strategy fields are the
    injectable interfaces for rules not yet in the database. Strategies are
    optional here so the architecture is constructible before every strategy
    exists -- an engine that needs a missing strategy raises ReasoningConfigError
    at call time via `require_*`, rather than the whole config failing to build.
    """

    question_scores: QuestionScores
    confirmation_multipliers: ConfirmationMultipliers
    ranking_weights: RankingWeights
    branching: BranchingThresholds
    distress: DistressThresholds
    confidence: ConfidenceThresholds

    confidence_strategy: OverallConfidenceStrategy | None = None
    category_max_scores: CategoryMaxScoreProvider | None = None
    distress_scorer: DistressSignalScorer | None = None
    industry_probability: IndustryProbabilityStrategy | None = None

    def require_confidence_strategy(self) -> OverallConfidenceStrategy:
        if self.confidence_strategy is None:
            raise ReasoningConfigError(
                "OverallConfidenceStrategy is not configured (the 0-100 confidence "
                "formula from PRD Section 04 has not been supplied)."
            )
        return self.confidence_strategy

    def require_category_max_scores(self) -> CategoryMaxScoreProvider:
        if self.category_max_scores is None:
            raise ReasoningConfigError(
                "CategoryMaxScoreProvider is not configured (per-category maximum "
                "scores from Doc 12 Part 2 have not been supplied)."
            )
        return self.category_max_scores

    def require_distress_scorer(self) -> DistressSignalScorer:
        if self.distress_scorer is None:
            raise ReasoningConfigError(
                "DistressSignalScorer is not configured (the distress scoring "
                "table from Doc 10 has not been supplied)."
            )
        return self.distress_scorer

    def require_industry_probability(self) -> IndustryProbabilityStrategy:
        if self.industry_probability is None:
            raise ReasoningConfigError(
                "IndustryProbabilityStrategy is not configured (the read shape for "
                "industries.top_pain_point_weights has not been supplied)."
            )
        return self.industry_probability


def _require(values: Mapping[str, Decimal], code: RuleCode) -> Decimal:
    try:
        return values[code.value]
    except KeyError:
        raise ReasoningConfigError(
            f"Required scoring rule {code.value!r} is missing or inactive in "
            "scoring_rules."
        )


def build_reasoning_config(
    rule_values: Mapping[str, Decimal],
    *,
    confidence_strategy: OverallConfidenceStrategy | None = None,
    category_max_scores: CategoryMaxScoreProvider | None = None,
    distress_scorer: DistressSignalScorer | None = None,
    industry_probability: IndustryProbabilityStrategy | None = None,
) -> ReasoningConfig:
    """Assemble a validated ReasoningConfig from active scoring_rules values.

    `rule_values` maps rule_code -> rule_value for active rules (the repository
    supplies it). Missing required codes raise ReasoningConfigError; the ranking
    weights are validated against WEIGHT_FACTORS_SUM_CHECK before returning.
    """
    ranking_weights = RankingWeights(
        category_risk=_require(rule_values, RuleCode.WEIGHT_CATEGORY_RISK),
        confirmation_status=_require(rule_values, RuleCode.WEIGHT_CONFIRMATION_STATUS),
        stage_probability=_require(rule_values, RuleCode.WEIGHT_STAGE_PROBABILITY),
        industry_probability=_require(rule_values, RuleCode.WEIGHT_INDUSTRY_PROBABILITY),
        expected_sum=_require(rule_values, RuleCode.WEIGHT_FACTORS_SUM_CHECK),
    )
    ranking_weights.validate()

    config = ReasoningConfig(
        question_scores=QuestionScores(
            green=_require(rule_values, RuleCode.QUESTION_SCORE_GREEN),
            amber=_require(rule_values, RuleCode.QUESTION_SCORE_AMBER),
            red=_require(rule_values, RuleCode.QUESTION_SCORE_RED),
        ),
        confirmation_multipliers=ConfirmationMultipliers(
            confirmed=_require(rule_values, RuleCode.CONFIRMED_MULTIPLIER),
            unconfirmed=_require(rule_values, RuleCode.UNCONFIRMED_MULTIPLIER),
            not_tested=_require(rule_values, RuleCode.NOT_TESTED_MULTIPLIER),
        ),
        ranking_weights=ranking_weights,
        branching=BranchingThresholds(
            category_risk_threshold=_require(rule_values, RuleCode.CAT_RISK_THRESHOLD),
            amber_cluster_trigger=int(_require(rule_values, RuleCode.AMBER_CLUSTER_TRIGGER)),
            multi_category_flag_threshold=int(
                _require(rule_values, RuleCode.MULTI_CATEGORY_FLAG_THRESHOLD)
            ),
            top_root_causes_report=int(
                _require(rule_values, RuleCode.TOP_ROOT_CAUSES_REPORT)
            ),
        ),
        distress=DistressThresholds(
            distress_score_red=_require(rule_values, RuleCode.DISTRESS_SCORE_RED),
            distress_questions_trigger=int(
                _require(rule_values, RuleCode.DISTRESS_QUESTIONS_TRIGGER)
            ),
            high_distress_score=_require(
                rule_values, RuleCode.SESSION_STATE_HIGH_DISTRESS_THRESHOLD
            ),
        ),
        confidence=ConfidenceThresholds(
            continue_max=_require(rule_values, RuleCode.CONFIDENCE_CONTINUE_MAX),
            validate_min=_require(rule_values, RuleCode.CONFIDENCE_VALIDATE_MIN),
            validate_max=_require(rule_values, RuleCode.CONFIDENCE_VALIDATE_MAX),
            generate_report_min=_require(
                rule_values, RuleCode.CONFIDENCE_GENERATE_REPORT_MIN
            ),
        ),
        confidence_strategy=confidence_strategy,
        category_max_scores=category_max_scores,
        distress_scorer=distress_scorer,
        industry_probability=industry_probability,
    )
    return config
