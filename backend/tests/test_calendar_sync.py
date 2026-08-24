"""Google Calendar sync.

The rule these tests exist to protect: **a calendar problem never costs a
founder their task.** Most of what follows is failure injection, because the
happy path is the easy half — what matters is that a revoked grant, a 500 from
Google, a rate limit or a missing encryption key all end with the task saved and
a badge, never an exception reaching the request.

Google is never contacted. httpx is monkeypatched at the module boundary, which
also lets the event body be asserted exactly — the reminder override is the
entire feature, and a silent change to it would be invisible in any test that
only checked for a 2xx.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.calendar_sync import connections, crypto, google_oauth, state, sync
from app.calendar_sync.db_models import STATUS_ACTIVE, STATUS_ERROR, STATUS_REVOKED
from app.core.config import settings

FERNET_KEY = "8Nq2rW1sT4vX7yZ0aB3cD6eF9gH2iJ5kL8mN1oP4qR0="


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setattr(settings, "CALENDAR_TOKEN_KEY", FERNET_KEY)
    crypto._fernet.cache_clear()
    yield
    crypto._fernet.cache_clear()


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or str(payload or "")
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload


class _FakeSession:
    """Just enough Session for the connection helpers."""

    def __init__(self):
        self.committed = 0
        self.rolled_back = 0
        self.deleted = []

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def delete(self, obj):
        self.deleted.append(obj)

    def add(self, obj):
        pass

    def refresh(self, obj):
        pass


def _connection(**overrides):
    row = SimpleNamespace(
        connection_id="c1", founder_id=7, provider="google",
        account_email="founder@gmail.com",
        access_token_encrypted="", refresh_token_encrypted="",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        status=STATUS_ACTIVE, last_error="",
        connected_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    for field, value in overrides.items():
        setattr(row, field, value)
    return row


# --- token encryption --------------------------------------------------------

def test_tokens_round_trip(key):
    assert crypto.decrypt(crypto.encrypt("refresh-token-abc")) == "refresh-token-abc"


def test_ciphertext_is_not_the_plaintext(key):
    """The point of the exercise: a database leak must not hand over calendars."""
    assert "refresh-token-abc" not in crypto.encrypt("refresh-token-abc")


def test_empty_stays_empty(key):
    # Google omits refresh_token on re-consent; an encrypted "" would be
    # indistinguishable from a real token until it failed.
    assert crypto.encrypt("") == ""
    assert crypto.decrypt("") == ""


def test_without_a_key_encryption_fails_closed(monkeypatch):
    """Never a silent fallback to plaintext."""
    monkeypatch.setattr(settings, "CALENDAR_TOKEN_KEY", "")
    crypto._fernet.cache_clear()
    assert crypto.is_available() is False
    with pytest.raises(crypto.TokenEncryptionUnavailableError):
        crypto.encrypt("secret")
    crypto._fernet.cache_clear()


def test_a_malformed_key_is_rejected_not_used(monkeypatch):
    monkeypatch.setattr(settings, "CALENDAR_TOKEN_KEY", "not-a-fernet-key")
    crypto._fernet.cache_clear()
    assert crypto.is_available() is False
    crypto._fernet.cache_clear()


def test_tampered_ciphertext_raises(key):
    """Fernet authenticates. A flipped byte must not decrypt to garbage we then
    send to Google as someone's credential."""
    from cryptography.fernet import InvalidToken

    token = crypto.encrypt("refresh-token-abc")
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(InvalidToken):
        crypto.decrypt(tampered)


# --- OAuth state -------------------------------------------------------------

_UUID = "7a70613d-6fb9-58a0-8642-a85fdaa135f4"


def test_state_round_trips_the_founder_and_their_uuid():
    """The UUID matters as much as the id: the callback needs it to set the RLS
    context, because it has no authenticated dependency that would."""
    assert state.read(state.issue(4242, _UUID)) == (4242, _UUID)


