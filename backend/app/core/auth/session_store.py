"""Session (refresh-token) revocation store -- scaffolding.

In the backend-issued-token model, a "session" is a live refresh token. Logout
and refresh-rotation both need to mark a specific refresh token (by its jti) as
no longer usable. That is all this tracks.

The interface is the point. `InMemorySessionStore` is intentionally minimal --
it is process-local and forgets everything on restart, which is fine for local
dev and a single instance. For multi-instance production it must be replaced
with a shared store (Redis, or a database table).

IMPORTANT: A database-backed store would need a NEW table. There is already a
`sessions` table in the schema, but it belongs to the diagnosis flow (it holds
question progress, risk scores, distress signals) -- it is NOT an auth session
table and must not be repurposed here. Adding an auth-session table is a schema
change, so it needs explicit sign-off before it happens.
"""

from abc import ABC, abstractmethod


class SessionStore(ABC):
    @abstractmethod
    def is_revoked(self, jti: str) -> bool: ...

    @abstractmethod
    def revoke(self, jti: str) -> None: ...


class InMemorySessionStore(SessionStore):
    """Process-local revocation set. Cleared on restart -- scaffolding only."""

    def __init__(self) -> None:
        self._revoked: set[str] = set()

    def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked

    def revoke(self, jti: str) -> None:
        if jti:
            self._revoked.add(jti)


_store: SessionStore = InMemorySessionStore()


def get_session_store() -> SessionStore:
    """Swap the single line in this function to change stores everywhere."""
    return _store
