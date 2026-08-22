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

from jose import JWTError, jwt

from app.core.config import settings

_PURPOSE = "calendar_oauth_state"
_TTL = timedelta(minutes=5)


class InvalidOAuthStateError(RuntimeError):
    """The state was missing, tampered with, expired, or for something else."""


def issue(founder_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "founder_id": founder_id,
            # Without this a token minted for some other purpose but signed with
            # the same key would be accepted here.
            "purpose": _PURPOSE,
            "iat": int(now.timestamp()),
            "exp": int((now + _TTL).timestamp()),
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def read(state: str | None) -> int:
    """The founder id inside a valid state, or raise."""
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
    return founder_id
