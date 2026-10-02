"""No industry question may assume one kind of business within its industry.

A founder picks their industry at onboarding and the diagnosis draws on that
industry's bank. An industry is not a business model, and 64 of those questions
were written as though it were. Found by running real diagnoses:

    Ravi sells booking software to physiotherapy clinics, and was asked "Out of
    100 patients, how many use you a second time?" and "How much of your week
    goes on clinical work?". He has no patients and is not a clinician.

    Priya sells banana chips online, and was asked what happened to "covers and
    waste" the last time she "cut the menu". She has no restaurant.

REWORDED RATHER THAN GATED, the same decision test_board_assumptions protects
and for a sharper reason. Gating needs a fact nobody collects -- whether the
founder operates in the industry or sells into it -- and the questions do not
need it: repeat usage, cost-to-serve and range discipline are real subjects for
both. Only the noun excluded anyone.

THE THREE BUCKETS, AND WHY A TEST FOR EACH. Reading all 128 flagged questions
split them three ways, and each way can rot differently:

    64 reworded     -- could be reworded into something that still presumes, or
                       into something that no longer measures what it measured.
    37 already fine -- could be "fixed" later by somebody keyword-matching, which
                       is how this bank has been got wrong twice before.
    27 unfixable    -- the subject really IS a kitchen or a fleet. These need a
                       scoping axis nobody has built, so the risk is that they
                       quietly stop being tracked.

THE SWEEP AT THE BOTTOM IS THE ONE THAT PROTECTS NEW CONTENT. The three buckets
are a closed list of what was reviewed in October 2026; the sweep re-runs the
detection over the live bank and fails on anything not on that list. A new
industry question written with "your kitchen" in it fails here, which is the
only way this does not silently regrow.
"""

import re

import pytest

MIGRATION = "a3f7b21c6d84"
REVIEW_DOC = "docs/drafts/industry-question-rewording.md"

#: Names a role the founder may not hold or premises they may not have. The
#: screen that found the 128; kept here so the sweep below uses the same one.
#:
#: It is deliberately crude and over-matches -- "covers" catches "covers every
#: legal duty" -- because a reviewer reading a false positive costs nothing and
#: a missed question ships. Judgement lives in the three buckets, not here.
PRESUMES_A_MODEL = re.compile(
    r"\b(patients?|menu|diners|footfall|guests|students|pupils|passengers"
    r"|tenants|policyholders|borrowers|prescriptions?|crops?|livestock|acres"
    r"|kitchen|storefront|clinic|clinical|clinician|classroom|ward|showroom"
    r"|dish|dishes|covers"
    r"|your (store|stores|outlet|outlets|shop|branch|branches|site|sites"
    r"|premises|warehouse|fleet|vehicles|drivers|riders|farm|factory|plant"
    r"|restaurant|cafe|hotel|salon))\b",
    re.I,
)

#: Reviewed and judged to work as written for somebody selling INTO the
#: industry: it names who ultimately pays, what the regulator requires, who the
#: end beneficiary is, or who you are selling to. Three are plain false
#: positives on "covers".
ALREADY_FINE = frozenset({
    "S0-AGR-006", "S0-AGR-011", "S0-AGR-012", "S0-AGR-208-1", "S01-AGR-017",
    "S10-AGR-208-1", "S10-DLV-010", "S0-SPF-303-1", "S10-LGL-011",
    "S10-EDU-304-2", "S0-HLT-006", "S0-HLT-008", "S0-HLT-010", "S0-HLT-015",
    "S0-HLT-307-1", "S0-HLT-307-2", "S01-HLT-001", "S10-HLT-007", "S10-HLT-010",
    "S10-HLT-011", "S10-HLT-012", "S10-HLT-013", "S10-HLT-014", "S10-HLT-016",
    "S10-HLT-017", "S10-HLT-019", "S10-HLT-024", "S10-HLT-025", "S0-PHM-014",
    "S01-PHM-018", "S01-GAM-013", "S10-AUT-009", "S0-TRV-006", "S0-TRV-011",
    "S10-MFG-016", "S10-MFG-304-2", "S10-TEL-301-1",
})

