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
from app.db.session import get_db, set_admin_rls_context
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


def get_panel_admin(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
) -> PanelAdmin:
    role = container.panel_registry().resolve(founder.email)
    if role is None:
        raise UnauthorizedAdminError()

    # WIDEN RLS TO THE WHOLE ESTATE -- the one place in a request path where
    # that is correct.
    #
    # `get_founder_record` has already pinned this session to the ADMIN's own
    # founder_id via set_founder_rls_context. Every founder-scoped table
    # (privacy_requests, founder_feedback, founders, discovery_calls...) carries
    # the policy `founder_id = get_founder_id() OR app.current_admin`, so
    # without this line an admin querying the review queues sees only their OWN
    # rows and an empty panel looks like an empty queue. Silently. That is the
    # worst possible failure for a screen whose entire job is to prove somebody
    # is watching.
    #
    # Not observable in local development, which connects as a BYPASSRLS
    # superuser and therefore never exercises the policy -- it only appears in
    # production, where the app runs as `ally_app`.
    #
    # AFTER the role check, never before: this is the privilege escalation that
    # the allowlist above authorises, so it must be unreachable by anyone the
    # allowlist rejected. It is set with is_local = true, so it dies with the
    # transaction and cannot leak to whoever gets this pooled connection next.
    set_admin_rls_context(db)

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
