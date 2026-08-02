"""Database access for the diagnosis module.

This layer only builds and runs queries. It holds no business rules, raises no
domain errors, and never commits -- transaction boundaries belong to the
service so that a single request stays atomic.
"""

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Answer, DiagnosisSession, Question, SessionStatus


class DiagnosisRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Sessions ---

    def get_session_by_id(self, session_id: int) -> DiagnosisSession | None:
        return self.db.get(DiagnosisSession, session_id)

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
