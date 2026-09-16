"""Shared test fixtures.

The auth-token tests are hermetic: they exercise pure identity/crypto and touch
no tables. Provisioning is off, so /auth/session never writes.

Much of the rest of the suite does use the database, and expects `auth.users`
to be there -- see `_auth_users_table`, which makes that expectation something
a plain Postgres can satisfy rather than something only Supabase can.
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


@pytest.fixture(scope="session", autouse=True)
def _auth_users_table():
    """Make sure `auth.users` exists, because forty test files insert into it
    and not one of them creates it.

    Supabase ships that table as part of GoTrue, so the suite has quietly
    depended on being pointed at a Supabase database since it was written.
    Point it at a Postgres built by replaying `alembic/versions/` -- which is
    what RESTORE.md produces, and what anyone gets who follows the README --
    and ninety-one tests ERROR on `relation "auth.users" does not exist`
    before a single assertion runs. They are not failures; they never got far
    enough to fail. That is the worst shape for a test to be in, because a
    hundred-odd errors in the output is indistinguishable from a broken branch.

    So: create it if it is missing, and leave it completely alone if it is
    not. On Supabase this does nothing at all -- GoTrue's real table is
    already there and is far richer than this one. Elsewhere it creates the
    five columns the tests actually use, which is the whole of what they touch.

    This is a TEST fixture and not a migration on purpose. `auth` is GoTrue's
    schema; the application does not own it and must never ship a migration
    that pretends to.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    from app.db.session import engine

    if settings.ENVIRONMENT == "production":
        # This fixture writes DDL. Nothing should ever run it at a database
        # serving real founders, and refusing is cheaper than regretting.
        pytest.exit("refusing to run the test suite against ENVIRONMENT=production")

    try:
        _ensure_auth_users(engine, text)
    except OperationalError:
        # No database reachable. That is not this fixture's problem to report.
        #
        # Being session-scoped and autouse, it runs before EVERY test, including
        # the many that need no database at all -- tests/test_rls_context.py is
        # pure MagicMock and passes in CI, which has no Postgres service. An
        # unguarded connect here turned those four into ERRORs on the first CI
        # run of this branch: a fixture nothing in that file asked for, failing
        # for a reason that file does not care about.
        #
        # So: swallow it. A test that genuinely needs the database still fails,
        # on its own connection and with its own message, exactly as it did
        # before this fixture existed.
        return


def _ensure_auth_users(engine, text) -> None:
    with engine.begin() as conn:
        exists = conn.execute(text(
            "select to_regclass('auth.users') is not null"
        )).scalar()
        if exists:
            return
        conn.execute(text("create schema if not exists auth"))
        conn.execute(text("""
            create table if not exists auth.users (
                id uuid primary key,
                instance_id uuid,
                aud varchar(255),
                role varchar(255),
                email varchar(255)
            )
        """))


@pytest.fixture(autouse=True)
def _empty_rate_limit_buckets():
    """Start every test with the rate limiter empty.

    It is a module-level singleton keyed by client IP, and every TestClient in
    the process presents the same IP -- so the whole suite shares one bucket.
    /auth/session allows ten requests a minute, the suite makes far more than
    ten, and every test after that got a 429 in place of whatever it asserted.
    Twelve tests across four files failed that way and not one of them was
    about rate limiting; which twelve depended on collection order, which is
    the worst property a failure can have.
    """
    from app.middleware.rate_limit import _limiter

    _limiter.reset()
    yield
    _limiter.reset()


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
