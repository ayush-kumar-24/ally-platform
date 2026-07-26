"""Abstract contracts for the reasoning engines.

Each engine is defined here as an ABC: the orchestrator, the DI layer, and the
tests all depend on these interfaces, never on a concrete engine. Concrete
engines (in engines/*.py) subclass these; their algorithm bodies are filled in
their own approved steps.

Method signatures use the DTOs from schemas.py and the parameters from config.py
so the data contracts are pinned now, before any algorithm exists.
"""

from __future__ import annotations

import abc
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.api.v1.reasoning.config import ConfidenceInputs, ReasoningConfig
from app.api.v1.reasoning.schemas import (
    AnswerClassification,
    CategoryRisk,
    ConversationTurn,
    FollowUpTrigger,
    RecommendationResult,
    RootCauseDetection,
    ScoredRootCause,
)
from app.services.retrieval.evidence import RetrievalEvidence
from app.models.diagnosis import Answer, DiagnosisSession, Founder, Question


@dataclass(frozen=True)
class ReasoningContext:
    """Read-only per-session context every engine may need. Assembled once by the
    orchestrator so engines never re-query it."""

    session: DiagnosisSession
    founder: Founder
    config: ReasoningConfig
    stage_id: int | None
    industry_id: int | None


class AnswerClassifier(abc.ABC):
    """Turns a founder's free-text answer into a Green/Amber/Red classification.

    The concrete classifier delegates the judgement to an injected
    `LLMProvider`, so the model vendor is never fixed here. Async because the
    underlying provider call is network I/O.
    """

    @abc.abstractmethod
    async def classify(
        self,
        answer: Answer,
        question: Question,
        context: ReasoningContext,
        *,
        previous_conversation: Sequence[ConversationTurn] | None = None,
    ) -> AnswerClassification:
        raise NotImplementedError


class DiagnosticEngine(abc.ABC):
    """Inner layer: score every answer, accumulate category risk, and detect
    distress. Owns the adaptive-branching interpretation of the scores."""

    @abc.abstractmethod
    async def classify_answers(
        self,
        answers: list[Answer],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> list[AnswerClassification]:
        raise NotImplementedError

    @abc.abstractmethod
    def compute_category_risks(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> list[CategoryRisk]:
        raise NotImplementedError

    @abc.abstractmethod
    def follow_up_triggers(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> list[FollowUpTrigger]:
        raise NotImplementedError

    @abc.abstractmethod
    def distress_signal_count(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def is_distress_mode(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> bool:
        raise NotImplementedError


@runtime_checkable
class RootCauseEnricher(Protocol):
    """Optional post-detection enhancement layer.

    The Retrieval Engine will implement this later to add semantic evidence,
    similar cases, and supporting context to already-detected candidates. It
    takes detections and returns detections, so enrichment plugs in without
    changing the RootCauseEngine.detect signature. Deterministic detection never
    depends on it; it can only enrich what deterministic mapping already found.
    """

    def enrich(
        self,
        detections: list[RootCauseDetection],
        context: "ReasoningContext",
    ) -> list[RootCauseDetection]: ...


class RootCauseEngine(abc.ABC):
    """Maps scored answers and flagged categories to candidate root causes and
    assigns each a confirmation status, with a traceable evidence trail."""

    @abc.abstractmethod
    def detect(
        self,
        classifications: list[AnswerClassification],
        category_risks: list[CategoryRisk],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> list[RootCauseDetection]:
        raise NotImplementedError


class ConfidenceModel(abc.ABC):
    """Applies the four-factor ranking formula to candidates and computes the
    outer-layer session confidence score."""

    @abc.abstractmethod
    def score_and_rank(
        self,
        detections: list[RootCauseDetection],
        context: ReasoningContext,
    ) -> list[ScoredRootCause]:
        raise NotImplementedError

    @abc.abstractmethod
    def overall_confidence(
        self,
        inputs: ConfidenceInputs,
        context: ReasoningContext,
    ) -> Decimal:
        raise NotImplementedError


class RecommendationEngine(abc.ABC):
    """Selects and ranks interventions for the ranked root causes.

    `semantic_evidence` (root_cause_id -> retrieval hits) is optional additive
    context; the contract is that it may enrich recommendations but must never
    change which interventions are selected or their order.
    """

    @abc.abstractmethod
    def recommend(
        self,
        ranked_root_causes: list[ScoredRootCause],
        context: ReasoningContext,
        *,
        semantic_evidence: Mapping[int, Sequence[RetrievalEvidence]] | None = None,
    ) -> RecommendationResult:
        raise NotImplementedError
