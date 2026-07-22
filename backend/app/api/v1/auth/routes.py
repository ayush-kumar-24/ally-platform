"""Authentication endpoints.

Flow (social login only -- Google / LinkedIn, no passwords):

    1. Frontend runs Google/LinkedIn login via Supabase and receives a Supabase
       access token.
    2. Frontend calls POST /auth/session with that token. The backend verifies it
       once, then issues its OWN access + refresh tokens.
    3. Every later request carries our access token.
    4. POST /auth/refresh trades a refresh token for a new access token.
    5. POST /auth/logout revokes a refresh token.

Why the backend issues its own tokens: the rest of the API never depends on the
provider's token format, so moving to AWS Cognito later changes only step 1.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import (
    ACCESS,
    REFRESH,
    AuthError,
    AuthUser,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_auth_provider,
    get_current_founder,
    get_session_store,
    get_upstream_identity,
    identity_from_claims,
)
from app.core.config import settings
from app.db.session import get_db
from app.schemas.auth import (
    AuthStatus,
    IdentityOut,
    LogoutRequest,
    RefreshRequest,
    SessionResponse,
    TokenPair,
)
from app.services.provisioning import ensure_founder

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_pair(identity: AuthUser) -> TokenPair:
    access, _ = create_access_token(identity)
    refresh, _ = create_refresh_token(identity)
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/session", response_model=SessionResponse)
async def start_session(
    identity: AuthUser = Depends(get_upstream_identity),
    db: Session = Depends(get_db),
):
    """Exchange a verified Google/LinkedIn (Supabase) token for backend tokens.

    Send the Supabase access token as the bearer token. In dev mode, send any id
    as the bearer token (or none for the default dev founder).
    """
    provisioned = ensure_founder(identity, db)

    pair = _token_pair(identity)
    return SessionResponse(
        **pair.model_dump(),
        founder=IdentityOut(id=identity.id, email=identity.email, provider=identity.provider),
        provisioned=provisioned,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh_session(payload: RefreshRequest):
    """Trade a valid, non-revoked refresh token for a fresh token pair.

    The old refresh token is revoked as part of this call (rotation), so a
    refresh token works exactly once.
    """
    claims = decode_token(payload.refresh_token, REFRESH)

    store = get_session_store()
    if store.is_revoked(claims["jti"]):
        raise AuthError("Refresh token has been revoked")

    store.revoke(claims["jti"])
    return _token_pair(identity_from_claims(claims))


@router.post("/resume", response_model=SessionResponse)
async def resume_session(payload: RefreshRequest):
    """Restore a session on app reload from a stored refresh token.

    Like /session, but the starting point is our refresh token rather than a
    fresh Google/LinkedIn login -- so a returning user who still holds a valid
    refresh token is brought back in without bouncing through the provider. The
    refresh token is rotated (the old one is revoked), and the caller gets a new
    pair plus their identity, ready to rehydrate the UI.

    Differs from /refresh, which only swaps tokens and returns no identity.
    """
    claims = decode_token(payload.refresh_token, REFRESH)

    store = get_session_store()
    if store.is_revoked(claims["jti"]):
        raise AuthError("Session has ended; please log in again")

    store.revoke(claims["jti"])
    identity = identity_from_claims(claims)
    pair = _token_pair(identity)
    return SessionResponse(
        **pair.model_dump(),
        founder=IdentityOut(id=identity.id, email=identity.email, provider=identity.provider),
        provisioned=False,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(payload: LogoutRequest):
    """Revoke a refresh token. The client should also discard its access token.

    Access tokens are short-lived and not individually tracked, so they remain
    valid until they expire -- keep their lifetime short. Revoking the refresh
    token is what actually ends the session.
    """
    claims = decode_token(payload.refresh_token, REFRESH)
    get_session_store().revoke(claims["jti"])
    return {"detail": "logged out"}


@router.get("/me", response_model=IdentityOut)
async def read_current_founder(founder: AuthUser = Depends(get_current_founder)):
    """Who am I, according to the access token I sent."""
    return IdentityOut(id=founder.id, email=founder.email, provider=founder.provider)


@router.get("/status", response_model=AuthStatus)
async def read_auth_status():
    """Non-protected: how auth is configured. Works before you have any token."""
    return AuthStatus(
        provider=get_auth_provider().name,
        token_model="backend-issued session tokens",
        access_token_ttl_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token_ttl_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        provisioning_enabled=settings.ENABLE_FOUNDER_PROVISIONING,
    )
