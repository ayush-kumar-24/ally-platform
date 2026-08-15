"""Integration tests for the ChatExecutionService (Phase 6, Milestone 2).

The full contextual chat turn over the real composed stack (only the LLM is
mocked): AllyContext (M1) + ConversationService (M1) + memory (M6) + retrieval
(M3) + graph (M4) + grounded prompt (M2.1) + AI execution (M5). Covers every
required Part-7 scenario, including multi-turn recall, isolation, concurrency,
trace correctness, determinism, and fail-closed failure modes.
"""

from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from itertools import count
import json

import pytest

from app.ai_chat import (
    ChatExecutionService,
    ChatRequest,
    ContextWindowBuilder,
    ContextWindowConfig,
    ConversationNotFoundError,
    InvalidConversationStateError,
    MessageRole,
    build_conversation_service,
)
from app.api.v1.ally.context.builder import AllyContextBuilder
from app.api.v1.ally.context.errors import FounderNotFoundError
from app.api.v1.ally.execution import MockLLMProvider, build_execution_service
from app.api.v1.ally.kg import (
    GraphEdge,
    GraphNode,
    InMemoryKnowledgeGraphRepository,
    NodeType,
    RelationshipType,
    build_knowledge_graph_service,
)
from app.api.v1.ally.memory import InMemoryMemoryRepository, MemoryType, build_memory_service
from app.api.v1.ally.prompts.grounding import default_grounded_prompt_manager
from app.api.v1.ally.rag import (
    InMemoryVectorRetrievalRepository,
    KnowledgeChunk,
    build_retrieval_service,
)
from app.models.enums import StageGroup
from types import SimpleNamespace

D = Decimal
T0 = datetime(2026, 7, 28, 11, 0, 0, tzinfo=timezone.utc)
ANSWER = "Here is your grounded answer."
VALID_BODY = json.dumps({"content": ANSWER, "response_type": "answer",
                         "confidence": 0.8, "citations": ["rc:10"]})

STEPS = ("build_context", "load_conversation", "append_user_message",
         "build_context_window", "render_prompt", "execute_ai", "append_assistant_message")


class FakeClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def now(self):
        v = self._now
        self._now += self._step
        return v


def _ids():
    c = count(1)
    return lambda: f"id-{next(c)}"


class WorldContextRepo:
    _STAGES = {5: "Growth / Scaling", 6: "Early Traction"}
    # stage_order drives AllyContextBuilder's stage_groups (which retrieval's
    # stage filter actually reads -- rag_documents.stage_relevance is tagged
    # with the question bank's stage-GROUP vocabulary, not stage names).
    # 6 -> Stage 1->10+, 3 -> Stage 0->1: arbitrary but internally consistent
    # with the seeded chunk below, which is what these tests actually check.
    _STAGE_ORDERS = {5: 6, 6: 3}
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
        return SimpleNamespace(stage_name=self._STAGES.get(sid, "Growth / Scaling"),
                               stage_order=self._STAGE_ORDERS.get(sid, 6))

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
    # stage="Stage 1->10+" (not the stage NAME "Growth / Scaling") to match
    # what founder 1 (stage_order=6, see WorldContextRepo) actually resolves
    # to via stage_groups -- the vocabulary retrieval's stage filter reads.
    chunk = KnowledgeChunk("c1", "rag_chunks", 1, "Guided onboarding lifts activation.",
                           D("0.7"), stage=StageGroup.STAGE_1_TO_10_PLUS.value, industry="SaaS",
                           category="Sales & Revenue", root_cause_ids=(10,))
    return build_retrieval_service(InMemoryVectorRetrievalRepository([chunk]))


def _kg():
    rc = GraphNode("root_cause:10", NodeType.ROOT_CAUSE, 10, "Weak activation")
    prob = GraphNode("problem:5", NodeType.PROBLEM, 5, "Low trial conversion")
    edge = GraphEdge("root_cause:10", "problem:5", RelationshipType.ROOT_CAUSE_TO_PROBLEM)
    return build_knowledge_graph_service(InMemoryKnowledgeGraphRepository([rc, prob], [edge]))


class Boom:
    def __getattr__(self, _n):
        def _raise(*a, **k):
            raise RuntimeError("subsystem down")
        return _raise


