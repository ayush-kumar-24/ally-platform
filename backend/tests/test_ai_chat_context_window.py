"""Unit tests for the ContextWindowBuilder (Phase 6, Milestone 2, Part 1).

Deterministic and hermetic: real ConversationService + real M3/M4/M6 services over
in-memory repos; AllyContext built directly. Verifies history folding, source
injection, fail-closed degradation, deterministic trimming, and that the produced
window is a valid GroundingSource for the frozen grounded prompt manager.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import count

from app.ai_chat import ContextWindowBuilder, ContextWindowConfig, MessageRole, build_conversation_service
from app.api.v1.ally.context.schemas import (
    AllyContext,
    DiagnosisContext,
    FounderProfileContext,
    RootCauseContext,
)
from app.api.v1.ally.kg import (
    GraphEdge,
    GraphNode,
    InMemoryKnowledgeGraphRepository,
    NodeType,
    RelationshipType,
    build_knowledge_graph_service,
)
from app.api.v1.ally.memory import (
    InMemoryMemoryRepository,
    MemoryType,
    build_memory_service,
)
from app.api.v1.ally.prompts.grounding import default_grounded_prompt_manager
from app.api.v1.ally.rag import (
    InMemoryVectorRetrievalRepository,
    KnowledgeChunk,
    build_retrieval_service,
)

D = Decimal
T0 = datetime(2026, 7, 28, 11, 0, 0, tzinfo=timezone.utc)
U, A = MessageRole.USER, MessageRole.ASSISTANT


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


def make_ctx():
    founder = FounderProfileContext(1, "Asha", 5, "Growth / Scaling", "SaaS")
    diagnosis = DiagnosisContext(
        session_id=42, overall_confidence=D("72"), routing_state="validate",
        distress_mode=False, session_state="stable", executive_summary="Focus on activation.",
        priority_actions=("Interview churned users",), next_steps=("Book a call",),
    )
    rcs = (RootCauseContext(10, "RC-010", "Weak activation", "Sales & Revenue", 1,
                            "unconfirmed", D("0.8"), True),)
    return AllyContext(founder=founder, has_diagnosis=True, diagnosis=diagnosis, root_causes=rcs)


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


class Boom:
    def __getattr__(self, _n):
        def _raise(*a, **k):
            raise RuntimeError("down")
        return _raise


def setup(*, memory=None, retrieval=None, kg=None, config=None):
    conv = build_conversation_service(clock=FakeClock(), id_factory=_ids())
    mem = memory if memory is not None else build_memory_service(InMemoryMemoryRepository(), clock=FakeClock())
    builder = ContextWindowBuilder(
        conversation_service=conv,
        memory=mem,
        retrieval=_retrieval() if retrieval is None else retrieval,
        knowledge_graph=_kg() if kg is None else kg,
        config=config,
    )
    return conv, builder


def _conv_with(conv, *messages, important_first=False):
    c = conv.create_conversation(1)
    for i, (role, text) in enumerate(messages):
        conv.append_message(c.conversation_id, role, text, important=(important_first and i == 0))
    return conv.get_conversation(c.conversation_id)


# --- message composition ----------------------------------------------------


def test_first_message_has_no_transcript():
    conv, builder = setup()
    c = _conv_with(conv, (U, "hello"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hello")
    assert w.request.message == "hello"


def test_history_is_folded_into_founder_message():
    conv, builder = setup()
    c = _conv_with(conv, (U, "q1"), (A, "a1"), (U, "q2"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="q2")
    msg = w.request.message
    assert "Founder: q1" in msg and "Ally: a1" in msg
    assert "Founder's current message:\nq2" in msg


# --- source injection -------------------------------------------------------


def test_memory_injected():
    mem = build_memory_service(InMemoryMemoryRepository(), clock=FakeClock())
    mem.store(1, MemoryType.STRATEGIC, "Founder prefers async updates.", importance=80, actor="t")
    conv, builder = setup(memory=mem)
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert w.memory_injected and len(w.memory_items) == 1


def test_retrieval_injected():
    conv, builder = setup()
    c = _conv_with(conv, (U, "how do I activate users"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="how do I activate users")
    assert w.retrieval_injected and not w.retrieval.is_empty


def test_graph_injected():
    conv, builder = setup()
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert w.graph_injected and len(w.graph.nodes) == 2


# --- fail-closed degradation ------------------------------------------------


def test_memory_failure_degrades():
    conv, builder = setup(memory=Boom())
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert w.memory_injected is False and w.memory_items == ()


def test_retrieval_failure_degrades():
    conv, builder = setup(retrieval=Boom())
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert w.retrieval_injected is False and w.retrieval is None


def test_graph_failure_degrades():
    conv, builder = setup(kg=Boom())
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert w.graph_injected is False and w.graph is None


# --- deterministic trimming -------------------------------------------------


def test_trims_long_history_deterministically():
    conv, builder = setup(config=ContextWindowConfig(max_history_messages=3))
    c = _conv_with(conv, *[(U, f"m{i}") for i in range(6)])
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="m5")
    assert w.history_size == 6 and w.included_size == 3 and w.trimmed_size == 3


def test_preserves_important_message_when_trimming():
    conv, builder = setup(config=ContextWindowConfig(max_history_messages=3))
    c = _conv_with(conv, *[(U, f"m{i}") for i in range(6)], important_first=True)
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="m5")
    kept = w.conversation_context.recent_messages
    assert any(m.important for m in kept)                    # m0 preserved despite being old


# --- GroundingSource compatibility ------------------------------------------


def test_window_is_a_valid_grounding_source():
    mem = build_memory_service(InMemoryMemoryRepository(), clock=FakeClock())
    mem.store(1, MemoryType.STRATEGIC, "Prefers data-driven advice.", importance=70, actor="t")
    conv, builder = setup(memory=mem)
    c = _conv_with(conv, (U, "How do I improve activation?"))
    w = builder.build(ally_context=make_ctx(), conversation=c,
                      current_message="How do I improve activation?")

    rendered = default_grounded_prompt_manager().render_grounded(w)   # frozen manager consumes it
    body = rendered.user_prompt
    assert "Prefers data-driven advice." in body                     # memory (M6)
    assert "Guided onboarding lifts activation." in body             # retrieval (M3)
    assert "Weak activation" in body                                 # graph (M4)
    assert "How do I improve activation?" in body                    # current message
