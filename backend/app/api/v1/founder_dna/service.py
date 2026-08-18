"""Business logic for the Founder DNA phase.

Founder-scoped, not session-scoped (unlike diagnosis): progress lives on the
`founders` row (founder_dna_resolved_dimensions, founder_dna_completed_at)
and on founder_dna_answers, so there's no separate "session" concept to
create/resume here -- a founder either has answers or doesn't, and either
has finished or hasn't. Simpler than diagnosis's session machinery because
this phase doesn't need routing_state/distress_mode/etc: those apply once
the founder reaches the actual diagnosis, which this phase gates entry to.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.founder_dna.advisor import DimensionResolutionAdvisor
from app.api.v1.founder_dna.engine import (
    FounderDnaSelectionEngine,
    resolve_founder_dna_stage_group,
)
from app.api.v1.founder_dna.repository import FounderDnaRepository
from app.core.config import settings
from app.core.logger import logger
from app.middleware.error_handler import AppError
from app.models.schema import FounderDnaAnswers, FounderDnaQuestions, Founders


class FounderDnaQuestionMismatchError(AppError):
    def __init__(self, message: str = "That question is not currently outstanding."):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class FounderDnaPersistenceError(AppError):
    def __init__(self, message: str = "Could not save the Founder DNA phase."):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FounderDnaService:
    def __init__(self, db: Session, *, advisor: DimensionResolutionAdvisor | None = None):
        self.db = db
        self.repository = FounderDnaRepository(db)
        self.engine = FounderDnaSelectionEngine(self.repository)
        self.advisor = advisor

    # --- Public API ---

    def current_state(
        self, founder: Founders
    ) -> tuple[FounderDnaQuestions | None, bool]:
        """(question, is_complete) for whatever the founder should see right
        now -- read-only, creates nothing (mirrors DiagnosisService's
        GET /current not implicitly starting anything)."""
        if founder.founder_dna_completed_at is not None:
            return None, True

        stage_group = resolve_founder_dna_stage_group(founder)
        if self.engine.is_phase_complete(founder, stage_group):
            return None, True
        return self.engine.select_next_question(founder, stage_group), False

    def start(self, founder: Founders) -> FounderDnaQuestions | None:
        """First (or next unanswered) question. Idempotent -- calling this on
        an already-in-progress founder just returns where they are, same as
        DiagnosisService.start_session's resume path."""
        question, is_complete = self.current_state(founder)
        if is_complete and founder.founder_dna_completed_at is None:
            self._complete(founder)
            self.db.commit()
        return question

    async def submit_answer(
        self, founder: Founders, question_id: int, answer_text: str
    ) -> tuple[FounderDnaQuestions | None, bool]:
        """Store an answer, judge resolution, and pick the next question.

        Returns (next_question, is_complete). Two commits, not one -- same
        reasoning as DiagnosisService.submit_answer: the answer is written
        and committed BEFORE the (optional) LLM resolution call, so a slow or
        failed advisor call never risks losing an already-given answer.
        """
        if founder.founder_dna_completed_at is not None:
            raise FounderDnaQuestionMismatchError(
                "The Founder DNA phase is already complete."
            )

        question = self.repository.get_question_by_id(question_id)
        if question is None:
            raise FounderDnaQuestionMismatchError(f"Question {question_id} does not exist.")

        stage_group = resolve_founder_dna_stage_group(founder)
        if question.stage_group != stage_group:
            raise FounderDnaQuestionMismatchError(
                "That question is not part of your current stage."
            )

        existing = self.repository.get_answer(founder.founder_id, question_id)
        if existing is not None:
            # Retry of an already-saved answer -- resume, don't duplicate.
            # Same recovery shape as DiagnosisService.submit_answer.
            logger.info(
                "Founder DNA answer already saved; resuming",
                extra={"founder_id": founder.founder_id, "question_id": question_id},
            )
        else:
            answer = FounderDnaAnswers(
                founder_id=founder.founder_id,
                founder_dna_question_id=question_id,
                answer_text=answer_text,
                answered_at=_utcnow(),
            )
            self.repository.add_answer(answer)
            try:
                self.db.commit()
            except IntegrityError as exc:
                self.db.rollback()
                existing = self.repository.get_answer(founder.founder_id, question_id)
                if existing is None:
                    logger.error(
                        "Integrity error saving Founder DNA answer",
                        extra={"founder_id": founder.founder_id},
                        exc_info=exc,
                    )
                    raise FounderDnaPersistenceError("Could not save the answer.")
            except SQLAlchemyError as exc:
                self.db.rollback()
                logger.error(
                    "Database error saving Founder DNA answer",
                    extra={"founder_id": founder.founder_id},
                    exc_info=exc,
                )
                raise FounderDnaPersistenceError("Could not save the answer.")

        await self._maybe_resolve(founder, question.dimension_code, stage_group)

        try:
            if self.engine.is_phase_complete(founder, stage_group):
                self._complete(founder)
                self.db.commit()
                return None, True

            next_question = self.engine.select_next_question(founder, stage_group)
            self.db.commit()
            return next_question, False
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "Database error saving Founder DNA progress",
                extra={"founder_id": founder.founder_id},
                exc_info=exc,
            )
            raise FounderDnaPersistenceError("Could not save your progress. Please try again.")

    # --- Internals ---

    async def _maybe_resolve(
        self, founder: Founders, dimension_code: str, stage_group: str
    ) -> None:
        """Ask the advisor whether `dimension_code` is resolved now, unless
        it's already resolved, hasn't hit the minimum-questions floor yet, or
        no advisor is wired (deterministic mode -- pool exhaustion is the
        only stop). Never raises: an advisor failure just leaves the
        dimension open, same fail-open contract as the diagnosis advisor.
        """
        resolved = self.repository.get_resolved_dimensions(founder)
        if dimension_code in resolved:
            return

        answered = self.repository.answers_per_dimension(founder.founder_id, stage_group)
        if answered.get(dimension_code, 0) < settings.FOUNDER_DNA_MIN_QUESTIONS_PER_DIMENSION:
            return

        if self.engine.dimension_pool_exhausted(founder, dimension_code, stage_group):
            # No more questions left for this dimension regardless of what
            # the advisor would say -- mark it resolved so is_phase_complete
            # and select_next_question agree it's done.
            self.repository.mark_dimension_resolved(founder, dimension_code)
            return

        if self.advisor is None:
            return

        history = self.repository.recent_qa_for_dimension(
            founder.founder_id, dimension_code, stage_group
        )
        try:
            verdict = await self.advisor.judge(
                dimension_code=dimension_code, qa_history=history
            )
        except Exception as exc:  # advisor must never break the flow
            logger.warning(
                "founder DNA resolution advisor raised; leaving dimension open",
                extra={"founder_id": founder.founder_id, "dimension": dimension_code},
                exc_info=exc,
            )
            return

        if verdict is not None and verdict.resolved:
            self.repository.mark_dimension_resolved(founder, dimension_code)

    def _complete(self, founder: Founders) -> None:
        self.repository.mark_phase_complete(founder, _utcnow())
