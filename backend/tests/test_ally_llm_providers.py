"""Tests for the real LLM providers. Fully offline via httpx.MockTransport --
no network, no API keys, no vendor SDKs. MockLLMProvider remains the deterministic
default and is unchanged.
"""

import json
from decimal import Decimal

import httpx
import pytest

from app.api.v1.ally.execution import (
    AIRequest,
    AIRouter,
    ResponseParser,
    RoutingPolicy,
    build_execution_service,
)
from app.api.v1.ally.execution.provider import MockLLMProvider
from app.api.v1.ally.execution.schemas import ProviderRequest
from app.api.v1.ally.prompts.schemas import PromptMetadata, RenderedPrompt
from app.integrations.llm import (
    ClaudeProvider,
    FailoverLLMProvider,
    GeminiProvider,
    GenerationOptions,
    HealthRegistry,
    LLMAuthError,
    LLMRateLimitError,
    LLMRoutingConfig,
    LLMSettings,
    LLMUnavailableError,
    OpenAIAdapter,
    OpenAIProvider,
    ProviderHealthState,
    build_failover_execution,
    build_provider_registry,
    build_providers,
    build_routing_policy,
)
from app.integrations.llm.routing import _resolve_chain


def provider_with(handler, cls=OpenAIProvider, **kw):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return cls(api_key="k", client=client, **kw)


def req():
    return ProviderRequest("You are Ally.", "Hi", "gpt-4o-mini", Decimal("0.7"), 100)


def status_handler(code):
    return lambda request: httpx.Response(code, json={"error": "x"})


# --- Vendor request/response mapping ----------------------------------------


def test_openai_maps_request_and_response():
    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "gpt-4o-mini"
        assert body["messages"][0]["role"] == "system" and body["messages"][1]["role"] == "user"
        # max_completion_tokens, not max_tokens -- current models (gpt-5.x+)
        # reject max_tokens outright (HTTP 400), which was silently swallowed
        # by FailoverLLMProvider and fell through to the mock provider on
        # every real chat turn until this was traced and fixed.
        assert body["temperature"] == 0.7 and body["max_completion_tokens"] == 100
        # Sending BOTH keys is also a 400, so assert the old one is gone rather
        # than only that the new one is present.
        assert "max_tokens" not in body
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Real answer."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })

    resp = provider_with(handler).generate(req())
    assert json.loads(resp.content)["content"] == "Real answer."
    assert resp.token_usage.total_tokens == 15 and resp.provider == "openai"


def test_claude_maps_request_and_response():
    def handler(request):
        body = json.loads(request.content)
        assert body["system"] == "You are Ally."           # system is top-level for Claude
        assert request.headers["x-api-key"] == "k"
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "Claude answer."}],
            "usage": {"input_tokens": 8, "output_tokens": 4}, "stop_reason": "end_turn",
        })

    resp = provider_with(handler, cls=ClaudeProvider).generate(req())
    assert json.loads(resp.content)["content"] == "Claude answer."
    assert resp.token_usage.total_tokens == 12 and resp.provider == "anthropic"


def test_gemini_maps_request_and_response():
    def handler(request):
        assert "key=k" in str(request.url)                  # Gemini keys the URL
        body = json.loads(request.content)
        assert body["systemInstruction"]["parts"][0]["text"] == "You are Ally."
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": "Gemini answer."}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3},
        })

    resp = provider_with(handler, cls=GeminiProvider).generate(req())
    assert json.loads(resp.content)["content"] == "Gemini answer."
    assert resp.token_usage.total_tokens == 10 and resp.provider == "gemini"


def test_envelope_parses_under_frozen_response_parser():
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Grounded reply."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        })

    ai = ResponseParser().parse(provider_with(handler).generate(req()))
    assert ai.ok and ai.content == "Grounded reply." and ai.response_type == "answer"


# --- Graceful error handling ------------------------------------------------


def test_rate_limit_raises():
    with pytest.raises(LLMRateLimitError):
        provider_with(status_handler(429)).generate(req())


def test_auth_failure_raises():
    with pytest.raises(LLMAuthError):
        provider_with(status_handler(401)).generate(req())


def test_provider_unavailable_raises():
    with pytest.raises(LLMUnavailableError):
        provider_with(status_handler(503)).generate(req())


