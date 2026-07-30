"""API tests for the Admin endpoints (Phase 12). dependency_overrides inject a
seeded in-memory-backed AdminService + a fake admin identity; no DB/auth backend."""

from datetime import datetime, timezone
from itertools import count
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.admin import (
    AdminRole,
    AdminService,
    AdminUser,
    FounderStatus,
    FounderSummary,
    InMemoryAdminRepository,
    InMemoryAnnouncementRepository,
    InMemoryAuditRepository,
    UsageMetrics,
)
from app.api.deps import get_founder_record
from app.api.v1.admin.dependencies import get_admin_service, get_current_admin

BASE = "/api/v1/admin"
T0 = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def admin_client():
    repo = InMemoryAdminRepository(
        founders=[FounderSummary(1, "Asha", "asha@x.com", FounderStatus.ACTIVE, "pro", T0, 2),
                  FounderSummary(2, "Bo", "bo@y.com", FounderStatus.ACTIVE, "free", T0, 0)],
        usage=UsageMetrics(50, 3, 7))
    service = AdminService(
        admin_repository=repo, announcement_repository=InMemoryAnnouncementRepository(),
        audit_repository=InMemoryAuditRepository(),
        clock=lambda: T0, id_factory=(lambda c=count(1): f"id-{next(c)}"))
    role = {"v": AdminRole.OPERATOR}
    app.dependency_overrides[get_current_admin] = lambda: AdminUser(99, "ops@goxl.in", role["v"])
    app.dependency_overrides[get_admin_service] = lambda: service
    yield SimpleNamespace(http=TestClient(app), service=service, role=role)
    app.dependency_overrides.pop(get_current_admin, None)
    app.dependency_overrides.pop(get_admin_service, None)


def test_dashboard_endpoint(admin_client):
    r = admin_client.http.get(f"{BASE}/dashboard")
    assert r.status_code == 200
    assert r.json()["total_founders"] == 2 and r.json()["usage"]["messages_sent"] == 50


def test_list_and_search_founders(admin_client):
    assert admin_client.http.get(f"{BASE}/founders").json()["total"] == 2
    searched = admin_client.http.get(f"{BASE}/founders", params={"q": "asha"}).json()
    assert searched["total"] == 1 and searched["founders"][0]["founder_id"] == 1


def test_get_founder_and_404(admin_client):
    assert admin_client.http.get(f"{BASE}/founders/1").json()["full_name"] == "Asha"
    assert admin_client.http.get(f"{BASE}/founders/999").status_code == 404


def test_suspend_and_restore_endpoints(admin_client):
    s = admin_client.http.post(f"{BASE}/founders/1/suspend", json={"reason": "spam"})
    assert s.status_code == 200 and s.json()["status"] == "suspended"
    assert admin_client.http.post(f"{BASE}/founders/1/restore").json()["status"] == "active"


def test_announcement_endpoints(admin_client):
    created = admin_client.http.post(f"{BASE}/announcements", json={"title": "Hi", "body": "Body text"})
    assert created.status_code == 201 and created.json()["title"] == "Hi"
    listed = admin_client.http.get(f"{BASE}/announcements").json()
    assert listed["total"] == 1


def test_audit_endpoint_reflects_actions(admin_client):
    admin_client.http.post(f"{BASE}/founders/1/suspend", json={"reason": "x"})
    events = admin_client.http.get(f"{BASE}/audit").json()
    assert events["total"] >= 1 and events["events"][0]["action"] == "suspend_founder"


def test_conversations_and_feedback_endpoints(admin_client):
    assert admin_client.http.get(f"{BASE}/conversations").status_code == 200
    assert admin_client.http.get(f"{BASE}/feedback").status_code == 200


def test_invalid_announcement_422(admin_client):
    assert admin_client.http.post(f"{BASE}/announcements", json={"title": "", "body": "b"}).status_code == 422


def test_readonly_role_cannot_suspend_403(admin_client):
    admin_client.role["v"] = AdminRole.READ_ONLY
    r = admin_client.http.post(f"{BASE}/founders/1/suspend", json={})
    assert r.status_code == 403
    assert set(r.json()) >= {"error", "message", "request_id"}


def test_non_admin_is_forbidden_403():
    # Real authorization path: an authenticated founder not on the admin allowlist.
    app.dependency_overrides[get_founder_record] = lambda: SimpleNamespace(
        founder_id=5, email="stranger@nope.com")
    try:
        assert TestClient(app).get(f"{BASE}/dashboard").status_code == 403
    finally:
        app.dependency_overrides.pop(get_founder_record, None)
