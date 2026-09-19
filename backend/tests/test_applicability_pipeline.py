"""Step 4 through the REAL selection pipeline, against the real question bank.

test_applicability_gate.py proves the filter's logic in isolation. This file
proves the WIRING: that the gate is in the pipeline, that it runs BEFORE
ranking and category balancing, and that the Top 5 the advisor is handed cannot
contain a question the founder has contradicted.

The order assertion is the one that matters most. Balancing categories first and
discovering afterwards that the chosen questions are inapplicable would produce
a shortlist that looks balanced and asks a solo founder about their managers --
so `test_round_robin_runs_after_applicability_not_before` compares the pool
before and after rather than inspecting the final pick.
"""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.advisor import AnswerInsight, resolve_next
from app.api.v1.diagnosis.engine import QuestionSelectionEngine
from app.api.v1.diagnosis.founder_context import FounderContext, TOKEN_HAS_TEAM
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.core.config import settings
from app.db.session import engine as db_engine

GROWTH = "Stage 1→10+"


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


@pytest.fixture
def team_bank(db):
    """One tagged (team-dependent) and one untagged question, both Growth.

    Seeded rather than assumed: the curated `hr-*` tags are data, and a test
    that read them would prove the curation instead of the mechanism. Everything
    lives in the rolled-back transaction.
    """
    problem_id, root_cause_id = db.execute(
        text("SELECT problem_id, root_cause_id FROM questions"
             " WHERE primary_stage_group = :g LIMIT 1"),
        {"g": GROWTH},
    ).first()

    marker = uuid.uuid4().hex[:8]
    tag_id = db.execute(
        text("INSERT INTO question_tags (tag_name, precondition_token)"
             " VALUES (:n, :t) RETURNING tag_id"),
        {"n": f"fixture-team-{marker}", "t": TOKEN_HAS_TEAM},
    ).scalar()

    ids = {}
    for label in ("tagged", "untagged"):
        qid = db.execute(
            text("""INSERT INTO questions (question_code, category, question_text,
                        problem_id, root_cause_id, question_type, difficulty_level,
                        priority, primary_stage_group, industry_relevance)
                    VALUES (:code, 'Team & Leadership', :qtext, :p, :r, 'open_text',
                            2, 'CORE', :stage, '["all"]'::jsonb)
                    RETURNING question_id"""),
            {"code": f"APP-{marker}-{label}", "qtext": f"fixture {label}",
             "p": problem_id, "r": root_cause_id, "stage": GROWTH},
        ).scalar()
        ids[label] = qid
    db.execute(
        text("INSERT INTO question_tag_mapping (question_id, tag_id) VALUES (:q, :t)"),
        {"q": ids["tagged"], "t": tag_id},
    )
    db.flush()
    return ids


def founder_row(team_size=None, stage_order=5):
    return SimpleNamespace(
        founder_id=-1,
        stage=SimpleNamespace(stage_order=stage_order, stage_name="Growth"),
        industry_mapped=None, team_size=team_size, business_model="B2B",
        current_revenue="25L_1Cr", current_challenges=["Growth"],
    )


class _Repo(DiagnosisRepository):
    """The real repository with the session-scoped lookups neutralised.

    `list_candidate_questions` filters on answers for a session that does not
    exist here, and the round-robin counts answers the same way. Both are
    someone else's tested behaviour; stubbing them keeps this file about
    applicability.
    """

    def answered_count_per_pillar_category(self, _session_id):
        return {}

    def get_detected_root_cause_ids(self, _session_id):
        return set()


def _engine(db):
    return QuestionSelectionEngine(_Repo(db))


def _session():
    return SimpleNamespace(session_id=-1, routing_state="continue")


# =========================================================== the critical wiring
def test_a_solo_founder_never_reaches_a_team_dependent_question(db, team_bank):
    """Before/after the gate -- not "the advisor did not pick it"."""
    eng = _engine(db)
    founder = founder_row(team_size="solo")

    raw = eng.repository.list_candidate_questions(
        session_id=-1, stage_groups=[GROWTH], founder_id=None
    )
    before = {q.question_id for q in raw}
    assert team_bank["tagged"] in before, (
        "the team question must be in the pool BEFORE the gate, or this test "
        "proves nothing"
    )

    after = {q.question_id for q in eng.candidate_questions(
        _session(), founder, FounderContext.from_founder(founder))}
    assert team_bank["tagged"] not in after
    assert team_bank["untagged"] in after


