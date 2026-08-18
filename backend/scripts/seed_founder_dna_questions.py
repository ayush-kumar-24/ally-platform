"""Seed the Founder DNA question bank (founder_dna_questions).

Follows `GoXL_Founder_DNA_Decoding_Journey.docx`: all thirteen dimensions
from its Section 2, plus an Emotional Intelligence dimension GoXL added on
top -- fourteen asked dimensions, one base question each.

Shape of a stage:
  * 14 BASE questions, one per dimension, pinned to a slot in the doc's
    narrative arc (`arc_position`). Ordered emotional/identity first,
    structured last, per Section 3. These always run.
  * The last of them is the CLOSING question (`is_closing`) -- the doc's
    "wow close", always asked last, never skipped.
  * Up to 2 adaptive FOLLOW-UPS (arc_position 90+) for dimensions the
    resolution advisor judges unresolved -> 14 min, 16 max.

Sourcing rules, so deviations are deliberate:

  * Doc questions are used VERBATIM wherever the doc provides one for a
    dimension. Some are abstract rather than story-based, which sits against
    the doc's own Section 1 principle -- but GoXL's authored text wins over
    my rewrite of it. Questions I author are situational (what actually
    happened), which is where that principle is mine to apply.

  * The doc's four Forced Choice questions keep that format (`options`).
    Its six Visual two-image questions have no text equivalent that keeps
    their intent, so where one carried a dimension we need (Motivation,
    Energy, Decision Style, Risk) a situational text question stands in --
    v1 is text-only.

  * `archetype` is asked through the doc's "Identity" rows, not a self-label
    pick: archetype.py infers the archetype from the founder's own language,
    so it needs language rather than a label.

  * `origin` and `vision` are also onboarding fields. Asked here too by
    product decision; the asked answer wins (see _persist's update order).

Safety: idempotent per (dimension_code, stage_group, question_text),
INSERT-only. --replace refreshes the bank wholesale, refusing if any answers
reference it.

Usage:
    python -m scripts.seed_founder_dna_questions [--replace]
"""

from __future__ import annotations

import sys
from collections import Counter

from app.db.session import SessionLocal
from app.models.enums import FounderDnaDimension as D
from app.models.enums import FounderDnaFormat, StageGroup
from app.models.schema import FounderDnaAnswers, FounderDnaQuestions

S0 = StageGroup.STAGE_0.value
S1 = StageGroup.STAGE_0_TO_1.value
S2 = StageGroup.STAGE_1_TO_10_PLUS.value

NARR = FounderDnaFormat.NARRATIVE.value
SCEN = FounderDnaFormat.SCENARIO.value
CHOICE = FounderDnaFormat.FORCED_CHOICE.value

