"""An unrecorded stage must not be read as "this founder has not started".

resolve_stage_groups deliberately FAILS OPEN for a founder whose stage is not
recorded: it returns every group, meaning "we don't actually know". Founder DNA
and Current Problem both need exactly ONE group (their question banks are
authored per group and queried with `stage_group == x`), and the resolver used
to collapse that list with `groups[0]`.

The list is built by iterating StageGroup, whose first member is STAGE_0. So
"we don't know" silently became "Ideation -- nothing built yet", for the whole
of BOTH phases. Observed live: a founder with a working MVP and three running
pilots was asked "what is the single biggest thing standing between you and
actually starting?" and "what would need to be true this week for you to
actually start?".

These pin two separate things: that a KNOWN stage is still passed straight
through, and that the unknown-stage default is a deliberate named constant
rather than an artifact of enum ordering.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.api.v1.founder_dna.engine import (
    UNKNOWN_STAGE_DEFAULT_GROUP,
    resolve_founder_dna_stage_group,
)
from app.models import StageGroup


def _founder(stage_order):
    """A founder whose stage has the given stage_order, or no stage at all."""
    stage = None if stage_order is None else SimpleNamespace(stage_order=stage_order)
    return SimpleNamespace(founder_id=1, stage=stage)


# --- a known stage is passed straight through -------------------------------

def test_ideation_still_resolves_to_stage_0():
    """The fix must not stop a genuine ideation founder getting Stage 0."""
    assert resolve_founder_dna_stage_group(_founder(1)) == StageGroup.STAGE_0.value


def test_validation_prototype_and_early_traction_resolve_to_stage_0_to_1():
    for stage_order in (2, 3, 4):
        assert (
            resolve_founder_dna_stage_group(_founder(stage_order))
            == StageGroup.STAGE_0_TO_1.value
        ), f"stage_order {stage_order}"


def test_growth_and_beyond_resolve_to_stage_1_to_10_plus():
    for stage_order in (5, 6, 7, 8):
        assert (
            resolve_founder_dna_stage_group(_founder(stage_order))
            == StageGroup.STAGE_1_TO_10_PLUS.value
        ), f"stage_order {stage_order}"


# --- an unknown stage ---------------------------------------------------------

def test_a_founder_with_no_stage_is_not_treated_as_pure_ideation():
    """THE REGRESSION. This is the founder who was asked what was stopping them
    from starting, while running three pilots on a shipped MVP."""
    assert resolve_founder_dna_stage_group(_founder(None)) != StageGroup.STAGE_0.value


def test_a_founder_with_no_stage_gets_the_documented_default():
    assert resolve_founder_dna_stage_group(_founder(None)) == UNKNOWN_STAGE_DEFAULT_GROUP


def test_a_stage_row_with_no_readable_order_is_also_unknown():
    """resolve_stage_groups treats a stage whose order cannot be read as the
    same "we don't know" case, so this side must agree."""
    stage = SimpleNamespace(stage_order=None)
    founder = SimpleNamespace(founder_id=1, stage=stage)
    assert resolve_founder_dna_stage_group(founder) == UNKNOWN_STAGE_DEFAULT_GROUP


def test_the_default_is_a_real_stage_group():
    """A typo here would query a bank that matches nothing and dead-end the
    phase for every unknown-stage founder."""
    assert UNKNOWN_STAGE_DEFAULT_GROUP in {group.value for group in StageGroup}


def test_the_default_is_the_deliberate_choice_not_the_first_enum_member():
    """The point of the fix. `groups[0]` returned whatever StageGroup declared
    first, which is STAGE_0 -- so the old default was an artifact of enum
    ordering, not a decision. Naming the choice means reordering that enum now
    fails this test instead of quietly changing what founders are asked."""
    assert UNKNOWN_STAGE_DEFAULT_GROUP == StageGroup.STAGE_0_TO_1.value
    # The trap that made the old code wrong, pinned so it stays visible.
    assert next(iter(StageGroup)).value == StageGroup.STAGE_0.value
