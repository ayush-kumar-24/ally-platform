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
from app.db.session import set_founder_rls_context
from app.models import Founder
from app.models.waitlist import APPROVED
from app.plans.catalog import PLANS, PlanTier
from app.repositories import founder_repository
from app.services.waitlist import register
from app.services.waitlist_notifications import send_direct_signup_overflow_email


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

    Use `ensure_founder_with_status` when you need to know whether the row was
    CREATED by this call or merely found -- this signature cannot express the
    difference, which is what made /auth/session report `provisioned: true` for
    founders that had existed for days.
    """
    founder, _created = ensure_founder_with_status(identity, db, ip_address=ip_address)
    return founder


def ensure_founder_with_status(
    identity: AuthUser, db: Session, ip_address: str = "0.0.0.0"
) -> tuple[Founder | None, bool]:
    """As `ensure_founder`, plus whether this call actually created the row.

    Returns (founder, created). `created` is True ONLY on the insert -- an
    identity whose founder already existed comes back (founder, False), and a
    dev identity comes back (founder_or_None, False) because dev never
    provisions.
    """
    try:
        user_uuid = UUID(str(identity.id))
    except (ValueError, TypeError):
        return None, False  # non-uuid subject (dev tokens) -- nothing to provision

    set_founder_rls_context(db, str(user_uuid))

    existing = founder_repository.get_by_user_id(db, user_uuid)
    if existing is not None:
        return existing, False

    if not settings.ENABLE_FOUNDER_PROVISIONING or identity.provider == "dev":
        return None, False

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
        return None, False

    return founder_repository.get(db, founder_id), True


def _came_through_the_waitlist(db: Session, user_uuid: UUID) -> bool:
    """Was this identity's Supabase account created by an admin's approval?

    True for every founder who ever went through the waitlist -- approve()
    stamps waitlist_registrations.auth_user_id at the moment it creates their
    identity. False for a direct sign-up: nothing wrote that row, because
    nothing here ever decided to let them in.

    The distinction matters because both paths land in this same function,
    at the same "no founders row yet" moment, and only one of them is
    supposed to be capacity-gated. An approved founder must NEVER be
    refused their own first login because direct capacity happens to read
    zero -- the team already said yes to them, on a completely different
    ledger.
    """
    return bool(
        db.execute(
            text(
                "SELECT 1 FROM waitlist_registrations "
                "WHERE auth_user_id = :u AND status = :approved LIMIT 1"
            ),
            {"u": str(user_uuid), "approved": APPROVED},
        ).scalar()
    )


def _take_a_direct_signup_slot(db: Session) -> bool:
    """Claim one slot of direct-signin capacity, or refuse.

    FOR UPDATE, inside the SAME transaction the caller will use to create (or
    not create) the founders row: two identities hitting /auth/session for the
    very last slot at the same moment must not both read remaining=1 and both
    proceed. The second one blocks on the lock until the first commits or
    rolls back, then reads the true, post-decrement number.

    Returns False, having changed nothing, when there is no capacity. True
    means one slot has been claimed -- the caller is now responsible for
    either using it (creating the founder) or rolling back the whole
    transaction, which un-claims it along with everything else.
    """
    remaining = db.execute(
        text("SELECT remaining FROM direct_signup_capacity WHERE id = true FOR UPDATE")
    ).scalar_one()
    if remaining <= 0:
        return False
    db.execute(
        text(
            "UPDATE direct_signup_capacity "
            "SET remaining = remaining - 1, updated_at = now() WHERE id = true"
        )
    )
    return True


def ensure_founder_or_waitlist(
    identity: AuthUser, db: Session, ip_address: str = "0.0.0.0"
) -> tuple[Founder | None, bool, bool]:
    """As `ensure_founder_with_status`, plus the direct-signup capacity gate.

    Registration is open at the client level now (see auth.js/Login.jsx): any
    address can ask Supabase for a sign-in code, and Supabase will make one.
    That is correct for exactly as many strangers as the team has opened
    direct capacity for, and wrong for everyone past that -- the login page's
    own URL is reachable with no button in front of it, so the button on the
    landing page is a convenience, never the boundary. This is the boundary.

    Returns (founder, created, waitlisted):
      - An EXISTING founder: unchanged, capacity never enters into it.
        (founder, False, False)
      - A brand-new identity that came through the waitlist (approve() made
        it), or that arrives while direct capacity is open: provisioned
        exactly as ensure_founder_with_status already does.
        (founder, True, False)
      - A brand-new identity with no waitlist history, arriving at capacity
        zero: NOT provisioned. Instead placed in the same pending queue an
        ordinary registration lands in (register(), so it is the identical
        row shape the admin panel already reads and open_slots() already
        walks), and mailed to say so.
        (None, False, True)

    The capacity check and the founders-row creation share one transaction
    (see _take_a_direct_signup_slot): if create_founder_on_signup fails after
    a slot was claimed, the rollback already inside ensure_founder_with_status
    undoes the claim along with it, so a failed creation can never quietly
    burn a slot nobody got.
    """
    try:
        user_uuid = UUID(str(identity.id))
    except (ValueError, TypeError):
        return None, False, False  # dev token; nothing to gate

    set_founder_rls_context(db, str(user_uuid))

    existing = founder_repository.get_by_user_id(db, user_uuid)
    if existing is not None:
        return existing, False, False

    if not settings.ENABLE_FOUNDER_PROVISIONING or identity.provider == "dev":
        return None, False, False

    if not _came_through_the_waitlist(db, user_uuid):
        if not _take_a_direct_signup_slot(db):
            db.rollback()  # release the FOR UPDATE lock; nothing to keep

            name = _display_name(identity)
            email = identity.email or ""
            if email:
                # Same function the "Register" button calls -- ON CONFLICT DO
                # NOTHING, so someone who already registered and is now also
                # trying the direct route does not get a second row or a
                # second place in line.
                register(
                    db,
                    email=email,
                    full_name=name,
                    source="direct_signup_overflow",
                    ip_address=ip_address,
                )
                try:
                    send_direct_signup_overflow_email(email, name)
                except Exception:  # noqa: BLE001 -- best effort, never blocks sign-in
                    logger.warning(
                        "direct-signup overflow email failed", extra={"path": email}
                    )

            return None, False, True

    founder, created = ensure_founder_with_status(identity, db, ip_address=ip_address)
    return founder, created, False
