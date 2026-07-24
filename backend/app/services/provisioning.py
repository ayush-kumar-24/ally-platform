"""Founder provisioning -- create the founder row that backs a new login.

Called at /auth/session. Idempotent: if a founder already exists for the
identity it is returned unchanged; otherwise, for a real logged-in user, a row
is created via the create_founder_on_signup database function (which also writes
the initial consent record).

Dev-mode identities are never provisioned -- they have no auth.users row, and
founders.user_id is a FK to auth.users, so the insert would fail. Dev therefore
stays read-only, which is what its tests expect.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.core.auth.base import AuthUser
from app.core.config import settings
from app.core.logger import logger
from app.models import Founder
from app.repositories import founder_repository


def _display_name(identity: AuthUser) -> str:
    """Best-effort human name from the IdP token, falling back to the email."""
    claims = identity.claims or {}
    meta = claims.get("user_metadata") or {}
    name = meta.get("full_name") or meta.get("name") or claims.get("name")
    if name:
        return str(name)
    if identity.email:
        return identity.email.split("@")[0]
    return "Founder"


def ensure_founder(identity: AuthUser, db: Session, ip_address: str = "0.0.0.0") -> Founder | None:
    """Return the founder for this identity, creating one on first real login.

    Returns None when there is no founder and none can be created (provisioning
    disabled, or a dev identity).
    """
    try:
        user_uuid = UUID(str(identity.id))
    except (ValueError, TypeError):
        return None  # non-uuid subject (dev tokens) -- nothing to provision

    existing = founder_repository.get_by_user_id(db, user_uuid)
    if existing is not None:
        return existing

    if not settings.ENABLE_FOUNDER_PROVISIONING or identity.provider == "dev":
        return None

    try:
        founder_id = db.execute(
            text("SELECT create_founder_on_signup(:u, :n, :e, :p, :t, :i, :b)"),
            {
                "u": str(user_uuid),
                "n": _display_name(identity),
                "e": identity.email,
                "p": settings.PRIVACY_POLICY_VERSION,
                "t": settings.TERMS_VERSION,
                "i": ip_address,
                "b": identity.provider,
            },
        ).scalar()
        db.commit()
    except DatabaseError:
        # e.g. the token's subject has no auth.users row. A real Supabase token
        # always does; this guards against bad/test tokens. Login still succeeds
        # (unprovisioned) rather than 500-ing.
        db.rollback()
        logger.warning("Founder provisioning failed", extra={"founder_id": str(user_uuid)})
        return None

    return founder_repository.get(db, founder_id)
