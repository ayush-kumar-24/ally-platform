"""Storing, refreshing and retiring a founder's calendar connection.

The one rule that shapes this module: **a calendar problem must never cost a
founder their data.** Everything here either succeeds or reports a state the
caller can ignore. Nothing raises into the Plan Your Day path.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.calendar_sync import crypto, google_oauth
from app.calendar_sync.db_models import (
    PROVIDER_GOOGLE,
    STATUS_ACTIVE,
    STATUS_ERROR,
    STATUS_REVOKED,
    CalendarConnectionRow,
)
from app.core.logger import logger


def get_connection(db: Session, founder_id: int,
                   provider: str = PROVIDER_GOOGLE) -> CalendarConnectionRow | None:
    return (db.query(CalendarConnectionRow)
            .filter(CalendarConnectionRow.founder_id == founder_id,
                    CalendarConnectionRow.provider == provider)
            .one_or_none())


def is_connected(db: Session, founder_id: int) -> bool:
    row = get_connection(db, founder_id)
    return row is not None and row.status == STATUS_ACTIVE


def save_connection(db: Session, founder_id: int, bundle: google_oauth.TokenBundle,
                    provider: str = PROVIDER_GOOGLE) -> CalendarConnectionRow:
    """Persist a freshly authorised connection, replacing any previous one.

    Updates in place rather than inserting: the unique (founder_id, provider)
    constraint means reconnecting is an update, and accumulating dead rows would
    make "which connection is live?" ambiguous.
    """
    row = get_connection(db, founder_id, provider)
    now = datetime.now(timezone.utc)

    if row is None:
        row = CalendarConnectionRow(
            connection_id=secrets.token_urlsafe(24),
            founder_id=founder_id, provider=provider, connected_at=now)
        db.add(row)

    row.access_token_encrypted = crypto.encrypt(bundle.access_token)
    # Only overwrite the refresh token when Google actually sent one. On
    # re-consent it is often omitted, and blanking the stored copy would leave a
    # connection that works for an hour and then dies with no way to renew.
    if bundle.refresh_token:
        row.refresh_token_encrypted = crypto.encrypt(bundle.refresh_token)
    if bundle.account_email:
        row.account_email = bundle.account_email
    row.token_expires_at = bundle.expires_at
    row.status = STATUS_ACTIVE
    row.last_error = ""
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return row


def disconnect(db: Session, founder_id: int, provider: str = PROVIDER_GOOGLE) -> bool:
    """Forget the connection. Returns False if there was nothing to forget.

    Events Ally already created are LEFT ON THE CALENDAR (team decision,
    2026-08-22). Bulk-deleting entries from someone's real calendar is
    unrecoverable and, if the disconnect was a mis-click, destroys work they may
    have reorganised their week around. Stale events are a nuisance; deleted
    ones are a support incident.

    planning_tasks.calendar_event_id is deliberately left populated too: if the
    founder reconnects the same Google account, those ids still resolve and
    edits keep landing on the original events instead of creating duplicates.
    """
    row = get_connection(db, founder_id, provider)
    if row is None:
        return False

    try:
        google_oauth.revoke(crypto.decrypt(row.refresh_token_encrypted)
                            or crypto.decrypt(row.access_token_encrypted))
    except Exception as exc:  # includes a missing/rotated encryption key
        # Never blocks the disconnect: the founder asked to be disconnected, and
        # our inability to tell Google is not a reason to keep saying "connected".
        logger.warning("calendar revoke failed; removing local connection anyway",
                       extra={"founder_id": founder_id}, exc_info=exc)

    db.delete(row)
    db.commit()
    return True


def mark_revoked(db: Session, row: CalendarConnectionRow, reason: str) -> None:
    """Access is gone for good -- the founder has to reconnect.

    The row is kept, not deleted, so the UI can say "reconnect your calendar"
    with the account name attached instead of silently reverting to a bare
    "Connect" button that gives no hint anything broke.
    """
    row.status = STATUS_REVOKED
    row.last_error = reason[:500]
    row.updated_at = datetime.now(timezone.utc)
    db.commit()


def mark_error(db: Session, row: CalendarConnectionRow, reason: str) -> None:
    """A transient failure. Stays usable; the next call may well succeed."""
    row.status = STATUS_ERROR
    row.last_error = reason[:500]
    row.updated_at = datetime.now(timezone.utc)
    db.commit()


def access_token(db: Session, row: CalendarConnectionRow) -> str | None:
    """A usable access token, refreshing first if needed. None if unusable.

    None rather than an exception because every caller is on the best-effort
    sync path, where "no token" and "token refused" lead to the same place:
    record the task as unsynced and carry on.
    """
    if not crypto.is_available():
        logger.warning("calendar token key unavailable; cannot use stored tokens")
        return None

    try:
        token = crypto.decrypt(row.access_token_encrypted)
        expires = row.token_expires_at
        if token and expires and expires > datetime.now(timezone.utc):
            return token

        refresh_token = crypto.decrypt(row.refresh_token_encrypted)
        if not refresh_token:
            # Expired, and nothing to renew with. Reconnection is the only path,
            # so say so rather than retrying forever.
            mark_revoked(db, row, "No refresh token stored; reconnect required.")
            return None

        bundle = google_oauth.refresh(refresh_token)
        row.access_token_encrypted = crypto.encrypt(bundle.access_token)
        row.token_expires_at = bundle.expires_at
        row.status = STATUS_ACTIVE
        row.last_error = ""
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        return bundle.access_token

    except google_oauth.GoogleAccessRevokedError as exc:
        mark_revoked(db, row, str(exc))
        return None
    except Exception as exc:
        # Transient: network, 5xx, a decrypt failure after a key rotation. Marked
        # as error, NOT revoked -- the founder did nothing and should not be
        # asked to reconnect over an outage.
        mark_error(db, row, str(exc))
        logger.warning("calendar token refresh failed",
                       extra={"founder_id": row.founder_id}, exc_info=exc)
        return None
