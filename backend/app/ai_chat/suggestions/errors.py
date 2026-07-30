"""Suggestion errors (Phase 6, Milestone 5)."""

from fastapi import status

from app.ai_chat.errors import ChatError


class SuggestionError(ChatError):
    """Base for suggestion failures."""


class SuggestionNotFoundError(SuggestionError):
    def __init__(self, suggestion_id: str):
        super().__init__(f"Suggestion '{suggestion_id}' was not found.",
                         status_code=status.HTTP_404_NOT_FOUND)
