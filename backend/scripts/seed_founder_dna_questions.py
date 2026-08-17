"""Seed the phase-2 Founder DNA question bank (founder_dna_questions).

Content for the 6 dimensions with no prior data source (Purpose & Mission,
Core Values & Non-Negotiables, Mindset & Excellence Standard, Energy
Patterns, Decision Style, Focus/Attention & Response Patterns) --
GoXL_Founder_DNA_Decoding_Journey.docx, and the project decision to start
with a small text-only set (~3 per dimension per stage) rather than the
doc's full exhaustive bank, matching the doc's own framing of its example
table as "a sample set per stage, not the exhaustive bank."

Situational/story-based per the doc's working principle (Section 1: "depth
comes from situational, story-based questions -- not from asking more
abstract self-rating questions"), and toned per stage the same way the doc's
own example table is (Section 5): Stage 0 warm/reflective, Stage 0->1
sharp/fast, Stage 1->10+ direct/challenging.

Safety: idempotent (skips a (dimension_code, stage_group, question_text)
already present), INSERT-only.

Usage:
    python -m scripts.seed_founder_dna_questions
"""

from __future__ import annotations

from app.db.session import SessionLocal
from app.models.enums import FounderDnaDimension, FounderDnaFormat, StageGroup
from app.models.schema import FounderDnaQuestions

S0 = StageGroup.STAGE_0.value
S1 = StageGroup.STAGE_0_TO_1.value
S2 = StageGroup.STAGE_1_TO_10_PLUS.value
NARRATIVE = FounderDnaFormat.NARRATIVE.value
SCENARIO = FounderDnaFormat.SCENARIO.value