#: Reviewed and WITHHELD rather than reworded, from founders who do not run the
#: industry's core operation. Two kinds, deliberately together here because the
#: review treated them the same way in the end:
#:
#:   49 whose original wording was RESTORED. They had been reworded -- patients
#:   to customers, guests to customers, dish and menu to item and range -- and
#:   that removed the premise and the specificity in one stroke. A homestay
#:   owner reading "Do you ask happy guests to leave a review?" is understood;
#:   reading "happy customers" could be any business alive. The founder who
#:   prompted the fix is the minority, since most people who pick Healthcare ARE
#:   a clinic, so rewording for everybody protected the exception by flattening
#:   the majority.
#:
#:   27 that could never have been reworded. The subject really is a kitchen, a
#:   fleet, a clinical rota or a second location, and no neutral noun keeps the
#:   question meaningful. "Is there a maintenance calendar for your fleet?"
#:   cannot be rewritten for a founder with no vehicles, only withheld.
#:
#: Tagged `requires_operating_role` (71) or `requires_multiple_locations` (5) by
#: migration b5d4e31a7c92, and gated by `business_model_scope`.
WITHHELD_FROM_NON_OPERATORS = frozenset({
    "S0-DLV-304-1", "S0-ECM-006", "S0-ECM-009", "S0-EDU-304-1",
    "S0-FNB-006", "S0-FNB-102-1", "S0-FNB-102-2", "S0-FNB-104-1",
    "S0-FNB-104-2", "S0-FNB-301-1", "S0-FNB-303-2", "S0-FNB-306-2",
    "S0-HLT-302-1", "S0-RTL-307-1", "S0-TRV-005", "S0-TRV-007",
    "S0-TRV-303-2", "S01-DLV-006", "S01-DLV-010", "S01-DLV-013",
    "S01-FNB-019", "S01-FNB-102-1", "S01-FNB-104-2", "S01-FNB-110-1",
    "S01-FNB-301-2", "S01-FNB-302-2", "S01-FNB-303-2", "S01-HLT-006",
    "S01-HLT-007", "S01-HLT-008", "S01-HLT-009", "S01-HLT-010",
    "S01-HLT-011", "S01-HLT-014", "S01-HLT-015", "S01-HLT-016",
    "S01-HLT-017", "S01-HLT-018", "S01-LOG-009", "S01-LOG-012",
    "S01-RTL-008", "S01-TRV-004", "S01-TRV-010", "S01-TRV-012",
    "S01-TRV-016", "S01-TRV-302-1", "S10-CEL-005", "S10-DLV-306-1",
    "S10-ECM-003", "S10-EDU-307-1", "S10-FNB-004", "S10-FNB-006",
    "S10-FNB-020", "S10-FNB-023", "S10-FNB-102-1", "S10-FNB-102-2",
    "S10-FNB-307-2", "S10-HLT-002", "S10-HLT-003", "S10-HLT-005",
    "S10-HLT-015", "S10-HLT-302-2", "S10-HLT-303-1", "S10-HLT-305-1",
    "S10-LOG-011", "S10-LOG-306-1", "S10-PRP-203-1", "S10-PRP-206-2",
    "S10-RTL-301-1", "S10-RTL-303-2", "S10-RTL-304-1", "S10-RTL-304-2",
    "S10-TRV-004", "S10-TRV-013", "S10-TRV-015", "S10-TRV-305-1",
})

#: Two rewordings still name a clinic or a patient, because both questions LIST
#: business types or payer types and naming them is the whole question.
DELIBERATELY_STILL_NAMES_ONE = frozenset({"S0-HLT-003", "S0-HLT-009"})

INDUSTRY_CODE = re.compile(r"^S\d+-[A-Z]{3}-")


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
def live_questions():
    """`question_code -> question_text` for the industry banks only."""
    try:
        rows = _rows(
            "SELECT question_code, question_text FROM questions "
            "WHERE question_code ~ '^S[0-9]+-[A-Z]{3}-'"
        )
    except Exception as exc:                                   # noqa: BLE001
        pytest.skip(f"no database available: {exc}")
    if not rows:
        pytest.skip("no seeded questions to test against")
    return dict(rows)


# --- the reviewed list is sound --------------------------------------------

def test_every_rewording_started_from_a_real_presumption():
    """Nothing belongs on this list that was not actually presuming a business
    model -- otherwise it is a wording change wearing a correctness fix's
    clothes, and it belongs in the plain-language pass the team owns."""
    for code, old, _new in _migration()._REWORD:
        assert PRESUMES_A_MODEL.search(old), (
            f"{code} was reworded but its old text presumed nothing: {old!r}"
        )


