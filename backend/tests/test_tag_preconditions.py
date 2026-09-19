"""The LIVE curation: which tags carry a precondition, and which must not.

Separate from test_applicability_gate.py on purpose. That file proves the
MECHANISM against synthetic tags and would pass on an empty curation. This one
is about the DATA -- the editorial judgement in migration b7c2d94e5f10 -- and it
reports what the database actually contains rather than asserting a number that
would fail the day Arya curates a fourth tag for a good reason.

The rejection tests are the important ones and they are stated as rules, not as
a list: a tag whose questions are answerable by a solo founder must never gate
on `has_team`, and `test_no_tag_gates_a_founder_dependency_subject` is what
stops a future curation pass quietly deciding that `delegation` is a team
subject. A solo founder is the founder MOST likely to have a delegation problem.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.founder_context import TOKEN_HAS_TEAM, family_of
from app.db.session import engine as db_engine

#: Tags that were read and REJECTED, with the reason in one word. Gating any of
#: these would remove questions a founder can answer -- see the migration for
#: the disqualifying question text quoted in full.
MUST_NOT_GATE_ON_TEAM = {
    "delegation": "a solo founder has delegation READINESS problems",
    "hiring": "a solo founder's first hire is the whole subject",
    "team-communication": "contains the founder-dependency question",
    "team-expertise": "contains '...on your own?' phrasings",
    "sales-team-capability": "contains 'if you had to hire your first rep'",
    "marketing-team-capability": "contains 'what capability are YOU missing'",
    "sales-founder-bottleneck": "about the founder, most acute when solo",
    "pitch": "a solo founder pitches",
    "work-life-sustainability": "workload is worst without a team",
    "fundraising-readiness": "all 14 FND-005 questions carry it",
    "accountability": "self-accountability is a solo subject",
    "culture": "a founder sets culture before hiring",
}


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
def curated(db):
    rows = db.execute(text(
        "SELECT tag_name, precondition_token FROM question_tags"
        " WHERE precondition_token IS NOT NULL"
    )).all()
    return {name: token for name, token in rows}


# =========================================================== what IS curated
def test_the_curated_tokens_are_all_recognised(curated):
    """A token with no family resolves to UNKNOWN and gates nothing.

    So an unrecognised token is not a safe typo -- it is a curation that looks
    applied and does nothing. This is the check that catches it.
    """
    for tag, token in curated.items():
        assert family_of(token) is not None, (
            f"tag {tag!r} carries {token!r}, which FounderContext cannot resolve; "
            "it would silently gate nothing"
        )


def test_the_hr_tags_gate_on_has_team(curated):
    for tag in ("hr-capability", "hr-process", "hr-tooling"):
        assert curated.get(tag) == TOKEN_HAS_TEAM, (
            f"{tag} should presuppose a team; these questions are about "
            "managers, performance reviews and payroll"
        )


def test_the_token_matches_the_constant_the_engine_reads():
    # The migration inlines the string; this is what stops the two drifting
    # apart into a token nothing resolves.
    assert TOKEN_HAS_TEAM == "has_team"


# =========================================================== what must NOT be
@pytest.mark.parametrize("tag,reason", sorted(MUST_NOT_GATE_ON_TEAM.items()))
def test_a_solo_answerable_tag_never_gates_on_team(curated, tag, reason):
    assert curated.get(tag) != TOKEN_HAS_TEAM, (
        f"{tag} must not presuppose a team: {reason}"
    )


def test_no_tag_gates_a_founder_dependency_subject(db, curated):
    """The rule behind the list: solo is not "no founder problems".

    Scans the curated tags' own question text for the phrasings that mark a
    question as being about the FOUNDER rather than about employees. A curation
    that gated one of those would be removing exactly the questions a solo
    founder most needs.
    """
    if not curated:
        pytest.skip("no curation in this database")
    rows = db.execute(text(
        "SELECT t.tag_name, q.question_text"
        "  FROM question_tags t"
        "  JOIN question_tag_mapping m ON m.tag_id = t.tag_id"
        "  JOIN questions q ON q.question_id = m.question_id"
        " WHERE t.precondition_token = :tok"
    ), {"tok": TOKEN_HAS_TEAM}).all()

    solo_phrasings = ("on your own", "by yourself", "without any help",
                      "your first hire", "first salesperson")
    offenders = [
        (tag, qt) for tag, qt in rows
        if any(p in (qt or "").lower() for p in solo_phrasings)
    ]
    assert not offenders, (
        "a team-gated tag contains questions written FOR a founder without a "
        f"team: {offenders[:3]}"
    )


# =========================================================== scope of the blast
def test_the_curation_is_small_and_reported(db, curated, capsys):
    """Reports rather than pins a number -- a fourth tag is not a regression."""
    gated = db.execute(text(
        "SELECT count(DISTINCT m.question_id) FROM question_tag_mapping m"
        "  JOIN question_tags t ON t.tag_id = m.tag_id"
        " WHERE t.precondition_token IS NOT NULL"
    )).scalar()
    total = db.execute(text("SELECT count(*) FROM questions")).scalar()
    assert gated < total * 0.1, (
        f"{gated} of {total} questions carry a precondition; a curation this "
        "broad should be reviewed rather than shipped"
    )
    with capsys.disabled():
        print(f"\n    preconditions: {len(curated)} tag(s), {gated} of {total} "
              f"questions gated")


def test_every_gated_question_is_a_team_and_leadership_question(db, curated):
    """A team precondition on, say, a pricing question would be a curation bug."""
    if not curated:
        pytest.skip("no curation in this database")
    categories = {c for (c,) in db.execute(text(
        "SELECT DISTINCT q.category FROM questions q"
        "  JOIN question_tag_mapping m ON m.question_id = q.question_id"
        "  JOIN question_tags t ON t.tag_id = m.tag_id"
        " WHERE t.precondition_token = :tok"
    ), {"tok": TOKEN_HAS_TEAM}).all()}
    assert categories <= {"Team & Leadership"}, (
        f"has_team is gating outside Team & Leadership: {sorted(categories)}"
    )
