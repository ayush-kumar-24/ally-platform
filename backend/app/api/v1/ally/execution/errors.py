"""Errors for the AI Execution Layer. No generic exceptions escape the package.

Provider failures and timeouts are handled by the service as fail-closed EMPTY
responses (not raised). Response-validation problems are the exception the Parser
raises -- the service converts them to an empty response too, but they exist as
typed errors so the Parser is testable in isolation.
"""

from fastapi import status

from app.middleware.error_handler import AppError


class ExecutionError(AppError):
    """Base for AI execution-layer errors."""


class ResponseValidationError(ExecutionError):
    """The provider returned something, but it is not a valid AI response."""

    def __init__(self, message: str):
        super().__init__(message, status_code=status.HTTP_502_BAD_GATEWAY)


class InvalidResponseJSONError(ResponseValidationError):
    """The provider response body was not valid JSON."""


class MissingResponseFieldError(ResponseValidationError):
    """A required field was absent from the response body."""


class InvalidResponseFieldError(ResponseValidationError):
    """A field was present but malformed (bad confidence, type, citations, usage)."""
