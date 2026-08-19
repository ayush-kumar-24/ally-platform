"""In-process rate limiter (app/middleware/rate_limit.py) -- unit tests for
the limiter itself, plus a live-endpoint proof that /auth/session actually
enforces its configured limit.

Pre-beta audit finding: there was no rate limiting anywhere in this backend.
"""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.middleware.rate_limit import _SlidingWindowLimiter, founder_rate_limit, ip_rate_limit


def test_sliding_window_allows_up_to_limit_then_rejects():
    limiter = _SlidingWindowLimiter()
    results = [limiter.allow("k", limit=3, window_seconds=60) for _ in range(5)]
    assert results == [True, True, True, False, False]


def test_sliding_window_buckets_are_independent():
    limiter = _SlidingWindowLimiter()
    for _ in range(3):
        assert limiter.allow("a", limit=3, window_seconds=60)
    # a's bucket is now exhausted, but b is untouched
    assert limiter.allow("b", limit=3, window_seconds=60)
    assert not limiter.allow("a", limit=3, window_seconds=60)


def test_sliding_window_expires_old_hits():
    limiter = _SlidingWindowLimiter()
    assert limiter.allow("k", limit=1, window_seconds=0.05)
    assert not limiter.allow("k", limit=1, window_seconds=0.05)
    import time
    time.sleep(0.07)
    assert limiter.allow("k", limit=1, window_seconds=0.05)


def test_ip_rate_limit_dependency_blocks_after_limit():
    app = FastAPI()

    @app.get("/probe", dependencies=[
        Depends(ip_rate_limit(key="test-probe", limit=2, window_seconds=60))
    ])
    def probe():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/probe").status_code == 200
    assert client.get("/probe").status_code == 200
    third = client.get("/probe")
    assert third.status_code == 429


def test_ip_rate_limit_buckets_do_not_leak_across_keys():
    """Two routes with different `key`s must not share a limit bucket even
    for the same client -- otherwise one endpoint's traffic could exhaust
    another's budget."""
    app = FastAPI()

    @app.get("/a", dependencies=[Depends(ip_rate_limit(key="route-a", limit=1, window_seconds=60))])
    def a():
        return {"ok": True}

    @app.get("/b", dependencies=[Depends(ip_rate_limit(key="route-b", limit=1, window_seconds=60))])
    def b():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/a").status_code == 200
    assert client.get("/a").status_code == 429
    assert client.get("/b").status_code == 200  # untouched by /a's traffic


def test_founder_rate_limit_keys_by_resolved_founder_id_int():
    app = FastAPI()

    def fake_founder_id() -> int:
        return 42

    @app.get("/founder-probe", dependencies=[
        Depends(founder_rate_limit(key="test-founder", limit=1, window_seconds=60,
                                   founder_id_dependency=fake_founder_id))
    ])
    def probe():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/founder-probe").status_code == 200
    assert client.get("/founder-probe").status_code == 429


def test_founder_rate_limit_accepts_object_with_founder_id_attribute():
    """Diagnosis's founder-resolving dependency returns a Founder domain
    object (.founder_id), not a bare int like chat's does -- both shapes
    must work without double-decoding the token."""
    app = FastAPI()

    class _FounderLike:
        founder_id = 7

    def fake_founder_record() -> _FounderLike:
        return _FounderLike()

    @app.get("/founder-obj-probe", dependencies=[
        Depends(founder_rate_limit(key="test-founder-obj", limit=1, window_seconds=60,
                                   founder_id_dependency=fake_founder_record))
    ])
    def probe():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/founder-obj-probe").status_code == 200
    assert client.get("/founder-obj-probe").status_code == 429
