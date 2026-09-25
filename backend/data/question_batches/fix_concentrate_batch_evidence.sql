-- =====================================================================
-- THIS FILE IS NO LONGER NEEDED. DO NOT RUN IT ON A FRESH DATABASE.
--
-- batch1_industries_1to5.sql and batch2_industries_6to10.sql were re-emitted
-- with evidence concentration built into the content itself. Measured on a
-- database that had ONLY batch 1 loaded, before this file was run at all:
--
--     questions per (root cause, stage):  2.00   min 2   max 2
--
-- and the same for batch 2. So there is nothing here left to fix. Running it
-- anyway is harmless -- verified, the question-to-cause links hash identically
-- before and after -- but it is a step with no purpose.
--
-- It is kept only for a database that loaded an OLDER copy of batch 1 or 2,
-- where the questions did scatter one per cause.
--
-- HOW TO TELL WHICH YOU HAVE. After loading batch 1, run:
--
--   select round(avg(n),2) from (
--     select root_cause_id, primary_stage_group, count(*) n from questions
--      where question_code ~ '^S(0|01|10)-(AGR|AUT|BFS|BPC|PRP)-[23][0-9][0-9]-[0-9]$'
--      group by 1,2) t;
--
--   2.00  -> concentrated already. Skip this file.
--   1.00  -> scattered. Run this file.
-- =====================================================================
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
declare per_cause numeric; per_problem numeric; rows_matched int;
begin
  -- FIRST: refuse if the prerequisite content is not loaded.
  --
  -- The checks below use avg(), and avg() over an EMPTY set returns NULL.
  -- `NULL < 2` evaluates to NULL, not true, so the guard below did not fire
  -- and this file reported success against a database with no batch questions
  -- at all. Caught by the AWS team during review, not by me. Counting rows
  -- first makes the empty case an explicit failure instead of a silent pass.
  select count(*) into rows_matched from questions
   where question_code ~ '^S(0|01|10)-(AGR|AUT|BFS|BPC|PRP|CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$';
  if rows_matched = 0 then
    raise exception 'no batch 1 or batch 2 questions found -- load batch1_industries_1to5.sql and batch2_industries_6to10.sql first. Nothing was changed.';
  end if;
  if rows_matched <> 540 then
    raise exception 'expected 540 batch 1+2 questions, found % -- load BOTH batch1_industries_1to5.sql and batch2_industries_6to10.sql before running this. Nothing was changed.', rows_matched;
  end if;

  select avg(n) into per_cause from (
    select root_cause_id, primary_stage_group, count(*) n from questions
     where question_code ~ '^S(0|01|10)-(AGR|AUT|BFS|BPC|PRP|CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     group by 1,2) a;
  select avg(c) into per_problem from (
    select problem_id, primary_stage_group, count(distinct root_cause_id) c from questions
     where question_code ~ '^S(0|01|10)-(AGR|AUT|BFS|BPC|PRP|CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     group by 1,2) b;
  if per_cause < 2 or per_problem > 1 then
    raise exception 'remap did not take: % questions per (cause,stage), % causes per (problem,stage) -- wanted 2 and 1. Rolled back, nothing changed.',
      per_cause, per_problem;
  end if;
  raise notice 'evidence concentrated: % questions per (cause,stage), % cause per (problem,stage)', per_cause, per_problem;
end $$;

COMMIT;
