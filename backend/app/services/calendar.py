"""Calendar / scheduling integration -- Google Calendar API.

Two modes, chosen automatically:

- **Real** (when GOOGLE_CALENDAR_ID + GOOGLE_CALENDAR_CREDENTIALS_JSON are set):
  `available_slots` filters candidate times against the host calendar's free/busy,
  and `create_meeting` inserts an event with a Google Meet link and invites the
  founder.
- **Stub** (when they're not set -- dev, tests, or before the service account
  exists): deterministic slots + a placeholder meeting link, so the whole booking
  flow works end to end without Google.

The Google client is imported lazily and cached, so importing this module is
cheap and never requires credentials.

NOTE for going live: a service account can create events on a calendar shared
with it, but inviting attendees / sending email invites may require domain-wide
delegation. If invites don't arrive, that's the cause -- the Meet link is still
created and stored either way.
"""

import json
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache

from app.core.config import settings
from app.core.logger import logger

GOXL_HOST = "GoXL Team"
DEFAULT_TIMEZONE = settings.DISCOVERY_TIMEZONE

# Candidate business hours (UTC) offered before free/busy filtering.
_SLOT_HOURS = (10, 11, 14, 15, 16)
_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


@lru_cache
def _service():
    """Build and cache the Google Calendar client from the service-account key.

    Prefers the key file (GOOGLE_CALENDAR_CREDENTIALS_FILE); falls back to inline
    JSON (GOOGLE_CALENDAR_CREDENTIALS_JSON).
    """
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if settings.GOOGLE_CALENDAR_CREDENTIALS_FILE:
        creds = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_CALENDAR_CREDENTIALS_FILE, scopes=_CALENDAR_SCOPES
        )
    else:
        info = json.loads(settings.GOOGLE_CALENDAR_CREDENTIALS_JSON)
        creds = service_account.Credentials.from_service_account_info(info, scopes=_CALENDAR_SCOPES)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _candidate_slots(from_dt: datetime, days: int) -> list[datetime]:
    """The grid of possible slots: weekday business hours, starting tomorrow."""
    slots: list[datetime] = []
    start = (from_dt + timedelta(days=1)).date()
    for offset in range(days):
        day = start + timedelta(days=offset)
        if day.weekday() >= 5:  # skip Sat/Sun
            continue
        for hour in _SLOT_HOURS:
            slots.append(datetime.combine(day, time(hour=hour), tzinfo=timezone.utc))
    return slots


def available_slots(from_dt: datetime, days: int = 7) -> list[datetime]:
    """Bookable slots over the next `days` weekdays.

    Real mode removes anything overlapping the host calendar's busy blocks; stub
    mode returns the full candidate grid.
    """
    candidates = _candidate_slots(from_dt, days)
    if not settings.google_calendar_enabled:
        return candidates

    try:
        service = _service()
        resp = service.freebusy().query(body={
            "timeMin": from_dt.isoformat(),
            "timeMax": (from_dt + timedelta(days=days + 1)).isoformat(),
            "items": [{"id": settings.GOOGLE_CALENDAR_ID}],
        }).execute()
        busy = resp["calendars"][settings.GOOGLE_CALENDAR_ID]["busy"]
        busy_ranges = [
            (datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"]))
            for b in busy
        ]
    except Exception:
        # Availability lookup should never take the endpoint down -- fall back to
        # the candidate grid and let the booking step catch a real conflict.
        logger.warning("Google Calendar free/busy query failed; returning candidate slots")
        return candidates

    duration = timedelta(minutes=settings.DISCOVERY_CALL_DURATION_MINUTES)
    return [
        s for s in candidates
        if not any(s < b_end and (s + duration) > b_start for b_start, b_end in busy_ranges)
    ]


def create_meeting(
    founder_id: int,
    scheduled_at: datetime,
    founder_email: str | None = None,
    duration_minutes: int | None = None,
) -> dict:
    """Create the meeting and return its join details + provider event id.

    Real mode inserts a Google Calendar event with a Meet link; stub mode returns
    a placeholder. The returned `event_id` is None in stub mode.
    """
    duration_minutes = duration_minutes or settings.DISCOVERY_CALL_DURATION_MINUTES

    if not settings.google_calendar_enabled:
        slot = scheduled_at.strftime("%Y%m%dT%H%M")
        return {
            "meeting_link": f"https://meet.goxl.stub/{founder_id}/{slot}",
            "host": GOXL_HOST,
            "provider": "stub",
            "event_id": None,
        }

    service = _service()
    end = scheduled_at + timedelta(minutes=duration_minutes)
    body = {
        "summary": "GoXL Discovery Call",
        "start": {"dateTime": scheduled_at.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }

    # --- Video link ---
    # Workspace: let Google auto-create a Meet room. Personal Gmail: attach the
    # configured static room, since auto-Meet is forbidden there.
    conference_version = 0
    if settings.GOOGLE_CALENDAR_CREATE_MEET:
        body["conferenceData"] = {
            "createRequest": {
                "requestId": f"goxl-{founder_id}-{scheduled_at.strftime('%Y%m%dT%H%M')}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
        conference_version = 1
    elif settings.GOXL_MEETING_URL:
        body["location"] = settings.GOXL_MEETING_URL
        body["description"] = f"Join the call: {settings.GOXL_MEETING_URL}"

    # --- Attendees ---
    # Only with Workspace + domain-wide delegation; otherwise the app sends the link.
    send_updates = "none"
    if founder_email and settings.GOOGLE_CALENDAR_INVITE_ATTENDEES:
        body["attendees"] = [{"email": founder_email}]
        send_updates = "all"

    created = service.events().insert(
        calendarId=settings.GOOGLE_CALENDAR_ID,
        body=body,
        conferenceDataVersion=conference_version,
        sendUpdates=send_updates,
    ).execute()

    meeting_link = (
        created.get("hangoutLink")
        or settings.GOXL_MEETING_URL
        or created.get("htmlLink")
    )
    return {
        "meeting_link": meeting_link,
        "host": GOXL_HOST,
        "provider": "google_calendar",
        "event_id": created.get("id"),
    }
