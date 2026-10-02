"""What a founder's TEAM SIZE makes it possible for them to answer.

A FOURTH AXIS, alongside `stage_scope`, `context_scope` and `industry_scope`,
and separate from all three for the same kind of reason each of those is
separate from the others:

    stage     is this founder far enough along to have an answer?
    context   is this subject part of their situation at all?
    industry  was this question written for someone else's business?
    team      are there enough people here for the question to have a subject?

A founder at Growth who works alone is not too early for "Can your staff agree
a discount without asking you?", and the subject is not foreign to their
industry. There is simply nobody the question is about. The answer they give is
a blank or an apology, and the diagnosis scores it as a gap in Team &
Leadership -- so working alone reads as failing at leadership.

WHAT THIS READS. Two columns, and the axis cuts both ways.

`questions.min_team_size` (d4a1f8c62b73) is the smallest `founders.team_size`
band that can answer a question. NULL means anyone can, which is every question
outside Team & Leadership. See that migration for why the column is on
`questions` and not on `problems`.

`questions.max_team_size` (c92a41f7b508) is the largest band it still means
anything to, and exists because the defect above has a mirror image. "What
would you need to see before you felt safe paying someone a salary?" has a
subject for a founder working alone; put to one with twelve staff it describes a
decision they made years ago. Twenty rows carry it -- the first-hire bank -- and
NULL everywhere else, so this half of the axis narrows nobody else's diagnosis.

UNKNOWN TEAM SIZE ADMITS EVERYTHING. `founders.team_size` was not asked for
until 2026-09-28, so every founder who onboarded before then has NULL. Gating on
an unknown would silently shrink the diagnosis for all of them, and shrink it
worst in the pillar this module exists to protect. Absence of a fact is never
evidence for withholding -- the same reading `_in_scope` gives an unmapped
dimension and `_context_gated` gives an unrecorded problem code.

THE FLOOR IS SOMEBODY ELSE'S PROBLEM, ON PURPOSE. A founder working alone has
31 Team & Leadership questions at Growth and 15 at Validation, which clears
`MIN_ANSWERS_PER_PILLAR_SCORE`, so the pillar is scored rather than withheld.
Whether it SHOULD be scored is a separate question and not this module's to
answer: several of those 31 ask whether anyone reviews the founder's decisions
or shares the load, and a truthful "no" from someone working alone is a
description of being solo, not a failing. The evidence floor in
`business_health` is where that belongs.
"""

from __future__ import annotations

from typing import Any

from app.core.logger import logger

#: `founders.team_size`'s six coded values, smallest first. The order IS the
#: comparison: a founder may be asked a question whose `min_team_size` sits at
#: or below their own band. Mirrors TeamSize in app/schemas/founder.py and the
#: founders_team_size_check constraint; migration d4a1f8c62b73 pins the three
#: against each other in tests so they cannot drift.
TEAM_SIZE_ORDER: tuple[str, ...] = (
    "solo", "2_5", "6_10", "11_25", "26_plus",
)

_RANK: dict[str, int] = {band: i for i, band in enumerate(TEAM_SIZE_ORDER)}

#: The two bands d71a4e8c3f05 replaced with '26_plus', ranked alongside it.
#:
#: Nothing can newly write one -- `TeamSize` does not offer them and the
#: migration moved every row -- but the column's CHECK still accepts them so a
#: write from the old frontend mid-deploy does not fail. Ranking them here is
#: what makes that straggler harmless: without it, `team_size_of` would read
#: the value as unrecognised, return None, and gate nothing at all, so a
#: fifty-person company would be asked the solo questions alongside everything
#: else. Failing open is right for a value we never asked for; it is wrong for
#: one we did ask for and merely renamed.
_RANK.update({band: _RANK["26_plus"] for band in ("26_50", "50_plus")})


def team_size_of(founder: Any) -> str | None:
    """The founder's band, or None when it is unknown or not a band we know.

    An unrecognised value is treated as unknown rather than raising: the column
    has a CHECK, but a migration or a hand-edit could still put something else
    there, and a bad row must not be able to stop a diagnosis.
    """
    band = getattr(founder, "team_size", None)
    if not isinstance(band, str):
        return None
    band = band.strip()
    return band if band in _RANK else None


def _rank_or_none(value: Any) -> int | None:
    """`value`'s band rank, or None when it is absent or not a band we know.

    One reader for both bounds. An unreadable bound is indistinguishable from
    no bound on purpose: a CHECK guards both columns, but a migration or a
    hand-edit could still write something else, and a bad row must narrow
    nobody.
    """
    if not isinstance(value, str):
        return None
    return _RANK.get(value.strip())


