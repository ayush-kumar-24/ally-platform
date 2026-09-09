"""A broken waitlist queue must not become a broken sign-in.

Regression for the production outage of 2026-09-09: RLS was enabled on
waitlist_registrations with no policy behind it, so register() could never
insert. The direct-signup crash handler "fell back" by calling that same
insert a second time, which failed identically and escaped POST /auth/session
as a 500 -- a founder who had just typed a correct email code got
"Something went wrong. We've logged it." and no way forward.

The queue is a courtesy. Whether the row lands must never decide whether the
request survives.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import provisioning


class Boom(Exception):
    """Stands in for whatever makes the queue insert fail -- in the real
    incident an RLS InsufficientPrivilege from psycopg2."""


class RecordingSession:
    """Enough Session for the code under test, and it remembers rollbacks:
    leaving the session dirty after a failure is how the NEXT statement on
    this connection fails for an unrelated reason."""

    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture
def identity():
    return SimpleNamespace(
        id=str(uuid4()), email="founder@example.com", provider="email", claims={},
    )


def test_queue_failure_does_not_propagate(monkeypatch, identity):
    """The whole point: an exception here used to reach the client as a 500."""
    monkeypatch.setattr(
        provisioning, "_queue_for_waitlist",
        lambda *a, **k: (_ for _ in ()).throw(Boom("RLS denied the insert")))

    db = RecordingSession()
    founder, created, waitlisted = provisioning._try_queue_for_waitlist(
        db, identity, "10.0.0.1")

    assert founder is None
    assert created is False
    # Honest: they are not provisioned and not getting in. It does not claim
    # the queue row exists, because it does not.
    assert waitlisted is True


def test_queue_failure_rolls_the_session_back(monkeypatch, identity):
    """A failed insert leaves the transaction aborted; without a rollback every
    later statement on this pooled connection fails with a misleading
    'current transaction is aborted'."""
    monkeypatch.setattr(
        provisioning, "_queue_for_waitlist",
        lambda *a, **k: (_ for _ in ()).throw(Boom("RLS denied the insert")))

    db = RecordingSession()
    provisioning._try_queue_for_waitlist(db, identity, "10.0.0.1")
    assert db.rollbacks == 1


def test_queue_failure_is_logged_loudly(monkeypatch, identity, caplog):
    """Silence here would mean a founder who is neither provisioned nor queued
    and nobody knowing -- which is how the original bug survived a whole day."""
    monkeypatch.setattr(
        provisioning, "_queue_for_waitlist",
        lambda *a, **k: (_ for _ in ()).throw(Boom("RLS denied the insert")))

    import logging
    caplog.set_level(logging.ERROR)
    with caplog.at_level(logging.ERROR):
        provisioning._try_queue_for_waitlist(RecordingSession(), identity, "10.0.0.1")

    assert any("neither provisioned nor queued" in r.message for r in caplog.records)


def test_a_working_queue_is_passed_straight_through(monkeypatch, identity):
    """The wrapper must not change the successful outcome it is guarding."""
    monkeypatch.setattr(
        provisioning, "_queue_for_waitlist", lambda *a, **k: (None, False, True))

    db = RecordingSession()
    assert provisioning._try_queue_for_waitlist(db, identity, "10.0.0.1") == (
        None, False, True)
    assert db.rollbacks == 0
