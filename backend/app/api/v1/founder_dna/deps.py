"""Founder DNA dependencies.

`get_dimension_resolution_advisor` mirrors
app/api/v1/diagnosis/deps.py::get_next_question_advisor exactly: gated on the
same ADAPTIVE_QUESTIONS flag (this phase's adaptiveness is the same feature,
not a separate switch), routed through provider_for_task so the model comes
from model_task_routing and every call is logged to llm_call_log, and
fails open to None (deterministic pool-exhaustion stop) if that routing row
hasn't been seeded yet -- LLMConfigurationError is exactly that "no active
routing" case, not a real outage, so it's caught here rather than surfacing
as a 500 to the founder.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.api.v1.founder_dna.advisor import (
    DimensionResolutionAdvisor,
    LLMDimensionResolutionAdvisor,
)
from app.core.config import settings
from app.core.logger import logger
from app.db.session import get_db
from app.models import Founder
from app.services.llm.base import LLMConfigurationError
from app.services.llm.router import LLMTask
from app.services.llm.tasks import provider_for_task


def get_dimension_resolution_advisor(
    db: Session = Depends(get_db),
    founder: Founder = Depends(get_founder_record),
) -> DimensionResolutionAdvisor | None:
    if not settings.ADAPTIVE_QUESTIONS:
        return None
    try:
        provider = provider_for_task(
            db, LLMTask.FOUNDER_DNA_DIMENSION_RESOLUTION, founder_id=founder.founder_id
        )
    except LLMConfigurationError as exc:
        # error, not warning: the row is seeded by migration a7c419d0f2b3, so
        # its absence now means a database that has not been migrated, not a
        # feature awaiting rollout. This branch is the entire difference
        # between an adaptive phase and a scripted one, and it went unnoticed
        # in production precisely because it was logged as routine.
        logger.error(
            "founder_dna_dimension_resolution has no active model_task_routing "
            "row; the Founder DNA phase will run NON-adaptively (dimensions "
            "resolved by question count alone). Run migrations.",
            exc_info=exc,
        )
        return None
    return LLMDimensionResolutionAdvisor(
        provider, timeout_seconds=settings.ADAPTIVE_TIMEOUT_SECONDS
    )
