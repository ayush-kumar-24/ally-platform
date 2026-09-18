"""Industry eligibility through the REAL selection pipeline, against the real bank.

The synthetic matrix in `test_industry_eligibility.py` proves the filter's logic.
This file proves the WIRING: that the filter is in the pipeline, upstream of
ranking, and that what reaches the advisor has already been through it.

`test_wrong_industry_question_is_removed_before_ranking` is the one that matters
most. It captures the candidate pool before and after the gate and asserts the
wrong-industry question is absent from the second. A test that only checked the
advisor's choice would pass while the question sat in the shortlist -- which is
the exact failure mode this step exists to close.

Agriculture questions are created inside the test transaction rather than
assumed: the 60 real agritech questions live in production and are not in the
repository, so a test that depended on them would pass on one database and skip
on every other. Tagging is what the engine reads, and tagging is what is seeded.
"""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.engine import QuestionSelectionEngine
from app.api.v1.diagnosis.founder_context import FounderContext
from app.api.v1.diagnosis.industry_scope import filter_by_industry
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.core.config import settings
from app.db.session import engine as db_engine

STAGE_0 = "Stage 0"
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
def industry_bank(db):
    """Five questions spanning the industry/stage matrix, tagged and seeded.

    Returns {label: question_id}. Everything lives in the rolled-back
    transaction, so nothing survives the test.
    """
    have = {
        code for (code,) in db.execute(text("SELECT industry_code FROM industries")).all()
    }
    for code in ("agritech", "healthtech"):
        if code not in have:
            next_id = db.execute(
                text("SELECT coalesce(max(industry_id), 0) + 1 FROM industries")
            ).scalar()
            db.execute(
                text("INSERT INTO industries (industry_id, industry_code, industry_name,"
                     " industry_subtitle, why_industry_context_matters, description)"
                     " VALUES (:i, :c, :c, 'fixture', 'fixture', 'fixture')"),
                {"i": next_id, "c": code},
            )

    problem_id, root_cause_id = db.execute(
        text("SELECT q.problem_id, q.root_cause_id FROM questions q"
             " WHERE q.primary_stage_group = :g LIMIT 1"),
        {"g": STAGE_0},
    ).first()

    marker = uuid.uuid4().hex[:8]
    spec = [
        ("universal", STAGE_0, ["all"]),
        ("agritech_stage0", STAGE_0, ["agritech"]),
        ("healthtech_stage0", STAGE_0, ["healthtech"]),
        ("agritech_growth", GROWTH, ["agritech"]),
        ("both_stage0", STAGE_0, ["agritech", "healthtech"]),
    ]
    ids = {}
    for label, stage, industries in spec:
        qid = db.execute(
            text("""
                INSERT INTO questions (question_code, category, question_text,
                    problem_id, root_cause_id, question_type, difficulty_level,
                    priority, primary_stage_group, industry_relevance)
                VALUES (:code, 'Idea & Validation', :qtext, :p, :r, 'open_text', 2,
                        'CORE', :stage, CAST(:ind AS jsonb))
                RETURNING question_id
            """),
            {"code": f"IND-{marker}-{label}", "qtext": f"fixture {label}",
             "p": problem_id, "r": root_cause_id, "stage": stage,
             "ind": '["' + '","'.join(industries) + '"]'},
        ).scalar()
        ids[label] = qid
    db.flush()
    return ids


def founder_row(industry_code=None, stage_order=1):
    """A founder double carrying what selection reads. No database row needed."""
    return SimpleNamespace(
        founder_id=-1,
        stage=SimpleNamespace(stage_order=stage_order, stage_name="Ideation"),
        industry_mapped=SimpleNamespace(industry_code=industry_code) if industry_code else None,
        team_size="solo", business_model="B2B", current_revenue="pre_revenue",
        current_challenges=["Growth"],
    )


class _Repo(DiagnosisRepository):
    """The real repository with the session-scoped lookups neutralised.

    `list_candidate_questions` filters on answers for a session that does not
    exist here, and the pillar round-robin counts answers the same way. Both are
    someone else's tested behaviour; stubbing them keeps this file about the
    industry axis.
    """

    def answered_count_per_pillar_category(self, _session_id):
        return {}

    def get_detected_root_cause_ids(self, _session_id):
        return set()


def _engine(db):
    return QuestionSelectionEngine(_Repo(db))


def _session():
    return SimpleNamespace(session_id=-1, routing_state="continue")


# --- the critical regression -----------------------------------------------
def test_wrong_industry_question_is_removed_before_ranking(db, industry_bank):
    """Before/after the gate -- not "the advisor did not pick it"."""
    eng = _engine(db)
    founder = founder_row("agritech")
    context = FounderContext.from_founder(founder)

    raw = eng.repository.list_candidate_questions(
        session_id=-1, stage_groups=["Stage 0"], founder_id=None
    )
    before = {q.question_id for q in raw}
    assert industry_bank["healthtech_stage0"] in before, (
        "the wrong-industry question must be in the pool BEFORE the gate, or "
        "this test proves nothing"
    )

    after = {q.question_id for q in eng.candidate_questions(_session(), founder, context)}

    assert industry_bank["healthtech_stage0"] not in after      # gone
    assert industry_bank["agritech_stage0"] in after            # own industry kept
    assert industry_bank["universal"] in after                  # universal kept
    assert industry_bank["both_stage0"] in after                # multi-industry kept


