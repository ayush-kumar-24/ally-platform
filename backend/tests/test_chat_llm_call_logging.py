"""Tests for the chat-path LLM call logging fix.

Live-confirmed bug: `llm_call_log` has always recorded every reasoning-pipeline
call but never a single chat-path call -- a real chat turn (200 OK, real Anthropic
response) left zero new rows even 15 minutes later. This covers the fix:
`record_chat_llm_call` (the logging function itself) and its wiring into
`ChatExecutionService.send_message` (call_logger is invoked with the right
arguments on success and on failure, is optional/backward-compatible, and can
never break the chat turn it's describing even if it raises).
"""

from decimal import Decimal
from datetime import datetime, timedelta, timezone

from app.ai_chat import ChatExecutionService, ChatRequest, ContextWindowBuilder, build_conversation_service
from app.ai_chat.execution.llm_call_logging import record_chat_llm_call
from app.api.v1.ally.memory.schemas import MemorySearchRequest, MemoryType
from app.api.v1.ally.context.builder import AllyContextBuilder
from app.api.v1.ally.execution.provider import MockLLMProvider
from app.api.v1.ally.execution.schemas import (
    AIResponse, ExecutionMetadata, ResponseType, TokenUsage,
)
from app.api.v1.ally.execution import build_execution_service
from app.api.v1.ally.kg import InMemoryKnowledgeGraphRepository, build_knowledge_graph_service
from app.api.v1.ally.memory import InMemoryMemoryRepository, build_memory_service
from app.api.v1.ally.prompts.grounding import default_grounded_prompt_manager
from app.api.v1.ally.rag import InMemoryVectorRetrievalRepository, build_retrieval_service
from types import SimpleNamespace
import json

D = Decimal
T0 = datetime(2026, 7, 28, 11, 0, 0, tzinfo=timezone.utc)
ANSWER = "Here is your grounded answer."
VALID_BODY = json.dumps({"content": ANSWER, "response_type": "answer", "confidence": 0.8, "citations": []})


# --- direct tests of record_chat_llm_call -----------------------------------


class FakeSession:
    """Minimal stand-in for a SQLAlchemy Session -- records what was added."""

    def __init__(self, raise_on_commit=False):
        self.added = []
        self.committed = False
        self.closed = False
        self._raise_on_commit = raise_on_commit

    def add(self, row):
        self.added.append(row)

    def commit(self):
        if self._raise_on_commit:
            raise RuntimeError("db down")
        self.committed = True

    def close(self):
        self.closed = True


def _ok_response(provider="anthropic", model="claude-sonnet-5"):
    return AIResponse(
        ok=True, content=ANSWER, response_type=ResponseType.ANSWER.value, confidence=D("0.8"),
        citations=(), token_usage=TokenUsage.of(100, 40),
        metadata=ExecutionMetadata(provider=provider, model=model, temperature=D("0.7"),
                                   max_tokens=800, attempts=1, succeeded=True),
    )


def _failed_response():
    return AIResponse(
        ok=False, content="", response_type="none", confidence=None, citations=(),
        token_usage=TokenUsage(), metadata=None, error="all providers exhausted",
    )


def test_record_chat_llm_call_writes_expected_row_on_success():
    session = FakeSession()
    record_chat_llm_call(
        _ok_response(), founder_id=7, session_id=42, latency_ms=1234,
        session_factory=lambda: session,
    )
    assert session.committed and session.closed
    assert len(session.added) == 1
    row = session.added[0]
    assert row.task == "ally_chat"
    assert row.provider == "anthropic"
    assert row.model_id == "claude-sonnet-5"
    assert row.status == "ok"
    assert row.input_tokens == 100
    assert row.output_tokens == 40
    assert row.latency_ms == 1234
    assert row.founder_id == 7
    assert row.session_id == 42
    assert row.error is None
    # claude-sonnet-5 is in the pricing table -> a real (non-None) estimate.
    assert row.estimated_cost_usd is not None


def test_record_chat_llm_call_writes_error_row_on_failure():
    session = FakeSession()
    record_chat_llm_call(
        _failed_response(), founder_id=7, session_id=None, latency_ms=50,
        session_factory=lambda: session,
    )
    row = session.added[0]
    assert row.status == "error"
    assert row.error == "all providers exhausted"
    assert row.input_tokens is None and row.output_tokens is None
    assert row.estimated_cost_usd is None
    assert row.session_id is None


