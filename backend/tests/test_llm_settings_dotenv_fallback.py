"""LLM providers register from `.env`, not only from the process environment.

`LLMSettings` reads `os.environ`. pydantic-settings parses `.env` into the
Settings OBJECT and never exports it to the environment -- so on a machine whose
keys live only in `.env`, every provider looked unconfigured and the registry
built with `mock` alone.

That does not raise. `mock` is the documented graceful fallback, so chat
answered founders with fabricated text ("Grounded answer from mock-standard")
and reported success. Whether it happened depended on IMPORT ORDER: something in
`app.main`'s chain populates os.environ, so importing it first gave real
providers and importing anything that built the container first gave the mock,
with no error either way.

Same class of bug as PLAN_ENFORCEMENT_ENABLED (see plans/dependencies.py), which
was fixed there and left here.
"""

from app.integrations.llm.settings import LLMSettings, _env_with_dotenv_fallback


def test_env_wins_over_dotenv():
    """A deployment that deliberately overrides a key keeps its override. The
    fallback fills gaps; it never replaces a real environment value."""
    merged = _env_with_dotenv_fallback()
    # Simulate: the environment already carries a value.
    import os

    os.environ["OPENAI_API_KEY"] = "sk-from-environment"
    try:
        assert _env_with_dotenv_fallback()["OPENAI_API_KEY"] == "sk-from-environment"
    finally:
        del os.environ["OPENAI_API_KEY"]
    assert isinstance(merged, dict)


def test_keys_from_dotenv_are_visible_without_being_exported(monkeypatch):
    """The actual regression: keys present in the parsed settings but absent
    from os.environ must still configure the providers."""
    from app.core import config

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "sk-dotenv-openai",
                        raising=False)
    monkeypatch.setattr(config.settings, "ANTHROPIC_API_KEY", "sk-dotenv-anthropic",
                        raising=False)

    settings = LLMSettings()

    assert settings.openai_api_key == "sk-dotenv-openai"
    assert settings.anthropic_api_key == "sk-dotenv-anthropic"


def test_providers_register_without_importing_app_main(monkeypatch):
    """The end the founder feels: a real provider chain rather than the mock.

    Asserted through the registry rather than the settings object, because the
    settings being right is not the bug -- the registry silently containing
    only `mock` is.
    """
    from app.core import config
    from app.integrations.llm.health import HealthRegistry
    from app.integrations.llm.routing import build_provider_registry

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "sk-dotenv-openai",
                        raising=False)

    providers = build_provider_registry(LLMSettings(), HealthRegistry())

    assert "openai" in providers, sorted(providers)
    assert providers != {"mock"}


def test_explicit_env_argument_is_still_honoured():
    """LLMSettings(env=...) is how tests pin an exact environment. The fallback
    must not leak real keys into a case that passed its own dict."""
    settings = LLMSettings(env={"OPENAI_API_KEY": "sk-explicit"})

    assert settings.openai_api_key == "sk-explicit"
    assert settings.anthropic_api_key in (None, "")
