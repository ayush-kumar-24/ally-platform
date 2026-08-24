"""Database access for the Founder DNA phase.

Only builds and runs queries -- no business rules, no commits. Mirrors
app/api/v1/diagnosis/repository.py's shape and conventions.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy import text as _text
from sqlalchemy.orm import Session

from app.models.schema import FounderDnaAnswers, FounderDnaQuestions, Founders


class FounderDnaRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Locks ---

    def lock_founder_for_update(self, founder_id: int) -> None:
        """Row-level lock on one founder, held for the rest of this transaction.

        Mirrors DiagnosisRepository.lock_session_for_update, and exists for the
        same class of bug. `founder_dna_resolved_dimensions` is a JSONB array
        updated by read-modify-write (see mark_dimension_resolved): the whole
        list is read into Python, appended to, and written back. Two overlapping
        answers -- a double-click, or a client retry that overlapped the
        original -- each read the list BEFORE either had committed, so the
        second commit wrote its own one-element addition over the first's. One
        dimension's resolution was silently lost, which makes the phase re-ask a
        dimension the advisor had already closed and run longer than its budget
        intends.

        Deliberately taken immediately before that write rather than at the top
        of the request: everything above it is the resolution advisor's LLM
        call, and holding a transaction open across it is the exact failure the
        two-commit split in FounderDnaService.submit_answer exists to avoid
        (Supabase's pooler closes a connection left idle-in-transaction for tens
        of seconds). Scoped to one founder's row -- does not serialize unrelated
        founders against each other.
        """
        self.db.execute(
            _text("select founder_id from founders where founder_id = :f for update"),
            {"f": founder_id},
        )

    # --- Questions ---

    def get_question_by_id(self, question_id: int) -> FounderDnaQuestions | None:
        return self.db.get(FounderDnaQuestions, question_id)

    def list_candidate_questions(
        self, founder_id: int, stage_group: str
    ) -> list[FounderDnaQuestions]:
        """Every active question for this stage group, not yet answered by
        this founder. Unordered -- ordering is the engine's job, same
        division of responsibility as the diagnosis repository."""
        answered = select(FounderDnaAnswers.founder_dna_question_id).where(
            FounderDnaAnswers.founder_id == founder_id
        )
        stmt = select(FounderDnaQuestions).where(
            FounderDnaQuestions.is_active.is_(True),
            FounderDnaQuestions.stage_group == stage_group,
            FounderDnaQuestions.founder_dna_question_id.not_in(answered),
        )
        return list(self.db.execute(stmt).scalars().all())

    def closing_answered(self, founder_id: int, stage_group: str) -> bool:
        """True once this founder has answered the stage group's closing question.

        The engine cannot infer this from `list_candidate_questions`, which drops
        answered questions: a close that has been ASKED and a close that was
        never AUTHORED both show up there as simply absent. Without the
        distinction the selector kept handing out follow-ups after the closing
        question had already run, which is how a founder ended up getting the
        "one sentence from your future self" close and then another analytical
        question after it.
        """
        stmt = (
            select(FounderDnaAnswers.founder_dna_answer_id)
            .join(
                FounderDnaQuestions,
                FounderDnaQuestions.founder_dna_question_id
                == FounderDnaAnswers.founder_dna_question_id,
            )
            .where(
                FounderDnaAnswers.founder_id == founder_id,
                FounderDnaQuestions.stage_group == stage_group,
                FounderDnaQuestions.is_closing.is_(True),
            )
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first() is not None

    # --- Answers ---

    def get_answer(self, founder_id: int, question_id: int) -> FounderDnaAnswers | None:
        stmt = select(FounderDnaAnswers).where(
            FounderDnaAnswers.founder_id == founder_id,
            FounderDnaAnswers.founder_dna_question_id == question_id,
        )
        return self.db.execute(stmt).scalars().first()

    def add_answer(self, answer: FounderDnaAnswers) -> FounderDnaAnswers:
        self.db.add(answer)
        self.db.flush()
        return answer

    def count_answered(self, founder_id: int) -> int:
        stmt = select(FounderDnaAnswers.founder_dna_answer_id).where(
            FounderDnaAnswers.founder_id == founder_id
        )
        return len(self.db.execute(stmt).all())

    def answers_per_dimension(self, founder_id: int, stage_group: str) -> Counter[str]:
        """How many questions this founder has answered per dimension, within
        this stage group -- drives round-robin selection (least-answered
        unresolved dimension goes next) and pool-exhaustion detection."""
        stmt = (
            select(FounderDnaQuestions.dimension_code)
            .join(
                FounderDnaAnswers,
                FounderDnaAnswers.founder_dna_question_id
                == FounderDnaQuestions.founder_dna_question_id,
            )
            .where(
                FounderDnaAnswers.founder_id == founder_id,
                FounderDnaQuestions.stage_group == stage_group,
            )
        )
        return Counter(self.db.execute(stmt).scalars().all())

    def pool_size_per_dimension(self, stage_group: str) -> Counter[str]:
        """Total active question count per dimension for this stage group --
        the denominator for "has this dimension's pool run out"."""
        stmt = select(FounderDnaQuestions.dimension_code).where(
            FounderDnaQuestions.is_active.is_(True),
            FounderDnaQuestions.stage_group == stage_group,
        )
        return Counter(self.db.execute(stmt).scalars().all())

    def answered_history(self, founder_id: int) -> list[tuple[str, str, str, object]]:
        """Every (question_text, dimension_code, answer_text, answered_at) this
        founder has given, oldest first.

        Feeds the transcript on resume. Without it the page shows only the
        current question after a reload -- the answers are safe on the server
        but invisible, which reads as the conversation having been wiped. The
        diagnosis flow already solved this the same way; this is the Founder
        DNA equivalent.
        """
        stmt = (
            select(
                FounderDnaQuestions.question_text,
                FounderDnaQuestions.dimension_code,
                FounderDnaAnswers.answer_text,
                FounderDnaAnswers.answered_at,
            )
            .join(
                FounderDnaAnswers,
                FounderDnaAnswers.founder_dna_question_id
                == FounderDnaQuestions.founder_dna_question_id,
            )
            .where(FounderDnaAnswers.founder_id == founder_id)
            .order_by(FounderDnaAnswers.answered_at.asc())
        )
        return list(self.db.execute(stmt).all())

    def recent_qa_for_dimension(
        self, founder_id: int, dimension_code: str, stage_group: str, limit: int = 6
    ) -> list[tuple[str, str]]:
        """(question_text, answer_text) pairs for one dimension, oldest-first
        -- what the resolution advisor judges against."""
        stmt = (
            select(FounderDnaQuestions.question_text, FounderDnaAnswers.answer_text)
            .join(
                FounderDnaAnswers,
                FounderDnaAnswers.founder_dna_question_id
                == FounderDnaQuestions.founder_dna_question_id,
            )
            .where(
                FounderDnaAnswers.founder_id == founder_id,
                FounderDnaQuestions.dimension_code == dimension_code,
                FounderDnaQuestions.stage_group == stage_group,
            )
            .order_by(FounderDnaAnswers.answered_at.desc())
            .limit(limit)
        )
        rows = self.db.execute(stmt).all()
        return [(qt, at) for qt, at in reversed(rows)]

    # --- Founder progress markers ---

    def get_resolved_dimensions(self, founder: Founders) -> set[str]:
        return set(founder.founder_dna_resolved_dimensions or [])

    def mark_dimension_resolved(self, founder: Founders, dimension_code: str) -> None:
        current = list(founder.founder_dna_resolved_dimensions or [])
        if dimension_code not in current:
            current.append(dimension_code)
            founder.founder_dna_resolved_dimensions = current

    def mark_phase_complete(self, founder: Founders, completed_at) -> None:
        founder.founder_dna_completed_at = completed_at
