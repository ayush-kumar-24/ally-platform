"""The settings that only matter the moment ENVIRONMENT=production.

Nothing tested these. They are the switch that is flipped once, by hand, on
the day it is hardest to debug, and the failure mode of the first one is the
worst kind there is: `AUTH_PROVIDER=dev` accepts a request with NO TOKEN as a
fixed founder, so a production deploy that kept the development default serves
every visitor the same founder's diagnosis.

The guard exists in app/core/auth/factory.py. These tests are what notice if
someone removes it, or adds a third provider that skips it.
"""

import pytest

from app.core.auth import factory
from app.core.config import settings


@pytest.fixture(autouse=True)
def _uncached():
    """get_auth_provider is lru_cached -- a real deployment builds it once, but
    a test that leaves a cached provider behind poisons the next one."""
    factory.get_auth_provider.cache_clear()
    yield
    factory.get_auth_provider.cache_clear()


def test_dev_auth_is_refused_in_production(monkeypatch):
    """No token at all is a valid dev request. It must never reach production."""
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "dev")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="not allowed when ENVIRONMENT=production"):
        factory.get_auth_provider()


@pytest.mark.parametrize("spelling", ["dev", "DEV", " Dev "])
def test_the_refusal_is_not_defeated_by_spelling(monkeypatch, spelling):
    monkeypatch.setattr(settings, "AUTH_PROVIDER", spelling)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    with pytest.raises(RuntimeError):
        factory.get_auth_provider()


def test_dev_auth_is_allowed_everywhere_else(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "dev")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    assert factory.get_auth_provider().name == "dev"


def test_an_unknown_provider_refuses_rather_than_falling_back(monkeypatch):
    """A typo in AUTH_PROVIDER must not authenticate anyone."""
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "supabse")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="Unknown AUTH_PROVIDER"):
        factory.get_auth_provider()


def test_supabase_auth_refuses_to_build_with_nothing_to_verify_against(monkeypatch):
    """Neither SUPABASE_URL nor the legacy secret means every token is
    unverifiable -- refuse at construction, not per request."""
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "supabase")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SUPABASE_URL", "")
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "")

    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        factory.get_auth_provider()


def test_supabase_url_alone_is_enough(monkeypatch):
    """ES256 is what real logins use; the legacy HS256 secret is optional."""
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "supabase")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://ref.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", "")

    provider = factory.get_auth_provider()
    assert provider.name == "supabase"
    assert provider._jwks_url == (
        "https://ref.supabase.co/auth/v1/.well-known/jwks.json")


# --- CORS ---------------------------------------------------------------
#
# An origin missing here fails in the visitor's browser console, not in this
# API's logs, so a missing one is invisible from the server side.


def test_cors_origins_are_split_and_stripped(monkeypatch):
    monkeypatch.setattr(settings, "CORS_ORIGINS",
                        "https://a.example, https://b.example ,")
    assert settings.cors_origins_list == ["https://a.example", "https://b.example"]


def test_cors_origins_are_never_a_wildcard_by_default():
    """allow_credentials=True with allow_origins=['*'] is refused by browsers
    outright, so a wildcard here silently breaks every authenticated call."""
    from app.core import cors

    assert "*" not in settings.cors_origins_list
    assert "allow_credentials=True" in open(cors.__file__, encoding="utf-8").read()


def test_the_example_env_lists_the_origins_a_launch_needs():
    """The browser-facing hosts: the app, the marketing site and the waitlist
    form, which posts to /api/v1/waitlist from its own origin."""
    from app.core.paths import ENV_EXAMPLE

    line = [l for l in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
            if l.startswith("CORS_ORIGINS=")]
    assert line, "CORS_ORIGINS is not documented in .env.example"
    assert "app.goxlally.ai" in line[0]
    assert "join.goxlally.ai" in line[0], (
        "the waitlist form's origin must be listed or every submission is "
        "blocked by CORS before it arrives")


# --- the production path, actually walked ----------------------------------
#
# Everything above asserts that a bad production configuration REFUSES. None
# of it proves the good one works: no run on record had ever set
# ENVIRONMENT=production and AUTH_PROVIDER=supabase together and then made a
# request. Every e2e journey used dev auth, because there is no browser in a
# script to log in with, and every test above stops at the factory.
#
# So the combination that production actually runs -- the identity provider
# real founders authenticate through, under the environment flag that changes
# how the app is assembled -- was the one combination nothing exercised.

import time
import uuid

from fastapi.testclient import TestClient
from jose import jwt

from app.main import app

BASE = "/api/v1/auth"


@pytest.fixture
def production_client(monkeypatch):
    """A client with the exact pair a production deploy sets."""
    secret = "production-path-test-secret"
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "supabase")
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", secret)
    factory.get_auth_provider.cache_clear()

    def make_token(**overrides):
        claims = {
            "sub": str(uuid.uuid4()),
            "email": "founder@gmail.com",
            "aud": "authenticated",
            "exp": int(time.time()) + 600,
            **overrides,
        }
        return jwt.encode(claims, secret, algorithm="HS256")

    yield TestClient(app), make_token, secret
    factory.get_auth_provider.cache_clear()


def test_the_provider_production_builds_is_the_supabase_one():
    settings_provider = settings.AUTH_PROVIDER
    try:
        settings.ENVIRONMENT, settings.AUTH_PROVIDER = "production", "supabase"
        settings.SUPABASE_JWT_SECRET = "x"
        factory.get_auth_provider.cache_clear()
        assert type(factory.get_auth_provider()).__name__ == "SupabaseAuthProvider"
    finally:
        settings.ENVIRONMENT, settings.AUTH_PROVIDER = "development", settings_provider
        factory.get_auth_provider.cache_clear()


def test_a_real_supabase_token_is_accepted_under_production(production_client):
    """The happy path, which nothing had ever run."""
    client, make_token, _ = production_client
    r = client.post(f"{BASE}/session",
                    headers={"Authorization": f"Bearer {make_token()}"})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


def test_production_still_refuses_a_request_with_no_token(production_client):
    """The failure this whole file exists for: dev auth serves a fixed founder
    to an unauthenticated request. Under production it must not."""
    client, _, _ = production_client
    assert client.post(f"{BASE}/session").status_code == 401
    assert client.get(f"{BASE}/me").status_code == 401


def test_production_refuses_a_token_signed_with_the_wrong_secret(production_client):
    client, _, _ = production_client
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "email": "attacker@example.com",
         "aud": "authenticated", "exp": int(time.time()) + 600},
        "not-the-secret", algorithm="HS256")
    r = client.post(f"{BASE}/session",
                    headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_production_refuses_an_expired_token(production_client):
    client, make_token, _ = production_client
    r = client.post(f"{BASE}/session",
                    headers={"Authorization":
                             f"Bearer {make_token(exp=int(time.time()) - 60)}"})
    assert r.status_code == 401


def test_the_interactive_docs_are_not_served_in_production():
    """They describe every endpoint and its schema. Development gets them;
    a public deploy should not."""
    import importlib

    import app.main

    original = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        reloaded = importlib.reload(app.main)
        paths = {getattr(r, "path", None) for r in reloaded.app.routes}
        assert "/docs" not in paths
        assert "/redoc" not in paths
        assert "/openapi.json" not in paths
    finally:
        settings.ENVIRONMENT = original
        importlib.reload(app.main)
