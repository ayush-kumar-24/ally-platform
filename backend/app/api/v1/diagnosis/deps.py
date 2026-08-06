"""Diagnosis dependencies.

`get_next_question_advisor` selects the adaptive next-question advisor from config.
When ADAPTIVE_QUESTIONS is off, it returns None and the flow stays fully
deterministic -- no LLM provider is built, so nothing changes for that path.

Why this goes through `provider_for_task`
-----------------------------------------
It used to call `get_provider(settings.LLM_PROVIDER)` directly. That works, but it
skips the telemetry wrapper, so next_question_selection calls never reached
`llm_call_log` -- no tokens, no cost, no model, no founder. It is the most
expensive line in a diagnosis (one call per question, ~1,500 in / 100 out, about
Rs 7.6 of the Rs 14.6 a full run costs) and it was the only one completely
invisible: `llm_call_log` contained nothing but `first_impression` rows while
adaptive questioning had been switched on the whole time.

Routing through `provider_for_task` also means the model comes from the
`model_task_routing` table like every other task, rather than from a single global
LLM_PROVIDER setting -- so this task can be re-pointed without a deploy, and the
routing row named `next_question_selection` finally controls the calls it names.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.api.v1.diagnosis.advisor import LLMNextQuestionAdvisor, NextQuestionAdvisor
from app.core.config import settings
from app.db.session import get_db
from app.models import Founder
from app.services.llm.tasks import provider_for_task

#: The routing key. Matches the seeded row in model_task_routing.
NEXT_QUESTION_TASK = "next_question_selection"


def get_next_question_advisor(
    db: Session = Depends(get_db),
    founder: Founder = Depends(get_founder_record),
) -> NextQuestionAdvisor | None:
    if not settings.ADAPTIVE_QUESTIONS:
        return None
    return LLMNextQuestionAdvisor(
        provider_for_task(db, NEXT_QUESTION_TASK, founder_id=founder.founder_id),
        timeout_seconds=settings.ADAPTIVE_TIMEOUT_SECONDS,
    )
