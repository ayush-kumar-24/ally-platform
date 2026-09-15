"""The journey check must fail when a phase serves nothing.

A run against a cleaned founder reported:

    Founder DNA:      0 question(s) answered
    Current Problem:  0 question(s) answered
    Diagnosis:       14 question(s) answered

and then printed a full report summary as though the journey had happened.
Two defects met: cleanup left founder_dna_completed_at / current_problem_
completed_at set on the founders row while deleting the answers, so both
phases answered "already complete" and served no question -- and `_walk`'s
`while q:` loop simply never entered, so it returned True.
"""

import pytest

from scripts.e2e_journey_check import (
    _JOURNEY_STAMPS,
    _MATCH_THRESHOLD,
    ANSWER_BANK,
    FALLBACKS,
    PERSONAS,
    STRONG_ANSWERS,
    WEAK_ANSWERS,
    _answer_for,
    _clear_journey_stamps,
    _walk,
    band_summary,
    match_answer,
    stop_reason,
)


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload, self.status_code = payload, status_code
        self.text = str(payload)

    def json(self):
        return self._payload


class _Client:
    """Serves a scripted sequence of question payloads."""

    def __init__(self, start_payload, answer_payloads=()):
        self.start_payload = start_payload
        self.answer_payloads = list(answer_payloads)
        self.answers_posted = 0

    def post(self, path, json=None):
        if json is None:
            return _Response(self.start_payload, 201)
        self.answers_posted += 1
        if not self.answer_payloads:
            return _Response({"is_complete": True, "next_question": None})
        return _Response(self.answer_payloads.pop(0))


def _q(qid):
    return {"founder_dna_question_id": qid, "question_text": f"Q{qid}"}


def test_walk_fails_when_the_phase_reports_itself_already_complete():
    """`question: null` means complete -- which proves nothing ran."""
    client = _Client({"question": None, "progress": {"is_complete": True}})
    out = []
    ok = _walk(client, "/start", "/answer", "founder_dna_question_id", "Founder DNA", out)
    assert ok is False
    assert out == []
    assert client.answers_posted == 0


def test_walk_reports_the_cleanup_remedy_when_it_fails(capsys):
    client = _Client({"question": None})
    _walk(client, "/start", "/answer", "founder_dna_question_id", "Founder DNA", [])
    printed = capsys.readouterr().out
    assert "FAIL" in printed
    assert "already complete" in printed
    assert "--cleanup-founder-id" in printed


def test_walk_still_succeeds_on_a_real_phase():
    client = _Client(
        {"question": _q(1)},
        [{"next_question": _q(2)}, {"is_complete": True, "next_question": None}],
    )
    out = []
    ok = _walk(client, "/start", "/answer", "founder_dna_question_id", "Founder DNA", out)
    assert ok is True
    assert len(out) == 2


def test_walk_fails_when_a_start_status_is_wrong():
    client = _Client({"question": _q(1)})
    client.start_payload = {"question": _q(1)}

    class _Bad(_Client):
        def post(self, path, json=None):
            if json is None:
                return _Response({"detail": "nope"}, 409)
            return _Response({})

    assert _walk(_Bad({}), "/start", "/answer", "founder_dna_question_id", "X", []) is False


# --- cleanup -----------------------------------------------------------


def test_both_completion_stamps_are_cleared():
    assert set(_JOURNEY_STAMPS) == {
        "founder_dna_completed_at", "current_problem_completed_at"
    }


class _FakeDb:
    def __init__(self, explode=False):
        self.statements, self.params, self.rolled_back = [], [], False
        self.explode = explode

    def execute(self, stmt, params=None):
        if self.explode:
            raise RuntimeError("column does not exist")
        self.statements.append(str(stmt))
        self.params.append(params)

    def rollback(self):
        self.rolled_back = True


class _FakeSa:
    @staticmethod
    def text(s):
        return s


def test_clear_journey_stamps_nulls_both_columns_for_the_given_founders():
    db = _FakeDb()
    _clear_journey_stamps(db, _FakeSa, [3704])
    assert len(db.statements) == 1
    sql = db.statements[0]
    assert sql.startswith("update founders set ")
    assert "founder_dna_completed_at = null" in sql
    assert "current_problem_completed_at = null" in sql
    assert "where founder_id = any(:f)" in sql
    assert db.params[0] == {"f": [3704]}


