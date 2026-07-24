"""Google-calendar mode logic, exercised with a fake Google client.

We can't reach real Google in tests, but we can prove our free/busy filtering
and event-body construction are correct by injecting a fake service.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.services import calendar as cal


class _Exec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _Freebusy:
    def __init__(self, busy):
        self._busy = busy

    def query(self, body):
        cal_id = body["items"][0]["id"]
        return _Exec({"calendars": {cal_id: {"busy": self._busy}}})


class _Events:
    def __init__(self, captured):
        self.captured = captured

    def insert(self, calendarId, body, conferenceDataVersion, sendUpdates):
        self.captured.update(calendarId=calendarId, body=body, sendUpdates=sendUpdates)
        result = {"id": "evt_123", "htmlLink": "https://calendar.google.com/event?eid=xyz"}
        # Google only returns a Meet link when a conference was actually requested.
        if "conferenceData" in body:
            result["hangoutLink"] = "https://meet.google.com/abc-defg-hij"
        return _Exec(result)


class _FakeService:
    def __init__(self, holder):
        self._holder = holder

    def freebusy(self):
        return _Freebusy(self._holder.busy)

    def events(self):
        return _Events(self._holder.captured)


class _Holder:
    def __init__(self):
        self.busy: list = []
        self.captured: dict = {}


@pytest.fixture
def google(monkeypatch):
    """Turn on Google mode with a fake client. Returns a holder with .busy/.captured.

    Workspace-style defaults here (invite + auto-Meet on) so the full event body
    is exercised; individual tests flip the flags for the personal-Gmail path.
    """
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_ID", "host@goxl.in")
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_CREDENTIALS_JSON", '{"fake": "creds"}')
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_INVITE_ATTENDEES", True)
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_CREATE_MEET", True)
    monkeypatch.setattr(settings, "GOXL_MEETING_URL", "")
    holder = _Holder()
    monkeypatch.setattr(cal, "_service", lambda: _FakeService(holder))
    return holder


def test_busy_slots_are_filtered_out(google):
    ref = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)
    grid = cal._candidate_slots(ref, 7)
    target = grid[0]
    google.busy = [{
        "start": target.isoformat(),
        "end": (target + timedelta(hours=1)).isoformat(),
    }]

    slots = cal.available_slots(ref, days=7)
    assert target not in slots        # busy -> removed
    assert grid[1] in slots           # a free slot survives


def test_create_meeting_builds_correct_event(google):
    when = datetime(2026, 7, 28, 14, 0, tzinfo=timezone.utc)
    result = cal.create_meeting(42, when, founder_email="f@x.com")

    assert result["provider"] == "google_calendar"
    assert result["event_id"] == "evt_123"
    assert result["meeting_link"] == "https://meet.google.com/abc-defg-hij"

    body = google.captured["body"]
    assert body["attendees"] == [{"email": "f@x.com"}]
    assert body["conferenceData"]["createRequest"]["conferenceSolutionKey"]["type"] == "hangoutsMeet"
    assert google.captured["sendUpdates"] == "all"


def test_personal_gmail_uses_static_link_no_conference(google, monkeypatch):
    # personal-Gmail setup: no auto-Meet, no attendee invite, static room link
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_CREATE_MEET", False)
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_INVITE_ATTENDEES", False)
    monkeypatch.setattr(settings, "GOXL_MEETING_URL", "https://meet.google.com/goxl-room")

    when = datetime(2026, 7, 28, 14, 0, tzinfo=timezone.utc)
    result = cal.create_meeting(42, when, founder_email="f@x.com")

    body = google.captured["body"]
    assert "conferenceData" not in body       # no auto-Meet on personal Gmail
    assert "attendees" not in body            # no service-account invites
    assert google.captured["sendUpdates"] == "none"
    assert body["location"] == "https://meet.google.com/goxl-room"
    assert result["meeting_link"] == "https://meet.google.com/goxl-room"


def test_freebusy_failure_falls_back_to_candidates(google, monkeypatch):
    def _boom():
        raise RuntimeError("google down")

    monkeypatch.setattr(cal, "_service", _boom)
    ref = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)
    # a Google outage must not break availability -- we return the candidate grid
    assert cal.available_slots(ref, days=7) == cal._candidate_slots(ref, 7)
