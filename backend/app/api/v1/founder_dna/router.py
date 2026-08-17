"""Founder DNA endpoints.

Routing and serialisation only, mirroring app/api/v1/diagnosis/router.py's
shape (start / current / answer) so the frontend can reuse the same call
pattern it already knows for diagnosis.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record as get_current_founder
from app.api.v1.founder_dna.advisor import DimensionResolutionAdvisor
from app.api.v1.founder_dna.deps import get_dimension_resolution_advisor
from app.api.v1.founder_dna.engine import ALL_DIMENSIONS, resolve_founder_dna_stage_group
from app.api.v1.founder_dna.repository import FounderDnaRepository
from app.api.v1.founder_dna.schemas import (
    CurrentFounderDnaQuestionResponse,
    FounderDnaProgress,
    FounderDnaTurn,
    StartFounderDnaResponse,
    SubmitFounderDnaAnswerRequest,
    SubmitFounderDnaAnswerResponse,
)
from app.api.v1.founder_dna.service import FounderDnaService
from app.db.session import get_db
from app.middleware.rate_limit import founder_rate_limit
from app.models import Founder

router = APIRouter(prefix="/founder-dna", tags=["founder-dna"])

# Same shape and same reasoning as diagnosis's rate limits (app/api/v1/
# diagnosis/router.py) -- this is the other place a founder's answer
# triggers an LLM call with no credit/plan gate.
start_rate_limit = founder_rate_limit(
    key="founder-dna-start", limit=10, window_seconds=60,
    founder_id_dependency=get_current_founder,
)
answer_rate_limit = founder_rate_limit(
    key="founder-dna-answer", limit=20, window_seconds=60,
    founder_id_dependency=get_current_founder,
)


def _progress(
    repository: FounderDnaRepository, founder: Founder, is_complete: bool
) -> FounderDnaProgress:
    resolved = sorted(repository.get_resolved_dimensions(founder))
    remaining = [d for d in ALL_DIMENSIONS if d not in resolved]
    return FounderDnaProgress(
        questions_answered=repository.count_answered(founder.founder_id),
        dimensions_resolved=resolved,
        dimensions_remaining=remaining,
        is_complete=is_complete,
    )


@router.post(
    "/start",
    response_model=StartFounderDnaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(start_rate_limit)],
)
def start(
    db: Session = Depends(get_db),
    founder: Founder = Depends(get_current_founder),
) -> StartFounderDnaResponse:
    service = FounderDnaService(db)
    question = service.start(founder)
    repository = FounderDnaRepository(db)
    return StartFounderDnaResponse(
        progress=_progress(repository, founder, question is None),
        question=question,
    )


@router.get("/current", response_model=CurrentFounderDnaQuestionResponse)
def current(
    db: Session = Depends(get_db),
    founder: Founder = Depends(get_current_founder),
) -> CurrentFounderDnaQuestionResponse:
    service = FounderDnaService(db)
    question, is_complete = service.current_state(founder)
    repository = FounderDnaRepository(db)
    return CurrentFounderDnaQuestionResponse(
        progress=_progress(repository, founder, is_complete),
        question=question,
        history=[
            FounderDnaTurn(
                question_text=qt, dimension_code=dc,
                answer_text=at, answered_at=ts,
            )
            for qt, dc, at, ts in repository.answered_history(founder.founder_id)
        ],
    )


@router.post(
    "/answer",
    response_model=SubmitFounderDnaAnswerResponse,
    dependencies=[Depends(answer_rate_limit)],
)
async def submit_answer(
    payload: SubmitFounderDnaAnswerRequest,
    db: Session = Depends(get_db),
    founder: Founder = Depends(get_current_founder),
    advisor: DimensionResolutionAdvisor | None = Depends(get_dimension_resolution_advisor),
) -> SubmitFounderDnaAnswerResponse:
    service = FounderDnaService(db, advisor=advisor)
    next_question, is_complete = await service.submit_answer(
        founder=founder,
        question_id=payload.founder_dna_question_id,
        answer_text=payload.answer_text,
    )
    repository = FounderDnaRepository(db)
    return SubmitFounderDnaAnswerResponse(
        progress=_progress(repository, founder, is_complete),
        next_question=next_question,
    )
