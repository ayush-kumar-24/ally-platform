-- =====================================================================
-- Stage weights for the BATCH 2 root causes.
--   consumer_electronics, ecommerce_d2c, edtech, cleantech_energy, media_entertainment
--
-- 135 root causes x 8 founder stages = 1,080 rows.
--
-- WHY THIS FILE EXISTS SEPARATELY. Batches 1 and 2 originally shared one
-- file (fix_batch_stage_weights.sql, 2,160 statements across ten industry
-- prefixes). That is correct SQL but it cannot be deployed one batch at a
-- time, and a staged rollout needs to verify batch 1 before batch 2 goes
-- in. The unnumbered filename also read like a stray duplicate next to
-- fix_batch3_stage_weights.sql. One file per batch, numbered, from here on.
--
-- WHAT stage_weight IS. confidence.py reads it as a four-level relevance
-- scale (0.50 / 1.00 / 1.50 / 2.00) and normalises it onto 0..1.
-- stage_probability carries 20% of root-cause ranking
-- (WEIGHT_STAGE_PROBABILITY = 0.20), so a cause with no row for the
-- founder's stage has that factor recorded UNAVAILABLE and ranks on the
-- remaining 80%. New content with no rows competes at a standing
-- disadvantage against the original catalogue.
--
-- THE CURVE IS PER DIMENSION, NOT PER BATCH. An earlier version of these
-- files wrote the same eight values for every cause, which put all of them
-- at the maximum 2.00 at Early Traction while the original catalogue
-- averages 1.557 there with only 20% of causes at the top value. That
-- removed a handicap and handed the new content an advantage instead.
-- stage_weight answers "how relevant is this cause at this stage", which is
-- a property of the DIMENSION:
--
--   skill_stage_fit              1.5  2.0  2.0  1.5  1.5  1.0  0.5  0.5
--   time_allocation_reality      1.0  1.5  1.5  2.0  2.0  1.5  0.5  0.5
--   founder_dependency           0.5  1.0  1.5  2.0  2.0  2.0  1.0  0.5
--   team_structure_role_clarity  0.5  0.5  1.0  1.5  2.0  2.0  1.5  0.5
--   decision_rights              0.5  0.5  1.0  1.5  2.0  2.0  1.5  1.0
--   hiring_repeatability         0.5  0.5  1.0  1.5  2.0  2.0  1.0  0.5
--   plan_to_vision_alignment     1.5  1.5  1.5  1.5  2.0  1.5  1.0  1.0
--   prioritization_discipline    1.0  1.5  2.0  1.5  2.0  1.5  1.0  0.5
--   institutional_memory         0.5  0.5  1.0  1.0  1.5  2.0  2.0  1.5
--
-- At Early Traction these average 1.556 against the catalogue's 1.557.
-- Because the curve is already correct here, fix_stage_weight_curves.sql
-- has nothing in this batch to correct and is NOT needed after this file.
--
-- HOW IT IS WRITTEN. Set-based: one INSERT per (dimension, stage), joining
-- root_causes -> problems to read dimension_code. 72 statements instead of
-- 1,080 hardcoded root-cause codes -- same rows, reviewable by eye, and it
-- cannot go wrong through a mistyped code.
--
-- NO HARDCODED IDS. Every id comes from the sequence or from a join.
-- SAFE TO RUN TWICE. ON CONFLICT (root_cause_id, stage_id) DO NOTHING.
-- ONE TRANSACTION with a self-check: you get all 1,080 rows or none.
--
-- RUN batch2_industries_6to10.sql FIRST. This file checks for all 135 causes and
-- refuses to run otherwise, naming the file to load.
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f <this file>
-- =====================================================================

BEGIN;

-- Repair the sequence first, in case an earlier explicit-id load left it
-- behind its own table. Harmless if already ahead.
select setval(pg_get_serial_sequence('root_cause_weights','weight_id'), greatest((select coalesce(max(weight_id),0) from root_cause_weights), 1));

