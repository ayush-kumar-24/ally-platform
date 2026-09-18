"""`industry_relevance` data quality. Reports problems; never repairs them.

Every check here is for something that fails SILENTLY in production. A question
tagged with an industry code that does not exist in `industries` is unreachable
-- no founder can ever match it -- and nothing anywhere would say so. A question
whose industries disagree with its problem's is a genuine editorial question, not
a bug to auto-fix, and the architecture is explicit that nothing reconciles it.

These assert the SHAPE of the report, and report what the current database
actually contains rather than asserting it is clean. A test that demanded zero
mismatches would fail the day Arya tags the first industry-specific problem, for
a reason that is not a defect.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.industry_scope import (
    UNIVERSAL,
    is_universal,
    relevance_codes,
    validate_industry_metadata,
)
from app.db.session import engine as db_engine


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
def report(db):
    return validate_industry_metadata(db)


# --- the live bank ----------------------------------------------------------
def test_every_industry_code_on_a_question_exists_in_the_catalogue(report):
    assert report["unknown_codes"] == [], (
        "questions carry industry codes that are not in `industries`. Each one "
        "is unreachable: no founder can ever match it."
    )


def test_the_catalogue_is_populated(report):
    assert report["catalogue_size"] >= 4
    assert report["checked"] > 0


def test_no_question_has_an_unreadable_relevance_value(report):
    assert report["unreadable"] == []


def test_no_duplicate_codes_within_one_relevance_array(report):
    assert report["duplicate_codes"] == []


def test_all_is_not_mixed_with_specific_codes(report):
    # `all` wins when both are present, so the row is askable either way -- but
    # the author meant one or the other and the data should say which.
    assert report["mixed_all_and_specific"] == []


def test_universal_questions_are_still_universal(db):
    # The 3,340 pre-existing questions must not have been narrowed by the
    # migration that added the column. Their default is what makes the hybrid
    # architecture work without duplicating a question per industry.
    universal = db.execute(text(
        "SELECT count(*) FROM questions WHERE industry_relevance = '[\"all\"]'::jsonb"
    )).scalar()
    total = db.execute(text("SELECT count(*) FROM questions")).scalar()
    assert universal >= 3340, (
        f"only {universal} of {total} questions are universal; the migration's "
        f"'[\"all\"]' default should have left every pre-existing question so"
    )


def test_no_question_has_a_null_relevance(db):
    # The migration backfilled NULLs. A NULL would still behave as universal via
    # relevance_codes(), but silently, and the column has a default for a reason.
    nulls = db.execute(
        text("SELECT count(*) FROM questions WHERE industry_relevance IS NULL")
    ).scalar()
    assert nulls == 0


def test_taxonomy_mismatches_are_reported_not_reconciled(report, capsys):
    """Reported, by architectural decision. This test records what exists.

    Question-level metadata answers "can we ask this"; problem and root-cause
    metadata answer "how relevant is the interpretation". Letting one override
    the other would create restrictions nobody wrote -- so this asserts the
    report has the right shape and prints what it found.
    """
    assert isinstance(report["mismatched_with_taxonomy"], list)
    for entry in report["mismatched_with_taxonomy"]:
        assert {"question_id", "level", "question", "taxonomy"} <= set(entry)
        assert entry["level"] in {"problem", "root_cause"}
    with capsys.disabled():
        print(f"\n    industry metadata: {report['checked']} questions checked, "
              f"{len(report['mismatched_with_taxonomy'])} taxonomy mismatch(es), "
              f"catalogue of {report['catalogue_size']}")


# --- the checks themselves, on data the fixtures control --------------------
def test_an_unknown_code_is_caught(db):
    problem_id, root_cause_id = db.execute(
        text("SELECT problem_id, root_cause_id FROM questions LIMIT 1")
    ).first()
    db.execute(
        text("""INSERT INTO questions (question_code, category, question_text,
                 problem_id, root_cause_id, question_type, difficulty_level,
                 priority, primary_stage_group, industry_relevance)
                VALUES ('BAD-CODE-1', 'Idea & Validation', 'fixture', :p, :r,
                        'open_text', 2, 'CORE', 'Stage 0',
                        '["not_a_real_industry"]'::jsonb)"""),
        {"p": problem_id, "r": root_cause_id},
    )
    db.flush()
    report = validate_industry_metadata(db)
    assert any(
        "not_a_real_industry" in entry["codes"] for entry in report["unknown_codes"]
    )


def test_a_duplicate_code_is_caught(db):
    problem_id, root_cause_id = db.execute(
        text("SELECT problem_id, root_cause_id FROM questions LIMIT 1")
    ).first()
    qid = db.execute(
        text("""INSERT INTO questions (question_code, category, question_text,
                 problem_id, root_cause_id, question_type, difficulty_level,
                 priority, primary_stage_group, industry_relevance)
                VALUES ('DUP-CODE-1', 'Idea & Validation', 'fixture', :p, :r,
                        'open_text', 2, 'CORE', 'Stage 0',
                        '["saas","saas"]'::jsonb)
                RETURNING question_id"""),
        {"p": problem_id, "r": root_cause_id},
    ).scalar()
    db.flush()
    assert qid in validate_industry_metadata(db)["duplicate_codes"]


# --- the primitives ---------------------------------------------------------
def test_all_is_the_universal_marker():
    assert UNIVERSAL == "all"
    assert is_universal(["all"]) is True
    assert is_universal(["All"]) is True
    assert is_universal(["agritech"]) is False


def test_relevance_codes_normalises():
    assert relevance_codes(["AgriTech", " saas "]) == {"agritech", "saas"}
    assert relevance_codes([]) is None
    assert relevance_codes(None) is None
