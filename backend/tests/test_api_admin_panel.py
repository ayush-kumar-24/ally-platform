"""API tests for the Admin Panel.

The point of these (over the service tests) is that authorization survives the HTTP
boundary: a Support token hitting the credits endpoint must get 403 from the server,
not merely be hidden in the UI.
"""

from datetime import datetime, timedelta, timezone
from itertools import count
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.admin.panel_audit import AuditRecorder, InMemoryPanelAuditRepository
from app.admin.panel_service import AdminPanelService
from app.admin.rbac import PanelRole
from app.admin.users_models import ConsentStatus, UserStatus, UserSummary
from app.admin.users_repository import InMemoryAdminUserRepository
from app.api.v1.admin.panel_dependencies import (
    PanelAdmin,
    get_panel_admin,
    get_panel_service,
)
from app.credits import InMemoryCreditRepository, build_credit_service
from app.main import app
from app.privacy import InMemoryPrivacyRepository, build_privacy_service

BASE = "/api/v1/admin"
T0 = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
YES = {"confirm": True}


def _user(fid, name, plan="free", credits=100, status=UserStatus.ACTIVE):
    return UserSummary(founder_id=fid, full_name=name, email=f"{name.lower()}@x.com",
                       phone=f"99900{fid:05d}", business_name=f"Biz {fid}", status=status,
                       plan_type=plan, credits_balance=credits, diagnosis_completed=False,
                       consent_status=ConsentStatus.GRANTED,
                       created_at=T0 - timedelta(days=fid), last_active_at=T0)


@pytest.fixture
def client():
    users = [_user(1, "Alice", plan="pro"), _user(2, "Bob"), _user(3, "Carol")]
    repo = InMemoryAdminUserRepository(users)
    credits = build_credit_service(InMemoryCreditRepository({1: 100, 2: 100, 3: 100}),
                                   clock=lambda: T0)
    audit_repo = InMemoryPanelAuditRepository()
    c = count(1)
    privacy = build_privacy_service(InMemoryPrivacyRepository(), clock=lambda: T0)
    service = AdminPanelService(
        repo, credits=credits,
        audit=AuditRecorder(audit_repo, clock=lambda: T0, id_factory=lambda: f"e-{next(c)}"),
        clock=lambda: T0, privacy=privacy)

    current = {"role": PanelRole.SUPER_ADMIN}
    app.dependency_overrides[get_panel_admin] = lambda: PanelAdmin(
        admin_id=99, email="admin@goxl.in", role=current["role"])
    app.dependency_overrides[get_panel_service] = lambda: service
    yield SimpleNamespace(http=TestClient(app), current=current, service=service,
                          audit=audit_repo, privacy=privacy)
    for dep in (get_panel_admin, get_panel_service):
        app.dependency_overrides.pop(dep, None)


def as_role(client, role):
    client.current["role"] = role


# --- unauthenticated / non-admin --------------------------------------------


def test_endpoints_require_admin_without_override():
    """No dependency override -> the real dependency chain runs and rejects.

    Guards against a route being added without the admin dependency: an
    unauthenticated caller must never get 200.
    """
    bare = TestClient(app)
    for method, path in (("get", f"{BASE}/users"), ("get", f"{BASE}/users/1"),
                         ("get", f"{BASE}/audit-log"), ("get", f"{BASE}/me")):
        r = getattr(bare, method)(path)
        assert r.status_code != 200, f"{method.upper()} {path} was reachable unauthenticated"


# --- whoami / capabilities --------------------------------------------------


def test_whoami_reports_capabilities(client):
    as_role(client, PanelRole.SUPPORT)
    body = client.http.get(f"{BASE}/me").json()
    assert body["role"] == "support"
    assert "view_users" in body["capabilities"]
    assert "transfer_credits" not in body["capabilities"]


# --- listing: search / filter / sort / paginate -----------------------------


def test_list_users(client):
    body = client.http.get(f"{BASE}/users").json()
    assert body["total"] == 3 and len(body["items"]) == 3


def test_search(client):
    assert client.http.get(f"{BASE}/users", params={"search": "Alice"}).json()["total"] == 1


def test_filter_by_subscription(client):
    assert client.http.get(f"{BASE}/users", params={"subscription": "pro"}).json()["total"] == 1


