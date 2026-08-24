"""A 422 must reach the founder as a sentence, and must not echo their input.

validation_exception_handler used to send `str(exc.errors())` as `message` --
the repr of Pydantic's error list. services/api.js reads `data.message` first,
so that repr was what the founder saw. Captured live on goxlally.ai, in a toast
on Plan Your Day:

    [{'type': 'string_too_long', 'loc': ('body', 'title'), 'msg': 'String
    should have at most 200 characters', 'input': 'I want to spend the whole
    day working through the pricing conversation problem with ...',
    'ctx': {'max_length': 200}}]

The `input` key is the part that makes this more than cosmetic: it holds the
value that failed, so every 422 returned the submitted value to the client.
Harmless for a task title; not harmless for a password or a token, and nothing
in the old line distinguished them.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.middleware.error_handler import (
    _field_name,
    _validation_message,
    validation_exception_handler,
)


class _Body(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@pytest.fixture
def client() -> TestClient:
    """A minimal app wired to the real handler -- the assertions are about the
    RESPONSE, so it has to go through FastAPI's own validation."""
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    @app.post("/things")
    def create(body: _Body):  # pragma: no cover - never reached in these tests
        return {"ok": True}

    @app.post("/secrets")
    def secret(body: _Secret):  # pragma: no cover - never reached
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


class _Secret(BaseModel):
    password: str = Field(min_length=12)


# --- the response the founder actually sees ---------------------------------

def test_the_message_is_a_sentence_not_a_python_repr(client):
    """THE REGRESSION."""
    body = {"title": "x" * 201}
    message = client.post("/things", json=body).json()["message"]

    assert message == "title: String should have at most 200 characters"
    for token in ("{", "}", "[", "]", "'type'", "'loc'", "'ctx'", "string_too_long"):
        assert token not in message, f"leaked Python structure: {token!r}"


def test_the_submitted_value_is_never_echoed_back(client):
    """`input` carried the failing value into the response body."""
    secret = "hunter2-but-longer-and-obviously-not-a-real-password"
    response = client.post("/things", json={"title": secret + "x" * 201})

    assert secret not in response.text


def test_a_failing_password_field_does_not_return_the_password(client):
    """The reason this is a security fix and not a copy fix."""
    password = "short-pw"
    response = client.post("/secrets", json={"password": password})

    assert response.status_code == 422
    assert password not in response.text


def test_the_status_and_envelope_are_unchanged(client):
    """Only `message` changes shape -- clients keying off the rest keep working."""
    response = client.post("/things", json={"title": ""})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "ValidationError"
    assert isinstance(payload["message"], str) and payload["message"]
    assert payload["request_id"]


def test_a_missing_field_names_the_field(client):
    message = client.post("/things", json={}).json()["message"]
    assert message.startswith("title: ")


# --- message construction -----------------------------------------------------

def test_the_wrapper_segment_is_not_shown_to_the_founder():
    """"body -> title" is FastAPI's plumbing, not a field name."""
    assert _field_name(("body", "title")) == "title"


def test_a_list_index_does_not_become_the_field_name():
    """loc can interleave integers; the founder needs the field, not the row."""
    assert _field_name(("body", 0, "tasks", 2, "due_time")) == "due_time"


def test_a_loc_with_nothing_nameable_falls_back_to_the_bare_message():
    assert _field_name(("body",)) is None
    assert _validation_message([{"loc": ("body",), "msg": "Invalid payload"}]) == "Invalid payload"


def test_an_empty_or_unrecognisable_error_list_still_gives_a_usable_sentence():
    """Never crash the handler on a shape we did not anticipate -- a 422 that
    500s is strictly worse than a vague 422."""
    fallback = "Some of that wasn't valid — please check and try again."
    assert _validation_message([]) == fallback
    assert _validation_message(["not a dict"]) == fallback
    assert _validation_message([{"loc": ("body", "title")}]) == fallback
    assert _validation_message([{"msg": "", "loc": ()}]) == fallback