def test_an_unknown_team_size_reaches_it_untouched(db, team_bank):
    eng = _engine(db)
    founder = founder_row(team_size=None)
    after = {q.question_id for q in eng.candidate_questions(
        _session(), founder, FounderContext.from_founder(founder))}
    assert team_bank["tagged"] in after
    assert team_bank["untagged"] in after


def test_a_founder_with_a_team_reaches_it_too(db, team_bank):
    eng = _engine(db)
    founder = founder_row(team_size="11_25")
    after = {q.question_id for q in eng.candidate_questions(
        _session(), founder, FounderContext.from_founder(founder))}
    assert team_bank["tagged"] in after


def test_the_uncertain_set_is_reachable_for_the_advisor(db, team_bank):
    # applicability_uncertain: kept, but the fit is not established.
    eng = _engine(db)
    founder = founder_row(team_size=None)
    context = FounderContext.from_founder(founder)
    pool = eng.repository.list_candidate_questions(
        session_id=-1, stage_groups=[GROWTH], founder_id=None
    )
    report = eng.applicability_report(pool, context)
    assert team_bank["tagged"] in report.uncertain_ids
    assert team_bank["untagged"] not in report.uncertain_ids


# =========================================================== G: ordering
def test_round_robin_runs_after_applicability_not_before(db, team_bank):
    """Case 15. Category balancing must never see a contradicted question.

    Asserted on the pipeline's SHAPE: `candidate_questions` (which gates) is a
    separate, earlier call from `order_candidates` (which balances), and the
    balanced output is a permutation of the gated input. If balancing ran first
    the gated question could appear in the ordered result.
    """
    eng = _engine(db)
    founder = founder_row(team_size="solo")
    gated = eng.candidate_questions(_session(), founder, FounderContext.from_founder(founder))
    ordered = eng.order_candidates(gated, _session())

    assert sorted(q.question_id for q in ordered) == sorted(q.question_id for q in gated), (
        "ordering must be a permutation of the gated pool -- it may not add "
        "candidates back"
    )
    assert team_bank["tagged"] not in {q.question_id for q in ordered}


def test_the_top_5_contains_only_eligible_candidates(db, team_bank):
    """Case 16."""
    eng = _engine(db)
    founder = founder_row(team_size="solo")
    candidates = eng.candidate_questions(
        _session(), founder, FounderContext.from_founder(founder))
    shortlist = eng.order_candidates(candidates, _session())[
        : settings.ADAPTIVE_SHORTLIST_SIZE]

    assert len(shortlist) == settings.ADAPTIVE_SHORTLIST_SIZE == 5
    eligible = {q.question_id for q in candidates}
    assert {q.question_id for q in shortlist} <= eligible
    assert team_bank["tagged"] not in {q.question_id for q in shortlist}


# =========================================================== H: the advisor bound
def test_the_advisor_selects_only_from_the_top_5(db, team_bank):
    """Case 17."""
    eng = _engine(db)
    founder = founder_row(team_size=None)
    ordered = eng.order_candidates(
        eng.candidate_questions(_session(), founder, FounderContext.from_founder(founder)),
        _session(),
    )
    shortlist = ordered[: settings.ADAPTIVE_SHORTLIST_SIZE]
    chosen = shortlist[-1]
    insight = AnswerInsight(score_label="amber", confidence=0.8,
                            next_question_id=chosen.question_id, rationale="")
    assert resolve_next(ordered, shortlist, insight).question_id == chosen.question_id


def test_the_advisor_cannot_introduce_a_question_outside_the_top_5(db, team_bank):
    """Case 18. The LLM is an interviewer, not the applicability engine.

    Pointed at the question the gate REMOVED, which is the dangerous version of
    this failure: a model that names an id outside the shortlist must be
    overruled, not obeyed.
    """
    eng = _engine(db)
    founder = founder_row(team_size="solo")
    ordered = eng.order_candidates(
        eng.candidate_questions(_session(), founder, FounderContext.from_founder(founder)),
        _session(),
    )
    shortlist = ordered[: settings.ADAPTIVE_SHORTLIST_SIZE]
    insight = AnswerInsight(score_label="amber", confidence=0.9,
                            next_question_id=team_bank["tagged"], rationale="")
    picked = resolve_next(ordered, shortlist, insight)
    assert picked.question_id != team_bank["tagged"]
    assert picked is ordered[0]           # falls back to the deterministic head
