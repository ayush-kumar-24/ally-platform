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

import math
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
    # Detection focusing (provisional; safe defaults apply if the rows are absent).
    ROOT_CAUSE_MIN_DETECTION_CONFIDENCE = "ROOT_CAUSE_MIN_DETECTION_CONFIDENCE"
    ROOT_CAUSE_MAX_CANDIDATES = "ROOT_CAUSE_MAX_CANDIDATES"

    DISTRESS_SCORE_RED = "DISTRESS_SCORE_RED"
    DISTRESS_QUESTIONS_TRIGGER = "DISTRESS_QUESTIONS_TRIGGER"
    SESSION_STATE_HIGH_DISTRESS_THRESHOLD = "SESSION_STATE_HIGH_DISTRESS_THRESHOLD"

    CONFIDENCE_CONTINUE_MAX = "CONFIDENCE_CONTINUE_MAX"
    CONFIDENCE_VALIDATE_MIN = "CONFIDENCE_VALIDATE_MIN"
    CONFIDENCE_VALIDATE_MAX = "CONFIDENCE_VALIDATE_MAX"
    CONFIDENCE_GENERATE_REPORT_MIN = "CONFIDENCE_GENERATE_REPORT_MIN"

    # Overall-confidence methodology (CONFIDENCE_SCORE_METHODOLOGY). The five
    # evidence-signal weights must sum to CONFIDENCE_INTEGRITY_WEIGHTS_SUM (1.0).
    # They are selected by explicit code -- NOT by a CONFIDENCE_WEIGHT_% prefix --
    # because "_" is a single-char wildcard in SQL LIKE and would also match the
    # integrity row, inflating the sum against valid data.
    CONFIDENCE_WEIGHT_CATEGORY_SIGNAL = "CONFIDENCE_WEIGHT_CATEGORY_SIGNAL"
    CONFIDENCE_WEIGHT_COVERAGE = "CONFIDENCE_WEIGHT_COVERAGE"
    CONFIDENCE_WEIGHT_CONSISTENCY = "CONFIDENCE_WEIGHT_CONSISTENCY"
    CONFIDENCE_WEIGHT_CONFIRMATION = "CONFIDENCE_WEIGHT_CONFIRMATION"
    CONFIDENCE_WEIGHT_SEPARATION = "CONFIDENCE_WEIGHT_SEPARATION"
    CONFIDENCE_INTEGRITY_WEIGHTS_SUM = "CONFIDENCE_INTEGRITY_WEIGHTS_SUM"
    CONFIDENCE_STAGE_COHERENCE_FACTOR = "CONFIDENCE_STAGE_COHERENCE_FACTOR"
    CONFIDENCE_MIN_QUESTIONS_FLOOR = "CONFIDENCE_MIN_QUESTIONS_FLOOR"

    # Fraction of the stage's question budget that must be answered, with no
    # category flagged, before the diagnosis may stop and report "areas to
    # monitor" instead of a diagnosis (NO_CATEGORY_ABOVE_THRESHOLD_ACTION).
    MONITOR_MIN_COVERAGE = "MONITOR_MIN_COVERAGE"

    # Minimum number of the five confidence signals that must be measurable for
    # the score to mean anything. The rule text describes the exclude-and-
    # renormalise contract; its rule_value is this floor.
    CONFIDENCE_UNAVAILABLE_INPUT_HANDLING = "CONFIDENCE_UNAVAILABLE_INPUT_HANDLING"


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
class ConfidenceScoreWeights:
    """The five evidence-signal weights of the overall-confidence base score.

    From CONFIDENCE_WEIGHT_CATEGORY_SIGNAL / _COVERAGE / _CONSISTENCY /
    _CONFIRMATION / _SEPARATION. Validated to sum to `expected_sum`
    (CONFIDENCE_INTEGRITY_WEIGHTS_SUM, normally 1.0) before any scoring runs --
    the same fail-closed guard RankingWeights applies to the ranking weights.
    """

    category_signal: Decimal
    coverage: Decimal
    consistency: Decimal
    confirmation: Decimal
    separation: Decimal
    expected_sum: Decimal = Decimal("1")

    def validate(self) -> None:
        total = (
            self.category_signal
            + self.coverage
            + self.consistency
            + self.confirmation
            + self.separation
        )
        if abs(total - self.expected_sum) > _WEIGHT_SUM_TOLERANCE:
            raise ReasoningConfigError(
                f"Confidence weights sum to {total}, expected {self.expected_sum} "
                "(CONFIDENCE_INTEGRITY_WEIGHTS_SUM). Adjust the scoring_rules so the "
                "five confidence weight factors sum to exactly the check value."
            )


@dataclass(frozen=True)
class BranchingThresholds:
    """Inner-layer branching parameters."""

    category_risk_threshold: Decimal  # fraction of category max that flags deep-dive
    amber_cluster_trigger: int
    multi_category_flag_threshold: int
    top_root_causes_report: int
    # Detection focusing: admit a candidate root cause only when its corroboration
    # (detection_confidence) reaches this floor, then keep at most this many
    # candidates. Stops a long tail of single-weak-signal causes (sessions were
    # surfacing up to 35). Provisional -- pending product sign-off.
    root_cause_min_detection_confidence: Decimal = Decimal("0")
    root_cause_max_candidates: int = 0  # 0 = no cap


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


#: Coverage required for the monitor route when MONITOR_MIN_COVERAGE is not
#: seeded. Three quarters of the stage budget. The DB row overrides it; this is
#: the empty-database fallback, not the business rule -- the `_optional`
#: convention used for every other provisional threshold here.
DEFAULT_MONITOR_MIN_COVERAGE = Decimal("0.75")


