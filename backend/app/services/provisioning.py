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
from app.plans.catalog import PLANS, PlanTier
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

    # The grant amount comes from the catalog, never from the stored procedure:
    # a number baked into a function body would drift from catalog.py silently,
    # and nothing could test that it had. Every founder starts on Free, so this
    # is Free's one-time grant.
    signup_credits = PLANS[PlanTier.FREE].signup_credits

    try:
        # Live-reproduced on production: migration 7c4f0f1a9d2e ("secure founder
        # provisioning for rls") added a security boundary to
        # create_founder_on_signup requiring the caller to assert, via this
        # session-scoped setting, which user it has ALREADY authenticated --
        # closing a real hole (anyone with ally_app's DB credentials could
        # otherwise provision a founder row for an arbitrary auth.users id).
        # That migration shipped without the matching backend change, so
        # every single provisioning call failed closed with "missing
        # authenticated user context" -- no new signup, Google or email/OTP,
        # could ever get a founder row. Safe to assert here specifically:
        # `identity` has already been through full JWT verification (signature,
        # expiry, claims) by this point, so user_uuid is not user-suppliable,
        # it's the backend's own already-established trust -- exactly what the
        # migration's security boundary asks for.
        #
        # set_config(..., is_local=true), not a plain SET: this connection is
        # pooled, so a plain SET would leak this value to whatever unrelated
        # request reuses the connection next. is_local=true scopes it to this
        # transaction only, clearing automatically at the commit right below.
        db.execute(
            text("SELECT set_config('app.current_founder_uuid', :u, true)"),
            {"u": str(user_uuid)},
        )
        founder_id = db.execute(
            text("SELECT create_founder_on_signup(:u, :n, :e, :p, :t, :i, :b, :c)"),
            {
                "u": str(user_uuid),
                "n": _display_name(identity),
                "e": identity.email,
                "p": settings.PRIVACY_POLICY_VERSION,
                "t": settings.TERMS_VERSION,
                "i": ip_address,
                "b": identity.provider,
                "c": signup_credits,
            },
        ).scalar()
        db.commit()
    except DatabaseError as exc:
        # e.g. the token's subject has no auth.users row. A real Supabase token
        # always does; this guards against bad/test tokens. Login still succeeds
        # (unprovisioned) rather than 500-ing.
        db.rollback()
        # exc_info=True: the previous version of this log line carried only the
        # founder_id, not SQLERRM -- the actual reason a provisioning failure
        # happened was never in the application logs at all, only reachable by
        # cross-referencing raw RDS/Postgres logs after the fact.
        logger.warning(
            "Founder provisioning failed",
            extra={"founder_id": str(user_uuid)}, exc_info=exc,
        )
        return None

    return founder_repository.get(db, founder_id)
