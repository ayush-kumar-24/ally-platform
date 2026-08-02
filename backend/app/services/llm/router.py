"""Task -> model resolution, read from the DB (`model_task_routing`).

Which model serves which task is DATA, not a code constant: changing it is an
UPDATE, not a deploy (same principle as scoring_rules). Engine code asks for a
task by name and never names a model or provider.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.llm import ModelTaskRouting
from app.services.llm.base import LLMConfigurationError


# Canonical task names. Engines reference these -- never a model string.
class LLMTask:
    ANSWER_INTERPRETATION = "answer_interpretation"
    NEXT_QUESTION_SELECTION = "next_question_selection"
    DISTRESS_DETECTION = "distress_detection"
    DIAGNOSIS_REASONING = "diagnosis_reasoning"
    ANSWER_CONSISTENCY = "answer_consistency"
    ARCHETYPE_ASSIGNMENT = "archetype_assignment"
    REPORT_NARRATIVE = "report_narrative"

    ALL = (
        ANSWER_INTERPRETATION, NEXT_QUESTION_SELECTION, DISTRESS_DETECTION,
        DIAGNOSIS_REASONING, ANSWER_CONSISTENCY, ARCHETYPE_ASSIGNMENT, REPORT_NARRATIVE,
    )


@dataclass(frozen=True)
class TaskModel:
    task: str
    provider: str
    model_id: str


def resolve_task_model(db: Session, task: str) -> TaskModel:
    """The active provider+model for `task`. Fails loudly if unmapped -- a task
    with no routing row is a misconfiguration, not a silent default."""
    row = db.execute(
        select(ModelTaskRouting).where(
            ModelTaskRouting.task == task, ModelTaskRouting.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if row is None:
        raise LLMConfigurationError(
            f"No active model routing for task {task!r}. Seed model_task_routing."
        )
    return TaskModel(task=task, provider=row.provider, model_id=row.model_id)
