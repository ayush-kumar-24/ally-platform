"""Exit has its own questions, and its own bank to keep them in.

A founder who picks "Exit -- preparing to hand it on or sell" got 2,414
questions and not one was about exiting: the whole catalogue mentioned
succession, handing over, selling the business or a buyer exactly nowhere.

The 200 new questions cannot live in `Stage 1->10+`, which Growth, Expansion
and Maturity also draw from -- a founder scaling up would be asked what a buyer
would discount them for. So `questions.primary_stage_group` gained a fourth
value and an Exit founder draws from BOTH banks: the general one they still
need, plus this one.
"""

import pytest

from app.models.enums import StageGroup

EXIT_GROUP = StageGroup.EXIT.value
EXIT_ORDER = 8
TOPICS = 10
PER_TOPIC = 20


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
            "SELECT count(*) FROM questions WHERE primary_stage_group = :g",
            g=EXIT_GROUP,
        )
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")
    if not rows or not rows[0][0]:
        pytest.skip("the Exit bank is not loaded in this database")
    return rows[0][0]


# --- who draws from which bank ---------------------------------------------

def _groups(order):
    from types import SimpleNamespace

    from app.api.v1.diagnosis.engine import stage_groups_for

    stage = SimpleNamespace(stage_order=order) if order else None
    return stage_groups_for(stage)


def test_an_exit_founder_draws_from_both_banks():
    """Both, not instead. The six pillars are still assessed at Exit; only the
    handover questions are new."""
    assert set(_groups(EXIT_ORDER)) == {
        StageGroup.STAGE_1_TO_10_PLUS.value, EXIT_GROUP}


@pytest.mark.parametrize("order", [1, 2, 3, 4, 5, 6, 7])
def test_no_other_stage_can_see_the_exit_bank(order):
    assert EXIT_GROUP not in _groups(order)


def test_an_unknown_stage_fails_open_to_the_general_banks_only():
    """`stage_groups_for` returns everything when it cannot place a founder,
    because returning nothing would dead-end the assessment. Exit is
    deliberately left out of that: its questions are written for someone
    handing the business on, and three banks is not a dead end."""
    groups = set(_groups(None))
    assert EXIT_GROUP not in groups
    assert len(groups) == 3


def test_the_enum_and_the_column_agree():
    from app.models.schema import Questions

    check = next(
        c for c in Questions.__table__.constraints
        if getattr(c, "name", None) == "questions_primary_stage_group_check"
    )
    clause = str(check.sqltext)
    for group in StageGroup:
        assert f"'{group.value}'" in clause, f"{group.value} missing from the CHECK"


# --- the bank itself --------------------------------------------------------

def test_the_bank_holds_twenty_questions_in_each_of_ten_topics(catalogue):
    rows = _rows(
        """
        SELECT p.problem_code, count(*) FROM questions q
        JOIN problems p ON p.problem_id = q.problem_id
        WHERE q.primary_stage_group = :g GROUP BY 1 ORDER BY 1
        """,
        g=EXIT_GROUP,
    )
    assert len(rows) == TOPICS, f"expected {TOPICS} topics, found {len(rows)}"
    for code, n in rows:
        assert n == PER_TOPIC, f"{code} has {n} questions, expected {PER_TOPIC}"


def test_every_pillar_is_covered(catalogue):
    """The first seven topics reached five pillars. Customer Definition was
    added to bring in Market Clarity, so an Exit founder's report does not go
    quiet on a whole section."""
    pillars = {
        r[0] for r in _rows(
            "SELECT DISTINCT p.pillar_id FROM questions q "
            "JOIN problems p ON p.problem_id = q.problem_id "
            "WHERE q.primary_stage_group = :g",
            g=EXIT_GROUP,
        )
    }
    assert pillars == {1, 2, 3, 4, 5, 6}


def test_every_topic_carries_its_dimension(catalogue):
    """These were tagged at writing time, which is the one moment it is cheap.
    Two thirds of the older bank has no dimension and retrofitting it means
    reading every question."""
    untagged = _rows(
        "SELECT DISTINCT p.problem_code FROM questions q "
        "JOIN problems p ON p.problem_id = q.problem_id "
        "WHERE q.primary_stage_group = :g AND p.dimension_code IS NULL",
        g=EXIT_GROUP,
    )
    assert not untagged, f"Exit problems with no dimension: {untagged}"


def test_no_exit_question_sits_in_a_category_exit_withholds(catalogue):
    """It would be unreachable by the only founders who can see this bank."""
    from app.api.v1.diagnosis.stage_scope import EXIT_WITHHELD_CATEGORIES

    stranded = _rows(
        "SELECT question_code FROM questions "
        "WHERE primary_stage_group = :g AND category = ANY(:withheld)",
        g=EXIT_GROUP,
        withheld=sorted(EXIT_WITHHELD_CATEGORIES),
    )
    assert not stranded, f"unreachable Exit questions: {stranded}"


def test_a_dimension_never_sits_in_the_wrong_pillar(catalogue):
    """Same invariant c3f7b28d5e91 checks for the rest of the catalogue: a
    dimension from another pillar would score under one and report under
    another."""
    from app.api.v1.diagnosis.business_dna import DIMENSION_BY_CODE

    for code, pillar, dimension in _rows(
        "SELECT DISTINCT p.problem_code, p.pillar_id, p.dimension_code FROM questions q "
        "JOIN problems p ON p.problem_id = q.problem_id "
        "WHERE q.primary_stage_group = :g",
        g=EXIT_GROUP,
    ):
        assert DIMENSION_BY_CODE[dimension].pillar_id == pillar, (
            f"{code}: {dimension} is pillar {DIMENSION_BY_CODE[dimension].pillar_id}, "
            f"filed under {pillar}"
        )


