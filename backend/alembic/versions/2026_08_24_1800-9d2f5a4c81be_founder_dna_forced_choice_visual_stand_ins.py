"""render the doc's remaining visual concepts as text forced choices

Revision ID: 9d2f5a4c81be
Revises: 3c7e91b40d52

`GoXL_Founder_DNA_Decoding_Journey.docx` s4 defines six two-image forced
choices and s5 places four of them in the stage journeys. c7e4b2a91f58 deferred
all six ("text-only was a deliberate v1 scope decision") and the seed script
put a situational text question in each slot instead.

Two of the four came through as text forced CHOICES and read exactly as the doc
intends -- Blueprint or Canvas is "are you working to a plan you set in advance,
or figuring it out as you go", and The Storm is "steering alone, or bracing with
the team". The other two became open scenarios, which loses the thing the doc
says these are for: s4 states the visual pairs "resolve ambiguity faster and
more honestly than another paragraph prompt", and a paragraph prompt is what
they became. The fourth, The Cliff Edge, has no question at all.

This closes those three, still without images -- both options are described in
words and the CHOICE is what carries.

Nothing is deleted, and no answered question's text is rewritten. The existing
scenarios are DEMOTED to follow-ups (arc 90+) rather than replaced: a founder
who already answered one keeps an answer whose question still reads the way it
did when they answered it, and the richer prompt becomes the clarifying
follow-up the doc's s3 describes -- asked when the binary left the dimension
unresolved. Each stage still has exactly 14 base questions, one per dimension.

The Cliff Edge is labelled "Risk Posture" in the doc's journey table, which is
not one of the fourteen dimensions -- the doc's own s2 dimension table has no
such entry. It sits under decision_style, where behaviour under uncertainty is
read, and as a follow-up rather than a base question because that stage's
decision_style base slot already carries the doc's own Blueprint-or-Canvas.

scripts/seed_founder_dna_questions.py carries the same change, so a fresh seed
and an existing database converge; without that, the next --replace run would
silently undo this.
"""

from alembic import op
from sqlalchemy import text


revision = "9d2f5a4c81be"
down_revision = "3c7e91b40d52"
branch_labels = None
depends_on = None


_TABLE = "founder_dna_questions"

#: (stage_group, dimension_code, old_arc, new_arc) -- the scenarios that step
#: aside for a forced choice. Matched on arc position rather than text so the
#: statement stays readable; the dimension pins it to one row either way.
_DEMOTIONS = (
    ("Stage 0", "core_motivation", 4, 94),
    ("Stage 0", "energy_patterns", 9, 95),
    ("Stage 1→10+", "core_motivation", 4, 94),
)

_TROPHY_OR_BRIDGE_S0 = (
    "Two futures, and without overthinking it -- which one pulls you more "
    "right now? One: a single trophy on a pedestal, the thing you made, "
    "recognised. Two: an unfinished bridge between two cliffs, people you "
    "will never meet crossing it."
)

_TROPHY_OR_BRIDGE_S2 = (
    "Two futures, and without overthinking it -- which one pulls you more "
    "now? One: a single trophy on a pedestal, what you built, recognised. "
    "Two: an unfinished bridge between two cliffs, people you will never "
    "meet crossing it."
)

_QUIET_OR_PACKED = (
    "Which one actually recharges you -- working alone at a desk lamp in a "
    "silent room, or a loud room full of people and energy?"
)

_CLIFF_EDGE = (
    "Your last big call under real uncertainty -- were you the person "
    "standing at the cliff edge looking out and weighing it, or the one "
    "already mid-air, having jumped?"
)

#: (stage_group, dimension_code, arc, question_text, options_json, is_closing)
_ADDITIONS = (
    ("Stage 0", "core_motivation", 4, _TROPHY_OR_BRIDGE_S0,
     '["The trophy", "The bridge"]'),
    ("Stage 0", "energy_patterns", 9, _QUIET_OR_PACKED,
     '["The quiet room", "The packed room"]'),
    ("Stage 1→10+", "core_motivation", 4, _TROPHY_OR_BRIDGE_S2,
     '["The trophy", "The bridge"]'),
    ("Stage 0→1", "decision_style", 94, _CLIFF_EDGE,
     '["Standing at the edge, weighing it", "Already mid-air"]'),
)


def upgrade() -> None:
    bind = op.get_bind()

    # Demote first: the new rows take the arc positions these vacate, and
    # leaving both at the same position would put two base questions on one
    # dimension and break the 14-base-per-stage shape the seed script asserts.
    for stage, dimension, old_arc, new_arc in _DEMOTIONS:
        bind.execute(
            text(
                f"UPDATE {_TABLE} SET arc_position = :new "
                "WHERE stage_group = :stage AND dimension_code = :dim "
                "AND arc_position = :old"
            ),
            {"new": new_arc, "stage": stage, "dim": dimension, "old": old_arc},
        )

    # Idempotent on question_text: re-running must not add a second copy.
    for stage, dimension, arc, question, options in _ADDITIONS:
        bind.execute(
            text(
                f"INSERT INTO {_TABLE} "
                "(dimension_code, stage_group, arc_position, format, "
                " question_text, options, is_closing, is_active) "
                "SELECT :dim, :stage, :arc, 'forced_choice', :q, "
                "       CAST(:opts AS jsonb), false, true "
                f"WHERE NOT EXISTS (SELECT 1 FROM {_TABLE} "
                "  WHERE stage_group = :stage AND question_text = :q)"
            ),
            {"dim": dimension, "stage": stage, "arc": arc,
             "q": question, "opts": options},
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Remove the added choices first, so the demoted scenarios can move back
    # into arc positions nothing else occupies.
    #
    # Answers are deleted alongside, which is destructive by nature: these are
    # questions this migration introduced, so an answer to one cannot survive
    # its question going away, and the FK would refuse the delete otherwise.
    # Same rule d8b3f6c204ae applies to a question-bank downgrade -- the bank is
    # content, not founder-authored data.
    for stage, _dimension, _arc, question, _options in _ADDITIONS:
        bind.execute(
            text(
                "DELETE FROM founder_dna_answers WHERE founder_dna_question_id IN "
                f"(SELECT founder_dna_question_id FROM {_TABLE} "
                " WHERE stage_group = :stage AND question_text = :q)"
            ),
            {"stage": stage, "q": question},
        )
        bind.execute(
            text(f"DELETE FROM {_TABLE} "
                 "WHERE stage_group = :stage AND question_text = :q"),
            {"stage": stage, "q": question},
        )

    for stage, dimension, old_arc, new_arc in _DEMOTIONS:
        bind.execute(
            text(
                f"UPDATE {_TABLE} SET arc_position = :old "
                "WHERE stage_group = :stage AND dimension_code = :dim "
                "AND arc_position = :new"
            ),
            {"old": old_arc, "stage": stage, "dim": dimension, "new": new_arc},
        )
