"""ConsentService -- the only place consent business rules live.

Repository-driven and deterministic (injected clock + id factory), so the hermetic
test suite can assert exact records. The API layer maps HTTP to these calls and
holds no logic of its own.

Three rules worth knowing:

1. `consented_at` is stamped by the SERVER, never taken from the request body. A
   client-supplied timestamp on a legal record is worthless -- it is trivially
   forged and unverifiable. The frontend still sends its local time; it is ignored.
2. `agree_terms=false` is refused (TermsNotAcceptedError) rather than stored. The
   ledger records consent that WAS given; a refusal is simply the absence of a
   record. Withdrawing the *optional* diagnosis consent is expressed by appending a
   new record with `agree_diagnosis=false`, which preserves the history.
3. Re-posting an identical consent is idempotent: the existing record is returned
   and nothing is appended. This is the server-side half of duplicate-submission
   protection (the client guard is the other half) and keeps the ledger free of
   double-click noise, without ever suppressing a genuine *change* of consent.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable

from app.consents.defaults import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION
from app.consents.errors import TermsNotAcceptedError
from app.consents.models import ConsentRecord
from app.consents.repository import ConsentRepository
from app.consents.validators import validate_version


class ConsentService:
    def __init__(
        self,
        repository: ConsentRepository,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ):
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)

    # --- write ------------------------------------------------------------

    def record_consent(
        self,
        founder_id: int,
        *,
        terms_version: str,
        privacy_version: str,
        agree_terms: bool,
        agree_diagnosis: bool = False,
    ) -> tuple[ConsentRecord, bool]:
        """Append a consent record. Returns (record, created).

        `created` is False when this exactly repeats the founder's current consent,
        in which case the existing record is returned untouched.
        """
        if not agree_terms:
            raise TermsNotAcceptedError()

        terms = validate_version(terms_version, "terms_version")
        privacy = validate_version(privacy_version, "privacy_version")

        current = self.repository.latest(founder_id)
        if current is not None and (
            current.terms_version == terms
            and current.privacy_version == privacy
            and current.agree_terms is True
            and current.agree_diagnosis == agree_diagnosis
        ):
            return current, False

        record = ConsentRecord(
            consent_id=self._new_id(),
            founder_id=founder_id,
            terms_version=terms,
            privacy_version=privacy,
            agree_terms=True,
            agree_diagnosis=agree_diagnosis,
            consented_at=self._now(),
        )
        return self.repository.add(record), True

    # --- read -------------------------------------------------------------

    def get_current(self, founder_id: int) -> ConsentRecord | None:
        """The founder's consent as it stands now, or None if never given."""
        return self.repository.latest(founder_id)

    def list_history(self, founder_id: int) -> list[ConsentRecord]:
        """Every consent event for the founder, newest first."""
        return self.repository.list_for_founder(founder_id)

    def has_consented(self, founder_id: int) -> bool:
        return self.repository.latest(founder_id) is not None

    def may_process_diagnosis_data(self, founder_id: int) -> bool:
        """The lawful-basis check for diagnosis processing. Fails closed: no record
        means no consent means no processing."""
        current = self.repository.latest(founder_id)
        return bool(current and current.agree_diagnosis)

    def needs_reconsent(self, founder_id: int) -> bool:
        """True when the founder has no consent, or consented to superseded
        document versions and must be re-prompted."""
        current = self.repository.latest(founder_id)
        if current is None:
            return True
        return (
            current.terms_version != CURRENT_TERMS_VERSION
            or current.privacy_version != CURRENT_PRIVACY_VERSION
        )


def build_consent_service(
    repository: ConsentRepository | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    id_factory: Callable[[], str] | None = None,
) -> ConsentService:
    """Factory. Defaults to the in-memory repository (tests/offline)."""
    from app.consents.repository import InMemoryConsentRepository

    return ConsentService(repository or InMemoryConsentRepository(),
                          clock=clock, id_factory=id_factory)
