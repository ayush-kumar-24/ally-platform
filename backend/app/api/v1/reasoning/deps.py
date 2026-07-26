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

from app.api.v1.reasoning.config import (
    NotImplementedOverallConfidenceStrategy,
    ReasoningConfig,
    build_reasoning_config,
)
from app.api.v1.reasoning.engines import (
    DeterministicDiagnosisEngine,
    LLMAnswerClassifier,
    StageDetector,
    StandardDiagnosticEngine,
    StandardRecommendationEngine,
    StandardRootCauseEngine,
    StoredScoreAnswerClassifier,
    SymptomDetector,
    WeightedConfidenceModel,
)
from app.api.v1.reasoning.enrichment import RetrievalRootCauseEnricher
from app.api.v1.reasoning.interfaces import AnswerClassifier, RootCauseEnricher
from app.api.v1.reasoning.repository import ReasoningRepository
from app.api.v1.reasoning.service import ReasoningService
from app.core.config import settings
from app.db.session import get_db
from app.services import embeddings
from app.services.llm import get_provider
from app.services.retrieval import RetrievalEngine


def get_reasoning_repository(db: Session = Depends(get_db)) -> ReasoningRepository:
    return ReasoningRepository(db)


def get_reasoning_config(
    repository: ReasoningRepository = Depends(get_reasoning_repository),
) -> ReasoningConfig:
    """Load and validate reasoning config from the active scoring_rules.

    Rebuilt per request for now (a small, indexed read). If this becomes hot, it
    is safe to cache with invalidation on scoring_rules change -- the values are
    configuration, not per-session data.
    """
    return build_reasoning_config(repository.get_active_rule_values())


def get_answer_classifier() -> AnswerClassifier:
    """Select the active answer classifier from configuration.

    ANSWER_CLASSIFIER="llm" activates the provider-driven classifier (with the
    deterministic stored-score classifier as its runtime fallback); anything else
    uses the deterministic classifier directly. Default is deterministic, so the
    pipeline needs no LLM provider.
    """
    if settings.ANSWER_CLASSIFIER == "llm":
        return LLMAnswerClassifier(
            get_provider(settings.LLM_PROVIDER),
            fallback=StoredScoreAnswerClassifier(),
            max_retries=settings.LLM_CLASSIFIER_MAX_RETRIES,
            timeout_seconds=settings.LLM_CLASSIFIER_TIMEOUT_SECONDS,
            temperature=settings.LLM_CLASSIFIER_TEMPERATURE,
        )
    return StoredScoreAnswerClassifier()


def get_diagnosis_engine(
    repository: ReasoningRepository = Depends(get_reasoning_repository),
) -> DeterministicDiagnosisEngine:
    return DeterministicDiagnosisEngine(
        category_engine=StandardDiagnosticEngine(get_answer_classifier()),
        stage_detector=StageDetector(repository),
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
    # The overall-confidence formula (PRD Section 04) is not implemented; the
    # fail-closed strategy raises rather than routing on placeholder logic. Swap
    # it for the real strategy to enable confidence/routing.
    config = build_reasoning_config(
        repository.get_active_rule_values(),
        confidence_strategy=NotImplementedOverallConfidenceStrategy(),
    )
    diagnosis_engine = DeterministicDiagnosisEngine(
        category_engine=StandardDiagnosticEngine(get_answer_classifier()),
        stage_detector=StageDetector(repository),
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
        recommendation_engine=StandardRecommendationEngine(repository),
        retrieval_enabled=settings.RETRIEVAL_ENABLED,
    )


def get_reasoning_service(db: Session = Depends(get_db)) -> ReasoningService:
    return build_reasoning_service(db)