def test_pagination_metadata(client):
    body = client.http.get(f"{BASE}/users", params={"page": 1, "page_size": 2}).json()
    assert (body["total"], body["page"], body["page_size"], body["pages"]) == (3, 1, 2, 2)
    assert len(body["items"]) == 2


def test_page_size_over_limit_422(client):
    assert client.http.get(f"{BASE}/users", params={"page_size": 5000}).status_code == 422


def test_invalid_sort_field_422(client):
    assert client.http.get(f"{BASE}/users", params={"sort_by": "; drop table"}).status_code == 422


def test_support_can_list(client):
    as_role(client, PanelRole.SUPPORT)
    assert client.http.get(f"{BASE}/users").status_code == 200


# --- credits: Super Admin only ----------------------------------------------


@pytest.mark.parametrize("role", [PanelRole.ADMIN, PanelRole.SUPPORT])
def test_credit_adjust_forbidden_for_non_super(client, role):
    as_role(client, role)
    r = client.http.post(f"{BASE}/users/1/credits",
                         json={"operation": "add", "amount": 10, "reason": "x"})
    assert r.status_code == 403
    assert client.service.credits.get_balance(1).balance == 100      # unchanged


def test_credit_adjust_by_super_admin(client):
    r = client.http.post(f"{BASE}/users/1/credits",
                         json={"operation": "add", "amount": 50, "reason": "goodwill"})
    assert r.status_code == 201
    body = r.json()
    assert body["balance"] == 150
    assert body["transaction"]["balance_before"] == 100
    assert body["transaction"]["balance_after"] == 150


def test_credit_removal_beyond_balance_409(client):
    r = client.http.post(f"{BASE}/users/1/credits",
                         json={"operation": "remove", "amount": 500, "reason": "oops"})
    assert r.status_code == 409
    assert client.service.credits.get_balance(1).balance == 100


def test_credit_negative_amount_422(client):
    assert client.http.post(f"{BASE}/users/1/credits",
                            json={"operation": "add", "amount": -5, "reason": "x"}).status_code == 422


def test_credit_missing_reason_422(client):
    assert client.http.post(f"{BASE}/users/1/credits",
                            json={"operation": "add", "amount": 5}).status_code == 422


def test_credit_unknown_operation_422(client):
    assert client.http.post(f"{BASE}/users/1/credits",
                            json={"operation": "steal", "amount": 5, "reason": "x"}).status_code == 422


def test_credit_ledger_listing(client):
    client.http.post(f"{BASE}/users/1/credits",
                     json={"operation": "add", "amount": 10, "reason": "a"})
    client.http.post(f"{BASE}/users/1/credits",
                     json={"operation": "remove", "amount": 4, "reason": "b"})
    body = client.http.get(f"{BASE}/users/1/credits").json()
    assert body["total"] == 2 and body["balance"] == 106
    assert [t["type"] for t in body["items"]] == ["remove", "add"]      # newest first


# --- user actions -----------------------------------------------------------


def test_patch_profile_allowed_for_admin(client):
    as_role(client, PanelRole.ADMIN)
    r = client.http.patch(f"{BASE}/users/1", json={"full_name": "Alice B"})
    assert r.status_code == 200 and r.json()["full_name"] == "Alice B"


def test_patch_status_forbidden_for_admin(client):
    as_role(client, PanelRole.ADMIN)
    assert client.http.patch(f"{BASE}/users/1", json={"status": "suspended"}).status_code == 403


def test_patch_forbidden_for_support(client):
    as_role(client, PanelRole.SUPPORT)
    assert client.http.patch(f"{BASE}/users/1", json={"full_name": "X"}).status_code == 403


def test_patch_unknown_field_422(client):
    assert client.http.patch(f"{BASE}/users/1", json={"credits_balance": 999}).status_code == 422


def test_status_change_super_only(client):
    as_role(client, PanelRole.ADMIN)
    assert client.http.post(f"{BASE}/users/2/status", json={"status": "suspended"}).status_code == 403
    as_role(client, PanelRole.SUPER_ADMIN)
    r = client.http.post(f"{BASE}/users/2/status", json={"status": "suspended", "reason": "spam"})
    assert r.status_code == 200 and r.json()["status"] == "suspended"


def test_destructive_actions_need_confirmation(client):
    as_role(client, PanelRole.ADMIN)
    assert client.http.post(f"{BASE}/users/1/reset-diagnosis",
                            json={"confirm": False}).status_code == 422
    assert client.http.post(f"{BASE}/users/1/reset-diagnosis", json=YES).status_code == 200


