"""Founder provisioning -- create or resolve the founder behind a login."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.core.auth.base import AuthError, AuthUser
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
    """Best-effort human name from the IdP token, falling back to email."""
    claims = identity.claims or {}
    meta = claims.get("user_metadata") or {}
    name = meta.get("full_name") or meta.get("name") or claims.get("name")
    if name:
        return str(name)
    if identity.email:
        return identity.email.split("@")[0]
    return "Founder"


def _cognito_email_verified(identity: AuthUser) -> bool:
    value = (identity.claims or {}).get("email_verified")
    return value is True or (
        isinstance(value, str) and value.strip().lower() == "true"
    )


def _link_existing_cognito_founder(
    identity: AuthUser,
    db: Session,
) -> Founder | None:
    """Perform the one-time Cognito -> existing Ally founder identity link."""

    cognito_sub = str(identity.id).strip()
    email = (identity.email or "").strip()

    email_verified = _cognito_email_verified(identity)

    try:
        # These values are transaction-local. The SECURITY DEFINER linker
        # independently verifies that its arguments match this authenticated
        # Cognito context before it can inspect/link any founder.
        db.execute(
            text(
                "SELECT set_config("
                "'app.current_cognito_sub', :value, true)"
            ),
            {"value": cognito_sub},
        )
        db.execute(
            text(
                "SELECT set_config("
                "'app.current_cognito_email', :value, true)"
            ),
            {"value": email},
        )
        db.execute(
            text(
                "SELECT set_config("
                "'app.current_cognito_email_verified', :value, true)"
            ),
            {"value": "true" if email_verified else "false"},
        )

        row = (
            db.execute(
                text(
                    "SELECT founder_id, user_id, linked "
                    "FROM public.link_cognito_founder(:sub, :email)"
                ),
                {"sub": cognito_sub, "email": email},
            )
            .mappings()
            .first()
        )

        # Clears the transaction-local Cognito security context.
        db.commit()

    except DatabaseError as exc:
        db.rollback()
        logger.warning(
            "Cognito founder identity linking failed",
            extra={"cognito_sub": cognito_sub},
            exc_info=exc,
        )
        raise AuthError("Unable to link Cognito identity") from exc

    # No matching historical founder: this is a brand-new Cognito user.
    if row is None:
        return None

    try:
        canonical_uuid = UUID(str(row["user_id"]))
    except (ValueError, TypeError) as exc:
        raise AuthError("Invalid linked founder identity") from exc

    # From this point onward the request uses the existing Ally user UUID,
    # not the Cognito sub, so all historical founder-scoped data remains visible.
    set_founder_rls_context(db, str(canonical_uuid))

    founder = founder_repository.get_by_user_id(db, canonical_uuid)
    if founder is None:
        logger.error(
            "Cognito linker returned a founder that could not be loaded",
            extra={
                "founder_id": row["founder_id"],
                "canonical_user_id": str(canonical_uuid),
            },
        )
        raise AuthError("Unable to load linked founder")

    return founder


def ensure_founder(
    identity: AuthUser,
    db: Session,
    ip_address: str = "0.0.0.0",
) -> Founder | None:
    founder, _created = ensure_founder_with_status(
        identity,
        db,
        ip_address=ip_address,
    )
    return founder


def ensure_founder_with_status(
    identity: AuthUser,
    db: Session,
    ip_address: str = "0.0.0.0",
) -> tuple[Founder | None, bool]:
    """Resolve or create the canonical Ally founder for this identity."""

    try:
        user_uuid = UUID(str(identity.id))
    except (ValueError, TypeError):
        return None, False

    # Existing Cognito users must be resolved BEFORE normal founder RLS is set,
    # because their Cognito sub differs from their historical Supabase user_id.
    if identity.provider == "cognito":
        existing = _link_existing_cognito_founder(identity, db)
        if existing is not None:
            return existing, False

    # Supabase users use their existing subject directly. Brand-new Cognito
    # users also use their Cognito sub as their canonical Ally user UUID.
    set_founder_rls_context(db, str(user_uuid))

    existing = founder_repository.get_by_user_id(db, user_uuid)
    if existing is not None:
        if identity.provider == "cognito":
            current_sub = getattr(existing, "cognito_sub", None)

            if current_sub is not None and current_sub != str(identity.id):
                raise AuthError("Founder is linked to another Cognito identity")

            if current_sub is None:
                existing.cognito_sub = str(identity.id)
                try:
                    db.commit()
                except DatabaseError as exc:
                    db.rollback()
                    logger.warning(
                        "Failed to complete Cognito identity mapping",
                        extra={"founder_id": existing.founder_id},
                        exc_info=exc,
                    )
                    raise AuthError("Unable to link Cognito identity") from exc

        return existing, False

    if not settings.ENABLE_FOUNDER_PROVISIONING or identity.provider == "dev":
        return None, False

    signup_credits = PLANS[PlanTier.FREE].signup_credits

    try:
        db.execute(
            text(
                "SELECT set_config("
                "'app.current_founder_uuid', :u, true)"
            ),
            {"u": str(user_uuid)},
        )

        founder_id = db.execute(
            text(
                "SELECT create_founder_on_signup("
                ":u, :n, :e, :p, :t, :i, :b, :c)"
            ),
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

        # Brand-new Cognito users have no historical Supabase UUID.
        # Their Cognito sub therefore becomes both user_id and cognito_sub.
        if identity.provider == "cognito":
            db.execute(
                text(
                    "UPDATE public.founders "
                    "SET cognito_sub = :sub "
                    "WHERE founder_id = :founder_id "
                    "AND user_id = :user_id "
                    "AND cognito_sub IS NULL"
                ),
                {
                    "sub": str(identity.id),
                    "founder_id": founder_id,
                    "user_id": str(user_uuid),
                },
            )

        db.commit()

    except DatabaseError as exc:
        db.rollback()
        logger.warning(
            "Founder provisioning failed",
            extra={"founder_id": str(user_uuid)},
            exc_info=exc,
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

    # Returning Cognito users must be resolved before the new-user capacity
    # gate. Their Cognito sub differs from their historical Ally user_id.
    if identity.provider == "cognito":
        existing = _link_existing_cognito_founder(identity, db)
        if existing is not None:
            return existing, False, False

    set_founder_rls_context(db, str(user_uuid))

    existing = founder_repository.get_by_user_id(db, user_uuid)
    if existing is not None:
        return existing, False, False

    if not settings.ENABLE_FOUNDER_PROVISIONING or identity.provider == "dev":
        return None, False, False

    # This whole block -- the capacity gate and the provisioning attempt it
    # guards -- is new and, until direct capacity was ever raised above zero,
    # had never actually executed against a real signup in production; every
    # brand-new identity took the capacity-zero branch below instead, which
    # never touches _take_a_direct_signup_slot or create_founder_on_signup at
    # all. The FOR UPDATE select, the slot decrement, and create_founder_on_signup
    # are each one query failing in a way ensure_founder_with_status's narrower
    # `except DatabaseError` does not catch (e.g. a driver-level or
    # RLS-context problem, not a constraint violation) would otherwise
    # propagate all the way out of /auth/session as a raw 500 -- a founder who
    # verified their code correctly and got nothing but "something went
    # wrong". Caught here and treated exactly like capacity-zero: queued and
    # emailed, not turned away. This does NOT explain away the failure -- it
    # is logged at error level with the traceback for whoever next has
    # application-log access, so the actual bug still gets found and fixed.
    # It only stops today's version of it from being a dead end at sign-in.
    try:
        if not _came_through_the_waitlist(db, user_uuid):
            if not _take_a_direct_signup_slot(db):
                db.rollback()  # release the FOR UPDATE lock; nothing to keep
                return _queue_for_waitlist(db, identity, ip_address)

        founder, created = ensure_founder_with_status(identity, db, ip_address=ip_address)
        return founder, created, False
    except Exception as exc:  # noqa: BLE001 -- see comment above
        db.rollback()
        logger.error(
            "Direct-signup provisioning crashed; falling back to waitlist",
            extra={"founder_id": str(user_uuid)}, exc_info=exc,
        )
        # NOT a bare retry. The failure this handler was written for turned out
        # to be the queue insert itself -- RLS was enabled on
        # waitlist_registrations with no policy behind it, so register() could
        # never write a row. Falling back by calling the same insert a second
        # time reproduced the same error inside the handler and escaped as the
        # very 500 the fallback existed to prevent ("During handling of the
        # above exception, another exception occurred"). The queue is a
        # courtesy; the sign-in outcome must not depend on it succeeding.
        return _try_queue_for_waitlist(db, identity, ip_address)


def _try_queue_for_waitlist(
    db: Session, identity: AuthUser, ip_address: str
) -> tuple[Founder | None, bool, bool]:
    """_queue_for_waitlist, but a failure to queue is not a failure to sign in.

    Used only from the crash handler above, where one insert has already gone
    wrong: if the reason it went wrong also stops the queue insert -- as it did
    in the outage this was written for -- then letting that second failure
    propagate turns a recoverable problem into a dead end at the login screen.

    The caller still gets `waitlisted=True`. That is honest about what happened
    to them (they are not provisioned, and they are not getting in right now)
    without claiming the queue row exists. Whether it does is recorded here,
    loudly, rather than inferred by the founder from a blank error box.
    """
    try:
        return _queue_for_waitlist(db, identity, ip_address)
    except Exception as exc:  # noqa: BLE001 -- last line before a 500
        db.rollback()
        logger.error(
            "Waitlist queue insert failed too; founder is neither provisioned "
            "nor queued",
            extra={"path": identity.email or "", "founder_id": str(identity.id)},
            exc_info=exc,
        )
        return None, False, True


def _queue_for_waitlist(
    db: Session, identity: AuthUser, ip_address: str
) -> tuple[Founder | None, bool, bool]:
    """Place `identity` in the same pending queue an ordinary registration
    lands in, and best-effort email them. Shared by the two ways a direct
    sign-up ends up here: capacity genuinely at zero, and the fallback above
    for an unexpected failure partway through trying to provision them.
    """
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
