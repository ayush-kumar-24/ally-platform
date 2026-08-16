"""Privacy Center -- data-subject rights (access, portability, erasure,
withdrawal, restriction).

Public surface (import from here, not from submodules):

    ExportBundle / PrivacyState / PrivacyAction   frozen domain DTOs
    PrivacyService                                business rules
    build_privacy_service()                       factory
    PrivacyRepository                             persistence seam

Scope: this module owns the *exercise* of rights. The record of consent given lives
in `app.consents`; the request audit trail reuses the existing `privacy_requests`
table. Neither is duplicated here.
"""

from app.privacy.errors import (
    DeletionAlreadyRequestedError,
    FounderNotFoundError,
    NoDeletionPendingError,
    PrivacyError,
)
from app.privacy.models import ExportBundle, PrivacyAction, PrivacyState
from app.privacy.repository import InMemoryPrivacyRepository, PrivacyRepository
from app.privacy.service import (
    DELETION_GRACE_DAYS,
    DSAR_DUE_DAYS,
    PrivacyService,
    build_privacy_service,
)

__all__ = [
    "DELETION_GRACE_DAYS",
    "DSAR_DUE_DAYS",
    "DeletionAlreadyRequestedError",
    "ExportBundle",
    "FounderNotFoundError",
    "InMemoryPrivacyRepository",
    "NoDeletionPendingError",
    "PrivacyAction",
    "PrivacyError",
    "PrivacyRepository",
    "PrivacyService",
    "PrivacyState",
    "build_privacy_service",
]
