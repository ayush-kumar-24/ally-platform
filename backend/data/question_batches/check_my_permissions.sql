-- ============================================================
-- STEP 0 -- PERMISSION CHECK.  READ ONLY. CHANGES NOTHING.
--
-- Run this FIRST, before any data file. It tells us in one go
-- whether your database role can do what the load needs.
--   psql "$DATABASE_URL" -f check_my_permissions.sql
-- ============================================================
\pset border 2

select current_user as role, current_database() as db;

select 'INSERT on problems'                  as needs,
       has_table_privilege('problems','INSERT')::text        as you_have,
       case when has_table_privilege('problems','INSERT') then 'OK' else 'MISSING - blocks everything' end as verdict
union all
select 'INSERT on root_causes',   has_table_privilege('root_causes','INSERT')::text,
       case when has_table_privilege('root_causes','INSERT') then 'OK' else 'MISSING - blocks everything' end
union all
select 'INSERT on questions',     has_table_privilege('questions','INSERT')::text,
       case when has_table_privilege('questions','INSERT') then 'OK' else 'MISSING - blocks everything' end
union all
select 'INSERT on interventions', has_table_privilege('interventions','INSERT')::text,
       case when has_table_privilege('interventions','INSERT') then 'OK' else 'MISSING - blocks everything' end
union all
select 'INSERT on root_cause_weights', has_table_privilege('root_cause_weights','INSERT')::text,
       case when has_table_privilege('root_cause_weights','INSERT') then 'OK' else 'MISSING - blocks everything' end
union all
select 'INSERT on question_industry_mapping', has_table_privilege('question_industry_mapping','INSERT')::text,
       case when has_table_privilege('question_industry_mapping','INSERT') then 'OK' else 'MISSING - blocks everything' end
union all
select 'UPDATE on questions (needed by one file only)', has_table_privilege('questions','UPDATE')::text,
       case when has_table_privilege('questions','UPDATE') then 'OK' else 'missing - only affects the optional file' end;

\echo ''
\echo '--- SEQUENCES: nextval needs USAGE. setval needs UPDATE. ---'
\echo '--- USAGE = enough. UPDATE = nice to have, not required. ---'

select s.sequencename as sequence,
       has_sequence_privilege(s.schemaname||'.'||s.sequencename,'USAGE')::text  as usage_ok,
       has_sequence_privilege(s.schemaname||'.'||s.sequencename,'UPDATE')::text as update_ok,
       case when has_sequence_privilege(s.schemaname||'.'||s.sequencename,'USAGE')
            then 'OK to load' else 'MISSING USAGE - blocks inserts' end as verdict
  from pg_sequences s
 where s.sequencename in ('problems_problem_id_seq','root_causes_root_cause_id_seq',
                          'questions_question_id_seq','interventions_intervention_id_seq',
                          'root_cause_weights_weight_id_seq','question_industry_mapping_id_seq')
 order by 1;

\echo ''
\echo 'WHAT TO DO WITH THIS:'
\echo '  any INSERT says MISSING      -> your role cannot load data at all. Ask for write access.'
\echo '  any sequence USAGE says MISSING -> inserts will fail. Ask for: GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO <role>;'
\echo '  all USAGE ok, UPDATE false   -> FINE. The current files handle that. You are good to go.'
