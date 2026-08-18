"""Business logic for the Current Problem phase.

Founder-scoped like Founder DNA, not session-scoped: progress lives on the
`founders` row (current_problem_completed_at) and on current_problem_answers.

Much thinner than FounderDnaService because there is no advisor and nothing
to resolve -- "complete" here just means "no unanswered active question left
for this stage", so a single commit per answer is enough. The two-commit
dance in FounderDnaService exists purely to protect an answer from a slow LLM
call that this phase never makes.

Entering the phase requires Founder DNA to be finished, mirroring the way
/diagnosis/start requires this one -- the three sections run in the doc's
order, each gating the next.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.current_problem.repository import CurrentProblemRepository
from app.api.v1.founder_dna.engine import resolve_founder_dna_stage_group
from app.core.logger import logger
from app.middleware.error_handler import AppError
from app.models.schema import CurrentProblemAnswers, CurrentProblemQuestions, Founders


class FounderDnaRequiredError(AppError):
    def __init__(
        self,
        message: str = "Finish the Founder DNA phase before describing the problem.",
    ):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class CurrentProblemQuestionMismatchError(AppError):
    def __init__(self, message: str = "That question is not currently outstanding."):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class CurrentProblemPersistenceError(AppError):
    def __init__(self, message: str = "Could not save the Current Problem phase."):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CurrentProblemService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = CurrentProblemRepository(db)

    # --- Public API ---

    def current_state(
        self, founder: Founders
    ) -> tuple[CurrentProblemQuestions | None, bool]:
        """(question, is_complete) -- read-only, creates nothing."""
        if founder.current_problem_completed_at is not None:
            return None, True

        stage_group = resolve_founder_dna_stage_group(founder)
        question = self.repository.next_unanswered(founder.founder_id, stage_group)
        return (None, True) if question is None else (question, False)

    def start(self, founder: Founders) -> CurrentProblemQuestions | None:
        """First (or next unanswered) question. Idempotent."""
        if founder.founder_dna_completed_at is None:
            raise FounderDnaRequiredError()

        question, is_complete = self.current_state(founder)
        if is_complete and founder.current_problem_completed_at is None:
            # Reachable when the seed bank is empty for this stage group --
            # completing rather than looping keeps a mis-seeded environment
            # from stranding the founder short of /diagnosis/start.
            self._complete(founder)
            self.db.commit()
        return question

    def submit_answer(
        self, founder: Founders, question_id: int, answer_text: str
    ) -> tuple[CurrentProblemQuestions | None, bool]:
        if founder.current_problem_completed_at is not None:
            raise CurrentProblemQuestionMismatchError(
                "The Current Problem phase is already complete."
            )

        question = self.repository.get_question_by_id(question_id)
        if question is None:
            raise CurrentProblemQuestionMismatchError(
                f"Question {question_id} does not exist."
            )

        stage_group = resolve_founder_dna_stage_group(founder)
        if question.stage_group != stage_group:
            raise CurrentProblemQuestionMismatchError(
                "That question is not part of your current stage."
            )

        if self.repository.get_answer(founder.founder_id, question_id) is None:
            self.repository.add_answer(
                CurrentProblemAnswers(
                    founder_id=founder.founder_id,
                    current_problem_question_id=question_id,
                    answer_text=answer_text,
                    answered_at=_utcnow(),
                )
            )
        else:
            # Retry of an already-saved answer -- resume, don't duplicate.
            logger.info(
                "Current Problem answer already saved; resuming",
                extra={"founder_id": founder.founder_id, "question_id": question_id},
            )

        try:
            next_question = self.repository.next_unanswered(
                founder.founder_id, stage_group
            )
            is_complete = next_question is None
            if is_complete:
                self._complete(founder)
            self.db.commit()
            return next_question, is_complete
        except IntegrityError as exc:
            self.db.rollback()
            if self.repository.get_answer(founder.founder_id, question_id) is None:
                logger.error(
                    "Integrity error saving Current Problem answer",
                    extra={"founder_id": founder.founder_id},
                    exc_info=exc,
                )
                raise CurrentProblemPersistenceError("Could not save the answer.")
            # A concurrent duplicate landed first; the answer is safe.
            return self.repository.next_unanswered(founder.founder_id, stage_group), False
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "Database error saving Current Problem progress",
                extra={"founder_id": founder.founder_id},
                exc_info=exc,
            )
            raise CurrentProblemPersistenceError(
                "Could not save your progress. Please try again."
            )

    # --- Internals ---

    def _complete(self, founder: Founders) -> None:
        self.repository.mark_phase_complete(founder, _utcnow())
