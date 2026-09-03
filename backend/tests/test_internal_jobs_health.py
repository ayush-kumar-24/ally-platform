"""POST /internal/jobs/check-health -- the push side of the Health page.

GET /admin/health (tests/test_api_admin_panel.py) is pull-based and never
alerts anyone by itself. This endpoint is what a scheduler (EventBridge,
pg_cron, a plain cron -- same shape as every other job in this router) hits
periodically; it runs the same check and fires the health alert exactly on a
green -> red transition.

Same auth as every other job here: a shared secret, not a founder/admin
token, so this is tested directly through TestClient with the header, not
through any admin dependency override.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.admin.health import ComponentHealth, HealthAlertService, HealthReport, HealthStatus
from app.core.config import settings
from app.core.container import container
from app.main import app

BASE = "/api/v1/internal/jobs"
SECRET = "test-internal-secret"


@pytest.fixture
def secured_client(monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_JOBS_SECRET", SECRET)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_health_alert_state():
    """HealthAlertService's edge-trigger state is a process-level singleton
    (container._health_alert_service) -- reset it around each test so one
    test's red doesn't suppress the next test's alert."""
    container._health_alert_service = container._build_health_alert_service()
    yield
    container._health_alert_service = container._build_health_alert_service()


def _install_fake_checker(monkeypatch, report):
    class _Checker:
        def check(self):
            return report

    monkeypatch.setattr(container, "health_checker", lambda db: _Checker())


def _install_fake_alerts(monkeypatch):
    sent = []

    class _FakeChannel:
        def send(self, report):
            sent.append(report.status)

    service = HealthAlertService([_FakeChannel()])
    monkeypatch.setattr(container, "health_alert_service", lambda: service)
    return sent


def test_rejects_without_the_secret(secured_client):
    r = secured_client.post(f"{BASE}/check-health")
    assert r.status_code == 401


def test_rejects_the_wrong_secret(secured_client):
    r = secured_client.post(f"{BASE}/check-health", headers={"X-Internal-Secret": "nope"})
    assert r.status_code == 401


def test_returns_the_report_shape(secured_client, monkeypatch):
    report = HealthReport(
        status=HealthStatus.GREEN, checked_at=datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc),
        components=[ComponentHealth("database", "Database", HealthStatus.GREEN, "connected")],
    )
    _install_fake_checker(monkeypatch, report)

    r = secured_client.post(f"{BASE}/check-health", headers={"X-Internal-Secret": SECRET})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "green"
    assert body["components"][0]["key"] == "database"
    assert body["alert_sent"] is False


def test_a_red_report_sends_exactly_one_alert(secured_client, monkeypatch):
    report = HealthReport(
        status=HealthStatus.RED, checked_at=datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc),
        components=[ComponentHealth("database", "Database", HealthStatus.RED, "unreachable")],
    )
    _install_fake_checker(monkeypatch, report)
    sent = _install_fake_alerts(monkeypatch)

    r1 = secured_client.post(f"{BASE}/check-health", headers={"X-Internal-Secret": SECRET})
    assert r1.json()["alert_sent"] is True

    r2 = secured_client.post(f"{BASE}/check-health", headers={"X-Internal-Secret": SECRET})
    assert r2.json()["alert_sent"] is False  # still red -- no repeat page

    assert sent == [HealthStatus.RED]  # exactly one channel invocation total
