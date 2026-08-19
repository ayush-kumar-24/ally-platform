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


class NoDeletionToCancelError(PrivacyError):
    """Nothing pending: either never requested, or the sweep already ran --
    cancelling after execution would be a no-op that reads like it undid
    something it cannot actually undo."""

    def __init__(self, founder_id: int):
        super().__init__(
            f"Founder {founder_id} has no pending deletion to cancel.",
            status_code=409,
        )


class PrivacyRequestNotFoundError(PrivacyError):
    """No privacy_requests row with this id -- distinct from FounderNotFoundError,
    which is about the founder, not the request."""

    def __init__(self, request_id: int):
        super().__init__(f"Privacy request {request_id} was not found.", status_code=404)


class InvalidPrivacyRequestStatusError(PrivacyError):
    """A resolution attempt with a status this workflow doesn't allow (only an
    admin may move a request to in_progress/completed/rejected; 'pending' is
    the only status a founder-initiated request may start in)."""

    def __init__(self, status: str):
        super().__init__(
            f"'{status}' is not a valid resolution status -- use "
            "in_progress, completed or rejected.",
            status_code=422,
        )


class ProcessingRestrictedError(PrivacyError):
    """Raised at every AI-processing entry point once a founder has withdrawn
    consent or requested restriction (PrivacyService.may_process() -> False).

    This is what makes "Restrict data processing" / "Withdraw consent" real:
    without it, the Privacy Center could tell a founder processing had paused
    while the diagnosis engine, Founder DNA engine and chat kept running
    exactly as before. 403, not 404/409 -- the founder did something
    deliberate (restricted themselves), this isn't a missing resource."""

    def __init__(self, founder_id: int):
        super().__init__(
            "AI processing is currently paused for this account (data processing "
            "was restricted or consent withdrawn). Resume processing from Privacy "
            "Center before starting a new session or sending a message.",
            status_code=403,
        )
