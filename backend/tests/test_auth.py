"""Integration tests for the auth flow: issue, validate, refresh, resume, logout.

Each test drives the real API through TestClient. No mocks of our own code, no
database writes.
"""

BASE = "/api/v1/auth"


def _issue(client):
    """Log in (dev) and return (access, refresh)."""
    r = client.post(f"{BASE}/session")
    assert r.status_code == 200, r.text
    body = r.json()
    return body["access_token"], body["refresh_token"]


# --- status / wiring -------------------------------------------------------

def test_status_reports_backend_token_model(client):
    r = client.get(f"{BASE}/status")
    assert r.status_code == 200
    assert r.json()["token_model"] == "backend-issued session tokens"


# --- issue + validate ------------------------------------------------------

def test_session_issues_access_and_refresh(client):
    r = client.post(f"{BASE}/session")
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["provisioned"] is False  # provisioning stays off


def test_me_accepts_access_token(client):
    access, _ = _issue(client)
    r = client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200
    assert r.json()["provider"] == "dev"


# --- token-type confusion must be rejected ---------------------------------

def test_me_rejects_refresh_token(client):
    _, refresh = _issue(client)
    r = client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {refresh}"})
    assert r.status_code == 401


def test_refresh_rejects_access_token(client):
    access, _ = _issue(client)
    r = client.post(f"{BASE}/refresh", json={"refresh_token": access})
    assert r.status_code == 401


def test_tampered_token_rejected(client):
    access, _ = _issue(client)
    r = client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {access[:-3]}xxx"})
    assert r.status_code == 401


# --- refresh rotation ------------------------------------------------------

def test_refresh_returns_new_pair(client):
    _, refresh = _issue(client)
    r = client.post(f"{BASE}/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert r.json()["access_token"] and r.json()["refresh_token"]


def test_old_refresh_token_cannot_be_reused(client):
    _, refresh = _issue(client)
    assert client.post(f"{BASE}/refresh", json={"refresh_token": refresh}).status_code == 200
    # second use of the same refresh token is rejected (rotation)
    assert client.post(f"{BASE}/refresh", json={"refresh_token": refresh}).status_code == 401


def test_refresh_rejects_extra_fields(client):
    _, refresh = _issue(client)
    r = client.post(f"{BASE}/refresh", json={"refresh_token": refresh, "extra": 1})
    assert r.status_code == 422


# --- resume ----------------------------------------------------------------

def test_resume_returns_tokens_and_identity(client):
    _, refresh = _issue(client)
    r = client.post(f"{BASE}/resume", json={"refresh_token": refresh})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["founder"]["provider"] == "dev"


def test_resume_rejects_reused_refresh_token(client):
    _, refresh = _issue(client)
    assert client.post(f"{BASE}/resume", json={"refresh_token": refresh}).status_code == 200
    assert client.post(f"{BASE}/resume", json={"refresh_token": refresh}).status_code == 401


# --- logout + revocation ---------------------------------------------------

def test_logout_then_refresh_is_rejected(client):
    _, refresh = _issue(client)
    assert client.post(f"{BASE}/logout", json={"refresh_token": refresh}).status_code == 200
    assert client.post(f"{BASE}/refresh", json={"refresh_token": refresh}).status_code == 401


def test_logout_then_resume_is_rejected(client):
    _, refresh = _issue(client)
    assert client.post(f"{BASE}/logout", json={"refresh_token": refresh}).status_code == 200
    assert client.post(f"{BASE}/resume", json={"refresh_token": refresh}).status_code == 401


# --- supabase (real-user) mode ---------------------------------------------

def test_supabase_login_exchanges_provider_token(supabase_client):
    client, make_token = supabase_client
    r = client.post(f"{BASE}/session", headers={"Authorization": f"Bearer {make_token()}"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_supabase_raw_token_rejected_on_protected_route(supabase_client):
    client, make_token = supabase_client
    # the provider token is only valid at /session, never as our access token
    r = client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {make_token()}"})
    assert r.status_code == 401


def test_supabase_session_requires_a_token(supabase_client):
    client, _ = supabase_client
    assert client.post(f"{BASE}/session").status_code == 401


def test_supabase_expired_provider_token_rejected(supabase_client):
    client, make_token = supabase_client
    r = client.post(f"{BASE}/session", headers={"Authorization": f"Bearer {make_token(exp=1)}"})
    assert r.status_code == 401
