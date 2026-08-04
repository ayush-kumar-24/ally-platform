"""Tests for M2.1 -- grounded prompt construction.

Hermetic: builds the frozen DTOs directly (context, memory, retrieval, graph) and
renders through the GroundedPromptManager. No DB, no LLM, no subsystem services.
Proves grounding works AND that the frozen M2 v1 path is untouched.
"""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.v1.ally.context.schemas import (
    AllyContext,
    DiagnosisContext,
    FounderProfileContext,
    RootCauseContext,
)
from app.api.v1.ally.kg.schemas import (
    GraphEdge,
    GraphMetadata,
    GraphNode,
    GraphView,
    NodeType,
    RelationshipType,
)
from app.api.v1.ally.memory.schemas import (
    MemoryAudit,
    MemoryItem,
    MemoryMetadata,
    MemoryStatus,
    MemoryType,
    Retention,
)
from app.api.v1.ally.prompts import default_prompt_manager
from app.api.v1.ally.prompts.grounding import (
    GroundingError,
    default_grounded_prompt_manager,
    graph_expansion,
    memory_summary,
)
from app.api.v1.ally.prompts.grounding.manager import GroundedPromptManager
from app.api.v1.ally.prompts.errors import MissingPromptVariableError
from app.api.v1.ally.rag.schemas import (
    KnowledgeChunk,
    RankingScore,
    RetrievalFilters,
    RetrievalResult,
    RetrievedKnowledge,
)

D = Decimal
DT = datetime(2026, 1, 1, 12, 0, 0)


# --- builders ---------------------------------------------------------------


def make_ctx(*, distress=False, name="Asha", stage="Growth / Scaling",
             summary="Focus on activation.", conf=D("72")):
    founder = FounderProfileContext(1, name, 5, stage, "SaaS")
    diagnosis = DiagnosisContext(
        session_id=42, overall_confidence=conf, routing_state="validate",
        distress_mode=distress, session_state="stable", executive_summary=summary,
        priority_actions=("Interview churned users",), next_steps=("Book a call",),
    )
    rcs = (
        RootCauseContext(10, "RC-010", "Weak activation", "Sales & Revenue", 1,
                         "unconfirmed", D("0.8"), True),
    )
    return AllyContext(founder=founder, has_diagnosis=True, diagnosis=diagnosis, root_causes=rcs)


def make_memory(content, importance, *, mem_id="mem:1", status=MemoryStatus.ACTIVE):
    audit = MemoryAudit(created_at=DT, updated_at=DT, created_by="ally", updated_by="ally")
    meta = MemoryMetadata(retention=Retention.TEMPORARY, status=status, importance=importance,
                          tags=(), session_id=None, expires_at=None, audit=audit)
    return MemoryItem(memory_id=mem_id, founder_id=1, memory_type=MemoryType.WORKING,
                      content=content, key=None, metadata=meta)


def make_retrieval(*chunks):
    items = tuple(
        RetrievedKnowledge(
            chunk=KnowledgeChunk(chunk_id=f"c{i}", source=src, source_id=i, content=text,
                                 similarity=D("0.9")),
            score=RankingScore(D("0.9"), D("1"), D("1"), D("1"), D("1"), D("1"), D("0.9")),
            rank=i + 1,
        )
        for i, (src, text) in enumerate(chunks)
    )
    return RetrievalResult(items=items, query="q", filters=RetrievalFilters(),
                           enabled=True, candidate_count=len(items), unique_count=len(items))


def make_graph():
    nodes = (
        GraphNode("root_cause:10", NodeType.ROOT_CAUSE, 10, "Weak activation"),
        GraphNode("problem:20", NodeType.PROBLEM, 20, "Low trial conversion"),
    )
    edges = (GraphEdge("root_cause:10", "problem:20", RelationshipType.ROOT_CAUSE_TO_PROBLEM),)
    meta = GraphMetadata(root_cause_ids=(10,), traversal_depth=1, truncated=False,
                         node_count=2, edge_count=1, node_type_counts={}, relationship_counts={})
    return GraphView(nodes=nodes, edges=edges, metadata=meta)