def can_answer(
    min_team_size: Any, band: str | None, max_team_size: Any = None
) -> bool:
    """Whether a founder in `band` can be asked a question bounded by
    `min_team_size` below and `max_team_size` above.

    True whenever the founder's size is unknown, and true for each bound that
    is absent or unreadable -- the fail-open half of this module. A question
    with no bounds is for everyone, and a founder whose size we never asked for
    is not narrowed at all.

    `max_team_size` is keyword-safe to omit: callers written before
    c92a41f7b508 keep asking exactly what they asked before.
    """
    if band is None:
        return True
    here = _RANK[band]

    required = _rank_or_none(min_team_size)
    if required is not None and required > here:
        return False

    ceiling = _rank_or_none(max_team_size)
    if ceiling is not None and ceiling < here:
        return False

    return True


def gate(candidates: list, founder: Any) -> list:
    """Drop the questions this founder has nobody to answer about.

    Degrades exactly like `_context_gated` and `_industry_gated`, and for the
    same reason: three separate ways to end up not gating -- an unknown team
    size, a question with no requirement, or a gate that would empty the set --
    and every one of them admits the question rather than withholding it.

    Never returns empty when it was given a non-empty set. Ending a founder's
    diagnosis early over a data problem is worse than asking one question they
    cannot answer.
    """
    if not candidates:
        return candidates

    band = team_size_of(founder)
    if band is None:
        return candidates                 # never asked, or unreadable

    kept = [q for q in candidates
            if can_answer(getattr(q, "min_team_size", None), band,
                          getattr(q, "max_team_size", None))]

    if not kept:
        logger.warning(
            "Team-size gate matched no candidate question; leaving the set "
            "ungated rather than ending the diagnosis",
            extra={
                "stage": "team_scope",
                "team_size": band,
                "candidates": len(candidates),
            },
        )
        return candidates

    if len(kept) != len(candidates):
        logger.info(
            "diagnosis gated on team size",
            extra={
                "stage": "team_scope",
                "team_size": band,
                "withheld": len(candidates) - len(kept),
                "candidates": len(candidates),
            },
        )
    return kept


def is_written_for_band(question: Any) -> bool:
    """Whether this question was written for a founder of a PARTICULAR size,
    rather than admitted to everyone of that size and larger.

    Read by the diagnosis ranking, not by the gate. A question that only makes
    sense below some team size is as specific to the founder in front of it as
    one written for their industry, so it ranks alongside industry content
    instead of behind it -- the same judgement `engine._round_robin_key_for`
    already makes for a founder's own stage bank, on the axis this module owns.

    WHY `max_team_size` AND NOT `min_team_size`. Only one of the two records a
    decision about the individual question. 1,031 rows carry `min_team_size`
    because '2_5' is Team & Leadership's reviewed default for the whole pillar
    (d4a1f8c62b73), so the column being set says almost nothing about who the
    question was aimed at. `max_team_size` is claimed one question at a time by
    somebody who read it (c92a41f7b508) -- twenty rows today. Promote on the
    first and half the pillar outranks industry content; promote on the second
    and exactly the twenty questions somebody targeted are promoted.

    Reads defensively for the same reason the ranking terms around it do: a
    candidate that cannot say whether it has a bound does not have one.
    """
    return _rank_or_none(getattr(question, "max_team_size", None)) is not None


#: Team & Leadership. The one pillar whose subject can be absent entirely.
_TEAM_PILLAR_ID = 5


def score_is_withheld(pillar_id: Any, founder: Any) -> bool:
    """Whether this pillar must be reported as not assessed for this founder.

    True only for Team & Leadership, and only for a founder working alone.

    WHY A SCORE IS WORSE THAN NO SCORE HERE. The gate above gives a solo
    founder the Team & Leadership questions they can actually answer, and
    several of those are about not having anyone:

        Is there anyone who actually pressure-tests your decisions before you
        commit to them?
        During a hard stretch, is there anyone who actually carries some of the
        emotional weight with you?
        Does growth feel capped by how much one person -- you -- can personally
        carry?

    A founder working alone answers no, no and yes, truthfully, and the rubric
    scores all three as gaps. The pillar then lands in the bottom band and the
    report tells them their leadership is failing. It is not. They are solo,
    and the answers describe that rather than any shortcoming -- so the score
    measures their team size and presents it as a verdict on them.

    The answers are still worth collecting: they are real evidence of founder
    dependency, which is Pillar 1's `Founder Dependency / Bus Factor` and is
    scored there. What is withheld is the Team & Leadership BAND, not the
    information.

    This is the same judgement the ideation scope already makes by withholding
    the pillar outright -- you cannot grade how someone leads a team they do
    not have -- applied on the axis that actually decides it. And it uses the
    machinery that already exists for saying so: the same branch as the
    evidence floor, so `assessed_question_count` still carries the real number
    and a caller can tell "nobody to ask about" from "never asked".

    Fails open like everything else here: an unknown team size withholds
    nothing.
    """
    if pillar_id != _TEAM_PILLAR_ID:
        return False
    return team_size_of(founder) == "solo"
