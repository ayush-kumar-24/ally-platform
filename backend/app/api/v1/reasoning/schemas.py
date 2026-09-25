"""Internal data-transfer objects passed between the reasoning engines.

These are the typed contracts that flow through the pipeline; they are not (yet)
HTTP response models. Kept as frozen dataclasses -- lightweight, immutable, and
free of any serialization concern -- because they never cross the API boundary
in Step 1. A router that exposes results (later) will map these to Pydantic
response schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from app.models.enums import ConfirmationStatus, ScoreLabel
from app.services.retrieval.evidence import RetrievalEvidence


@dataclass(frozen=True)
class AnswerClassification:
    """Output of the Diagnostic Engine's Green/Amber/Red classifier for one
    answer. `score` is the numeric band value (0/1/2) resolved from config;
    `rationale` is the classifier's explanation, retained for auditability."""

    answer_id: int
    question_id: int
    label: ScoreLabel
    #: None when `label` is NOT_APPLICABLE -- that state is unscored on purpose,
    #: because zero would read as Green (positive evidence). Every consumer must
    #: filter on `label.is_scored` before touching this.
    score: Decimal | None
    is_distress_flagged: bool
    # Branching linkage, carried from the Answer so the Root Cause Engine can
    # resolve the double-red confirmation pattern without re-querying.
    is_follow_up: bool = False
    triggered_follow_up_id: int | None = None
    rationale: str | None = None
    # Full structured reasoning when produced by an LLM classifier; None for the
    # deterministic stored-score path. Additive and ignored by every downstream
    # engine -- preserved only for reports, debugging and prompt/quality
    # monitoring, so no downstream logic depends on it.
    llm_classification: "LLMClassification | None" = None


@dataclass(frozen=True)
class LLMClassification:
    """The structured output of an LLM answer classification.

    `score` is resolved from the label via the configured bands (not the model's
    arithmetic), so it stays consistent with the deterministic scoring rules; the
    model contributes the label, confidence, explanation and reasoning trail.
    """

    score_label: ScoreLabel
    score: Decimal | None        # None for NOT_APPLICABLE -- see ScoreLabel
    confidence: Decimal          # model's self-reported confidence, [0,1]
    explanation: str
    reasoning_steps: tuple[str, ...]


@dataclass(frozen=True)
class ConversationTurn:
    """One prior question/answer exchange, optional context for classification."""

    question_text: str
    answer_text: str
    score_label: ScoreLabel | None = None


@dataclass(frozen=True)
class CategoryRisk:
    """Accumulated, normalised risk for one diagnostic category."""

    category: str
    raw_score: Decimal
    max_score: Decimal
    normalised_risk: Decimal  # raw_score / max_score, 0..1
    is_flagged: bool          # normalised_risk >= CAT_RISK_THRESHOLD
    #: How many SCORED answers produced the risk above (NOT_APPLICABLE
    #: excluded, same as the numerator). Carried because risk alone cannot
    #: distinguish "asked repeatedly and healthy" from "barely asked": both
    #: come out near 0, and the report called both a strength.
    answers_count: int = 0


@dataclass(frozen=True)
class RootCauseEvidence:
    """One piece of the audit trail behind a detected root cause.

    `contribution` is this answer's additive share of the detection_score, so the
    contributions of a detection's evidence sum to its detection_score -- the
    score is never a black box. `source` marks provenance: deterministic FK
    mapping today, and later "retrieval" / "interpretation" when the enrichment
    layer appends items, without this type or the engine interface changing.
    """

    question_id: int
    answer_id: int
    score_label: ScoreLabel
    score: Decimal
    contribution: Decimal
    source: str = "question_mapping"
    # --- Phase A: evidence quality -------------------------------------------
    # Descriptive only. Nothing reads these for ranking yet; the ranking formula
    # is unchanged. They exist so the ranking layer HAS something to weigh when
    # it is changed, and so a reviewer can see why a finding was reached.
    #
    # `directness`: "direct" when the answer was given to a question mapped to
    # this root cause, "inferred" when it reached this cause some other way.
    # Only the deterministic FK mapping produces evidence today, so everything
    # from it is direct by construction.
    directness: str = "direct"
    # The diagnostic dimension this evidence touches -- the question's category.
    # Counting DISTINCT dimensions is what separates six answers about one thing
    # from six answers about six things, which a mean over evidence cannot see.
    dimension: str | None = None
    # True when the founder raised this without being asked for it. Not yet
    # produced by any code path: the deterministic engine only sees answers to
    # questions it asked. The field exists so volunteered evidence has somewhere
    # to live when extraction learns to spot it, rather than being silently
    # dropped as it is today.
    volunteered: bool = False


