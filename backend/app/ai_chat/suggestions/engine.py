"""SuggestionEngine (Phase 6, Milestone 5, Part 2).

Runs the deterministic rule set over a SuggestionContext and materializes the drafts
into Suggestions (assigning id + timestamp). It NEVER executes actions and NEVER
calls an LLM -- it only produces structured proposals. Ranking is a separate step.
"""

from __future__ import annotations

import uuid
from typing import Callable, Sequence

from app.ai_chat.clock import Clock, SystemClock
from app.ai_chat.suggestions.rules import DEFAULT_RULES
from app.ai_chat.suggestions.schemas import Suggestion, SuggestionContext, SuggestionStatus


class SuggestionEngine:
    def __init__(
        self,
        rules: Sequence[Callable[[SuggestionContext], list]] | None = None,
        *,
        clock: Clock | None = None,
        id_factory: Callable[[], str] | None = None,
    ):
        self.rules = tuple(rules) if rules is not None else DEFAULT_RULES
        self.clock = clock or SystemClock()
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)

    def generate(self, context: SuggestionContext) -> tuple[list[Suggestion], tuple[str, ...]]:
        """Return (raw suggestions, names of the rules that fired). Deterministic:
        rules run in a fixed order; a single generation timestamp is used."""
        now = self.clock.now()
        suggestions: list[Suggestion] = []
        fired: list[str] = []
        for rule in self.rules:
            drafts = rule(context)
            if not drafts:
                continue
            fired.append(rule.__name__)
            for draft in drafts:
                suggestions.append(Suggestion(
                    suggestion_id=self._new_id(),
                    conversation_id=context.conversation.conversation_id,
                    founder_id=context.founder_id,
                    suggestion_type=draft.suggestion_type,
                    title=draft.title,
                    body=draft.body,
                    priority=draft.priority,
                    source=draft.source,
                    reason=draft.reason,
                    dedup_key=draft.dedup_key,
                    created_at=now,
                    updated_at=now,
                    status=SuggestionStatus.ACTIVE,
                    relevance_score=draft.base_relevance,
                ))
        return suggestions, tuple(fired)
