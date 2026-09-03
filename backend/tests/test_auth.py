"""Integration tests for the auth flow: issue, validate, refresh, resume, logout.

Each test drives the real API through TestClient. No mocks of our own code, no
database writes. Every protected call now does one read against `founders`
(the suspension check -- see test_account_suspension.py), but for the
random/dev identities these tests use, that read never matches a row, so
`is_account_active` reports active and behaviour here is unchanged.

Refresh-token transport: the HttpOnly ally_refresh_token cookie, not the JSON
body (see routes.py's module docstring for why). TestClient auto-persists
cookies across calls on the same `client` within a test, exactly like a real
browser session -- which is realistic for the "happy path" tests below, but
would make a naive reuse/rejection test pass for the wrong reason (the call
picks up whatever fresh cookie the previous call just set, not the specific
stale token the test means to retry). Every test that specifically means to
present a particular token passes `cookies={COOKIE: token}` explicitly rather
than relying on the jar, so it tests what it says it tests.
"""

COOKIE = "ally_refresh_token"
BASE = "/api/v1/auth"


def _issue(client):
    """Log in (dev). Returns (access_token, refresh_token) -- the refresh
    token comes from the Set-Cookie header now, never the response body."""
    r = client.post(f"{BASE}/session")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["refresh_token"] is None  # never in the body -- see TokenPair's docstring
    refresh = r.cookies.get(COOKIE)
    assert refresh, "expected the ally_refresh_token cookie to be set"
    return body["access_token"], refresh


# --- status / wiring -------------------------------------------------------

def test_status_reports_backend_token_model(client):
    r = client.get(f"{BASE}/status")
    assert r.status_code == 200
    assert r.json()["token_model"] == "backend-issued session tokens"


# --- issue + validate ------------------------------------------------------

def test_session_issues_access_token_and_refresh_cookie(client):
    r = client.post(f"{BASE}/session")
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"] is None  # never in the body -- only the cookie
    assert body["token_type"] == "bearer"
    assert body["provisioned"] is False  # provisioning stays off

    assert r.cookies.get(COOKIE)
    set_cookie = r.headers.get("set-cookie", "")
    assert COOKIE in set_cookie
    assert "httponly" in set_cookie.lower()


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
    # Explicit cookie override: `client`'s jar already holds a valid refresh
    # cookie from _issue()'s own /session call, which would otherwise win
    # over this test's whole point (presenting an access token where a
    # refresh token belongs).
    r = client.post(f"{BASE}/refresh", cookies={COOKIE: access})
    assert r.status_code == 401


def test_tampered_token_rejected(client):
    access, _ = _issue(client)
    r = client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {access[:-3]}xxx"})
    assert r.status_code == 401


# --- refresh rotation ------------------------------------------------------

def test_refresh_returns_new_pair(client):
    _, refresh = _issue(client)
    r = client.post(f"{BASE}/refresh", cookies={COOKIE: refresh})
    assert r.status_code == 200
    assert r.json()["access_token"]
    assert r.json()["refresh_token"] is None  # rotated token goes to the cookie, not the body
    new_refresh = r.cookies.get(COOKIE)
    assert new_refresh and new_refresh != refresh  # rotation: a genuinely new token


def test_old_refresh_token_cannot_be_reused(client):
    _, refresh = _issue(client)
    # Both calls pin the SAME original token via an explicit cookie override --
    # otherwise the client's jar would auto-update to the freshly rotated
    # token after the first call, and the second call would silently use
    # that instead of actually retrying the old one.
    assert client.post(f"{BASE}/refresh", cookies={COOKIE: refresh}).status_code == 200
    assert client.post(f"{BASE}/refresh", cookies={COOKIE: refresh}).status_code == 401


def test_refresh_falls_back_to_body_when_no_cookie_present(client):
    """The body field exists for a non-browser caller that cannot hold a
    cookie jar. Confirmed to actually work, not just accepted and ignored."""
    _, refresh = _issue(client)
    client.cookies.clear()  # simulate a caller with no cookie jar at all
    r = client.post(f"{BASE}/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200


def test_refresh_with_no_token_anywhere_is_rejected(client):
    client.cookies.clear()
    r = client.post(f"{BASE}/refresh")
    assert r.status_code == 401


def test_refresh_rejects_extra_fields(client):
    _, refresh = _issue(client)
    r = client.post(f"{BASE}/refresh", cookies={COOKIE: refresh}, json={"extra": 1})
    assert r.status_code == 422


# --- resume ----------------------------------------------------------------

def test_resume_returns_tokens_and_identity(client):
    _, refresh = _issue(client)
    r = client.post(f"{BASE}/resume", cookies={COOKIE: refresh})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"] is None  # rotated token goes to the cookie, not the body
    assert body["founder"]["provider"] == "dev"
    new_refresh = r.cookies.get(COOKIE)
    assert new_refresh and new_refresh != refresh


def test_resume_rejects_reused_refresh_token(client):
    _, refresh = _issue(client)
    assert client.post(f"{BASE}/resume", cookies={COOKIE: refresh}).status_code == 200
    assert client.post(f"{BASE}/resume", cookies={COOKIE: refresh}).status_code == 401


# --- logout + revocation ---------------------------------------------------

def test_logout_clears_the_cookie(client):
    _, refresh = _issue(client)
    r = client.post(f"{BASE}/logout", cookies={COOKIE: refresh})
    assert r.status_code == 200
    # A cleared cookie is still a Set-Cookie header (with an expiry in the
    # past / empty value) -- confirm logout actually tells the browser to
    # drop it, not just that the server-side revocation happened.
    set_cookie = r.headers.get("set-cookie", "")
    assert COOKIE in set_cookie


def test_logout_then_refresh_is_rejected(client):
    _, refresh = _issue(client)
    assert client.post(f"{BASE}/logout", cookies={COOKIE: refresh}).status_code == 200
    assert client.post(f"{BASE}/refresh", cookies={COOKIE: refresh}).status_code == 401


def test_logout_then_resume_is_rejected(client):
    _, refresh = _issue(client)
    assert client.post(f"{BASE}/logout", cookies={COOKIE: refresh}).status_code == 200
    assert client.post(f"{BASE}/resume", cookies={COOKIE: refresh}).status_code == 401


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
