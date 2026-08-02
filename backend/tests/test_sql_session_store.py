"""SqlSessionStore -- live DB conformance + the actual resume-safety proof.

No founder/auth.users fixture needed: revoked_tokens has no FK (a jti is an
opaque token id, not founder data), so cleanup is a plain delete-by-jti.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text

from app.core.auth.session_store import InMemorySessionStore, SqlSessionStore
from app.db.session import SessionLocal

FUTURE = datetime.now(timezone.utc) + timedelta(days=1)
PAST = datetime.now(timezone.utc) - timedelta(days=1)


def _jti() -> str:
    return uuid4().hex


def _cleanup(*jtis: str) -> None:
    db = SessionLocal()
    for j in jtis:
        db.execute(text("delete from revoked_tokens where jti=:j"), {"j": j})
    db.commit()
    db.close()


# --- basic contract -----------------------------------------------------------

def test_unrevoked_jti_is_not_revoked():
    jti = _jti()
    db = SessionLocal()
    store = SqlSessionStore(db)
    assert store.is_revoked(jti) is False
    db.close()


def test_revoke_persists_and_is_revoked_true():
    jti = _jti()
    db = SessionLocal()
    store = SqlSessionStore(db)
    store.revoke(jti, expires_at=FUTURE)
    assert store.is_revoked(jti) is True
    db.close()
    _cleanup(jti)


def test_revoke_is_idempotent():
    jti = _jti()
    db = SessionLocal()
    store = SqlSessionStore(db)
    store.revoke(jti, expires_at=FUTURE)
    store.revoke(jti, expires_at=FUTURE)   # second revoke must not raise / duplicate-key error
    assert store.is_revoked(jti) is True
    db.close()
    _cleanup(jti)


def test_revoke_without_jti_is_a_noop():
    db = SessionLocal()
    store = SqlSessionStore(db)
    store.revoke("", expires_at=FUTURE)    # must not raise, must not insert an empty-key row
    assert store.is_revoked("") is False
    db.close()


# --- opportunistic pruning ----------------------------------------------------

def test_expired_rows_are_pruned_on_next_revoke():
    stale = _jti()
    fresh = _jti()
    db = SessionLocal()
    store = SqlSessionStore(db)
    store.revoke(stale, expires_at=PAST)     # already "expired" -- eligible for pruning
    assert store.is_revoked(stale) is True   # still visible immediately after insert
    store.revoke(fresh, expires_at=FUTURE)   # triggers the opportunistic prune
    remaining = db.execute(text("select count(*) from revoked_tokens where jti=:j"), {"j": stale}).scalar()
    assert remaining == 0, "expired revocation row was not pruned"
    assert store.is_revoked(fresh) is True   # the fresh one is untouched
    db.close()
    _cleanup(fresh)


# --- THE ACTUAL FIX: visible across a completely separate DB session ---------

def test_revocation_visible_across_separate_sessions():
    """The one the in-memory store could never pass: a token revoked in one DB
    session (simulating one server process / one logout request) is seen as
    revoked from a totally independent session (simulating another worker
    handling the NEXT request with that same token)."""
    jti = _jti()
    db1 = SessionLocal()
    SqlSessionStore(db1).revoke(jti, expires_at=FUTURE)
    db1.close()   # the "process" that handled the logout is gone

    db2 = SessionLocal()
    assert SqlSessionStore(db2).is_revoked(jti) is True
    db2.close()
    _cleanup(jti)


# --- in-memory store still works for hermetic callers ------------------------

def test_in_memory_store_still_works_standalone():
    store = InMemorySessionStore()
    jti = _jti()
    assert store.is_revoked(jti) is False
    store.revoke(jti)  # no expires_at -- interface stays backward compatible
    assert store.is_revoked(jti) is True