def test_clear_journey_stamps_touches_nothing_else_on_the_row():
    """Identity, consent, plan and profile are not cleanup's business."""
    db = _FakeDb()
    _clear_journey_stamps(db, _FakeSa, [3704])
    sql = db.statements[0]
    for column in ("email", "user_id", "plan_type", "profile_completed",
                   "stage_id", "full_name"):
        assert column not in sql


def test_clear_journey_stamps_survives_a_schema_without_those_columns():
    """Cleanup must not become the reason a tidy-up fails."""
    db = _FakeDb(explode=True)
    _clear_journey_stamps(db, _FakeSa, [3704])
    assert db.rolled_back is True


# --- personas ----------------------------------------------------------


def test_both_personas_cover_the_same_topics_in_the_same_order():
    """The comparison is only meaningful if the sets differ in quality and
    not in what they are about -- so slot N is the same subject in both."""
    assert len(WEAK_ANSWERS) == len(STRONG_ANSWERS) == len(ANSWER_BANK["weak"])
    assert set(PERSONAS) == {"weak", "strong"}
    weak_topics = [t for t, _ in ANSWER_BANK["weak"]]
    strong_topics = [t for t, _ in ANSWER_BANK["strong"]]
    assert weak_topics == strong_topics


def test_weak_is_the_default_so_existing_runs_are_unchanged():
    assert _answer_for(0) == _answer_for(0, "weak") == WEAK_ANSWERS[0]


def test_personas_give_genuinely_different_answers():
    for i in range(len(WEAK_ANSWERS)):
        assert _answer_for(i, "weak") != _answer_for(i, "strong")


def test_answers_still_cycle_by_index_when_no_question_text_is_given():
    """The old behaviour, kept for callers that have no question to match."""
    n = len(WEAK_ANSWERS)
    assert _answer_for(n, "strong") == _answer_for(0, "strong")
    assert _answer_for(n + 1, "weak") == _answer_for(1, "weak")


def test_strong_answers_carry_the_evidence_the_weak_ones_lack():
    """Not a style check: each phrase is the thing a pillar scores on. If a
    rewrite drops them, the strong run stops testing what it claims to."""
    blob = " ".join(STRONG_ANSWERS).lower()
    for evidence in ("never met", "wrote", "tested", "bottom-up",
                     "drop-off", "in writing"):
        assert evidence in blob, f"strong answers no longer show {evidence!r}"


def test_strong_answers_stay_at_the_founder_s_stage():
    """A scaled-company answer would make the run measure stage mismatch
    against the confidence engine's stage_coherence_factor rather than
    answer quality."""
    blob = " ".join(STRONG_ANSWERS).lower()
    for overreach in ("series a", "series b", "crore", "million in revenue",
                      "arr", "our team of"):
        assert overreach not in blob, f"strong answers overreach: {overreach!r}"


def test_walk_sends_the_persona_it_was_given():
    client = _Client(
        {"question": {"founder_dna_question_id": 1,
                      "question_text": "When did you last sit down "
                                       "specifically to plan?"}},
        [{"is_complete": True, "next_question": None}],
    )
    sent = []
    original = client.post

    def _spy(path, json=None):
        if json is not None:
            sent.append(json["answer_text"])
        return original(path, json)

    client.post = _spy
    _walk(client, "/start", "/answer", "founder_dna_question_id", "X", [], "strong")
    assert sent and sent[0] in STRONG_ANSWERS


# --- topic matching ----------------------------------------------------
#
# Answers used to be handed out round-robin by question index, so which
# answer met which question was luck. The strong run's analytics question
# drew the cofounder paragraph and was scored red, and RC-441 Weak Product
# Analytics was detected against a founder whose answer said the product was
# instrumented. These tests are about that.


ANALYTICS_Q = ("Do you have any way to see how someone actually used what "
               "you've built, or would you only know if they told you?")


