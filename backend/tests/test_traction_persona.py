"""The traction persona answers the questions Early Traction actually asks.

Report #96 ran founder 3706 at Early Traction with `--persona strong`, and
nine of thirty diagnosis answers fell through to the generic reply. Eight of
those nine scored RED, because a non-answer reads to the classifier as
evasion. Founder Readiness and Product & Execution both came back Critical
Gap on the strength of them.

The questions below are the real thirty from that run, copied from its
output. Each asserts the SUBJECT the answer lands on, not the wording -- that
is the thing that was broken, and it is the thing a future edit to the
keyword lists can quietly break again.
"""

import pytest

from scripts.e2e_journey_check import (
    ANSWER_BANK,
    FALLBACKS,
    PERSONAS,
    _OPERATING_TOPICS,
    _TOPICS,
    _TRACTION_CP_TEXTS,
    _TRACTION_TEXTS,
    _TRACTION_TOPICS,
    match_answer,
)

PERSONA = "traction"


def topic_index(question: str) -> int:
    """Which slot the question routes to, or -1 when it falls back."""
    answer, matched = match_answer(question, PERSONA)
    if not matched:
        return -1
    return [a for _, a in ANSWER_BANK[PERSONA]].index(answer)


# Slot names, so a failure says "went to pricing, expected cash" rather than
# "got 10, expected 25".
CUSTOMERS, PLANNING, MARKET, PRODUCT, PRICING, TEAM, RISK, DECISIONS, \
    FEEDBACK, PURPOSE, EXCELLENCE, PITCH, OWN_PROBLEM, TOOLS, TIME_WASTED = range(15)
DELEGATION, DEPENDENCY, WRITTEN, ROLES, DECISION_RIGHTS, PERFORMANCE, \
    HIRING, CHURN, JOURNEY, PRICE_PRESENTATION, CASH, EVIDENCE, MARKETING, \
    ICP_DRIFT = range(15, 29)


#: The thirty diagnosis questions served in report #96, with the slot each
#: one belongs in. The nine marked GENERIC in that run are the reason this
#: file exists.
STAGE_4_QUESTIONS = [
    ("Has anyone on your team ever actually been taught, by you, how you want "
     "something delegated — or do they just guess?", DELEGATION),
    ("When did you last actually talk to a customer about the problem, versus "
     "just building based on what you already believed?", CUSTOMERS),
    ("What specifically separates a customer who sticks around from one who "
     "churns quickly — do you actually know?", CHURN),
    ("On a scale of 1 to 5, how well do you know your customer's buying "
     "journey?", JOURNEY),
    ("Do you know exactly what's expected of each person on your team right "
     "now, in writing?", ROLES),
    # GENERIC in #96
    ("Is there anything tracking what compliance filings are due and when?",
     WRITTEN),
    ("Describe your best customer so far in specific detail — not a persona, "
     "a real person.", CUSTOMERS),
    # GENERIC in #96
    ("If you got sick for a week right now, what would simply stop happening "
     "in the business?", DEPENDENCY),
    # GENERIC in #96
    ("What real evidence do you have right now that this is working, beyond "
     "your own belief in it?", EVIDENCE),
    # GENERIC in #96
    ("Before you launch a campaign, do you define what success actually looks "
     "like, or figure that out after?", MARKETING),
    # GENERIC in #96
    ("If you had to hand off a key part of the business tomorrow, is there "
     "anything written down for the person taking over — or does it all live "
     "in your head?", WRITTEN),
    ("Is there any system for tracking who owns what, or does it live in "
     "conversations and memory?", ROLES),
    ("Where does your plan currently live — is it written somewhere your team "
     "can see it, or just in your head?", PLANNING),
    ("Last month, was your business profitable or just generating revenue?",
     CASH),
    # GENERIC in #96 -- every pricing term said "pricing"; this says "price"
    ("Walk me through the math behind your price — what did you start with?",
     PRICING),
    # GENERIC in #96
    ("If you had to prove the problem you're solving is still the same one "
     "you started with, what evidence would you show?", EVIDENCE),
    # GENERIC in #96
    ("What's something only you know how to do in this business right now, "
     "that nobody else could pick up without you explaining it live?",
     DEPENDENCY),
    ("Have you ever kept someone on the team longer than you should have, "
     "because replacing them felt harder than the problem they were "
     "causing?", HIRING),
    ("Is there a clear, consistent way you present pricing, or does it vary "
     "each time?", PRICE_PRESENTATION),
    ("When did you last actually check whether your understanding of your "
     "customer still matches reality?", ICP_DRIFT),
    ("Name a risk you know about but haven't done anything about yet. Why "
     "not?", RISK),
    ("For a task you or your team does repeatedly, is there a written "
     "step-by-step procedure for it, or does it live only in someone's "
     "head?", WRITTEN),
    # GENERIC in #96
    ("What percentage of deals, projects, or key tasks this month required "
     "you personally, versus ran without you?", DEPENDENCY),
    ("If two people on your team disagreed about who owned a task, is there "
     "a clear way to resolve that?", DECISION_RIGHTS),
    ("Do you check your cash position on a regular schedule, or only when "
     "something prompts you to look?", CASH),
    ("When did you last sit down and look at who your paying customers "
     "actually are, versus who you originally designed for?", ICP_DRIFT),
    ("Is your fundraising pitch built around evidence of market demand, or "
     "around how personally convinced you are of the idea?", EVIDENCE),
    ("Are the customers actually using your product today the same type of "
     "customer you originally designed it for?", ICP_DRIFT),
    ("Do you have a second-in-command who could make a real decision in your "
     "absence, or does everything genuinely wait for you?", DEPENDENCY),
    ("How do you know if your team is actually performing well, versus just "
     "staying busy?", PERFORMANCE),
]