def test_no_rewording_leaves_the_presumption_behind():
    for code, _old, new in _migration()._REWORD:
        if code in DELIBERATELY_STILL_NAMES_ONE:
            continue
        hit = PRESUMES_A_MODEL.search(new)
        assert hit is None, (
            f"{code} was reworded to {new!r}, which still presumes "
            f"a business model via {hit.group(0)!r}"
        )


def test_every_rewording_actually_changes_the_text():
    for code, old, new in _migration()._REWORD:
        assert old != new, f"{code} is listed as reworded but the text is unchanged"


def test_the_three_buckets_do_not_overlap():
    """A question is reworded, or fine, or needs scoping. Never two of those --
    an overlap means somebody changed one bucket and forgot the others."""
    reworded = {code for code, _, _ in _migration()._REWORD}
    for a, b, names in (
        (reworded, ALREADY_FINE, "reworded / already fine"),
        (reworded, WITHHELD_FROM_NON_OPERATORS, "reworded / needs scoping"),
        (ALREADY_FINE, WITHHELD_FROM_NON_OPERATORS, "already fine / needs scoping"),
    ):
        assert not (a & b), f"{names} overlap on {sorted(a & b)}"


def test_the_review_covered_every_question_it_claims_to():
    """128 flagged, 128 accounted for. The arithmetic is the whole claim the
    review document makes, so it is pinned here rather than left in prose."""
    reworded = {code for code, _, _ in _migration()._REWORD}
    assert len(reworded) == 15, "the rewordings that lose no specificity"
    assert len(ALREADY_FINE) == 37, "flagged by the word, not actually broken"
    assert len(WITHHELD_FROM_NON_OPERATORS) == 76, "withheld, not reworded"
    assert len(reworded | ALREADY_FINE | WITHHELD_FROM_NON_OPERATORS) == 128


# --- the live bank matches the review ---------------------------------------

def test_the_rewordings_are_live(live_questions):
    for code, _old, new in _migration()._REWORD:
        assert code in live_questions, f"{code} is reworded but not in the bank"
        assert live_questions[code] == new, (
            f"{code} should read {new!r} but reads {live_questions[code]!r} -- "
            f"has {MIGRATION} run?"
        )


def test_every_withheld_question_is_actually_tagged(live_questions):
    """The gate reads the two flags, not this list, so a question on this list
    with neither flag set is withheld from nobody -- and reads, to a software
    founder, as being asked about a kitchen they do not have."""
    from sqlalchemy import text as _t

    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        tagged = {
            code for (code,) in db.execute(_t(
                "SELECT question_code FROM questions "
                "WHERE requires_operating_role OR requires_multiple_locations"
            )).all()
        }
    finally:
        db.close()
    assert tagged == WITHHELD_FROM_NON_OPERATORS, (
        f"tagged but not reviewed: {sorted(tagged - WITHHELD_FROM_NON_OPERATORS)}; "
        f"reviewed but not tagged: {sorted(WITHHELD_FROM_NON_OPERATORS - tagged)}"
    )


def test_no_new_industry_question_presumes_a_business_model(live_questions):
    """THE SWEEP. The three buckets are a closed record of the October 2026
    review; this re-runs the detection over the live bank and fails on anything
    that is not on it.

    A question added later with "your kitchen" or "your drivers" in it lands
    here, which is the only thing standing between this fix and the defect
    growing straight back as the banks are extended.

    If you are reading this because the test failed: the new question either
    needs rewording (put the pair in a migration), or it is fine as written and
    belongs in ALREADY_FINE with a one-line reason, or its subject really is a
    kitchen and it belongs in WITHHELD_FROM_NON_OPERATORS. Do not widen
    PRESUMES_A_MODEL to make it pass.
    """
    reviewed = (
        {code for code, _, _ in _migration()._REWORD}
        | ALREADY_FINE
        | WITHHELD_FROM_NON_OPERATORS
    )
    unreviewed = sorted(
        code for code, text_ in live_questions.items()
        if INDUSTRY_CODE.match(code)
        and PRESUMES_A_MODEL.search(text_)
        and code not in reviewed
    )
    assert not unreviewed, (
        f"{len(unreviewed)} industry question(s) presume a business model and "
        f"were never reviewed: {unreviewed}. See {REVIEW_DOC}."
    )
