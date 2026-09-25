-- =====================================================================
-- FIX: point both questions in a stage at the SAME root cause.
--
-- WHY. detection_score is the mean severity of a root cause's negative
-- evidence, and ROOT_CAUSE_MAX_CANDIDATES is 8. The batch questions rotated
-- root cause per question, so each cause collected ONE question per stage.
-- Measured on an E-Commerce founder: ten batch questions were asked, they
-- mapped to TEN DISTINCT root causes with one piece of evidence each, and not
-- one reached the candidate set -- the original catalogue's causes carry
-- several questions apiece and filled all 8 slots.
--
-- This is an UPDATE rather than a reload because `answers` has a foreign key
-- to `questions`, so test sessions pin the rows.
--
-- Which cause a stage points at: S0 -> -1, S01 -> -2, S10 -> -3.
-- Idempotent; re-running sets the same values.
-- =====================================================================
BEGIN;

update questions q
   set root_cause_id = rc.root_cause_id
  from root_causes rc
 where q.question_code ~ '^S(0|01|10)-(AGR|AUT|BFS|BPC|PRP|CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
   and rc.root_cause_code =
       'RC-' || split_part(q.question_code, '-', 2)
            || '-' || split_part(q.question_code, '-', 3)
            || '-' || case split_part(q.question_code, '-', 1)
                        when 'S0'  then '1'
                        when 'S01' then '2'
                        when 'S10' then '3'
                      end;

do $$
declare per_cause numeric; per_problem numeric;
begin
  select avg(n) into per_cause from (
    select root_cause_id, primary_stage_group, count(*) n from questions
     where question_code ~ '^S(0|01|10)-(AGR|AUT|BFS|BPC|PRP|CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     group by 1,2) a;
  select avg(c) into per_problem from (
    select problem_id, primary_stage_group, count(distinct root_cause_id) c from questions
     where question_code ~ '^S(0|01|10)-(AGR|AUT|BFS|BPC|PRP|CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     group by 1,2) b;
  if per_cause < 2 or per_problem > 1 then
    raise exception 'remap did not take: % questions per (cause,stage), % causes per (problem,stage) -- wanted 2 and 1',
      per_cause, per_problem;
  end if;
  raise notice 'evidence concentrated: % questions per (cause,stage), % cause per (problem,stage)', per_cause, per_problem;
end $$;

COMMIT;