@pytest.mark.parametrize("question,expected", STAGE_4_QUESTIONS,
                         ids=[q[:45] for q, _ in STAGE_4_QUESTIONS])
def test_stage_4_question_routing(question, expected):
    got = topic_index(question)
    assert got != -1, "fell through to the generic answer"
    assert got == expected, (
        f"routed to slot {got}, expected {expected}\n"
        f"  landed on: {ANSWER_BANK[PERSONA][got][1][:90]}...")


def test_no_stage_4_question_falls_back():
    """The headline: nine of thirty did, and eight of those scored red."""
    fell_back = [q for q, _ in STAGE_4_QUESTIONS if topic_index(q) == -1]
    assert not fell_back, f"{len(fell_back)} still fall back: {fell_back}"


def test_the_nine_that_were_generic_are_specifically_fixed():
    """Named individually so a regression says which one came back."""
    previously_generic = [
        "Is there anything tracking what compliance filings are due and when?",
        "If you got sick for a week right now, what would simply stop "
        "happening in the business?",
        "What real evidence do you have right now that this is working, "
        "beyond your own belief in it?",
        "Before you launch a campaign, do you define what success actually "
        "looks like, or figure that out after?",
        "Walk me through the math behind your price — what did you start "
        "with?",
        "What's something only you know how to do in this business right "
        "now, that nobody else could pick up without you explaining it live?",
        "What percentage of deals, projects, or key tasks this month "
        "required you personally, versus ran without you?",
    ]
    for question in previously_generic:
        assert topic_index(question) != -1, f"still generic: {question}"


# --- the structure the other personas depend on ------------------------


def test_weak_and_strong_keep_exactly_the_fifteen_shared_topics():
    """Appending must not have moved anything the earlier runs matched on.

    weak and strong now carry the Current Problem topics too -- that phase
    exists at every stage, not just Early Traction, and all three personas
    were falling back on three of its four questions. What matters for
    comparability is not that the bank is fifteen long, but that the FIRST
    fifteen are untouched and still in order: a question that matched slot 4
    in an earlier run still matches slot 4 now.
    """
    from scripts.e2e_journey_check import _CURRENT_PROBLEM_TOPICS

    for persona in ("weak", "strong"):
        topics = [t for t, _ in ANSWER_BANK[persona]]
        assert topics[:15] == list(_TOPICS), (
            f"{persona}'s original topics moved -- every earlier run's "
            f"routing is now unreproducible")
        assert topics[15:] == list(_CURRENT_PROBLEM_TOPICS)
    assert len(_TOPICS) == 15


def test_traction_is_the_shared_fifteen_then_the_operating_topics():
    assert _TRACTION_TOPICS[:15] == _TOPICS
    assert _TRACTION_TOPICS[15:] == _OPERATING_TOPICS
    assert len(_TRACTION_TEXTS) == len(_TRACTION_TOPICS)


def test_the_persona_is_selectable():
    assert "traction" in PERSONAS
    assert "traction" in FALLBACKS
    assert PERSONAS["traction"] == _TRACTION_TEXTS + _TRACTION_CP_TEXTS