def test_record_chat_llm_call_unknown_model_gets_no_cost_estimate():
    session = FakeSession()
    record_chat_llm_call(
        _ok_response(provider="openai", model="gpt-4o-mini"), founder_id=1, session_id=1,
        latency_ms=10, session_factory=lambda: session,
    )
    # gpt-4o-mini isn't in the (Anthropic-only) pricing table -- estimate_cost
    # returns None rather than guessing or raising. Confirms the fail-soft
    # behaviour this function inherits from services.llm.telemetry.estimate_cost.
    assert session.added[0].estimated_cost_usd is None


def test_record_chat_llm_call_swallows_db_failure_never_raises():
    session = FakeSession(raise_on_commit=True)
    # Must not raise -- telemetry must never break the chat turn it describes.
    record_chat_llm_call(
        _ok_response(), founder_id=1, session_id=1, latency_ms=10,
        session_factory=lambda: session,
    )
    assert session.closed  # cleanup still happens even though commit blew up


def test_record_chat_llm_call_swallows_factory_failure_never_raises():
    def _boom():
        raise RuntimeError("no connection")
    # Must not raise even if getting a session at all fails.
    record_chat_llm_call(_ok_response(), founder_id=1, session_id=1, latency_ms=10, session_factory=_boom)


# --- wiring into ChatExecutionService ----------------------------------------


class WorldContextRepo:
    def get_founder(self, fid):
        return SimpleNamespace(founder_id=fid, full_name="Asha", stage_id=5, industry_mapped_id=3)

    def get_stage(self, sid):
        return SimpleNamespace(stage_name="Growth / Scaling", stage_order=6)

    def get_industry(self, iid):
        return SimpleNamespace(industry_name="SaaS")

    def get_session(self, sid):
        return SimpleNamespace(overall_confidence_score=D("72"), routing_state="validate",
                               distress_mode_triggered=False, session_state="stable")

    def get_latest_active_report(self, fid, session_id=None):
        return None

    def get_detected_root_causes(self, sid):
        return []

    def get_root_causes_by_ids(self, ids):
        return {}

    def get_internal_report(self, sid):
        return None


class FakeClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def now(self):
        v = self._now
        self._now += self._step
        return v


def _chat_service(*, call_logger=None, execution=None):
    memory = build_memory_service(InMemoryMemoryRepository(), clock=FakeClock())
    conversations = build_conversation_service(clock=FakeClock())
    retrieval = build_retrieval_service(InMemoryVectorRetrievalRepository([]))
    kg = build_knowledge_graph_service(InMemoryKnowledgeGraphRepository([], []))
    execution = execution or build_execution_service({"mock": MockLLMProvider(content=VALID_BODY)})
    window_builder = ContextWindowBuilder(
        conversation_service=conversations, memory=memory, retrieval=retrieval, knowledge_graph=kg)
    return ChatExecutionService(
        context_builder=AllyContextBuilder(WorldContextRepo()),
        conversation_service=conversations,
        context_window_builder=window_builder,
        prompt_manager=default_grounded_prompt_manager(),
        execution=execution,
        call_logger=call_logger,
        clock=FakeClock(),
    )


def test_call_logger_invoked_on_successful_turn():
    calls = []
    chat = _chat_service(call_logger=lambda ai, **kw: calls.append((ai, kw)))
    resp = chat.send_message(ChatRequest(founder_id=1, message="Why are my margins thin?", session_id=42))
    assert resp.ok
    assert len(calls) == 1
    ai, kw = calls[0]
    assert ai.ok and ai.content == ANSWER
    assert kw["founder_id"] == 1
    assert kw["session_id"] == 42
    assert isinstance(kw["latency_ms"], int) and kw["latency_ms"] >= 0


def test_no_call_logger_is_backward_compatible():
    # Default (call_logger=None) -- unchanged behaviour from before this fix,
    # must not error just because nothing was passed.
    chat = _chat_service(call_logger=None)
    resp = chat.send_message(ChatRequest(founder_id=1, message="Hello", session_id=1))
    assert resp.ok


def test_raising_call_logger_never_breaks_the_chat_turn():
    def _boom(ai, **kw):
        raise RuntimeError("logging exploded")
    chat = _chat_service(call_logger=_boom)
    resp = chat.send_message(ChatRequest(founder_id=1, message="Hello", session_id=1))
    # The chat turn must still succeed -- telemetry failing is never the
    # founder's problem. This is the whole point of the fail-open wrapping
    # around self.call_logger(...) in send_message.
    assert resp.ok
    assert resp.answer == ANSWER


# --- wiring the memory-write fix ---------------------------------------------


