from datetime import datetime, timedelta, timezone

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth.base import AccountSuspendedError, AuthError, AuthUser
from app.core.auth.dev_provider import DEV_FOUNDER_EMAIL, DEV_FOUNDER_ID
from app.core.auth.factory import get_auth_provider
from app.core.auth.tokens import ACCESS, decode_token, identity_from_claims
from app.core.logger import logger
from app.db.session import get_db

# auto_error=False so a missing header reaches our code, which decides what to do.
_bearer = HTTPBearer(auto_error=False, description="Bearer token")

_SUSPENDED_STATUSES = {"suspended", "banned"}

# How often a founder's last-seen stamp actually writes. A busy chat session
# alone can fire dozens of requests a minute, and none of the three dashboard
# windows this feeds (Live now / Today / 7 days -- see app/admin/insights.py)
# need finer than a minute.
_LAST_ACTIVE_THROTTLE = timedelta(seconds=60)


def _token(credentials: HTTPAuthorizationCredentials | None) -> str | None:
    return credentials.credentials if credentials else None


def is_account_active(db: Session, user_id: str) -> bool:
    """False only when the founder row says `suspended` or `banned`.

    This is the Admin Panel proposal's Gap #1 fix: suspending a founder wrote
    `founders.status` but nothing ever read it back, so the founder's existing
    token kept working until it naturally expired -- suspend was not actually
    revoke. Called on every authenticated request (see `get_current_founder`
    below), so the founder's very next call after being suspended is refused,
    not their next login.

    Fails OPEN, deliberately and only for "we could not check" -- a `founders`
    row that does not exist yet (no founder ever provisioned for this token),
    a `status` column missing on a database this migration has not reached yet
    (see `add_admin_panel_tables`), or a transient DB error. None of those mean
    "this account is fine"; they mean this check has no answer, and refusing
    every authenticated request in the app because of that would be a much
    louder failure than the suspension check silently sitting out one request.
    A real `suspended`/`banned` row, once the query succeeds, always wins.
    """
    try:
        row = db.execute(
            text("SELECT status FROM founders WHERE user_id = :uid"),
            {"uid": user_id},
        ).scalar()
    except Exception:
        db.rollback()
        logger.warning("Could not check account status; failing open",
                       extra={"founder_id": user_id})
        return True
    return row not in _SUSPENDED_STATUSES


def record_last_active(db: Session, user_id: str, *, now: datetime | None = None) -> None:
    """Admin Panel proposal Gap #2 ("no live-user view"): `founders.last_active_at`
    has existed since the same migration that added `status`, but nothing has
    ever written it -- the dashboard's "Active today" card has always read 0,
    however many founders were actually on the platform (see
    `app/admin/insights.py`'s `active_today` metric, which reads this exact
    column). This is the write it was always missing.

    Throttled, not unconditional: the WHERE clause below matches zero rows --
    and writes nothing -- for a founder already stamped within
    `_LAST_ACTIVE_THROTTLE`, so the throttle costs no extra read.

    Best-effort like `is_account_active`: a write that only measures activity
    must never fail the request it is measuring, so errors are swallowed
    (after rolling back, so a failed write doesn't poison the session for
    whatever the route handler does with `db` next).
    """
    at = now or datetime.now(timezone.utc)
    try:
        db.execute(
            text(
                "UPDATE founders SET last_active_at = :at "
                "WHERE user_id = :uid "
                "  AND (last_active_at IS NULL OR last_active_at < :threshold)"
            ),
            {"at": at, "uid": user_id, "threshold": at - _LAST_ACTIVE_THROTTLE},
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Could not record last-active timestamp",
                       extra={"founder_id": user_id})


async def get_upstream_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthUser:
    """Verify the identity-provider token. Used ONLY at /auth/session.

    This is the token the frontend receives from Supabase after an OTP or
    password login (or, on AWS later, from Cognito). It proves who the user is exactly
    once; after that the backend issues its own session tokens and this is not
    used again until the next login.
    """
    return get_auth_provider().verify_token(_token(credentials))


async def get_current_founder(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AuthUser:
    """Verify OUR session access token. Used on every protected route.

    Dev convenience: when AUTH_PROVIDER=dev and no token is sent, this resolves
    to the fixed dev founder so you can hit endpoints from /docs without logging
    in. To act as a specific founder in dev, call /auth/session with that id as
    the bearer token to mint real session tokens, then use those.

    That shortcut is gated on `get_auth_provider()` rather than on the setting
    alone. The factory is what refuses to build a dev provider under
    ENVIRONMENT=production; reading `settings.AUTH_PROVIDER` directly skipped
    that check, so a deployment with AUTH_PROVIDER=dev left behind would have
    authenticated every unauthenticated request on every protected route as the
    dev founder while /auth/session correctly refused to start a session.

    Also checks the founder is not suspended/banned -- see `is_account_active`
    -- and records this as their last-seen activity -- see `record_last_active`.
    Both deliberately after the dev shortcut, not before it: the dev founder
    is a fixture, not a real row, and there is nothing to suspend or track
    activity against.
    """
    token = _token(credentials)

    if not token and get_auth_provider().name == "dev":
        founder = AuthUser(id=DEV_FOUNDER_ID, email=DEV_FOUNDER_EMAIL, provider="dev")
        request.state.founder_id = founder.id
        return founder

    claims = decode_token(token, ACCESS)
    founder = identity_from_claims(claims)

    if not is_account_active(db, founder.id):
        raise AccountSuspendedError()
    record_last_active(db, founder.id)

    # Picked up by the JSON logger's founder_id field.
    request.state.founder_id = founder.id
    return founder
