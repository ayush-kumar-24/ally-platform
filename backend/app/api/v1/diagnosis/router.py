"""Diagnosis endpoints.

Routing and serialisation only. No business rules and no queries live here --
the service raises `AppError` subclasses carrying their own status codes, and
the handler registered in main.py renders them, so there is no try/except
noise in this layer.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

# Phase 3's get_founder_record resolves the AuthUser token to the Founders row.
from app.api.deps import get_founder_record as get_current_founder
from app.api.v1.diagnosis.schemas import (
    CurrentQuestionResponse,
    StartSessionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from app.api.v1.diagnosis.advisor import NextQuestionAdvisor
from app.api.v1.diagnosis.deps import get_next_question_advisor
from app.api.v1.diagnosis.notifications import (
    SessionCompletionNotifier,
    get_session_completion_notifier,
)
from app.api.v1.diagnosis.service import DiagnosisService
from app.db.session import get_db
from app.models import Founder, SessionStatus

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


@router.post(
    "/start",
    response_model=StartSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start (or resume) a diagnosis session",
)
def start_session(
    db: Session = Depends(get_db),
    founder: Founder = Depends(get_current_founder),
) -> StartSessionResponse:
    session, question, resumed = DiagnosisService(db).start_session(founder)
    return StartSessionResponse(session=session, question=question, resumed=resumed)


@router.get(
    "/current",
    response_model=CurrentQuestionResponse,
    summary="Get the current question for the active session",
)
def get_current_question(
    db: Session = Depends(get_db),
    founder: Founder = Depends(get_current_founder),
) -> CurrentQuestionResponse:
    session, question = DiagnosisService(db).get_current_question(founder)
    return CurrentQuestionResponse(session=session, question=question)


@router.post(
    "/answer",
    response_model=SubmitAnswerResponse,
    summary="Submit an answer and receive the next question",
)
async def submit_answer(
    payload: SubmitAnswerRequest,
    db: Session = Depends(get_db),
    founder: Founder = Depends(get_current_founder),
    completion_notifier: SessionCompletionNotifier = Depends(
        get_session_completion_notifier
    ),
    advisor: NextQuestionAdvisor | None = Depends(get_next_question_advisor),
) -> SubmitAnswerResponse:
    session, next_question = await DiagnosisService(db, advisor=advisor).submit_answer(
        founder=founder,
        question_id=payload.question_id,
        answer_text=payload.answer_text,
    )

    # When this answer completes the session, notify that it completed. The
    # router does not know or care that reasoning listens -- the listener is
    # bound at composition (main.py). The default notifier is a no-op.
    if session.status == SessionStatus.COMPLETED:
        completion_notifier.notify_session_completed(db, founder, session.session_id)

    return SubmitAnswerResponse(
        session=session,
        next_question=next_question,
        is_complete=session.status == SessionStatus.COMPLETED,
    )
