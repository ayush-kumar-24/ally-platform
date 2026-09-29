"""A question must not be put to a founder who has nobody to answer it about.

`founders.team_size` was never asked for until 2026-09-28, so the diagnosis had
no way to know how many people work anywhere, and nothing in the question bank
said which questions need other people to exist. A founder working alone was
walked through "Can your staff agree a discount without asking you?" and "When
you last hired, how did you check they could do the work?", and the blank that
follows was scored as a Team & Leadership gap rather than as a question that
should never have been asked.

`questions.min_team_size` (migration d4a1f8c62b73) records the smallest team
that can answer each question. These tests pin the two things that would make
the column useless or harmful:

  * It cannot drift from `founders.team_size`. A question requiring a band a
    founder has no way to state can never be satisfied.
  * Team & Leadership's reviewed default must actually cover the pillar. A
    single question left without a value is one that reaches a solo founder
    once the filter lands, which is the defect this exists to fix.

The offline half runs anywhere. The catalogue half needs a seeded database and
skips without one, so this file still guards the constants in an offline run.
"""

from typing import get_args

import pytest

from app.schemas.founder import TeamSize

MIGRATION = "d4a1f8c62b73"
TEAM_PILLAR_ID = 5


def _migration():
    """Load the migration by path -- alembic revisions are not importable as
    modules, and its reviewed lists are the thing under test."""
    import importlib.util
    from pathlib import Path

    from app.core.paths import BACKEND_DIR

    matches = sorted(Path(BACKEND_DIR, "alembic", "versions").glob(f"*{MIGRATION}*.py"))
    assert len(matches) == 1, f"expected one {MIGRATION} migration, found {matches}"
    spec = importlib.util.spec_from_file_location(f"_mig_{MIGRATION}", matches[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- the bands cannot drift from what a founder can state -------------------

def test_the_migrations_bands_are_exactly_founders_team_size():
    assert _migration()._TEAM_SIZES == get_args(TeamSize)


def test_the_review_scripts_bands_are_exactly_founders_team_size():
    from scripts.review_question_team_size import BANDS

    assert BANDS == get_args(TeamSize)


def test_the_model_check_allows_exactly_those_bands_and_null():
    """The column's CHECK is what stops a typo becoming a question nobody can
    ever be asked."""
    from app.models.schema import Questions

    checks = [
        c for c in Questions.__table__.constraints
        if getattr(c, "name", None) == "questions_min_team_size_check"
    ]
    assert len(checks) == 1, "the CHECK is missing from the model"
    clause = str(checks[0].sqltext)
    assert "min_team_size IS NULL" in clause, "NULL must stay allowed -- it means 'anyone'"
    for band in get_args(TeamSize):
        assert f"'{band}'" in clause, f"{band} missing from the CHECK"


def test_the_model_carries_the_column():
    from app.models.schema import Questions

    assert "min_team_size" in Questions.__table__.c


# --- the reviewed lists are internally sound --------------------------------

def test_the_solo_list_has_no_duplicates():
    solo = _migration()._SOLO
    assert len(solo) == len(set(solo))
    assert solo, "the whole point is that some questions are answerable alone"


def test_every_assigned_dimension_belongs_to_team_and_leadership():
    """A dimension from another pillar would score an answer under one pillar
    and report it under another -- the same invariant c3f7b28d5e91 checks."""
    from app.api.v1.diagnosis.business_dna import DIMENSION_BY_CODE

    mig = _migration()
    assigned = set(mig._BY_SUBCATEGORY.values()) | set(mig._BY_PROBLEM_NAME.values())
    assert assigned, "nothing assigned"
    for code in assigned:
        dimension = DIMENSION_BY_CODE.get(code)
        assert dimension is not None, f"{code!r} is not a Business DNA dimension"
        assert dimension.pillar_id == TEAM_PILLAR_ID, (
            f"{code!r} is pillar {dimension.pillar_id}, not Team & Leadership"
        )


def test_the_assigned_dimensions_are_the_three_the_pillar_has():
    from app.api.v1.diagnosis.business_dna import DIMENSION_BY_CODE

    mig = _migration()
    real = {c for c, d in DIMENSION_BY_CODE.items() if d.pillar_id == TEAM_PILLAR_ID}
    assert set(mig._TEAM_DIMENSIONS) == real


def test_a_group_is_not_assigned_twice():
    """by_problem_name exists for the one subcategory that spans dimensions.
    A name also matched by subcategory would make the outcome order-dependent."""
    mig = _migration()
    overlap = set(mig._BY_SUBCATEGORY) & set(mig._BY_PROBLEM_NAME)
    assert not overlap, f"assigned by both subcategory and name: {sorted(overlap)}"


def test_every_deliberate_null_carries_a_reason():
    """NULL means 'not yet known'. Recording WHY a group was left there is what
    stops the next content pass re-deciding it from scratch."""
    for name, why in _migration()._DELIBERATELY_NULL:
        assert name.strip(), "a deliberate NULL with no group name"
        assert len(why.strip()) > 20, f"{name}: {why!r} is not a reason"


# --- the catalogue itself ---------------------------------------------------

def _rows(sql, **params):
    from sqlalchemy import text

    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return db.execute(text(sql), params).all()
    finally:
        db.close()


@pytest.fixture
def catalogue():
    try:
        rows = _rows(
            "SELECT count(*) FROM questions q JOIN problems p "
            "ON p.problem_id = q.problem_id WHERE p.pillar_id = :pillar",
            pillar=TEAM_PILLAR_ID,
        )
    except Exception as exc:  # no database configured for this run
        pytest.skip(f"no database available: {exc}")
    if not rows or not rows[0][0]:
        pytest.skip("no seeded Team & Leadership questions to test against")
    return rows[0][0]


def test_no_team_and_leadership_question_is_left_without_a_value(catalogue):
    """The one that matters. A NULL here is a question that still reaches a
    founder with nobody to answer it about."""
    missing = _rows(
        """
        SELECT q.question_code FROM questions q
        JOIN problems p ON p.problem_id = q.problem_id
        WHERE p.pillar_id = :pillar AND q.min_team_size IS NULL
        ORDER BY q.question_code LIMIT 20
        """,
        pillar=TEAM_PILLAR_ID,
    )
    assert not missing, (
        f"{len(missing)} Team & Leadership question(s) carry no min_team_size, "
        f"e.g. {[r[0] for r in missing][:5]}"
    )


def test_a_founder_working_alone_still_gets_asked_something(catalogue):
    """The mirror of the test above. Defaulting the pillar to '2_5' without
    opening anything back up would leave a solo founder with no Team &
    Leadership questions at all, and the pillar unscorable rather than scored."""
    solo = _rows(
        """
        SELECT count(*) FROM questions q
        JOIN problems p ON p.problem_id = q.problem_id
        WHERE p.pillar_id = :pillar AND q.min_team_size = 'solo'
        """,
        pillar=TEAM_PILLAR_ID,
    )[0][0]
    assert solo > 0, "no Team & Leadership question is answerable by a solo founder"


def test_every_reviewed_solo_question_is_team_and_leadership(catalogue):
    """A stray code would quietly widen some other pillar for solo founders."""
    codes = list(_migration()._SOLO)
    stray = _rows(
        """
        SELECT q.question_code, p.pillar_id FROM questions q
        JOIN problems p ON p.problem_id = q.problem_id
        WHERE q.question_code = ANY(:codes) AND p.pillar_id <> :pillar
        """,
        codes=codes,
        pillar=TEAM_PILLAR_ID,
    )
    assert not stray, f"reviewed as solo but not Team & Leadership: {stray}"


def test_no_question_requires_a_band_a_founder_cannot_state(catalogue):
    bad = _rows(
        "SELECT DISTINCT min_team_size FROM questions "
        "WHERE min_team_size IS NOT NULL AND min_team_size <> ALL(:bands)",
        bands=list(get_args(TeamSize)),
    )
    assert not bad, f"questions requiring unknown team sizes: {[r[0] for r in bad]}"


def test_team_and_leadership_problems_carry_only_their_own_dimensions(catalogue):
    mig = _migration()
    bad = _rows(
        """
        SELECT problem_name, dimension_code FROM problems
        WHERE pillar_id = :pillar AND dimension_code IS NOT NULL
          AND dimension_code <> ALL(:dims)
        """,
        pillar=TEAM_PILLAR_ID,
        dims=list(mig._TEAM_DIMENSIONS),
    )
    assert not bad, f"pillar 5 problems carrying a non-pillar-5 dimension: {bad}"
