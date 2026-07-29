"""Admin & Operations module (Phase 12) -- an independent, repository-driven admin
backend for internal GoXL operators.

Composes existing data through read-only seams (AdminRepository) and owns only admin
records (announcements, append-only audit). Role-gated (READ_ONLY / OPERATOR / ADMIN)
via an email allowlist over the existing auth. Deterministic + testable offline
(in-memory repos); a production adapter reads the DB + ai_chat stores.

Modifies no existing module.
"""

from app.admin.audit import AuditRepository, InMemoryAuditRepository
from app.admin.errors import (
    AdminError,
    AdminForbiddenError,
    AdminFounderNotFoundError,
    InvalidAnnouncementError,
    InvalidSearchError,
    UnauthorizedAdminError,
)
from app.admin.models import (
    AdminRole,
    AdminUser,
    Announcement,
    AuditEvent,
    ConversationSummary,
    FeedbackSummary,
    FounderStatus,
    FounderSummary,
    SystemStats,
    UsageMetrics,
)
from app.admin.permissions import AdminPermissionService, AdminRegistry
from app.admin.repository import (
    AdminRepository,
    AnnouncementRepository,
    InMemoryAdminRepository,
    InMemoryAnnouncementRepository,
)
from app.admin.service import AdminService

__all__ = [
    # models
    "AdminUser", "AdminRole", "FounderStatus", "FounderSummary", "ConversationSummary",
    "FeedbackSummary", "UsageMetrics", "SystemStats", "Announcement", "AuditEvent",
    # permissions
    "AdminPermissionService", "AdminRegistry",
    # repositories
    "AdminRepository", "InMemoryAdminRepository",
    "AnnouncementRepository", "InMemoryAnnouncementRepository",
    "AuditRepository", "InMemoryAuditRepository",
    # service
    "AdminService",
    # errors
    "AdminError", "UnauthorizedAdminError", "AdminForbiddenError",
    "AdminFounderNotFoundError", "InvalidAnnouncementError", "InvalidSearchError",
]
