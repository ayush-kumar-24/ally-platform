"""Database access for the Current Problem phase.

Queries only -- no business rules, no commits. Mirrors
app/api/v1/founder_dna/repository.py.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schema import (
    CurrentProblemAnswers,
    CurrentProblemQuestions,
    Founders,
)


class CurrentProblemRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Questions ---

    def get_question_by_id(self, question_id: int) -> CurrentProblemQuestions | None:
        return self.db.get(CurrentProblemQuestions, question_id)

    def next_unanswered(
        self, founder_id: int, stage_group: str
    ) -> CurrentProblemQuestions | None:
        """The lowest-arc active question this founder hasn't answered.

        Ordering lives in the query rather than in an engine class because
        this phase has no selection logic worth the indirection -- it is four
        questions in a fixed order. The symptom (arc 0) therefore always
        comes first, which the rest of the phase depends on.
        """
        answered = select(CurrentProblemAnswers.current_problem_question_id).where(
            CurrentProblemAnswers.founder_id == founder_id
        )
        stmt = (
            select(CurrentProblemQuestions)
            .where(
                CurrentProblemQuestions.is_active.is_(True),
                CurrentProblemQuestions.stage_group == stage_group,
                CurrentProblemQuestions.current_problem_question_id.not_in(answered),
            )
            .order_by(
                CurrentProblemQuestions.arc_position.asc(),
                CurrentProblemQuestions.current_problem_question_id.asc(),
            )
        )
        return self.db.execute(stmt).scalars().first()

    def count_active(self, stage_group: str) -> int:
        stmt = select(CurrentProblemQuestions.current_problem_question_id).where(
            CurrentProblemQuestions.is_active.is_(True),
            CurrentProblemQuestions.stage_group == stage_group,
        )
        return len(self.db.execute(stmt).all())

    # --- Answers ---

    def get_answer(
        self, founder_id: int, question_id: int
    ) -> CurrentProblemAnswers | None:
        stmt = select(CurrentProblemAnswers).where(
            CurrentProblemAnswers.founder_id == founder_id,
            CurrentProblemAnswers.current_problem_question_id == question_id,
        )
        return self.db.execute(stmt).scalars().first()

    def add_answer(self, answer: CurrentProblemAnswers) -> CurrentProblemAnswers:
        self.db.add(answer)
        self.db.flush()
        return answer

    def count_answered(self, founder_id: int, stage_group: str) -> int:
        stmt = (
            select(CurrentProblemAnswers.current_problem_answer_id)
            .join(
                CurrentProblemQuestions,
                CurrentProblemQuestions.current_problem_question_id
                == CurrentProblemAnswers.current_problem_question_id,
            )
            .where(
                CurrentProblemAnswers.founder_id == founder_id,
                CurrentProblemQuestions.stage_group == stage_group,
            )
        )
        return len(self.db.execute(stmt).all())

    def answered_history(self, founder_id: int) -> list[tuple[str, str, bool, object]]:
        """(question_text, answer_text, is_symptom, answered_at), oldest first.

        Feeds both the resume transcript and the report -- see
        app/api/v1/reports/payload.py, which reads the symptom and the probe
        answers out of exactly this shape.
        """
        stmt = (
            select(
                CurrentProblemQuestions.question_text,
                CurrentProblemAnswers.answer_text,
                CurrentProblemQuestions.is_symptom,
                CurrentProblemAnswers.answered_at,
            )
            .join(
                CurrentProblemAnswers,
                CurrentProblemAnswers.current_problem_question_id
                == CurrentProblemQuestions.current_problem_question_id,
            )
            .where(CurrentProblemAnswers.founder_id == founder_id)
            .order_by(CurrentProblemAnswers.answered_at.asc())
        )
        return list(self.db.execute(stmt).all())

    # --- Founder progress markers ---

    def mark_phase_complete(self, founder: Founders, completed_at) -> None:
        founder.current_problem_completed_at = completed_at
