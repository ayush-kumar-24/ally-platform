"""AdminService (Phase 12, Parts 3/4/5).

Composes the admin/announcement/audit repositories, enforces role permissions on
every call, and appends an audit event for every mutating admin action. Deterministic
(injected clock + id_factory). No business logic from other modules is duplicated --
it reads through the AdminRepository seam and writes only admin-owned records.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.admin.audit import AuditRepository
from app.admin.errors import AdminFounderNotFoundError
from app.admin.models import (
    AdminUser,
    Announcement,
    AuditEvent,
    FounderStatus,
    SystemStats,
)
from app.admin.permissions import AdminPermissionService
from app.admin.repository import AdminRepository, AnnouncementRepository
from app.admin.validators import validate_announcement, validate_search_query

_NEW_FOUNDER_DAYS = 7


class AdminService:
    def __init__(
        self,
        *,
        admin_repository: AdminRepository,
        announcement_repository: AnnouncementRepository,
        audit_repository: AuditRepository,
        permissions: AdminPermissionService | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ):
        self.admin_repository = admin_repository
        self.announcement_repository = announcement_repository
        self.audit_repository = audit_repository
        self.permissions = permissions or AdminPermissionService()
        self._now = clock or (lambda: datetime.now(timezone.utc))
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)

    # --- founders --------------------------------------------------------

    def list_founders(self, admin: AdminUser, *, limit: int = 50, offset: int = 0):
        self.permissions.require_read(admin)
        return self.admin_repository.list_founders(limit=limit, offset=offset)

    def search_founders(self, admin: AdminUser, query: str, *, limit: int = 50):
        self.permissions.require_read(admin)
        return self.admin_repository.search_founders(validate_search_query(query), limit=limit)

    def get_founder(self, admin: AdminUser, founder_id: int):
        self.permissions.require_read(admin)
        founder = self.admin_repository.get_founder(founder_id)
        if founder is None:
            raise AdminFounderNotFoundError(founder_id)
        return founder

    def suspend_founder(self, admin: AdminUser, founder_id: int, *, reason: str | None = None):
        return self._set_status(admin, founder_id, FounderStatus.SUSPENDED, "suspend_founder", reason)

    def restore_founder(self, admin: AdminUser, founder_id: int, *, reason: str | None = None):
        return self._set_status(admin, founder_id, FounderStatus.ACTIVE, "restore_founder", reason)

    def _set_status(self, admin, founder_id, status, action, reason):
        self.permissions.require_manage_founders(admin)
        if self.admin_repository.get_founder(founder_id) is None:
            self._audit(admin, action, f"founder:{founder_id}", "failure", reason)
            raise AdminFounderNotFoundError(founder_id)
        updated = self.admin_repository.set_founder_status(founder_id, status)
        self._audit(admin, action, f"founder:{founder_id}", "success", reason)
        return updated

    # --- conversations / feedback ----------------------------------------

    def list_conversations(self, admin: AdminUser, *, founder_id: int | None = None,
                           limit: int = 50, offset: int = 0):
        self.permissions.require_read(admin)
        return self.admin_repository.list_conversations(
            founder_id=founder_id, limit=limit, offset=offset)

    def list_feedback(self, admin: AdminUser, *, limit: int = 50):
        self.permissions.require_read(admin)
        return self.admin_repository.list_feedback(limit=limit)

    # --- dashboard -------------------------------------------------------

    def dashboard(self, admin: AdminUser) -> SystemStats:
        self.permissions.require_read(admin)
        now = self._now()
        founders = self.admin_repository.list_founders(limit=None)
        conversations = self.admin_repository.list_conversations(limit=None)
        active = sum(1 for f in founders if f.status == FounderStatus.ACTIVE)

        def within(days: int) -> int:
            cutoff = now - timedelta(days=days)
            return sum(1 for c in conversations if c.created_at >= cutoff)

        return SystemStats(
            total_founders=len(founders),
            active_founders=active,
            suspended_founders=len(founders) - active,
            new_founders=sum(1 for f in founders if f.created_at >= now - timedelta(days=_NEW_FOUNDER_DAYS)),
            total_conversations=len(conversations),
            usage=self.admin_repository.usage_metrics(),
            daily_activity=within(1), weekly_activity=within(7), monthly_activity=within(30),
            generated_at=now,
        )

    # --- announcements ---------------------------------------------------

    def publish_announcement(self, admin: AdminUser, *, title: str, body: str,
                             audience: str = "all") -> Announcement:
        self.permissions.require_manage_announcements(admin)
        validate_announcement(title, body)
        announcement = Announcement(
            announcement_id=self._new_id(), title=title.strip(), body=body.strip(),
            audience=audience, created_by=admin.admin_id, created_at=self._now(), active=True,
        )
        self.announcement_repository.save(announcement)
        self._audit(admin, "publish_announcement", f"announcement:{announcement.announcement_id}",
                    "success", None)
        return announcement

    def list_announcements(self, admin: AdminUser, *, active_only: bool = False):
        self.permissions.require_read(admin)
        return self.announcement_repository.list(active_only=active_only)

    # --- audit -----------------------------------------------------------

    def list_audit(self, admin: AdminUser, *, limit: int = 100):
        self.permissions.require_read(admin)
        return self.audit_repository.list(limit=limit)

    def _audit(self, admin: AdminUser, action: str, resource: str, result: str,
               reason: str | None) -> None:
        self.audit_repository.record(AuditEvent(
            event_id=self._new_id(), admin_id=admin.admin_id, action=action, resource=resource,
            timestamp=self._now(), result=result, reason=reason,
        ))
