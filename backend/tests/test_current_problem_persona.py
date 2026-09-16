"""The Current Problem phase, which for every run on record was mostly noise.

`current_problem_questions` holds twelve rows -- four per stage group -- and
each founder answers the four for their stage. Measured against the answer
bank as it stood before this file existed, exactly ONE of any four matched a
topic. The other three took the generic fallback. So in every e2e journey ever
recorded, three quarters of this phase's evidence was a topic-neutral line
that says nothing about the founder, and the phase was measuring the fallback
rather than the persona.

Two of the twelve so-called matches were worse than falling back:

  Q9  "what is the single biggest problem in the company right now? Say it
      the way you'd say it to a co-founder, not the way you'd say it to a
      board" -- matched the TEAM topic, on the word "co-founder" inside the
      sentence telling the founder how to PHRASE their answer, and came back
      with an answer about who owns what.

  Q12 "the last time you made a call that a team lead should have made
      instead" -- a delegation question -- matched TEAM on "team lead" and
      answered about team structure.

A fallback is visibly a non-answer. A confident answer to a question nobody
asked is not, and it reaches the report as evidence.

Every question below asserts the SUBJECT its answer lands on. The wording of
the answers is free to change; what must not change is which question each one
is answering.
"""

import pytest

from scripts.e2e_journey_check import (
    ANSWER_BANK,
    _CURRENT_PROBLEM_TOPICS,
    _TOPICS,
    _TRACTION_TOPICS,
    match_answer,
)

PERSONAS = ("weak", "strong", "traction")

#: Where the Current Problem block starts in each persona's bank. weak and
#: strong never carry the operating topics; traction does.
_OFFSET = {
    "weak": len(_TOPICS),
    "strong": len(_TOPICS),
    "traction": len(_TRACTION_TOPICS),
}

# Slot names, so a failure reads "went to AVOIDED_METRIC, expected RECURRING"
# rather than "got 5, expected 6".
(HEADLINE, WOULD_BE_TRUE, ALREADY_TRIED, SINGLE_POINT,
 AVOIDING, AVOIDED_METRIC, RECURRING, LANDED_ON_YOU) = range(
    len(_CURRENT_PROBLEM_TOPICS))


def cp_slot(question: str, persona: str) -> int | None:
    """Which Current Problem slot the question routes to.

    None when it falls back; -1 when it matches something OUTSIDE the Current
    Problem block, which is the Q9-matched-TEAM failure and needs to be
    distinguishable from a clean fallback.
    """
    answer, matched = match_answer(question, persona)
    if not matched:
        return None
    index = [a for _, a in ANSWER_BANK[persona]].index(answer)
    relative = index - _OFFSET[persona]
    return relative if 0 <= relative < len(_CURRENT_PROBLEM_TOPICS) else -1


#: The twelve rows of `current_problem_questions`, verbatim, with the subject
#: each one is asking about. Four for Stage 0, four for Stage 0->1, four for
#: Stage 1->10+.
CURRENT_PROBLEM_QUESTIONS = [
    # --- Stage 0 (Ideation)
    ("Now the part that matters most. In your own words, what is the single "
     "biggest thing standing between you and actually starting? Don't polish "
     "it -- say it the way you'd say it to a friend at the end of a long day.",
     HEADLINE),
    ("What is the one thing that would need to be true this week for you to "
     "actually start?", WOULD_BE_TRUE),
    ("What have you already tried to move this forward -- a call, a sketch, "
     "a search -- and why did it stall out?", ALREADY_TRIED),
    # Deliberately NOT a Current Problem slot: this one has always routed to
    # the customer topic, correctly, and must keep doing so.
    ("If I asked you to talk to one real potential customer this week, "
     "what's stopping you from already having done that?", -1),

    # --- Stage 0->1
    ("Now the part that matters most. In your own words, what is the single "
     "biggest problem in your business right now? Don't polish it -- say it "
     "the way you'd say it to a friend at the end of a long day.", HEADLINE),
    ("What's the one thing that, if it broke tomorrow, would stop the "
     "business cold?", SINGLE_POINT),
    # Also correctly outside the block: a genuine co-founder question.
    ("Tell me about the last time you and a co-founder or teammate disagreed "
     "on what to do next. How was it resolved -- or wasn't it?", -1),
    ("What have you been avoiding this week that you know you need to deal "
     "with?", AVOIDING),

    # --- Stage 1->10+
    ("Now the part that matters most. In your own words, what is the single "
     "biggest problem in the company right now? Say it the way you'd say it "
     "to a co-founder, not the way you'd say it to a board.", HEADLINE),
    ("What metric have you been quietly avoiding looking at this month?",
     AVOIDED_METRIC),
    ("Where in the business does the same problem keep resurfacing, even "
     "after you thought you'd already fixed it?", RECURRING),
    ("Tell me about the last time you made a call that a team lead should "
     "have made instead. Why did it land on you?", LANDED_ON_YOU),
]


