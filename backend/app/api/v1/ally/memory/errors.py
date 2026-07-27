"""Errors for the Founder Memory Layer."""

from app.middleware.error_handler import AppError


class MemoryError(AppError):
    """Base for memory-layer errors."""


class InvalidMemoryError(MemoryError):
    """A memory could not be stored/updated because it is malformed (empty
    content, importance out of range, bad founder id). Fail-closed -- the layer
    never stores or fabricates an invalid memory."""

    def __init__(self, message: str):
        super().__init__(message, status_code=422)
