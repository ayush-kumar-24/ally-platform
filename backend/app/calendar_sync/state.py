"""The OAuth `state` parameter, signed.

The callback arrives as a browser redirect from Google with no Authorization
header, so the request cannot tell us who it belongs to. `state` has to carry
that -- and because it makes a round trip through the user agent, it has to be
unforgeable, or anyone could hand a victim a link that attaches THEIR Google
calendar to someone else's Ally account.

So: a short-lived JWT signed with SECRET_KEY, carrying the founder id. Signed
rather than a random string checked against a stored row, because the stored-row
approach needs a table, a cleanup sweep, and a decision about what happens when
the row expires mid-flow. This has none of those and the same property.

Five minutes: a consent screen takes seconds, and a state token that stays valid
for an hour is an hour in which a leaked redirect URL still works.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt

from app.core.config import settings

_PURPOSE = "calendar_oauth_state"
_TTL = timedelta(minutes=5)


class InvalidOAuthStateError(RuntimeError):
    """The state was missing, tampered with, expired, or for something else."""


def issue(founder_id: int, founder_uuid: str) -> str:
    """Mint the state for one OAuth round trip.

    Carries the founder's auth UUID as well as the internal id, because the
    callback needs BOTH: the id to write the row, and the UUID to establish the
    RLS context (`app.current_founder_uuid`) that the founder-scoped policies
    check. Every other write path gets that context from `get_founder_record`,
    but a Google redirect carries no Authorization header, so this endpoint has
    no such dependency and nothing else can supply it.

    Safe to put here precisely because the state is already a signed,
    short-lived JWT: a caller cannot substitute someone else's UUID without
    forging SECRET_KEY, which is the same property the founder_id already
    relies on.
    """
    now = datetime.now(timezone.utc)

    # Normalised and validated at mint time so a malformed value fails here,
    # where the founder is still in an authenticated request and can be shown a
    # real error, rather than at the callback where the only outcome is a
    # redirect carrying "something went wrong".
    try:
        founder_uuid = str(UUID(str(founder_uuid)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid founder UUID") from exc

    return jwt.encode(
        {
            "founder_id": founder_id,
            "founder_uuid": founder_uuid,
            # Without this a token minted for some other purpose but signed with
            # the same key would be accepted here.
            "purpose": _PURPOSE,
            "iat": int(now.timestamp()),
            "exp": int((now + _TTL).timestamp()),
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def read(state: str | None) -> tuple[int, str]:
    """The founder id and auth UUID inside a valid state, or raise.

    Both are required, and a state missing either is rejected rather than
    partially honoured: writing the row without the UUID would mean writing
    without an RLS context, which fails silently on a SELECT and loudly on an
    INSERT. Better to refuse the callback than to half-complete it.
    """
    if not state:
        raise InvalidOAuthStateError("Missing state.")
    try:
        claims = jwt.decode(state, settings.SECRET_KEY,
                            algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise InvalidOAuthStateError("State is invalid or has expired.") from exc

    if claims.get("purpose") != _PURPOSE:
        raise InvalidOAuthStateError("State was issued for something else.")

    founder_id = claims.get("founder_id")
    if not isinstance(founder_id, int):
        raise InvalidOAuthStateError("State carries no founder.")

    try:
        founder_uuid = str(UUID(str(claims.get("founder_uuid"))))
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidOAuthStateError(
            "State carries no valid founder identity.") from exc

    return founder_id, founder_uuid
