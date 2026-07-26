"""Founder stage detection -- deterministic, database-backed.

The declared stage (session.founder_stage_id, else founder.stage_id) is the
deterministic basis. Criteria-based inference from founder_stages.min_criteria is
a business rule whose per-criterion comparison semantics are not yet specified, so
it is left as an injectable StageDetectionStrategy rather than guessed.

The default strategy reports the declared stage, and derives a confidence from how
well the answered questions' primary_stage_group corroborates it. The output plugs
straight into the Confidence Model, which uses stage_id to fetch stage-adjusted
root-cause priors.
"""

from __future__ import annotations

from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol, runtime_checkable

from app.api.v1.reasoning.interfaces import ReasoningContext
from app.api.v1.reasoning.repository import ReasoningRepository
from app.api.v1.reasoning.schemas import AnswerClassification, StageDetection
from app.models.diagnosis import Question

_QUANT = Decimal("0.0001")
_ONE = Decimal("1")
_ZERO = Decimal("0")

# stage_order -> primary_stage_group bucket. A documented heuristic (founder_stages
# has no group column); the single source of truth for the reasoning layer.
_STAGE_ORDER_GROUP_BOUNDS: tuple[tuple[int, str], ...] = (
    (2, "Stage 0"),
    (4, "Stage 0→1"),
    (8, "Stage 1→10+"),
)


def _group_for_stage_order(stage_order: int) -> str:
    for max_order, group in _STAGE_ORDER_GROUP_BOUNDS:
        if stage_order <= max_order:
            return group
    return _STAGE_ORDER_GROUP_BOUNDS[-1][1]


@runtime_checkable
class StageDetectionStrategy(Protocol):
    def detect(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
        repository: ReasoningRepository,
    ) -> StageDetection: ...


class DeclaredStageStrategy:
    """Declared stage + primary_stage_group corroboration."""

    def detect(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
        repository: ReasoningRepository,
    ) -> StageDetection:
        declared = self._declared_stage(context)
        if declared is None:
            return StageDetection(
                stage_id=None,
                stage_name=None,
                probability=_ZERO,
                confidence=_ZERO,
                evidence=("No declared stage on the session or founder profile.",),
            )

        stage = repository.get_founder_stage(declared)
        stage_name = stage.stage_name if stage is not None else None
        expected_group = (
            _group_for_stage_order(stage.stage_order) if stage is not None else None
        )

        group_counts = Counter(
            questions[c.question_id].primary_stage_group
            for c in classifications
            if c.question_id in questions
            and questions[c.question_id].primary_stage_group
        )
        tagged_total = sum(group_counts.values())

        if expected_group is not None and tagged_total > 0:
            matching = group_counts.get(expected_group, 0)
            confidence = _quant(Decimal(matching) / Decimal(tagged_total))
        else:
            # No stage-tagged answers to corroborate -> trust the declared stage.
            confidence = _ONE

        evidence = [f"Declared stage: {stage_name or declared}."]
        if tagged_total > 0:
            distribution = ", ".join(
                f"{group}={count}" for group, count in sorted(group_counts.items())
            )
            evidence.append(f"Answered stage-group distribution: {distribution}.")
            if expected_group is not None:
                evidence.append(f"Expected group for stage: {expected_group}.")
        else:
            evidence.append("No stage-tagged answers to corroborate.")

        return StageDetection(
            stage_id=declared,
            stage_name=stage_name,
            probability=_ONE,  # declared -> a direct signal
            confidence=confidence,
            evidence=tuple(evidence),
        )

    def _declared_stage(self, context: ReasoningContext) -> int | None:
        if context.session is not None and context.session.founder_stage_id is not None:
            return context.session.founder_stage_id
        if context.founder is not None and context.founder.stage_id is not None:
            return context.founder.stage_id
        return None


def _quant(value: Decimal) -> Decimal:
    return value.quantize(_QUANT, rounding=ROUND_HALF_UP)


class StageDetector:
    def __init__(
        self,
        repository: ReasoningRepository,
        strategy: StageDetectionStrategy | None = None,
    ):
        self.repository = repository
        self.strategy = strategy or DeclaredStageStrategy()

    def detect(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> StageDetection:
        return self.strategy.detect(classifications, questions, context, self.repository)
