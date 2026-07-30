"""API tests for the Chat HTTP layer (Phase 6, Milestone 6).

Transport tests over the real FastAPI app via TestClient. Services are injected with
offline-wired doubles through dependency_overrides (fake M1 context repo + mock LLM),
so no DB or auth backend is needed. Business logic is covered by the ai_chat suites.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from itertools import count
import json

import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.main import app
from app.api.v1.chat import dependencies as deps
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
        self._founders = {
            1: dict(full_name="Asha", stage_id=5, industry_mapped_id=3),
            2: dict(full_name="Bo", stage_id=6, industry_mapped_id=4),
        }

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
        execution=build_execution_service({"mock": MockLLMProvider(content=VALID_BODY)}))
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
    }
    app.dependency_overrides.update(overrides)
    yield SimpleNamespace(client=TestClient(app), conv=conv, att=att, sug=sug, founder=founder)
    for key in overrides:
        app.dependency_overrides.pop(key, None)


def _new_conversation(client, title="Chat"):
    return client.post(f"{BASE}/conversations", json={"title": title}).json()["conversation_id"]


# --- messaging --------------------------------------------------------------


def test_message_endpoint(world):
    r = world.client.post(f"{BASE}/message", json={"message": "How do I improve activation?"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["answer"] == ANSWER and body["conversation_id"]
    assert body["metrics"]["retrieval_hits"] == 1


def test_message_validation_missing_field(world):
    assert world.client.post(f"{BASE}/message", json={}).status_code == 422


def test_deterministic_message_responses(world):
    a = world.client.post(f"{BASE}/message", json={"message": "hi"}).json()
    b = world.client.post(f"{BASE}/message", json={"message": "hi"}).json()
    assert a["answer"] == b["answer"] == ANSWER


# --- SSE --------------------------------------------------------------------


def test_stream_content_type_is_event_stream(world):
    r = world.client.post(f"{BASE}/stream", json={"message": "hi"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")


def test_sse_event_ordering(world):
    r = world.client.post(f"{BASE}/stream", json={"message": "hi", "max_chunk_size": 8})
    events = re.findall(r"event: (\w+)", r.text)
    assert events[0] == "start" and events[1] == "message_received"
    for a, b in [("context_ready", "prompt_ready"), ("prompt_ready", "ai_started"),
                 ("ai_started", "token"), ("ai_finished", "message_persisted"),
                 ("message_persisted", "complete")]:
        assert events.index(a) < events.index(b)
    assert events[-1] == "complete"
    assert events.count("token") >= 1


# --- conversations ----------------------------------------------------------


def test_create_and_list_conversation(world):
    created = world.client.post(f"{BASE}/conversations", json={"title": "Growth"})
    assert created.status_code == 201 and created.json()["title"] == "Growth"
    listed = world.client.get(f"{BASE}/conversations").json()
    assert listed["total"] == 1 and listed["conversations"][0]["title"] == "Growth"


def test_get_conversation_details(world):
    cid = _new_conversation(world.client)
    r = world.client.get(f"{BASE}/conversations/{cid}")
    assert r.status_code == 200 and r.json()["conversation_id"] == cid


def test_get_unknown_conversation_404(world):
    r = world.client.get(f"{BASE}/conversations/does-not-exist")
    assert r.status_code == 404
    assert set(r.json()) >= {"error", "message", "request_id"}


def test_archive_and_restore_conversation(world):
    cid = _new_conversation(world.client)
    assert world.client.delete(f"{BASE}/conversations/{cid}").json()["status"] == "archived"
    assert world.client.get(f"{BASE}/conversations").json()["total"] == 0
    assert world.client.post(f"{BASE}/conversations/{cid}/restore").json()["status"] == "active"


def test_foreign_conversation_hidden(world):
    cid = _new_conversation(world.client)
    world.founder["id"] = 2                                   # switch authenticated founder
    assert world.client.get(f"{BASE}/conversations/{cid}").status_code == 404


# --- attachments ------------------------------------------------------------


def _upload(client, cid, filename="report.pdf", content=b"%PDF-1.4 data", ctype="application/pdf"):
    return client.post(f"{BASE}/attachments", data={"conversation_id": cid},
                       files={"file": (filename, content, ctype)})


def test_upload_and_get_attachment(world):
    cid = _new_conversation(world.client)
    up = _upload(world.client, cid)
    assert up.status_code == 201
    aid = up.json()["attachment_id"]
    assert up.json()["mime_type"] == "application/pdf" and up.json()["attachment_type"] == "document"
    got = world.client.get(f"{BASE}/attachments/{aid}")
    assert got.status_code == 200 and got.json()["checksum"]


def test_list_conversation_attachments(world):
    cid = _new_conversation(world.client)
    _upload(world.client, cid, filename="a.pdf")
    _upload(world.client, cid, filename="b.png", content=b"img", ctype="image/png")
    listed = world.client.get(f"{BASE}/conversations/{cid}/attachments").json()
    assert listed["total"] == 2


def test_archive_and_restore_attachment(world):
    cid = _new_conversation(world.client)
    aid = _upload(world.client, cid).json()["attachment_id"]
    assert world.client.delete(f"{BASE}/attachments/{aid}").json()["status"] == "archived"
    assert world.client.post(f"{BASE}/attachments/{aid}/restore").json()["status"] == "active"


def test_unsupported_attachment_415(world):
    cid = _new_conversation(world.client)
    r = _upload(world.client, cid, filename="malware.zip", content=b"PK", ctype="application/zip")
    assert r.status_code == 415


def test_duplicate_attachment_409(world):
    cid = _new_conversation(world.client)
    _upload(world.client, cid, content=b"same")
    r = _upload(world.client, cid, filename="copy.pdf", content=b"same")
    assert r.status_code == 409


# --- suggestions ------------------------------------------------------------


def test_get_suggestions(world):
    world.client.post(f"{BASE}/message", json={"message": "How do I improve activation?"})
    cid = world.client.get(f"{BASE}/conversations").json()["conversations"][0]["conversation_id"]
    r = world.client.get(f"{BASE}/conversations/{cid}/suggestions")
    assert r.status_code == 200 and r.json()["returned"] >= 1


def test_suggestion_feedback(world):
    world.client.post(f"{BASE}/message", json={"message": "hi"})
    cid = world.client.get(f"{BASE}/conversations").json()["conversations"][0]["conversation_id"]
    sid = world.client.get(f"{BASE}/conversations/{cid}/suggestions").json()["suggestions"][0]["suggestion_id"]
    r = world.client.post(f"{BASE}/suggestions/{sid}/feedback", json={"feedback": "accepted"})
    assert r.status_code == 200 and r.json()["feedback_type"] == "accepted"


def test_feedback_on_unknown_suggestion_404(world):
    r = world.client.post(f"{BASE}/suggestions/nope/feedback", json={"feedback": "dismissed"})
    assert r.status_code == 404


def test_feedback_invalid_value_422(world):
    r = world.client.post(f"{BASE}/suggestions/x/feedback", json={"feedback": "maybe"})
    assert r.status_code == 422


# --- concurrency ------------------------------------------------------------


def test_concurrent_requests(world):
    def create(i):
        client = TestClient(app)                             # per-thread client, shared app+overrides
        return client.post(f"{BASE}/conversations", json={"title": f"c{i}"}).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(create, range(20)))
    assert all(code == 201 for code in codes)
    assert world.client.get(f"{BASE}/conversations").json()["total"] == 20
