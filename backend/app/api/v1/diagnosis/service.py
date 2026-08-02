"""Business logic for the diagnosis assessment flow.

Owns the transaction boundary: each public method commits once, or lets the
exception propagate so `get_db` discards the connection with nothing partially
written. In particular an answer and the session-progress update it causes are
committed together -- never one without the other.
"""

from datetime import datetime, timezone

from fastapi import status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.advisor import AnswerInsight, NextQuestionAdvisor, resolve_next
from app.api.v1.diagnosis.engine import QuestionSelectionEngine
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.core.config import settings
from app.core.logger import logger
from app.middleware.error_handler import AppError
from app.models import (
    Answer,
    DiagnosisSession,
    Founder,
    Question,
    RoutingState,
    SessionState,
    SessionStatus,
)


class SessionNotFoundError(AppError):
    def __init__(self, message: str = "No active diagnosis session was found."):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)


class SessionNotActiveError(AppError):
    def __init__(self, message: str = "This diagnosis session is no longer active."):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class QuestionMismatchError(AppError):
    def __init__(self, message: str = "That question is not the current question."):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class DuplicateAnswerError(AppError):
    def __init__(self, message: str = "This question has already been answered."):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class DiagnosisPersistenceError(AppError):
    def __init__(self, message: str = "Could not save the diagnosis session."):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DiagnosisService:
    def __init__(self, db: Session, *, advisor: NextQuestionAdvisor | None = None):
        self.db = db
        self.repository = DiagnosisRepository(db)
        self.engine = QuestionSelectionEngine(self.repository)
        # Optional adaptive next-question advisor (Hybrid). None => deterministic.
        self.advisor = advisor

    # --- Public API ---

    def start_session(self, founder: Founder) -> tuple[DiagnosisSession, Question | None, bool]:
        """Start a diagnosis session, or resume the founder's active one.

        Resuming rather than creating a second session is deliberate: the
        schema permits multiple in-progress rows per founder, and a double-
        submitted "Start" would otherwise silently fork the assessment and
        strand the answers already given.

        Returns (session, first_question, resumed).
        """
        existing = self.repository.get_active_session_for_founder(founder.founder_id)
        if existing is not None:
            logger.info(
                "Resuming existing diagnosis session",
                extra={"founder_id": founder.founder_id},
            )
            question = self._current_question_for(existing, founder)
            return existing, question, True

        session = DiagnosisSession(
            founder_id=founder.founder_id,
            status=SessionStatus.IN_PROGRESS.value,
            questions_answered_count=0,
            session_state=SessionState.STABLE.value,
            routing_state=RoutingState.CONTINUE.value,
            founder_stage_id=founder.stage_id,
            founder_industry_id=founder.industry_mapped_id,
            started_at=_utcnow(),
            last_activity_at=_utcnow(),
        )

        try:
            self.repository.add_session(session)

            first_question = self.engine.select_next_question(session, founder)
            self._attach_question(session, first_question)

            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            # Most likely a CHECK/FK violation -- surfaced explicitly because
            # the generic 500 handler would hide which constraint failed.
            logger.error(
                "Integrity error creating diagnosis session",
                extra={"founder_id": founder.founder_id},
                exc_info=exc,
            )
            raise DiagnosisPersistenceError()
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "Database error creating diagnosis session",
                extra={"founder_id": founder.founder_id},
                exc_info=exc,
            )
            raise DiagnosisPersistenceError()

        self.db.refresh(session)
        logger.info(
            "Started diagnosis session",
            extra={"founder_id": founder.founder_id},
        )
        return session, first_question, False

    def get_current_question(self, founder: Founder) -> tuple[DiagnosisSession, Question | None]:
        """Current question for the founder's active session.

        404s when there is no active session -- the caller must POST /start
        first. This is a read; it does not create one implicitly.
        """
        session = self.repository.get_active_session_for_founder(founder.founder_id)
        if session is None:
            raise SessionNotFoundError()

        return session, self._current_question_for(session, founder)

    async def submit_answer(
        self,
        founder: Founder,
        question_id: int,
        answer_text: str,
    ) -> tuple[DiagnosisSession, Question | None]:
        """Store an answer, advance progress, and select the next question.

        Returns (session, next_question). `next_question` is None once the bank
        is exhausted, at which point the session is marked completed.

        Adaptive (Hybrid): when an advisor is wired, the LLM reads the answer,
        scores it (persisted on the answer), and re-ranks the deterministic
        shortlist to pick the next question. It fails open to the deterministic
        pick on any error, so the flow always progresses.
        """
        session = self.repository.get_active_session_for_founder(founder.founder_id)
        if session is None:
            raise SessionNotFoundError()

        self._assert_active(session)

        # Guard against a stale client replaying an old question. Without this,
        # a retried request could attach an answer to the wrong question.
        if session.current_question_id is not None and question_id != session.current_question_id:
            raise QuestionMismatchError(
                f"Expected question {session.current_question_id}, received {question_id}."
            )

        question = self.repository.get_question_by_id(question_id)
        if question is None:
            raise QuestionMismatchError(f"Question {question_id} does not exist.")

        if self.repository.get_answer(session.session_id, question_id) is not None:
            raise DuplicateAnswerError()

        answer = Answer(
            session_id=session.session_id,
            founder_id=founder.founder_id,
            question_id=question_id,
            answer_text=answer_text,
            is_follow_up=False,
            is_distress_flagged=False,
            answered_at=_utcnow(),
        )
        self.repository.add_answer(answer)

        # Choose the next question BEFORE opening the write transaction's commit:
        # the advisor call is network I/O and must not fail the answer save. It
        # returns the deterministic pick on any problem.
        next_question = await self._choose_next_question(session, founder, question, answer)

        try:
            session.questions_answered_count += 1
            session.last_activity_at = _utcnow()
            session.updated_at = _utcnow()
            self._attach_question(session, next_question)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            logger.error(
                "Integrity error saving answer",
                extra={"founder_id": founder.founder_id},
                exc_info=exc,
            )
            raise DiagnosisPersistenceError("Could not save the answer.")
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "Database error saving answer",
                extra={"founder_id": founder.founder_id},
                exc_info=exc,
            )
            raise DiagnosisPersistenceError("Could not save the answer.")

        self.db.refresh(session)
        return session, next_question

    async def _choose_next_question(
        self, session: DiagnosisSession, founder: Founder, answered: Question, answer: Answer
    ) -> Question | None:
        """Deterministic pick, optionally overridden by the LLM advisor.

        Never raises: an advisor failure or an out-of-shortlist recommendation
        falls back to the deterministic head, so the assessment always advances.
        """
        candidates = self.engine.candidate_questions(session, founder)
        if not candidates:
            return None  # bank exhausted -> completion

        ordered = self.engine.order_candidates(candidates)
        if self.advisor is None:
            return ordered[0]

        shortlist = ordered[: settings.ADAPTIVE_SHORTLIST_SIZE]
        history = self.repository.recent_qa(session.session_id, limit=5)
        insight: AnswerInsight | None = None
        try:
            insight = await self.advisor.analyze(
                answered_question=answered,
                answer_text=answer.answer_text,
                shortlist=shortlist,
                history=history,
            )
        except Exception as exc:  # advisor must never break the flow
            logger.warning(
                "adaptive advisor raised; using deterministic pick",
                extra={"founder_id": founder.founder_id, "stage": "adaptive_questions"},
                exc_info=exc,
            )

        if insight is not None:
            self._apply_insight(answer, insight)
        return resolve_next(ordered, shortlist, insight)

    def _apply_insight(self, answer: Answer, insight: AnswerInsight) -> None:
        """Persist the LLM's Green/Amber/Red read on the answer, so the reasoning
        pipeline reuses it (via the stored-score classifier) instead of re-scoring."""
        if insight.score_label is not None:
            answer.score_label = insight.score_label
            answer.score = insight.score

    # --- Internals ---

    def _assert_active(self, session: DiagnosisSession) -> None:
        if session.status != SessionStatus.IN_PROGRESS:
            raise SessionNotActiveError(
                f"Session {session.session_id} has status '{session.status}'."
            )

    def _attach_question(
        self,
        session: DiagnosisSession,
        question: Question | None,
    ) -> None:
        """Point the session at `question`, or complete it when None.

        Completion lives here rather than in the engine so that "no questions
        left" has exactly one meaning across every entry point.
        """
        if question is None:
            session.current_question_id = None
            session.current_category = None
            session.status = SessionStatus.COMPLETED.value
            session.completed_at = _utcnow()
            session.routing_state = RoutingState.GENERATE_REPORT.value
            return

        session.current_question_id = question.question_id
        session.current_category = question.category

    def _current_question_for(
        self,
        session: DiagnosisSession,
        founder: Founder,
    ) -> Question | None:
        """Question the session is currently sitting on.

        Self-heals a session whose pointer is null while it is still active --
        that can happen if a previous request died between creating the session
        and selecting a question. Re-selecting is safe because selection is
        deterministic and derived from what has been answered.
        """
        if session.current_question_id is not None:
            return self.repository.get_question_by_id(session.current_question_id)

        if session.status != SessionStatus.IN_PROGRESS:
            return None

        question = self.engine.select_next_question(session, founder)
        self._attach_question(session, question)

        try:
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "Database error repairing session question pointer",
                extra={"founder_id": founder.founder_id},
                exc_info=exc,
            )
            raise DiagnosisPersistenceError()

        return question