@pytest.mark.parametrize("persona", ["weak", "strong"])
def test_the_analytics_question_gets_the_analytics_answer(persona):
    """The RC-441 regression, stated as a test."""
    answer, matched = match_answer(ANALYTICS_Q, persona)
    assert matched
    assert answer == ANSWER_BANK[persona][3][1], "expected the product topic"


def test_strong_analytics_answer_actually_describes_instrumentation():
    answer, _ = match_answer(ANALYTICS_Q, "strong")
    assert "instrumented" in answer


def test_terms_match_at_a_word_boundary():
    """'charge' sits inside 'recharges'. Substring matching sent an energy
    question to the pricing answer."""
    _, matched = match_answer(
        "Which one actually recharges you -- working alone in a silent room, "
        "or a loud room full of people?", "strong")
    assert matched is False


def test_one_supporting_term_is_not_enough():
    """'the last time you...' opens a dozen unrelated questions."""
    _, matched = match_answer(
        "Tell me about the last time you laughed at work.", "weak")
    assert matched is False


def test_one_defining_term_is_enough():
    answer, matched = match_answer(
        "Tell me about the last time you had to give someone difficult "
        "feedback.", "weak")
    assert matched
    assert answer == ANSWER_BANK["weak"][8][1], "expected the feedback topic"


def test_a_multi_topic_question_goes_to_its_defining_term():
    """Scores two either way; only risk scores on a defining term."""
    answer, matched = match_answer(
        "When this idea could fail in a way that costs you real time or "
        "money, does that possibility excite you or unsettle you?", "strong")
    assert matched
    assert answer == ANSWER_BANK["strong"][6][1], "expected the risk topic"


def test_a_question_listing_several_areas_goes_to_the_one_it_asks_about():
    answer, matched = match_answer(
        "Which areas have you thought about risk in -- finance, legal, "
        "operations, market, team -- and which haven't you touched?", "weak")
    assert matched
    assert answer == ANSWER_BANK["weak"][6][1], "expected the risk topic"


def test_no_match_returns_the_persona_fallback():
    for persona in ("weak", "strong"):
        answer, matched = match_answer("What colour is the sky?", persona)
        assert matched is False
        assert answer == FALLBACKS[persona]


def test_both_personas_match_the_same_topic_for_the_same_question():
    """What makes two runs comparable: the same question reaches the same
    slot in either persona, so only answer QUALITY differs between runs,
    never which subject got discussed."""
    questions = [ANALYTICS_Q,
                 "When was the last time you sat down specifically to plan?",
                 "How many people outside your personal network have you "
                 "spoken to about this problem?",
                 "Is your sense of what financial controls you need based on "
                 "evidence, or mostly on gut feeling?"]
    for q in questions:
        weak, w_ok = match_answer(q, "weak")
        strong, s_ok = match_answer(q, "strong")
        assert w_ok and s_ok, q
        weak_texts = [a for _, a in ANSWER_BANK["weak"]]
        strong_texts = [a for _, a in ANSWER_BANK["strong"]]
        assert weak_texts.index(weak) == strong_texts.index(strong), q


def test_threshold_is_documented_as_two():
    """Named so the tests above read as intent rather than coincidence."""
    assert _MATCH_THRESHOLD == 2


def test_every_topic_is_reachable_by_at_least_one_real_question():
    """A topic nothing can match is dead weight pretending to be coverage."""
    reachable = set()
    for q in [
        "How many customers have you spoken to outside your personal network?",
        "When did you last sit down specifically to plan?",
        "How many businesses would actually need this?",
        ANALYTICS_Q,
        "Why do you charge for it what you charge for it?",
        "Who owns what between you and your cofounder?",
        "What is the biggest risk you have taken on this?",
        "When you face a big unknown, how do you decide?",
        "When did someone last give you difficult feedback?",
        "In one sentence, why does this problem deserve your next few years?",
        "Does doing this really well mean being first, the best, or being "
        "trusted?",
        "If a stranger asked you to explain this idea in one breath, what "
        "would you say?",
        "When did you personally ran into this problem yourself?",
        "What tool are you currently using to build this?",
        "What eats the most time without actually moving this forward?",
    ]:
        answer, matched = match_answer(q, "strong")
        assert matched, q
        reachable.add([a for _, a in ANSWER_BANK["strong"]].index(answer))
    assert reachable == set(range(len(ANSWER_BANK["strong"])))


