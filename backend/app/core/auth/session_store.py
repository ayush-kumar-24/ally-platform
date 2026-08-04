"""Session (refresh-token) revocation store.

In the backend-issued-token model, a "session" is a live refresh token. Logout
and refresh-rotation both need to mark a specific refresh token (by its jti) as
no longer usable. That is all this tracks.

`SqlSessionStore` is the durable, DB-backed implementation, persisting to
`revoked_tokens` (migration f6b8c0d2e4a5) -- request-scoped, built per-request
with the request's DB session, same shape as the chat repositories fix.
`InMemorySessionStore` remains for tests/hermetic callers that construct a store
directly without a DB session.

NOTE ON THE PRIOR STATE: this used to be process-local only ("scaffolding"),
which meant every logout / refresh-rotation was forgotten on restart and
invisible across worker processes -- a revoked token could validate as live on a
different instance. Adding a table for this was flagged as needing explicit
sign-off (a database change is not a decision this module makes unilaterally);
that sign-off was given, and this is the smallest table that closes the gap. The
pre-existing `sessions` table belongs to the diagnosis flow (question progress,
risk scores, distress signals) and must not be repurposed here.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.auth import RevokedTokenRow


class SessionStore(ABC):
    @abstractmethod
    def is_revoked(self, jti: str) -> bool: ...

    @abstractmethod
    def revoke(self, jti: str, *, expires_at: datetime | None = None) -> None: ...


class InMemorySessionStore(SessionStore):
    """Process-local revocation set. Cleared on restart -- for tests and any
    hermetic caller that builds a store without a DB session."""

    def __init__(self) -> None:
        self._revoked: set[str] = set()

    def is_revoked(self, jti: str) -> bool:
        return jti in self._revoked

    def revoke(self, jti: str, *, expires_at: datetime | None = None) -> None:
        if jti:
            self._revoked.add(jti)


class SqlSessionStore(SessionStore):
    """Durable, DB-backed revocation store. FAILS LOUD, not resilient-degrade:
    this repository IS the revocation record -- a silent degrade here would mean
    'logout succeeded' while the token that should be dead remained usable
    elsewhere, which is a security hole, not a UX gap."""

    def __init__(self, db: Session):
        self.db = db

    def is_revoked(self, jti: str) -> bool:
        return self.db.execute(
            select(RevokedTokenRow.jti).where(RevokedTokenRow.jti == jti)
        ).scalar_one_or_none() is not None

    def revoke(self, jti: str, *, expires_at: datetime | None = None) -> None:
        if not jti:
            return
        # A row already there (e.g. a retried logout) is not an error -- revoking
        # an already-revoked token is idempotent by definition.
        if self.is_revoked(jti):
            self.db.commit()
            return
        self.db.add(RevokedTokenRow(
            jti=jti,
            expires_at=expires_at or datetime.max.replace(tzinfo=timezone.utc),
        ))
        # Opportunistic prune: a revoked row is useless once its own token would
        # have expired anyway (decode_token rejects it on `exp` regardless of
        # revocation state). Bounds table growth without a separate cron job.
        self.db.execute(delete(RevokedTokenRow).where(RevokedTokenRow.expires_at < datetime.now(timezone.utc)))
        self.db.commit()


_store: SessionStore = InMemorySessionStore()


def get_session_store(db: Session | None = None) -> SessionStore:
    """The durable store when a DB session is available (the real request path);
    the in-memory scaffold otherwise (hermetic tests / callers with no DB)."""
    if db is not None:
        return SqlSessionStore(db)
    return _store
