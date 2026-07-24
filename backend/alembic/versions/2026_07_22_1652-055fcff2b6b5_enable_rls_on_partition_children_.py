"""enable RLS on partition children + alembic_version; auto-RLS future partitions

Revision ID: 055fcff2b6b5
Revises: b960b83ab79e
Create Date: 2026-07-22 16:52:47.317061

Closes the Supabase "table publicly accessible" / "sensitive data exposed"
alerts. Row-Level Security is not inherited by partitions, so the 36 monthly
child partitions of messages / analytics_events / audit_logs were readable
through the public API even though their parents are protected. `alembic_version`
was also flagged.

Two parts:
  1. Enable RLS on every existing partition child + alembic_version. With no
     policy this is deny-all to the anon/authenticated API roles; the backend
     connects as the table owner, which bypasses RLS, and real user access still
     flows through the parent tables (which keep their policies). So nothing the
     app does breaks -- only the direct-to-child API hole closes.
  2. Patch create_next_month_partitions() to enable RLS on each partition it
     creates, so future months are protected automatically and this never has to
     be redone.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "055fcff2b6b5"
down_revision: Union[str, Sequence[str], None] = "b960b83ab79e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- 1. Backfill: enable RLS on all existing partition children.
DO $$
DECLARE r record;
BEGIN
    FOR r IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relispartition = true
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.relname);
    END LOOP;
END $$;

ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY;

-- 2. Future partitions: enable RLS as part of creating them.
CREATE OR REPLACE FUNCTION public.create_next_month_partitions()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    v_next_month  DATE := DATE_TRUNC('month', NOW()) + INTERVAL '1 month';
    v_month_after DATE := v_next_month + INTERVAL '1 month';
    v_suffix      TEXT := TO_CHAR(v_next_month, 'YYYY_MM');
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS messages_%s PARTITION OF messages FOR VALUES FROM (%L) TO (%L)',
        v_suffix, v_next_month, v_month_after
    );
    EXECUTE format('ALTER TABLE messages_%s ENABLE ROW LEVEL SECURITY', v_suffix);

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS analytics_events_%s PARTITION OF analytics_events FOR VALUES FROM (%L) TO (%L)',
        v_suffix, v_next_month, v_month_after
    );
    EXECUTE format('ALTER TABLE analytics_events_%s ENABLE ROW LEVEL SECURITY', v_suffix);

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS audit_logs_%s PARTITION OF audit_logs FOR VALUES FROM (%L) TO (%L)',
        v_suffix, v_next_month, v_month_after
    );
    EXECUTE format('ALTER TABLE audit_logs_%s ENABLE ROW LEVEL SECURITY', v_suffix);

    RAISE NOTICE 'Partitions created for %', v_suffix;
END;
$function$;
"""

# Reverses part 1 (disable RLS on the partition children + alembic_version).
# The create_next_month_partitions() change is intentionally left in place --
# there is no reason to reintroduce the exposure on downgrade.
DOWNGRADE_SQL = r"""
DO $$
DECLARE r record;
BEGIN
    FOR r IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relispartition = true
    LOOP
        EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', r.relname);
    END LOOP;
END $$;

ALTER TABLE public.alembic_version DISABLE ROW LEVEL SECURITY;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
