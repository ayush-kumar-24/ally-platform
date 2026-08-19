"""Milestone 7 -- production end-to-end validation & hardening (no new features).

Validates the whole AI Chat system through the HTTP layer: the full founder journey,
the failure matrix, concurrency, a load simulation, and API-contract checks. Reuses
the offline-wired harness from test_api_chat (fake M1 context repo + mock LLM). Deep
per-layer failure modes (streaming cancel/timeout, memory/retrieval/graph
unavailable, provider timeout) are covered in the ai_chat service suites, which also
run under `python -m pytest`.
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.v1.chat import dependencies as deps
from app.api.v1.privacy.dependencies import require_ai_processing_allowed_for_id
# `from app.api.v1.chat import router` would resolve to the re-exported
# APIRouter instance (app/api/v1/chat/__init__.py does `from .router import
# router`, colliding with the submodule's own name) rather than the module --
# import the two names directly instead, off the actual module object.
from app.api.v1.chat.router import message_rate_limit, stream_rate_limit
from app.api.v1.plans.dependencies import ChatGate, chat_gate
from app.ai_chat import build_conversation_service
from app.ai_chat.attachments import build_attachment_service
from app.ai_chat.builders.context_window import ContextWindowBuilder
from app.ai_chat.execution.chat_execution import ChatExecutionService
from app.ai_chat.links import LinkExtractor
from app.ai_chat.streaming.service import StreamingChatService
from app.ai_chat.suggestions import build_suggestion_service
from app.api.v1.ally.context.builder import AllyContextBuilder
from app.api.v1.ally.execution import MockLLMProvider, build_execution_service
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
ANSWER = "Here is your grounded answer."
VALID_BODY = json.dumps({"content": ANSWER, "response_type": "answer",
                         "confidence": 0.8, "citations": ["rc:10"]})
BASE = "/api/v1/chat"


class WorldContextRepo:
    _STAGES = {5: "Growth / Scaling", 6: "Early Traction"}
    _INDUSTRIES = {3: "SaaS", 4: "Fintech"}

    def __init__(self):
        self._founders = {1: dict(full_name="Asha", stage_id=5, industry_mapped_id=3),
                          2: dict(full_name="Bo", stage_id=6, industry_mapped_id=4)}

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
        return SimpleNamespace(report_id=90 + fid, session_id=40 + fid, is_active=True,
                               generated_at=None, summary="Focus on activation.",
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


@pytest.fixture
def world():
    conv = build_conversation_service()
    att = build_attachment_service()
    sug = build_suggestion_service()
    links = LinkExtractor()
    window = ContextWindowBuilder(conversation_service=conv,
                                  memory=build_memory_service(InMemoryMemoryRepository()),
                                  retrieval=_retrieval(), knowledge_graph=_kg())
    chat = ChatExecutionService(
        context_builder=AllyContextBuilder(WorldContextRepo()), conversation_service=conv,
        context_window_builder=window, prompt_manager=default_grounded_prompt_manager(),
        execution=build_execution_service({"mock": MockLLMProvider(content=VALID_BODY)}),
        # Suggestions are now generated inline right after a chat turn (see
        # ChatExecutionService.send_message step 8) -- wired to the SAME `sug`
        # instance the GET /suggestions endpoint override reads from below.
        suggestion_service=sug)
    stream = StreamingChatService(chat_service=chat, conversation_service=conv)

    founder = {"id": 1}
    overrides = {
        deps.get_current_founder_id: lambda: founder["id"],
        deps.get_conversation_service: lambda: conv,
        deps.get_attachment_service: lambda: att,
        deps.get_suggestion_service: lambda: sug,
        deps.get_link_extractor: lambda: links,
        deps.get_chat_service: lambda: chat,
        deps.get_streaming_service: lambda: stream,
        # This suite (see module docstring) validates the chat pipeline itself --
        # conversations, attachments, concurrency -- not plan enforcement, which
        # has its own dedicated tests. Without this override, PLAN_ENFORCEMENT_ENABLED
        # locally (true in .env) sends every message through the REAL entitlement
        # gate against whatever founder_id=1 actually is in the database. That
        # was silently riding on the old 40,000 token/day Free ceiling; dropping
        # it to 4,000 (2026-08-16 product decision) started failing
        # test_100_concurrent_messages with a bare KeyError, because a handful of
        # the 100 calls got a real 429 mid-run instead of the mocked answer.
        chat_gate: lambda: ChatGate(founder_id=founder["id"], tier="free",
                                    service=None, enforced=False),
        # Same reasoning as the chat_gate override above, for a second, later
        # gate: require_ai_processing_allowed_for_id resolves a real DB-backed
        # PrivacyService (may_process checks founders.processing_restricted_at
        # for founder_id=1), which this offline suite has no DB to back.
        require_ai_processing_allowed_for_id: lambda: None,
        # Same reasoning as chat_gate above, for the per-founder request-rate
        # limiter (app/middleware/rate_limit.py): this suite's load/concurrency
        # tests legitimately send far more than 20 messages/minute for a
        # single founder_id, which the limiter (correctly) has no way to tell
        # apart from real abuse. It has its own dedicated tests
        # (test_rate_limit.py).
        message_rate_limit: lambda: None,
        stream_rate_limit: lambda: None,
    }
    app.dependency_overrides.update(overrides)
    yield SimpleNamespace(client=TestClient(app), conv=conv, att=att, sug=sug, founder=founder)
    app.dependency_overrides.clear()


def _new_conversation(client, title="Chat"):
    return client.post(f"{BASE}/conversations", json={"title": title}).json()["conversation_id"]


def _upload(client, cid, filename="report.pdf", content=b"%PDF-1.4 data", ctype="application/pdf"):
    return client.post(f"{BASE}/attachments", data={"conversation_id": cid},
                       files={"file": (filename, content, ctype)})


# --- Part 1: full end-to-end founder journey -------------------------------


def test_full_founder_journey(world):
    c = world.client
    # create -> message -> details -> suggestions -> attachment -> list -> stream
    cid = c.post(f"{BASE}/conversations", json={"title": "Growth"}).json()["conversation_id"]

    msg = c.post(f"{BASE}/message", json={"message": "How do I improve activation?",
                                          "conversation_id": cid}).json()
    assert msg["ok"] and msg["answer"] == ANSWER

    details = c.get(f"{BASE}/conversations/{cid}").json()
    assert details["message_count"] == 2 and details["unread_count"] == 1

    sug = c.get(f"{BASE}/conversations/{cid}/suggestions").json()
    assert sug["returned"] >= 1
    sid = sug["suggestions"][0]["suggestion_id"]

    up = _upload(c, cid, filename="deck.pdf")
    assert up.status_code == 201
    assert c.get(f"{BASE}/conversations/{cid}/attachments").json()["total"] == 1

    stream = c.post(f"{BASE}/stream", json={"message": "and next?", "conversation_id": cid})
    events = re.findall(r"event: (\w+)", stream.text)
    assert events[0] == "start" and events[-1] == "complete"

    # feedback -> archive -> restore
    assert c.post(f"{BASE}/suggestions/{sid}/feedback", json={"feedback": "accepted"}).status_code == 200
    assert c.delete(f"{BASE}/conversations/{cid}").json()["status"] == "archived"
    assert c.post(f"{BASE}/conversations/{cid}/restore").json()["status"] == "active"

    # conversation survived the whole journey (message + stream turns persisted)
    assert c.get(f"{BASE}/conversations/{cid}").json()["message_count"] == 4


# --- Part 2: failure matrix (HTTP-observable) -------------------------------


def test_unknown_founder_404(world):
    world.founder["id"] = 999                                 # not in the context repo
    assert world.client.post(f"{BASE}/message", json={"message": "hi"}).status_code == 404


def test_missing_conversation_404(world):
    assert world.client.get(f"{BASE}/conversations/nope").status_code == 404


def test_conversation_messages_endpoint_returns_the_transcript(world):
    """Regression test for the gap live verification found: GET
    /conversations/{id} only ever returned the header (title, counts,
    timestamps), never the messages, so reopening a past conversation always
    rendered empty in the UI regardless of how many messages it had."""
    c = world.client
    cid = c.post(f"{BASE}/conversations", json={"title": "Growth"}).json()["conversation_id"]
    c.post(f"{BASE}/message", json={"message": "How do I improve activation?",
                                    "conversation_id": cid})

    body = c.get(f"{BASE}/conversations/{cid}/messages").json()
    assert body["conversation_id"] == cid
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert body["messages"][0]["content"] == "How do I improve activation?"
    assert body["messages"][1]["content"] == ANSWER
    # sequence is 0-based and in send order -- what the UI relies on to render
    # the transcript top-to-bottom without re-sorting client-side.
    assert [m["sequence"] for m in body["messages"]] == [0, 1]


def test_conversation_messages_endpoint_ownership_and_404(world):
    c = world.client
    assert c.get(f"{BASE}/conversations/nope/messages").status_code == 404
    # founder 2's request against founder 1's conversation -- must not leak
    # another founder's transcript. owned_conversation reports a foreign
    # resource as NotFound (never disclosed), same as every other
    # conversation-scoped endpoint here -- so 404, not 403.
    cid = _new_conversation(c)
    world.founder["id"] = 2
    try:
        assert c.get(f"{BASE}/conversations/{cid}/messages").status_code == 404
    finally:
        world.founder["id"] = 1


def test_upload_attachment_rejects_foreign_conversation(world):
    """Regression test: POST /attachments previously had no ownership check on
    the client-supplied conversation_id, so an authenticated founder could
    upload an attachment into another founder's conversation. Every sibling
    route in the router already checks ownership before acting; this closes
    the gap the same way -- 404, not 403, matching owned_conversation's
    never-disclose-a-foreign-resource convention."""
    c = world.client
    cid = _new_conversation(c)
    world.founder["id"] = 2
    try:
        resp = _upload(c, cid)
        assert resp.status_code == 404
    finally:
        world.founder["id"] = 1
    # and the attachment must not have been written against founder 1's
    # conversation despite the rejected request
    assert c.get(f"{BASE}/conversations/{cid}/attachments").json()["total"] == 0


def test_chat_in_archived_conversation_409(world):
    cid = _new_conversation(world.client)
    world.client.delete(f"{BASE}/conversations/{cid}")        # archive
    r = world.client.post(f"{BASE}/message", json={"message": "hi", "conversation_id": cid})
    assert r.status_code == 409


def test_failure_matrix_status_codes(world):
    c = world.client
    cid = _new_conversation(c)
    _upload(c, cid, content=b"dupe")
    checks = {
        "missing_conversation": (c.get(f"{BASE}/conversations/x").status_code, 404),
        "unsupported_mime": (_upload(c, cid, filename="x.zip", content=b"PK", ctype="application/zip").status_code, 415),
        "duplicate_attachment": (_upload(c, cid, filename="y.pdf", content=b"dupe").status_code, 409),
        "missing_attachment": (c.get(f"{BASE}/attachments/nope").status_code, 404),
        "unknown_suggestion_feedback": (c.post(f"{BASE}/suggestions/z/feedback", json={"feedback": "ignored"}).status_code, 404),
        "invalid_feedback_value": (c.post(f"{BASE}/suggestions/z/feedback", json={"feedback": "bad"}).status_code, 422),
        "missing_message_field": (c.post(f"{BASE}/message", json={}).status_code, 422),
    }
    assert all(actual == expected for actual, expected in checks.values()), checks


def test_provider_failure_returns_structured_ok_false(world):
    # Fail-closed: a provider timeout yields ok=False (200 with structured error),
    # not a 500, and no assistant message is persisted.
    conv = build_conversation_service()
    window = ContextWindowBuilder(conversation_service=conv,
                                  memory=build_memory_service(InMemoryMemoryRepository()),
                                  retrieval=_retrieval(), knowledge_graph=_kg())
    failing = ChatExecutionService(
        context_builder=AllyContextBuilder(WorldContextRepo()), conversation_service=conv,
        context_window_builder=window, prompt_manager=default_grounded_prompt_manager(),
        execution=build_execution_service({"mock": MockLLMProvider(timeout_times=99)}, max_retries=1))
    app.dependency_overrides[deps.get_chat_service] = lambda: failing
    app.dependency_overrides[deps.get_conversation_service] = lambda: conv

    r = world.client.post(f"{BASE}/message", json={"message": "hi"})
    body = r.json()
    assert r.status_code == 200 and body["ok"] is False and body["answer"] == ""
    cid = body["conversation_id"]
    assert [m.role.value for m in conv.get_history(cid)] == ["user"]   # assistant NOT persisted


def test_malformed_links_do_not_break_suggestions(world):
    c = world.client
    cid = _new_conversation(c)
    c.post(f"{BASE}/message", json={
        "message": "see http:// broken and https://github.com/goxl/ally", "conversation_id": cid})
    r = c.get(f"{BASE}/conversations/{cid}/suggestions")
    assert r.status_code == 200                               # malformed URL ignored, no crash


# --- Part 4: concurrency ----------------------------------------------------


def test_50_concurrent_conversations(world):
    def create(i):
        return TestClient(app).post(f"{BASE}/conversations", json={"title": f"c{i}"}).status_code

    with ThreadPoolExecutor(max_workers=16) as pool:
        codes = list(pool.map(create, range(50)))
    assert all(code == 201 for code in codes)
    assert world.client.get(f"{BASE}/conversations").json()["total"] == 50    # no lost writes


def test_100_concurrent_messages(world):
    def send(i):
        return TestClient(app).post(f"{BASE}/message", json={"message": f"q{i}"}).json()["ok"]

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(send, range(100)))
    assert all(results)                                       # every request answered ok


def test_concurrent_attachment_uploads(world):
    cid = _new_conversation(world.client)

    def up(i):
        return _upload(TestClient(app), cid, filename=f"f{i}.txt",
                       content=f"data-{i}".encode(), ctype="text/plain").status_code

    with ThreadPoolExecutor(max_workers=16) as pool:
        codes = list(pool.map(up, range(30)))
    assert all(code == 201 for code in codes)
    assert world.client.get(f"{BASE}/conversations/{cid}/attachments").json()["total"] == 30


def test_concurrent_suggestion_generation(world):
    world.client.post(f"{BASE}/message", json={"message": "hi"})
    cid = world.client.get(f"{BASE}/conversations").json()["conversations"][0]["conversation_id"]

    def gen(_):
        return TestClient(app).get(f"{BASE}/conversations/{cid}/suggestions").status_code

    with ThreadPoolExecutor(max_workers=16) as pool:
        assert all(code == 200 for code in pool.map(gen, range(20)))


# --- Part 5: load simulation ------------------------------------------------


def _session(client, i):
    """One realistic founder session: create -> turns -> attachment -> suggestions
    -> stream -> archive -> restore. Returns True on full success."""
    try:
        cid = client.post(f"{BASE}/conversations", json={"title": f"s{i}"}).json()["conversation_id"]
        for t in range(6):
            if not client.post(f"{BASE}/message", json={"message": f"turn {t}", "conversation_id": cid}).json()["ok"]:
                return False
        _upload(client, cid, filename=f"s{i}.pdf", content=f"deck-{i}".encode())
        if client.get(f"{BASE}/conversations/{cid}/suggestions").status_code != 200:
            return False
        client.post(f"{BASE}/stream", json={"message": "wrap up", "conversation_id": cid})
        client.delete(f"{BASE}/conversations/{cid}")
        return client.post(f"{BASE}/conversations/{cid}/restore").json()["status"] == "active"
    except Exception:
        return False


def test_load_20_founder_sessions(world):
    results = [_session(world.client, i) for i in range(20)]
    assert sum(results) == 20                                 # 100% success rate


def test_load_concurrent_sessions(world):
    def run(i):
        return _session(TestClient(app), i)

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(run, range(24)))
    assert sum(results) == 24                                 # 100% under concurrency


# --- Part 6: API contract ---------------------------------------------------


def test_openapi_documents_every_chat_endpoint(world):
    schema = world.client.get("/openapi.json").json()
    paths = {p for p in schema["paths"] if p.startswith("/api/v1/chat/")}
    # 12, not 11: /conversations/{id}/messages was added -- GET /conversations/{id}
    # only ever returned the header (title, counts, timestamps), never the
    # transcript, so reopening a past conversation always rendered empty.
    # 13, not 12: /attachments/{id}/link was added -- an upload happens before
    # the message exists, so the two can only be associated afterwards.
    assert len(paths) == 13
    # every operation documents a response model (no undocumented responses)
    for path, ops in schema["paths"].items():
        if path.startswith("/api/v1/chat/"):
            for method, spec in ops.items():
                assert spec.get("responses"), (path, method)


def test_error_shape_is_consistent(world):
    for r in (world.client.get(f"{BASE}/conversations/nope"),
              world.client.post(f"{BASE}/suggestions/x/feedback", json={"feedback": "ignored"})):
        assert r.status_code == 404 and set(r.json()) >= {"error", "message", "request_id"}


def test_response_schema_keys(world):
    cid = _new_conversation(world.client)
    conv = world.client.get(f"{BASE}/conversations/{cid}").json()
    assert set(conv) >= {"conversation_id", "founder_id", "title", "status", "message_count",
                         "unread_count", "total_tokens", "created_at", "updated_at"}


def test_sse_content_type_and_frames(world):
    r = world.client.post(f"{BASE}/stream", json={"message": "hi"})
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.text.count("data: ") == r.text.count("event: ")   # every event has a data frame


# --- performance smoke (bounded; full numbers in the standalone measurement) --


def test_message_latency_bounded(world):
    latencies = []
    for _ in range(30):
        start = time.perf_counter()
        assert world.client.post(f"{BASE}/message", json={"message": "hi"}).status_code == 200
        latencies.append((time.perf_counter() - start) * 1000)
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    assert p95 < 500, f"p95 message latency too high: {p95:.1f}ms"   # generous offline bound
