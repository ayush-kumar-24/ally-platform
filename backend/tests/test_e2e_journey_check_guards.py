"""The journey check must fail when a phase serves nothing.

A run against a cleaned founder reported:

    Founder DNA:      0 question(s) answered
    Current Problem:  0 question(s) answered
    Diagnosis:       14 question(s) answered

and then printed a full report summary as though the journey had happened.
Two defects met: cleanup left founder_dna_completed_at / current_problem_
completed_at set on the founders row while deleting the answers, so both
phases answered "already complete" and served no question -- and `_walk`'s
`while q:` loop simply never entered, so it returned True.
"""

import pytest

from scripts.e2e_journey_check import (
    _JOURNEY_STAMPS,
    _clear_journey_stamps,
    _walk,
)


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload, self.status_code = payload, status_code
        self.text = str(payload)

    def json(self):
        return self._payload


class _Client:
    """Serves a scripted sequence of question payloads."""

    def __init__(self, start_payload, answer_payloads=()):
        self.start_payload = start_payload
        self.answer_payloads = list(answer_payloads)
        self.answers_posted = 0

    def post(self, path, json=None):
        if json is None:
            return _Response(self.start_payload, 201)
        self.answers_posted += 1
        if not self.answer_payloads:
            return _Response({"is_complete": True, "next_question": None})
        return _Response(self.answer_payloads.pop(0))


def _q(qid):
    return {"founder_dna_question_id": qid, "question_text": f"Q{qid}"}


def test_walk_fails_when_the_phase_reports_itself_already_complete():
    """`question: null` means complete -- which proves nothing ran."""
    client = _Client({"question": None, "progress": {"is_complete": True}})
    out = []
    ok = _walk(client, "/start", "/answer", "founder_dna_question_id", "Founder DNA", out)
    assert ok is False
    assert out == []
    assert client.answers_posted == 0


def test_walk_reports_the_cleanup_remedy_when_it_fails(capsys):
    client = _Client({"question": None})
    _walk(client, "/start", "/answer", "founder_dna_question_id", "Founder DNA", [])
    printed = capsys.readouterr().out
    assert "FAIL" in printed
    assert "already complete" in printed
    assert "--cleanup-founder-id" in printed


def test_walk_still_succeeds_on_a_real_phase():
    client = _Client(
        {"question": _q(1)},
        [{"next_question": _q(2)}, {"is_complete": True, "next_question": None}],
    )
    out = []
    ok = _walk(client, "/start", "/answer", "founder_dna_question_id", "Founder DNA", out)
    assert ok is True
    assert len(out) == 2


def test_walk_fails_when_a_start_status_is_wrong():
    client = _Client({"question": _q(1)})
    client.start_payload = {"question": _q(1)}

    class _Bad(_Client):
        def post(self, path, json=None):
            if json is None:
                return _Response({"detail": "nope"}, 409)
            return _Response({})

    assert _walk(_Bad({}), "/start", "/answer", "founder_dna_question_id", "X", []) is False


# --- cleanup -----------------------------------------------------------


def test_both_completion_stamps_are_cleared():
    assert set(_JOURNEY_STAMPS) == {
        "founder_dna_completed_at", "current_problem_completed_at"
    }


class _FakeDb:
    def __init__(self, explode=False):
        self.statements, self.params, self.rolled_back = [], [], False
        self.explode = explode

    def execute(self, stmt, params=None):
        if self.explode:
            raise RuntimeError("column does not exist")
        self.statements.append(str(stmt))
        self.params.append(params)

    def rollback(self):
        self.rolled_back = True


class _FakeSa:
    @staticmethod
    def text(s):
        return s


def test_clear_journey_stamps_nulls_both_columns_for_the_given_founders():
    db = _FakeDb()
    _clear_journey_stamps(db, _FakeSa, [3704])
    assert len(db.statements) == 1
    sql = db.statements[0]
    assert sql.startswith("update founders set ")
    assert "founder_dna_completed_at = null" in sql
    assert "current_problem_completed_at = null" in sql
    assert "where founder_id = any(:f)" in sql
    assert db.params[0] == {"f": [3704]}


def test_clear_journey_stamps_touches_nothing_else_on_the_row():
    """Identity, consent, plan and profile are not cleanup's business."""
    db = _FakeDb()
    _clear_journey_stamps(db, _FakeSa, [3704])
    sql = db.statements[0]
    for column in ("email", "user_id", "plan_type", "profile_completed",
                   "stage_id", "full_name"):
        assert column not in sql


def test_clear_journey_stamps_survives_a_schema_without_those_columns():
    """Cleanup must not become the reason a tidy-up fails."""
    db = _FakeDb(explode=True)
    _clear_journey_stamps(db, _FakeSa, [3704])
    assert db.rolled_back is True
