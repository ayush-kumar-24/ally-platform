"""Session tokens issued by this backend.

The backend mints two JWTs, both signed with SECRET_KEY (HS256):

- access  -- short-lived, sent on every API request.
- refresh -- long-lived, sent only to /auth/refresh to mint a new access token.

These are OUR tokens, distinct from the upstream Supabase/Cognito token that
proves identity at login. Nothing here talks to the identity provider; the
provider's job is finished by the time these are issued.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import JWTError, jwt

from app.core.auth.base import AuthError, AuthUser
from app.core.config import settings

ACCESS = "access"
REFRESH = "refresh"


def _issue(identity: AuthUser, token_type: str, expires: timedelta) -> tuple[str, dict]:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": identity.id,
        "email": identity.email,
        "provider": identity.provider,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires).timestamp()),
        # jti lets a specific token be revoked (see session_store) -- this is what
        # makes logout and refresh-rotation possible.
        "jti": uuid4().hex,
    }
    token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, claims


def create_access_token(identity: AuthUser) -> tuple[str, dict]:
    return _issue(identity, ACCESS, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(identity: AuthUser) -> tuple[str, dict]:
    return _issue(identity, REFRESH, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token: str | None, expected_type: str) -> dict:
    """Validate one of our tokens and return its claims, or raise AuthError.

    `expected_type` guards against using a refresh token where an access token is
    required (and vice versa) -- a refresh token is long-lived and must never be
    accepted as a per-request credential.
    """
    if not token:
        raise AuthError("Missing bearer token")

    try:
        claims = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require_exp": True, "require_sub": True},
        )
    except JWTError as exc:
        raise AuthError("Invalid or expired token") from exc

    if claims.get("type") != expected_type:
        raise AuthError(f"Expected a {expected_type} token")

    return claims


def identity_from_claims(claims: dict) -> AuthUser:
    return AuthUser(
        id=claims["sub"],
        email=claims.get("email"),
        provider=claims.get("provider", "unknown"),
        claims=claims,
    )
