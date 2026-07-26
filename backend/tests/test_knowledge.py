"""Knowledge-graph traversal, read-only over the seeded reference data (dev mode)."""

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.main import app

logging.disable(logging.CRITICAL)
BASE = "/api/v1/knowledge"


@pytest.fixture
def client():
    settings.AUTH_PROVIDER = "dev"  # dev-mode auth: no token needed, no founder row
    return TestClient(app)


@pytest.fixture
def sample_ids():
    with engine.connect() as conn:
        pid = conn.execute(text(
            "select problem_id from problems order by problem_id limit 1")).scalar()
        rcid = conn.execute(text(
            "select root_cause_id from root_causes where problem_id is not null "
            "order by root_cause_id limit 1")).scalar()
    return pid, rcid


def test_list_problems(client):
    r = client.get(f"{BASE}/problems?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert len(body) > 0
    assert "problem_name" in body[0]


def test_problem_detail_has_graph_edges(client, sample_ids):
    pid, _ = sample_ids
    r = client.get(f"{BASE}/problems/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["problem_id"] == pid
    assert "root_causes" in body and "interventions" in body  # one hop out


def test_problem_not_found(client):
    assert client.get(f"{BASE}/problems/999999999").status_code == 404


def test_root_cause_detail_has_weights(client, sample_ids):
    _, rcid = sample_ids
    r = client.get(f"{BASE}/root-causes/{rcid}")
    assert r.status_code == 200
    body = r.json()
    assert body["root_cause_id"] == rcid
    assert "stage_weights" in body


def test_root_cause_not_found(client):
    assert client.get(f"{BASE}/root-causes/999999999").status_code == 404