def source(*, ctx=None, memory=(), retrieval=None, graph=None, message="Why is activation weak?",
           category="diagnosis_answer", language="en"):
    return SimpleNamespace(
        request=SimpleNamespace(message=message, language=language, response_category=category),
        ally_context=make_ctx() if ctx is None else ctx,
        memory_items=tuple(memory),
        retrieval=retrieval,
        graph=graph,
    )


# --- grounded rendering -----------------------------------------------------


def test_grounded_prompt_includes_all_four_sources_plus_message():
    src = source(
        memory=[make_memory("Founder prefers weekly async check-ins.", 80)],
        retrieval=make_retrieval(("rag_chunks", "Activation improves when onboarding is guided.")),
        graph=make_graph(),
    )
    rendered = default_grounded_prompt_manager().render_grounded(src)

    assert rendered.template_key == "diagnosis_answer_grounded.standard"
    assert rendered.version == 2 and rendered.category == "diagnosis_answer_grounded"
    body = rendered.user_prompt
    assert "Focus on activation." in body                         # diagnosis (M1)
    assert "Weak activation" in body                              # top root cause (M1)
    assert "weekly async check-ins" in body                       # memory (M6)
    assert "onboarding is guided" in body                         # retrieval (M3)
    assert "Weak activation —[root cause to problem]→ Low trial conversion" in body  # graph (M4)
    assert "Why is activation weak?" in body                      # founder message


def test_absent_sources_use_sentinels_not_fabrication():
    rendered = default_grounded_prompt_manager().render_grounded(source())  # no memory/rag/graph
    body = rendered.user_prompt
    assert "No stored founder memory yet." in body
    assert "No supporting knowledge retrieved." in body
    assert "No related diagnostic map available." in body


def test_distress_selects_grounded_distress_template():
    src = source(ctx=make_ctx(distress=True), memory=[make_memory("Had a tough fundraising month.", 60)],
                 retrieval=make_retrieval(("rag_chunks", "should-not-appear")))
    rendered = default_grounded_prompt_manager().render_grounded(src)
    assert rendered.template_key == "diagnosis_answer_grounded.distress"
    assert "should-not-appear" not in rendered.user_prompt        # no retrieval in distress
    assert "tough fundraising month" in rendered.user_prompt      # memory still used for warmth


def test_blank_message_fails_closed():
    with pytest.raises(MissingPromptVariableError):
        default_grounded_prompt_manager().render_grounded(source(message="   "))


def test_missing_context_raises_grounding_error():
    src = source()
    src.ally_context = None
    with pytest.raises(GroundingError):
        default_grounded_prompt_manager().render_grounded(src)


def test_render_is_deterministic():
    src = source(memory=[make_memory("x", 50)], graph=make_graph())
    a = default_grounded_prompt_manager().render_grounded(src)
    b = default_grounded_prompt_manager().render_grounded(src)
    assert a.prompt_fingerprint == b.prompt_fingerprint


# --- backward compatibility (frozen M2 untouched) ---------------------------


def test_original_v1_templates_still_resolve_unchanged():
    # Frozen manager: original path unaffected.
    v1 = default_prompt_manager().render(make_ctx(), category="diagnosis_answer")
    assert v1.template_key == "diagnosis_answer.standard" and v1.version == 1

    # Grounded manager renders v1 through the INHERITED render for the same category
    # (grounded v2 lives under a distinct category, so there is no collision).
    v1_via_grounded = default_grounded_prompt_manager().render(make_ctx(), category="diagnosis_answer")
    assert v1_via_grounded.template_key == "diagnosis_answer.standard" and v1_via_grounded.version == 1