def test_delete_requires_confirmation_and_super_admin(client):
    as_role(client, PanelRole.ADMIN)
    assert client.http.request("DELETE", f"{BASE}/users/3", json=YES).status_code == 403
    as_role(client, PanelRole.SUPER_ADMIN)
    assert client.http.request("DELETE", f"{BASE}/users/3", json={"confirm": False}).status_code == 422
    r = client.http.request("DELETE", f"{BASE}/users/3", json=YES)
    assert r.status_code == 200 and r.json()["status"] == "banned"


def test_missing_user_404(client):
    assert client.http.get(f"{BASE}/users/4242").status_code == 404


# --- cancel deletion ---------------------------------------------------------


def test_cancel_deletion_requires_confirmation_and_super_admin(client):
    client.privacy.request_account_deletion(1)

    as_role(client, PanelRole.ADMIN)
    assert client.http.post(f"{BASE}/users/1/cancel-deletion", json=YES).status_code == 403

    as_role(client, PanelRole.SUPER_ADMIN)
    assert client.http.post(f"{BASE}/users/1/cancel-deletion",
                            json={"confirm": False}).status_code == 422

    r = client.http.post(f"{BASE}/users/1/cancel-deletion", json=YES)
    assert r.status_code == 200
    assert r.json()["deletion_pending"] is False
    assert client.privacy.get_state(1).deletion_pending is False


def test_cancel_deletion_without_pending_request_409(client):
    as_role(client, PanelRole.SUPER_ADMIN)
    assert client.http.post(f"{BASE}/users/1/cancel-deletion", json=YES).status_code == 409


def test_cancel_deletion_missing_user_404(client):
    as_role(client, PanelRole.SUPER_ADMIN)
    assert client.http.post(f"{BASE}/users/4242/cancel-deletion", json=YES).status_code == 404


def test_cancel_deletion_is_audited(client):
    client.privacy.request_account_deletion(2)
    as_role(client, PanelRole.SUPER_ADMIN)
    client.http.post(f"{BASE}/users/2/cancel-deletion", json={"confirm": True, "reason": "support call"})
    events, _ = client.audit.list(target_user_id=2)
    assert any(e.action == "user.cancel_deletion" and e.reason == "support call" for e in events)


# --- subscription -----------------------------------------------------------


def test_subscription_super_only(client):
    as_role(client, PanelRole.ADMIN)
    assert client.http.patch(f"{BASE}/users/1/subscription",
                             json={"plan": "pro"}).status_code == 403
    as_role(client, PanelRole.SUPER_ADMIN)
    r = client.http.patch(f"{BASE}/users/1/subscription",
                          json={"plan": "elite", "bonus_credits": 25})
    assert r.status_code == 200
    assert r.json()["changes"]["bonus_credits"]["balance_after"] == 125


# --- audit ------------------------------------------------------------------


def test_audit_records_every_mutation(client):
    client.http.post(f"{BASE}/users/1/credits",
                     json={"operation": "add", "amount": 5, "reason": "r"})
    client.http.post(f"{BASE}/users/2/status", json={"status": "suspended"})
    body = client.http.get(f"{BASE}/audit-log").json()
    assert body["total"] == 2
    assert {e["action"] for e in body["items"]} == {"credits.add", "user.suspended"}
    assert all(e["timestamp"] for e in body["items"])


def test_audit_filter_by_target(client):
    client.http.post(f"{BASE}/users/1/credits",
                     json={"operation": "add", "amount": 5, "reason": "r"})
    client.http.post(f"{BASE}/users/2/status", json={"status": "suspended"})
    body = client.http.get(f"{BASE}/audit-log", params={"target_user_id": 1}).json()
    assert body["total"] == 1 and body["items"][0]["target_user_id"] == 1


def test_audit_forbidden_for_support(client):
    as_role(client, PanelRole.SUPPORT)
    assert client.http.get(f"{BASE}/audit-log").status_code == 403


def test_audit_records_ip(client):
    client.http.post(f"{BASE}/users/1/credits",
                     json={"operation": "add", "amount": 5, "reason": "r"},
                     headers={"X-Forwarded-For": "198.51.100.7, 10.0.0.1"})
    e = client.http.get(f"{BASE}/audit-log").json()["items"][0]
    assert e["ip_address"] == "198.51.100.7"       # original client, not the proxy hop