# (dimension, stage, arc_position, format, question_text, options, is_closing)
QUESTIONS: list[tuple] = [

    # ================= STAGE 0 -- The Idea Stage =====================
    # Tone: warm, reflective, validating. Ally is a mirror.
    (D.ORIGIN, S0, 1, NARR,
     "Picture the moment this idea first properly grabbed you -- where were "
     "you, and what actually triggered it?", None, False),
    (D.ARCHETYPE, S0, 2, NARR,
     "If you were writing the opening line of your own founder origin story, "
     "what would it say?", None, False),
    (D.MINDSET_EXCELLENCE, S0, 3, CHOICE,
     "When you picture doing this really well, what does 'well' actually mean "
     "to you -- being first, being the best, or being trusted?",
     ["Being first", "Being the best", "Being trusted"], False),
    (D.CORE_MOTIVATION, S0, 4, SCEN,
     "Think about the last thing you built or finished that genuinely "
     "satisfied you -- before this venture, even. What about it landed?",
     None, False),
    (D.EMOTIONAL_INTELLIGENCE, S0, 5, SCEN,
     "Someone far more experienced than you dismisses your idea in one "
     "sentence. What's your honest first internal reaction -- before you "
     "compose yourself?", None, False),
    (D.PURPOSE_MISSION, S0, 6, NARR,
     "In one sentence, why does this problem deserve your next few years?",
     None, False),
    (D.VISION, S0, 7, NARR,
     "Picture this venture thriving five years from now -- what does "
     "'thriving' actually look like, concretely?", None, False),
    (D.CORE_VALUES, S0, 8, SCEN,
     "Tell me about a time before this venture when you walked away from "
     "something because it crossed a line for you. What was the line?",
     None, False),
    (D.ENERGY_PATTERNS, S0, 9, SCEN,
     "Think about the last time you finished a day genuinely energised rather "
     "than drained. What had you been doing, and who was around?",
     None, False),
    (D.DECISION_STYLE, S0, 10, CHOICE,
     "When you face a big unknown, do you decide fast and adjust as you go, "
     "or gather everything you can before you move?",
     ["Decide fast and adjust", "Gather everything first"], False),
    (D.STRESS_RESPONSE, S0, 11, SCEN,
     "Think of the last time you faced real uncertainty outside of work. What "
     "did you actually do -- not what you wish you'd done?", None, False),
    (D.STRENGTHS_BLIND_SPOTS, S0, 12, SCEN,
     "Tell me about the last time someone who knows you well pointed out "
     "something about how you work that you hadn't seen. What was it?",
     None, False),
    (D.COMMUNICATION_PREFERENCE, S0, 13, CHOICE,
     "When something's going wrong, do you want it told to you straight, laid "
     "out step by step, or talked through out loud?",
     ["Told straight", "Laid out step by step", "Talked through out loud"],
     False),
    (D.FOCUS_ATTENTION, S0, 14, SCEN,
     "Tell me about the last time you sat with one problem for a long stretch "
     "without switching to something else. What made that possible?",
     None, False),
    (D.PURPOSE_MISSION, S0, 99, NARR,   # wow close
     "If your future self, five years into this, sent you one sentence of "
     "advice right now -- what would it say?", None, True),

    # Follow-ups
    (D.PURPOSE_MISSION, S0, 90, SCEN,
     "Tell me about the last time you seriously considered dropping this "
     "idea. What actually made you stay with it?", None, False),
    (D.DECISION_STYLE, S0, 91, SCEN,
     "Tell me about the last real decision you made for this idea. Walk me "
     "through how you actually got there.", None, False),
    (D.ENERGY_PATTERNS, S0, 92, SCEN,
     "Tell me about the last time working on this left you completely "
     "drained. What had you been doing that day?", None, False),
    (D.EMOTIONAL_INTELLIGENCE, S0, 93, SCEN,
     "Tell me about the last time you had to give someone difficult feedback. "
     "How did you handle it?", None, False),

    # ============ STAGE 0->1 -- Building & Early Traction ============
    # Tone: sharp, fast, decisive. Ally is a compass.
    (D.ORIGIN, S1, 1, SCEN,
     "Think back to the moment you decided this was worth actually building, "
     "not just thinking about. What tipped it?", None, False),
    (D.ARCHETYPE, S1, 2, NARR,
     "What's actually different about how you show up now versus before you "
     "started building?", None, False),
    (D.MINDSET_EXCELLENCE, S1, 3, SCEN,
     "Tell me about the last thing you shipped that you weren't fully happy "
     "with, but shipped anyway. Why?", None, False),
    (D.CORE_MOTIVATION, S1, 4, SCEN,
     "Tell me about the last win here that actually felt good. What made that "
     "one land more than the others?", None, False),
    (D.EMOTIONAL_INTELLIGENCE, S1, 5, SCEN,
     "Walk me through the last time you were completely overwhelmed. What did "
     "you actually do -- push through, shut down, or reach out?", None, False),
    (D.PURPOSE_MISSION, S1, 6, NARR,
     "If you had to defend why this still deserves your time, in one sentence "
     "-- has that sentence changed since you started?", None, False),
    (D.VISION, S1, 7, NARR,
     "What's the one number that, if it moved, would tell you this is really "
     "working?", None, False),
    (D.CORE_VALUES, S1, 8, SCEN,
     "Tell me about the last time growth tempted you to compromise on "
     "something you'd said mattered. What happened?", None, False),
    (D.ENERGY_PATTERNS, S1, 9, SCEN,
     "Tell me about the last stretch of work here that gave you real "
     "momentum. What conditions made it possible?", None, False),
    (D.DECISION_STYLE, S1, 10, CHOICE,
     "Thinking about how you're actually building right now -- are you working "
     "to a plan you set in advance, or figuring it out as you go?",
     ["To a plan set in advance", "Figuring it out as I go"], False),
    (D.STRESS_RESPONSE, S1, 11, SCEN,
     "Tell me about the last week here that genuinely got to you. What did "
     "you do with it?", None, False),
    (D.STRENGTHS_BLIND_SPOTS, S1, 12, SCEN,
     "Tell me about something you've had to learn the hard way since starting "
     "to build. What did you get wrong first?", None, False),
    (D.COMMUNICATION_PREFERENCE, S1, 13, CHOICE,
     "When something's going wrong, do you want it told to you straight, laid "
     "out step by step, or talked through out loud?",
     ["Told straight", "Laid out step by step", "Talked through out loud"],
     False),
    (D.FOCUS_ATTENTION, S1, 14, SCEN,
     "Tell me about the last time you context-switched mid-task and lost real "
     "time to it. What pulled you away?", None, False),
    (D.EMOTIONAL_INTELLIGENCE, S1, 99, NARR,   # wow close
     "What's the thing about running this that you haven't told anyone yet?",
     None, True),

    # Follow-ups
    (D.PURPOSE_MISSION, S1, 90, NARR,
     "What's the thing you're doing right now that isn't scalable, but you're "
     "doing anyway -- and why?", None, False),
    (D.MINDSET_EXCELLENCE, S1, 91, SCEN,
     "Tell me about the last time perfectionism cost you real time here. What "
     "were you polishing, and what did it delay?", None, False),
    (D.DECISION_STYLE, S1, 92, SCEN,
     "Tell me about the last decision you made here that you'd now call "
     "rushed. What did you skip?", None, False),
    (D.ENERGY_PATTERNS, S1, 93, SCEN,
     "Tell me about the last week that left you wiped out. What was different "
     "about it?", None, False),

    # ================ STAGE 1->10+ -- Scaling ========================
    # Tone: direct, challenging, structural. Ally audits blind spots.
    (D.ORIGIN, S2, 1, SCEN,
     "Think back to why you started this in the first place. Tell me about "
     "the moment that made it feel necessary rather than optional.",
     None, False),
    (D.ARCHETYPE, S2, 2, NARR,
     "Who were you as a leader in year one, and who are you now -- what's the "
     "actual difference?", None, False),
    (D.MINDSET_EXCELLENCE, S2, 3, SCEN,
     "Tell me about a standard you refused to lower, even when it cost you "
     "time or money.", None, False),
    (D.CORE_MOTIVATION, S2, 4, SCEN,
     "Tell me about the last thing this business achieved that genuinely "
     "moved you. What was it about that one?", None, False),
    (D.EMOTIONAL_INTELLIGENCE, S2, 5, SCEN,
     "Tell me about the last time you were wrong about a person on your team. "
     "What did that actually cost you?", None, False),
    (D.PURPOSE_MISSION, S2, 6, NARR,
     "What does this venture being 'done' even mean to you -- does it end, or "
     "does it just change shape?", None, False),
    (D.VISION, S2, 7, NARR,
     "If you stepped away for a year, what's the one thing about this business "
     "you'd want to still be true when you came back?", None, False),
    (D.CORE_VALUES, S2, 8, SCEN,
     "Tell me about the last time someone on your team crossed a line you "
     "care about. What actually happened next?", None, False),
    (D.ENERGY_PATTERNS, S2, 9, SCEN,
     "Tell me about the last thing you did here that you'd hand off tomorrow "
     "if you could, purely because it drains you. What was it?", None, False),
    (D.DECISION_STYLE, S2, 10, CHOICE,
     "In your last real crisis, were you closer to steering alone, or bracing "
     "with the team?",
     ["Steering alone", "Bracing with the team"], False),
    (D.STRESS_RESPONSE, S2, 11, SCEN,
     "Tell me about the last stretch here that genuinely wore you down. What "
     "did you actually do about it?", None, False),
    (D.STRENGTHS_BLIND_SPOTS, S2, 12, SCEN,
     "Tell me about the last time a senior person on your team told you "
     "something about yourself you didn't want to hear. What was it?",
     None, False),
    (D.COMMUNICATION_PREFERENCE, S2, 13, CHOICE,
     "When you hand something off, do you check in daily, weekly, or only "
     "when it's flagged to you?",
     ["Daily", "Weekly", "Only when it's flagged"], False),
    (D.FOCUS_ATTENTION, S2, 14, SCEN,
     "Tell me about the last time you were pulled into something that should "
     "have been someone else's to handle. Why did it land on you?",
     None, False),
    (D.PURPOSE_MISSION, S2, 99, NARR,   # wow close
     "If your company outlives you, what's the one decision you hope nobody "
     "ever has to unmake?", None, True),

    # Follow-ups
    (D.PURPOSE_MISSION, S2, 90, NARR,
     "What's the one thing you still do yourself that you know, honestly, you "
     "should have handed off by now?", None, False),
    (D.DECISION_STYLE, S2, 91, SCEN,
     "Tell me about a decision you delegated and then regretted delegating. "
     "What went wrong in how you handed it over?", None, False),
    (D.ENERGY_PATTERNS, S2, 92, SCEN,
     "Tell me about the last time you felt genuinely in flow running this. "
     "What were you doing?", None, False),
    (D.CORE_VALUES, S2, 93, SCEN,
     "Tell me about the last time you turned down money or growth because of "
     "something you weren't willing to trade. What was it?", None, False),
]