def test_walk_reports_how_many_answers_matched(capsys):
    client = _Client(
        {"question": {"founder_dna_question_id": 1,
                      "question_text": ANALYTICS_Q}},
        [{"is_complete": True, "next_question": None}],
    )
    _walk(client, "/start", "/answer", "founder_dna_question_id", "X", [],
          "strong")
    printed = capsys.readouterr().out
    assert "1 matched on topic" in printed


def test_walk_names_the_fallbacks_so_a_weak_run_is_visible(capsys):
    client = _Client(
        {"question": {"founder_dna_question_id": 1,
                      "question_text": "What colour is the sky?"}},
        [{"is_complete": True, "next_question": None}],
    )
    _walk(client, "/start", "/answer", "founder_dna_question_id", "X", [],
          "weak")
    printed = capsys.readouterr().out
    assert "0 matched on topic" in printed
    assert "1 fell back" in printed


# --- the gaps that manufactured findings -------------------------------
#
# Every root cause in the strong run traced to a fallback or a mismatch,
# not to a strong answer. RC-1088 "No Breakdown from Annual Goal to Weekly
# Action" was rank 1 and a top finding off ONE question, because "five
# years" pulled a Business Planning question into the purpose answer.


def _topic_index(answer, persona="strong"):
    return [a for _, a in ANSWER_BANK[persona]].index(answer)


def test_a_question_about_today_is_planning_not_purpose():
    """The RC-1088 regression. It asks what today did, not why it matters."""
    answer, matched = match_answer(
        "What did you actually do today that moves you toward the life you "
        "picture in five years?", "strong")
    assert matched
    assert _topic_index(answer) == 1, "expected the time/planning topic"


def test_five_years_alone_does_not_mean_purpose():
    """A date is not a subject."""
    _, matched = match_answer("Where will you be in five years?", "strong")
    assert matched is False


def test_five_years_still_reads_as_purpose_with_a_defining_term():
    answer, matched = match_answer(
        "Picture this venture thriving five years from now -- what does "
        "'thriving' actually look like?", "strong")
    assert matched
    assert _topic_index(answer) == 9, "expected the purpose topic"


def test_hours_spent_is_a_time_question():
    answer, matched = match_answer(
        "Think about yesterday. How many actual hours went into this idea "
        "versus just thinking about it?", "strong")
    assert matched
    assert _topic_index(answer) == 1, "expected the time/planning topic"


def test_rivals_can_be_asked_about_without_the_word_competitor():
    answer, matched = match_answer(
        "Do you have any actual process for finding out who else solves this "
        "problem, or does it happen randomly?", "strong")
    assert matched
    assert _topic_index(answer) == 2, "expected the market/competitors topic"


def test_walk_marks_which_questions_got_the_generic_answer():
    """The summary separates bands the persona earned from bands the
    fallback earned; that needs a per-question flag."""
    out = []
    client = _Client(
        {"question": {"question_id": 1,
                      "question_text": "What colour is the sky?"}},
        [{"next_question": {"question_id": 2,
                            "question_text": "When did you last sit down "
                                             "specifically to plan?"}},
         {"is_complete": True, "next_question": None}],
    )
    _walk(client, "/start", "/answer", "question_id", "X", out, "strong")
    assert [q["_fell_back"] for q in out] == [True, False]


# --- the RESULT block --------------------------------------------------
#
# These exist because a NameError shipped here. The split was added, `bands`
# became `answered`, the flat-amber check three lines below still said
# `bands`, and RESULT died after the bands and before the pillars, model
# calls and cost. Every test covered the matching; none covered the
# reporting, so a paid run printed a traceback where its summary should
# have been.


def test_band_summary_runs_to_the_end():
    """The regression, stated plainly: it must not raise."""
    lines = band_summary([(1, "red"), (2, "green")], {1})
    assert lines and all(isinstance(x, str) for x in lines)


def test_band_summary_splits_generic_from_on_topic():
    lines = band_summary(
        [(1, "red"), (2, "red"), (3, "green"), (4, "amber")], {1, 2})
    assert "'red': 2" in lines[0] and "'green': 1" in lines[0]
    assert "on topic" in lines[1] and "'green': 1" in lines[1]
    assert "generic" in lines[2] and "'red': 2" in lines[2]


