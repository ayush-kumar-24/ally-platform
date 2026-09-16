"""The weak counterpart at Early Traction -- the other half of a comparison
that had only one side.

`traction` proved COVERAGE at stage 4: report #96 was the first run in this
project's history to assess six pillars of six, a hundred per cent of the
Business DNA model. It proved nothing whatever about DISCRIMINATION there.

weak and strong are a quality pair at Ideation, and the engine separates them
cleanly -- health 20 against 92, Critical Gap against Strong, eight root
causes against two, reproduced across two independent runs. At Early Traction
there was one persona, so a run could only ever come back "strong". An engine
that scored every stage-4 founder well would have produced results identical
to the ones we had, and nothing in the suite would have noticed.

`weak_traction` answers the same thirty-eight subjects as `traction`, slot for
slot. The founder is not failing: they have sixty-odd paying customers, four
staff and revenue. They are running all of it on memory and reaction -- no
number anybody measured, nothing written down, every system living in whoever
touched it last, every problem noticed after it cost something.

That is the interesting weak case at this stage, and it is the one the
six-pillar model should be able to see.
"""

import pytest

from scripts.e2e_journey_check import (
    ANSWER_BANK,
    FALLBACKS,
    PERSONAS,
    TRACTION_ANSWERS,
    WEAK_TRACTION_ANSWERS,
    _CURRENT_PROBLEM_TOPICS,
    _TRACTION_TOPICS,
    match_answer,
)
from tests.test_traction_persona import STAGE_4_QUESTIONS

PERSONA = "weak_traction"


def topic_index(question: str) -> int:
    answer, matched = match_answer(question, PERSONA)
    if not matched:
        return -1
    return [a for _, a in ANSWER_BANK[PERSONA]].index(answer)


def test_the_persona_is_selectable():
    assert PERSONA in PERSONAS
    assert PERSONA in FALLBACKS
    assert PERSONA in ANSWER_BANK


def test_it_covers_exactly_the_same_topics_as_traction():
    """The pair is only a QUALITY comparison if the subjects are identical.

    If the two personas differed in what they talk about as well as how well
    they talk about it, a difference in the report would not tell you which
    of the two caused it -- which is the whole failure mode this file exists
    to rule out.
    """
    assert [t for t, _ in ANSWER_BANK[PERSONA]] == \
           [t for t, _ in ANSWER_BANK["traction"]]
    assert [t for t, _ in ANSWER_BANK[PERSONA]] == \
        list(_TRACTION_TOPICS + _CURRENT_PROBLEM_TOPICS)


def test_no_answer_is_shared_with_traction():
    """A slot answered identically in both is a slot the comparison is blind
    to, and it would read as agreement rather than as a gap in the test."""
    assert len(WEAK_TRACTION_ANSWERS) == len(TRACTION_ANSWERS)
    shared = [i for i, (w, t)
              in enumerate(zip(WEAK_TRACTION_ANSWERS, TRACTION_ANSWERS))
              if w == t]
    assert not shared, f"slots identical in both personas: {shared}"


@pytest.mark.parametrize("question,expected", STAGE_4_QUESTIONS,
                         ids=[q[:45] for q, _ in STAGE_4_QUESTIONS])
def test_stage_4_question_routing(question, expected):
    """The same thirty real questions from report #96, routed through the weak
    set. They must land in the same slots -- a persona that fell back where
    its counterpart matched would look weak for the wrong reason."""
    got = topic_index(question)
    assert got != -1, "fell through to the generic answer"
    assert got == expected, (
        f"routed to slot {got}, expected {expected}\n"
        f"  landed on: {ANSWER_BANK[PERSONA][got][1][:90]}...")


def test_no_stage_4_question_falls_back():
    fell_back = [q for q, _ in STAGE_4_QUESTIONS if topic_index(q) == -1]
    assert not fell_back, f"{len(fell_back)} fall back: {fell_back}"


def test_the_answers_lack_the_evidence_traction_carries():
    """Not a style check. Each of these is a thing a pillar scores on, and
    the weak set has to be weak for the reason the engine measures -- an
    absence of evidence -- rather than merely being shorter or gloomier."""
    blob = " ".join(WEAK_TRACTION_ANSWERS).lower()
    for absent in ("written down, in one place", "reviewed monthly",
                   "instrumented", "on a rota", "same fifteen minutes"):
        assert absent not in blob, (
            f"the weak set is showing evidence it should not have: {absent!r}")
    for present in ("i'd have to look", "written down", "in my head",
                    "meaning to"):
        assert present in blob, (
            f"the weak set no longer sounds like {present!r}")


def test_it_is_a_real_business_and_not_a_pre_launch_one():
    """The stage has to be right or the run measures stage mismatch against
    the confidence engine's stage_coherence_factor instead of answer quality.

    This founder has customers, staff and revenue. They are bad at running
    them. Those are different failures and only the second one is under test.
    """
    blob = " ".join(WEAK_TRACTION_ANSWERS).lower()
    for present in ("paying", "support", "revenue", "refund"):
        assert present in blob, f"weak_traction does not sound like a business"
    for absent in ("i have not started", "half-finished document",
                   "landing page"):
        assert absent not in blob, (
            f"weak_traction is answering as a pre-launch founder: {absent!r}")


def test_the_fallback_is_topic_neutral():
    """It must not smuggle in evidence, or absence of it, about a dimension
    the question never raised."""
    fallback = FALLBACKS[PERSONA].lower()
    for leak in ("customer", "revenue", "team", "pricing", "churn", "cash"):
        assert leak not in fallback, f"the fallback names {leak!r}"


def test_every_current_problem_topic_has_a_weak_traction_answer():
    bank_topics = [t for t, _ in ANSWER_BANK[PERSONA]]
    for topic in _CURRENT_PROBLEM_TOPICS:
        assert topic in bank_topics
