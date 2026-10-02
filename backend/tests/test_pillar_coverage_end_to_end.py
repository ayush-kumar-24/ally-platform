"""Every pillar a founder is scored on gets enough answers to score.

WHY THIS EXISTS AS AN END-TO-END TEST. `test_industry_opening_block` already
covers the block thoroughly, against fakes, one bound at a time. It cannot catch
what a real founder meets, because the thing that decides coverage is the
interaction of four parts over twenty turns: the opening block's size, how the
founder's INDUSTRY BANK happens to be spread across pillars, the round-robin's
per-pillar term, and the stage budget. Each is correct on its own.

THE FAILURE IT IS WRITTEN AGAINST. A pillar below
`MIN_ANSWERS_PER_PILLAR_SCORE` is not a degraded score; it prints as "not
assessed", and a founder who answered twenty questions gets a report with
visible holes in it. The industry banks hold NO Market Clarity questions for any
of the three founders below, so Market Clarity is the pillar that depends
entirely on the round-robin recovering after the block closes. That is the exact
path no unit test exercises.

A NOTE ON MEASURING THIS, because it is easy to get wrong and I did. The opening
block reads `sessions.questions_answered_count`, which `submit_answer` derives
from the answer rows. A harness that inserts into `answers` without maintaining
that counter leaves it at 0, the block never closes, and the diagnosis spends
every turn inside the industry bank -- which looks exactly like a catastrophic
coverage bug and is not one. `_answer` below maintains the counter the way
production does, and `test_the_opening_block_actually_closes` pins that
specifically so a future harness cannot quietly reintroduce the illusion.

THE TIGHTNESS IS REAL THOUGH, and these numbers are why. Validation spends 20
questions on 6 pillars needing 3 each: 18 of the 20 must land well. The measured
result is 3 in four pillars and 4 in two -- correct, with two questions of
slack in the whole diagnosis. `MIN_QUESTIONS_PER_PILLAR` (2), the reserve the
block keeps back, is also one BELOW `MIN_ANSWERS_PER_PILLAR_SCORE` (3), so the
guarantee is weaker than the requirement and the margin above comes from the
block's own questions landing across pillars rather than from the bound. Raising
the reserve to 3 would cut the Validation block from 8 to 2; raising the budget
to 26 would keep both. That is a product decision, recorded here rather than
decided quietly.
"""

import pytest
from sqlalchemy import text

from app.core.config import settings

#: Real founders, chosen so that between them they cover the three shapes that
#: stress coverage differently: the tightest budget, a second industry, and the
#: two-bank Exit case.
FOUNDERS = [
    pytest.param(
        "pytest-coverage-ravi@ally-test.invalid", 2, "healthtech",
        "Appointment booking and reminders for small clinics", "solo", None,
        id="validation-solo-software-seller",
    ),
    pytest.param(
        "pytest-coverage-priya@ally-test.invalid", 5, "foodtech",
        "Small-batch banana chips sold online, direct to customers.", "solo", "1L_5L",
        id="growth-solo-food-maker",
    ),
    pytest.param(
        "pytest-coverage-suresh@ally-test.invalid", 8, "manufacturing",
        "A 31-year-old auto-component workshop supplying tier-1 manufacturers.",
        "11_25", "25L_1Cr",
        id="exit-with-staff",
    ),
]


def _db():
    from app.db.session import SessionLocal

    return SessionLocal()


@pytest.fixture
def seeded():
    """Skip unless there is a real question bank to run against."""
    try:
        db = _db()
    except Exception as exc:                                   # noqa: BLE001
        pytest.skip(f"no database available: {exc}")
    try:
        n = db.execute(text("SELECT count(*) FROM questions")).scalar()
    except Exception as exc:                                   # noqa: BLE001
        pytest.skip(f"no database available: {exc}")
    finally:
        db.close()
    if not n:
        pytest.skip("no seeded questions to run against")
    return n


def _make_founder(db, email, stage_order, industry, description, team, revenue):
    import uuid

    db.execute(text("DELETE FROM founders WHERE email = :e"), {"e": email})
    stage_id = db.execute(
        text("SELECT stage_id FROM founder_stages WHERE stage_order = :o"),
        {"o": stage_order},
    ).scalar()
    # `industry_mapped_id` is what `industry_scope` reads; the free-text
    # `industry` column alone gives the founder no industry bank and therefore
    # no opening block, which would make this test pass for the wrong reason.
    industry_id = db.execute(
        text("SELECT industry_id FROM industries WHERE industry_code = :c"),
        {"c": industry},
    ).scalar()
    assert industry_id is not None, f"unknown industry_code {industry!r}"
    founder_id = db.execute(
        text(
            "INSERT INTO founders (user_id, full_name, email, stage_id, team_size,"
            " current_revenue, industry, industry_mapped_id, product_description,"
            " profile_completed, created_at, updated_at)"
            " VALUES (:u, 'Coverage Test', :e, :s, :t, :r, :i, :m, :d, true,"
            " now(), now()) RETURNING founder_id"
        ),
        {"u": str(uuid.uuid4()), "e": email, "s": stage_id, "t": team,
         "r": revenue, "i": industry, "m": industry_id, "d": description},
    ).scalar()
    session_id = db.execute(
        text(
            "INSERT INTO sessions (founder_id, status, questions_answered_count)"
            " VALUES (:f, 'in_progress', 0) RETURNING session_id"
        ),
        {"f": founder_id},
    ).scalar()
    db.commit()
    return founder_id, session_id


