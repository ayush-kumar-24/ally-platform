"""Add the `monitor` routing state and its coverage threshold.

A healthy founder could not finish a diagnosis. Three of the five confidence
signals measure pathology -- category risk, confirmation of a detected cause,
and separation between competing causes -- so all three read 0 when nothing is
wrong. Only coverage (0.25) and consistency (0.20) can rise, capping a
perfectly healthy founder at 45 against a CONFIDENCE_GENERATE_REPORT_MIN of 80.
CONFIDENCE_HARD_RULES rule 4 then caps an unflagged session at 59, so `validate`
is unreachable as well.

The result: they answered every question in their budget and the session
completed carrying `continue` -- the state that means "keep asking" -- while the
reasoning pipeline wrote them a report anyway off the highest sub-threshold
category. NO_CATEGORY_ABOVE_THRESHOLD_ACTION already said not to force a
diagnosis in that situation. It never said when to stop asking.

`monitor` is that stopping point, and it is a success rather than a fallback:
enough was asked, and nothing crossed its risk threshold.

MONITOR_MIN_COVERAGE is deliberately high. Calling an all-clear is a stronger
claim than naming a problem -- a false all-clear sends a founder away reassured
and nothing later re-opens the question -- so it takes more evidence, not less.
Three quarters of the stage's own budget, which with the budgets seeded by
8f3a1c92d7b4 means 11 questions at Ideation (raised to 12 by
MIN_ANSWERS_BEFORE_COMPLETION) and 23 at Growth.

Revision ID: d5b81e37c9a2
Revises: 8f3a1c92d7b4
"""

from __future__ import annotations

from alembic import op

revision = "d5b81e37c9a2"
down_revision = "8f3a1c92d7b4"
branch_labels = None
depends_on = None

_CHECK = "sessions_routing_state_check"
_COLUMN = "routing_state"

_STATES_AFTER = ("continue", "validate", "generate_report", "distress_support", "monitor")
_STATES_BEFORE = ("continue", "validate", "generate_report", "distress_support")

_RULE_CODE = "MONITOR_MIN_COVERAGE"


def _states_check(states: tuple[str, ...]) -> str:
    values = ", ".join(f"'{s}'::character varying" for s in states)
    return f"({_COLUMN})::text = ANY ((ARRAY[{values}])::text[])"


def upgrade() -> None:
    op.execute(f"ALTER TABLE public.sessions DROP CONSTRAINT IF EXISTS {_CHECK}")
    op.create_check_constraint(_CHECK, "sessions", _states_check(_STATES_AFTER))

    # Repair the sequence BEFORE the insert below, or the insert fails.
    #
    # The INSERT omits rule_id and relies on the sequence, but scoring_rules was
    # seeded with explicit ids -- and an explicit id does not advance the
    # sequence. On a database seeded that way, nextval() returns an id that
    # already exists and the insert dies on the primary key. That is what failed
    # this migration on production RDS (verified via ECS Exec: the DB rolled
    # back cleanly to ba7ca1acfa53).
    #
    # Not reproducible everywhere, which is what makes it worth a comment rather
    # than a silent fix: on Supabase the same sequence reads last_value=45,
    # is_called=true against MAX(rule_id)=45, so nextval() returns 46 and the
    # insert succeeds. A migration that passes on one database and dies on the
    # other is exactly the shape this repair exists to remove.
    #
    # The third setval argument is `is_called`: true when rows exist, so the
    # next id is MAX+1; false on an empty table, so the next id is 1 rather than
    # 2. Idempotent -- running it again on a repaired sequence is a no-op.
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('public.scoring_rules', 'rule_id')::regclass,
            COALESCE(MAX(rule_id), 1),
            MAX(rule_id) IS NOT NULL
        )
        FROM public.scoring_rules
        """
    )

    # Externalised like every other threshold in this pipeline. The reading code
    # carries a 0.75 fallback so an unseeded database still routes correctly,
    # which is why this is an INSERT rather than a hard requirement.
    op.execute(
        f"""
        INSERT INTO public.scoring_rules
            (rule_code, rule_name, rule_value, rule_description, source_document,
             is_active)
        SELECT
            '{_RULE_CODE}',
            'Monitor Route - Minimum Coverage',
            0.7500,
            'Fraction of the founder stage question budget that must be answered, '
            'with no category at or above CAT_RISK_THRESHOLD, before the diagnosis '
            'may stop and route to monitor instead of continuing to ask. The other '
            'half of NO_CATEGORY_ABOVE_THRESHOLD_ACTION, which says not to force a '
            'diagnosis when nothing is flagged but does not say when to stop. Set '
            'high on purpose: an all-clear is a stronger claim than a diagnosis '
            'because nothing downstream re-opens it, so it requires more evidence, '
            'not less. Read together with CONFIDENCE_MIN_QUESTIONS_FLOOR, which '
            'still applies -- whichever is greater wins.',
            'Confidence Scoring Model',
            true
        WHERE NOT EXISTS (
            SELECT 1 FROM public.scoring_rules WHERE rule_code = '{_RULE_CODE}'
        )
        """
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM public.scoring_rules WHERE rule_code = '{_RULE_CODE}'")

    # Any session already parked on `monitor` would violate the narrower
    # constraint. They completed legitimately, so fold them into the state they
    # would have carried before this existed rather than deleting them.
    op.execute(
        f"UPDATE public.sessions SET {_COLUMN} = 'continue' "
        f"WHERE {_COLUMN} = 'monitor'"
    )
    op.execute(f"ALTER TABLE public.sessions DROP CONSTRAINT IF EXISTS {_CHECK}")
    op.create_check_constraint(_CHECK, "sessions", _states_check(_STATES_BEFORE))
