"""Typed errors for the ai_chat layer.

Extends the shared AppError so failures map to precise HTTP responses and never
leak as generic 500s. The conversation engine fails closed: an operation on a
missing or wrong-state conversation raises here rather than silently no-op'ing.
"""

from fastapi import status

from app.middleware.error_handler import AppError


class ChatError(AppError):
    """Base for all ai_chat errors."""


class ConversationNotFoundError(ChatError):
    def __init__(self, conversation_id: str):
        super().__init__(
            f"Conversation '{conversation_id}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class InvalidConversationStateError(ChatError):
    """The conversation exists but is in a state that forbids the operation
    (e.g. appending to an archived or deleted conversation)."""

    def __init__(self, conversation_id: str, state: str, action: str):
        super().__init__(
            f"Cannot {action} conversation '{conversation_id}' while it is {state}.",
            status_code=status.HTTP_409_CONFLICT,
        )


class InvalidMessageError(ChatError):
    """A message failed validation (e.g. empty content). Fail closed."""

    def __init__(self, reason: str):
        super().__init__(f"Invalid message: {reason}.", status_code=422)