@dataclass(frozen=True)
class RootCauseDetection:
    """A root cause surfaced by the Root Cause Engine, with its reasoning trail.

    Produced from deterministic database mappings. `detection_score` and
    `detection_confidence` are the engine's own evidence-derived signals (both
    0..1); they are inputs to the Confidence Model, which produces the
    authoritative final_weighted_score and ranking -- these are not that.
    `contributing_factors` are human-readable tags explaining why the cause
    surfaced; downstream engines may append their own (e.g. "Stage Match").
    """

    root_cause_id: int
    category: str
    confirmation_status: ConfirmationStatus
    detection_score: Decimal       # severity of the negative evidence, 0..1
    detection_confidence: Decimal  # corroboration across all probes, 0..1
    evidence: tuple[RootCauseEvidence, ...]
    contributing_factors: tuple[str, ...]
    category_risk_score: Decimal | None = None
    # Populated only by the optional retrieval enrichment layer; empty for
    # deterministic detection. Semantic context never alters the deterministic
    # fields above -- it is purely additive supporting evidence.
    semantic_evidence: tuple[RetrievalEvidence, ...] = ()
    # --- Phase A: breadth of evidence ----------------------------------------
    # detection_score is a MEAN over negative evidence (root_cause.py), so it
    # divides breadth out: one Red scores 2/(2*1) = 1.00 and six Ambers score
    # 6/(2*6) = 0.50. That is why an isolated signal outranked six converging
    # ones for both the Vikram and the Siddharth runs.
    #
    # These two record what the mean discards. NOTHING READS THEM FOR RANKING
    # YET -- detection_score keeps its meaning and the four-factor formula is
    # untouched. This is the measurement, not the fix.
    #
    # `independent_signal_count`: how many DISTINCT diagnostic dimensions the
    # negative evidence spans. Six answers in one dimension are one signal
    # repeated; that is the Desi Protein case, where friends-and-family
    # validation shows up again and again and is still a single pattern.
    independent_signal_count: int = 0
    # `evidence_mass`: the un-normalised sum of the negative evidence scores.
    # detection_score is this divided by its own maximum, which is exactly the
    # step that loses the quantity.
    evidence_mass: Decimal = Decimal("0")
    # --- Option C: a ranking-facing risk, separate from the founder-facing one
    # `category_risk_score` above is the founder's diagnostic health model. It is
    # a MEAN over the answers in one category, so a category asked once and
    # answered Red scores the maximum 1.0 while a category asked five times
    # scores 0.5 on the same evidence. Since the adaptive interview asks MORE
    # questions where it suspects a problem, that reading penalises the engine's
    # own investigation, and it decided both live QA inversions.
    #
    # It stays exactly as it is: report flags, health bands, the
    # NO_CLEAR_DIAGNOSIS gate and every stored session value depend on it.
    #
    # `ranking_category_risk` answers a different question -- how much relevant
    # evidence did we actually collect about THIS cause -- and only the ranker
    # reads it. Two differences from the founder-facing value:
    #   * the per-category intensity is smoothed by a prior, so one question
    #     answered Red cannot reach the maximum;
    #   * it is averaged across every category this cause draws evidence from,
    #     weighted by the evidence in each, rather than borrowed whole from the
    #     single "dominant" category, which discards the rest.
    # None when no category the cause touches carries a risk, and absence is
    # recorded rather than read as zero.
    ranking_category_risk: Decimal | None = None


@dataclass(frozen=True)
class ScoreComponent:
    """One factor of the four-factor ranking formula and its contribution.

    `contribution == weight * value`, and the contributions of a ScoredRootCause
    sum to its final_weighted_score -- so the score is fully reconstructable from
    its components. `available` is False when the source datum was missing (e.g.
    the root cause has no stage weight, or no industry strategy is configured), in
    which case `value` is the neutral 0 that was used in the sum.
    """

    factor: str
    weight: Decimal
    value: Decimal
    contribution: Decimal
    available: bool = True


