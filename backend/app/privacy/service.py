"""PrivacyService -- the data-subject rights engine.

Repository-driven and deterministic (injected clock), so the hermetic suite can
assert exact dates. The API layer maps HTTP to these calls and holds no logic.

Four rights, four deliberate designs:

* **Export** (Art 15 + 20) is served *immediately* rather than queued. The founder
  already has the right; making them wait 30 days for data we can assemble in a
  request is friction with no legal upside. The request is still logged, because
  Art 5(2) accountability means we must be able to show what was disclosed and when.

* **Erasure** (Art 17) is SCHEDULED, never an instant purge. A single HTTP call that
  irreversibly destroys an account is a footgun: one mis-click, one stolen session,
  one bug, and the data is gone with no recovery. A grace window makes the deletion
  real but recoverable, which is also what "without undue delay" permits. Re-calling
  is refused rather than silently resetting the clock -- otherwise a repeated call
  could postpone erasure forever, defeating the right it implements.

* **Withdrawal** (Art 7(3)) is NOT erasure and is deliberately kept separate. Pulling
  consent stops future processing that relied on it; it does not by itself destroy
  records the controller keeps on another lawful basis. Conflating the two would
  either under-deliver (withdraw that doesn't stop processing) or over-deliver
  (withdraw that unexpectedly deletes the account). Withdrawing also restricts
  processing immediately, so the pause takes effect at once rather than at whatever
  time an operator gets to the queue.

* **Restriction** (Art 18) is a reversible toggle -- restriction is explicitly a
  pause, not a termination, so lifting it must be possible from the same endpoint.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from app.privacy.errors import DeletionAlreadyRequestedError
from app.privacy.models import DataSummary, ExportBundle, PrivacyAction, PrivacyState
from app.privacy.repository import PrivacyRepository

# GDPR Art 12(3): respond to a request within one month.
DSAR_DUE_DAYS = 30
# Recovery window before an erasure request is actually executed.
DELETION_GRACE_DAYS = 30


class PrivacyService:
    def __init__(
        self,
        repository: PrivacyRepository,
        *,
        clock: Callable[[], datetime] | None = None,
        consent_service=None,
    ):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))
        # Optional: when present, withdrawal is also written to the consent ledger
        # so the consent history and the privacy log agree with each other.
        self._consents = consent_service

    # --- Art 15 + 20: access / portability --------------------------------

    def export_data(self, founder_id: int,
                    kind: str = "access") -> tuple[ExportBundle, PrivacyAction]:
        """Assemble the founder's data now and log the disclosure.

        `kind` picks which of the two rights is being exercised: "access" hands
        back everything held, "portability" only what the founder provided. Both
        were previously the same call logged as `portability`, so a right-of-access
        download was recorded in the audit trail as a portability request.
        """
        if kind not in ("access", "portability"):
            kind = "access"
        now = self._now()
        bundle = self.repository.gather_export(founder_id, now, kind=kind)
        action = self.repository.log_request(
            founder_id,
            request_type="portability" if kind == "portability" else "download_data",
            details=("Self-service portability export downloaded" if kind == "portability"
                     else "Self-service data export downloaded"),
            at=now, due_by=None)
        return bundle, action

    def data_summary(self, founder_id: int) -> tuple[DataSummary, PrivacyAction]:
        """What "View data summary" actually does now: counts per category from
        the same gather_export a full export uses, no raw rows returned. No
        email is sent -- there is no delivery step to wait on, so unlike
        view_data/correct_data's original design (a queued admin request this
        codebase had no way to ever resolve or deliver), this answers
        immediately, the same way export_data already does.
        """
        now = self._now()
        bundle = self.repository.gather_export(founder_id, now)
        counts = {label: (len(rows) if isinstance(rows, list) else 0)
                 for label, rows in bundle.sections.items()}
        summary = DataSummary(founder_id=founder_id, generated_at=now, counts=counts)
        action = self.repository.log_request(
            founder_id, request_type="view_data", details="Self-service summary viewed",
            at=now, due_by=None)
        return summary, action

    # --- Art 17: erasure ---------------------------------------------------

    def request_account_deletion(self, founder_id: int) -> tuple[PrivacyState, PrivacyAction]:
        """Schedule erasure after a grace window. Refuses if one is already pending."""
        state = self.repository.get_state(founder_id)
        if state.deletion_requested_at is not None:
            raise DeletionAlreadyRequestedError(state.deletion_scheduled_at or state.deletion_requested_at)

        now = self._now()
        scheduled = now + timedelta(days=DELETION_GRACE_DAYS)
        new_state = self.repository.schedule_deletion(
            founder_id, requested_at=now, scheduled_at=scheduled)
        action = self.repository.log_request(
            founder_id, request_type="delete_account",
            details=f"Account erasure requested; scheduled for {scheduled:%Y-%m-%d}",
            at=now, due_by=scheduled)
        return new_state, action

    def cancel_account_deletion(self, founder_id: int) -> tuple[PrivacyState, PrivacyAction]:
        """Undo a scheduled erasure while it is still inside the grace window.

        The 30-day window exists so an erasure request is recoverable, but until
        now only an admin could recover it (admin panel cancel-deletion) -- a
        founder who mis-clicked had no way back and, because may_process() gates
        on deletion_pending, silently lost every AI feature for those 30 days.
        A recovery window nobody can reach is not a recovery window.

        Refuses once the sweep has run (NoDeletionToCancelError from the
        repository): after deletion_executed_at is set there is nothing left to
        restore, and pretending otherwise would be worse than refusing.
        """
        now = self._now()
        state = self.repository.cancel_deletion(founder_id)
        action = self.repository.log_request(
            founder_id, request_type="cancel_deletion",
            details="Account deletion cancelled by the founder",
            at=now, due_by=None)
        return state, action

    # --- Art 7(3): withdraw consent ---------------------------------------

    def withdraw_consent(self, founder_id: int) -> tuple[PrivacyState, PrivacyAction]:
        """Revoke the optional processing consent and pause processing immediately.

        Does NOT delete the account -- that is request_account_deletion.
        """
        now = self._now()
        if self._consents is not None:
            current = self._consents.get_current(founder_id)
            if current is not None:
                # Append a new ledger entry turning the diagnosis opt-in off. The
                # prior grant survives as evidence of what was true before.
                self._consents.record_consent(
                    founder_id,
                    terms_version=current.terms_version,
                    privacy_version=current.privacy_version,
                    agree_terms=True,
                    agree_diagnosis=False,
                )
        state = self.repository.set_restriction(founder_id, restricted=True, at=now)
        action = self.repository.log_request(
            founder_id, request_type="withdraw_consent",
            details="Consent withdrawn; AI processing paused",
            at=now, due_by=now + timedelta(days=DSAR_DUE_DAYS))
        return state, action

    # --- Art 18: restriction of processing --------------------------------

    def restrict_processing(self, founder_id: int, *, restricted: bool = True
                            ) -> tuple[PrivacyState, PrivacyAction]:
        """Pause (or resume) AI profiling without touching the account."""
        now = self._now()
        state = self.repository.set_restriction(founder_id, restricted=restricted, at=now)
        action = self.repository.log_request(
            founder_id, request_type="restrict_processing",
            details="Processing restricted" if restricted else "Restriction lifted",
            at=now, due_by=now + timedelta(days=DSAR_DUE_DAYS))
        return state, action

    # --- reads -------------------------------------------------------------

    def get_state(self, founder_id: int) -> PrivacyState:
        return self.repository.get_state(founder_id)

    def list_requests(self, founder_id: int) -> list[PrivacyAction]:
        return self.repository.list_requests(founder_id)

    def may_process(self, founder_id: int) -> bool:
        """Lawful-basis gate for AI processing. Fails closed: restricted or
        pending-deletion founders are not processed."""
        state = self.repository.get_state(founder_id)
        return not state.processing_restricted and not state.deletion_pending


def build_privacy_service(
    repository: PrivacyRepository | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    consent_service=None,
) -> PrivacyService:
    from app.privacy.repository import InMemoryPrivacyRepository

    return PrivacyService(repository or InMemoryPrivacyRepository(),
                          clock=clock, consent_service=consent_service)