def test_tampered_state_is_rejected():
    """The callback has no auth header, so state is the ONLY thing binding the
    flow to a founder. If it were forgeable, anyone could attach their calendar
    to someone else's account."""
    token = state.issue(4242, _UUID)
    with pytest.raises(state.InvalidOAuthStateError):
        state.read(token[:-6] + "xxxxxx")


def test_missing_state_is_rejected():
    with pytest.raises(state.InvalidOAuthStateError):
        state.read(None)


def test_a_token_issued_for_something_else_is_rejected():
    """Signed with the same SECRET_KEY, but not for this purpose."""
    from jose import jwt

    other = jwt.encode(
        {"founder_id": 1, "founder_uuid": _UUID, "purpose": "password_reset",
         "exp": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())},
        settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(state.InvalidOAuthStateError):
        state.read(other)


def test_expired_state_is_rejected():
    from jose import jwt

    stale = jwt.encode(
        {"founder_id": 1, "founder_uuid": _UUID, "purpose": "calendar_oauth_state",
         "exp": int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp())},
        settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(state.InvalidOAuthStateError):
        state.read(stale)


# --- the consent URL ---------------------------------------------------------

def test_authorization_url_requests_offline_access_and_forces_consent(monkeypatch):
    """Both are required to reliably get a refresh token.

    offline alone yields one only on the FIRST authorisation for a client/user
    pair, so a founder who disconnects and reconnects would come back with a
    one-hour token and no way to renew it.
    """
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "https://api.example/cb")
    url = google_oauth.authorization_url("st")
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "state=st" in url


def test_scope_is_events_not_full_calendar(monkeypatch):
    """calendar.events is enough to manage our own events. The broader
    `calendar` scope would also grant reading every calendar they can see."""
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "https://api.example/cb")
    url = google_oauth.authorization_url("st")
    assert "calendar.events" in url
    assert "auth%2Fcalendar+" not in url and "auth%2Fcalendar&" not in url


# --- the event body ----------------------------------------------------------

def test_event_is_timed_and_carries_the_reminder_override():
    """The reminder IS the feature -- it replaces a notification system Ally
    does not have. useDefault must be False or Google applies the founder's own
    defaults and ignores ours entirely."""
    body = sync._event_body("Call five labs", date(2026, 8, 26), time(14, 30), "Asia/Kolkata")

    assert body["start"]["dateTime"].startswith("2026-08-26T14:30")
    assert body["start"]["timeZone"] == "Asia/Kolkata"
    assert body["reminders"]["useDefault"] is False
    assert body["reminders"]["overrides"] == [
        {"method": "popup", "minutes": settings.CALENDAR_REMINDER_MINUTES_BEFORE}]


def test_a_task_with_no_time_lands_at_the_default_hour():
    """Not all-day: Google counts reminder offsets back from the start, so an
    all-day event's "30 minutes before" fires at 23:30 the night before."""
    body = sync._event_body("Task", date(2026, 8, 26), None, "UTC")
    assert body["start"]["dateTime"].startswith(
        f"2026-08-26T{settings.CALENDAR_DEFAULT_TASK_HOUR:02d}:00")
    assert "date" not in body["start"]      # never an all-day event


# --- pushing an event --------------------------------------------------------

@pytest.fixture
def connected(monkeypatch, key):
    """A founder with a live connection and a valid access token."""
    row = _connection(access_token_encrypted=crypto.encrypt("access-1"))
    monkeypatch.setattr(connections, "get_connection", lambda db, fid, provider="google": row)
    return row


def test_push_creates_an_event_and_returns_its_id(monkeypatch, connected):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url))
        return _Response(200, {"id": "evt-1"})

    monkeypatch.setattr(sync.httpx, "request", fake_request)
    status, event_id = sync.push_task(
        _FakeSession(), 7, task_id="t1", title="Call five labs",
        due_date=date(2026, 8, 26), due_time=time(9, 0), existing_event_id=None)

    assert (status, event_id) == (sync.SYNCED, "evt-1")
    assert calls[0][0] == "POST"