-- Refuse to run against a database that has not had the content loaded.
do $$
declare found int;
begin
  select count(*) into found from root_causes
   where root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$';
  if found <> 135 then
    raise exception 'expected 135 batch 2 root causes, found % -- load batch2_industries_6to10.sql first', found;
  end if;
end $$;

-- skill_stage_fit
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 1, 1.5, 'batch 2 content: stage relevance curve for dimension skill_stage_fit'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'skill_stage_fit'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 2, 2.0, 'batch 2 content: stage relevance curve for dimension skill_stage_fit'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'skill_stage_fit'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 3, 2.0, 'batch 2 content: stage relevance curve for dimension skill_stage_fit'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'skill_stage_fit'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 4, 1.5, 'batch 2 content: stage relevance curve for dimension skill_stage_fit'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'skill_stage_fit'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 5, 1.5, 'batch 2 content: stage relevance curve for dimension skill_stage_fit'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'skill_stage_fit'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 6, 1.0, 'batch 2 content: stage relevance curve for dimension skill_stage_fit'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'skill_stage_fit'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 7, 0.5, 'batch 2 content: stage relevance curve for dimension skill_stage_fit'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'skill_stage_fit'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 8, 0.5, 'batch 2 content: stage relevance curve for dimension skill_stage_fit'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'skill_stage_fit'
  on conflict (root_cause_id, stage_id) do nothing;

-- time_allocation_reality
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 1, 1.0, 'batch 2 content: stage relevance curve for dimension time_allocation_reality'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'time_allocation_reality'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 2, 1.5, 'batch 2 content: stage relevance curve for dimension time_allocation_reality'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'time_allocation_reality'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 3, 1.5, 'batch 2 content: stage relevance curve for dimension time_allocation_reality'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'time_allocation_reality'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 4, 2.0, 'batch 2 content: stage relevance curve for dimension time_allocation_reality'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'time_allocation_reality'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 5, 2.0, 'batch 2 content: stage relevance curve for dimension time_allocation_reality'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'time_allocation_reality'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 6, 1.5, 'batch 2 content: stage relevance curve for dimension time_allocation_reality'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'time_allocation_reality'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 7, 0.5, 'batch 2 content: stage relevance curve for dimension time_allocation_reality'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'time_allocation_reality'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 8, 0.5, 'batch 2 content: stage relevance curve for dimension time_allocation_reality'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'time_allocation_reality'
  on conflict (root_cause_id, stage_id) do nothing;

-- founder_dependency
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 1, 0.5, 'batch 2 content: stage relevance curve for dimension founder_dependency'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'founder_dependency'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 2, 1.0, 'batch 2 content: stage relevance curve for dimension founder_dependency'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'founder_dependency'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 3, 1.5, 'batch 2 content: stage relevance curve for dimension founder_dependency'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'founder_dependency'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 4, 2.0, 'batch 2 content: stage relevance curve for dimension founder_dependency'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'founder_dependency'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 5, 2.0, 'batch 2 content: stage relevance curve for dimension founder_dependency'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'founder_dependency'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 6, 2.0, 'batch 2 content: stage relevance curve for dimension founder_dependency'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'founder_dependency'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 7, 1.0, 'batch 2 content: stage relevance curve for dimension founder_dependency'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'founder_dependency'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 8, 0.5, 'batch 2 content: stage relevance curve for dimension founder_dependency'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'founder_dependency'
  on conflict (root_cause_id, stage_id) do nothing;

