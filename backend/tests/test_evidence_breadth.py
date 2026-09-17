"""Semantic regression tests for evidence breadth (Phase A).

These assert PROPERTIES, never percentages or wording, so they survive a change
to the weights they are meant to govern.

The failure they exist to catch, reproduced live in two QA runs:

    detection_score is a mean over the negative evidence, so it divides breadth
    out. One Red scores 2/(2*1) = 1.00. Six Ambers score 6/(2*6) = 0.50. An
    isolated signal therefore outranks converging ones -- which is what put
    "Weak Discovery Skills" above segmentation for the ComplyFlow founder, and
    "No Defensible Competitive Moat" above founder dependency for the logistics
    one.

Phase A does not fix that. It records what the mean discards
(`independent_signal_count`, `evidence_mass`) so the ranking layer has
something to weigh in Phase B. The tests split accordingly:

  * tests of the MEASUREMENT pass now -- breadth is recorded correctly;
  * tests of the RANKING are marked xfail(strict=True) -- they must fail while
    the old formula stands, and must start passing when Phase B lands. Strict
    means an unexpected pass is itself a failure, so Phase B cannot be declared
    done by accident.

The three scenarios are the QA personas, reduced to the shape that matters. They
are not transcripts: a regression test that depended on a live model would be
measuring the model.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.v1.reasoning.engines.root_cause import StandardRootCauseEngine
from app.api.v1.reasoning.schemas import AnswerClassification, CategoryRisk
from app.models.enums import ScoreLabel

D = Decimal

# Band scores as the config resolves them: Green 0, Amber 1, Red 2.
GREEN, AMBER, RED = D("0"), D("1"), D("2")


def q(question_id: int, root_cause_id: int, category: str):
    """A question bank row, reduced to what detection reads off it."""
    return SimpleNamespace(question_id=question_id, root_cause_id=root_cause_id,
                           category=category, is_distress_tagged=False,
                           follow_up_question_id=None)


def ans(answer_id: int, question_id: int, score: Decimal):
    label = (ScoreLabel.GREEN if score == GREEN
             else ScoreLabel.AMBER if score == AMBER else ScoreLabel.RED)
    return AnswerClassification(
        answer_id=answer_id, question_id=question_id, label=label, score=score,
        is_distress_flagged=False,
    )


def ctx():
    """Focusing disabled: these tests are about scoring, not candidate culling."""
    branching = SimpleNamespace(root_cause_min_detection_confidence=D("0"),
                                root_cause_max_candidates=0,
                                # Real value from scoring_rules; these tests are
                                # not about the amber-cluster tag.
                                amber_cluster_trigger=3)
    return SimpleNamespace(config=SimpleNamespace(branching=branching))


def detect(questions, answers, risks=()):
    engine = StandardRootCauseEngine(repository=None)
    qmap = {x.question_id: x for x in questions}
    return {d.root_cause_id: d
            for d in engine.detect(list(answers), list(risks), qmap, ctx())}


# --- Siddharth / ComplyFlow -------------------------------------------------
#
# RC 1 -- "weak discovery": ONE Red, one dimension. The isolated signal.
# RC 2 -- "unclear ICP":    SIX Ambers across six distinct dimensions, which is
#         what the clean transcript actually contained (segmentation, best
#         customer, team description, untested problem-fit, why-these-42,
#         research cadence).

SID_QUESTIONS = [
    q(101, 1, "Sales & Revenue"),
    q(201, 2, "Target Customer & ICP"),
    q(202, 2, "Go-To-Market"),
    q(203, 2, "Product"),
    q(204, 2, "Business Model Design"),
    q(205, 2, "Competitive Awareness"),
    q(206, 2, "Business Planning"),
]
SID_ANSWERS = [ans(1, 101, RED)] + [
    ans(i, qid, AMBER) for i, qid in enumerate(range(201, 207), start=2)
]


def test_siddharth_breadth_is_recorded_for_the_converging_cause():
    """The measurement Phase A adds: six dimensions vs one."""
    d = detect(SID_QUESTIONS, SID_ANSWERS)
    assert d[2].independent_signal_count == 6
    assert d[1].independent_signal_count == 1


def test_siddharth_evidence_mass_favours_the_converging_cause():
    """Mass is the un-normalised sum -- six Ambers (6) outweigh one Red (2).
    This is precisely the quantity detection_score divides away."""
    d = detect(SID_QUESTIONS, SID_ANSWERS)
    assert d[2].evidence_mass > d[1].evidence_mass


def test_siddharth_detection_score_still_inverts_them():
    """Characterises the defect rather than asserting it is correct.

    Kept so the inversion is documented in the suite: if someone changes the
    mean without changing the ranking, this test tells them what they changed.
    """
    d = detect(SID_QUESTIONS, SID_ANSWERS)
    assert d[1].detection_score > d[2].detection_score


@pytest.mark.xfail(strict=True, reason="Phase B: ranking has no breadth factor")
def test_siddharth_converging_evidence_outranks_the_isolated_signal():
    """The property the whole exercise is for.

    Six independent dimensions must beat one isolated Red. Asserted on
    detection_score because that is the engine's own severity signal; Phase B
    adds breadth to the ranking formula and this flips.
    """
    d = detect(SID_QUESTIONS, SID_ANSWERS)
    assert d[2].detection_score > d[1].detection_score


def test_siddharth_actor_evidence_has_somewhere_to_live():
    """The founder volunteered that HR uses it and the CFO signs off, twice,
    and nothing recorded it. The field now exists and defaults honestly to
    False -- no code path sets it yet, and the test says so rather than
    pretending the capability is there."""
    d = detect(SID_QUESTIONS, SID_ANSWERS)
    assert all(not e.volunteered for e in d[2].evidence)


def test_every_piece_of_evidence_is_traceable_to_a_question():
    """Recommendation traceability (Phase D) needs question ids to survive
    detection. They do."""
    d = detect(SID_QUESTIONS, SID_ANSWERS)
    asked = {a.question_id for a in SID_ANSWERS}
    for detection in d.values():
        for e in detection.evidence:
            assert e.question_id in asked
            assert e.directness == "direct"
            assert e.dimension is not None


# --- Desi Protein -----------------------------------------------------------
#
# The counter-case. Friends-and-family validation is ONE pattern that recurs;
# six answers about it must not read as six independent signals, or Phase B
# simply swaps one wrong ranking for another.

DESI_QUESTIONS = [q(300 + i, 3, "Idea & Validation") for i in range(6)]
DESI_ANSWERS = [ans(10 + i, 300 + i, AMBER) for i in range(6)]


def test_desi_repeated_signals_do_not_become_independent_evidence():
    d = detect(DESI_QUESTIONS, DESI_ANSWERS)
    assert len(d[3].evidence) == 6          # six answers
    assert d[3].independent_signal_count == 1  # one dimension, one pattern


def test_desi_converging_pattern_is_still_visible_as_mass():
    """Repetition is not independence, but it is not nothing either: the founder
    really did say it six times. Mass keeps that, so Phase B can weigh
    repetition and breadth differently instead of discarding one of them."""
    d = detect(DESI_QUESTIONS, DESI_ANSWERS)
    assert d[3].evidence_mass == D("6")


def test_desi_food_context_survives_detection():
    """The dimension label must reach the detection intact -- context gating
    (Phase C) has nothing to gate on otherwise."""
    d = detect(DESI_QUESTIONS, DESI_ANSWERS)
    assert {e.dimension for e in d[3].evidence} == {"Idea & Validation"}


# --- Arya Beauty ------------------------------------------------------------
#
# Founder dependency shows up across several dimensions at once -- delegation,
# bus factor, decision rights, SOPs. Those must converge on one cause, not
# fragment into four unrelated findings.

ARYA_QUESTIONS = [
    q(401, 4, "Founder Psychology"),
    q(402, 4, "Operations & Systems"),
    q(403, 4, "Team & Leadership"),
    q(404, 4, "Business Planning"),
    q(501, 5, "Fundraising"),
]
ARYA_ANSWERS = [ans(20 + i, 400 + i, AMBER) for i in range(1, 5)]


def test_arya_dependency_signals_converge_on_one_cause():
    d = detect(ARYA_QUESTIONS, ARYA_ANSWERS)
    assert set(d) == {4}                       # one finding, not four
    assert d[4].independent_signal_count == 4  # spanning four dimensions


def test_arya_fundraising_does_not_activate_without_evidence():
    """No answer touched fundraising, so no fundraising candidate exists.

    This is the floor for Phase C, not the ceiling: it proves an UNASKED
    category stays silent. It does not prove that an asked-but-irrelevant one
    does, which is the ComplyFlow deck-recommendation failure and needs the
    context-precondition axis that does not exist yet.
    """
    d = detect(ARYA_QUESTIONS, ARYA_ANSWERS)
    assert 5 not in d


@pytest.mark.xfail(strict=True,
                   reason="Phase C: no context-precondition axis on categories")
def test_arya_fundraising_stays_shut_even_when_probed():
    """A single Amber on a fundraising question, from a founder with no funding
    intent, must not open a fundraising finding. Today it does: one negative
    answer is enough to make any category a candidate."""
    answers = ARYA_ANSWERS + [ans(99, 501, AMBER)]
    d = detect(ARYA_QUESTIONS, answers)
    assert 5 not in d


def test_arya_franchise_context_survives_detection():
    d = detect(ARYA_QUESTIONS, ARYA_ANSWERS)
    dims = {e.dimension for e in d[4].evidence}
    assert "Operations & Systems" in dims and "Team & Leadership" in dims


# --- invariants -------------------------------------------------------------

def test_green_answers_are_not_evidence_of_a_problem():
    """A genuine unknown scored amber stays amber; a green answer must not
    become negative evidence. Guards the "I don't know is not a weakness"
    property the clean run showed holding."""
    questions = [q(601, 6, "Financial Management"), q(602, 6, "Financial Management")]
    d = detect(questions, [ans(30, 601, GREEN), ans(31, 602, AMBER)])
    assert [e.question_id for e in d[6].evidence] == [602]
    assert d[6].evidence_mass == D("1")


def test_a_cause_with_only_green_evidence_is_not_a_candidate():
    questions = [q(701, 7, "Product")]
    assert detect(questions, [ans(40, 701, GREEN)]) == {}


def test_breadth_fields_default_safely_for_old_callers():
    """Backward compatibility: both fields are optional, so a RootCauseDetection
    built by existing code (tests, the enricher, anything constructing one
    directly) still works and reads as "no breadth recorded"."""
    from app.api.v1.reasoning.schemas import RootCauseDetection
    from app.models.enums import ConfirmationStatus
    det = RootCauseDetection(
        root_cause_id=1, category="C",
        confirmation_status=ConfirmationStatus.UNCONFIRMED,
        detection_score=D("0.5"), detection_confidence=D("0.5"),
        evidence=(), contributing_factors=(),
    )
    assert det.independent_signal_count == 0
    assert det.evidence_mass == D("0")
