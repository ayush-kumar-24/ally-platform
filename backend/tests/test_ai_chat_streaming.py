"""Tests for Streaming Responses (Phase 6, Milestone 3).

Deterministic and offline: the streaming layer wraps the real M2 chat flow (mock
LLM only). Covers chunking, ordering, cancellation, timeout, empty/error handling,
metrics, trace lifecycle, persistence gating, concurrency, isolation, determinism,
and the async/iterator interfaces.
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import count
from types import SimpleNamespace

import pytest

from app.ai_chat import build_conversation_service, MessageRole
from app.ai_chat.execution.chat_execution import ChatExecutionService
from app.ai_chat.builders.context_window import ContextWindowBuilder
from app.ai_chat.schemas.chat import ChatMetrics, ChatResponse, ConversationExecutionTrace
from app.ai_chat.streaming import (
    CancelToken,
    ChunkType,
    StreamingChatRequest,
    StreamingChatService,
    StreamingConfig,
    StreamingGenerator,
    chunk_text,
)
from app.ai_chat.streaming.events import StreamingEventType as ET
from app.api.v1.ally.context.builder import AllyContextBuilder
from app.api.v1.ally.execution import MockLLMProvider, build_execution_service
from app.api.v1.ally.execution.schemas import TokenUsage
from app.api.v1.ally.kg import (
    GraphEdge, GraphNode, InMemoryKnowledgeGraphRepository, NodeType,
    RelationshipType, build_knowledge_graph_service,
)
from app.api.v1.ally.memory import InMemoryMemoryRepository, build_memory_service
from app.api.v1.ally.prompts.grounding import default_grounded_prompt_manager
from app.api.v1.ally.rag import (
    InMemoryVectorRetrievalRepository, KnowledgeChunk, build_retrieval_service,
)

D = Decimal
T0 = datetime(2026, 7, 28, 12, 0, 0, tzinfo=timezone.utc)
ANSWER = "Here is your grounded answer."
VALID_BODY = json.dumps({"content": ANSWER, "response_type": "answer",
                         "confidence": 0.8, "citations": ["rc:10"]})


class FakeClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def now(self):
        v = self._now
        self._now += self._step
        return v


class FrozenClock:
    def now(self):
        return T0


def _ids():
    c = count(1)
    return lambda: f"id-{next(c)}"


class WorldContextRepo:
    _STAGES = {5: "Growth / Scaling", 6: "Early Traction"}
    _INDUSTRIES = {3: "SaaS", 4: "Fintech"}

    def __init__(self):
        self._founders = {
            1: dict(full_name="Asha", stage_id=5, industry_mapped_id=3),
            2: dict(full_name="Bo", stage_id=6, industry_mapped_id=4),
            3: dict(full_name="Cara", stage_id=5, industry_mapped_id=3),
        }
        self._has_report = {1, 2}

    def get_founder(self, fid):
        f = self._founders.get(fid)
        return SimpleNamespace(founder_id=fid, **f) if f else None

    def get_stage(self, sid):
        return SimpleNamespace(stage_name=self._STAGES.get(sid, "Growth / Scaling"))

    def get_industry(self, iid):
        return SimpleNamespace(industry_name=self._INDUSTRIES.get(iid, "SaaS"))

    def get_session(self, sid):
        return SimpleNamespace(overall_confidence_score=D("72"), routing_state="validate",
                               distress_mode_triggered=False, session_state="stable")

    def get_latest_active_report(self, fid, session_id=None):
        if fid not in self._has_report:
            return None
        return SimpleNamespace(report_id=90 + fid, session_id=40 + fid, is_active=True,
                               generated_at=T0, summary="Focus on activation.",
                               session_state_at_generation="stable",
                               insights={"executive_summary": "Focus on activation."})

    def get_detected_root_causes(self, sid):
        return [SimpleNamespace(root_cause_id=10, rank=1, is_top_finding=True,
                                confirmation_status="unconfirmed", final_weighted_score=D("0.8"))]

    def get_root_causes_by_ids(self, ids):
        return {10: SimpleNamespace(root_cause_name="Weak activation", root_cause_code="RC-010",
                                    category="Sales & Revenue")}

    def get_internal_report(self, sid):
        return None


def _retrieval():
    chunk = KnowledgeChunk("c1", "rag_chunks", 1, "Guided onboarding lifts activation.",
                           D("0.7"), stage="Growth / Scaling", industry="SaaS",
                           category="Sales & Revenue", root_cause_ids=(10,))
    return build_retrieval_service(InMemoryVectorRetrievalRepository([chunk]))


def _kg():
    rc = GraphNode("root_cause:10", NodeType.ROOT_CAUSE, 10, "Weak activation")
    prob = GraphNode("problem:5", NodeType.PROBLEM, 5, "Low trial conversion")
    edge = GraphEdge("root_cause:10", "problem:5", RelationshipType.ROOT_CAUSE_TO_PROBLEM)
    return build_knowledge_graph_service(InMemoryKnowledgeGraphRepository([rc, prob], [edge]))


class StreamWorld:
    def __init__(self, *, execution=None, deterministic=True, stream_clock=None):
        repo = WorldContextRepo()
        det = deterministic
        self.memory = build_memory_service(InMemoryMemoryRepository(),
                                           clock=(FakeClock() if det else None))
        self.conversations = build_conversation_service(
            clock=(FakeClock() if det else None), id_factory=(_ids() if det else None))
        execution = execution or build_execution_service({"mock": MockLLMProvider(content=VALID_BODY)})
        window = ContextWindowBuilder(conversation_service=self.conversations, memory=self.memory,
                                      retrieval=_retrieval(), knowledge_graph=_kg())
        chat = ChatExecutionService(
            context_builder=AllyContextBuilder(repo), conversation_service=self.conversations,
            context_window_builder=window, prompt_manager=default_grounded_prompt_manager(),
            execution=execution, clock=(FakeClock() if det else None),
            id_factory=(_ids() if det else None))
        self.streaming = StreamingChatService(
            chat_service=chat, conversation_service=self.conversations,
            clock=(stream_clock or (FrozenClock() if det else None)),
            id_factory=(_ids() if det else None))

    def req(self, founder_id=1, message="How do I improve activation?", conversation_id=None, **kw):
        return StreamingChatRequest(founder_id=founder_id, message=message,
                                    conversation_id=conversation_id, session_id=42, **kw)


# --- Part 4: deterministic chunking -----------------------------------------


def test_chunk_by_sentence():
    assert chunk_text("A cat sat. A dog ran.", 100) == ["A cat sat.", "A dog ran."]


def test_chunk_word_fallback():
    assert chunk_text("alpha beta gamma delta", 11) == ["alpha beta", "gamma delta"]


def test_chunk_is_deterministic():
    text = "Focus on activation. Interview churned users to learn why they left."
    assert chunk_text(text, 15) == chunk_text(text, 15)


def test_chunk_empty_and_whitespace():
    assert chunk_text("", 10) == [] and chunk_text("   ", 10) == []


def test_chunk_respects_max_size():
    out = chunk_text("one two six ten sun cat dog", 7)
    assert all(len(c) <= 7 for c in out)


# --- stream start / complete ------------------------------------------------


def test_stream_start_chunk_first():
    chunks = list(StreamWorld().streaming.stream(StreamWorld().req()))
    assert chunks[0].chunk_type == ChunkType.START and chunks[0].index == 0


def test_stream_completes_with_answer():
    w = StreamWorld()
    r = w.streaming.collect(w.req())
    assert r.ok and r.completed and r.answer == ANSWER
    assert r.chunks[-1].chunk_type == ChunkType.COMPLETE and r.chunks[-1].final


def test_deterministic_chunks():
    a = StreamWorld().streaming.collect(StreamWorld().req(max_chunk_size=8))
    b = StreamWorld().streaming.collect(StreamWorld().req(max_chunk_size=8))
    assert [c.content for c in a.token_chunks] == [c.content for c in b.token_chunks]


def test_chunk_ordering_and_reconstruction():
    w = StreamWorld()
    r = w.streaming.collect(w.req(max_chunk_size=8))
    assert [c.index for c in r.chunks] == list(range(len(r.chunks)))
    assert r.chunks[0].chunk_type == ChunkType.START
    assert r.chunks[-1].chunk_type == ChunkType.COMPLETE
    assert " ".join(c.content for c in r.token_chunks) == ANSWER


# --- metrics + trace --------------------------------------------------------


def test_metrics_populated():
    w = StreamWorld()
    r = w.streaming.collect(w.req())
    m = r.metrics
    assert m.chunk_count == len(r.chunks) and m.token_count == len(ANSWER.split())
    assert m.completed and not m.cancelled and not m.timed_out
    assert m.request_id and m.conversation_id


def test_trace_event_lifecycle_order():
    w = StreamWorld()
    r = w.streaming.collect(w.req(max_chunk_size=8))
    types = [e.event_type for e in r.trace.events]
    assert types[0] == ET.START and types[1] == ET.MESSAGE_RECEIVED
    for earlier, later in [(ET.CONTEXT_READY, ET.PROMPT_READY), (ET.PROMPT_READY, ET.AI_STARTED),
                           (ET.AI_STARTED, ET.TOKEN), (ET.AI_FINISHED, ET.MESSAGE_PERSISTED),
                           (ET.MESSAGE_PERSISTED, ET.COMPLETE)]:
        assert types.index(earlier) < types.index(later)
    assert types[-1] == ET.COMPLETE


# --- persistence gating -----------------------------------------------------


def test_assistant_persisted_after_completion():
    w = StreamWorld()
    r = w.streaming.collect(w.req())
    assert r.assistant_message_id is not None
    history = w.conversations.get_history(r.conversation_id)
    assert history[-1].role == MessageRole.ASSISTANT and history[-1].content == ANSWER


def test_no_persistence_after_cancel_midstream():
    w = StreamWorld()
    token = CancelToken()
    sink = []
    cancelled_once = False
    for chunk in w.streaming.stream(w.req(max_chunk_size=5), cancel=token, sink=sink):
        if chunk.chunk_type == ChunkType.TOKEN and not cancelled_once:
            token.cancel()                        # stop after the first token
            cancelled_once = True
    r = sink[0]
    assert r.cancelled and not r.completed and r.assistant_message_id is None
    assert r.chunks[-1].chunk_type == ChunkType.CANCELLED
    history = w.conversations.get_history(r.conversation_id)
    assert [m.role for m in history] == [MessageRole.USER]     # assistant NOT persisted


def test_cancel_before_generation():
    w = StreamWorld()
    token = CancelToken()
    token.cancel()
    r = w.streaming.collect(w.req(), cancel=token)
    assert r.cancelled and not r.completed
    assert [c.chunk_type for c in r.chunks] == [ChunkType.START, ChunkType.CANCELLED]


# --- timeout ----------------------------------------------------------------


def test_timeout_midstream_does_not_persist():
    class TimeoutClock:
        def __init__(self):
            self.n = 0

        def now(self):
            self.n += 1
            return T0 if self.n <= 2 else T0 + timedelta(seconds=1000)

    w = StreamWorld(stream_clock=TimeoutClock())
    r = w.streaming.collect(w.req(timeout_seconds=5))
    assert r.timed_out and not r.completed and r.assistant_message_id is None
    assert r.chunks[-1].chunk_type == ChunkType.ERROR
    history = w.conversations.get_history(r.conversation_id)
    assert [m.role for m in history] == [MessageRole.USER]


# --- empty + error (generator over a stubbed chat service) ------------------


def _fake_response(*, ok, answer, conversation_id="conv-1", error=None):
    trace = ConversationExecutionTrace(
        request_id="r", conversation_id=conversation_id, started_at=T0, finished_at=T0,
        duration_ms=0.0,
        completed_steps=("build_context", "load_conversation", "append_user_message",
                         "build_context_window", "render_prompt", "execute_ai"),
        failed_step=None if ok else "render_prompt",
        provider="mock" if ok else None, model="mock-standard" if ok else None,
        memory_injected=True, retrieval_injected=True, graph_injected=True,
        metrics=ChatMetrics(token_usage=TokenUsage()))
    return ChatResponse(request_id="r", conversation_id=conversation_id, ok=ok, answer=answer,
                        response_type="answer" if ok else "none", confidence=None, citations=(),
                        assistant_message_id=None, trace=trace, metrics=ChatMetrics(token_usage=TokenUsage()),
                        error=error)


class FakeChatService:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def send_message(self, request, *, persist_assistant=True):
        self.calls += 1
        return self.response


def _generator_over(response):
    return StreamingGenerator(
        chat_service=FakeChatService(response),
        conversation_service=build_conversation_service(clock=FakeClock(), id_factory=_ids()),
        clock=FrozenClock(), id_factory=_ids())


def test_empty_response_completes_without_persisting():
    r = _generator_over(_fake_response(ok=True, answer="")).collect(
        StreamingChatRequest(founder_id=1, message="hi"))
    assert r.completed and r.ok and r.metrics.token_count == 0
    assert r.assistant_message_id is None and len(r.token_chunks) == 0


def test_error_propagation():
    r = _generator_over(_fake_response(ok=False, answer="", error="boom")).collect(
        StreamingChatRequest(founder_id=1, message="hi"))
    assert not r.ok and not r.completed and r.error == "boom"
    assert r.chunks[-1].chunk_type == ChunkType.ERROR
    assert r.assistant_message_id is None


# --- concurrency + isolation ------------------------------------------------


def test_concurrent_streams():
    w = StreamWorld(deterministic=False)

    def run(founder):
        r = w.streaming.collect(w.req(founder_id=founder, message=f"hi {founder}"))
        return r.completed and r.answer == ANSWER

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(run, [1, 2] * 12))


def test_multiple_founders_isolated():
    w = StreamWorld()
    r1 = w.streaming.collect(w.req(founder_id=1, message="founder one"))
    r2 = w.streaming.collect(w.req(founder_id=2, message="founder two"))
    assert r1.conversation_id != r2.conversation_id
    u1 = [m.content for m in w.conversations.get_history(r1.conversation_id) if m.role == MessageRole.USER]
    u2 = [m.content for m in w.conversations.get_history(r2.conversation_id) if m.role == MessageRole.USER]
    assert u1 == ["founder one"] and u2 == ["founder two"]


# --- deterministic replay ---------------------------------------------------


def test_deterministic_replay():
    a = StreamWorld().streaming.collect(StreamWorld().req(max_chunk_size=8))
    b = StreamWorld().streaming.collect(StreamWorld().req(max_chunk_size=8))
    assert [(c.chunk_type, c.content, c.index) for c in a.chunks] == \
           [(c.chunk_type, c.content, c.index) for c in b.chunks]
    assert a.metrics.token_count == b.metrics.token_count and a.metrics.chunk_count == b.metrics.chunk_count


# --- iterator + async interfaces --------------------------------------------


def test_iterator_interface():
    w = StreamWorld()
    it = iter(w.streaming.stream(w.req()))
    assert next(it).chunk_type == ChunkType.START


def test_async_collect():
    w = StreamWorld()
    r = asyncio.run(w.streaming.acollect(w.req()))
    assert r.completed and r.ok and r.answer == ANSWER


def test_async_stream_yields_same_chunks():
    w = StreamWorld()

    async def go():
        return [c async for c in w.streaming.astream(w.req(max_chunk_size=8))]

    chunks = asyncio.run(go())
    assert chunks[0].chunk_type == ChunkType.START and chunks[-1].chunk_type == ChunkType.COMPLETE
