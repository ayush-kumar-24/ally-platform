-- ============================================================
-- ALLY MIGRATION STATUS  --  READ ONLY, SAFE TO RUN ANY TIME
-- Changes nothing. Run it mid-migration if you like.
--   psql "$DATABASE_URL" -f check_migration_status.sql
-- ============================================================
\pset border 2

select 'alembic version' as item,
       coalesce((select version_num from alembic_version limit 1),'(none)') as value,
       case when (select version_num from alembic_version limit 1) = 'd4a91c7e2b83'
            then 'OK - schema fix applied' else 'check with dev' end as status
union all
select 'answers.score_label width',
       coalesce((select character_maximum_length::text from information_schema.columns
                  where table_name='answers' and column_name='score_label'),'?'),
       case when (select character_maximum_length from information_schema.columns
                   where table_name='answers' and column_name='score_label') >= 20
            then 'OK' else 'TOO NARROW - file 1 not applied' end
union all
select 'catalogue interventions (problems 1-275)',
       (select count(*)::text from interventions i join problems p using (problem_id)
         where p.problem_id between 1 and 275),
       case when (select count(*) from interventions i join problems p using (problem_id)
                   where p.problem_id between 1 and 275) >= 400
            then 'OK - loaded' else 'NOT LOADED' end;

\echo ''
\echo '--- PER BATCH ---'

with b(n, pfx, content_file) as (values
  (1,'AGR|AUT|BFS|BPC|PRP','batch1_industries_1to5.sql'),
  (2,'CEL|ECM|EDU|ENR|MED','batch2_industries_6to10.sql'),
  (3,'FSH|FNB|GAM|HLT|TRV','batch3_industries_11to15.sql'),
  (4,'HRT|TRD|MFG|SAS|LGL','batch4_industries_16to20.sql'),
  (5,'LOG|MKT|NGO|PHM|SVC','batch5_industries_21to25.sql'),
  (6,'RTL|SPF|TEL|TXT|DLV','batch6_industries_26to30.sql'))
select b.n as batch,
       (select count(*) from problems p   where p.problem_code    ~ ('^('||b.pfx||')-[23][0-9][0-9]$'))            as problems,
       (select count(*) from root_causes r where r.root_cause_code ~ ('^RC-('||b.pfx||')-[23][0-9][0-9]-[0-9]$'))  as causes,
       (select count(*) from questions q   where q.question_code   ~ ('^S(0|01|10)-('||b.pfx||')-[23][0-9][0-9]-[0-9]$')) as questions,
       (select count(*) from root_cause_weights w join root_causes r on r.root_cause_id=w.root_cause_id
         where r.root_cause_code ~ ('^RC-('||b.pfx||')-[23][0-9][0-9]-[0-9]$'))                                    as weights,
       (select round(avg(w.stage_weight),3) from root_cause_weights w join root_causes r on r.root_cause_id=w.root_cause_id
         where r.root_cause_code ~ ('^RC-('||b.pfx||')-[23][0-9][0-9]-[0-9]$') and w.stage_id=4)                    as weight_check,
       case
         when (select count(*) from problems p where p.problem_code ~ ('^('||b.pfx||')-[23][0-9][0-9]$')) = 0
              then 'not started'
         when (select count(*) from problems p where p.problem_code ~ ('^('||b.pfx||')-[23][0-9][0-9]$')) <> 45
              then 'CONTENT INCOMPLETE - reload ' || b.content_file
         when (select count(*) from root_cause_weights w join root_causes r on r.root_cause_id=w.root_cause_id
                where r.root_cause_code ~ ('^RC-('||b.pfx||')-[23][0-9][0-9]-[0-9]$')) = 0
              then 'content OK - WEIGHTS MISSING'
         when (select count(*) from root_cause_weights w join root_causes r on r.root_cause_id=w.root_cause_id
                where r.root_cause_code ~ ('^RC-('||b.pfx||')-[23][0-9][0-9]-[0-9]$')) <> 1080
              then 'WEIGHTS INCOMPLETE'
         when (select round(avg(w.stage_weight),3) from root_cause_weights w join root_causes r on r.root_cause_id=w.root_cause_id
                where r.root_cause_code ~ ('^RC-('||b.pfx||')-[23][0-9][0-9]-[0-9]$') and w.stage_id=4) > 1.7
              then 'DONE but OLD weight file used'
         else 'DONE' end as status
from b order by b.n;

\echo ''
\echo '--- EXPECTED per batch: problems 45 | causes 135 | questions 270 | weights 1080 | weight_check 1.556 ---'