class CapturingExecution:
    """Wraps an execution service and records the prompt actually sent."""

    def __init__(self, inner):
        self.inner = inner
        self.requests = []

    def execute(self, req):
        self.requests.append(req)
        return self.inner.execute(req)

    @property
    def last_prompt(self):
        return self.requests[-1].prompt


class ChatWorld:
    def __init__(self, *, memory=None, retrieval=None, knowledge_graph=None, execution=None,
                 max_history=20, deterministic=True):
        self.repo = WorldContextRepo()
        self.memory = memory or build_memory_service(
            InMemoryMemoryRepository(), clock=(FakeClock() if deterministic else None))
        self.conversations = build_conversation_service(
            clock=(FakeClock() if deterministic else None),
            id_factory=(_ids() if deterministic else None))
        self.retrieval = _retrieval() if retrieval is None else retrieval
        self.kg = _kg() if knowledge_graph is None else knowledge_graph
        self.execution = execution or build_execution_service({"mock": MockLLMProvider(content=VALID_BODY)})
        self.window_builder = ContextWindowBuilder(
            conversation_service=self.conversations, memory=self.memory,
            retrieval=self.retrieval, knowledge_graph=self.kg,
            config=ContextWindowConfig(max_history_messages=max_history))
        self.chat = ChatExecutionService(
            context_builder=AllyContextBuilder(self.repo),
            conversation_service=self.conversations,
            context_window_builder=self.window_builder,
            prompt_manager=default_grounded_prompt_manager(),
            execution=self.execution,
            clock=(FakeClock() if deterministic else None),
            id_factory=(_ids() if deterministic else None))

    def send(self, founder_id=1, message="How do I improve activation?", conversation_id=None, **kw):
        return self.chat.send_message(ChatRequest(
            founder_id=founder_id, message=message, conversation_id=conversation_id,
            session_id=42, **kw))


# --- happy path -------------------------------------------------------------


def test_first_message_creates_conversation_and_answers():
    w = ChatWorld()
    r = w.send()
    assert r.ok and r.answer == ANSWER and r.confidence == D("0.8")
    history = w.conversations.get_history(r.conversation_id)
    assert [m.role for m in history] == [MessageRole.USER, MessageRole.ASSISTANT]
    assert r.assistant_message_id is not None


def test_second_message_recalls_previous_context():
    w = ChatWorld(execution=CapturingExecution(build_execution_service(
        {"mock": MockLLMProvider(content=VALID_BODY)})))
    first = w.send(message="How do I improve activation?")
    w.send(message="What metric matters?", conversation_id=first.conversation_id)
    prompt = w.execution.last_prompt.user_prompt
    assert "How do I improve activation?" in prompt          # turn 1 folded into turn 2 context


def test_long_conversation_is_trimmed():
    w = ChatWorld(max_history=4)
    conv_id = w.send(message="turn 0").conversation_id
    for i in range(1, 8):
        w.send(message=f"turn {i}", conversation_id=conv_id)
    r = w.send(message="final", conversation_id=conv_id)
    assert r.metrics.trimmed_messages > 0
    assert r.metrics.included_messages <= 4


# --- source injection through the flow --------------------------------------


def _capturing_world(**kw):
    return ChatWorld(execution=CapturingExecution(build_execution_service(
        {"mock": MockLLMProvider(content=VALID_BODY)})), **kw)


def test_founder_memory_injected_into_prompt():
    w = _capturing_world()
    w.memory.store(1, MemoryType.STRATEGIC, "Founder prefers async updates.", importance=80, actor="t")
    r = w.send()
    assert r.trace.memory_injected and r.metrics.memory_reads >= 1
    assert "async updates" in w.execution.last_prompt.user_prompt


def test_retrieval_injected_into_prompt():
    w = _capturing_world()
    r = w.send(message="how do I activate trial users")
    assert r.trace.retrieval_injected and r.metrics.retrieval_hits >= 1
    assert "Guided onboarding lifts activation." in w.execution.last_prompt.user_prompt


def test_graph_injected_into_prompt():
    w = _capturing_world()
    r = w.send()
    assert r.trace.graph_injected and r.metrics.graph_nodes == 2
    assert "Low trial conversion" in w.execution.last_prompt.user_prompt