-- team_structure_role_clarity
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 1, 0.5, 'batch 2 content: stage relevance curve for dimension team_structure_role_clarity'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'team_structure_role_clarity'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 2, 0.5, 'batch 2 content: stage relevance curve for dimension team_structure_role_clarity'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'team_structure_role_clarity'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 3, 1.0, 'batch 2 content: stage relevance curve for dimension team_structure_role_clarity'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'team_structure_role_clarity'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 4, 1.5, 'batch 2 content: stage relevance curve for dimension team_structure_role_clarity'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'team_structure_role_clarity'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 5, 2.0, 'batch 2 content: stage relevance curve for dimension team_structure_role_clarity'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'team_structure_role_clarity'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 6, 2.0, 'batch 2 content: stage relevance curve for dimension team_structure_role_clarity'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'team_structure_role_clarity'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 7, 1.5, 'batch 2 content: stage relevance curve for dimension team_structure_role_clarity'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'team_structure_role_clarity'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 8, 0.5, 'batch 2 content: stage relevance curve for dimension team_structure_role_clarity'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'team_structure_role_clarity'
  on conflict (root_cause_id, stage_id) do nothing;

-- decision_rights
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 1, 0.5, 'batch 2 content: stage relevance curve for dimension decision_rights'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'decision_rights'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 2, 0.5, 'batch 2 content: stage relevance curve for dimension decision_rights'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'decision_rights'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 3, 1.0, 'batch 2 content: stage relevance curve for dimension decision_rights'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'decision_rights'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 4, 1.5, 'batch 2 content: stage relevance curve for dimension decision_rights'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'decision_rights'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 5, 2.0, 'batch 2 content: stage relevance curve for dimension decision_rights'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'decision_rights'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 6, 2.0, 'batch 2 content: stage relevance curve for dimension decision_rights'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'decision_rights'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 7, 1.5, 'batch 2 content: stage relevance curve for dimension decision_rights'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'decision_rights'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 8, 1.0, 'batch 2 content: stage relevance curve for dimension decision_rights'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'decision_rights'
  on conflict (root_cause_id, stage_id) do nothing;

-- hiring_repeatability
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 1, 0.5, 'batch 2 content: stage relevance curve for dimension hiring_repeatability'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'hiring_repeatability'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 2, 0.5, 'batch 2 content: stage relevance curve for dimension hiring_repeatability'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'hiring_repeatability'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 3, 1.0, 'batch 2 content: stage relevance curve for dimension hiring_repeatability'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'hiring_repeatability'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 4, 1.5, 'batch 2 content: stage relevance curve for dimension hiring_repeatability'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'hiring_repeatability'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 5, 2.0, 'batch 2 content: stage relevance curve for dimension hiring_repeatability'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'hiring_repeatability'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 6, 2.0, 'batch 2 content: stage relevance curve for dimension hiring_repeatability'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'hiring_repeatability'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 7, 1.0, 'batch 2 content: stage relevance curve for dimension hiring_repeatability'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'hiring_repeatability'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 8, 0.5, 'batch 2 content: stage relevance curve for dimension hiring_repeatability'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'hiring_repeatability'
  on conflict (root_cause_id, stage_id) do nothing;

-- plan_to_vision_alignment
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 1, 1.5, 'batch 2 content: stage relevance curve for dimension plan_to_vision_alignment'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'plan_to_vision_alignment'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 2, 1.5, 'batch 2 content: stage relevance curve for dimension plan_to_vision_alignment'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'plan_to_vision_alignment'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 3, 1.5, 'batch 2 content: stage relevance curve for dimension plan_to_vision_alignment'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'plan_to_vision_alignment'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 4, 1.5, 'batch 2 content: stage relevance curve for dimension plan_to_vision_alignment'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'plan_to_vision_alignment'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 5, 2.0, 'batch 2 content: stage relevance curve for dimension plan_to_vision_alignment'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'plan_to_vision_alignment'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 6, 1.5, 'batch 2 content: stage relevance curve for dimension plan_to_vision_alignment'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'plan_to_vision_alignment'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 7, 1.0, 'batch 2 content: stage relevance curve for dimension plan_to_vision_alignment'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'plan_to_vision_alignment'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 8, 1.0, 'batch 2 content: stage relevance curve for dimension plan_to_vision_alignment'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'plan_to_vision_alignment'
  on conflict (root_cause_id, stage_id) do nothing;

