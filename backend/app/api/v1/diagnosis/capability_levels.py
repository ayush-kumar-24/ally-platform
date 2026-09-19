"""The shared capability level scale, and the state that is NOT a level.

ONE SCALE FOR EVERY CAPABILITY. A per-capability rubric would make levels
incomparable, and the whole point of the taxonomy is that a target requirement
and a current observation can be compared. So the scale is universal and the
axis it measures is FOUNDER DEPENDENCE:

    0  ABSENT      the thing does not happen, or happens by accident
    1  PERSONAL    it works because the founder personally does it
    2  DOCUMENTED  it exists outside the founder's head
    3  OWNED       someone other than the founder owns and improves it

1 -> 2 -> 3 is the only progression that matters for a founder trying to scale,
and it is what lets this taxonomy say something the existing diagnosis cannot:
"you have a sales process" and "your sales process is you" are different answers
to the same question, and today they score the same.

UNASSESSED IS NOT A LEVEL, which is why it is a separate type rather than a
fifth enum member. A capability nobody has asked about has no level -- not 0.
Zero is a positive claim that the thing is absent; UNASSESSED is the absence of
a claim. Making it an enum member would let it be compared with `<` against a
requirement, and the first time someone wrote `observed < required` a founder
would be told they are missing a capability nobody ever asked them about. That
is the capability-level form of the rule Step 4 established for answers, where
UNKNOWN must never mean NO.

Nothing stores these yet. Step 8 introduces capability_evidence and Step 9 the
Gap Engine; this module exists now so both are built against one definition
rather than two that drift.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Final


class CapabilityLevel(IntEnum):
    """How independent of the founder a capability is. Ordered, comparable."""

    ABSENT = 0
    PERSONAL = 1
    DOCUMENTED = 2
    OWNED = 3

    @property
    def label(self) -> str:
        return {
            CapabilityLevel.ABSENT: "absent",
            CapabilityLevel.PERSONAL: "founder-dependent",
            CapabilityLevel.DOCUMENTED: "documented",
            CapabilityLevel.OWNED: "owned by someone else",
        }[self]

    @property
    def is_founder_dependent(self) -> bool:
        """True where the capability still runs through the founder personally."""
        return self <= CapabilityLevel.PERSONAL


#: The sentinel for "nobody has asked about this capability yet".
#:
#: Deliberately a string and NOT a member of CapabilityLevel: it must be
#: impossible to accidentally order it against a level. `UNASSESSED < 2` is a
#: TypeError, which is exactly the protection wanted -- a founder must never be
#: told a capability is missing on the strength of never having been asked.
UNASSESSED: Final[str] = "unassessed"


def is_assessed(observed: CapabilityLevel | str | None) -> bool:
    """Whether an observation carries a level at all.

    Every comparison against a requirement must pass through this first. There
    is deliberately no `level_or_default` helper: a default would be a number,
    and a number is a claim.
    """
    return isinstance(observed, CapabilityLevel)