def test_band_summary_stays_quiet_when_nothing_fell_back():
    lines = band_summary([(1, "green"), (2, "green")], set())
    assert not [l for l in lines if "generic" in l or "on topic" in l]


def test_band_summary_still_flags_flat_amber():
    """Unscored answers reach the pipeline as one band for everything. That
    is about SCORING, not about this script's answers, and survived the
    refactor that broke its neighbour."""
    lines = band_summary([(1, "amber"), (2, "amber"), (3, "amber")], set())
    assert any("unscored fallback" in x for x in lines)


def test_band_summary_does_not_cry_flat_amber_on_a_real_spread():
    lines = band_summary([(1, "amber"), (2, "green"), (3, "red")], set())
    assert not any("unscored fallback" in x for x in lines)


def test_band_summary_handles_an_unscored_label():
    lines = band_summary([(1, None), (2, "green")], set())
    assert "unscored" in lines[0]


def test_band_summary_handles_no_answers_at_all():
    assert band_summary([], set()) == ["  answer bands            none"]


# --- the gaps that produced the last false findings ---------------------
#
# In the strong run, RC-001 and RC-003 "Lack of Customer Discovery" came
# back as ranks 1 and 2, both top findings, against a persona whose answer
# was "forty-one conversations with people I had never met". Both traced
# to the two Idea & Validation questions getting the generic reply: a
# two-question category with two fallbacks reads as 100% risk.


TOPIC = {name: i for i, name in enumerate([
    "customers", "time/plan", "market", "product", "pricing", "team", "risk",
    "decisions", "feedback", "purpose", "success", "pitch", "own_problem",
    "tooling", "wasted"])}


def _topic_of(question, persona="strong"):
    answer, matched = match_answer(question, persona)
    if not matched:
        return "FALLBACK"
    return [a for _, a in ANSWER_BANK[persona]].index(answer)


@pytest.mark.parametrize("question,topic", [
    # the two that made RC-001 and RC-003 top findings
    ("If a stranger asked you to explain this idea in one breath, what "
     "would you say -- no rehearsing, just the honest first version.", "pitch"),
    ("Think of the last time you personally ran into this problem "
     "yourself. Describe exactly what happened.", "own_problem"),
    # the forced choice on what success means
    ("When you picture doing this really well, what does 'well' actually "
     "mean to you -- being first, being the best, or being trusted?", "success"),
    # what it is being built WITH, three phrasings
    ("What tool, if any, are you currently using to build this -- even "
     "something simple like a no-code app or spreadsheet?", "tooling"),
    ("What's the simplest version of this you could put in front of "
     "someone today using only free or no-code tools?", "tooling"),
    ("Is there a specific reason you haven't used an existing tool or "
     "template to speed up building the first version?", "tooling"),
    # time WASTED, which is not how time is planned -- RC-974's two answers
    ("What's the one activity that eats the most time without actually "
     "moving this idea forward?", "wasted"),
    ("What's something you spent hours on this week that, looking back, "
     "didn't need that much time?", "wasted"),
    # a risk question that never says "risk"
    ("Have you ever sat down and specifically listed out everything that "
     "could seriously hurt this business?", "risk"),
])
def test_questions_that_used_to_fall_back_now_match(question, topic):
    assert _topic_of(question) == TOPIC[topic]


@pytest.mark.parametrize("persona", ["weak", "strong"])
def test_every_new_topic_has_an_answer_in_both_personas(persona):
    for name in ("success", "pitch", "own_problem", "tooling", "wasted"):
        answer = ANSWER_BANK[persona][TOPIC[name]][1]
        assert len(answer) > 80, f"{persona}/{name} is too thin to score"


def test_planning_and_wasted_time_stay_separate():
    """The planning answer describes protected Mondays and was correctly
    marked down on 'what eats the most time' -- it never names a waster.
    Two Founder Psychology answers, and RC-974 behind them."""
    planning = _topic_of("When was the last time you sat down specifically "
                         "to plan, not just to work?")
    wasted = _topic_of("What's the one activity that eats the most time "
                       "without actually moving this idea forward?")
    assert planning == TOPIC["time/plan"]
    assert wasted == TOPIC["wasted"]
    assert planning != wasted


