"""Errors for the Ally context layer."""

from fastapi import status

from app.middleware.error_handler import AppError


class AllyContextError(AppError):
    """Base for context-assembly errors."""


class FounderNotFoundError(AllyContextError):
    """No founder row exists for the requested id. Distinct from 'no diagnosis
    yet' -- a missing founder is a 404, a founder without a diagnosis is a valid
    (but not answerable) context, not an error."""

    def __init__(self, message: str = "No founder exists for this identity."):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)