def test_grounded_prompt_receives_all_sources():
    w = _capturing_world()
    w.memory.store(1, MemoryType.STRATEGIC, "Prefers data-driven advice.", importance=70, actor="t")
    first = w.send(message="How do I improve activation?")
    w.send(message="And after that?", conversation_id=first.conversation_id)
    body = w.execution.last_prompt.user_prompt
    assert "Prefers data-driven advice." in body                # memory
    assert "Guided onboarding lifts activation." in body        # retrieval
    assert "Weak activation" in body                            # graph
    assert "How do I improve activation?" in body               # earlier turn
    assert "And after that?" in body                            # current message


# --- persistence + multi-turn -----------------------------------------------


def test_assistant_reply_is_persisted():
    w = ChatWorld()
    r = w.send()
    last = w.conversations.get_history(r.conversation_id)[-1]
    assert last.role == MessageRole.ASSISTANT and last.content == ANSWER
    assert w.conversations.get_conversation(r.conversation_id).unread_count == 1


# --- idempotent replay (retried request_id) ---------------------------------


def test_retried_request_id_does_not_call_the_llm_again():
    """Live-reproduced gap: a client timeout can fire after the server has
    actually completed the turn, and the founder is told to resend. Resending
    with the SAME request_id must return the original answer without a
    second LLM call or a duplicated turn in history."""
    capturing = CapturingExecution(build_execution_service({"mock": MockLLMProvider(content=VALID_BODY)}))
    w = ChatWorld(execution=capturing)
    first = w.send(message="hi", request_id="retry-1")
    assert len(capturing.requests) == 1

    second = w.send(message="hi", conversation_id=first.conversation_id, request_id="retry-1")
    assert len(capturing.requests) == 1                          # no second LLM call
    assert second.ok and second.answer == first.answer
    assert second.assistant_message_id == first.assistant_message_id

    history = w.conversations.get_history(first.conversation_id)
    assert [m.role for m in history] == [MessageRole.USER, MessageRole.ASSISTANT]  # not duplicated


def test_request_id_only_on_user_message_still_runs():
    """A request_id present on a user message but with no assistant reply yet
    (e.g. the process died mid-turn before persisting one) must NOT be treated
    as already-complete -- that would silently answer nothing forever."""
    capturing = CapturingExecution(build_execution_service({"mock": MockLLMProvider(content=VALID_BODY)}))
    w = ChatWorld(execution=capturing)
    cid = w.send(message="setup").conversation_id                # 1 LLM call
    w.conversations.append_message(cid, MessageRole.USER, "orphaned", metadata={"request_id": "orphan-1"})

    r = w.send(message="orphaned", conversation_id=cid, request_id="orphan-1")
    assert len(capturing.requests) == 2                           # ran normally, not replayed
    assert r.ok and r.answer == ANSWER


def test_different_request_id_with_same_text_is_a_new_turn():
    """An edited-and-resent (or genuinely repeated) message with a NEW
    request_id is a real new message, not a replay -- the frontend only
    reuses the id when resending the exact failed attempt unchanged."""
    capturing = CapturingExecution(build_execution_service({"mock": MockLLMProvider(content=VALID_BODY)}))
    w = ChatWorld(execution=capturing)
    first = w.send(message="hi", request_id="a")
    w.send(message="hi", conversation_id=first.conversation_id, request_id="b")
    assert len(capturing.requests) == 2
    assert w.conversations.get_conversation(first.conversation_id).message_count == 4


def test_conversation_survives_multiple_turns():
    w = ChatWorld()
    cid = w.send(message="one").conversation_id
    w.send(message="two", conversation_id=cid)
    w.send(message="three", conversation_id=cid)
    conv = w.conversations.get_conversation(cid)
    assert conv.message_count == 6                              # 3 user + 3 assistant


def test_multiple_founders_isolated():
    w = ChatWorld()
    r1 = w.send(founder_id=1, message="founder one")
    r2 = w.send(founder_id=2, message="founder two")
    assert r1.conversation_id != r2.conversation_id
    h1 = [m.content for m in w.conversations.get_history(r1.conversation_id) if m.role == MessageRole.USER]
    h2 = [m.content for m in w.conversations.get_history(r2.conversation_id) if m.role == MessageRole.USER]
    assert h1 == ["founder one"] and h2 == ["founder two"]


