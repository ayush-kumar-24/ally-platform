"""Regression tests for GET /api/v1/health.

This is the endpoint DEPLOY_AWS.md tells App Runner to actually poll for
instance health/traffic routing -- unlike bare `/`, which always returns 200
unconditionally and checks nothing. The behavior that matters here is the
HTTP status code: a health-check integration commonly looks only at that,
not the JSON body, so "degraded" in a 200 response would be invisible to it.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_connected_with_200():
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["database"] == "connected"


def test_health_reports_503_when_db_unreachable(monkeypatch):
    from app.api.v1 import router as router_module

    class _BrokenEngine:
        def connect(self):
            raise RuntimeError("simulated DB outage")

    monkeypatch.setattr(router_module, "engine", _BrokenEngine())

    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unreachable"


def test_root_endpoint_is_unconditional_liveness_only(monkeypatch):
    """`/` intentionally does NOT check the DB -- it exists as a bare liveness
    ping, not a readiness check. Infrastructure health checks must point at
    /api/v1/health instead (see DEPLOY_AWS.md)."""
    from app.api.v1 import router as router_module

    class _BrokenEngine:
        def connect(self):
            raise RuntimeError("simulated DB outage")

    monkeypatch.setattr(router_module, "engine", _BrokenEngine())
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
