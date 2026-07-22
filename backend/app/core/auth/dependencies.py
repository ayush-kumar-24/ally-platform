from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth.base import AuthError, AuthUser
from app.core.auth.dev_provider import DEV_FOUNDER_EMAIL, DEV_FOUNDER_ID
from app.core.auth.factory import get_auth_provider
from app.core.auth.tokens import ACCESS, decode_token, identity_from_claims
from app.core.config import settings

# auto_error=False so a missing header reaches our code, which decides what to do.
_bearer = HTTPBearer(auto_error=False, description="Bearer token")


def _token(credentials: HTTPAuthorizationCredentials | None) -> str | None:
    return credentials.credentials if credentials else None


async def get_upstream_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthUser:
    """Verify the identity-provider token. Used ONLY at /auth/session.

    This is the token the frontend receives from Supabase after Google/LinkedIn
    login (or, on AWS later, from Cognito). It proves who the user is exactly
    once; after that the backend issues its own session tokens and this is not
    used again until the next login.
    """
    return get_auth_provider().verify_token(_token(credentials))


async def get_current_founder(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthUser:
    """Verify OUR session access token. Used on every protected route.

    Dev convenience: when AUTH_PROVIDER=dev and no token is sent, this resolves
    to the fixed dev founder so you can hit endpoints from /docs without logging
    in. To act as a specific founder in dev, call /auth/session with that id as
    the bearer token to mint real session tokens, then use those.
    """
    token = _token(credentials)

    if settings.AUTH_PROVIDER.strip().lower() == "dev" and not token:
        founder = AuthUser(id=DEV_FOUNDER_ID, email=DEV_FOUNDER_EMAIL, provider="dev")
        request.state.founder_id = founder.id
        return founder

    claims = decode_token(token, ACCESS)
    founder = identity_from_claims(claims)

    # Picked up by the JSON logger's founder_id field.
    request.state.founder_id = founder.id
    return founder
