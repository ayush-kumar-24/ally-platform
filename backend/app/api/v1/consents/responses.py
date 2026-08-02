"""Response models for the consents endpoints.

Strongly-typed Pydantic boundary models with `from_domain` mappers -- the domain
dataclasses never touch the wire.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.consents.models import ConsentRecord


class ConsentResponse(BaseModel):
    consent_id: str
    founder_id: int
    terms_version: str
    privacy_version: str
    agree_terms: bool
    agree_diagnosis: bool
    consented_at: datetime

    @classmethod
    def from_domain(cls, r: ConsentRecord) -> "ConsentResponse":
        return cls(
            consent_id=r.consent_id,
            founder_id=r.founder_id,
            terms_version=r.terms_version,
            privacy_version=r.privacy_version,
            agree_terms=r.agree_terms,
            agree_diagnosis=r.agree_diagnosis,
            consented_at=r.consented_at,
        )


class ConsentStatusResponse(BaseModel):
    """What GET /consents returns: the current state plus the full audit trail.

    `current` is null for a founder who has never consented -- the endpoint returns
    200 with that null rather than 404, because "has this founder consented?" is a
    legitimate question with a legitimate negative answer, and the frontend needs
    to branch on it without treating it as an error.
    """

    has_consented: bool
    needs_reconsent: bool
    current_terms_version: str
    current_privacy_version: str
    current: ConsentResponse | None
    history: list[ConsentResponse]
    total: int
