"""An answer has to be an answer to the question that was asked.

Found live: the founder-facing screen accepted the QUESTION ITSELF, pasted
back into the box, saved it, and moved straight on to the next one -- so
nothing in the phase gave any sign of having read what was written. The only
validation between the client and the database was "not blank".

The rules deliberately reject little. A false reject (Ally refusing a real
answer) is far worse than a false accept, so the negative cases below matter
more than the positive ones: short, vague and "I don't know" are all answers,
and are the dimension-resolution advisor's job to judge, not this gate's.
"""

from __future__ import annotations

import pytest

from app.api.v1.founder_dna.responsiveness import check

NARRATIVE = (
    "Tell me about the last time someone who knows you well pointed out "
    "something about how you work that you hadn't seen. What was it?"
)
CHOICE = (
    "When something's going wrong, do you want it told to you straight, "
    "laid out step by step, or talked through out loud?"
)
OPTIONS = ["Told straight", "Laid out step by step", "Talked through out loud"]


def _check(answer, question=NARRATIVE, fmt="narrative", options=None):
    return check(
        question_text=question,
        question_format=fmt,
        options=options,
        answer_text=answer,
    )


@pytest.mark.parametrize(
    "answer",
    [
        NARRATIVE,
        NARRATIVE.rstrip("?"),
        "Tell me about the last time someone pointed out how you work",
    ],
    ids=["verbatim", "punctuation-stripped", "partial-paste"],
)
def test_the_question_handed_back_is_not_an_answer(answer):
    rejection = _check(answer)
    assert rejection is not None
    assert rejection.reason == "echo"
    assert rejection.reprompt


@pytest.mark.parametrize(
    "answer",
    [
        "My co-founder said I re-open decisions after they're made. I hadn't "
        "noticed until she counted three in one week.",
        "I don't know",
        "Nothing comes to mind",
        "Money. Always has been.",
        # Quotes the question before answering it -- heavy overlap, but it
        # adds real content, so it is an answer.
        "The last time someone pointed something out was my sister telling me "
        "I gather information instead of asking for help.",
    ],
    ids=["specific", "dont-know", "blank-drawn", "terse", "quotes-then-answers"],
)
def test_real_answers_are_accepted(answer):
    assert _check(answer) is None


def test_input_with_no_letters_is_rejected():
    rejection = _check("1234 !!")
    assert rejection is not None
    assert rejection.reason == "no_content"


@pytest.mark.parametrize("answer", ["Told straight", "  told  STRAIGHT "])
def test_a_picked_option_is_accepted(answer):
    assert _check(answer, question=CHOICE, fmt="forced_choice", options=OPTIONS) is None


def test_free_text_on_a_pick_one_is_accepted():
    """FounderDnaChat's own placeholder says "or type if none of them fit".
    Requiring an exact option would break a promise the UI makes on screen."""
    assert _check(
        "Depends who's telling me", question=CHOICE, fmt="forced_choice", options=OPTIONS
    ) is None


def test_the_question_pasted_into_a_pick_one_is_still_rejected():
    rejection = _check(CHOICE, question=CHOICE, fmt="forced_choice", options=OPTIONS)
    assert rejection is not None
    assert rejection.reason == "echo"
