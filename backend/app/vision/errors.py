"""Vision errors. AppError subclasses -> mapped to consistent JSON."""

from app.middleware.error_handler import AppError


class VisionError(AppError):
    """Base for vision failures."""


class InvalidVisionTerritoryError(VisionError):
    def __init__(self, territory: str):
        super().__init__(f"'{territory}' is not a recognized vision territory.", status_code=422)


class InvalidVisionInputError(VisionError):
    def __init__(self, field: str, reason: str):
        super().__init__(f"Invalid {field}: {reason}.", status_code=422)