def test_a_founder_working_alone_still_gets_a_real_exit_diagnosis(catalogue):
    """43 of the 200 need other people. If the rest had been written for a
    company with staff, a solo founder selling a one-person business would get
    the new bank and almost nothing from it."""
    solo = _rows(
        "SELECT count(*) FROM questions WHERE primary_stage_group = :g "
        "AND min_team_size IS NULL",
        g=EXIT_GROUP,
    )[0][0]
    assert solo >= 100, f"only {solo} of the Exit bank is answerable alone"


def test_the_wording_rules_hold(catalogue):
    """Short, plain, no consultant vocabulary -- the standing rule for this
    bank, and the reason these were written rather than borrowed."""
    import re

    JARGON = re.compile(
        r"\b(cadence|scorecard|systemati|benchmark|siloed|cross-functional|"
        r"unit economics|runway|stakeholder|leverage|synerg|KPI|ROI)\b", re.I
    )
    rows = _rows(
        "SELECT question_code, question_text FROM questions "
        "WHERE primary_stage_group = :g",
        g=EXIT_GROUP,
    )
    too_long = [c for c, t in rows if len(t) > 110]
    jargon = [c for c, t in rows if JARGON.search(t)]
    assert not too_long, f"Exit questions over 110 characters: {too_long}"
    assert not jargon, f"Exit questions using banned vocabulary: {jargon}"


def test_the_bank_matches_the_draft_it_was_generated_from(catalogue):
    """docs/drafts/exit-stage-questions.md is the reviewable version and the
    source of truth. If someone edits the database directly the two drift, and
    the next regeneration silently reverts their edit."""
    import re

    from app.core.paths import BACKEND_DIR

    draft = BACKEND_DIR.parent / "docs/drafts/exit-stage-questions.md"
    if not draft.exists():
        pytest.skip("the draft is not in this checkout")
    body = draft.read_text(encoding="utf-8").split("## 1. Founder Dependency", 1)[1]
    in_draft = {
        m.group(2).strip()
        for m in re.finditer(r"^\| (\d+) \| (.+?) \| (\w+) \| (yes|no) \|$", body, re.M)
    }
    in_db = {t for _c, t in _rows(
        "SELECT question_code, question_text FROM questions "
        "WHERE primary_stage_group = :g", g=EXIT_GROUP)}
    assert in_db == in_draft, (
        f"{len(in_db - in_draft)} in the database but not the draft, "
        f"{len(in_draft - in_db)} the other way round"
    )


# --- the second bank must not look like an unknown stage --------------------
#
# Three places read `stage_groups_for` and branched on getting exactly one
# group back, because until now that was the same thing as "the stage is
# known". An Exit founder returns two. Each of these broke in a different,
# silent way, and none of them is about Exit questions at all.

def test_an_exit_founder_still_owes_the_path_two_profile_fields():
    """`_path_required` compared the group list to a one-element list. An Exit
    founder matched neither, so their profile counted as complete with no
    revenue figure, no product description and no one-year vision."""
    from types import SimpleNamespace

    from app.services.profile_progress import validate_profile

    founder = SimpleNamespace(
        founder_id=1, stage_id=8, profile_completed=True,
        stage=SimpleNamespace(stage_order=EXIT_ORDER, question_budget=None),
        experience_level="serial", problem_statement="x", building_summary="x",
        industry="SaaS", customer_segment=["x"], founder_reality_signals={"a": True},
        invisible_gaps=["x"], current_challenges=["x"], linkedin_url=None,
        current_revenue=None, product_description=None,
        business_reality_signals=None, vision_1_year=None, goal_90_day=None,
    )
    missing = {row["label"] for row in validate_profile(founder)["missing"]}
    assert {"What It Is", "Business Reality", "One-Year Vision"} <= missing


def test_a_founder_with_no_stage_still_owes_neither_path():
    """The mirror. Fixing the above with a membership test instead of equality
    handed Path 2's requirements to every founder whose stage is unknown."""
    from types import SimpleNamespace

    from app.services.profile_progress import compute_progress

    founder = SimpleNamespace(
        founder_id=1, stage_id=None, profile_completed=False, stage=None,
    )
    labels = {row["label"] for row in compute_progress(founder)["fields"]}
    assert "Monthly Revenue" not in labels
    assert "One-Year Vision" not in labels


def test_founder_dna_still_places_an_exit_founder():
    """Founder DNA has no Exit bank and resolves to exactly ONE group, using
    "more than one group" as its signal that the stage is unknown. An Exit
    founder tripped that signal and had their whole Founder DNA phase resolved
    against the default as though they had never answered the stage question."""
    from types import SimpleNamespace

    from app.api.v1.founder_dna.engine import resolve_founder_dna_stage_group

    founder = SimpleNamespace(stage=SimpleNamespace(stage_order=EXIT_ORDER))
    assert (resolve_founder_dna_stage_group(founder)
            == StageGroup.STAGE_1_TO_10_PLUS.value)