# (dimension_code, stage_group, format, question_text)
QUESTIONS: list[tuple[str, str, str, str]] = [
    # --- Purpose & Mission ---
    (FounderDnaDimension.PURPOSE_MISSION.value, S0, NARRATIVE,
     "In one sentence, why does this problem deserve your next few years?"),
    (FounderDnaDimension.PURPOSE_MISSION.value, S0, NARRATIVE,
     "If this succeeds completely, what changes for the people you're building it for?"),
    (FounderDnaDimension.PURPOSE_MISSION.value, S0, NARRATIVE,
     "When you imagine telling someone what you're building in one line, what do you actually say?"),
    (FounderDnaDimension.PURPOSE_MISSION.value, S1, NARRATIVE,
     "If you had to defend why this still deserves your time, in one sentence -- has that sentence changed since you started?"),
    (FounderDnaDimension.PURPOSE_MISSION.value, S1, NARRATIVE,
     "What's the one number that, if it moved, would tell you the mission is actually working -- not just the business?"),
    (FounderDnaDimension.PURPOSE_MISSION.value, S1, NARRATIVE,
     "What would you keep doing even if it stopped making money?"),
    (FounderDnaDimension.PURPOSE_MISSION.value, S2, NARRATIVE,
     "What does this venture being 'done' even mean to you -- does it end, or does it just change shape?"),
    (FounderDnaDimension.PURPOSE_MISSION.value, S2, NARRATIVE,
     "If you stepped away for a year, what's the one thing about this business you'd want to still be true when you came back?"),
    (FounderDnaDimension.PURPOSE_MISSION.value, S2, SCENARIO,
     "Has the mission actually shaped a real decision this quarter, or has it become a slide nobody reads?"),

    # --- Core Values & Non-Negotiables ---
    (FounderDnaDimension.CORE_VALUES.value, S0, SCENARIO,
     "Tell me about a time before this venture when you walked away from something because it crossed a line for you. What was the line?"),
    (FounderDnaDimension.CORE_VALUES.value, S0, NARRATIVE,
     "What's something you'd refuse to do to get this off the ground, even if it would clearly help?"),
    (FounderDnaDimension.CORE_VALUES.value, S0, SCENARIO,
     "If a mentor told you the fastest path forward required cutting a corner you cared about, what would you actually do?"),
    (FounderDnaDimension.CORE_VALUES.value, S1, SCENARIO,
     "Tell me about the last time growth tempted you to compromise on something you said mattered. What happened?"),
    (FounderDnaDimension.CORE_VALUES.value, S1, NARRATIVE,
     "What's one thing you won't do for a customer, even a big one, no matter how much they ask?"),
    (FounderDnaDimension.CORE_VALUES.value, S1, SCENARIO,
     "Is there a standard you've quietly lowered since you started, that you haven't admitted to yourself?"),
    (FounderDnaDimension.CORE_VALUES.value, S2, SCENARIO,
     "Tell me about a value you held in year one that the business has genuinely outgrown -- was that a compromise or real growth?"),
    (FounderDnaDimension.CORE_VALUES.value, S2, SCENARIO,
     "When someone on your team crosses a line you care about, what actually happens to them?"),
    (FounderDnaDimension.CORE_VALUES.value, S2, NARRATIVE,
     "What's a non-negotiable you'd defend even if the board pushed back on it?"),

    # --- Mindset & Excellence Standard ---
    (FounderDnaDimension.MINDSET_EXCELLENCE.value, S0, NARRATIVE,
     "When you picture doing this really well, what does 'well' actually mean to you -- being first, being the best, or being trusted?"),
    (FounderDnaDimension.MINDSET_EXCELLENCE.value, S0, SCENARIO,
     "Tell me about something you're proud of that nobody else noticed. What made it feel like quality to you?"),
    (FounderDnaDimension.MINDSET_EXCELLENCE.value, S0, SCENARIO,
     "Someone far more experienced than you dismisses your idea in one sentence. What's your honest first internal reaction -- before you compose yourself?"),
    (FounderDnaDimension.MINDSET_EXCELLENCE.value, S1, SCENARIO,
     "Tell me about the last thing you shipped that you weren't fully happy with, but shipped anyway. Why?"),
    (FounderDnaDimension.MINDSET_EXCELLENCE.value, S1, NARRATIVE,
     "When perfectionism has cost you time recently, what did it actually look like?"),
    (FounderDnaDimension.MINDSET_EXCELLENCE.value, S1, NARRATIVE,
     "What's the difference between 'good enough to ship' and 'actually good' for you right now -- and which one are you optimising for?"),
    (FounderDnaDimension.MINDSET_EXCELLENCE.value, S2, SCENARIO,
     "Tell me about a standard you refused to lower, even when it cost you time or money."),
    (FounderDnaDimension.MINDSET_EXCELLENCE.value, S2, NARRATIVE,
     "When you look at your team's output today versus your own bar, where's the gap -- and whose fault is that gap?"),
    (FounderDnaDimension.MINDSET_EXCELLENCE.value, S2, NARRATIVE,
     "What's a shortcut you've started tolerating that year-one you would have refused?"),

    # --- Energy Patterns ---
    (FounderDnaDimension.ENERGY_PATTERNS.value, S0, SCENARIO,
     "Think about the last time you lost track of time working on this. What were you actually doing?"),
    (FounderDnaDimension.ENERGY_PATTERNS.value, S0, NARRATIVE,
     "What's the part of building this that quietly drains you, even though you'd never say it out loud?"),
    (FounderDnaDimension.ENERGY_PATTERNS.value, S0, NARRATIVE,
     "When do you do your best thinking -- and are you actually protecting that time right now?"),
    (FounderDnaDimension.ENERGY_PATTERNS.value, S1, SCENARIO,
     "Tell me about the last week that left you completely wiped out. What was different about it?"),
    (FounderDnaDimension.ENERGY_PATTERNS.value, S1, NARRATIVE,
     "What's one task you keep procrastinating on because it drains you more than the others?"),
    (FounderDnaDimension.ENERGY_PATTERNS.value, S1, NARRATIVE,
     "If you had one extra focused hour today with no interruptions, what would you actually spend it on?"),
    (FounderDnaDimension.ENERGY_PATTERNS.value, S2, NARRATIVE,
     "What part of running this business today would you hand off first if you genuinely could, purely because it drains you?"),
    (FounderDnaDimension.ENERGY_PATTERNS.value, S2, SCENARIO,
     "Tell me about the last time you felt real momentum. What conditions made that possible?"),
    (FounderDnaDimension.ENERGY_PATTERNS.value, S2, NARRATIVE,
     "Has what energises you about this business changed since year one -- and have you adjusted your role to match?"),

    # --- Decision Style ---
    (FounderDnaDimension.DECISION_STYLE.value, S0, NARRATIVE,
     "When you face a big unknown, do you decide fast and adjust as you go, or gather everything you can before you move?"),
    (FounderDnaDimension.DECISION_STYLE.value, S0, SCENARIO,
     "Tell me about the last real decision you made for this idea. Walk me through how you actually got there."),
    (FounderDnaDimension.DECISION_STYLE.value, S0, NARRATIVE,
     "When you're stuck between two options, what do you actually do to break the tie?"),
    (FounderDnaDimension.DECISION_STYLE.value, S1, SCENARIO,
     "Tell me about the last decision you made that you'd now call rushed. What did you skip?"),
    (FounderDnaDimension.DECISION_STYLE.value, S1, NARRATIVE,
     "When data and your gut disagree, which one has actually won more often for you?"),
    (FounderDnaDimension.DECISION_STYLE.value, S1, SCENARIO,
     "Walk me through the last time you asked someone else's opinion before deciding something you could have decided alone. Why that time?"),
    (FounderDnaDimension.DECISION_STYLE.value, S2, SCENARIO,
     "In your last real crisis, were you closer to steering alone, or bracing with the team?"),
    (FounderDnaDimension.DECISION_STYLE.value, S2, SCENARIO,
     "Tell me about a decision you delegated that you regretted delegating -- what went wrong in how you handed it off?"),
    (FounderDnaDimension.DECISION_STYLE.value, S2, NARRATIVE,
     "How has your decision-making changed now that a wrong call costs more than it did in year one?"),

    # --- Focus, Attention & Response Patterns ---
    (FounderDnaDimension.FOCUS_ATTENTION.value, S0, NARRATIVE,
     "What's actually pulling your attention away from this idea most days -- be specific."),
    (FounderDnaDimension.FOCUS_ATTENTION.value, S0, SCENARIO,
     "Tell me about the last time you sat with one problem for a long stretch without switching to something else. What made that possible?"),
    (FounderDnaDimension.FOCUS_ATTENTION.value, S0, NARRATIVE,
     "When something urgent interrupts your plan for the day, what usually happens to the plan?"),
    (FounderDnaDimension.FOCUS_ATTENTION.value, S1, NARRATIVE,
     "How many things are you actively trying to move forward on right now, all competing for the same hours?"),
    (FounderDnaDimension.FOCUS_ATTENTION.value, S1, SCENARIO,
     "Tell me about the last time you context-switched mid-task and lost real time to it. What triggered the switch?"),
    (FounderDnaDimension.FOCUS_ATTENTION.value, S1, NARRATIVE,
     "Is there any time in your week that's actually protected for important-not-urgent work, or does urgent always win?"),
    (FounderDnaDimension.FOCUS_ATTENTION.value, S2, NARRATIVE,
     "Does solving an urgent problem feel more satisfying than making progress on what actually matters long-term?"),
    (FounderDnaDimension.FOCUS_ATTENTION.value, S2, SCENARIO,
     "Tell me about the last time you were pulled into something that should have been someone else's to handle. Why did it land on you?"),
    (FounderDnaDimension.FOCUS_ATTENTION.value, S2, NARRATIVE,
     "When you look at your calendar from last week, how much of it was actually spent on what you'd call the highest-leverage work?"),
]


def seed() -> int:
    db = SessionLocal()
    inserted = 0
    try:
        existing = {
            (q.dimension_code, q.stage_group, q.question_text)
            for q in db.query(FounderDnaQuestions).all()
        }
        for dimension_code, stage_group, fmt, question_text in QUESTIONS:
            key = (dimension_code, stage_group, question_text)
            if key in existing:
                continue
            db.add(FounderDnaQuestions(
                dimension_code=dimension_code, stage_group=stage_group,
                format=fmt, question_text=question_text, is_active=True,
            ))
            inserted += 1
        db.commit()
        return inserted
    finally:
        db.close()


if __name__ == "__main__":
    count = seed()
    print(f"Inserted {count} founder_dna_questions row(s) "
          f"({len(QUESTIONS)} defined total; rest already present).")
