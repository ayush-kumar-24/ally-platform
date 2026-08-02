"""API tests for the Consents endpoints. dependency_overrides inject an in-memory
service + a fake founder; no DB/auth backend."""

from datetime import datetime, timedelta, timezone
from itertools import count
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.consents.dependencies import get_consent_service, get_current_founder_id
from app.consents import build_consent_service
from app.main import app

BASE = "/api/v1/consents"
T0 = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
BODY = {"terms_version": "1.0", "privacy_version": "1.0", "agree_terms": True}


class StepClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def __call__(self):
        v = self._now
        self._now += self._step
        return v


@pytest.fixture
def client():
    c = count(1)
    service = build_consent_service(clock=StepClock(), id_factory=lambda: f"c-{next(c)}")
    founder = {"id": 1}
    app.dependency_overrides[get_current_founder_id] = lambda: founder["id"]
    app.dependency_overrides[get_consent_service] = lambda: service
    yield SimpleNamespace(http=TestClient(app), founder=founder, service=service)
    for dep in (get_current_founder_id, get_consent_service):
        app.dependency_overrides.pop(dep, None)


# --- POST /consents ---------------------------------------------------------


def test_record_consent_201(client):
    r = client.http.post(BASE, json={**BODY, "agree_diagnosis": True})
    assert r.status_code == 201
    body = r.json()
    assert body["agree_terms"] is True and body["agree_diagnosis"] is True
    assert body["terms_version"] == "1.0" and body["founder_id"] == 1
    assert body["consented_at"].startswith("2026-08-02T12:00:00")


def test_diagnosis_opt_in_defaults_false(client):
    assert client.http.post(BASE, json=BODY).json()["agree_diagnosis"] is False


def test_duplicate_post_returns_200_not_duplicate(client):
    first = client.http.post(BASE, json=BODY)
    second = client.http.post(BASE, json=BODY)
    assert first.status_code == 201 and second.status_code == 200
    assert second.json()["consent_id"] == first.json()["consent_id"]
    assert client.http.get(BASE).json()["total"] == 1


def test_changed_consent_appends(client):
    client.http.post(BASE, json={**BODY, "agree_diagnosis": True})
    r = client.http.post(BASE, json={**BODY, "agree_diagnosis": False})
    assert r.status_code == 201
    assert client.http.get(BASE).json()["total"] == 2


def test_terms_refused_422(client):
    r = client.http.post(BASE, json={**BODY, "agree_terms": False})
    assert r.status_code == 422
    assert client.http.get(BASE).json()["has_consented"] is False


def test_invalid_version_422(client):
    assert client.http.post(BASE, json={**BODY, "terms_version": "latest"}).status_code == 422


def test_missing_field_422(client):
    assert client.http.post(BASE, json={"terms_version": "1.0", "agree_terms": True}).status_code == 422


def test_unknown_field_rejected(client):
    """extra='forbid' -- in particular a client-supplied consented_at is refused,
    since the server is the only trustworthy source of that timestamp."""
    r = client.http.post(BASE, json={**BODY, "consented_at": "2020-01-01T00:00:00Z"})
    assert r.status_code == 422


# --- GET /consents ----------------------------------------------------------


def test_get_before_any_consent(client):
    body = client.http.get(BASE).json()
    assert body["has_consented"] is False
    assert body["needs_reconsent"] is True
    assert body["current"] is None and body["history"] == [] and body["total"] == 0


def test_get_returns_current_and_history_newest_first(client):
    client.http.post(BASE, json={**BODY, "agree_diagnosis": True})
    client.http.post(BASE, json={**BODY, "agree_diagnosis": False})
    body = client.http.get(BASE).json()
    assert body["has_consented"] is True and body["needs_reconsent"] is False
    assert body["current"]["agree_diagnosis"] is False
    assert [h["agree_diagnosis"] for h in body["history"]] == [False, True]
    assert body["current_terms_version"] == "1.0"


def test_stale_version_needs_reconsent(client):
    client.http.post(BASE, json={"terms_version": "0.9", "privacy_version": "1.0", "agree_terms": True})
    body = client.http.get(BASE).json()
    assert body["has_consented"] is True and body["needs_reconsent"] is True


# --- isolation --------------------------------------------------------------


def test_founder_isolation(client):
    client.http.post(BASE, json=BODY)
    client.founder["id"] = 2
    body = client.http.get(BASE).json()
    assert body["has_consented"] is False and body["total"] == 0