def test_the_pitch_question_does_not_take_the_customer_answer():
    """'stranger' appears in both; only one of them is asking about people
    the founder has spoken to."""
    assert _topic_of("If a stranger asked you to explain this idea in one "
                     "breath, what would you say?") == TOPIC["pitch"]
    assert _topic_of("How many people outside your personal network have "
                     "you spoken to this month?") == TOPIC["customers"]


# --- reprompts and the counts ------------------------------------------
#
# A run printed:
#
#     Diagnosis: 12 question(s) answered (14 matched on topic,
#                -2 fell back to the generic answer)
#
# Two reprompts. `matched_count` was incremented when the answer was POSTED,
# but a rejected answer pops its question back off `out` -- so the counter
# kept two matches for questions that were no longer there, and the
# subtraction went negative. The counts are now derived from the questions
# that survived, which cannot disagree with each other.



def test_a_reprompt_does_not_leave_a_phantom_match(capsys):
    """The exact defect: one accepted answer, one rejected-then-dropped."""
    on_topic = {"question_id": 1, "question_text": ANALYTICS_Q}
    out = []
    client = _Client(
        {"question": on_topic},
        [{"accepted": False},                      # rejected -> popped
         {"is_complete": True, "next_question": None}],
    )
    _walk(client, "/start", "/answer", "question_id", "X", out, "strong")
    printed = capsys.readouterr().out
    assert len(out) == 1
    assert "1 question(s) answered" in printed
    assert "1 matched on topic" in printed
    assert "fell back" not in printed, printed
    assert "-" not in printed.split("answered", 1)[1]


def test_counts_never_go_negative_however_many_reprompts(capsys):
    """Three reprompts is the limit; the arithmetic must survive all of them."""
    on_topic = {"question_id": 1, "question_text": ANALYTICS_Q}
    out = []
    client = _Client(
        {"question": on_topic},
        [{"accepted": False}, {"accepted": False}, {"accepted": False},
         {"is_complete": True, "next_question": None}],
    )
    assert _walk(client, "/start", "/answer", "question_id", "X", out,
                 "strong") is True
    printed = capsys.readouterr().out
    assert "1 question(s) answered (1 matched on topic)" in printed


def test_answered_and_matched_always_reconcile(capsys):
    """answered = matched + fell_back, whatever the mix."""
    out = []
    client = _Client(
        {"question": {"question_id": 1, "question_text": ANALYTICS_Q}},
        [{"accepted": False},
         {"next_question": {"question_id": 2,
                            "question_text": "What colour is the sky?"}},
         {"is_complete": True, "next_question": None}],
    )
    _walk(client, "/start", "/answer", "question_id", "X", out, "strong")
    printed = capsys.readouterr().out
    assert "2 question(s) answered (1 matched on topic, 1 fell back" in printed


def test_walk_counts_only_its_own_questions(capsys):
    """`out` accumulates across phases in the real run; a walk must report
    what IT served, not everything collected so far."""
    out = [{"question_id": 99, "question_text": "from an earlier phase",
            "_fell_back": True}]
    client = _Client(
        {"question": {"question_id": 1, "question_text": ANALYTICS_Q}},
        [{"is_complete": True, "next_question": None}],
    )
    _walk(client, "/start", "/answer", "question_id", "X", out, "strong")
    printed = capsys.readouterr().out
    assert "1 question(s) answered (1 matched on topic)" in printed
    assert len(out) == 2


# --- comparing two runs that answered different numbers of questions ---
#
# The strong run finished at 12 answers, the weak one at 14. That is the
# engine ending the session once confidence clears the routing threshold,
# not the harness dropping two questions -- but "10 green" against "8 green"
# with no denominator reads like the former. Both the share line and
# stop_reason() exist so the two runs can be put side by side.


def test_band_lines_carry_a_denominator():
    lines = band_summary([(1, "green")] * 10 + [(2, "red"), (3, "amber")], set())
    share = [l for l in lines if "share of" in l]
    assert share, lines
    assert "12" in share[0]
    assert "green 83%" in share[0]