def _answer(db, session_id, founder_id, question_id):
    """Record an answer the way `submit_answer` does.

    The counter is DERIVED from the rows, not incremented, matching
    service.py. Leaving it unmaintained is what makes the opening block look
    like it never closes -- see the module docstring.
    """
    db.execute(
        text(
            "INSERT INTO answers (session_id, founder_id, question_id,"
            " answer_text, answered_at) VALUES (:s, :f, :q, 'coverage test', now())"
        ),
        {"s": session_id, "f": founder_id, "q": question_id},
    )
    db.execute(
        text(
            "UPDATE sessions SET questions_answered_count ="
            " (SELECT count(*) FROM answers WHERE session_id = :s)"
            " WHERE session_id = :s"
        ),
        {"s": session_id},
    )
    db.commit()


def _run_diagnosis(db, email, stage_order, industry, description, team, revenue):
    """Drive the real engine to the stage's budget. Returns {pillar_id: count}."""
    from app.api.v1.diagnosis.engine import QuestionSelectionEngine
    from app.api.v1.diagnosis.repository import DiagnosisRepository
    from app.models import DiagnosisSession, Founders

    founder_id, session_id = _make_founder(
        db, email, stage_order, industry, description, team, revenue)
    founder = db.query(Founders).filter(Founders.founder_id == founder_id).one()
    session = db.query(DiagnosisSession).filter(
        DiagnosisSession.session_id == session_id).one()

    engine = QuestionSelectionEngine(DiagnosisRepository(db))
    budget = settings.question_budget(getattr(founder.stage, "question_budget", None))

    pillar_of = dict(db.execute(text("SELECT problem_id, pillar_id FROM problems")).all())
    counts, seen = {}, set()
    for _ in range(budget):
        question = engine.select_next_question(session, founder)
        if question is None or question.question_id in seen:
            break
        seen.add(question.question_id)
        pillar = pillar_of.get(question.problem_id)
        counts[pillar] = counts.get(pillar, 0) + 1
        _answer(db, session_id, founder_id, question.question_id)
        db.refresh(session)
    return counts, budget, founder


@pytest.mark.parametrize(
    "email,stage_order,industry,description,team,revenue", FOUNDERS)
def test_every_pillar_in_scope_clears_the_scoring_floor(
    seeded, email, stage_order, industry, description, team, revenue
):
    from app.api.v1.diagnosis.stage_scope import resolve_scope
    from app.api.v1.diagnosis.team_scope import score_is_withheld

    db = _db()
    try:
        counts, budget, founder = _run_diagnosis(
            db, email, stage_order, industry, description, team, revenue)

        floor = max(1, settings.MIN_ANSWERS_PER_PILLAR_SCORE)
        scope = resolve_scope(founder)
        in_scope = scope.pillars if scope is not None else {1, 2, 3, 4, 5, 6}

        short = {
            pillar: counts.get(pillar, 0)
            for pillar in in_scope
            # A pillar the report deliberately withholds needs no evidence:
            # Team & Leadership is "not assessed" for a founder working alone
            # whatever they answer, which is team_scope's whole purpose.
            if not score_is_withheld(pillar, founder)
            and counts.get(pillar, 0) < floor
        }
        assert not short, (
            f"after {sum(counts.values())} of {budget} questions these pillars "
            f"cannot be scored and will print as 'not assessed': {short}"
        )
    finally:
        db.execute(text("DELETE FROM founders WHERE email = :e"), {"e": email})
        db.commit()
        db.close()


def test_the_opening_block_actually_closes(seeded):
    """The block is a head start, not the whole diagnosis.

    Pinned separately because the way it fails is silent. The industry banks
    hold no Market Clarity questions for any founder tested here, so a block
    that never closes does not error or run short -- it returns twenty perfectly
    good industry questions and simply never reaches a pillar, and the hole only
    appears in the report.
    """
    from app.api.v1.diagnosis.engine import QuestionSelectionEngine
    from app.api.v1.diagnosis.repository import DiagnosisRepository
    from app.models import DiagnosisSession, Founders

    email = "pytest-coverage-block@ally-test.invalid"
    db = _db()
    try:
        founder_id, session_id = _make_founder(
            db, email, 2, "healthtech",
            "Appointment booking and reminders for small clinics", "solo", None)
        founder = db.query(Founders).filter(Founders.founder_id == founder_id).one()
        session = db.query(DiagnosisSession).filter(
            DiagnosisSession.session_id == session_id).one()
        engine = QuestionSelectionEngine(DiagnosisRepository(db))

        size = engine._opening_block_size(session, founder)
        assert size > 0, "this founder's industry should open the diagnosis"

        for _ in range(size):
            question = engine.select_next_question(session, founder)
            assert question is not None
            _answer(db, session_id, founder_id, question.question_id)
            db.refresh(session)

        assert engine._answered_count(session) >= size, (
            "the answer counter did not follow the recorded answers, so the "
            "block cannot close -- see this module's docstring"
        )
    finally:
        db.execute(text("DELETE FROM founders WHERE email = :e"), {"e": email})
        db.commit()
        db.close()
