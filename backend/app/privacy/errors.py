"""Errors for the Privacy module. Extend the shared AppError so failures map to
precise HTTP responses via the global handler and fail closed."""

from app.middleware.error_handler import AppError


class PrivacyError(AppError):
    """Base for privacy/data-rights failures."""


class DeletionAlreadyRequestedError(PrivacyError):
    """A deletion is already scheduled -- re-requesting must not silently reset the
    clock, which would let a repeated call postpone erasure indefinitely."""

    def __init__(self, scheduled_at):
        super().__init__(
            f"Account deletion is already scheduled for {scheduled_at:%Y-%m-%d}.",
            status_code=409,
        )


class FounderNotFoundError(PrivacyError):
    def __init__(self, founder_id: int):
        super().__init__(f"No founder {founder_id} exists.", status_code=404)


class NoDeletionPendingError(PrivacyError):
    """Cancelling requires a deletion actually in flight -- otherwise "cancel" is
    meaningless and the caller likely mis-read the founder's state."""

    def __init__(self, founder_id: int):
        super().__init__(f"Founder {founder_id} has no pending deletion to cancel.",
                         status_code=409)
