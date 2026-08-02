"""Errors for the Consents module. Extend the shared AppError so failures map to
precise HTTP responses via the global handler and fail closed."""

from fastapi import status

from app.middleware.error_handler import AppError


class ConsentError(AppError):
    """Base for consent failures."""


class InvalidConsentInputError(ConsentError):
    def __init__(self, reason: str):
        super().__init__(f"Invalid consent: {reason}.", status_code=422)


class TermsNotAcceptedError(ConsentError):
    """The mandatory Terms + Privacy gate was not accepted.

    Recording a consent record with `agree_terms=false` would be recording a
    consent that was never given, so the write is refused outright.
    """

    def __init__(self) -> None:
        super().__init__(
            "The Terms of Service and Privacy Policy must be accepted to continue.",
            status_code=422,
        )


class ConsentNotFoundError(ConsentError):
    def __init__(self, founder_id: int):
        super().__init__(f"No consent record exists for founder {founder_id}.",
                         status_code=status.HTTP_404_NOT_FOUND)
