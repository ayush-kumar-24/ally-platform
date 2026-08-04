"""SQL-backed SuggestionRepository -- persists to `suggestions` / `suggestion_feedback`.

Same fix, same shape as SqlConversationRepository / SqlAttachmentRepository: the
process-level InMemorySuggestionRepository singleton loses every AI-generated
suggestion and every founder's accept/dismiss feedback on restart/redeploy and
cannot be shared across worker processes.

Unlike conversations/file_uploads, these are brand-new tables (migration
e5a7b9c1d3f4), so the domain's own string ids (suggestion_id, feedback_id) are the
primary key directly -- no external_id indirection needed.

FAILS LOUD, not resilient-degrade -- same reasoning as the other two: this
repository IS the suggestion/feedback storage.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_chat.suggestions.repository import SuggestionRepository
from app.ai_chat.suggestions.schemas import (
    Suggestion,
    SuggestionFeedback,
    SuggestionFeedbackType,
    SuggestionPriority,
    SuggestionReason,
    SuggestionSource,
    SuggestionStatus,
    SuggestionType,
)
from app.models.suggestions import SuggestionFeedbackRow, SuggestionRow


class SqlSuggestionRepository(SuggestionRepository):
    def __init__(self, db: Session):
        self.db = db

    def add(self, suggestion: Suggestion) -> None:
        self.db.add(self._to_row(suggestion))
        self.db.flush()

    def get(self, suggestion_id: str) -> Suggestion | None:
        row = self._get_row(suggestion_id)
        return self._to_domain(row) if row is not None else None

    def replace(self, suggestion: Suggestion) -> None:
        row = self._get_row(suggestion.suggestion_id)
        if row is None:
            raise LookupError(f"suggestion {suggestion.suggestion_id!r} not found")
        row.status = suggestion.status.value
        row.feedback = suggestion.feedback.value
        row.updated_at = suggestion.updated_at
        row.relevance_score = suggestion.relevance_score
        row.rank = suggestion.rank
        row.meta_data = dict(suggestion.metadata)
        self.db.flush()

    def list_for_conversation(
        self, conversation_id: str, *, statuses: tuple[SuggestionStatus, ...]
    ) -> tuple[Suggestion, ...]:
        status_values = [s.value for s in statuses]
        stmt = (
            select(SuggestionRow)
            .where(SuggestionRow.conversation_id == conversation_id, SuggestionRow.status.in_(status_values))
        )
        rows = self.db.execute(stmt).scalars().all()
        found = [self._to_domain(r) for r in rows]
        # Deterministic: rank (if set) then creation time then id -- matches the
        # in-memory repository's ordering exactly.
        found.sort(key=lambda s: (s.rank if s.rank is not None else 1_000_000, s.created_at, s.suggestion_id))
        return tuple(found)

    def add_feedback(self, feedback: SuggestionFeedback) -> None:
        self.db.add(SuggestionFeedbackRow(
            feedback_id=feedback.feedback_id,
            suggestion_id=feedback.suggestion_id,
            founder_id=feedback.founder_id,
            feedback_type=feedback.feedback_type.value,
            created_at=feedback.created_at,
            note=feedback.note,
        ))
        self.db.flush()

    def list_feedback(self, suggestion_id: str) -> tuple[SuggestionFeedback, ...]:
        stmt = (
            select(SuggestionFeedbackRow)
            .where(SuggestionFeedbackRow.suggestion_id == suggestion_id)
            .order_by(SuggestionFeedbackRow.created_at.asc())
        )
        rows = self.db.execute(stmt).scalars().all()
        return tuple(
            SuggestionFeedback(
                feedback_id=r.feedback_id, suggestion_id=r.suggestion_id, founder_id=r.founder_id,
                feedback_type=SuggestionFeedbackType(r.feedback_type), created_at=r.created_at, note=r.note,
            )
            for r in rows
        )

    def purge(self, suggestion_id: str) -> bool:
        row = self._get_row(suggestion_id)
        if row is None:
            return False
        self.db.delete(row)  # ON DELETE CASCADE removes its feedback rows
        self.db.flush()
        return True

    # --- mapping helpers -----------------------------------------------

    def _get_row(self, suggestion_id: str) -> SuggestionRow | None:
        return self.db.execute(
            select(SuggestionRow).where(SuggestionRow.suggestion_id == suggestion_id)
        ).scalar_one_or_none()

    @staticmethod
    def _to_row(s: Suggestion) -> SuggestionRow:
        return SuggestionRow(
            suggestion_id=s.suggestion_id,
            conversation_id=s.conversation_id,
            founder_id=s.founder_id,
            suggestion_type=s.suggestion_type.value,
            title=s.title,
            body=s.body,
            priority=s.priority.value,
            source=s.source.value,
            reason_code=s.reason.code,
            reason_description=s.reason.description,
            dedup_key=s.dedup_key,
            created_at=s.created_at,
            updated_at=s.updated_at,
            status=s.status.value,
            feedback=s.feedback.value,
            relevance_score=s.relevance_score,
            rank=s.rank,
            meta_data=dict(s.metadata),
        )

    @staticmethod
    def _to_domain(row: SuggestionRow) -> Suggestion:
        return Suggestion(
            suggestion_id=row.suggestion_id,
            conversation_id=row.conversation_id,
            founder_id=row.founder_id,
            suggestion_type=SuggestionType(row.suggestion_type),
            title=row.title,
            body=row.body,
            priority=SuggestionPriority(row.priority),
            source=SuggestionSource(row.source),
            reason=SuggestionReason(code=row.reason_code, description=row.reason_description),
            dedup_key=row.dedup_key,
            created_at=row.created_at,
            updated_at=row.updated_at,
            status=SuggestionStatus(row.status),
            feedback=SuggestionFeedbackType(row.feedback),
            relevance_score=float(row.relevance_score),
            rank=row.rank,
            metadata=dict(row.meta_data or {}),
        )
