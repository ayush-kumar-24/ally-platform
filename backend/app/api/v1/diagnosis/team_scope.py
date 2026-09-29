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

WHAT THIS READS. `questions.min_team_size`, the smallest `founders.team_size`
band that can answer a question, added by migration d4a1f8c62b73. NULL means
anyone can, which is every question outside Team & Leadership. See that
migration for why the column is on `questions` and not on `problems`.

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


def can_answer(min_team_size: Any, band: str | None) -> bool:
    """Whether a founder in `band` can be asked a question needing
    `min_team_size`.

    True whenever either side is unknown, which is the fail-open half of this
    module: a question with no requirement is for everyone, and a founder whose
    size we never asked for is not narrowed at all.
    """
    if min_team_size is None or band is None:
        return True
    required = _RANK.get(min_team_size if isinstance(min_team_size, str) else "")
    if required is None:
        return True                       # unknown requirement, admit
    return required <= _RANK[band]


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
            if can_answer(getattr(q, "min_team_size", None), band)]

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
