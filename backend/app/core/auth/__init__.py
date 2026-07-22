"""Auth package.

Layout mirrors how the pieces are swapped:
  base.py              contract (AuthProvider, AuthUser, AuthError)
  dev_provider.py      local stand-in, never reachable in production
  supabase_provider.py verifies the login token from Supabase Auth
  factory.py           picks the identity provider from AUTH_PROVIDER
  tokens.py            the session tokens THIS backend issues (access/refresh)
  session_store.py     refresh-token revocation (logout, rotation)
  dependencies.py      FastAPI dependencies routes actually use

Two token worlds live here, kept deliberately separate:
  - the IdP token (Supabase/Cognito) proves identity once, at /auth/session
  - our session tokens carry every request thereafter

Import from the package, not the modules.
"""

from app.core.auth.base import AuthError, AuthProvider, AuthUser
from app.core.auth.dependencies import get_current_founder, get_upstream_identity
from app.core.auth.factory import get_auth_provider
from app.core.auth.session_store import get_session_store
from app.core.auth.tokens import (
    ACCESS,
    REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    identity_from_claims,
)

__all__ = [
    "AuthError",
    "AuthProvider",
    "AuthUser",
    "get_auth_provider",
    "get_current_founder",
    "get_upstream_identity",
    "get_session_store",
    "ACCESS",
    "REFRESH",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "identity_from_claims",
]