@dataclass(frozen=True)
class ScoredRootCause:
    """A candidate after the Confidence Model applies the four-factor formula.

    The score fields mirror the persisted columns of detected_root_causes so the
    repository can map it straight through; `components` carries the audit trail
    and is not persisted. Factor values are the ones actually used in the sum
    (neutral 0 when a source datum was absent), so a stored row reconstructs its
    own final_weighted_score.
    """

    root_cause_id: int
    category_risk_score: Decimal | None
    confirmation_status: ConfirmationStatus
    confirmation_multiplier: Decimal
    stage_probability: Decimal | None
    industry_probability: Decimal | None
    final_weighted_score: Decimal
    rank: int
    is_top_finding: bool
    components: tuple[ScoreComponent, ...] = ()


class RecommendationType(str, Enum):
    """Whether a recommendation drives action or validation.

    Derived from the confirmation status of the root cause it addresses:
    CONFIRMED causes get SOLVE recommendations (act now); UNCONFIRMED/NOT_TESTED
    get CONFIRM recommendations (validate first). This mirrors the founder_reports
    solve_actions / confirm_actions split, but the *mapping into a report* is
    report generation's job -- here it is only a property of the recommendation.
    """

    SOLVE = "solve"
    CONFIRM = "confirm"


@dataclass(frozen=True)
class Recommendation:
    """One structured recommendation for the founder.

    Selection, priority, confidence and ordering derive ONLY from the ranked
    root causes and intervention relevance -- never from semantic evidence.
    `supporting_retrieval_evidence` is additive context that enriches the
    rationale but cannot change which interventions are chosen or their order.
    """

    intervention_id: int
    recommendation_type: RecommendationType
    priority: int                       # 1 = highest; the best supporting cause's rank
    confidence: Decimal                 # from the supporting ranked cause scores, [0,1]
    supporting_root_causes: tuple[int, ...]
    supporting_retrieval_evidence: tuple[RetrievalEvidence, ...]
    rationale: str
    next_actions: tuple[str, ...]
    intervention_code: str | None = None
    section: str | None = None
    #: "library" when this came from a curated intervention row, "llm" when the
    #: library had nothing for the detected cause and a model wrote it instead.
    #:
    #: Not cosmetic. A library recommendation has been reviewed and is tied to a
    #: real intervention_id; a generated one has neither. A founder acting on
    #: advice, and anyone auditing why it was given, needs to be able to tell
    #: those apart -- and a gap in the library should be visible as a gap rather
    #: than disappearing behind prose that reads identically.
    source: str = "library"


@dataclass(frozen=True)
class RecommendationResult:
    """The Recommendation Engine's ordered output for a session."""

    recommendations: tuple[Recommendation, ...]

    @property
    def intervention_ids(self) -> tuple[int, ...]:
        return tuple(r.intervention_id for r in self.recommendations)


@dataclass(frozen=True)
class SessionAssessment:
    """Where a session stands after one answer -- what the in-loop scorer returns.

    Deliberately more than a number. The confidence score cannot distinguish
    "nothing is wrong with this founder" from "we have not found it yet": three
    of its five signals measure pathology and read 0 either way, and
    CONFIDENCE_HARD_RULES rule 4 caps an unflagged session below the validate
    threshold on top of that. Routing needs both facts, so both travel together.
    """

    score: Decimal
    #: True when at least one category is at or above CAT_RISK_THRESHOLD.
    any_category_flagged: bool
    questions_answered: int


@dataclass(frozen=True)
class ReasoningResult:
    """The full result of analysing one session -- what ReasoningService returns
    to its caller after the pipeline (and persistence) completes."""

    session_id: int
    founder_id: int
    detected_root_causes: tuple[ScoredRootCause, ...]
    overall_confidence_score: Decimal
    routing_state: str
    distress_mode: bool
    recommendations: RecommendationResult
    report_id: int | None = None


# ---------------------------------------------------------------------------
# Diagnosis Engine outputs (deterministic front of the pipeline)
# ---------------------------------------------------------------------------


class FollowUpReason(str, Enum):
    """Why the configured branching rules call for a follow-up."""

    RED_SINGLE_PROBE = "red_single_probe"     # a Red answer triggers one probe
    AMBER_CLUSTER = "amber_cluster"           # >= N Ambers in a category


