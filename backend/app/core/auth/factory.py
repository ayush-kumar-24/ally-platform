from functools import lru_cache

from app.core.auth.base import AuthProvider
from app.core.auth.dev_provider import DevAuthProvider
from app.core.auth.supabase_provider import SupabaseAuthProvider
from app.core.config import settings


@lru_cache
def get_auth_provider() -> AuthProvider:
    """Build the provider named by AUTH_PROVIDER. Cached -- this runs once.

    Every failure here is a RuntimeError raised on first use, not a silent
    fallback: a misconfigured deployment should refuse to serve rather than
    quietly authenticate everyone.
    """
    provider = settings.AUTH_PROVIDER.strip().lower()

    if provider == "dev":
        if settings.is_production:
            raise RuntimeError("AUTH_PROVIDER='dev' is not allowed when ENVIRONMENT=production")
        return DevAuthProvider()

    if provider == "supabase":
        return SupabaseAuthProvider(settings.SUPABASE_JWT_SECRET)

    raise RuntimeError(f"Unknown AUTH_PROVIDER {provider!r} (expected 'dev' or 'supabase')")