def test_shares_make_different_question_counts_comparable():
    """8 of 14 and 10 of 12 are not the same run, and must not read as one."""
    weak = band_summary([(i, "green") for i in range(8)]
                        + [(i, "red") for i in range(8, 14)], set())
    strong = band_summary([(i, "green") for i in range(10)]
                          + [(i, "red") for i in range(10, 12)], set())
    assert "green 57%" in "".join(weak)
    assert "green 83%" in "".join(strong)


def test_no_share_line_when_nothing_was_answered():
    assert not [l for l in band_summary([], set()) if "share of" in l]


def test_stop_reason_names_the_confidence_that_ended_the_session():
    line = stop_reason((12, "generate_report", 82.0))
    assert "12 answers" in line
    assert "82" in line
    assert "generate_report" in line
    assert ">80" in line, "the threshold is what explains the early stop"


def test_stop_reason_covers_every_routing_state_the_database_allows():
    """Read off the sessions_routing_state_check constraint, so a new state
    added to the schema turns this red instead of printing a bare value."""
    import re

    from app.core.paths import BACKEND_DIR
    from scripts.e2e_journey_check import _ROUTING_MEANING

    schema = (BACKEND_DIR / "app" / "models" / "schema.py").read_text(
        encoding="utf-8")
    clause = re.search(r"name='sessions_routing_state_check'", schema)
    assert clause, "the constraint moved; this test needs updating"
    line = schema[:clause.start()].rsplit("CheckConstraint", 1)[1]
    states = set(re.findall(r"'(\w+)'::character varying", line))
    assert states, line
    assert states <= set(_ROUTING_MEANING), (
        f"routing states with no explanation in the harness: "
        f"{states - set(_ROUTING_MEANING)}")
    for state in states:
        assert _ROUTING_MEANING[state] in stop_reason((5, state, 40))


def test_stop_reason_survives_a_null_confidence():
    """A session row exists before the engine has scored anything."""
    assert "?" in stop_reason((1, "continue", None))


def test_stop_reason_survives_an_unknown_routing_state():
    line = stop_reason((3, "something_new", 50))
    assert "something_new" in line


def test_stop_reason_says_so_when_there_is_no_session():
    assert "not found" in stop_reason(None)


# --- when the stored score and the state disagree ----------------------
#
# A completed live run printed:
#
#   stopped after 12 answers -- routing_state 'generate_report' at
#   confidence 80   (>80 = confident enough to report, stop asking)
#
# which reads as 80 being greater than 80. Both numbers are real:
# questioning stopped at 82, then the report pipeline recomputed confidence
# with answer_consistency available -- a factor that has no data until the
# answers exist -- and wrote 80 back to the session. The line now says so
# rather than presenting a contradiction as a derivation.


def test_a_score_below_its_states_band_is_explained():
    line = stop_reason((12, "generate_report", 80.0))
    assert "recompute" in line
    assert "DURING questioning" in line


def test_a_score_inside_its_band_needs_no_explanation():
    line = stop_reason((12, "generate_report", 82.0))
    assert "recompute" not in line
    assert ">80" in line


@pytest.mark.parametrize("state,confidence", [
    ("continue", 45.0),
    ("validate", 70.0),
    ("validate", 80.0),
    ("generate_report", 100.0),
])
def test_scores_inside_their_bands_stay_quiet(state, confidence):
    assert "recompute" not in stop_reason((5, state, confidence))


@pytest.mark.parametrize("state,confidence", [
    ("continue", 75.0),
    ("validate", 20.0),
    ("generate_report", 30.0),
])
def test_scores_outside_their_bands_are_flagged(state, confidence):
    assert "recompute" in stop_reason((5, state, confidence))


def test_distress_support_is_never_called_inconsistent():
    """It is not reached by a confidence threshold, so no score contradicts it."""
    for confidence in (0.0, 50.0, 100.0):
        assert "recompute" not in stop_reason((5, "distress_support", confidence))


def test_an_unknown_state_is_never_called_inconsistent():
    assert "recompute" not in stop_reason((5, "something_new", 50.0))


def test_a_null_confidence_is_not_compared():
    assert "recompute" not in stop_reason((5, "generate_report", None))
