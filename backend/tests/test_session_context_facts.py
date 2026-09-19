"""Session-learned context: tightens THIS session, never edits the founder.

THE BOUNDARY IS THE FEATURE. A fact here is an inference drawn from a sentence
of free text. The profile is what the founder chose in onboarding. Promoting the
first into the second would let one ambiguous answer silently rewrite someone's
record, invisibly -- nothing in the product shows a founder what Ally concluded
about them. So `test_a_session_fact_never_touches_the_founder_row` is the test
that matters most here, and it checks the database rather than the object.

The precedence tests are the other half: a stated profile value must beat an
inference every time, so an answer that reads like "no team" cannot override a
founder who told us they have eleven people.
"""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.applicability import filter_by_applicability
from app.api.v1.diagnosis.founder_context import (
    Applicability,
    FounderContext,
    TOKEN_HAS_TEAM,
)
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.db.session import engine as db_engine

CONTRADICTED = Applicability.CONTRADICTED
SATISFIED = Applicability.SATISFIED
UNKNOWN = Applicability.UNKNOWN


@pytest.fixture
def db():
    conn = db_engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


def ctx(team_size=None):
    return FounderContext.from_founder(SimpleNamespace(
        stage=SimpleNamespace(stage_order=5, stage_name="Growth"),
        industry_mapped=None, team_size=team_size, business_model=None,
        current_revenue=None, current_challenges=None,
    ))


def q(qid):
    return SimpleNamespace(question_id=qid, category="Team & Leadership",
                           problem_id=1, root_cause_id=1, industry_relevance=["all"])


# =========================================================== E: learning
def test_a_fact_settles_a_family_the_profile_left_unknown():
    """Case 11. "I don't have any employees" -> has_team false, this session."""
    before = ctx(team_size=None)
    assert before.verdict(TOKEN_HAS_TEAM) is UNKNOWN

    after = before.with_session_facts({TOKEN_HAS_TEAM: False})
    assert after.verdict(TOKEN_HAS_TEAM) is CONTRADICTED


def test_the_fact_changes_what_is_eligible_next(db):
    """Case 11, through the gate rather than the value object."""
    preconditions = {1: frozenset({TOKEN_HAS_TEAM})}
    unknown = ctx(team_size=None)
    assert filter_by_applicability([q(1)], unknown, preconditions).kept      # kept

    learned = unknown.with_session_facts({TOKEN_HAS_TEAM: False})
    assert filter_by_applicability([q(1)], learned, preconditions).removed_ids == {1}


def test_a_positive_fact_also_settles_the_family():
    after = ctx(team_size=None).with_session_facts({TOKEN_HAS_TEAM: True})
    assert after.verdict(TOKEN_HAS_TEAM) is SATISFIED


# =========================================================== precedence
def test_a_stated_profile_value_beats_an_inference():
    """A founder who told us they have 11-25 people keeps their team."""
    stated = ctx(team_size="11_25")
    assert stated.with_session_facts({TOKEN_HAS_TEAM: False}).verdict(
        TOKEN_HAS_TEAM) is SATISFIED


def test_a_stated_solo_is_not_overridden_either():
    stated = ctx(team_size="solo")
    assert stated.with_session_facts({TOKEN_HAS_TEAM: True}).verdict(
        TOKEN_HAS_TEAM) is CONTRADICTED


def test_an_unrecognised_token_is_ignored_rather_than_stored():
    context = ctx(team_size=None)
    assert context.with_session_facts({"has_tema": False}) is context


def test_no_facts_returns_the_same_object():
    context = ctx()
    assert context.with_session_facts(None) is context
    assert context.with_session_facts({}) is context


# =========================================================== persistence
def test_a_session_fact_never_touches_the_founder_row(db):
    """Case 12, checked in the DATABASE -- the only place it would matter."""
    repo = DiagnosisRepository(db)
    # A founder that HAS a session, rather than the first founder -- this is the
    # assertion the whole module exists for and it must not skip.
    row = db.execute(text(
        "SELECT f.founder_id, f.team_size, s.session_id"
        "  FROM founders f JOIN sessions s ON s.founder_id = f.founder_id"
        " ORDER BY s.session_id LIMIT 1"
    )).first()
    assert row is not None, "this database has no founder with a session"
    founder_id, before, session_id = row

    repo.record_session_fact(session_id, TOKEN_HAS_TEAM, False, None)
    db.flush()

    after = db.execute(
        text("SELECT team_size FROM founders WHERE founder_id = :f"), {"f": founder_id}
    ).scalar()
    assert after == before, "recording a session fact must not edit the profile"
    assert repo.session_context_facts(session_id) == {TOKEN_HAS_TEAM: False}


def test_a_later_answer_replaces_the_earlier_verdict(db):
    """One row per (session, token) -- not two rows disagreeing."""
    repo = DiagnosisRepository(db)
    session_id = db.execute(text("SELECT session_id FROM sessions LIMIT 1")).scalar()
    if session_id is None:
        pytest.skip("no sessions in this database")

    repo.record_session_fact(session_id, TOKEN_HAS_TEAM, False, None)
    repo.record_session_fact(session_id, TOKEN_HAS_TEAM, True, None)
    db.flush()

    assert repo.session_context_facts(session_id) == {TOKEN_HAS_TEAM: True}
    rows = db.execute(
        text("SELECT count(*) FROM session_context_facts"
             " WHERE session_id = :s AND token = :t"),
        {"s": session_id, "t": TOKEN_HAS_TEAM},
    ).scalar()
    assert rows == 1


def test_facts_are_scoped_to_one_session(db):
    repo = DiagnosisRepository(db)
    ids = [r[0] for r in db.execute(
        text("SELECT session_id FROM sessions ORDER BY session_id LIMIT 2")).all()]
    if len(ids) < 2:
        pytest.skip("need two sessions")

    repo.record_session_fact(ids[0], TOKEN_HAS_TEAM, False, None)
    db.flush()
    assert repo.session_context_facts(ids[0]) == {TOKEN_HAS_TEAM: False}
    assert repo.session_context_facts(ids[1]) == {}, (
        "a fact learned in one session must not leak into another"
    )


def test_unknown_is_never_written_down(db):
    """Absence is UNKNOWN. There is no third value to store, by design."""
    repo = DiagnosisRepository(db)
    session_id = db.execute(text("SELECT session_id FROM sessions LIMIT 1")).scalar()
    if session_id is None:
        pytest.skip("no sessions in this database")
    assert repo.session_context_facts(session_id) == {}
    assert ctx(team_size=None).verdict(TOKEN_HAS_TEAM) is UNKNOWN
