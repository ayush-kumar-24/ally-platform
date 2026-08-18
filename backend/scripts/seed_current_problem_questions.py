"""Seed the Current Problem question bank.

Four rows per stage group, twelve total:

  arc 0  -- the founder states the symptom IN THEIR OWN WORDS (is_symptom).
            The Stage-Adaptive doc does not script this one, because its
            whole point is that it is unscripted; the wording below only has
            to get an unrehearsed answer, so it says so explicitly. The
            report quotes this verbatim.
  arc 1-3 -- the doc's s4.1.c / s4.2.c / s4.3.c situational questions, copied
            word for word. They are not paraphrased: the doc's Stage 0 probes
            are built to expose fear-as-research, the Stage 0->1 probes to
            expose validation-as-marketing, and the Stage 1->10+ probes to
            expose structure-as-people. Rewording them loses the trap.

Idempotent -- matches on (stage_group, arc_position) and updates in place, so
re-running after a wording change edits rather than duplicates.

    python -m scripts.seed_current_problem_questions
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.schema import CurrentProblemQuestions

STAGE_0 = "Stage 0"
STAGE_0_1 = "Stage 0→1"
STAGE_1_10 = "Stage 1→10+"

#: (stage_group, arc_position, is_symptom, question_text)
QUESTIONS: tuple[tuple[str, int, bool, str], ...] = (
    # --- Stage 0 -- idea only. Root-cause zone: clarity & conviction gaps. ---
    (STAGE_0, 0, True,
     "Now the part that matters most. In your own words, what is the single "
     "biggest thing standing between you and actually starting? Don't polish "
     "it -- say it the way you'd say it to a friend at the end of a long day."),
    (STAGE_0, 1, False,
     "What is the one thing that would need to be true this week for you to "
     "actually start?"),
    (STAGE_0, 2, False,
     "What have you already tried to move this forward -- a call, a sketch, a "
     "search -- and why did it stall out?"),
    (STAGE_0, 3, False,
     "If I asked you to talk to one real potential customer this week, what's "
     "stopping you from already having done that?"),

    # --- Stage 0->1 -- launched, underwater. Zone: execution & prioritisation. ---
    (STAGE_0_1, 0, True,
     "Now the part that matters most. In your own words, what is the single "
     "biggest problem in your business right now? Don't polish it -- say it "
     "the way you'd say it to a friend at the end of a long day."),
    (STAGE_0_1, 1, False,
     "What's the one thing that, if it broke tomorrow, would stop the business "
     "cold?"),
    (STAGE_0_1, 2, False,
     "Tell me about the last time you and a co-founder or teammate disagreed "
     "on what to do next. How was it resolved -- or wasn't it?"),
    (STAGE_0_1, 3, False,
     "What have you been avoiding this week that you know you need to deal "
     "with?"),

    # --- Stage 1->10+ -- scaling. Zone: structural & delegation gaps. ---
    (STAGE_1_10, 0, True,
     "Now the part that matters most. In your own words, what is the single "
     "biggest problem in the company right now? Say it the way you'd say it to "
     "a co-founder, not the way you'd say it to a board."),
    (STAGE_1_10, 1, False,
     "What metric have you been quietly avoiding looking at this month?"),
    (STAGE_1_10, 2, False,
     "Where in the business does the same problem keep resurfacing, even after "
     "you thought you'd already fixed it?"),
    (STAGE_1_10, 3, False,
     "Tell me about the last time you made a call that a team lead should have "
     "made instead. Why did it land on you?"),
)

_STAGES = (STAGE_0, STAGE_0_1, STAGE_1_10)


def _selfcheck() -> None:
    """Fail loudly here rather than shipping a bank that strands a founder.

    Each invariant maps to something that actually breaks downstream: a stage
    with no symptom row means the report has nothing to quote, a duplicate
    arc_position makes the fixed order non-deterministic, and an unequal
    question count per stage means the progress bar reads differently
    depending on which stage the founder is in.
    """
    for stage in _STAGES:
        rows = [q for q in QUESTIONS if q[0] == stage]
        assert len(rows) == 4, f"{stage}: expected 4 questions, got {len(rows)}"

        symptoms = [q for q in rows if q[2]]
        assert len(symptoms) == 1, f"{stage}: expected exactly 1 symptom question"
        assert symptoms[0][1] == 0, f"{stage}: the symptom question must be arc 0"

        arcs = sorted(q[1] for q in rows)
        assert arcs == [0, 1, 2, 3], f"{stage}: arc positions must be 0-3, got {arcs}"

    unknown = {q[0] for q in QUESTIONS} - set(_STAGES)
    assert not unknown, f"unknown stage groups: {unknown}"


def main() -> int:
    _selfcheck()
    inserted = updated = 0

    with SessionLocal() as db:
        for stage_group, arc_position, is_symptom, question_text in QUESTIONS:
            existing = db.execute(
                select(CurrentProblemQuestions).where(
                    CurrentProblemQuestions.stage_group == stage_group,
                    CurrentProblemQuestions.arc_position == arc_position,
                )
            ).scalars().first()

            if existing is None:
                db.add(CurrentProblemQuestions(
                    stage_group=stage_group,
                    arc_position=arc_position,
                    question_text=question_text,
                    is_symptom=is_symptom,
                    is_active=True,
                ))
                inserted += 1
            else:
                changed = (
                    existing.question_text != question_text
                    or existing.is_symptom != is_symptom
                    or not existing.is_active
                )
                if changed:
                    existing.question_text = question_text
                    existing.is_symptom = is_symptom
                    existing.is_active = True
                    updated += 1

        db.commit()

    print(f"current_problem_questions: {inserted} inserted, {updated} updated, "
          f"{len(QUESTIONS)} total across {len(_STAGES)} stage groups.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