def test_editing_updates_the_same_event_rather_than_duplicating(monkeypatch, connected):
    """The whole reason the event id is stored on the task."""
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url))
        return _Response(200, {"id": "evt-1"})

    monkeypatch.setattr(sync.httpx, "request", fake_request)
    status, event_id = sync.push_task(
        _FakeSession(), 7, task_id="t1", title="Edited",
        due_date=date(2026, 8, 26), due_time=None, existing_event_id="evt-1")

    assert (status, event_id) == (sync.SYNCED, "evt-1")
    assert len(calls) == 1
    assert calls[0][0] == "PATCH" and calls[0][1].endswith("/evt-1")


def test_an_event_deleted_in_google_is_recreated(monkeypatch, connected):
    """404 on update means they deleted it in their calendar app. Recreate
    rather than reporting a failure the founder can do nothing about."""
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(method)
        return _Response(404) if method == "PATCH" else _Response(200, {"id": "evt-2"})

    monkeypatch.setattr(sync.httpx, "request", fake_request)
    status, event_id = sync.push_task(
        _FakeSession(), 7, task_id="t1", title="T",
        due_date=date(2026, 8, 26), due_time=None, existing_event_id="evt-old")

    assert calls == ["PATCH", "POST"]
    assert (status, event_id) == (sync.SYNCED, "evt-2")


def test_a_google_error_reports_failed_and_keeps_the_old_event_id(monkeypatch, connected):
    monkeypatch.setattr(sync.httpx, "request",
                        lambda *a, **k: _Response(500, {}, "upstream boom"))
    status, event_id = sync.push_task(
        _FakeSession(), 7, task_id="t1", title="T",
        due_date=date(2026, 8, 26), due_time=None, existing_event_id="evt-1")
    assert status == sync.FAILED
    # Not cleared: the event still exists, and forgetting its id would create a
    # duplicate on the next successful save.
    assert event_id == "evt-1"


def test_a_network_error_reports_failed_rather_than_raising(monkeypatch, connected):
    import httpx as real_httpx

    def boom(*a, **k):
        raise real_httpx.ConnectError("no route to host")

    monkeypatch.setattr(sync.httpx, "request", boom)
    status, _ = sync.push_task(_FakeSession(), 7, task_id="t1", title="T",
                               due_date=date(2026, 8, 26), due_time=None,
                               existing_event_id=None)
    assert status == sync.FAILED


def test_no_date_is_skipped_not_failed(connected):
    """Most tasks are just list items. Badging them 'failed' would be a lie."""
    assert sync.push_task(_FakeSession(), 7, task_id="t1", title="T",
                          due_date=None, due_time=None,
                          existing_event_id=None) == (sync.SKIPPED, None)


def test_no_connection_is_skipped(monkeypatch):
    monkeypatch.setattr(connections, "get_connection", lambda db, fid, provider="google": None)
    assert sync.push_task(_FakeSession(), 7, task_id="t1", title="T",
                          due_date=date(2026, 8, 26), due_time=None,
                          existing_event_id=None) == (sync.SKIPPED, None)


# --- deleting ----------------------------------------------------------------

@pytest.mark.parametrize("code", [200, 204, 404, 410])
def test_delete_treats_already_gone_as_success(monkeypatch, connected, code):
    monkeypatch.setattr(sync.httpx, "request", lambda *a, **k: _Response(code))
    assert sync.delete_event(_FakeSession(), 7, "evt-1") is True


def test_delete_of_a_task_that_never_synced_is_a_no_op(connected):
    assert sync.delete_event(_FakeSession(), 7, None) is True


# --- token refresh -----------------------------------------------------------

def test_a_valid_token_is_used_without_calling_google(monkeypatch, key):
    def fail(*a, **k):
        raise AssertionError("should not refresh a token that is still valid")

    monkeypatch.setattr(google_oauth, "refresh", fail)
    row = _connection(access_token_encrypted=crypto.encrypt("still-good"))
    assert connections.access_token(_FakeSession(), row) == "still-good"