def test_timeout_raises_builtin_timeouterror():
    def handler(request):
        raise httpx.TimeoutException("slow")

    with pytest.raises(TimeoutError):
        provider_with(handler).generate(req())


def test_transport_error_is_unavailable():
    def handler(request):
        raise httpx.ConnectError("down")

    with pytest.raises(LLMUnavailableError):
        provider_with(handler).generate(req())


# --- End-to-end through the FROZEN AIExecutionService ------------------------


def _prompt():
    return RenderedPrompt(template_key="t", version=1, category="c", language="en",
                          distress_mode=False, system_prompt="sys", user_prompt="user",
                          variables={}, metadata=PromptMetadata())


def _openai_ok(request):
    return httpx.Response(200, json={
        "choices": [{"message": {"content": "Real answer."}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}})


def test_real_provider_through_execution_service():
    svc = build_execution_service(
        {"openai": provider_with(_openai_ok)},
        router=AIRouter(RoutingPolicy(default_provider="openai", default_model="gpt-4o-mini",
                                      distress_model="gpt-4o-mini")),
    )
    ai = svc.execute(AIRequest(prompt=_prompt()))
    assert ai.ok and ai.content == "Real answer." and ai.metadata.provider == "openai"


def test_execution_service_fails_closed_on_provider_error():
    svc = build_execution_service(
        {"openai": provider_with(status_handler(429))},
        router=AIRouter(RoutingPolicy(default_provider="openai", default_model="gpt-4o-mini",
                                      distress_model="gpt-4o-mini")),
        max_retries=1,
    )
    ai = svc.execute(AIRequest(prompt=_prompt()))
    assert ai.is_empty and ai.ok is False and ai.metadata.attempts == 2


# --- Settings / factory -----------------------------------------------------


def test_no_keys_registers_only_mock():
    s = LLMSettings(env={})
    providers = build_providers(s)
    assert set(providers) == {"mock"}
    assert build_routing_policy(s, providers).default_provider == "mock"


def test_provider_registered_when_key_present():
    s = LLMSettings(env={"OPENAI_API_KEY": "k", "ALLY_LLM_PROVIDER": "openai", "OPENAI_MODEL": "gpt-4o"})
    providers = build_providers(s)
    assert "openai" in providers
    policy = build_routing_policy(s, providers)
    assert policy.default_provider == "openai" and policy.default_model == "gpt-4o"


def test_falls_back_to_mock_when_selected_provider_unconfigured():
    s = LLMSettings(env={"ALLY_LLM_PROVIDER": "gemini"})   # no GEMINI_API_KEY
    providers = build_providers(s)
    assert build_routing_policy(s, providers).default_provider == "mock"


# --- Problem 2: request adapters + generation options -----------------------


def test_openai_adapter_default_options_are_no_ops():
    payload = OpenAIAdapter().build_payload(req(), "gpt-4o-mini", GenerationOptions())
    assert "response_format" not in payload and "tools" not in payload
    assert "reasoning_effort" not in payload and "stream" not in payload


def test_openai_adapter_applies_options_when_set():
    opts = GenerationOptions(response_format="json", reasoning_effort="high", tools=("t",), stream=True)
    payload = OpenAIAdapter().build_payload(req(), "gpt-4o-mini", opts)
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["reasoning_effort"] == "high" and payload["tools"] == ["t"] and payload["stream"] is True


def test_provider_uses_its_own_model_not_request_model():
    def handler(request):
        assert json.loads(request.content)["model"] == "gpt-4o"      # provider config, not req()'s model
        return _openai_ok(request)

    provider_with(handler, model="gpt-4o").generate(req())           # req() carries "gpt-4o-mini"


# --- Problem 3: rich provider health ----------------------------------------


def test_health_state_transitions():
    st = ProviderHealthState(provider="openai", model="m", failure_threshold=1)
    assert st.healthy
    st.record_failure()
    assert not st.healthy and st.failures == 1 and st.last_failure is not None
    st.record_success(12.5)
    assert st.healthy and st.failures == 0 and st.latency_ms == 12.5 and st.last_success is not None


def test_provider_records_health_on_success_and_failure():
    ok = ProviderHealthState(provider="openai", model="m")
    provider_with(_openai_ok, health_state=ok).generate(req())
    assert ok.healthy and ok.last_success is not None and ok.latency_ms is not None

    bad = ProviderHealthState(provider="openai", model="m", failure_threshold=1)
    with pytest.raises(LLMRateLimitError):
        provider_with(status_handler(429), health_state=bad).generate(req())
    assert bad.failures == 1 and not bad.healthy


# --- Problem 3b: cross-provider failover ------------------------------------


def _mock_transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _chain_provider(name, model, handler, registry, cls=OpenAIProvider):
    state = registry.ensure(name, model)
    return cls(api_key="k", model=model, client=_mock_transport(handler), health_state=state)


def test_failover_skips_failing_provider():
    reg = HealthRegistry()
    reg.ensure("mock", "mock-standard")
    chain = [
        ("openai", _chain_provider("openai", "gpt-4o-mini", status_handler(503), reg)),
        ("anthropic", _chain_provider("anthropic", "claude-3-5-sonnet-latest",
                                      lambda r: httpx.Response(200, json={
                                          "content": [{"type": "text", "text": "Claude answer."}],
                                          "usage": {"input_tokens": 1, "output_tokens": 1},
                                          "stop_reason": "end_turn"}), reg, cls=ClaudeProvider)),
        ("mock", MockLLMProvider()),
    ]
    resp = FailoverLLMProvider(chain, reg).generate(req())
    assert json.loads(resp.content)["content"] == "Claude answer." and resp.provider == "anthropic"


def test_failover_prefers_healthy_after_failure():
    reg = HealthRegistry()
    reg.ensure("mock", "mock-standard")
    calls = [0]

    def counting_503(request):
        calls[0] += 1
        return httpx.Response(503, json={})

    chain = [
        ("openai", _chain_provider("openai", "gpt-4o-mini", counting_503, reg)),
        ("mock", MockLLMProvider()),
    ]
    failover = FailoverLLMProvider(chain, reg)
    failover.generate(req())        # openai fails once -> unhealthy, mock serves
    failover.generate(req())        # openai now deprioritised, mock served first
    assert calls[0] == 1            # openai not retried while mock is healthy


def test_failover_raises_when_all_fail():
    reg = HealthRegistry()
    chain = [("openai", _chain_provider("openai", "gpt-4o-mini", status_handler(503), reg))]
    with pytest.raises(LLMUnavailableError):
        FailoverLLMProvider(chain, reg).generate(req())


# --- Routing as configuration -----------------------------------------------


def test_routing_config_from_dict():
    cfg = LLMRoutingConfig.from_dict({
        "provider": "openai", "fallback": ["anthropic", "gemini"],
        "temperature": 0.2, "reasoning_model": {"openai": "o4-mini"}})
    assert cfg.default_provider == "openai" and cfg.fallback == ("anthropic", "gemini")
    assert cfg.temperature == Decimal("0.2") and cfg.reasoning_models == {"openai": "o4-mini"}


def test_routing_config_from_settings_reads_fallback_and_temperature():
    s = LLMSettings(env={"ALLY_LLM_PROVIDER": "openai", "ALLY_LLM_FALLBACK": "anthropic, gemini",
                         "ALLY_LLM_TEMPERATURE": "0.3"})
    cfg = LLMRoutingConfig.from_settings(s)
    assert cfg.default_provider == "openai" and cfg.fallback == ("anthropic", "gemini")
    assert cfg.temperature == Decimal("0.3")


def test_resolve_chain_filters_unavailable_and_appends_mock_last():
    s = LLMSettings(env={"OPENAI_API_KEY": "k"})            # only openai available
    reg = HealthRegistry()
    providers = build_provider_registry(s, reg)
    cfg = LLMRoutingConfig(default_provider="openai", fallback=("anthropic", "gemini"))
    assert _resolve_chain(cfg, providers) == ["openai", "mock"]   # anthropic/gemini dropped, mock last


def test_build_failover_execution_offline_defaults_to_mock():
    svc = build_failover_execution(LLMSettings(env={}))     # no keys -> chain is [mock]
    ai = svc.execute(AIRequest(prompt=_prompt()))
    assert ai.ok and not ai.is_empty
