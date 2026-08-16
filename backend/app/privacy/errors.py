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


# MERGE ARTEFACT -- needs a decision, see below.
#
# Two account-deletion implementations were developed in parallel: origin/main's
# reviewed "unified account-deletion pipeline" (d1d1992), which raises
# NoDeletionToCancelError, and an unreviewed local one (privacy/executor.py and
# privacy/deletion_repository.py, neither of which exists upstream) which raises
# NoDeletionPendingError from privacy/service.py and tests/test_privacy_executor.py.
#
# The merge kept both, so the module imported a name the reviewed errors.py does
# not define and the whole app failed at import. This alias is the smallest thing
# that makes the tree run WITHOUT deleting anyone's work -- it is not a design
# decision, and the duplicate pipelines still need to be reconciled by whoever
# owns the DPDP deletion path. Remove this alias once that is settled.
NoDeletionPendingError = NoDeletionToCancelError
