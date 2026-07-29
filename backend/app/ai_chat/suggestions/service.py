"""SuggestionService (Phase 6, Milestone 5, Parts 2/4/5/6).

Orchestrates: build context -> engine.generate -> ranking.rank -> persist -> return a
ranked SuggestionCollection. Also manages feedback (metadata only -- never changes AI
behaviour) and the suggestion lifecycle (archive/restore/delete/list/history).

Composition only: it consumes existing artifacts (conversation, context window, AI
response, attachments, links) and never re-implements chat/attachment/link logic.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Callable

from app.ai_chat.clock import Clock, SystemClock
from app.ai_chat.suggestions.engine import SuggestionEngine
from app.ai_chat.suggestions.errors import SuggestionNotFoundError
from app.ai_chat.suggestions.ranking import SuggestionRankingService
from app.ai_chat.suggestions.repository import SuggestionRepository
from app.ai_chat.suggestions.schemas import (
    Suggestion,
    SuggestionCollection,
    SuggestionContext,
    SuggestionFeedback,
    SuggestionFeedbackType,
    SuggestionMetrics,
    SuggestionStatus,
    SuggestionTrace,
)

_ACTIVE = SuggestionStatus.ACTIVE
_ARCHIVED = SuggestionStatus.ARCHIVED
_DELETED = SuggestionStatus.DELETED


class SuggestionServiceConfig:
    def __init__(self, *, max_suggestions: int = 5):
        self.max_suggestions = max_suggestions


class SuggestionService:
    def __init__(
        self,
        repository: SuggestionRepository,
        *,
        engine: SuggestionEngine | None = None,
        ranking: SuggestionRankingService | None = None,
        clock: Clock | None = None,
        id_factory: Callable[[], str] | None = None,
        config: SuggestionServiceConfig | None = None,
    ):
        self.repository = repository
        self.clock = clock or SystemClock()
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)
        self.config = config or SuggestionServiceConfig()
        self.engine = engine or SuggestionEngine(clock=self.clock, id_factory=self._new_id)
        self.ranking = ranking or SuggestionRankingService(max_suggestions=self.config.max_suggestions)

    # --- generation ------------------------------------------------------

    def generate_suggestions(
        self,
        conversation,
        *,
        context_window=None,
        ai_response=None,
        attachments: tuple = (),
        links: tuple = (),
        max_count: int | None = None,
    ) -> SuggestionCollection:
        context = SuggestionContext(
            conversation=conversation, context_window=context_window, ai_response=ai_response,
            attachments=tuple(attachments), links=tuple(links),
        )
        raw, fired = self.engine.generate(context)
        result = self.ranking.rank(raw, max_count=max_count or self.config.max_suggestions)

        for suggestion in result.ranked:
            self.repository.add(suggestion)               # persist surfaced suggestions

        generated_at = self.clock.now()
        metrics = SuggestionMetrics(
            generated=len(raw), suppressed_duplicates=result.suppressed_duplicates,
            returned=len(result.ranked), by_type=_count(result.ranked, lambda s: s.suggestion_type.value),
            by_priority=_count(result.ranked, lambda s: s.priority.value),
        )
        trace = SuggestionTrace(
            conversation_id=conversation.conversation_id, generated_at=generated_at,
            rules_fired=fired, generated=len(raw),
            suppressed=result.suppressed_duplicates, limited=result.limited,
        )
        return SuggestionCollection(
            conversation_id=conversation.conversation_id, founder_id=conversation.founder_id,
            suggestions=result.ranked, generated_at=generated_at, metrics=metrics, trace=trace,
        )

    # --- read ------------------------------------------------------------

    def get_suggestion(self, suggestion_id: str) -> Suggestion:
        return self._require(suggestion_id)

    def list_suggestions(
        self, conversation_id: str, *, include_archived: bool = False, include_deleted: bool = False
    ) -> tuple[Suggestion, ...]:
        statuses = [_ACTIVE]
        if include_archived:
            statuses.append(_ARCHIVED)
        if include_deleted:
            statuses.append(_DELETED)
        return self.repository.list_for_conversation(conversation_id, statuses=tuple(statuses))

    def history(self, conversation_id: str) -> tuple[Suggestion, ...]:
        return self.repository.list_for_conversation(
            conversation_id, statuses=(_ACTIVE, _ARCHIVED, _DELETED))

    # --- lifecycle -------------------------------------------------------

    def archive_suggestion(self, suggestion_id: str) -> Suggestion:
        return self._transition(suggestion_id, _ARCHIVED)

    def restore_suggestion(self, suggestion_id: str) -> Suggestion:
        return self._transition(suggestion_id, _ACTIVE)

    def delete_suggestion(self, suggestion_id: str) -> Suggestion:
        return self._transition(suggestion_id, _DELETED)

    # --- feedback (metadata only; never changes AI behaviour) ------------

    def record_feedback(
        self, suggestion_id: str, feedback_type: SuggestionFeedbackType, *, note: str | None = None
    ) -> SuggestionFeedback:
        suggestion = self._require(suggestion_id)
        now = self.clock.now()
        feedback = SuggestionFeedback(
            feedback_id=self._new_id(), suggestion_id=suggestion_id,
            founder_id=suggestion.founder_id, feedback_type=feedback_type,
            created_at=now, note=note,
        )
        self.repository.add_feedback(feedback)
        self.repository.replace(replace(suggestion, feedback=feedback_type, updated_at=now))
        return feedback

    def feedback_history(self, suggestion_id: str) -> tuple[SuggestionFeedback, ...]:
        self._require(suggestion_id)
        return self.repository.list_feedback(suggestion_id)

    # --- internals -------------------------------------------------------

    def _require(self, suggestion_id: str) -> Suggestion:
        suggestion = self.repository.get(suggestion_id)
        if suggestion is None:
            raise SuggestionNotFoundError(suggestion_id)
        return suggestion

    def _transition(self, suggestion_id: str, target: SuggestionStatus) -> Suggestion:
        suggestion = self._require(suggestion_id)
        if suggestion.status == target:
            return suggestion
        updated = replace(suggestion, status=target, updated_at=self.clock.now())
        self.repository.replace(updated)
        return updated


def _count(items, key) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        out[key(item)] = out.get(key(item), 0) + 1
    return out


def build_suggestion_service(
    repository: SuggestionRepository | None = None,
    *,
    clock: Clock | None = None,
    id_factory: Callable[[], str] | None = None,
    config: SuggestionServiceConfig | None = None,
) -> SuggestionService:
    from app.ai_chat.suggestions.repository import InMemorySuggestionRepository

    return SuggestionService(repository or InMemorySuggestionRepository(),
                             clock=clock, id_factory=id_factory, config=config)
