-- ============================================================================
-- SCHEMA FIX: answers.score_label must hold 'not_applicable'
-- ============================================================================
-- This is the one schema change in the current batch of fixes. It is the plain
-- SQL equivalent of Alembic revision d4a91c7e2b83, for teams that apply SQL to
-- RDS directly rather than running `alembic upgrade head`.
--
-- WHY
--   Migration c7d18a3f420b added 'not_applicable' to the answers_score_label
--   check constraint but left the column at varchar(10). 'not_applicable' is
--   fourteen characters, so every attempt to write the band failed with:
--
--       StringDataRightTruncation:
--       value too long for type character varying(10)
--
--   The fourth band has therefore been unwritable since the day it was added.
--   Any answer that genuinely does not apply to the founder's business was
--   either rejected outright or downgraded, and the pipeline raised
--   reasoning_error and completed the session with no report.
--
-- WHAT IT DOES
--   Widens answers.score_label from varchar(10) to varchar(20). No data is
--   changed, no rows are moved, no constraint is dropped: the existing
--   answers_score_label check already permits the four values and keeps doing
--   so. Widening a varchar in PostgreSQL 16 is a catalogue-only operation --
--   no table rewrite, no long ACCESS EXCLUSIVE hold, safe on a live table.
--
-- SAFE TO RE-RUN
--   Yes. The guard below skips the ALTER if the column is already wide enough.
-- ============================================================================

begin;

do $$
declare
    current_len integer;
begin
    select character_maximum_length
      into current_len
      from information_schema.columns
     where table_schema = current_schema()
       and table_name   = 'answers'
       and column_name  = 'score_label';

    if current_len is null then
        raise exception
            'answers.score_label not found in schema %. Run this against the '
            'Ally application schema.', current_schema();
    end if;

    if current_len >= 20 then
        raise notice
            'answers.score_label is already varchar(%) -- nothing to do.',
            current_len;
    else
        raise notice
            'Widening answers.score_label from varchar(%) to varchar(20).',
            current_len;
        alter table answers
            alter column score_label type varchar(20);
    end if;
end $$;

-- Self-check: prove the band is writable before committing. This inserts
-- nothing -- it casts the longest permitted value and confirms the column can
-- now hold it, so a silent no-op cannot pass for a successful run.
do $$
declare
    final_len integer;
begin
    select character_maximum_length
      into final_len
      from information_schema.columns
     where table_schema = current_schema()
       and table_name   = 'answers'
       and column_name  = 'score_label';

    if final_len < length('not_applicable') then
        raise exception
            'answers.score_label is varchar(%) -- still too narrow for '
            '''not_applicable'' (% chars). Rolling back.',
            final_len, length('not_applicable');
    end if;

    raise notice
        'OK: answers.score_label is varchar(%); ''not_applicable'' (% chars) fits.',
        final_len, length('not_applicable');
end $$;

commit;
