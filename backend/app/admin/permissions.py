"""Admin authorization (Phase 12, Part 7).

Two pieces:
  * AdminRegistry -- resolves an authenticated identity (by email) to an AdminRole.
    Loaded from the GOXL_ADMIN_USERS env var ("email:role,email:role"); empty by
    default (secure: nobody is an admin unless explicitly granted). This is a minimal
    allowlist over the existing auth, NOT a new auth system.
  * AdminPermissionService -- role-gated checks. READ_ONLY may read; OPERATOR may
    also manage founders + publish announcements; ADMIN may do everything.
Both fail closed: an unknown identity or an insufficient role raises.
"""

from __future__ import annotations

import os

from app.admin.errors import AdminForbiddenError
from app.admin.models import AdminRole, AdminUser

_RANK = {AdminRole.READ_ONLY: 1, AdminRole.OPERATOR: 2, AdminRole.ADMIN: 3}


class AdminRegistry:
    def __init__(self, mapping: dict[str, AdminRole] | None = None, *, env: dict | None = None):
        if mapping is not None:
            self._by_email = {e.lower(): r for e, r in mapping.items()}
        else:
            self._by_email = self._parse(env if env is not None else os.environ)

    @staticmethod
    def _parse(env) -> dict[str, AdminRole]:
        raw = env.get("GOXL_ADMIN_USERS", "")
        out: dict[str, AdminRole] = {}
        for entry in raw.split(","):
            entry = entry.strip()
            if not entry or ":" not in entry:
                continue
            email, _, role = entry.rpartition(":")
            try:
                out[email.strip().lower()] = AdminRole(role.strip().lower())
            except ValueError:
                continue                       # ignore malformed role tokens
        return out

    def resolve(self, email: str | None) -> AdminRole | None:
        return self._by_email.get((email or "").lower())


class AdminPermissionService:
    def _at_least(self, admin: AdminUser, role: AdminRole, action: str) -> None:
        if _RANK[admin.role] < _RANK[role]:
            raise AdminForbiddenError(admin.role.value, action)

    def require_read(self, admin: AdminUser) -> None:
        self._at_least(admin, AdminRole.READ_ONLY, "read admin data")

    def require_manage_founders(self, admin: AdminUser) -> None:
        self._at_least(admin, AdminRole.OPERATOR, "manage founders")

    def require_manage_announcements(self, admin: AdminUser) -> None:
        self._at_least(admin, AdminRole.OPERATOR, "manage announcements")
