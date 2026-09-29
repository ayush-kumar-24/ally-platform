"""An idea-stage founder must not be asked about a business they have not started.

Reported from a live diagnosis. A founder whose idea existed only in their head
was asked "How do you handle customer support or service requests?", "How many
active users or customers do you currently have?" and "How do you typically
react when your startup hits a major setback?". No customers, no users, no
startup -- and `business_health` scores the blank answer as a gap.

The same shape as the team-size defect, on a different axis. `stage_scope`
withholds whole pillars and categories and does that correctly, but the
presupposition varies WITHIN a category: under `Product`, "What's the simplest
version of this you could put in front of someone today?" is written for
someone with nothing built, and "Rate how well your product currently solves
the problem" cannot be answered by them. A category filter takes both or
neither.

Migration c58d1e7b0a94 fixes seventeen questions three ways -- ten retagged off
the ideation bank, five reworded to drop the premise, two gated on team size.
These tests pin the rules rather than the seventeen, so a question added later
with the same flaw is caught.
"""

import re

import pytest

MIGRATION = "c58d1e7b0a94"
IDEATION_GROUP = "Stage 0"


def _migration():
    import importlib.util
    from pathlib import Path

    from app.core.paths import BACKEND_DIR

    matches = sorted(Path(BACKEND_DIR, "alembic", "versions").glob(f"*{MIGRATION}*.py"))
    assert len(matches) == 1, f"expected one {MIGRATION} migration, found {matches}"
    spec = importlib.util.spec_from_file_location(f"_mig_{MIGRATION}", matches[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
            g=IDEATION_GROUP,
        )
    except Exception as exc:                  # no database configured for this run
        pytest.skip(f"no database available: {exc}")
    if not rows or not rows[0][0]:
        pytest.skip("no seeded ideation questions to test against")
    return rows[0][0]


# --- the reviewed lists are sound ------------------------------------------

def test_the_three_fixes_do_not_overlap():
    """A question retagged off the bank should not also be reworded for the
    bank; the outcome would depend on statement order."""
    mig = _migration()
    reworded = {code for code, _old, _new in mig._REWORD}
    assert not (set(mig._RETAG) & reworded)
    assert not (set(mig._RETAG) & set(mig._NEEDS_A_TEAM))
    assert not (reworded & set(mig._NEEDS_A_TEAM))


def test_every_retag_records_why_it_cannot_be_answered():
    for code, why in _migration()._RETAG.items():
        assert len(why.strip()) > 20, f"{code}: {why!r} is not a reason"


def test_a_reword_actually_changes_the_text():
    for code, old, new in _migration()._REWORD:
        assert old.strip() and new.strip()
        assert old != new, f"{code} is listed as reworded but the text is identical"


def test_the_rewordings_drop_the_premise_rather_than_restating_it():
    """The point of a reword is that the founder has not started. Text still
    claiming they have would defeat it."""
    PRESUMES = re.compile(
        r"\b(your startup|this business|your company|the venture|your product)\b", re.I
    )
    for code, _old, new in _migration()._REWORD:
        assert not PRESUMES.search(new), (
            f"{code} was reworded to {new!r}, which still assumes the business exists"
        )


def test_the_rewordings_stay_short_and_plain():
    """Question text is held to plain, short wording -- the standing rule for
    this bank. A reword is a chance to comply, not an excuse to grow."""
    for code, old, new in _migration()._REWORD:
        assert len(new) <= max(110, len(old)), (
            f"{code} grew to {len(new)} characters: {new!r}"
        )


# --- the catalogue ---------------------------------------------------------

def test_no_ideation_question_asks_for_a_count_of_users_or_customers(catalogue):
    """The narrowest, least arguable version of the defect: a question whose
    answer is zero for every founder who can be asked it tells us nothing and
    reads as an accusation."""
    bad = _rows(
        """
        SELECT question_code, question_text FROM questions
        WHERE primary_stage_group = :g
          AND question_text ~* '(how many|number of).{0,30}(active users|paying customers|customers do you)'
        """,
        g=IDEATION_GROUP,
    )
    assert not bad, f"ideation questions asking for a customer count: {bad}"


def test_no_ideation_question_asks_how_the_founder_handles_something_running(catalogue):
    bad = _rows(
        """
        SELECT question_code, question_text FROM questions
        WHERE primary_stage_group = :g
          AND question_text ~* 'how do you (handle|manage) (customer support|service requests)'
        """,
        g=IDEATION_GROUP,
    )
    assert not bad, f"ideation questions about running a support function: {bad}"


def test_the_questions_needing_other_people_are_gated_wherever_they_sit(catalogue):
    """RSK-006 and IVA-060 ask about a team and about employees but sit under
    Strategic Clarity and Market Clarity, so the Team & Leadership defaults
    never reached them. Without a band, `team_scope` admits them to a founder
    working alone at every stage."""
    codes = list(_migration()._NEEDS_A_TEAM)
    ungated = _rows(
        "SELECT question_code FROM questions "
        "WHERE question_code = ANY(:codes) AND min_team_size IS NULL",
        codes=codes,
    )
    assert not ungated, (
        f"questions about a team that nothing withholds from a solo founder: {ungated}"
    )


def test_the_purpose_written_ideation_bank_was_left_alone(catalogue):
    """988 of the 1,171 questions reachable at ideation carry an `S0-` code and
    were written for that bank on purpose. The fix is confined to the legacy
    codes; touching the rest would be a content rewrite wearing a bug fix's
    clothes."""
    mig = _migration()
    touched = set(mig._RETAG) | {c for c, _o, _n in mig._REWORD} | set(mig._NEEDS_A_TEAM)
    assert not [c for c in touched if c.startswith("S0-")], (
        "the fix reaches into the purpose-written Stage 0 bank"
    )


# --- the whole operating-business family, not just seventeen questions ------
#
# c58d1e7b0a94 checked the 183 legacy-coded ideation questions and took the 988
# `S0-` coded ones on trust. Collapsing those 1,127 by code shape gives 148
# templates in two clearly different hands: `S0-XXX-0nn` for an idea with
# nothing built, and `S0-XXX-1nn`/`2nn`/`3nn` for a business already trading
# ("How did you arrive at your current price list?", "If your dispatcher left,
# what would you lose?"). 410 of the second kind were still reachable by an
# idea-stage founder. e4c9b21d8a76 moves them.

import re

OPERATING_FAMILY = re.compile(r"^S0-([A-Z]{3})-[123]\d\d(-\d)?$")

#: `S0-` codes naming a SUBJECT rather than an industry. `S0-IVA-1nn` matches
#: the number shape and is idea-stage content -- "Have you studied a failed
#: attempt at something similar?" -- so the family is industry prefix AND
#: number, never the number alone.
NOT_INDUSTRIES = frozenset(
    {"IVA", "BPL", "PRD", "PSY", "OPS", "TCI", "CMA", "RSK", "SCL"}
)


def _is_operating_family(code: str) -> bool:
    match = OPERATING_FAMILY.match(code)
    return bool(match) and match.group(1) not in NOT_INDUSTRIES


def test_the_operating_business_family_is_off_the_ideation_bank(catalogue):
    left = _rows(
        "SELECT question_code FROM questions WHERE primary_stage_group = :g "
        "ORDER BY question_code",
        g=IDEATION_GROUP,
    )
    stranded = [c for (c,) in left if _is_operating_family(c)]
    assert not stranded, (
        f"{len(stranded)} question(s) written for a trading business are still "
        f"asked of idea-stage founders, e.g. {stranded[:5]}"
    )


def test_the_idea_stage_family_was_not_swept_up_with_it(catalogue):
    """The mirror. `S0-IVA-100` to `S0-IVA-114` match the family's number shape
    and are idea-stage questions; a first pass matching the number alone moved
    fifteen of them. Losing good ideation content to a too-broad rule would be
    a worse outcome than the defect."""
    kept = {
        c for (c,) in _rows(
            "SELECT question_code FROM questions WHERE primary_stage_group = :g",
            g=IDEATION_GROUP,
        )
    }
    survivors = [c for c in kept if c.startswith("S0-IVA-1")]
    assert len(survivors) >= 10, (
        "the S0-IVA-1nn idea-stage questions were swept out with the operating "
        f"family; only {sorted(survivors)} remain"
    )


def test_an_idea_stage_founder_still_has_plenty_to_be_asked(catalogue):
    """Moving 410 questions out must not leave the bank too thin to fill a
    diagnosis. The ideation budget is 14."""
    from app.api.v1.diagnosis.stage_scope import SCOPE_BY_STAGE_ORDER

    scope = SCOPE_BY_STAGE_ORDER[1]
    reachable = _rows(
        """
        SELECT count(*) FROM questions q
        JOIN problems p ON p.problem_id = q.problem_id
        WHERE q.primary_stage_group = :g
          AND p.pillar_id = ANY(:pillars)
          AND q.category <> ALL(:withheld)
        """,
        g=IDEATION_GROUP,
        pillars=list(scope.pillars),
        withheld=list(scope.withheld_categories or ()) or [""],
    )[0][0]
    assert reachable > 200, (
        f"only {reachable} questions reachable at ideation; the bank is now too "
        "thin to build a varied diagnosis from"
    )


# --- the one admitted exception --------------------------------------------
#
# 139 questions sit under Revenue Maturity problems and are categorised
# `Idea & Validation`. Their text is not about revenue -- "Where would you
# actually get your product from?", "How would the product reach the customer,
# and who pays for that?" -- and they exist in 24 industry flavours, so they
# are the only industry-specific validation content an ideation founder can
# get. Ideation withholds Revenue Maturity correctly, and was locking these out
# as a side effect of where their problems are filed rather than what they ask.

IDEA_AND_VALIDATION = "Idea & Validation"
REVENUE_MATURITY = 3


def _ideation_scope():
    from app.api.v1.diagnosis.stage_scope import SCOPE_BY_STAGE_ORDER

    return SCOPE_BY_STAGE_ORDER[1]


def test_validation_questions_are_admitted_despite_their_pillar():
    assert _ideation_scope().admits(REVENUE_MATURITY, IDEA_AND_VALIDATION)


def test_the_rest_of_revenue_maturity_stays_out():
    """The exception is one category, not the pillar. Business Model Design
    presumes a price already being charged."""
    scope = _ideation_scope()
    for category in ("Business Model Design", "Sales & Revenue", None):
        assert not scope.admits(REVENUE_MATURITY, category)


def test_team_and_leadership_is_not_admitted_by_the_same_door():
    """The rule is deliberately (pillar, category), not "any withheld pillar's
    Idea & Validation questions". A founder with no team has no more business
    answering those than a founder with no revenue has answering about
    pricing."""
    assert not _ideation_scope().admits(5, IDEA_AND_VALIDATION)


def test_pillars_in_scope_are_unaffected():
    scope = _ideation_scope()
    for pillar in scope.pillars:
        assert scope.admits(pillar, IDEA_AND_VALIDATION)
        assert scope.admits(pillar, "anything at all")


def test_the_exception_is_switched_off_for_every_later_stage():
    """Stages from Validation on assess Revenue Maturity outright, so the
    exception must never be the reason a question is admitted there -- it would
    be dead code pretending to be a rule."""
    from app.api.v1.diagnosis.stage_scope import SCOPE_BY_STAGE_ORDER

    for order, scope in SCOPE_BY_STAGE_ORDER.items():
        if order == 1:
            continue
        assert REVENUE_MATURITY in scope.pillars, (
            f"stage {order} withholds Revenue Maturity; the ideation exception "
            "would silently start applying there too"
        )


def test_an_ideation_founder_actually_gains_the_questions(catalogue):
    scope = _ideation_scope()
    gained = _rows(
        """
        SELECT count(*) FROM questions q
        JOIN problems p ON p.problem_id = q.problem_id
        WHERE q.primary_stage_group = :g
          AND p.pillar_id = :pillar
          AND q.category = :cat
        """,
        g=IDEATION_GROUP,
        pillar=REVENUE_MATURITY,
        cat=IDEA_AND_VALIDATION,
    )[0][0]
    assert gained > 100, (
        f"only {gained} validation questions on the Revenue Maturity shelf; "
        "the set this exception exists for has moved or shrunk"
    )
    assert scope.admits(REVENUE_MATURITY, IDEA_AND_VALIDATION)


def test_the_scorer_still_withholds_a_band_for_a_pillar_the_stage_skips():
    """Admitting the questions must not publish a Revenue Maturity verdict on a
    founder who has no revenue. The report has already told them that pillar
    was not assessed."""
    import inspect

    from app.api.v1.reasoning.engines.business_health import BusinessHealthScorer

    source = inspect.getsource(BusinessHealthScorer)
    assert "pillar.pillar_id not in scope.pillars" in source, (
        "nothing stops an admitted question's answers banding a pillar the "
        "stage does not assess"
    )
