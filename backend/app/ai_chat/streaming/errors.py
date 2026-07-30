"""Streaming errors (Phase 6, Milestone 3, Part 6). Extend the ai_chat error tree."""

from app.ai_chat.errors import ChatError


class StreamingError(ChatError):
    """Base for streaming failures."""


class StreamingCancelled(StreamingError):
    """The stream was cancelled (client disconnect or manual cancel). No assistant
    message is persisted."""

    def __init__(self, request_id: str):
        super().__init__(f"Streaming cancelled for request '{request_id}'.", status_code=499)


class StreamingTimeout(StreamingError):
    """The stream exceeded its deadline. No assistant message is persisted."""

    def __init__(self, request_id: str, seconds: float):
        super().__init__(
            f"Streaming timed out after {seconds}s for request '{request_id}'.",
            status_code=504,
        )
