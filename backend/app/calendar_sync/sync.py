"""Pushing Plan Your Day tasks onto the founder's Google Calendar.

One-way, Ally -> Google. Nothing here reads changes made in Google Calendar back
into Ally; that needs webhooks and conflict resolution and is a separate piece
of work.

**Every public function in this module swallows its own failures.** A task is
the founder's data; a calendar event is a convenience layered on top. If Google
is down, rate-limiting us, or the founder revoked access an hour ago, the task
still saves and the only consequence is a sync-status badge. The functions
return a status string rather than raising, and the caller records it.

The reminder is the entire point of the feature -- it is what replaces a
notification system Ally does not have -- so events are TIMED, never all-day.
Google counts reminder offsets backwards from the event start, so on an all-day
event (which starts at midnight) a 30-minutes-before popup fires at 23:30 the
night before, and a morning-of popup cannot be expressed at all. A task with no
time of its own is therefore scheduled at CALENDAR_DEFAULT_TASK_HOUR so the
chosen offset lands somewhere a person is awake.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import httpx
from sqlalchemy.orm import Session

from app.calendar_sync import connections
from app.calendar_sync.db_models import CalendarConnectionRow
from app.core.config import settings
from app.core.logger import logger

_EVENTS_ENDPOINT = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
_TIMEOUT = 15.0

# planning_tasks.calendar_sync_status
SYNCED = "synced"
FAILED = "failed"
SKIPPED = "skipped"      # nothing to do: no connection, or no date on the task
PENDING = "pending"


def _window(due_date: date, due_time: time | None) -> tuple[datetime, datetime]:
    start = datetime.combine(
        due_date, due_time or time(hour=settings.CALENDAR_DEFAULT_TASK_HOUR))
    return start, start + timedelta(minutes=settings.CALENDAR_EVENT_DURATION_MINUTES)


def _event_body(title: str, due_date: date, due_time: time | None,
                timezone_name: str) -> dict:
    start, end = _window(due_date, due_time)
    return {
        "summary": title,
        # Says where it came from without shouting. A founder scanning a busy
        # week should be able to tell which entries Ally put there.
        "description": "Added from Plan Your Day in Ally.",
        "source": {"title": "Ally · Plan Your Day", "url": "https://goxlally.ai/app/plan"},
        "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
        "reminders": {
            # useDefault=False, or Google applies the founder's own calendar
            # defaults and silently ignores these overrides -- which would mean
            # the one feature this exists for depends on a setting we never see.
            "useDefault": False,
            "overrides": [
                {"method": "popup",
                 "minutes": settings.CALENDAR_REMINDER_MINUTES_BEFORE},
            ],
        },
    }


def _request(method: str, url: str, token: str, json: dict | None = None) -> httpx.Response:
    return httpx.request(method, url, timeout=_TIMEOUT, json=json,
                         headers={"Authorization": f"Bearer {token}",
                                  "Content-Type": "application/json"})


def _usable_connection(db: Session, founder_id: int) -> tuple[CalendarConnectionRow, str] | None:
    row = connections.get_connection(db, founder_id)
    if row is None:
        return None
    token = connections.access_token(db, row)
    if not token:
        return None
    return row, token


def push_task(db: Session, founder_id: int, *, task_id: str, title: str,
              due_date: date | None, due_time: time | None,
              existing_event_id: str | None,
              timezone_name: str = "UTC") -> tuple[str, str | None]:
    """Create or update this task's calendar event.

    Returns (status, event_id). Never raises.

    Updates in place when we already own an event id, which is what stops an
    edit from leaving a trail of duplicates across the founder's week. A 404 on
    update means the event is gone from Google's side -- deleted by the founder
    in their calendar app, most likely -- so we create a replacement rather than
    treating it as an error.
    """
    if due_date is None:
        # No date, nothing to put on a calendar. Not a failure: most tasks are
        # just a list item, and badging them "failed" would be a lie.
        return SKIPPED, existing_event_id

    usable = _usable_connection(db, founder_id)
    if usable is None:
        return SKIPPED, existing_event_id
    _, token = usable

    body = _event_body(title, due_date, due_time, timezone_name)

    try:
        if existing_event_id:
            response = _request("PATCH", f"{_EVENTS_ENDPOINT}/{existing_event_id}", token, body)
            if response.status_code == 404:
                response = _request("POST", _EVENTS_ENDPOINT, token, body)
        else:
            response = _request("POST", _EVENTS_ENDPOINT, token, body)

        if response.status_code >= 400:
            logger.warning("calendar event push failed",
                           extra={"founder_id": founder_id, "task_id": task_id,
                                  "status": response.status_code,
                                  "body": response.text[:300]})
            return FAILED, existing_event_id

        return SYNCED, response.json().get("id") or existing_event_id

    except Exception as exc:
        logger.warning("calendar event push errored",
                       extra={"founder_id": founder_id, "task_id": task_id}, exc_info=exc)
        return FAILED, existing_event_id


def delete_event(db: Session, founder_id: int, event_id: str | None) -> bool:
    """Remove a task's event. Never raises; True only if it is really gone.

    410 and 404 both count as success -- already deleted is the state we wanted.
    """
    if not event_id:
        return True

    usable = _usable_connection(db, founder_id)
    if usable is None:
        return False
    _, token = usable

    try:
        response = _request("DELETE", f"{_EVENTS_ENDPOINT}/{event_id}", token)
        if response.status_code in (200, 204, 404, 410):
            return True
        logger.warning("calendar event delete failed",
                       extra={"founder_id": founder_id, "event_id": event_id,
                              "status": response.status_code})
        return False
    except Exception as exc:
        logger.warning("calendar event delete errored",
                       extra={"founder_id": founder_id, "event_id": event_id}, exc_info=exc)
        return False
