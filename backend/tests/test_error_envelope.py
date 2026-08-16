"""Every error this API returns must be readable by the clients we ship.

The frontend's normalizeError() looks for `detail` and nothing else. When the
envelope carried only `message`, every backend error reached founders as axios's
raw "Request failed with status code NNN" -- which is how a 422 on /auth/refresh
got shown on the login screen as a consent failure. These tests pin both keys so
that can't regress, in either direction.
"""

BASE = "/api/v1/auth"


def _both_keys(body):
    assert "message" in body, body
    assert "detail" in body, body
    assert body["request_id"]


# --- AppError (our own domain errors, incl. AuthError) ----------------------

def test_app_error_carries_detail_and_message(client):
    r = client.post(f"{BASE}/refresh", json={"refresh_token": "not-a-token"})
    assert r.status_code == 401
    body = r.json()
    _both_keys(body)
    assert body["detail"] == body["message"] == "Invalid or expired token"


def test_missing_credentials_reads_as_a_sentence(client):
    """What a logged-out browser gets. It is rendered verbatim, so it has to be
    something a founder can act on."""
    r = client.post(f"{BASE}/refresh", json={})
    assert r.status_code == 401
    assert r.json()["detail"] == "You're not signed in."


# --- validation errors ------------------------------------------------------

def test_validation_detail_is_human_readable(client):
    """`message` keeps Pydantic's raw list for debugging; `detail` is the line the
    UI actually prints, so it must not be a Python repr."""
    r = client.post(f"{BASE}/refresh", json={"refresh_token": "x", "extra": 1})
    assert r.status_code == 422
    body = r.json()
    _both_keys(body)
    assert body["detail"].startswith("extra: ")
    assert "{'type'" not in body["detail"]
    assert "'type'" in body["message"]  # raw errors still available


def test_validation_detail_names_the_field(client):
    r = client.post(f"{BASE}/resume", json={"refresh_token": 12345})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail.startswith("refresh_token: ")
    assert "(" not in detail  # no tuples, no repr leaking through
