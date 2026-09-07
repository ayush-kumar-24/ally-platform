"""The rules that make the bell usable rather than noisy.

These test `notify()` -- the single door every notification goes through --
because the four things it enforces are the difference between a feed founders
open and one they learn to ignore:

  * a switched-off type writes nothing (the kill switch works)
  * the same dedup key writes once (a sweep running four times a day does not
    say "your credits expire soon" four times a day)
  * a founder who muted the bell gets nothing
  * a failure never reaches the caller

No database: the session is faked, because what is under test is the decision
logic, not SQLAlchemy.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.notifications import writer


@pytest.fixture(autouse=True)
def _fresh_cache():
    writer.reset_type_cache()
    yield
    writer.reset_type_cache()


def _db(*, active_types=("credits_low",), existing_dedup=False):
    """A Session stand-in: answers the active-types read and the dedup lookup."""
    db = MagicMock()

    def execute(stmt, *a, **k):
        result = MagicMock()
        text = str(getattr(stmt, "text", stmt))
        if "notification_types" in text:
            result.scalars.return_value.all.return_value = list(active_types)
        else:
            result.first.return_value = (1,) if existing_dedup else None
        return result

    db.execute.side_effect = execute
    return db


FOUNDER = SimpleNamespace(founder_id=1, notification_preferences={})


def _call(db, **over):
    kwargs = dict(founder_id=1, type="credits_low", title="t", body="b", founder=FOUNDER)
    kwargs.update(over)
    return writer.notify(db, **kwargs)


def test_a_notification_is_written():
    db = _db()
    assert _call(db) is not None
    assert db.add.called and db.commit.called


def test_a_switched_off_type_writes_nothing():
    """`is_active = false` is the kill switch -- one UPDATE silences a type for
    everyone, with no deploy. If this stops working, that promise is gone."""
    db = _db(active_types=())
    assert _call(db) is None
    assert not db.add.called


def test_the_same_dedup_key_writes_once():
    """The sweep re-evaluates the same conditions every few hours. Without this
    a founder is told their credits expire soon on every single run."""
    db = _db(existing_dedup=True)
    assert _call(db, dedup_key="credits_low:2026-W37") is None
    assert not db.add.called


def test_no_dedup_key_means_always_write():
    """One-off events (a payment failed) legitimately have no key and must not
    be forced to invent one."""
    db = _db(existing_dedup=True)
    assert _call(db, dedup_key=None) is not None


def test_a_muted_founder_gets_nothing():
    db = _db()
    muted = SimpleNamespace(founder_id=1, notification_preferences={"in_app_all": False})
    assert _call(db, founder=muted) is None
    assert not db.add.called


def test_the_default_is_on_when_no_preference_is_set():
    db = _db()
    blank = SimpleNamespace(founder_id=1, notification_preferences=None)
    assert _call(db, founder=blank) is not None


def test_a_database_failure_never_reaches_the_caller():
    """Notifying is always a side effect of something more important. A booking
    must not fail because a bell row could not be written."""
    db = _db()
    db.commit.side_effect = __import__("sqlalchemy").exc.SQLAlchemyError("boom")
    assert _call(db) is None          # returns None rather than raising
    assert db.rollback.called


def test_a_long_title_is_truncated_not_rejected():
    """title is varchar(200). A long business name in a template must not turn
    into an insert error."""
    db = _db()
    _call(db, title="x" * 500)
    written = db.add.call_args[0][0]
    assert len(written.title) == 200


def test_unreadable_type_table_fails_open():
    """On a target that has not migrated, we still write.

    A silent notification blackout is a worse failure than a possible extra row,
    and the foreign key on `notifications.type` still rejects a bad value -- so
    failing open here cannot produce a corrupt row, only an unfiltered one.
    """
    db = MagicMock()
    db.execute.side_effect = __import__("sqlalchemy").exc.SQLAlchemyError("no table")
    assert _call(db) is not None
    assert db.add.called
