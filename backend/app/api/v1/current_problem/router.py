"""Current Problem endpoints.

Routing and serialisation only. Same start / current / answer shape as
app/api/v1/founder_dna/router.py.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record as get_current_founder, require_profile_complete
from app.api.v1.current_problem.repository import CurrentProblemRepository
from app.api.v1.current_problem.schemas import (
    CurrentCurrentProblemResponse,
    CurrentProblemProgress,
    CurrentProblemTurn,
    StartCurrentProblemResponse,
    SubmitCurrentProblemAnswerRequest,
    SubmitCurrentProblemAnswerResponse,
)
from app.api.v1.current_problem.service import CurrentProblemService
from app.api.v1.founder_dna.engine import resolve_founder_dna_stage_group
from app.db.session import get_db
from app.middleware.rate_limit import founder_rate_limit
from app.models import Founder

router = APIRouter(prefix="/current-problem", tags=["current-problem"])

# Same shape as founder_dna's limits. Lower ceilings than that phase would
# also be defensible -- this one makes no LLM call -- but keeping them equal
# means one number to reason about across the journey.
start_rate_limit = founder_rate_limit(
    key="current-problem-start", limit=10, window_seconds=60,
    founder_id_dependency=get_current_founder,
)
answer_rate_limit = founder_rate_limit(
    key="current-problem-answer", limit=20, window_seconds=60,
    founder_id_dependency=get_current_founder,
)


def _progress(
    repository: CurrentProblemRepository, founder: Founder, is_complete: bool
) -> CurrentProblemProgress:
    stage_group = resolve_founder_dna_stage_group(founder)
    return CurrentProblemProgress(
        questions_answered=repository.count_answered(founder.founder_id, stage_group),
        questions_total=repository.count_active(stage_group),
        is_complete=is_complete,
    )


@router.post(
    "/start",
    response_model=StartCurrentProblemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(start_rate_limit), Depends(require_profile_complete)],
)
def start(
    db: Session = Depends(get_db),
    founder: Founder = Depends(get_current_founder),
) -> StartCurrentProblemResponse:
    service = CurrentProblemService(db)
    question = service.start(founder)
    return StartCurrentProblemResponse(
        progress=_progress(CurrentProblemRepository(db), founder, question is None),
        question=question,
    )


@router.get("/current", response_model=CurrentCurrentProblemResponse)
def current(
    db: Session = Depends(get_db),
    founder: Founder = Depends(get_current_founder),
) -> CurrentCurrentProblemResponse:
    service = CurrentProblemService(db)
    question, is_complete = service.current_state(founder)
    repository = CurrentProblemRepository(db)
    return CurrentCurrentProblemResponse(
        progress=_progress(repository, founder, is_complete),
        question=question,
        history=[
            CurrentProblemTurn(
                question_text=qt, answer_text=at, is_symptom=sym, answered_at=ts,
            )
            for qt, at, sym, ts in repository.answered_history(founder.founder_id)
        ],
    )


@router.post(
    "/answer",
    response_model=SubmitCurrentProblemAnswerResponse,
    dependencies=[Depends(answer_rate_limit)],
)
def submit_answer(
    payload: SubmitCurrentProblemAnswerRequest,
    db: Session = Depends(get_db),
    founder: Founder = Depends(get_current_founder),
) -> SubmitCurrentProblemAnswerResponse:
    service = CurrentProblemService(db)
    next_question, is_complete = service.submit_answer(
        founder=founder,
        question_id=payload.current_problem_question_id,
        answer_text=payload.answer_text,
    )
    return SubmitCurrentProblemAnswerResponse(
        progress=_progress(CurrentProblemRepository(db), founder, is_complete),
        next_question=next_question,
    )
