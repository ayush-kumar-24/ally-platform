"""Founder provisioning -- create the founder row that backs a new login.

Deliberately inert right now. `ENABLE_FOUNDER_PROVISIONING` defaults to false, so
`ensure_founder` never writes to the database. Two things must happen before it
can be turned on:

1. The create_founder_on_signup / consents bugs must be fixed (onboarding writes
   fail today), and
2. someone must approve writing real rows.

When enabled, this will call the create_founder_on_signup database function
inside a transaction, keyed on the founder's user_id (the Supabase auth uid).
Until then, turning the flag on raises loudly rather than silently doing nothing.
"""

from sqlalchemy.orm import Session

from app.core.auth.base import AuthUser
from app.core.config import settings


def ensure_founder(identity: AuthUser, db: Session) -> bool:
    """Ensure a founder row exists for this identity. Returns True if provisioned.

    No-op (returns False) while provisioning is disabled -- login still succeeds,
    the user just has no founder row until provisioning is switched on.
    """
    if not settings.ENABLE_FOUNDER_PROVISIONING:
        return False

    raise NotImplementedError(
        "Founder provisioning is enabled but not wired to live DB writes yet. "
        "Fix create_founder_on_signup / consents first and implement the guarded "
        "INSERT here, with explicit approval to write rows."
    )