@dataclass(frozen=True)
class FollowUpTrigger:
    """A branching decision the configured rules imply for a session.

    The Diagnosis Engine decides WHAT the rules trigger; actually asking the
    follow-up is the session layer's concern. In post-hoc analysis these document
    the branching that the rules call for.
    """

    reason: FollowUpReason
    question_id: int | None = None           # the answer that triggered it (red probe)
    follow_up_question_id: int | None = None  # questions.follow_up_question_id
    category: str | None = None              # the category (amber cluster)


@dataclass(frozen=True)
class StageDetection:
    """The founder's detected lifecycle stage and how strongly it is supported.

    `stage_id` plugs directly into the Confidence Model (via ReasoningContext),
    which uses it to look up stage-adjusted root-cause priors.
    """

    stage_id: int | None
    stage_name: str | None
    probability: Decimal          # likelihood this is the stage, [0,1]
    confidence: Decimal           # evidential support for the detection, [0,1]
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class SymptomDetection:
    """A detected problem symptom cluster for the session.

    Built deterministically from non-Green answers -> questions.problem_id ->
    problems.symptoms. `severity` is the normalised strength of the negative
    answers pointing at this problem.
    """

    problem_id: int
    category: str
    symptoms: tuple[str, ...]
    severity: Decimal                        # 0..1
    evidence_question_ids: tuple[int, ...]
    is_distress: bool


@dataclass(frozen=True)
class DiagnosisResult:
    """Everything the deterministic Diagnosis Engine produces for a session --
    the complete input surface the downstream reasoning pipeline needs, plus the
    audit outputs (follow-up decisions, stage, symptoms, distress)."""

    classifications: tuple[AnswerClassification, ...]
    category_risks: tuple[CategoryRisk, ...]
    follow_up_triggers: tuple[FollowUpTrigger, ...]
    stage_detection: StageDetection
    symptoms: tuple[SymptomDetection, ...]
    distress_mode: bool
    distress_signal_count: int
    unscored_answer_ids: tuple[int, ...] = ()
    #: The answers that produced distress_signal_count, so the decision can be
    #: checked against what is actually stored on those rows.
    distress_signal_answer_ids: tuple[int, ...] = ()


# ---------------------------------------------------------------------------
# Business Health Score (readiness_pillars)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PillarScore:
    """One readiness pillar's health for a session.

    `score` is 0-100 (higher = healthier), derived from the session answers mapped
    to this pillar via question -> problem.pillar_id, then inverted from risk. It
    is None when the session contained no questions for the pillar. `weight`,
    `band` and the red-flag threshold all come from the readiness_pillars row --
    none are hardcoded.
    """

    pillar_id: int
    pillar_name: str
    weight: Decimal                 # pillar_weightage from readiness_pillars
    score: Decimal | None           # 0-100 health, None if not assessed
    band: str | None                # score_bands level (e.g. "Developing")
    red_flag_triggered: bool
    red_flag_note: str | None
    assessed_question_count: int

    #: Which of this pillar's Business DNA Part 2 dimensions the founder's STAGE
    #: covers, by the document's own names, and how many the pillar has in total.
    #:
    #: Part 3 scopes several pillars partially -- Product & Execution is one of
    #: three dimensions at ideation, Revenue Maturity three of four through
    #: Stage 0->1 -- and without this the report prints the pillar's full name
    #: over a reading taken from part of it. "Product & Execution" implies the
    #: product was assessed; at ideation only its execution pace was.
    #:
    #: A property of the STAGE, not of the session: it says what the assessment
    #: covers, which is the same for every founder at that stage. Per-session
    #: coverage would need `problems.dimension_code`, still mostly NULL.
    #:
    #: Defaulted so a caller that does not resolve a scope (an unknown stage, a
    #: test fixture) gets a pillar with no coverage claim rather than a wrong one:
    #: empty names with a 0 total renders no qualifier at all.
    dimensions_in_scope: tuple[str, ...] = ()
    dimensions_total: int = 0


@dataclass(frozen=True)
class BusinessHealthScore:
    """Weighted readiness across the six pillars.

    `overall_score` is the pillar scores weighted by pillar_weightage (renormalised
    over the pillars actually assessed in the session). `band` uses the same
    score_bands. `red_flags` lists the pillars whose score fell to/below their
    configured red_flag_threshold.
    """

    overall_score: Decimal          # 0-100
    band: str | None
    pillars: tuple[PillarScore, ...]
    red_flags: tuple[str, ...]