# --- trace + determinism ----------------------------------------------------


def test_pipeline_trace_correctness():
    r = ChatWorld().send()
    t = r.trace
    assert t.completed_steps == STEPS and t.failed_step is None
    assert t.provider == "mock" and t.model in ("mock-standard", "mock-careful")
    assert t.memory_injected and t.retrieval_injected and t.graph_injected
    assert t.started_at < t.finished_at and t.duration_ms > 0
    # prompt_version 1: general_chat_grounded.standard is the default chat category
    # (a founder can talk about anything, not only their diagnosis -- see the
    # attachment/general-chat fix); diagnosis_answer_grounded (v2) is still
    # resolvable but is no longer what an ordinary chat turn selects by default.
    assert r.metrics.retrieval_hits == 1 and r.metrics.graph_nodes == 2 and r.metrics.prompt_version == 1


def test_deterministic_execution():
    a = ChatWorld().send(request_id="fixed")
    b = ChatWorld().send(request_id="fixed")
    assert a.answer == b.answer
    assert a.trace.completed_steps == b.trace.completed_steps
    assert a.trace.metrics == b.trace.metrics
    assert a.trace.duration_ms == b.trace.duration_ms
    assert a.conversation_id == b.conversation_id


# --- concurrency ------------------------------------------------------------


def test_concurrent_conversations_across_founders():
    w = ChatWorld(deterministic=False)                         # uuid ids, real clock

    def journey(founder):
        r = w.send(founder_id=founder, message=f"hello from {founder}")
        return r.ok and r.answer == ANSWER

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(journey, [1, 2] * 12))
    assert all(results)


# --- failure scenarios (fail closed) ----------------------------------------


def test_unknown_founder_raises():
    with pytest.raises(FounderNotFoundError):
        ChatWorld().send(founder_id=999)


def test_missing_conversation_raises():
    with pytest.raises(ConversationNotFoundError):
        ChatWorld().send(conversation_id="does-not-exist")


def test_archived_conversation_raises():
    w = ChatWorld()
    cid = w.send().conversation_id
    w.conversations.archive_conversation(cid)
    with pytest.raises(InvalidConversationStateError):
        w.send(conversation_id=cid)


def test_foreign_conversation_is_hidden():
    w = ChatWorld()
    cid = w.send(founder_id=1).conversation_id
    with pytest.raises(ConversationNotFoundError):
        w.send(founder_id=2, conversation_id=cid)              # founder 2 cannot use founder 1's chat


def test_ai_timeout_fails_closed_without_persisting_reply():
    w = ChatWorld(execution=build_execution_service(
        {"mock": MockLLMProvider(timeout_times=99)}, max_retries=1))
    r = w.send()
    assert r.ok is False and r.is_empty and r.answer == ""
    assert r.trace.failed_step == "execute_ai" and r.assistant_message_id is None
    # user message persisted, assistant NOT.
    history = w.conversations.get_history(r.conversation_id)
    assert [m.role for m in history] == [MessageRole.USER]


def test_retrieval_unavailable_degrades_but_answers():
    w = ChatWorld(retrieval=Boom())
    r = w.send()
    assert r.ok and not r.trace.retrieval_injected and r.metrics.retrieval_hits == 0


def test_graph_unavailable_degrades_but_answers():
    w = ChatWorld(knowledge_graph=Boom())
    r = w.send()
    assert r.ok and not r.trace.graph_injected and r.metrics.graph_nodes == 0


def test_memory_unavailable_degrades_but_answers():
    w = ChatWorld(memory=Boom())
    r = w.send()
    assert r.ok and not r.trace.memory_injected and r.metrics.memory_reads == 0


def test_founder_without_diagnosis_can_still_chat():
    # A founder with no diagnosis yet must still be able to chat -- the
    # general_chat_grounded default has no diagnosis precondition (unlike the
    # old diagnosis_answer_grounded default, which made this founder's very
    # first chat message fail closed before they'd ever completed a diagnosis).
    w = ChatWorld()
    r = w.send(founder_id=2, message="hi")   # founder 2 answerable; sanity it works
    assert r.ok
    r3 = w.send(founder_id=3, message="hi")  # founder 3: valid, no diagnosis
    assert r3.ok is True and r3.trace.failed_step is None
    assert r3.assistant_message_id is not None
