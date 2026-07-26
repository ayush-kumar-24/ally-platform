"""Email service + discovery notifications, with a fake SMTP server."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import engine
from app.services import email as email_mod
from app.services import discovery_notifications as dn


def test_stub_mode_does_not_send(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_HOST", "")  # stub
    assert email_mod.send_email("x@y.com", "hi", "body") is False


class _FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        pass

    def login(self, user, pw):
        pass

    def send_message(self, msg):
        _FakeSMTP.sent.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_HOST", "smtp.test")
    monkeypatch.setattr(settings, "EMAIL_USER", "u")
    monkeypatch.setattr(settings, "EMAIL_PASSWORD", "p")
    _FakeSMTP.sent = []
    monkeypatch.setattr(email_mod.smtplib, "SMTP", _FakeSMTP)
    return _FakeSMTP


def test_send_email_builds_and_sends(smtp):
    ok = email_mod.send_email("f@x.com", "Subject!", "text body", "<p>html</p>")
    assert ok is True
    assert len(smtp.sent) == 1
    msg = smtp.sent[0]
    assert msg["To"] == "f@x.com"
    assert msg["Subject"] == "Subject!"


def test_booking_confirmation_content(smtp):
    when = datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)
    ok = dn.send_booking_confirmation("f@x.com", "Ayush", when, "https://meet.example/room")
    assert ok is True
    msg = smtp.sent[0]
    assert "confirmed" in msg["Subject"].lower()
    # multipart (text + html) -- read the plain-text part
    body = msg.get_body(preferencelist=("plain",)).get_content()
    assert "https://meet.example/room" in body


def test_send_failure_never_raises(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_HOST", "smtp.test")

    class _Boom:
        def __init__(self, *a, **k): raise OSError("smtp down")

    monkeypatch.setattr(email_mod.smtplib, "SMTP", _Boom)
    # must swallow the error and return False, not raise
    assert email_mod.send_email("f@x.com", "s", "b") is False


# --- reminder job ----------------------------------------------------------

def test_send_due_reminders_respects_prefs_and_flags(smtp, monkeypatch):
    uid = uuid.uuid4()
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    conn.execute(text("insert into auth.users (id, email) values (:i, :e)"),
                 {"i": str(uid), "e": f"t{uid.hex[:8]}@x.com"})
    fid = conn.execute(text("select create_founder_on_signup(:u,:n,:e,:p,:t,:i,:b)"),
                       dict(u=str(uid), n="Rem Test", e=f"t{uid.hex[:8]}@x.com",
                            p="v1", t="v1", i="127.0.0.1", b="test")).scalar()
    now = datetime.now(timezone.utc)
    # a call ~23h out -> inside the 24h window, reminder not yet sent
    session.execute(text(
        "insert into discovery_calls (founder_id, scheduled_at, status, meeting_link) "
        "values (:f, :s, 'confirmed', 'https://meet.example/room')"
    ), {"f": fid, "s": now + timedelta(hours=23)})
    session.flush()

    try:
        result = dn.send_due_reminders(session, now=now)
        assert result["24h"] == 1        # one reminder sent
        assert len(smtp.sent) == 1
        # running again sends nothing (flag now set)
        smtp.sent.clear()
        assert dn.send_due_reminders(session, now=now)["24h"] == 0
        assert smtp.sent == []
    finally:
        session.close()
        trans.rollback()
        conn.close()
