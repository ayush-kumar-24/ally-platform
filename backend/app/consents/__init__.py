"""Consents -- the append-only record of what each founder agreed to, and when.

Public surface (import from here, not from submodules):

    ConsentRecord            frozen domain DTO -- one immutable consent event
    ConsentService           business rules; build_consent_service() to construct
    ConsentRepository        persistence seam (InMemory / SqlAlchemy)
    errors                   ConsentError and friends -> precise HTTP statuses

Scope: this module owns *evidence of consent* only. The privacy/data-rights
requests (export, erasure, restriction) live in the existing settings module under
`/settings/privacy`, and identity/credentials belong to the auth provider. Nothing
here is duplicated from those.
"""

from app.consents.defaults import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION
from app.consents.errors import (
    ConsentError,
    ConsentNotFoundError,
    InvalidConsentInputError,
    TermsNotAcceptedError,
)
from app.consents.models import ConsentRecord
from app.consents.repository import ConsentRepository, InMemoryConsentRepository
from app.consents.service import ConsentService, build_consent_service

__all__ = [
    "CURRENT_PRIVACY_VERSION",
    "CURRENT_TERMS_VERSION",
    "ConsentError",
    "ConsentNotFoundError",
    "ConsentRecord",
    "ConsentRepository",
    "ConsentService",
    "InMemoryConsentRepository",
    "InvalidConsentInputError",
    "TermsNotAcceptedError",
    "build_consent_service",
]
