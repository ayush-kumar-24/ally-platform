"""The email leg of the notification system.

The failure this guards against is specific: notifications were written and
shown in the bell, and a founder who never opened the app learned nothing. So
these tests care most about the seams -- that a pending row actually produces an
email, that every row examined is stamped so nothing is retried forever, and
that the Pro gate and the opt-out are real rather than decorative.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services import notification_emails

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


class Row:
    """Stands in for a Notifications ORM row."""

    def __init__(self, founder_id=1, type="task_due_today", title="1 task due today",
                 body="Open Plan Your Day.", action_url="/app/plan",
                 created_at=None, is_read=False, sent_at=None):
        self.founder_id, self.type = founder_id, type
        self.title, self.body, self.action_url = title, body, action_url
        self.created_at = created_at or (NOW - timedelta(minutes=5))
        self.is_read, self.dismissed_at, self.sent_at = is_read, None, sent_at
        self.channel = "in_app"


class FakeEntitlements:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def has_feature(self, tier, feature):
        return self.allowed


class FakeDB:
    def __init__(self, rows, founder, types=("task_due_today", "credits_low")):
        self.rows, self.founder, self.types = rows, founder, types
        self.commits = 0

    def get(self, model, pk):
        return self.founder if self.founder and self.founder.founder_id == pk else None

    def commit(self):
        self.commits += 1


def _founder(**kw):
    kw.setdefault("plan_type", "pro")
    return SimpleNamespace(founder_id=1, email="founder@example.com",
                           full_name="Ayush",
                           notification_preferences=kw.pop("prefs", {}), **kw)


@pytest.fixture
def run(monkeypatch):
    """Runs the sweep with the DB reads stubbed, capturing emails."""
    sent = []
    monkeypatch.setattr(notification_emails, "send_notification_email",
                        lambda to, name, row: sent.append((to, row)) or True)

    def go(rows, founder, *, allowed=True, types=("task_due_today", "credits_low"),
           now=NOW):
        db = FakeDB(rows, founder, types)
        monkeypatch.setattr(notification_emails, "_email_enabled_types",
                            lambda _db: set(types) if types is not None else None)
        monkeypatch.setattr(notification_emails, "_pending_rows",
                            lambda _db: [r for r in rows
                                         if r.sent_at is None and not r.is_read
                                         and r.dismissed_at is None])
        from app.core import container as container_mod
        monkeypatch.setattr(container_mod.container, "entitlement_service",
                            lambda db: FakeEntitlements(allowed), raising=False)
        return notification_emails.send_pending_notification_emails(db, now=now)

    return SimpleNamespace(go=go, sent=sent)


def test_a_pending_notification_is_emailed_and_stamped(run):
    row = Row()
    counts = run.go([row], _founder())
    assert counts["sent"] == 1
    assert len(run.sent) == 1
    assert row.sent_at is not None


def test_the_same_notification_is_never_emailed_twice(run):
    row = Row()
    run.go([row], _founder())
    counts = run.go([row], _founder())
    assert counts["sent"] == 0
    assert len(run.sent) == 1


def test_a_founder_whose_plan_lacks_the_feature_gets_no_email(run):
    """The gate is Feature.EMAIL_NOTIFICATIONS, whatever tier carries it.

    Was named for Free, which held while email was Pro-only; Free carries the
    feature during the testing phase now, so the plan is faked rather than
    named -- what is under test is the gate, not which tier is behind it."""
    row = Row()
    counts = run.go([row], _founder(plan_type="basic"), allowed=False)
    assert counts["skipped_plan"] == 1 and run.sent == []
    # Still stamped: an unstamped row is re-examined on every run forever.
    assert row.sent_at is not None


def test_the_opt_out_is_respected(run):
    row = Row()
    counts = run.go([row], _founder(prefs={"email_notifications": False}))
    assert counts["skipped_pref"] == 1 and run.sent == []


def test_a_type_with_email_switched_off_is_not_mailed(run):
    """The per-type kill switch: one UPDATE, no deploy."""
    row = Row(type="profile_incomplete")
    counts = run.go([row], _founder())
    assert counts["skipped_type"] == 1 and run.sent == []
    assert row.sent_at is not None


def test_nothing_is_sent_when_the_switch_table_cannot_be_read(run):
    """Fails closed, unlike the writer's is_active read. An unreadable switch
    table must not become a decision to email everyone about everything."""
    row = Row()
    counts = run.go([row], _founder(), types=None)
    assert counts["sent"] == 0 and run.sent == []
    assert row.sent_at is None          # nothing stamped, so nothing is lost


def test_an_already_read_notification_is_not_emailed(run):
    """They are in the app and have seen it."""
    row = Row(is_read=True)
    counts = run.go([row], _founder())
    assert counts["sent"] == 0 and run.sent == []


def test_a_stale_notification_is_dropped_rather_than_sent(run):
    """After an outage, a week of history in one inbox is worse than silence."""
    row = Row(created_at=NOW - timedelta(days=3))
    counts = run.go([row], _founder())
    assert counts["stale"] == 1 and run.sent == []
    assert row.sent_at is not None


def test_the_per_run_cap_defers_the_overflow_instead_of_dropping_it(run):
    from app.core.config import settings
    rows = [Row() for _ in range(settings.NOTIFICATION_EMAIL_MAX_PER_RUN + 3)]
    counts = run.go(rows, _founder())
    assert counts["sent"] == settings.NOTIFICATION_EMAIL_MAX_PER_RUN
    assert counts["capped"] == 3
    # The overflow is deliberately left unstamped so the next run picks it up.
    assert [r for r in rows if r.sent_at is None] != []
    second = run.go(rows, _founder())
    assert second["sent"] == 3


def test_every_notification_for_a_founder_gets_its_own_email(run):
    """One email per notification, which is what was asked for."""
    rows = [Row(type="task_due_today"), Row(type="credits_low")]
    counts = run.go(rows, _founder())
    assert counts["sent"] == 2 and len(run.sent) == 2


def test_a_row_whose_founder_is_gone_is_closed_out(run):
    row = Row(founder_id=99)
    counts = run.go([row], None)
    assert counts["orphaned"] == 1 and row.sent_at is not None


def test_one_founders_failure_does_not_stop_another(run, monkeypatch):
    def explode(to, name, notification):
        if notification.founder_id == 1:
            raise RuntimeError("smtp exploded")
        run.sent.append((to, notification))
        return True

    monkeypatch.setattr(notification_emails, "send_notification_email", explode)
    rows = [Row(founder_id=1), Row(founder_id=2)]
    founder2 = _founder()
    founder2.founder_id = 2

    class TwoFounderDB(FakeDB):
        def get(self, model, pk):
            f = _founder()
            f.founder_id = pk
            return f

    monkeypatch.setattr(notification_emails, "_email_enabled_types",
                        lambda _db: {"task_due_today"})
    monkeypatch.setattr(notification_emails, "_pending_rows", lambda _db: rows)
    from app.core import container as container_mod
    monkeypatch.setattr(container_mod.container, "entitlement_service",
                        lambda db: FakeEntitlements(True), raising=False)

    counts = notification_emails.send_pending_notification_emails(
        TwoFounderDB(rows, None), now=NOW)
    assert counts["failed"] == 1
    assert counts["sent"] == 1          # founder 2 still got theirs
