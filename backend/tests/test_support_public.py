"""The anonymous help bot, and the limits that make it safe to expose.

This endpoint is open to the internet and costs money per call, so the tests
that matter are the ones about what it REFUSES. The bot's answers are covered
elsewhere; nothing here is about answer quality.

Four things must hold, and each has cost someone somewhere real money when it
did not:

  * no account needed -- the whole point is the founder who cannot sign in
  * one visitor cannot hammer it
  * a distributed script cannot either, which per-IP limits alone cannot stop
  * a refusal still helps the person, because they may be locked out

The model is stubbed throughout: none of this should reach a provider.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.support import public as pub
from app.main import app

URL = "/api/v1/support/public/ask"


@pytest.fixture
def client():
    svc = MagicMock()
    svc.answer = AsyncMock(return_value=MagicMock(
        answer="Here is how to sign in.", answered=True, escalate=False,
        links=(), sources=()))
    app.dependency_overrides[pub.get_public_support_service] = lambda: svc
    pub._by_ip.clear()
    pub._global.clear()
    yield TestClient(app)
    app.dependency_overrides.pop(pub.get_public_support_service, None)
    pub._by_ip.clear()
    pub._global.clear()


def _ask(c, ip="203.0.113.1", q="how do I sign in?"):
    return c.post(URL, json={"question": q}, headers={"X-Forwarded-For": ip})


def test_no_account_is_needed(client):
    """The reason this endpoint exists: a locked-out founder has no session."""
    r = _ask(client)
    assert r.status_code == 200
    assert r.json()["answered"] is True


def test_one_visitor_cannot_hammer_it(client):
    answered = [_ask(client).json()["answered"] for _ in range(pub._IP_LIMIT + 3)]
    assert sum(answered) == pub._IP_LIMIT


def test_the_limit_is_per_visitor_not_global(client):
    """One person exhausting their allowance must not lock out everyone else."""
    for _ in range(pub._IP_LIMIT + 2):
        _ask(client, ip="203.0.113.1")
    assert _ask(client, ip="198.51.100.7").json()["answered"] is True


def test_a_distributed_script_is_capped(client):
    """THE ONE THAT PROTECTS THE BILL.

    Every request here comes from a different address, so the per-IP limit
    never fires -- exactly what a botnet or a rotating proxy looks like. The
    global hourly ceiling is the only thing standing between that and an
    unbounded model spend.
    """
    blocked = 0
    for i in range(pub._GLOBAL_LIMIT + 20):
        if not _ask(client, ip=f"10.0.{i // 256}.{i % 256}").json()["answered"]:
            blocked += 1
    assert blocked == 20


def test_a_refused_visitor_is_still_helped(client):
    """They may be the founder who cannot get in. A 429 would be the second
    door shut in their face, so they get 200 and a real route to a person."""
    for _ in range(pub._IP_LIMIT):
        _ask(client)
    body = _ask(client).json()
    assert body["escalate"] is True
    assert "info@goxl.in" in body["answer"]


def test_a_long_prompt_is_refused(client):
    """A sign-in question is a sentence. Anything near the authenticated
    route's 2,000-character allowance is somebody using us as a free model."""
    r = client.post(URL, json={"question": "x" * (pub._MAX_QUESTION_CHARS + 1)})
    assert r.status_code == 422


def test_an_empty_question_is_refused(client):
    assert client.post(URL, json={"question": "   "}).status_code in (200, 422)


def test_no_sources_or_links_are_exposed(client):
    """The anonymous response is deliberately thinner. Which help entries exist
    is not something a stranger probing the endpoint needs to learn."""
    body = _ask(client).json()
    assert set(body) == {"answer", "answered", "escalate"}
