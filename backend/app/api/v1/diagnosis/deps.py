"""Diagnosis dependencies.

`get_next_question_advisor` selects the adaptive next-question advisor from config.
When ADAPTIVE_QUESTIONS is off (default), it returns None and the flow stays fully
deterministic -- no LLM provider is built, so nothing changes for the default path.
"""

from __future__ import annotations

from app.api.v1.diagnosis.advisor import LLMNextQuestionAdvisor, NextQuestionAdvisor
from app.core.config import settings
from app.services.llm import get_provider


def get_next_question_advisor() -> NextQuestionAdvisor | None:
    if not settings.ADAPTIVE_QUESTIONS:
        return None
    return LLMNextQuestionAdvisor(
        get_provider(settings.LLM_PROVIDER),
        timeout_seconds=settings.ADAPTIVE_TIMEOUT_SECONDS,
    )