def test_every_traction_answer_is_reachable():
    """A slot no question can route to is dead weight that looks like cover."""
    reachable = {topic_index(q) for q, _ in STAGE_4_QUESTIONS}
    reachable.discard(-1)
    # The fifteen shared slots are exercised by the weak/strong suites; these
    # are the ones this persona adds, and every one must be gettable.
    unreachable = set(range(15, 29)) - reachable
    assert not unreachable, (
        f"operating slots no stage-4 question reaches: {sorted(unreachable)}")


def test_answers_are_substantial_enough_to_classify():
    """"Yes" tells you the plumbing works and nothing about the scoring."""
    for i, text in enumerate(_TRACTION_TEXTS):
        assert len(text) > 120, f"slot {i} is too thin to score: {text!r}"


def test_the_fallback_stays_topic_neutral():
    """It must not smuggle in evidence about a dimension never raised."""
    fallback = FALLBACKS["traction"].lower()
    for leak in ("customer", "revenue", "pricing", "team", "churn", "cash",
                 "market", "product"):
        assert leak not in fallback, f"fallback mentions {leak!r}"


def test_the_persona_stays_at_early_traction():
    """Overshooting is measured as stage mismatch by stage_coherence_factor,
    and the comparison then reports the wrong thing."""
    joined = " ".join(_TRACTION_TEXTS).lower()
    for overshoot in ("series a", "series b", "vp of", "board meeting",
                      "head of sales", "crore", "million in arr"):
        assert overshoot not in joined, f"reads past Early Traction: {overshoot!r}"


# --- the Ideation runs must not have moved -----------------------------
#
# Adding the operating topics meant adding later-stage phrasings to five of
# the fifteen SHARED topics too, because Early Traction asks the same
# dimensions in different words ("the last week that genuinely got to you"
# is the stress question; "learn the hard way" is the blind-spot one). Those
# topics are the ones weak and strong match on.
#
# Every added phrase is specific to a later-stage question, so no Ideation
# question contains one. This measures that rather than asserting it: the
# twelve below are the real diagnosis questions from report #95, and their
# slots are what the code produced BEFORE the operating topics existed,
# captured by running the previous revision.

IDEATION_QUESTIONS = [
    ("When you picture doing this really well, what does 'well' actually mean "
     "to you — being first, being the best, or being trusted?", EXCELLENCE),
    ("Has anyone else told you this problem is real, or is this based only on "
     "your own experience so far?", CUSTOMERS),
    ("What's the simplest version of this you could put in front of someone "
     "today using only free or no-code tools?", TOOLS),
    ("Right now, is most of your time going into thinking about the idea, or "
     "actually testing it?", PLANNING),
    ("If your long-term vision for this disappeared tomorrow, would today "
     "look any different?", PURPOSE),
    ("If a new competitor appeared tomorrow, how would you actually find "
     "out?", MARKET),
    ("What's the one activity that eats the most time without actually "
     "moving this idea forward?", TIME_WASTED),
    ("Do you have any way to see how someone actually used what you've "
     "built, or would you only know if they told you?", PRODUCT),
    ("How many people outside your personal network have you spoken to about "
     "this problem in the last month?", CUSTOMERS),
    ("What's a risk you only realized was a risk after it actually caused a "
     "problem?", RISK),
    ("If you tracked every hour this week, what would surprise you most "
     "about where it went?", PLANNING),
    ("Is there a way for someone testing this to leave feedback right now, "
     "or would they have to find you separately?", FEEDBACK),
]


@pytest.mark.parametrize("persona", ["weak", "strong"])
@pytest.mark.parametrize("question,expected", IDEATION_QUESTIONS,
                         ids=[q[:40] for q, _ in IDEATION_QUESTIONS])
def test_ideation_routing_is_unchanged(persona, question, expected):
    answer, matched = match_answer(question, persona)
    assert matched, "an Ideation question started falling back"
    got = [a for _, a in ANSWER_BANK[persona]].index(answer)
    assert got == expected, (
        f"{persona} moved from slot {expected} to {got} -- a phrase added for "
        "a later-stage question is matching an Ideation one")


@pytest.mark.parametrize("question,expected", IDEATION_QUESTIONS,
                         ids=[q[:40] for q, _ in IDEATION_QUESTIONS])
def test_traction_routes_ideation_questions_the_same_way(question, expected):
    """The shared fifteen are shared: a founder at a later stage still gets
    asked some of these, and must land in the same slot."""
    assert topic_index(question) == expected
