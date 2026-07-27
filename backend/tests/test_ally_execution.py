"""Unit tests for the Ally AI Execution Layer (Phase 5, Milestone 5).

Fully offline: MockLLMProvider only, no SDK, no network, no API keys.
"""

import json
from decimal import Decimal

import pytest

from app.api.v1.ally.execution import (
    AIExecutionService,
    AIRequest,
    AIResponse,
    AIRouter,
    InvalidResponseFieldError,
    InvalidResponseJSONError,
    MissingResponseFieldError,
    MockLLMProvider,
    ProviderRequest,
    ProviderResponse,
    ResponseParser,
    RoutingPolicy,
    TokenUsage,
    build_execution_service,
)
from app.api.v1.ally.prompts.schemas import PromptMetadata, RenderedPrompt

D = Decimal


def make_prompt(distress=False):
    return RenderedPrompt(
        template_key="t", version=1, category="diagnosis_answer", language="en",
        distress_mode=distress, system_prompt="You are Ally.", user_prompt="Answer this.",
        variables={}, metadata=PromptMetadata(),
    )


def req(distress=False, **kw):
    return AIRequest(prompt=make_prompt(distress), **kw)


def service(provider=None, **kw):
    provider = provider or MockLLMProvider()
    return build_execution_service({"mock": provider}, **kw)


def prov_response(body, prompt=3, completion=4):
    return ProviderResponse(content=body, finish_reason="stop",
                            token_usage=TokenUsage.of(prompt, completion),
                            model="mock-standard", provider="mock")


VALID_BODY = json.dumps({"content": "Hello.", "response_type": "answer",
                         "confidence": 0.8, "citations": ["rc:10"]})


# --- Routing ---------------------------------------------------------------


def test_routing_defaults():
    d = AIRouter().route(req())
    assert (d.provider, d.model, d.temperature, d.max_tokens) == ("mock", "mock-standard", D("0.7"), 800)


def test_routing_distress_uses_careful_model_and_low_temperature():
    d = AIRouter().route(req(distress=True))
    assert d.model == "mock-careful"
    assert d.temperature == D("0.2")
    assert d.max_tokens == 500


def test_routing_overrides_win():
    d = AIRouter().route(req(requested_provider="x", requested_model="m",
                             temperature=D("0.1"), max_tokens=42))
    assert (d.provider, d.model, d.temperature, d.max_tokens) == ("x", "m", D("0.1"), 42)


def test_routing_is_deterministic():
    r = AIRouter()
    first = r.route(req())
    assert all(r.route(req()) == first for _ in range(5))


def test_custom_policy_applied():
    d = AIRouter(RoutingPolicy(default_model="big", default_temperature=D("0.5"))).route(req())
    assert d.model == "big" and d.temperature == D("0.5")


# --- Mock provider ----------------------------------------------------------


def test_mock_provider_generate_is_deterministic():
    p = MockLLMProvider()
    r = ProviderRequest("sys", "user text here", "mock-standard", D("0.7"), 800)
    a, b = MockLLMProvider().generate(r), MockLLMProvider().generate(r)
    assert a.content == b.content and a.token_usage == b.token_usage


def test_provider_metadata_and_health():
    p = MockLLMProvider()
    assert p.metadata().name == "mock"
    assert "mock-standard" in p.metadata().models
    assert p.health().healthy is True


def test_token_accounting_is_consistent():
    r = ProviderRequest("one two", "three four five", "mock-standard", D("0.7"), 800)
    u = MockLLMProvider().generate(r).token_usage
    assert u.prompt_tokens == 5                     # 2 + 3 whitespace tokens
    assert u.total_tokens == u.prompt_tokens + u.completion_tokens


# --- Parser -----------------------------------------------------------------


def test_parser_valid_response():
    out = ResponseParser().parse(prov_response(VALID_BODY))
    assert isinstance(out, AIResponse) and out.ok
    assert out.content == "Hello."
    assert out.confidence == D("0.8")
    assert out.citations == ("rc:10",)
    assert out.token_usage.total_tokens == 7


def test_parser_missing_content():
    with pytest.raises(MissingResponseFieldError):
        ResponseParser().parse(prov_response(json.dumps({"response_type": "answer"})))


def test_parser_invalid_json():
    with pytest.raises(InvalidResponseJSONError):
        ResponseParser().parse(prov_response("not json {"))


def test_parser_confidence_out_of_range():
    with pytest.raises(InvalidResponseFieldError):
        ResponseParser().parse(prov_response(json.dumps({"content": "x", "confidence": 1.5})))


def test_parser_invalid_response_type():
    with pytest.raises(InvalidResponseFieldError):
        ResponseParser().parse(prov_response(json.dumps({"content": "x", "response_type": "sing"})))


def test_parser_invalid_citations():
    with pytest.raises(InvalidResponseFieldError):
        ResponseParser().parse(prov_response(json.dumps({"content": "x", "citations": [1, 2]})))


def test_parser_rejects_negative_token_usage():
    bad = ProviderResponse("{\"content\":\"x\"}", "stop", TokenUsage(-1, 0, -1), "m", "mock")
    with pytest.raises(InvalidResponseFieldError):
        ResponseParser().parse(bad)


# --- Execution service ------------------------------------------------------


def test_execute_success():
    out = service(MockLLMProvider(content=VALID_BODY)).execute(req())
    assert out.ok and out.content == "Hello."
    assert out.metadata.succeeded is True and out.metadata.attempts == 1
    assert out.metadata.provider == "mock" and out.metadata.model == "mock-standard"


def test_execute_malformed_returns_empty():
    out = service(MockLLMProvider(content="not json {")).execute(req())
    assert out.is_empty and out.ok is False
    assert "validation" in out.error


def test_execute_timeout_returns_empty():
    out = service(MockLLMProvider(timeout_times=99), max_retries=2).execute(req())
    assert out.is_empty
    assert out.metadata.timed_out is True
    assert out.metadata.attempts == 3               # 1 + 2 retries
    assert "timeout" in out.error


def test_execute_provider_failure_returns_empty():
    out = service(MockLLMProvider(fail_times=99), max_retries=1).execute(req())
    assert out.is_empty and out.metadata.attempts == 2
    assert "provider_error" in out.error


def test_execute_retries_then_succeeds():
    out = service(MockLLMProvider(fail_times=1, content=VALID_BODY), max_retries=2).execute(req())
    assert out.ok and out.metadata.attempts == 2


def test_execute_unknown_provider_returns_empty():
    out = service().execute(req(requested_provider="ghost"))
    assert out.is_empty and "unknown provider" in out.error


def test_empty_response_never_has_fabricated_text():
    out = service(MockLLMProvider(fail_times=99), max_retries=0).execute(req())
    assert out.content == "" and out.confidence is None and out.citations == ()


def test_distress_routes_to_careful_model_end_to_end():
    out = service(MockLLMProvider(content=VALID_BODY)).execute(req(distress=True))
    assert out.metadata.model == "mock-careful"
    assert out.metadata.temperature == D("0.2")


def test_execution_is_deterministic():
    a = service(MockLLMProvider(content=VALID_BODY)).execute(req())
    b = service(MockLLMProvider(content=VALID_BODY)).execute(req())
    assert a == b