def test_pipeline_context_satisfies_grounding_source():
    # The real frozen M7 PipelineContext must be a valid GroundingSource (structural),
    # so the orchestrator can pass it directly.
    from app.api.v1.ally.orchestrator.schemas import FounderRequest, PipelineContext

    pctx = PipelineContext(
        request=FounderRequest(founder_id=1, message="What should I fix first?"),
        ally_context=make_ctx(),
        memory_items=(make_memory("Prefers data-driven advice.", 70),),
        retrieval=make_retrieval(("root_causes", "Weak activation is the top blocker.")),
        graph=make_graph(),
    )
    rendered = default_grounded_prompt_manager().render_grounded(pctx)
    assert rendered.category == "diagnosis_answer_grounded"
    assert "What should I fix first?" in rendered.user_prompt
    assert "data-driven advice" in rendered.user_prompt


# --- flattener units --------------------------------------------------------


def test_memory_summary_orders_by_importance_then_id():
    items = (make_memory("low", 30, mem_id="mem:b"), make_memory("high", 90, mem_id="mem:a"))
    out = memory_summary(items)
    assert out.index("high") < out.index("low")


def test_memory_summary_skips_archived():
    items = (make_memory("archived", 90, status=MemoryStatus.ARCHIVED),)
    assert memory_summary(items) == ""


def test_graph_expansion_falls_back_to_nodes_without_edges():
    nodes = (GraphNode("root_cause:10", NodeType.ROOT_CAUSE, 10, "Weak activation"),)
    meta = GraphMetadata(root_cause_ids=(10,), traversal_depth=0, truncated=False,
                         node_count=1, edge_count=0, node_type_counts={}, relationship_counts={})
    out = graph_expansion(GraphView(nodes=nodes, edges=(), metadata=meta))
    assert out == "- root_cause: Weak activation"


def test_inherited_render_is_a_grounded_manager():
    assert isinstance(default_grounded_prompt_manager(), GroundedPromptManager)


# --- general_chat_grounded (default chat category -- can talk about anything) --


def test_general_chat_renders_without_a_diagnosis():
    """The behaviour the diagnosis-only default used to break: a founder with no
    diagnosis yet must still get a rendered prompt, not a fail-closed error."""
    no_diagnosis_ctx = AllyContext(
        founder=FounderProfileContext(3, "Priya", None, None, None), has_diagnosis=False,
    )
    src = source(ctx=no_diagnosis_ctx, message="hey, how's it going?", category="general_chat")
    rendered = default_grounded_prompt_manager().render_grounded(src)
    assert rendered.template_key == "general_chat_grounded.standard"
    assert "No diagnosis completed yet." in rendered.user_prompt
    assert "hey, how's it going?" in rendered.user_prompt


def test_general_chat_includes_diagnosis_when_present():
    src = source(category="general_chat")  # default make_ctx() has a diagnosis
    rendered = default_grounded_prompt_manager().render_grounded(src)
    assert "Focus on activation." in rendered.user_prompt
    assert "Weak activation" in rendered.user_prompt


def test_general_chat_attachments_use_sentinel_when_absent():
    src = source(category="general_chat")
    rendered = default_grounded_prompt_manager().render_grounded(src)
    assert "No files uploaded in this conversation." in rendered.user_prompt


def test_general_chat_attachments_are_rendered_when_present():
    src = source(category="general_chat")
    src.attachments_text = "- notes.txt (text, 1 KB):\nfollow up with sales"
    rendered = default_grounded_prompt_manager().render_grounded(src)
    assert "follow up with sales" in rendered.user_prompt


def test_general_chat_distress_selects_distress_template():
    src = source(ctx=make_ctx(distress=True), category="general_chat",
                 memory=[make_memory("Had a tough fundraising month.", 60)])
    rendered = default_grounded_prompt_manager().render_grounded(src)
    assert rendered.template_key == "general_chat_grounded.distress"
    assert "tough fundraising month" in rendered.user_prompt