def _chat_service_with_memory(*, memory):
    conversations = build_conversation_service(clock=FakeClock())
    retrieval = build_retrieval_service(InMemoryVectorRetrievalRepository([]))
    kg = build_knowledge_graph_service(InMemoryKnowledgeGraphRepository([], []))
    execution = build_execution_service({"mock": MockLLMProvider(content=VALID_BODY)})
    window_builder = ContextWindowBuilder(
        conversation_service=conversations, memory=memory, retrieval=retrieval, knowledge_graph=kg)
    return ChatExecutionService(
        context_builder=AllyContextBuilder(WorldContextRepo()),
        conversation_service=conversations,
        context_window_builder=window_builder,
        prompt_manager=default_grounded_prompt_manager(),
        execution=execution,
        memory=memory,
        clock=FakeClock(),
    )


def test_memory_gets_written_after_a_real_chat_turn():
    # Live-confirmed bug this fixes: a real chat turn (real Anthropic response,
    # RAG genuinely firing) left founder_memory at 0 rows immediately after.
    # ChatExecutionService never called memory.store() anywhere -- this proves
    # it now does, using the real (in-memory-backed) MemoryService, not a fake.
    memory = build_memory_service(InMemoryMemoryRepository(), clock=FakeClock())
    chat = _chat_service_with_memory(memory=memory)
    resp = chat.send_message(ChatRequest(
        founder_id=1, message="Why do my margins stay flat while revenue grows?", session_id=42))
    assert resp.ok
    found = memory.search(MemorySearchRequest(founder_id=1, limit=10)).items
    assert len(found) == 1
    item = found[0]
    assert item.content == "Why do my margins stay flat while revenue grows?"
    assert item.memory_type == MemoryType.WORKING
    assert item.metadata.importance == 50


def test_no_memory_service_is_backward_compatible():
    # Default (memory=None passed explicitly via the plain _chat_service helper,
    # which is what every existing caller/test in this file already does) --
    # must not error just because nothing was passed.
    chat = _chat_service(call_logger=None)
    resp = chat.send_message(ChatRequest(founder_id=1, message="Hello", session_id=1))
    assert resp.ok


def test_raising_memory_store_never_breaks_the_chat_turn():
    class BoomMemory:
        def store(self, *a, **k):
            raise RuntimeError("memory store exploded")

    chat = _chat_service_with_memory(memory=BoomMemory())
    resp = chat.send_message(ChatRequest(founder_id=1, message="Hello", session_id=1))
    # Same fail-open guarantee as call_logger: a broken memory write must never
    # surface as a broken chat turn.
    assert resp.ok
    assert resp.answer == ANSWER


def test_memory_persisted_even_when_ai_execution_fails():
    # Mirrors the M7 orchestrator's own (already-reviewed) design: the memory
    # write is unconditional on ai.ok -- the founder said this regardless of
    # whether Ally managed to answer it.
    from app.api.v1.ally.execution.provider import LLMProvider as _LLMProvider

    class FailingProvider(_LLMProvider):
        def generate(self, request):
            raise RuntimeError("boom")

        def health(self):
            from app.api.v1.ally.execution.schemas import ProviderHealth
            return ProviderHealth(healthy=False, detail="down")

        def metadata(self):
            from app.api.v1.ally.execution.schemas import ProviderMetadata
            return ProviderMetadata(name="failing", models=("x",))

    memory = build_memory_service(InMemoryMemoryRepository(), clock=FakeClock())
    execution = build_execution_service({"mock": FailingProvider()})
    chat = _chat_service_with_memory(memory=memory)
    chat.execution = execution
    resp = chat.send_message(ChatRequest(founder_id=1, message="This will fail", session_id=1))
    assert not resp.ok
    found = memory.search(MemorySearchRequest(founder_id=1, limit=10)).items
    assert len(found) == 1
    assert found[0].content == "This will fail"


def test_chat_telemetry_applies_founder_rls_context():
    class RlsFakeSession(FakeSession):
        def __init__(self):
            super().__init__()
            self.info = {}

        def in_transaction(self):
            return False

    session = RlsFakeSession()
    founder_uuid = "22222222-2222-2222-2222-222222222222"

    record_chat_llm_call(
        _ok_response(),
        founder_id=7,
        founder_uuid=founder_uuid,
        session_id=42,
        latency_ms=123,
        session_factory=lambda: session,
    )

    assert session.info["current_founder_uuid"] == founder_uuid
    assert session.added[0].founder_id == 7
