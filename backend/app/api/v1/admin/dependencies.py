"""Admin API dependencies (Phase 12).

`get_current_admin` resolves the authenticated identity to an AdminUser via the
container's email->role allowlist, failing closed (403) for non-admins. The service
comes from the container. Tests override both.
"""

from __future__ import annotations

from fastapi import Depends

from app.admin.errors import UnauthorizedAdminError
from app.admin.models import AdminUser
from app.admin.service import AdminService
from app.api.deps import get_founder_record
from app.core.container import container
from app.models import Founder


def get_current_admin(founder: Founder = Depends(get_founder_record)) -> AdminUser:
    role = container.admin_registry().resolve(founder.email)
    if role is None:
        raise UnauthorizedAdminError()
    return AdminUser(admin_id=founder.founder_id, email=founder.email, role=role)


def get_admin_service() -> AdminService:
    return container.admin_service()