def test_the_shortlist_the_advisor_sees_contains_no_wrong_industry_question(db, industry_bank):
    # The end of the deterministic pipeline: whatever the advisor is handed has
    # already been through stage and industry eligibility.
    eng = _engine(db)
    founder = founder_row("agritech")
    candidates = eng.candidate_questions(_session(), founder, FounderContext.from_founder(founder))
    ordered = eng.order_candidates(candidates, _session())
    shortlist = ordered[: settings.ADAPTIVE_SHORTLIST_SIZE]

    assert len(shortlist) == settings.ADAPTIVE_SHORTLIST_SIZE == 5
    shortlist_ids = {q.question_id for q in shortlist}
    assert industry_bank["healthtech_stage0"] not in shortlist_ids
    for q in shortlist:
        codes = q.industry_relevance or ["all"]
        assert "all" in codes or "agritech" in codes, (
            f"question {q.question_id} reached the shortlist with {codes}"
        )


def test_stage_and_industry_intersect(db, industry_bank):
    # Agritech + Stage 0 must not contain the agritech GROWTH question. Stage
    # removes it upstream; industry would have admitted it.
    eng = _engine(db)
    founder = founder_row("agritech", stage_order=1)
    after = {q.question_id for q in eng.candidate_questions(
        _session(), founder, FounderContext.from_founder(founder))}
    assert industry_bank["agritech_stage0"] in after
    assert industry_bank["agritech_growth"] not in after


# --- the other industries ---------------------------------------------------
def test_a_healthtech_founder_gets_the_mirror_image(db, industry_bank):
    eng = _engine(db)
    founder = founder_row("healthtech")
    after = {q.question_id for q in eng.candidate_questions(
        _session(), founder, FounderContext.from_founder(founder))}
    assert industry_bank["healthtech_stage0"] in after
    assert industry_bank["agritech_stage0"] not in after
    assert industry_bank["both_stage0"] in after
    assert industry_bank["universal"] in after


def test_an_unknown_industry_removes_nothing(db, industry_bank):
    # The 46-of-47 case. Every industry-specific question stays eligible.
    eng = _engine(db)
    founder = founder_row(None)
    after = {q.question_id for q in eng.candidate_questions(
        _session(), founder, FounderContext.from_founder(founder))}
    for label in ("universal", "agritech_stage0", "healthtech_stage0", "both_stage0"):
        assert industry_bank[label] in after, label


def test_how_many_wrong_industry_questions_were_removed(db, industry_bank, capsys):
    """The count attributable to INDUSTRY, isolated from the other gates.

    Measured on the industry pass alone rather than on `candidate_questions`,
    because that method also applies StageScope -- at Ideation it withholds
    eight categories and eleven dimensions, so a before/after diff across the
    whole method attributes hundreds of stage removals to industry. (My first
    version of this test made exactly that mistake and the assertion caught it.)
    """
    eng = _engine(db)
    founder = founder_row("agritech")
    context = FounderContext.from_founder(founder)

    raw = eng.repository.list_candidate_questions(
        session_id=-1, stage_groups=["Stage 0"], founder_id=None
    )
    result = filter_by_industry(raw, context)
    removed = result.removed_ids

    # Exactly the fixture's healthtech question: every one of the 3,340 shipped
    # questions is ["all"] and therefore universal. Asserted exactly rather than
    # "> 0", because an over-eager gate shows up as a bigger number and a test
    # that only demanded non-zero would not notice.
    assert removed == {industry_bank["healthtech_stage0"]}
    with capsys.disabled():
        print(f"\n    industry gate: {len(raw)} stage-eligible -> "
              f"{len(result.kept)} kept, {len(removed)} removed as wrong-industry")


# --- fail-open paths --------------------------------------------------------
def test_an_empty_pool_is_never_the_gates_doing(db, industry_bank):
    # If every candidate were the wrong industry, the gate leaves the set alone
    # rather than ending the diagnosis. Asserted directly on the pass, because
    # the real bank is too universal to reach this state.
    eng = _engine(db)
    founder = founder_row("agritech")
    context = FounderContext.from_founder(founder)
    only_wrong = [SimpleNamespace(question_id=9001, industry_relevance=["healthtech"])]
    assert eng._industry_gated(only_wrong, context) == only_wrong


def test_the_gate_is_skipped_entirely_when_industry_is_unknown(db):
    eng = _engine(db)
    context = FounderContext.from_founder(founder_row(None))
    candidates = [SimpleNamespace(question_id=1, industry_relevance=["healthtech"])]
    assert eng._industry_gated(candidates, context) is candidates
