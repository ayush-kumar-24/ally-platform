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
