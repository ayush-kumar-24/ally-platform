"""Unit tests for the ContextWindowBuilder (Phase 6, Milestone 2, Part 1).

Deterministic and hermetic: real ConversationService + real M3/M4/M6 services over
in-memory repos; AllyContext built directly. Verifies history folding, source
injection, fail-closed degradation, deterministic trimming, and that the produced
window is a valid GroundingSource for the frozen grounded prompt manager.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import count
from types import SimpleNamespace

from app.ai_chat import ContextWindowBuilder, ContextWindowConfig, MessageRole, build_conversation_service
from app.ai_chat.attachments.schemas import AttachmentType, SupportedMimeType
from app.planning.models import PlanStatus, Priority, ProgressStatus
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


def setup(*, memory=None, retrieval=None, kg=None, attachments=None, planning=None, config=None):
    conv = build_conversation_service(clock=FakeClock(), id_factory=_ids())
    mem = memory if memory is not None else build_memory_service(InMemoryMemoryRepository(), clock=FakeClock())
    builder = ContextWindowBuilder(
        conversation_service=conv,
        memory=mem,
        retrieval=_retrieval() if retrieval is None else retrieval,
        knowledge_graph=_kg() if kg is None else kg,
        attachments=attachments,
        planning=planning,
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


# --- attachments (Milestone 4 -- files uploaded in this conversation) -------


class FakeAttachment:
    def __init__(self, attachment_id, filename, attachment_type, size_bytes, mime_type=None):
        self.attachment_id = attachment_id
        self.metadata = SimpleNamespace(
            filename=filename, attachment_type=attachment_type, size_bytes=size_bytes,
            mime_type=mime_type,
        )


class FakeAttachments:
    def __init__(self, items=(), content=None):
        self._items = items
        self._content = content or {}

    def list_attachments(self, conversation_id):
        return self._items

    def get_content(self, attachment_id):
        return self._content.get(attachment_id)


def test_attachments_not_configured_is_not_injected():
    conv, builder = setup()  # no attachments service wired
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert w.attachments_injected is False and w.attachments_text == ""


def test_text_attachment_content_is_inlined():
    att = FakeAttachment("att-1", "notes.txt", AttachmentType.TEXT, 20)
    attachments = FakeAttachments(items=(att,), content={"att-1": b"remember to follow up with sales"})
    conv, builder = setup(attachments=attachments)
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert w.attachments_injected is True
    assert "notes.txt" in w.attachments_text
    assert "remember to follow up with sales" in w.attachments_text


def test_binary_attachment_is_named_not_fabricated():
    att = FakeAttachment("att-2", "deck.pdf", AttachmentType.DOCUMENT, 4096)
    attachments = FakeAttachments(items=(att,))  # no decodable content
    conv, builder = setup(attachments=attachments)
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert "deck.pdf" in w.attachments_text
    assert "cannot read its contents" in w.attachments_text


def test_pdf_attachment_text_is_extracted_and_inlined():
    from reportlab.pdfgen import canvas

    buf = __import__("io").BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "Runway is eleven months")
    c.save()
    pdf_bytes = buf.getvalue()

    att = FakeAttachment("att-3", "board-deck.pdf", AttachmentType.DOCUMENT, len(pdf_bytes),
                          mime_type=SupportedMimeType.PDF)
    attachments = FakeAttachments(items=(att,), content={"att-3": pdf_bytes})
    conv, builder = setup(attachments=attachments)
    c2 = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c2, current_message="hi")
    assert "board-deck.pdf" in w.attachments_text
    assert "Runway is eleven months" in w.attachments_text


def test_docx_attachment_text_is_extracted_and_inlined():
    from docx import Document

    buf = __import__("io").BytesIO()
    doc = Document()
    doc.add_paragraph("We are hiring two engineers this quarter.")
    doc.save(buf)
    docx_bytes = buf.getvalue()

    att = FakeAttachment("att-4", "hiring-plan.docx", AttachmentType.DOCUMENT, len(docx_bytes),
                          mime_type=SupportedMimeType.DOCX)
    attachments = FakeAttachments(items=(att,), content={"att-4": docx_bytes})
    conv, builder = setup(attachments=attachments)
    c2 = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c2, current_message="hi")
    assert "hiring-plan.docx" in w.attachments_text
    assert "hiring two engineers" in w.attachments_text


def test_corrupted_pdf_attachment_is_named_not_fabricated():
    att = FakeAttachment("att-5", "corrupt.pdf", AttachmentType.DOCUMENT, 4,
                          mime_type=SupportedMimeType.PDF)
    attachments = FakeAttachments(items=(att,), content={"att-5": b"nope"})
    conv, builder = setup(attachments=attachments)
    c2 = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c2, current_message="hi")
    assert w.attachments_injected is True  # the block itself still renders
    assert "corrupt.pdf" in w.attachments_text
    assert "cannot read its contents" in w.attachments_text


def test_attachment_byte_budget_falls_back_to_name_only_past_the_cap():
    big = FakeAttachment("att-6", "huge.txt", AttachmentType.TEXT, 1000)
    small = FakeAttachment("att-7", "small.txt", AttachmentType.TEXT, 10)
    attachments = FakeAttachments(
        items=(big, small),
        content={"att-6": b"x" * 1000, "att-7": b"tiny note"},
    )
    conv, builder = setup(
        attachments=attachments,
        config=ContextWindowConfig(attachment_byte_budget=1),
    )
    c2 = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c2, current_message="hi")
    # first file is within budget (spent starts at 0) -> extracted
    assert "x" * 1000 in w.attachments_text
    # second file pushes past the tiny budget -> name-only, not fabricated
    assert "small.txt" in w.attachments_text
    assert "tiny note" not in w.attachments_text


def test_attachments_failure_degrades():
    conv, builder = setup(attachments=Boom())
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert w.attachments_injected is False and w.attachments_text == ""


# --- planning tasks (Plan Your Day -- so Ally can relate a message to a task) ---


class FakePlan:
    def __init__(self, plan_id, status=PlanStatus.ACTIVE):
        self.plan_id = plan_id
        self.status = status


class FakeTask:
    def __init__(self, title, status=ProgressStatus.TODO, priority=Priority.MEDIUM, due_date=None):
        self.title = title
        self.status = status
        self.priority = priority
        self.due_date = due_date


class FakePlanning:
    """Mirrors PlanningService's shape for exactly the two calls
    ContextWindowBuilder._safe_tasks makes -- list_plans + get_plan_detail."""

    def __init__(self, plans=(), tasks_by_plan=None):
        self._plans = plans
        self._tasks_by_plan = tasks_by_plan or {}

    def list_plans(self, founder_id):
        return self._plans

    def get_plan_detail(self, founder_id, plan_id):
        tasks = self._tasks_by_plan.get(plan_id, ())
        goal = SimpleNamespace(tasks=tasks)
        return SimpleNamespace(goals=(goal,))


def test_no_planning_configured_is_not_injected():
    conv, builder = setup()  # no planning service wired
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert w.tasks_injected is False and w.tasks_text == ""


def test_not_done_tasks_are_inlined():
    plan = FakePlan("plan-1")
    task = FakeTask("Finish the pitch deck", priority=Priority.HIGH)
    planning = FakePlanning(plans=(plan,), tasks_by_plan={"plan-1": (task,)})
    conv, builder = setup(planning=planning)
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert w.tasks_injected is True
    assert "Finish the pitch deck" in w.tasks_text
    assert "high" in w.tasks_text


def test_done_tasks_are_excluded():
    plan = FakePlan("plan-1")
    done = FakeTask("Ship pricing page copy", status=ProgressStatus.DONE)
    todo = FakeTask("Review CAC")
    planning = FakePlanning(plans=(plan,), tasks_by_plan={"plan-1": (done, todo)})
    conv, builder = setup(planning=planning)
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert "Ship pricing page copy" not in w.tasks_text
    assert "Review CAC" in w.tasks_text


def test_archived_plan_excluded():
    plan = FakePlan("plan-1", status=PlanStatus.ARCHIVED)
    planning = FakePlanning(plans=(plan,), tasks_by_plan={"plan-1": (FakeTask("Old task"),)})
    conv, builder = setup(planning=planning)
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert w.tasks_text == ""


def test_no_active_tasks_still_injected_empty():
    planning = FakePlanning(plans=())
    conv, builder = setup(planning=planning)
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert w.tasks_injected is True  # the source itself didn't fail
    assert w.tasks_text == ""        # just nothing to say


def test_tasks_failure_degrades():
    conv, builder = setup(planning=Boom())
    c = _conv_with(conv, (U, "hi"))
    w = builder.build(ally_context=make_ctx(), conversation=c, current_message="hi")
    assert w.tasks_injected is False and w.tasks_text == ""


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