def test_an_expired_token_is_refreshed_silently(monkeypatch, key):
    row = _connection(
        access_token_encrypted=crypto.encrypt("old"),
        refresh_token_encrypted=crypto.encrypt("refresh-1"),
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    monkeypatch.setattr(google_oauth, "refresh", lambda rt: google_oauth.TokenBundle(
        access_token="fresh", refresh_token="",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))

    assert connections.access_token(_FakeSession(), row) == "fresh"
    assert row.status == STATUS_ACTIVE
    assert crypto.decrypt(row.access_token_encrypted) == "fresh"


def test_a_revoked_grant_marks_the_connection_for_reconnection(monkeypatch, key):
    """invalid_grant is permanent -- the founder must act, so say so."""
    row = _connection(
        access_token_encrypted=crypto.encrypt("old"),
        refresh_token_encrypted=crypto.encrypt("refresh-1"),
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5))

    def revoked(rt):
        raise google_oauth.GoogleAccessRevokedError("Token has been expired or revoked.")

    monkeypatch.setattr(google_oauth, "refresh", revoked)
    assert connections.access_token(_FakeSession(), row) is None
    assert row.status == STATUS_REVOKED


def test_a_transient_failure_does_not_revoke_the_connection(monkeypatch, key):
    """A 5xx is not evidence the founder withdrew access. Prompting them to
    reconnect over an outage teaches them to ignore the prompt that matters."""
    row = _connection(
        access_token_encrypted=crypto.encrypt("old"),
        refresh_token_encrypted=crypto.encrypt("refresh-1"),
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5))

    def flaky(rt):
        raise google_oauth.GoogleOAuthError("503 from Google")

    monkeypatch.setattr(google_oauth, "refresh", flaky)
    assert connections.access_token(_FakeSession(), row) is None
    assert row.status == STATUS_ERROR
    assert row.status != STATUS_REVOKED


def test_expired_with_no_refresh_token_asks_for_reconnection(key):
    row = _connection(
        access_token_encrypted=crypto.encrypt("old"), refresh_token_encrypted="",
        token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    assert connections.access_token(_FakeSession(), row) is None
    assert row.status == STATUS_REVOKED


def test_without_an_encryption_key_no_token_is_returned(monkeypatch):
    monkeypatch.setattr(settings, "CALENDAR_TOKEN_KEY", "")
    crypto._fernet.cache_clear()
    assert connections.access_token(_FakeSession(), _connection()) is None
    crypto._fernet.cache_clear()


def test_reconnect_keeps_an_existing_refresh_token_when_google_omits_one(monkeypatch, key):
    """Google frequently omits refresh_token on re-consent. Blanking the stored
    one would leave a connection that works for an hour and then dies."""
    row = _connection(refresh_token_encrypted=crypto.encrypt("original-refresh"))
    monkeypatch.setattr(connections, "get_connection", lambda db, fid, provider="google": row)

    connections.save_connection(_FakeSession(), 7, google_oauth.TokenBundle(
        access_token="new-access", refresh_token="",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))

    assert crypto.decrypt(row.refresh_token_encrypted) == "original-refresh"


def test_state_without_a_uuid_is_rejected():
    """A state carrying only founder_id would write the row with no RLS context.

    That is the exact failure this pair of fields exists to prevent: under
    row-level security the SELECT silently returns nothing and the INSERT is
    refused, so the founder sees "not connected" and then "could not save".
    Refusing the callback outright is better than half-completing it.
    """
    from jose import jwt

    legacy = jwt.encode(
        {"founder_id": 7, "purpose": "calendar_oauth_state",
         "exp": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())},
        settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(state.InvalidOAuthStateError):
        state.read(legacy)


def test_a_malformed_uuid_is_refused_at_mint_time():
    """Fails while the founder is still in an authenticated request, where a real
    error can be shown -- not at the callback, whose only outcome is a redirect."""
    with pytest.raises(ValueError):
        state.issue(7, "not-a-uuid")
