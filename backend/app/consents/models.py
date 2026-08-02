"""Domain DTOs for the Consents module.

Immutable frozen dataclasses -- the service returns these (never ORM rows), so the
persistence layer can be swapped (in-memory <-> SQLAlchemy) without touching the
service or the API.

Why a LEDGER and not a single mutable row: GDPR Art 7(1) requires the controller to
*demonstrate* that consent was given -- which version of the Terms/Privacy Policy,
with which options, at what moment. A row you overwrite destroys that evidence. So
every grant (and every change, e.g. withdrawing the optional diagnosis consent) is
appended as a new immutable record. The current state is simply the newest record.
This mirrors the append-only patterns already in the codebase (admin audit log,
founder memory events).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ConsentRecord:
    """One immutable consent event for one founder."""

    consent_id: str
    founder_id: int

    # Which documents were shown. Versioned so a later policy update can be
    # detected as "needs re-consent" by comparing against the current versions.
    terms_version: str
    privacy_version: str

    # The two checkboxes. `agree_terms` is the mandatory gate (Terms + Privacy);
    # `agree_diagnosis` is the separate, unbundled opt-in for processing business
    # diagnostic data -- unbundled because GDPR Art 7(2)/(4) forbids tying an
    # optional processing purpose to access.
    agree_terms: bool
    agree_diagnosis: bool

    # Server-stamped. Never taken from the client -- see service.record_consent.
    consented_at: datetime
