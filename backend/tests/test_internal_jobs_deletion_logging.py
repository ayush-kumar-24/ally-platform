"""POST /internal/jobs/process-deletions -- the sweep must log a HEARTBEAT,
including on the days it finds nobody to erase.

WHY THIS FILE EXISTS. The failure this job has to be watched for is that it
stops running, and a job that does not run produces no output at all. So the
only thing that can catch it is an expected log line going missing -- which is
what the CloudWatch alarm on this one does: a metric filter on
`deletion sweep completed`, alarming on ABSENCE over 48 hours.

That alarm was built against a line logged per FOUNDER, inside
AccountDeletionExecutor.run, and it was backwards in both directions:

  * A healthy sweep on a day nobody was due logged nothing, so the alarm fired
    on a job that was working perfectly.
  * A dead job on a day somebody WAS due would have looked identical to a
    working one, because the only evidence either way is that same line.

The per-founder line is now `founder deletion completed`, and this endpoint
emits exactly one `deletion sweep completed` per run, unconditionally. The
tests below pin all three properties the alarm depends on: the line exists on
an EMPTY sweep, there is exactly ONE of them however many founders were
processed, and the counts arrive as top-level JSON fields a metric filter can
read rather than interpolated into the message.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.logger import JSONFormatter
from app.main import app

BASE = "/api/v1/internal/jobs"
SECRET = "test-internal-secret"
HEARTBEAT = "deletion sweep completed"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_JOBS_SECRET", SECRET)
    return TestClient(app)


@pytest.fixture
def sweep(monkeypatch):
    """Drive the endpoint with a chosen set of due founders, and a chosen set
    that blow up. The executor and repository are stubbed: this file is about
    what the endpoint REPORTS, not about what the sweep decides to delete."""
    import app.api.v1.webhooks.internal_jobs as jobs

    def configure(due, fail_on=()):
        repo = MagicMock()
        repo.find_due_for_deletion.return_value = list(due)

        def run(founder_id):
            if founder_id in fail_on:
                raise RuntimeError("integrity error")
            result = MagicMock()
            result.hard_deleted = {"answers": 3}
            return result

        executor = MagicMock()
        executor.run.side_effect = run

        monkeypatch.setattr(jobs, "SqlAlchemyPrivacyRepository", lambda db: repo)
        monkeypatch.setattr(jobs, "AccountDeletionExecutor", lambda db: executor)
        # RLS context and the session are infrastructure, not this test's subject.
        monkeypatch.setattr(jobs, "set_admin_rls_context", lambda db: None)

    return configure


def _post(client):
    return client.post(f"{BASE}/process-deletions",
                       headers={"X-Internal-Secret": SECRET})


def _heartbeats(caplog):
    return [r for r in caplog.records if r.getMessage() == HEARTBEAT]


def test_an_empty_sweep_still_logs_the_heartbeat(client, sweep, caplog):
    """THE test in this file. A day with nobody due is the normal case, and it
    is the one the old per-founder line could not report."""
    sweep(due=[])
    with caplog.at_level(logging.INFO):
        assert _post(client).status_code == 200

    records = _heartbeats(caplog)
    assert len(records) == 1, "a sweep that found nobody must still say it ran"
    assert records[0].due_count == 0
    assert records[0].executed_count == 0
    assert records[0].failed_count == 0


def test_exactly_one_heartbeat_however_many_founders_were_erased(client, sweep, caplog):
    """One line per SWEEP. Three lines for three founders would make the
    metric filter count erasures and call it uptime."""
    sweep(due=[11, 22, 33])
    with caplog.at_level(logging.INFO):
        _post(client)

    records = _heartbeats(caplog)
    assert len(records) == 1
    assert records[0].due_count == 3
    assert records[0].executed_count == 3
    assert records[0].failed_count == 0


def test_a_founder_failing_does_not_cost_the_heartbeat(client, sweep, caplog):
    """One founder's failure must not stop the sweep OR silence it -- that
    would turn a partial failure into an apparent outage."""
    sweep(due=[11, 22, 33], fail_on={22})
    with caplog.at_level(logging.INFO):
        body = _post(client).json()

    records = _heartbeats(caplog)
    assert len(records) == 1
    assert records[0].due_count == 3
    assert records[0].executed_count == 2
    assert records[0].failed_count == 1
    assert body["failed_count"] == 1
    assert body["executed_count"] == 2


def test_the_counts_render_as_top_level_json_fields(client, sweep, caplog):
    """The CloudWatch contract. A metric filter reads `$.failed_count`; a count
    interpolated into the message string is an alarm that never fires rather
    than an error anybody would notice."""
    sweep(due=[11, 22], fail_on={22})
    with caplog.at_level(logging.INFO):
        _post(client)

    payload = json.loads(JSONFormatter().format(_heartbeats(caplog)[0]))
    assert payload["message"] == HEARTBEAT
    assert payload["level"] == "INFO"
    assert payload["due_count"] == 2
    assert payload["executed_count"] == 1
    assert payload["failed_count"] == 1


def test_the_per_founder_line_no_longer_claims_to_be_the_sweep(client, sweep, caplog):
    """The rename is the other half of the fix. If AccountDeletionExecutor ever
    goes back to logging the sweep's name, the alarm silently starts measuring
    erasures again and this file's first test stops meaning anything."""
    import ast
    import inspect

    from app.privacy import deletion_executor

    # Parsed, not grepped. A substring search over the source also matches the
    # COMMENT in that module explaining this very rename, so it would fail on
    # correct code -- and it would pass on a log call built by string
    # concatenation, which is the case worth catching.
    tree = ast.parse(inspect.getsource(deletion_executor))
    logged = [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"info", "warning", "error", "exception"}
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ]
    assert HEARTBEAT not in logged, (
        "deletion_executor must not emit the sweep heartbeat -- that name "
        f"belongs to one scheduled run, not to one deleted founder. Logged: {logged}"
    )
    assert "founder deletion completed" in logged
