"""Admin Panel API dependencies.

`get_panel_admin` resolves the caller to a PanelAdmin (identity + role). It fails
closed: a founder whose email is not in the allowlist gets 403, never a default role.

The role allowlist is read from GOXL_ADMIN_PANEL_USERS ("email:role,..."), separate
from the Phase 12 GOXL_ADMIN_USERS so the two role vocabularies don't collide.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.admin.errors import UnauthorizedAdminError
from app.admin.rbac import PanelRole
from app.api.deps import get_founder_record
from app.core.container import container
from app.db.session import get_db
from app.models import Founder


@dataclass(frozen=True)
class PanelAdmin:
    admin_id: int
    email: str
    role: PanelRole


class PanelRegistry:
    """email -> PanelRole. Empty by default: nobody is an admin unless granted."""

    def __init__(self, mapping: dict[str, PanelRole] | None = None, *, env: dict | None = None):
        if mapping is not None:
            self._by_email = {e.lower(): r for e, r in mapping.items()}
        else:
            self._by_email = self._parse(env if env is not None else os.environ)

    @staticmethod
    def _parse(env) -> dict[str, PanelRole]:
        out: dict[str, PanelRole] = {}
        for entry in env.get("GOXL_ADMIN_PANEL_USERS", "").split(","):
            entry = entry.strip()
            if not entry or ":" not in entry:
                continue
            email, _, role = entry.rpartition(":")
            try:
                out[email.strip().lower()] = PanelRole(role.strip().lower())
            except ValueError:
                continue                        # malformed role token -> not granted
        return out

    def resolve(self, email: str | None) -> PanelRole | None:
        return self._by_email.get((email or "").lower())


def get_panel_admin(founder: Founder = Depends(get_founder_record)) -> PanelAdmin:
    role = container.panel_registry().resolve(founder.email)
    if role is None:
        raise UnauthorizedAdminError()
    return PanelAdmin(admin_id=founder.founder_id, email=founder.email, role=role)


def get_panel_service(db: Session = Depends(get_db)):
    return container.admin_panel_service(db)


def client_ip(request: Request) -> str | None:
    """Caller IP for the audit trail.

    X-Forwarded-For is honoured because the app runs behind a proxy, but only the
    FIRST entry (the original client) is taken -- later entries are proxy hops. This
    header is client-controllable, so it is evidence, not authentication: nothing is
    authorized on its basis.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return request.client.host if request.client else None