def _rows():
    for dim, stage, arc, fmt, textq, options, closing in QUESTIONS:
        yield dict(
            dimension_code=dim.value, stage_group=stage, arc_position=arc,
            format=fmt, question_text=textq, options=options,
            is_closing=closing, is_active=True,
        )


def seed(replace: bool = False) -> tuple[int, int]:
    db = SessionLocal()
    try:
        deleted = 0
        if replace:
            if db.query(FounderDnaAnswers).count():
                raise SystemExit(
                    "Refusing --replace: founder_dna_answers rows reference "
                    "this bank. Clear them first, or seed without --replace."
                )
            deleted = db.query(FounderDnaQuestions).delete()

        existing = {
            (q.dimension_code, q.stage_group, q.question_text)
            for q in db.query(FounderDnaQuestions).all()
        }
        inserted = 0
        for row in _rows():
            key = (row['dimension_code'], row['stage_group'], row['question_text'])
            if key in existing:
                continue
            db.add(FounderDnaQuestions(**row))
            inserted += 1
        db.commit()
        return inserted, deleted
    finally:
        db.close()


def _selfcheck() -> None:
    """Fail loudly on a bank that would ask the wrong thing -- cheaper to
    catch here than from a founder's half-empty dashboard."""
    all_dims = {d.value for d in D}
    for stage in (S0, S1, S2):
        rows = [q for q in QUESTIONS if q[1] == stage]
        base = [q for q in rows if q[2] < 90]
        closing = [q for q in rows if q[6]]
        covered = {q[0].value for q in base}

        missing = all_dims - covered
        assert not missing, f"{stage}: dimensions never asked: {sorted(missing)}"
        assert len(closing) == 1, f"{stage}: expected 1 closing, got {len(closing)}"
        assert closing[0][2] == 99, f"{stage}: closing must sit at arc 99"
        positions = [q[2] for q in base]
        assert len(positions) == len(set(positions)), \
            f"{stage}: duplicate arc_position in base journey"
        for q in rows:
            has_opts = q[5] is not None
            is_choice = q[3] == CHOICE
            assert has_opts == is_choice, \
                f"{stage}: options/forced_choice mismatch: {q[4][:50]}"


if __name__ == "__main__":
    _selfcheck()
    ins, dele = seed(replace="--replace" in sys.argv)
    per_stage = Counter(q[1] for q in QUESTIONS)
    base = Counter(q[1] for q in QUESTIONS if q[2] < 90)
    print(f"deleted {dele}, inserted {ins} (of {len(QUESTIONS)} defined)")
    for stage in (S0, S1, S2):
        print(f"  {stage:14} base={base[stage]:2} (14 dims + close) "
              f"total_in_bank={per_stage[stage]:2}")
    print("=> 14 asked minimum, 16 maximum (2 adaptive follow-ups)")
