"""Errors for the Settings module. Extend the shared AppError so failures map to
precise HTTP responses via the global handler and fail closed."""

from fastapi import status

from app.middleware.error_handler import AppError


class SettingsError(AppError):
    """Base for settings failures."""


class InvalidSettingError(SettingsError):
    def __init__(self, field: str, reason: str):
        super().__init__(f"Invalid setting '{field}': {reason}.", status_code=422)


class SettingsNotFoundError(SettingsError):
    def __init__(self, founder_id: int):
        super().__init__(f"Settings for founder {founder_id} were not found.",
                         status_code=status.HTTP_404_NOT_FOUND)
