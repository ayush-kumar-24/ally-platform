"""Waitlist business rules: register, approve, reject, and the cap.

The ordering inside `approve` is the whole design, so it is stated once here:

    1. re-read the row FOR UPDATE      (two admins clicking at once)
    2. check the cap                   (before anything irreversible)
    3. create the Supabase identity    (the irreversible step)
    4. mark the row approved + commit  (durable record of step 3)
    5. send the email                  (best effort, after the commit)

Steps 3 and 4 cannot be one atomic thing -- one is an HTTP call to Supabase and
the other is a database write -- so the question is only which failure you
prefer. This order prefers "identity exists, row not yet marked": the recovery
is to approve again, which finds the existing identity (see supabase_admin's
422 handling) and marks the row. The reverse order would leave rows marked
approved with no identity behind them, which reads as success in the panel and
is a founder who has been told they are in and cannot log in.

The email is last and outside the transaction because a mail failure must not
undo a grant that already happened. Whether it actually sent is recorded, so
the panel can show who still needs chasing.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.admin.rbac import PanelRole
from app.core.config import settings
from app.core.logger import logger
from app.middleware.error_handler import AppError
from app.models.waitlist import (
    APPROVED,
    PENDING,
    REJECTED,
    WaitlistRegistration,
    WaitlistSlotOpening,
)
from app.services.supabase_admin import create_auth_user
from app.services.waitlist_notifications import send_approval_email


class RegistrationNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__("Registration not found", status_code=404)


class RegistrationNotPendingError(AppError):
    """Already answered. 409, not 400: the request was well formed, the world
    moved. Almost always two admins working the queue at the same time."""

    def __init__(self, status: str) -> None:
        super().__init__(
            f"This registration was already {status}. Nothing was changed.",
            status_code=409,
        )


class WaitlistCapReachedError(AppError):
    def __init__(self, approved: int, cap: int) -> None:
        super().__init__(
            f"The founder list is full: {approved} of {cap} places are taken. "
            "A super admin can approve past the cap, or raise "
            "WAITLIST_APPROVAL_CAP for the next phase.",
            status_code=409,
        )


def normalise_email(email: str) -> str:
    """The single definition of "the same person". Lower-cased and trimmed --
    the unique index depends on every writer agreeing, so nothing else may
    normalise an address its own way."""
    return (email or "").strip().lower()


def approved_count(db: Session) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(WaitlistRegistration)
            .where(WaitlistRegistration.status == APPROVED)
        ).scalar_one()
    )


def slots_opened_total(db: Session) -> int:
    """Every slot the team has opened from the panel, added up.

    `scalar()` rather than `scalar_one()`: SUM over an empty table is NULL, and
    COALESCE makes that 0 here rather than at four call sites.
    """
    return int(
        db.execute(
            select(func.coalesce(func.sum(WaitlistSlotOpening.slots_opened), 0))
        ).scalar()
        or 0
    )


def effective_cap(db: Session) -> int:
    """How many places exist right now: the environment's starting size plus
    everything opened from the panel since.

    Addition rather than replacement on purpose. If the panel wrote an absolute
    number somewhere, the env var would become a lie that only looks true until
    someone reads it -- and a deploy that changed it would silently undo the
    team's decisions. This way `WAITLIST_APPROVAL_CAP` keeps one meaning ("the
    size we launched with") and the openings are a visible, attributable
    ledger on top of it.
    """
    return int(settings.WAITLIST_APPROVAL_CAP) + slots_opened_total(db)


def cap_status(db: Session) -> dict:
    """What the panel shows above the queue, and what approve/1 checks."""
    approved = approved_count(db)
    base = int(settings.WAITLIST_APPROVAL_CAP)
    opened = slots_opened_total(db)
    cap = base + opened
    return {
        "approved": approved,
        "cap": cap,
        # Broken out so the panel can say where the number came from -- "300
        # to start, 25 opened by you" reads as a decision someone made, which
        # a bare 325 does not.
        "base_cap": base,
        "slots_opened": opened,
        "remaining": max(cap - approved, 0),
        "is_full": approved >= cap,
    }


def register(
    db: Session,
    *,
    email: str,
    full_name: str,
    company: str | None = None,
    role_title: str | None = None,
    stage: str | None = None,
    note: str | None = None,
    source: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Record a registration. Idempotent, and deliberately returns nothing.

    ON CONFLICT DO NOTHING rather than a check-then-insert: two submissions of
    the same form a second apart would both pass the check and one would hit
    the unique index as a 500. It also keeps the endpoint from being an
    existence oracle -- the caller cannot tell a new row from a duplicate,
    because this function does not know either.

    A re-registration never revives a decided row. Someone the team already
    rejected does not return to the top of the queue by filling the form in
    again, and someone already approved does not get a second identity.
    """
    stmt = (
        pg_insert(WaitlistRegistration)
        .values(
            email=normalise_email(email),
            full_name=full_name.strip(),
            company=(company or None),
            role_title=(role_title or None),
            stage=(stage or None),
            note=(note or None),
            source=(source or None),
            status=PENDING,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        .on_conflict_do_nothing(index_elements=["email"])
    )
    db.execute(stmt)
    db.commit()


def _load_pending_for_update(db: Session, registration_id: int) -> WaitlistRegistration:
    """The row, locked, or the right error.

    FOR UPDATE because approve does read-check-write across an HTTP call: two
    admins hitting approve on the same registration would otherwise both read
    `pending`, both create an identity, and the second would silently overwrite
    the first's auth_user_id.
    """
    row = db.execute(
        select(WaitlistRegistration)
        .where(WaitlistRegistration.registration_id == registration_id)
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise RegistrationNotFoundError()
    if row.status != PENDING:
        raise RegistrationNotPendingError(row.status)
    return row


def approve(
    db: Session,
    registration_id: int,
    *,
    admin_id: int,
    admin_email: str,
    admin_role: PanelRole,
) -> WaitlistRegistration:
    """Grant access: create the identity, mark the row, email the founder.

    See the module docstring for why the steps are in this order.
    """
    row = _load_pending_for_update(db, registration_id)

    # Checked inside the lock and before the identity call: the cap is only
    # meaningful if it is read at the moment of the decision, and the identity
    # is the step that cannot be taken back.
    status = cap_status(db)
    if status["is_full"] and admin_role is not PanelRole.SUPER_ADMIN:
        db.rollback()
        raise WaitlistCapReachedError(status["approved"], status["cap"])

    # Raises on failure, so nothing below runs unless the founder really can
    # sign in. The row stays `pending` and the admin can retry.
    auth_user_id = create_auth_user(row.email, full_name=row.full_name)

    now = datetime.now(timezone.utc)
    row.status = APPROVED
    row.decided_at = now
    row.decided_by_admin_id = admin_id
    row.decided_by_email = admin_email
    row.auth_user_id = auth_user_id
    row.access_granted_at = now
    db.commit()
    db.refresh(row)

    # After the commit, and never allowed to raise: the grant has happened, and
    # an unreachable mail server must not turn it back into a pending row.
    try:
        if send_approval_email(row.email, row.full_name):
            row.approval_email_sent_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(row)
    except Exception:  # noqa: BLE001 -- best effort by design, see above
        logger.warning("Waitlist approval email failed", extra={"path": row.email})

    return row


def reject(
    db: Session,
    registration_id: int,
    *,
    reason: str,
    admin_id: int,
    admin_email: str,
) -> WaitlistRegistration:
    """Turn a registration down, with a reason recorded.

    No email is sent. A rejection notice to someone who asked for early access
    is a worse experience than silence, and the team can write to anyone they
    want to let down personally -- which is not something to automate.
    """
    row = _load_pending_for_update(db, registration_id)
    row.status = REJECTED
    row.decided_at = datetime.now(timezone.utc)
    row.decided_by_admin_id = admin_id
    row.decided_by_email = admin_email
    row.decision_reason = reason.strip()
    db.commit()
    db.refresh(row)
    return row


# --- opening slots --------------------------------------------------------
#
# The team decides how many people come in, from the panel, and the queue
# answers itself in the order it was formed. Everything below is that one act:
# raise the ceiling, then walk the queue oldest-first until the new places are
# used up.


def next_in_queue(db: Session, limit: int) -> list[WaitlistRegistration]:
    """The next `limit` people in line -- oldest registration first.

    The same ordering the panel shows, and deliberately the same one: an admin
    who opens ten slots must get exactly the ten rows at the top of the screen
    they were looking at, or the feature is a lottery. `registration_id` breaks
    ties so two registrations in the same clock tick still have a stable order.
    """
    if limit < 1:
        return []
    return list(
        db.execute(
            select(WaitlistRegistration)
            .where(WaitlistRegistration.status == PENDING)
            .order_by(
                WaitlistRegistration.created_at.asc(),
                WaitlistRegistration.registration_id.asc(),
            )
            .limit(limit)
        )
        .scalars()
        .all()
    )


def open_slots(
    db: Session,
    *,
    slots: int,
    admin_id: int,
    admin_email: str,
    admin_role: PanelRole,
) -> dict:
    """Open `slots` places and let the front of the queue into them.

    ORDER, AND WHY THE OPENING IS RECORDED FIRST
    The opening row is written and committed before a single approval runs, so
    the cap is already raised when `approve` checks it. The reverse order would
    make every approval in this batch a cap violation and the whole feature
    would depend on the caller being a super admin to bypass its own limit.

    It also means an opening that approves nobody still counts. That is
    correct: the team decided the list may hold that many, and a queue shorter
    than the number opened leaves real headroom for whoever registers next --
    exactly what "we are open for 25 more" means. `approved_count` records how
    much of it was used, so the two facts never have to be guessed apart.

    PARTIAL FAILURE IS A RESULT, NOT AN ERROR
    Each approval is its own transaction (see `approve`). One person's identity
    call failing must not deny the other twenty-four their place, so a failure
    is collected and reported per person rather than raised. The failed rows
    stay `pending` and are still at the front of the queue, so retrying is just
    opening slots again -- or approving them one by one.
    """
    if slots < 1:
        raise ValueError("slots must be at least 1")

    opening = WaitlistSlotOpening(
        slots_opened=slots,
        opened_by_admin_id=admin_id,
        opened_by_email=admin_email,
    )
    db.add(opening)
    db.commit()
    db.refresh(opening)

    approved: list[WaitlistRegistration] = []
    failures: list[dict] = []

    for row in next_in_queue(db, slots):
        # Read before the call: `approve` mutates this row, and a failure
        # halfway through can leave the ORM copy unusable for the message.
        who = {"email": row.email, "full_name": row.full_name}
        try:
            approved.append(
                approve(
                    db,
                    row.registration_id,
                    admin_id=admin_id,
                    admin_email=admin_email,
                    admin_role=admin_role,
                )
            )
        except AppError as exc:
            # Includes the case where another admin approved this row a second
            # ago (409). Nothing is wrong with the world; this batch just does
            # not own that person.
            db.rollback()
            failures.append({**who, "reason": str(exc)})
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.warning(
                "Waitlist slot approval failed", extra={"path": who["email"]}
            )
            failures.append({**who, "reason": str(exc) or exc.__class__.__name__})

    opening.approved_count = len(approved)
    db.commit()

    logger.info(
        "Waitlist slots opened",
        extra={"path": f"{slots} slots, {len(approved)} approved, by {admin_email}"},
    )

    return {
        "slots": slots,
        "approved": approved,
        "failures": failures,
        "cap": cap_status(db),
    }
