"""The email-change request, and the queued privacy path it rides on.

WHY THIS FILE EXISTS AT ALL. `POST /settings/privacy` -- the branch every
human-actioned right goes through, correction included -- had no test on either
side. The endpoint that a locked-out founder's only route back to us runs on was
the untested one.

WHAT THE FEATURE IS FOR. A founder who mistypes their address at signup is
signed in as an address they do not own. Everything we send goes elsewhere, and
"email us from the address on your account" is the one thing they cannot do.
The request is reviewed by a person rather than applied, because pointing an
account at a new inbox is an account-takeover primitive -- so the tests below
care as much about what does NOT happen as what does.

No DB and no auth backend: `get_founder_record` and the repository are both
overridden, the same way test_api_settings_preferences.py does it.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_founder_record
from app.api.v1.settings import routes as settings_routes
from app.main import app

BASE = "/api/v1/settings/privacy"
CURRENT_EMAIL = "founder@example.com"


class FakeRepo:
    """Stands in for privacy_request_repository. Records what it was asked to do."""

    def __init__(self):
        self.rows: list[dict] = []
        self.next_id = 1

    def has_pending(self, db, founder_id, *, request_type):
        return any(
            r["founder_id"] == founder_id
            and r["request_type"] == request_type
            and r["status"] == "pending"
            for r in self.rows
        )

    def submit(self, db, founder_id, request_type, request_details=None):
        row = {
            "request_id": self.next_id,
            "founder_id": founder_id,
            "request_type": request_type,
            "request_details": request_details,
            "status": "pending",
            "requested_at": "2026-09-06T12:00:00Z",
            "created_at": "2026-09-06T12:00:00Z",
            "processing_notes": None,
            "rejection_reason": None,
            "due_by": None,
            "completed_at": None,
        }
        self.next_id += 1
        self.rows.append(row)
        return SimpleNamespace(**row)


@pytest.fixture
def client(monkeypatch):
    repo = FakeRepo()
    monkeypatch.setattr(settings_routes, "privacy_request_repository", repo)
    app.dependency_overrides[get_founder_record] = lambda: SimpleNamespace(
        founder_id=1, email=CURRENT_EMAIL
    )
    # get_db is only ever passed through to the fake repo, which ignores it.
    from app.db.session import get_db
    app.dependency_overrides[get_db] = lambda: None
    yield SimpleNamespace(http=TestClient(app), repo=repo)
    app.dependency_overrides.pop(get_founder_record, None)
    app.dependency_overrides.pop(get_db, None)


# --- the happy path --------------------------------------------------------

def test_email_change_is_queued_with_the_new_address(client):
    r = client.http.post(BASE, json={
        "request_type": "email_change",
        "request_details": "new@example.com",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["request_type"] == "email_change"
    assert body["request_details"] == "new@example.com"
    # Pending, not applied. The address on the account is unchanged until a
    # human verifies who asked -- that is the entire security model here.
    assert body["status"] == "pending"


def test_the_address_is_normalised_so_the_admin_reads_one_form(client):
    r = client.http.post(BASE, json={
        "request_type": "email_change",
        "request_details": "  New@Example.COM  ",
    })
    assert r.status_code == 201
    assert client.repo.rows[0]["request_details"] == "new@example.com"


# --- what must be refused --------------------------------------------------

@pytest.mark.parametrize("details", [None, "", "   ", "not an email", "9876543210", "@nope"])
def test_an_email_change_without_a_usable_address_is_refused(client, details):
    """The admin's only recourse for an unusable one is to ask the founder --
    at the address that does not work. It would sit in the queue forever."""
    payload = {"request_type": "email_change"}
    if details is not None:
        payload["request_details"] = details
    r = client.http.post(BASE, json=payload)
    assert r.status_code == 422, r.text
    assert client.repo.rows == []


def test_requesting_the_address_you_already_have_is_refused(client):
    r = client.http.post(BASE, json={
        "request_type": "email_change",
        "request_details": CURRENT_EMAIL.upper(),   # case must not smuggle it past
    })
    assert r.status_code == 400
    # The app's handler returns {error, message, request_id} -- not FastAPI's
    # {detail}. The frontend's api.js maps `message` onto ApiError.detail, so
    # this wording is what the founder actually reads in the toast.
    assert "already the address" in r.json()["message"]
    assert client.repo.rows == []


def test_a_second_pending_request_is_refused_not_duplicated(client):
    """The founder this feature serves cannot be sent a confirmation, so they
    will press it again. One row, not ten."""
    first = client.http.post(BASE, json={
        "request_type": "email_change", "request_details": "new@example.com"})
    assert first.status_code == 201

    second = client.http.post(BASE, json={
        "request_type": "email_change", "request_details": "other@example.com"})
    assert second.status_code == 409
    assert "waiting for review" in second.json()["message"]
    assert len(client.repo.rows) == 1


def test_a_new_request_is_allowed_once_the_first_is_resolved(client):
    client.http.post(BASE, json={
        "request_type": "email_change", "request_details": "new@example.com"})
    client.repo.rows[0]["status"] = "completed"

    again = client.http.post(BASE, json={
        "request_type": "email_change", "request_details": "third@example.com"})
    assert again.status_code == 201
    assert len(client.repo.rows) == 2


def test_deletion_cannot_be_queued_through_this_endpoint(client):
    """`delete_account` is a legal value in the table but not a submittable one.

    Erasure has its own endpoint, which schedules the deletion and records the
    grace period. A row queued here would look like a deletion request while
    none of that happened -- a deletion we believe we have and never perform.
    """
    r = client.http.post(BASE, json={"request_type": "delete_account"})
    assert r.status_code == 422
    assert client.repo.rows == []


# --- the correction request, which shares the path -------------------------

def test_a_correction_now_carries_its_details(client):
    """It always accepted `request_details`; the UI never sent any, so every
    correction reached an admin as "this founder wants something corrected"."""
    r = client.http.post(BASE, json={
        "request_type": "correct_data",
        "request_details": "Company name should be GoXL, not Goxl.",
    })
    assert r.status_code == 201
    assert client.repo.rows[0]["request_details"].startswith("Company name")


def test_a_correction_without_details_is_still_allowed(client):
    """Unlike an email change, a correction with no text is merely unhelpful --
    the founder can be emailed to ask what they meant."""
    r = client.http.post(BASE, json={"request_type": "correct_data"})
    assert r.status_code == 201


def test_the_one_pending_rule_does_not_leak_across_request_types(client):
    """A pending email change must not block an unrelated right."""
    client.http.post(BASE, json={
        "request_type": "email_change", "request_details": "new@example.com"})
    r = client.http.post(BASE, json={"request_type": "correct_data"})
    assert r.status_code == 201