-- prioritization_discipline
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 1, 1.0, 'batch 2 content: stage relevance curve for dimension prioritization_discipline'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'prioritization_discipline'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 2, 1.5, 'batch 2 content: stage relevance curve for dimension prioritization_discipline'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'prioritization_discipline'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 3, 2.0, 'batch 2 content: stage relevance curve for dimension prioritization_discipline'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'prioritization_discipline'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 4, 1.5, 'batch 2 content: stage relevance curve for dimension prioritization_discipline'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'prioritization_discipline'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 5, 2.0, 'batch 2 content: stage relevance curve for dimension prioritization_discipline'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'prioritization_discipline'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 6, 1.5, 'batch 2 content: stage relevance curve for dimension prioritization_discipline'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'prioritization_discipline'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 7, 1.0, 'batch 2 content: stage relevance curve for dimension prioritization_discipline'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'prioritization_discipline'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 8, 0.5, 'batch 2 content: stage relevance curve for dimension prioritization_discipline'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'prioritization_discipline'
  on conflict (root_cause_id, stage_id) do nothing;

-- institutional_memory
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 1, 0.5, 'batch 2 content: stage relevance curve for dimension institutional_memory'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'institutional_memory'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 2, 0.5, 'batch 2 content: stage relevance curve for dimension institutional_memory'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'institutional_memory'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 3, 1.0, 'batch 2 content: stage relevance curve for dimension institutional_memory'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'institutional_memory'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 4, 1.0, 'batch 2 content: stage relevance curve for dimension institutional_memory'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'institutional_memory'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 5, 1.5, 'batch 2 content: stage relevance curve for dimension institutional_memory'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'institutional_memory'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 6, 2.0, 'batch 2 content: stage relevance curve for dimension institutional_memory'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'institutional_memory'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 7, 2.0, 'batch 2 content: stage relevance curve for dimension institutional_memory'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'institutional_memory'
  on conflict (root_cause_id, stage_id) do nothing;
insert into root_cause_weights (root_cause_id, stage_id, stage_weight, notes)
  select rc.root_cause_id, 8, 1.5, 'batch 2 content: stage relevance curve for dimension institutional_memory'
    from root_causes rc join problems p on p.problem_id = rc.problem_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     and p.dimension_code = 'institutional_memory'
  on conflict (root_cause_id, stage_id) do nothing;

-- Self-check inside the transaction. Any shortfall raises and the whole
-- file rolls back rather than leaving partial weights behind.
do $$
declare rows_now int; short int; s4 numeric;
begin
  select count(*) into rows_now
    from root_cause_weights w join root_causes rc on rc.root_cause_id = w.root_cause_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$';
  if rows_now <> 1080 then
    raise exception 'batch 2 stage weights: expected 1080 rows, have %', rows_now;
  end if;

  select count(*) into short from (
    select rc.root_cause_id
      from root_causes rc
      left join root_cause_weights w on w.root_cause_id = rc.root_cause_id
     where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$'
     group by rc.root_cause_id having count(w.weight_id) <> 8) x;
  if short > 0 then
    raise exception 'batch 2 stage weights: % causes do not have all 8 stages', short;
  end if;

  -- Parity guard. A mean above 1.7 at Early Traction is the signature of
  -- the old flat curve, which would mean this file was regenerated wrongly.
  select round(avg(w.stage_weight),3) into s4
    from root_cause_weights w join root_causes rc on rc.root_cause_id = w.root_cause_id
   where rc.root_cause_code ~ '^RC-(CEL|ECM|EDU|ENR|MED)-[23][0-9][0-9]-[0-9]$' and w.stage_id = 4;
  if s4 > 1.7 then
    raise exception 'batch 2 Early Traction mean is % -- flat curve, not per-dimension', s4;
  end if;

  raise notice 'batch 2 stage weights ok: 135 causes x 8 stages = % rows, Early Traction mean % (catalogue 1.557).', rows_now, s4;
end $$;

COMMIT;