@pytest.mark.parametrize("persona", PERSONAS)
@pytest.mark.parametrize(
    "question,expected", CURRENT_PROBLEM_QUESTIONS,
    ids=[q[:45] for q, _ in CURRENT_PROBLEM_QUESTIONS])
def test_current_problem_question_routing(question, expected, persona):
    got = cp_slot(question, persona)
    assert got is not None, "fell through to the generic answer"
    assert got == expected, (
        f"routed to slot {got}, expected {expected}\n"
        f"  landed on: {match_answer(question, persona)[0][:90]}...")


@pytest.mark.parametrize("persona", PERSONAS)
def test_no_current_problem_question_falls_back(persona):
    """The headline: nine of twelve did, in every run ever recorded."""
    fell_back = [q for q, _ in CURRENT_PROBLEM_QUESTIONS
                 if cp_slot(q, persona) is None]
    assert not fell_back, f"{len(fell_back)} still fall back: {fell_back}"


@pytest.mark.parametrize("persona", PERSONAS)
def test_the_two_questions_that_matched_the_wrong_topic(persona):
    """Q9 and Q12 -- the ones that came back confident and wrong."""
    q9 = ("Now the part that matters most. In your own words, what is the "
          "single biggest problem in the company right now? Say it the way "
          "you'd say it to a co-founder, not the way you'd say it to a board.")
    q12 = ("Tell me about the last time you made a call that a team lead "
           "should have made instead. Why did it land on you?")
    assert cp_slot(q9, persona) == HEADLINE, (
        "Q9 is about the biggest problem in the company. It used to match the "
        "team topic on the word 'co-founder' in its phrasing instruction.")
    assert cp_slot(q12, persona) == LANDED_ON_YOU, (
        "Q12 is about a decision that belonged a level down. It used to match "
        "the team topic on 'team lead'.")


#: The first draft of the Current Problem topics used the bare terms "stall"
#: and "matters most", and these six questions from the diagnosis bank matched
#: them. Every one came back with an answer about an abandoned landing page or
#: a business that was never started. Six false matches in exchange for fixing
#: two is a bad trade, and the phrases are full phrases now because of it.
QUESTIONS_THAT_MUST_NOT_MATCH = [
    "When your standard follow-up stalls, do you have other tactics ready to "
    "try, or does it just stop there?",
    "Has the business started stalling because your attention is fully "
    "diverted into investor meetings?",
    "How many deals are currently stalled simply because nobody followed up "
    "at the right time?",
    "Do you track why deals stall at a specific stage, or only that they "
    "stalled?",
    "Does what you evaluate someone on stay broad and generic, rather than "
    "reflecting what actually matters most?",
    "Are multiple goals being pursued simultaneously with no clear ranking "
    "of which matters most right now?",
    "What's one thing you could stop doing this week to free up real time "
    "for this idea?",
]


@pytest.mark.parametrize("persona", PERSONAS)
@pytest.mark.parametrize("question", QUESTIONS_THAT_MUST_NOT_MATCH,
                         ids=[q[:45] for q in QUESTIONS_THAT_MUST_NOT_MATCH])
def test_current_problem_topics_do_not_swallow_other_questions(
        question, persona):
    # None (clean fallback) and -1 (matched some other topic) are both fine.
    # What must not happen is landing inside the Current Problem block.
    slot = cp_slot(question, persona)
    assert slot is None or slot == -1, (
        f"a Current Problem answer captured a question that is not about the "
        f"current problem: {match_answer(question, persona)[0][:90]}...")


def test_every_persona_answers_every_current_problem_topic():
    """A topic with no answer behind it in some persona is a fallback waiting
    to happen in exactly one kind of run."""
    for persona in PERSONAS:
        bank_topics = [t for t, _ in ANSWER_BANK[persona]]
        for topic in _CURRENT_PROBLEM_TOPICS:
            assert topic in bank_topics, (
                f"{persona} has no answer for Current Problem topic "
                f"{topic[0][0]!r}")
