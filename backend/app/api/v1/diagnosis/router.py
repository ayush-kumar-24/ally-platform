"""Diagnosis endpoints.

Routing and serialisation only. No business rules and no queries live here --
the service raises `AppError` subclasses carrying their own status codes, and
the handler registered in main.py renders them, so there is no try/except
noise in this layer.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

# Phase 3's get_founder_record resolves the AuthUser token to the Founders row.
from app.api.deps import get_founder_record as get_current_founder
from app.api.v1.diagnosis.schemas import (
    AnsweredQA,
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
from app.api.v1.privacy.dependencies import require_ai_processing_allowed
from app.db.session import get_db
from app.middleware.rate_limit import founder_rate_limit
from app.models import Founder, SessionStatus

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])

# Named module-level dependency objects (not inline Depends(founder_rate_limit(...))
# calls) so tests can override them the same way other per-founder gates in
# this codebase already are -- FastAPI's dependency_overrides keys by the
# exact callable object passed to Depends(), and a factory call produces a
# fresh closure each time.
start_rate_limit = founder_rate_limit(
    key="diagnosis-start", limit=10, window_seconds=60,
    founder_id_dependency=get_current_founder,
)
answer_rate_limit = founder_rate_limit(
    key="diagnosis-answer", limit=20, window_seconds=60,
    founder_id_dependency=get_current_founder,
)


@router.post(
    "/start",
    response_model=StartSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start (or resume) a diagnosis session",
    dependencies=[Depends(start_rate_limit), Depends(require_ai_processing_allowed)],
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
    session, question, history = DiagnosisService(db).get_current_question(founder)
    return CurrentQuestionResponse(
        session=session,
        question=question,
        history=[
            AnsweredQA(question_text=qt, category=cat, answer_text=at, answered_at=ts)
            for qt, cat, at, ts in history
        ],
    )


@router.post(
    "/answer",
    response_model=SubmitAnswerResponse,
    summary="Submit an answer and receive the next question",
    # This is where the real LLM cost lives (advisor pick + incremental
    # confidence scoring), and the diagnosis path has no credit/plan gate at
    # all (unlike chat's chat_gate) -- so a per-founder request-rate ceiling
    # is the only backstop against a single account driving unbounded LLM
    # spend here. A 30-question diagnosis under normal use stays well under
    # this in any single minute. require_ai_processing_allowed is the other
    # half: the rate limit bounds throughput, this one refuses entirely once
    # the founder has restricted processing or withdrawn consent.
    dependencies=[Depends(answer_rate_limit), Depends(require_ai_processing_allowed)],
)
async def submit_answer(
    payload: SubmitAnswerRequest,
    background_tasks: BackgroundTasks,
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
    #
    # SCHEDULED, not called. The bound listener runs the full reasoning pipeline,
    # profiled at 203 seconds on a real session; calling it here held the
    # founder's final answer request open for all of it, well past both the
    # frontend's 45s timeout and the load balancer's. The request was routinely
    # severed mid-pipeline, and because the listener swallows its own failures
    # that produced a COMPLETED session with no report and no error anywhere.
    # A BackgroundTask runs after the response is sent, so this endpoint now
    # returns in the time the answer itself takes.
    #
    # Ids, not `db` and `founder`: by the time the task runs, get_db's `finally`
    # has closed this session and the Founder row is detached. The notifier port
    # takes ids for exactly this reason and opens its own session.
    #
    # founder.user_id rides along because that new session starts with no RLS
    # context, and the founder-isolation policies resolve through
    # get_founder_id() -> app.current_founder_uuid. Read here, while the row is
    # still attached, rather than re-queried there -- the query to fetch it would
    # itself be the first thing RLS hides.
    #
    # The founder is not left guessing during the wait -- the Thinking screen
    # already polls /intelligence/reports/latest until the report appears, which
    # is the behaviour this change makes correct rather than incidental.
    if session.status == SessionStatus.COMPLETED:
        background_tasks.add_task(
            completion_notifier.notify_session_completed,
            founder.founder_id,
            session.session_id,
            str(founder.user_id),
        )

    return SubmitAnswerResponse(
        session=session,
        next_question=next_question,
        is_complete=session.status == SessionStatus.COMPLETED,
    )