def monitor_eligible(
    *,
    any_category_flagged: bool,
    answered: int,
    budget: int,
    min_coverage: Decimal,
    min_answers: int,
) -> bool:
    """May this session stop and report "areas to monitor" instead of a diagnosis?

    The second half of NO_CATEGORY_ABOVE_THRESHOLD_ACTION. That rule says not to
    force a diagnosis when nothing is flagged; it never said when to stop asking,
    so a healthy founder ran to the end of their budget and completed carrying
    `continue`.

    Pure arithmetic on values the caller resolves, because TWO callers decide
    this and must never disagree:

      * `incremental_confidence.recompute` -- the in-loop decision, after each
        answer, that ends the session.
      * `ReasoningService._run_pipeline` -- the final pass, which recomputes
        routing from the full signal set and would otherwise overwrite the
        session's `monitor` with `continue` off the same low score.

    Two copies of this condition in two packages is exactly how they drift, and
    the drift would be invisible: the session would stop correctly and then be
    silently relabelled by the pipeline that runs a moment later.

    `min_coverage` is deliberately a high fraction, not the report floor. An
    all-clear is a stronger claim than a diagnosis -- nothing downstream reopens
    it -- so it takes more evidence, not less. `min_answers` still applies on top;
    whichever binds harder wins.
    """
    if any_category_flagged:
        return False
    if answered < min_answers:
        return False
    required = math.ceil(Decimal(budget) * min_coverage)
    return answered >= required


# ---------------------------------------------------------------------------
# Strategy contracts for business rules NOT yet in the database
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfidenceInputs:
    """Resolved inputs to the overall-confidence formula for one session.

    Every field is pre-computed by the caller (the confidence model's assembler,
    which owns the DB access) so a strategy's `compute` is a pure function of
    these values plus its DB-loaded weights. The five evidence signals are each
    normalised to 0..1; the reliability factor and hard-rule facts follow.
    """

    # --- Five evidence signals (each 0..1), per CONFIDENCE_SCORE_METHODOLOGY ---
    category_signal: Decimal        # (a) strongest category risk, max(normalised_risk)
    evidence_coverage: Decimal      # (b) answered / in-scope questions, capped 1.0
    confirmation_ratio: Decimal     # (d) top causes' confirmation, rescaled to 0..1
    separation: Decimal             # (e) (top - second) / top of ranked scores

    # (c) ANSWER CONSISTENCY. Availability is explicit rather than encoded in the
    # number: `consistency_available` is False while the LLM contradiction detector
    # is unimplemented, and `consistency_score` is the measured 0..1 value only when
    # it is True. An unmeasured signal is excluded from the weighted average (and
    # the other weights renormalised), never defaulted to a perfect 1.0.
    consistency_available: bool
    consistency_score: Decimal | None


    # --- Reliability modifier (from session_state_bands); None = High Distress ---
    reliability_factor: Decimal | None

    # --- Facts the six hard rules evaluate before routing ---
    questions_answered: int         # rule 3: minimum question floor
    flagged_category_count: int     # rule 5: multi-category cross-check
    any_category_flagged: bool      # rule 4: no category above threshold
    distress_override: bool         # rule 1: distress path
    stages_away: int | None         # rule 2: severe stage mismatch (>= 2)

    # Availability for the other four signals, same contract as consistency above
    # and required by the same rule -- CONFIDENCE_UNAVAILABLE_INPUT_HANDLING says
    # explicitly that it "applies to all five inputs, not only Answer Consistency".
    #
    # These default True so every existing caller keeps today's behaviour; only a
    # signal the assembler positively knows it could not measure sets one False.
    #
    # The rule names three states and they are NOT the same. An input that RAN and
    # found nothing wrong is a genuine measurement and keeps its value. An input
    # whose calculation had no data to run on, or that errored, is UNAVAILABLE and
    # must be excluded so the remaining weights renormalise -- never scored 0.
    # Confirmation and separation both used to return 0 with no ranked cause,
    # which is the forbidden case: it reads as "we checked and found nothing to
    # confirm" when the truth is that there was nothing to check.
    category_signal_available: bool = True
    confirmation_available: bool = True
    separation_available: bool = True


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


def require_rule_value(values: Mapping[str, Decimal], code: RuleCode) -> Decimal:
    """Fetch one active rule value or fail closed. Public so the composition root
    can load rules for the confidence strategy without reaching into internals."""
    try:
        return values[code.value]
    except KeyError:
        raise ReasoningConfigError(
            f"Required scoring rule {code.value!r} is missing or inactive in "
            "scoring_rules."
        )


def _require(values: Mapping[str, Decimal], code: RuleCode) -> Decimal:
    return require_rule_value(values, code)


def _optional(values: Mapping[str, Decimal], code: RuleCode, default: Decimal) -> Decimal:
    """Like _require but returns `default` when the rule is absent/inactive. For
    provisional rules that may not yet exist in scoring_rules -- the default is a
    safe fallback, and the DB row (once present) overrides it. Never a hardcoded
    business rule: the value is externalised, this is only the empty-DB fallback."""
    return values.get(code.value, default)


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
            root_cause_min_detection_confidence=_optional(
                rule_values, RuleCode.ROOT_CAUSE_MIN_DETECTION_CONFIDENCE, Decimal("0.20")
            ),
            root_cause_max_candidates=int(
                _optional(rule_values, RuleCode.ROOT_CAUSE_MAX_CANDIDATES, Decimal("8"))
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
