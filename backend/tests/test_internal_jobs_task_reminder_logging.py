"""POST /internal/jobs/send-task-reminders -- the counts must be LOGGED, not
just returned.

WHY THIS FILE EXISTS. EventBridge Scheduler does not record a target's
response body anywhere, so the counts this endpoint returns were invisible to
the thing that calls it: a run that sent nothing and a run that dropped forty
reminders as stale both looked like one successful invocation. The counts are
logged now, and two CloudWatch metric filters + alarms are built on that log
line:

  * `stale` above zero for a sustained period -- reminders are coming due
    faster than the endpoint is called, so founders are getting silence.
  * `email_configured` false -- EMAIL_HOST is unset, so nothing can be sent
    however often the schedule fires.

Those alarms read JSON FIELDS, not a formatted message, which is what the
last test here pins: JSONFormatter must promote every count to a top-level
key. A refactor that logged `f"...{result}"` instead would still look like a
perfectly good log line and would silently break both alarms.
"""

from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.logger import JSONFormatter
from app.main import app

BASE = "/api/v1/internal/jobs"
SECRET = "test-internal-secret"

#: What send_due_reminders returns. Non-zero in a few places on purpose --
#: an all-zero fixture would pass even if the log dropped the values.
COUNTS = {"sent": 3, "in_app": 1, "skipped_pref": 0,
          "stale": 2, "orphaned": 0, "failed": 0}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_JOBS_SECRET", SECRET)
    return TestClient(app)


@pytest.fixture
def swept(monkeypatch):
    """Stub the sweep itself -- this is about what the endpoint reports, not
    about what the sweep decides. Patched on the module the endpoint imports
    from inside the function body, so the lookup happens at call time."""
    import app.services.task_reminders as tr
    monkeypatch.setattr(tr, "send_due_reminders", lambda db: dict(COUNTS))


def _post(client):
    return client.post(f"{BASE}/send-task-reminders",
                       headers={"X-Internal-Secret": SECRET})


def test_the_response_carries_the_counts_and_the_email_flag(client, swept):
    r = _post(client)
    assert r.status_code == 200
    body = r.json()
    for key, value in COUNTS.items():
        assert body[key] == value
    assert body["email_configured"] is settings.email_enabled


def test_the_same_counts_are_logged(client, swept, caplog):
    with caplog.at_level(logging.INFO):
        _post(client)

    matching = [r for r in caplog.records
                if r.getMessage() == "task reminder job complete"]
    assert len(matching) == 1, "expected exactly one completion log line"

    record = matching[0]
    for key, value in COUNTS.items():
        assert getattr(record, key) == value, f"{key} missing from the log record"
    assert hasattr(record, "email_configured")


def test_stale_survives_when_it_is_the_only_thing_wrong(client, monkeypatch, caplog):
    """The alarm that matters most fires on `stale`, and a sweep that is
    failing this way is otherwise completely quiet -- zero sent, no errors."""
    import app.services.task_reminders as tr
    monkeypatch.setattr(tr, "send_due_reminders", lambda db: {
        "sent": 0, "in_app": 0, "skipped_pref": 0,
        "stale": 12, "orphaned": 0, "failed": 0,
    })
    with caplog.at_level(logging.INFO):
        _post(client)
    record = next(r for r in caplog.records
                  if r.getMessage() == "task reminder job complete")
    assert record.stale == 12


def test_the_counts_render_as_top_level_json_fields(client, swept, caplog):
    """The CloudWatch contract. A metric filter reads `$.stale`, so a count
    nested inside the message string -- or dropped by the formatter -- is an
    alarm that never fires rather than an error anyone would notice."""
    with caplog.at_level(logging.INFO):
        _post(client)
    record = next(r for r in caplog.records
                  if r.getMessage() == "task reminder job complete")

    payload = json.loads(JSONFormatter().format(record))
    assert payload["message"] == "task reminder job complete"
    assert payload["level"] == "INFO"
    for key, value in COUNTS.items():
        assert payload[key] == value
    assert "email_configured" in payload
