"""Database access for the diagnosis module.

This layer only builds and runs queries. It holds no business rules, raises no
domain errors, and never commits -- transaction boundaries belong to the
service so that a single request stays atomic.
"""

from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy import text as _text
from sqlalchemy.orm import Session

from app.models import Answer, DiagnosisSession, Question, SessionStatus


class DiagnosisRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Sessions ---

    def lock_founder_for_diagnosis_start(self, founder_id: int) -> None:
        """Row-level lock, held for the rest of this transaction.

        Live-reproduced: two near-simultaneous POST /diagnosis/start calls for
        the same founder both read "no active session, 0 used this month"
        before either had committed, so both passed the monthly limit check
        and both created an in-progress session -- a limit of 1 became 2, and
        the "never fork the assessment" invariant start_session's own
        docstring describes was violated. SELECT ... FOR UPDATE here blocks a
        concurrent second call until the first one's transaction resolves, at
        which point it correctly sees the just-created session and takes the
        resume path instead of creating a duplicate. Scoped to one founder's
        row -- does not serialize unrelated founders against each other.
        """
        self.db.execute(
            _text("select founder_id from founders where founder_id = :f for update"),
            {"f": founder_id},
        )

    def get_session_by_id(self, session_id: int) -> DiagnosisSession | None:
        return self.db.get(DiagnosisSession, session_id)

    def get_detected_root_cause_ids(self, session_id: int) -> set[int]:
        """Root causes this session has already detected.

        Drives the validate-mode question bias: once there are candidate causes,
        questions that could confirm or rule one out are worth more than another
        broad sweep. Empty until the reasoning pipeline has written detections.
        """
        rows = self.db.execute(
            _text("select root_cause_id from detected_root_causes where session_id = :s"),
            {"s": session_id},
        ).scalars().all()
        return {int(r) for r in rows if r is not None}

    def count_sessions_started_since(self, founder_id: int, since: datetime) -> int:
        """Diagnoses this founder has STARTED since `since`, whatever their state.

        Counts abandoned and completed runs alike: the cost of a diagnosis is
        incurred when it is started and questions are answered, not when it is
        finished, so counting only completions would let someone abandon at
        question 29 and start again for free.
        """
        return self.db.scalar(
            select(func.count())
            .select_from(DiagnosisSession)
            .where(
                DiagnosisSession.founder_id == founder_id,
                DiagnosisSession.started_at >= since,
            )
        ) or 0

    def count_completed_sessions(self, founder_id: int) -> int:
        """Diagnoses this founder has ever COMPLETED -- a lifetime count, not
        scoped to a month.

        Backs the lifetime diagnosis cap: an abandoned or still-in-progress
        session must never count here, because the resume path must never be
        blocked and a founder must never be told their one free diagnosis is
        "used" before they have actually reached a report.
        """
        return self.db.scalar(
            select(func.count())
            .select_from(DiagnosisSession)
            .where(
                DiagnosisSession.founder_id == founder_id,
                DiagnosisSession.status == SessionStatus.COMPLETED,
            )
        ) or 0

    def get_active_session_for_founder(self, founder_id: int) -> DiagnosisSession | None:
        """Most recent in-progress session, if any.

        Ordered newest-first so that historical data predating the
        one-active-session rule still resolves deterministically.
        """
        stmt = (
            select(DiagnosisSession)
            .where(
                DiagnosisSession.founder_id == founder_id,
                DiagnosisSession.status == SessionStatus.IN_PROGRESS,
            )
            .order_by(DiagnosisSession.started_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def add_session(self, session: DiagnosisSession) -> DiagnosisSession:
        """Stage a new session and flush so `session_id` is populated.

        Flush, not commit: the caller may still need to attach the first
        question in the same transaction.
        """
        self.db.add(session)
        self.db.flush()
        return session

    # --- Questions ---

    def get_question_by_id(self, question_id: int) -> Question | None:
        return self.db.get(Question, question_id)

    def get_answered_question_ids(self, session_id: int) -> set[int]:
        stmt = select(Answer.question_id).where(Answer.session_id == session_id)
        return set(self.db.execute(stmt).scalars().all())

    def list_candidate_questions(
        self,
        session_id: int,
        stage_groups: list[str],
    ) -> list[Question]:
        """Every question still unanswered in this session and valid for the
        founder's stage.

        `stage_groups` should include NULL-equivalent breadth: questions with a
        NULL `primary_stage_group` are stage-agnostic and always eligible. They
        are the majority of the bank, so excluding them would strip out most of
        the CORE questions.

        Ordering is left to the engine -- this returns an unordered candidate
        set on purpose.
        """
        answered = select(Answer.question_id).where(Answer.session_id == session_id)

        stmt: Select = select(Question).where(
            Question.question_id.not_in(answered),
            (Question.primary_stage_group.is_(None))
            | (Question.primary_stage_group.in_(stage_groups)),
        )
        return list(self.db.execute(stmt).scalars().all())

    # --- Answers ---

    def get_answer(self, session_id: int, question_id: int) -> Answer | None:
        stmt = select(Answer).where(
            Answer.session_id == session_id,
            Answer.question_id == question_id,
        )
        return self.db.execute(stmt).scalars().first()

    def add_answer(self, answer: Answer) -> Answer:
        self.db.add(answer)
        self.db.flush()
        return answer

    def recent_qa(self, session_id: int, limit: int = 5) -> list[tuple[str, str]]:
        """The last `limit` (question_text, answer_text) pairs, oldest-first, for
        adaptive next-question context. Ordered by answer time."""
        stmt = (
            select(Question.question_text, Answer.answer_text)
            .join(Answer, Answer.question_id == Question.question_id)
            .where(Answer.session_id == session_id)
            .order_by(Answer.answered_at.desc())
            .limit(limit)
        )
        rows = self.db.execute(stmt).all()
        return [(qt, at) for qt, at in reversed(rows)]
