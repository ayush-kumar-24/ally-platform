"""`loads_json` parses what models actually return, not what they promise.

Four reasoning engines called `json.loads(response.text)` directly. That works
until a reply arrives fenced or with a sentence in front of it, which is what
happened to the recommendation engine on RC-519 in production: JSONDecodeError,
a fail-open warning, and a root cause shipped with no recommendation.
"""

import json

import pytest

from app.services.llm.text import loads_json


def test_bare_object():
    assert loads_json('{"a": 1}') == {"a": 1}


def test_json_code_fence():
    """The exact shape that broke RC-519."""
    assert loads_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_bare_code_fence():
    assert loads_json('```\n{"a": 1}\n```') == {"a": 1}


def test_prose_before_the_object():
    assert loads_json('Here is the recommendation:\n{"a": 1}') == {"a": 1}


def test_prose_on_both_sides():
    assert loads_json('Sure!\n{"a": 1}\nLet me know if you need more.') == {"a": 1}


def test_leading_whitespace_and_newlines():
    assert loads_json('\n\n  {"a": 1}  \n') == {"a": 1}


def test_nested_braces_keep_the_outermost_object():
    text = '```json\n{"a": {"b": [1, 2]}, "c": "}"}\n```'
    assert loads_json(text) == json.loads('{"a": {"b": [1, 2]}, "c": "}"}')


def test_multiline_realistic_reply():
    reply = (
        "I'll suggest three actions for this root cause.\n\n"
        "```json\n"
        '{"actions": [{"title": "Call five labs", "why": "demand is unproven"}],\n'
        ' "confidence": 0.7}\n'
        "```\n\n"
        "These are ordered by urgency."
    )
    assert loads_json(reply)["confidence"] == 0.7


def test_no_object_still_raises_json_error():
    """Passed through untouched, so the caller's own guard fires and the
    message still reports what actually came back."""
    with pytest.raises(json.JSONDecodeError):
        loads_json("I'm sorry, I can't help with that.")


def test_empty_string_still_raises_json_error():
    with pytest.raises(json.JSONDecodeError):
        loads_json("")


def test_the_exact_production_failure_is_fixed():
    """Reproduces the RC-519 traceback: `json.loads` on a fenced reply raises
    'Expecting value: line 1 column 1 (char 0)'; loads_json does not."""
    fenced = '```json\n{"actions": [], "note": "nothing to add"}\n```'

    with pytest.raises(json.JSONDecodeError) as exc:
        json.loads(fenced)
    assert "Expecting value: line 1 column 1" in str(exc.value)

    assert loads_json(fenced) == {"actions": [], "note": "nothing to add"}


@pytest.mark.parametrize("module_name", [
    "recommendation_llm", "stage_detection_llm", "archetype_llm", "action_plan_llm",
])
def test_no_engine_parses_model_json_naively(module_name):
    """All four engines share the helper. A new one copying the old line back
    in should turn this red rather than wait for a fenced reply in production."""
    from pathlib import Path

    import app.api.v1.reasoning.engines as engines

    source = (Path(engines.__file__).parent / f"{module_name}.py").read_text(
        encoding="utf-8")
    assert "json.loads(response.text)" not in source
    assert "loads_json(response.text)" in source
