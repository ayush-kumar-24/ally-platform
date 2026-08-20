"""Framework Usage errors. AppError subclasses -> mapped to consistent JSON."""

from app.middleware.error_handler import AppError


class FrameworkUsageError(AppError):
    """Base for framework-usage failures."""


class InvalidFrameworkUsageInputError(FrameworkUsageError):
    def __init__(self, field: str, reason: str):
        super().__init__(f"Invalid {field}: {reason}.", status_code=422)
