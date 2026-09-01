"""Dependency injection for the reasoning layer.

Assembles a ReasoningService from a request-scoped DB session: loads the
configuration from scoring_rules, resolves the LLM provider by name, and wires
the engines. These are FastAPI dependencies, ready for the integration step that
triggers reasoning on session completion -- no route consumes them yet.

The injectable strategies for business rules not yet in the database (confidence
formula, category maxima, distress scorer, industry-probability shape) are left
unset here; an engine that needs one raises ReasoningConfigError at call time via
`ReasoningConfig.require_*`. Nothing is hardcoded to fill the gap.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from collections.abc import Mapping
from decimal import Decimal

from app.api.v1.reasoning.config import (
    ConfidenceScoreWeights,
    OverallConfidenceStrategy,
    ReasoningConfig,
    RuleCode,
    build_reasoning_config,
    require_rule_value,
)
from app.api.v1.reasoning.engines import (
    ConfidenceScoreStrategy,
    DeterministicDiagnosisEngine,
    LLMAnswerClassifier,
    StageDetector,
    StandardDiagnosticEngine,
    StandardRecommendationEngine,
    StandardRootCauseEngine,
    StoredFirstAnswerClassifier,
    StoredScoreAnswerClassifier,
    SymptomDetector,
    WeightedConfidenceModel,
)
from app.api.v1.ally.memory.sql_repository import build_db_memory_service
from app.api.v1.reasoning.engines.consistency import LLMConsistencyDetector
from app.api.v1.reasoning.engines.distress_language import LLMDistressDetector
from app.api.v1.reasoning.engines.psychological_state import PsychologicalStateSignalScorer
from app.api.v1.reasoning.enrichment import RetrievalRootCauseEnricher
from app.api.v1.reasoning.interfaces import AnswerClassifier, RootCauseEnricher
from app.api.v1.reasoning.engines.archetype import ArchetypeEngine
from app.api.v1.reasoning.repository import ReasoningRepository
from app.api.v1.reasoning.service import ReasoningService
from app.core.config import settings
from app.db.session import get_db
from app.services import embeddings
from app.services.llm import LLMTask, get_provider, provider_for_task
from app.services.retrieval import RetrievalEngine


def get_reasoning_repository(db: Session = Depends(get_db)) -> ReasoningRepository:
    return ReasoningRepository(db)


def build_confidence_strategy(
    rule_values: Mapping[str, Decimal],
) -> OverallConfidenceStrategy:
    """Construct the overall-confidence strategy from scoring_rules.

    Every weight, factor and threshold is read from the database here -- the
    strategy holds no literal business values. The five evidence weights are
    selected by explicit code (never a CONFIDENCE_WEIGHT_% prefix) and validated to
    sum to CONFIDENCE_INTEGRITY_WEIGHTS_SUM inside the strategy's constructor.
    """
    weights = ConfidenceScoreWeights(
        category_signal=require_rule_value(rule_values, RuleCode.CONFIDENCE_WEIGHT_CATEGORY_SIGNAL),
        coverage=require_rule_value(rule_values, RuleCode.CONFIDENCE_WEIGHT_COVERAGE),
        consistency=require_rule_value(rule_values, RuleCode.CONFIDENCE_WEIGHT_CONSISTENCY),
        confirmation=require_rule_value(rule_values, RuleCode.CONFIDENCE_WEIGHT_CONFIRMATION),
        separation=require_rule_value(rule_values, RuleCode.CONFIDENCE_WEIGHT_SEPARATION),
        expected_sum=require_rule_value(rule_values, RuleCode.CONFIDENCE_INTEGRITY_WEIGHTS_SUM),
    )
    return ConfidenceScoreStrategy(
        weights=weights,
        stage_coherence_factor=require_rule_value(
            rule_values, RuleCode.CONFIDENCE_STAGE_COHERENCE_FACTOR
        ),
        min_questions_floor=int(
            require_rule_value(rule_values, RuleCode.CONFIDENCE_MIN_QUESTIONS_FLOOR)
        ),
        multi_category_flag_threshold=int(
            require_rule_value(rule_values, RuleCode.MULTI_CATEGORY_FLAG_THRESHOLD)
        ),
        # Optional, not required: this row may be absent on an older database, and
        # the strategy's own default (3) is the documented value. A missing rule
        # must not stop every diagnosis from scoring.
        min_measurable_inputs=int(
            rule_values.get(RuleCode.CONFIDENCE_UNAVAILABLE_INPUT_HANDLING.value, 3)
        ),
        continue_max=require_rule_value(rule_values, RuleCode.CONFIDENCE_CONTINUE_MAX),
        generate_report_min=require_rule_value(
            rule_values, RuleCode.CONFIDENCE_GENERATE_REPORT_MIN
        ),
    )


def get_reasoning_config(
    repository: ReasoningRepository = Depends(get_reasoning_repository),
) -> ReasoningConfig:
    """Load and validate reasoning config from the active scoring_rules.

    Rebuilt per request for now (a small, indexed read). If this becomes hot, it
    is safe to cache with invalidation on scoring_rules change -- the values are
    configuration, not per-session data.
    """
    rule_values = repository.get_active_rule_values()
    return build_reasoning_config(
        rule_values, confidence_strategy=build_confidence_strategy(rule_values)
    )


def get_answer_classifier(db: Session | None = None) -> AnswerClassifier:
    """Select the active answer classifier from configuration.

    ANSWER_CLASSIFIER="llm" activates the provider-driven classifier (model chosen
    by DB task->model routing for `answer_interpretation`, with the deterministic
    stored-score classifier as its runtime fallback); anything else uses the
    deterministic classifier directly. Falls back to deterministic when no db is
    available to resolve routing.

    In the "llm" case the provider classifier is wrapped in
    StoredFirstAnswerClassifier, so an answer the submit-time advisor already
    scored is read rather than re-derived. Without that wrapper, running
    ADAPTIVE_QUESTIONS=true alongside ANSWER_CLASSIFIER=llm -- which is what this
    deployment actually runs -- paid for thirty provider calls per diagnosis to
    recompute labels already stored on the rows. See the wrapper's own docstring;
    it is the 161s of the 203s pipeline.

    Note the two fallbacks are not redundant. StoredFirstAnswerClassifier decides
    what to do BEFORE calling out (stored label present -> never call the
    provider); LLMAnswerClassifier's own `fallback` decides what to do AFTER a
    call has failed all its retries. Only the second can be reached now, and only
    for answers that had no stored band to begin with -- so in practice it raises
    LLMClassificationError, which is correct: an unscored answer whose
    classification failed has no band to fall back to.
    """
    if settings.ANSWER_CLASSIFIER == "llm" and db is not None:
        return StoredFirstAnswerClassifier(
            stored=StoredScoreAnswerClassifier(),
            fallback=LLMAnswerClassifier(
                provider_for_task(db, LLMTask.ANSWER_INTERPRETATION),
                fallback=StoredScoreAnswerClassifier(),
                max_retries=settings.LLM_CLASSIFIER_MAX_RETRIES,
                timeout_seconds=settings.LLM_CLASSIFIER_TIMEOUT_SECONDS,
                temperature=settings.LLM_CLASSIFIER_TEMPERATURE,
            ),
        )
    return StoredScoreAnswerClassifier()


def get_diagnosis_engine(
    db: Session = Depends(get_db),
    repository: ReasoningRepository = Depends(get_reasoning_repository),
) -> DeterministicDiagnosisEngine:
    return DeterministicDiagnosisEngine(
        category_engine=StandardDiagnosticEngine(get_answer_classifier(db)),
        stage_detector=build_stage_detector(db, repository),
        symptom_detector=SymptomDetector(repository),
    )


def _build_enricher(
    db: Session, repository: ReasoningRepository
) -> RootCauseEnricher | None:
    """Build the retrieval enricher, or None when retrieval is disabled.

    Returning None keeps the Root Cause Engine fully deterministic -- the default
    path. When enabled, an unregistered embedding provider fails loudly via the
    registry rather than silently skipping enrichment.
    """
    if not settings.RETRIEVAL_ENABLED:
        return None
    provider = embeddings.get_provider(settings.EMBEDDING_PROVIDER)
    engine = RetrievalEngine(
        db, provider, expected_dimension=settings.EMBEDDING_DIMENSION
    )
    return RetrievalRootCauseEnricher(
        engine,
        repository,
        top_k=settings.RETRIEVAL_TOP_K,
        min_similarity=settings.RETRIEVAL_MIN_SIMILARITY,
    )


def get_root_cause_enricher(
    db: Session = Depends(get_db),
    repository: ReasoningRepository = Depends(get_reasoning_repository),
) -> RootCauseEnricher | None:
    return _build_enricher(db, repository)


def build_reasoning_service(db: Session) -> ReasoningService:
    """Construct a fully-wired ReasoningService from a DB session.

    The single assembly point used by both the FastAPI dependency and the inline
    completion trigger, so both stay identical.
    """
    repository = ReasoningRepository(db)
    # Overall confidence uses the approved CONFIDENCE_SCORE_METHODOLOGY, with every
    # weight and factor loaded from scoring_rules (never hardcoded).
    rule_values = repository.get_active_rule_values()
    config = build_reasoning_config(
        rule_values,
        confidence_strategy=build_confidence_strategy(rule_values),
        # Distress scoring is now implemented (Doc-10 tables), replacing the
        # fail-closed stub. The named PsychologicalStateEngine in the service
        # uses the same scorer to compute sessions.session_distress_score.
        distress_scorer=PsychologicalStateSignalScorer(repository),
    )
    diagnosis_engine = DeterministicDiagnosisEngine(
        category_engine=StandardDiagnosticEngine(get_answer_classifier(db)),
        stage_detector=build_stage_detector(db, repository),
        symptom_detector=SymptomDetector(repository),
    )
    return ReasoningService(
        db=db,
        repository=repository,
        config=config,
        diagnosis_engine=diagnosis_engine,
        root_cause_engine=StandardRootCauseEngine(
            repository, enricher=_build_enricher(db, repository)
        ),
        confidence_model=WeightedConfidenceModel(repository),
        recommendation_engine=StandardRecommendationEngine(
            repository, llm_fallback=_build_recommendation_fallback(db)
        ),
        retrieval_enabled=settings.RETRIEVAL_ENABLED,
        consistency_detector=_build_consistency_detector(db),
        distress_detector=_build_distress_detector(db, repository),
        # Records the completed diagnosis into founder memory (best-effort, see
        # ReasoningService._record_diagnosis_memory) so chat's memory_summary
        # block carries it too, not only the session-scoped AllyContext.diagnosis.
        memory=build_db_memory_service(db),
        archetype_engine=build_archetype_engine(db, repository),
        action_plan_balancer=_build_action_plan_balancer(db),
    )


def _build_consistency_detector(db: Session):
    """LLM answer-consistency detector (answer_consistency task), or None when off.
    None keeps the confidence score on its prior four-input renormalised path."""
    if not settings.ANSWER_CONSISTENCY_LLM:
        return None
    return LLMConsistencyDetector(
        provider_for_task(db, LLMTask.ANSWER_CONSISTENCY),
        timeout_seconds=settings.LLM_CLASSIFIER_TIMEOUT_SECONDS,
    )


def _build_distress_detector(db: Session, repository: ReasoningRepository):
    """LLM distress language detector (distress_detection task), or None when off.
    None keeps the deterministic distress proxy. The catalogue is loaded once here."""
    if not settings.DISTRESS_LLM:
        return None
    return LLMDistressDetector(
        provider_for_task(db, LLMTask.DISTRESS_DETECTION),
        repository.get_distress_signals_catalog(),
        timeout_seconds=settings.LLM_CLASSIFIER_TIMEOUT_SECONDS,
    )


def get_reasoning_service(db: Session = Depends(get_db)) -> ReasoningService:
    return build_reasoning_service(db)


def _build_recommendation_fallback(db: Session):
    """LLM gap-filler for root causes the intervention library does not cover, or
    None when off. None restores the prior behaviour exactly: an uncovered cause
    yields no recommendation.

    Gated on RECOMMENDATION_FALLBACK_LLM rather than sharing a diagnosis flag.
    This one writes advice a founder reads and acts on, with no reviewed
    intervention behind it -- it deserves its own switch, so it can be turned off
    without also disabling answer classification or distress detection.
    """
    if not settings.RECOMMENDATION_FALLBACK_LLM:
        return None
    from app.api.v1.reasoning.engines.recommendation_llm import LLMRecommendationFallback
    return LLMRecommendationFallback(
        provider_for_task(db, LLMTask.DIAGNOSIS_REASONING),
    )


def _build_action_plan_balancer(db: Session):
    """Fills the empty half of the free report's 3+3 plan, or None when off.

    None is exactly today's behaviour: the report ships whatever the curated
    library produced, which for a single diagnosed root cause is all-confirm or
    all-solve. Its own flag for the same reason the gap-filler above has one --
    it writes advice a founder reads with no reviewed intervention behind it.
    """
    if not settings.ACTION_PLAN_BALANCE_LLM:
        return None
    from app.api.v1.reasoning.engines.action_plan_llm import LLMActionPlanBalancer
    return LLMActionPlanBalancer(
        provider_for_task(db, LLMTask.DIAGNOSIS_REASONING),
    )


def build_stage_detector(db: Session, repository: ReasoningRepository) -> StageDetector:
    """LLM stage inference when STAGE_INFERENCE_LLM is on, declared-only otherwise.

    Both satisfy the same StageDetectionStrategy shape, so DeterministicDiagnosisEngine
    is unchanged either way, and the LLM path keeps DeclaredStageStrategy as the
    thing it defers to -- a declared stage is never inferred over, and every
    inference failure lands back on exactly today's answer.

    Reuses DIAGNOSIS_REASONING rather than introducing a new LLMTask, matching
    build_recommendation_fallback: a new task value needs a model_task_routing
    row to exist before it resolves, and adding one here would make this fail
    for a reason unrelated to what it does.
    """
    if not settings.STAGE_INFERENCE_LLM:
        return StageDetector(repository)
    from app.api.v1.reasoning.engines.stage_detection_llm import LLMStageInferenceStrategy
    return StageDetector(
        repository,
        strategy=LLMStageInferenceStrategy(
            provider_for_task(db, LLMTask.DIAGNOSIS_REASONING)
        ),
    )


def build_archetype_engine(db: Session, repository: ReasoningRepository):
    """LLM archetype assignment when ARCHETYPE_LLM is on, deterministic otherwise.

    Both satisfy the same `assign(answer_texts) -> ArchetypeMatch | None` shape,
    so ReasoningService is unchanged either way, and the LLM path keeps the
    deterministic engine as its fallback rather than replacing it.
    """
    deterministic = ArchetypeEngine(repository)
    if not settings.ARCHETYPE_LLM:
        return deterministic
    from app.api.v1.reasoning.engines.archetype_llm import LLMArchetypeAssigner
    return LLMArchetypeAssigner(
        provider_for_task(db, LLMTask.ARCHETYPE_ASSIGNMENT),
        fallback=deterministic,
    )


def build_reasoning_service_for_scoring(db: Session) -> ReasoningService:
    """A ReasoningService for scoring a session mid-diagnosis, not reporting on it.

    Differs from the full service in exactly one way that matters, and it is the
    difference between this being free and being unaffordable: the answer
    classifier is the STORED one, never the LLM.

    classify_answers() re-classifies every answer it is handed, with no reuse
    check. Scoring after each answer hands it the whole history, so with the LLM
    classifier a 30-question diagnosis would make 1+2+...+30 = 465 classification
    calls instead of 30 -- roughly fifteen times the cost, and seconds of latency
    added to every answer. Each answer's label is already persisted to
    answers.score_label when it is first submitted, so re-reading it is both
    cheaper and more consistent: the score cannot drift because the model
    happened to classify the same answer differently on a later pass.

    The enricher, recommendation engine, consistency and distress detectors and
    memory are all omitted -- score_only never reaches them.
    """
    repository = ReasoningRepository(db)
    rule_values = repository.get_active_rule_values()
    config = build_reasoning_config(
        rule_values, confidence_strategy=build_confidence_strategy(rule_values)
    )
    return ReasoningService(
        db=db,
        repository=repository,
        config=config,
        diagnosis_engine=DeterministicDiagnosisEngine(
            category_engine=StandardDiagnosticEngine(StoredScoreAnswerClassifier()),
            stage_detector=StageDetector(repository),
            symptom_detector=SymptomDetector(repository),
        ),
        root_cause_engine=StandardRootCauseEngine(repository),   # no enrichment
        confidence_model=WeightedConfidenceModel(repository),
        recommendation_engine=StandardRecommendationEngine(repository),
        retrieval_enabled=False,
    )
