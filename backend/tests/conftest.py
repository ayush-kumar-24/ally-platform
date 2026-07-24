"""Shared test fixtures.

These tests are hermetic: they exercise the auth token machinery, which is pure
identity/crypto and touches no tables. Provisioning is off, so /auth/session
never writes. Nothing here mutates the database.
"""

import sys
import time
import uuid
from pathlib import Path

# Make `app` importable when pytest is run from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging

logging.disable(logging.CRITICAL)

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.core.auth import factory
from app.core.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def _no_real_google_calendar(monkeypatch):
    """Force calendar stub mode in every test so bookings never hit real Google.

    The dev .env may carry live Google credentials; without this, a booking test
    would create a real calendar event. Tests that exercise Google mode
    (test_calendar_google) re-enable it with a *fake* client.
    """
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_ID", "")
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_CREDENTIALS_FILE", "")
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_CREDENTIALS_JSON", "")


@pytest.fixture
def client():
    """A TestClient in dev mode (default), reset around each test."""
    original = settings.AUTH_PROVIDER
    settings.AUTH_PROVIDER = "dev"
    factory.get_auth_provider.cache_clear()
    yield TestClient(app)
    settings.AUTH_PROVIDER = original
    factory.get_auth_provider.cache_clear()


@pytest.fixture
def supabase_client():
    """A TestClient in supabase mode, with a helper to mint provider tokens.

    Yields (client, make_token) where make_token(**overrides) returns a JWT
    shaped like the one Supabase issues after a Google/LinkedIn login.
    """
    secret = "test-jwt-secret"
    original_provider = settings.AUTH_PROVIDER
    original_secret = settings.SUPABASE_JWT_SECRET
    settings.AUTH_PROVIDER = "supabase"
    settings.SUPABASE_JWT_SECRET = secret
    factory.get_auth_provider.cache_clear()

    def make_token(**overrides):
        now = int(time.time())
        claims = {
            "sub": str(uuid.uuid4()),
            "email": "founder@gmail.com",
            "aud": "authenticated",
            "exp": now + 600,
            **overrides,
        }
        return jwt.encode(claims, secret, algorithm="HS256")

    yield TestClient(app), make_token

    settings.AUTH_PROVIDER = original_provider
    settings.SUPABASE_JWT_SECRET = original_secret
    factory.get_auth_provider.cache_clear()
