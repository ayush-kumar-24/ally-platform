-- =====================================================================
-- CORRECTION: give the batch stage weights a curve per DIMENSION instead of
-- one flat curve for every cause.
--
-- WHAT WENT WRONG -- and this is my error, not a catalogue problem.
-- fix_batch_stage_weights.sql, fix_batch3_stage_weights.sql and
-- fix_batch4_stage_weights.sql all wrote the SAME eight values for every
-- cause: 1.0, 2.0, 2.0, 2.0, 1.5, 1.0, 0.5, 0.5. That put every one of the
-- 540 batch causes at the maximum 2.00 at Early Traction, while the original
-- catalogue is spread across 0.50-2.00 there with a mean of 1.557 and only
-- 20% of causes at the top value.
--
-- MEASURED CONSEQUENCE. A real SaaS founder run at Early Traction returned
-- batch causes at ranks 1, 2, 3, 4 and 5, with all three top findings from
-- batch content, every one carrying stage_probability 1.0000 against 0.6667
-- for the original causes below them. The intent was to remove a handicap;
-- the effect was to hand the new content an advantage. A ranking that looks
-- like the new content winning on merit, when it is winning on a weight I
-- chose, is worse than the handicap it replaced.
--
-- THE FIX. stage_weight answers "how relevant is this cause at this stage",
-- which is a property of the DIMENSION, not of the batch the content arrived
-- in. One curve per dimension, reasoned from what the dimension is:
--
--   skill_stage_fit              1.5  2.0  2.0  1.5  1.5  1.0  0.5  0.5
--     the gap between what the founder can do and what the stage needs is sharpest while the business is still being figured out
--   time_allocation_reality      1.0  1.5  1.5  2.0  2.0  1.5  0.5  0.5
--     founder hours bind hardest once there is traction to service but no team to service it
--   founder_dependency           0.5  1.0  1.5  2.0  2.0  2.0  1.0  0.5
--     a bottleneck only costs you once there is volume trying to get through it
--   team_structure_role_clarity  0.5  0.5  1.0  1.5  2.0  2.0  1.5  0.5
--     needs a team before it can be wrong
--   decision_rights              0.5  0.5  1.0  1.5  2.0  2.0  1.5  1.0
--     same, and it stays expensive later than role clarity does
--   hiring_repeatability         0.5  0.5  1.0  1.5  2.0  2.0  1.0  0.5
--     matters when hiring at pace, not when hiring your first two
--   plan_to_vision_alignment     1.5  1.5  1.5  1.5  2.0  1.5  1.0  1.0
--     live at every stage; drift is possible from day one
--   prioritization_discipline    1.0  1.5  2.0  1.5  2.0  1.5  1.0  0.5
--     peaks when the options multiply faster than the capacity
--   institutional_memory         0.5  0.5  1.0  1.0  1.5  2.0  2.0  1.5
--     needs history and turnover before the loss can be felt
--
-- At Early Traction this lands the batch mean on 1.556 against the original
-- catalogue's 1.557 -- parity, which is what was wanted. Where the curves do
-- diverge from the catalogue (lower at Ideation, higher at Expansion) it is
-- because the dimension says so: a solo pre-team founder does not have a
-- role-clarity problem, and founder dependency is exactly what binds at
-- Expansion. That divergence is a claim about the content, not a thumb on
-- the scale for it.
--
-- SUPERSEDES the flat curve in the three insert files. Run this AFTER them.
-- It is an UPDATE only: it inserts nothing, deletes nothing, and touches no
-- cause outside the batch code pattern. Safe to re-run -- the second run
-- sets the same values.
-- =====================================================================

BEGIN;

-- skill_stage_fit
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension skill_stage_fit'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 1   and p.dimension_code = 'skill_stage_fit'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension skill_stage_fit'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 2   and p.dimension_code = 'skill_stage_fit'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension skill_stage_fit'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 3   and p.dimension_code = 'skill_stage_fit'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension skill_stage_fit'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 4   and p.dimension_code = 'skill_stage_fit'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension skill_stage_fit'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 5   and p.dimension_code = 'skill_stage_fit'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension skill_stage_fit'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 6   and p.dimension_code = 'skill_stage_fit'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension skill_stage_fit'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 7   and p.dimension_code = 'skill_stage_fit'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension skill_stage_fit'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 8   and p.dimension_code = 'skill_stage_fit'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';

-- time_allocation_reality
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension time_allocation_reality'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 1   and p.dimension_code = 'time_allocation_reality'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension time_allocation_reality'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 2   and p.dimension_code = 'time_allocation_reality'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension time_allocation_reality'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 3   and p.dimension_code = 'time_allocation_reality'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension time_allocation_reality'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 4   and p.dimension_code = 'time_allocation_reality'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension time_allocation_reality'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 5   and p.dimension_code = 'time_allocation_reality'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension time_allocation_reality'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 6   and p.dimension_code = 'time_allocation_reality'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension time_allocation_reality'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 7   and p.dimension_code = 'time_allocation_reality'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension time_allocation_reality'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 8   and p.dimension_code = 'time_allocation_reality'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';

-- founder_dependency
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension founder_dependency'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 1   and p.dimension_code = 'founder_dependency'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension founder_dependency'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 2   and p.dimension_code = 'founder_dependency'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension founder_dependency'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 3   and p.dimension_code = 'founder_dependency'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension founder_dependency'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 4   and p.dimension_code = 'founder_dependency'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension founder_dependency'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 5   and p.dimension_code = 'founder_dependency'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension founder_dependency'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 6   and p.dimension_code = 'founder_dependency'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension founder_dependency'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 7   and p.dimension_code = 'founder_dependency'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension founder_dependency'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 8   and p.dimension_code = 'founder_dependency'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';

-- team_structure_role_clarity
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension team_structure_role_clarity'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 1   and p.dimension_code = 'team_structure_role_clarity'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension team_structure_role_clarity'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 2   and p.dimension_code = 'team_structure_role_clarity'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension team_structure_role_clarity'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 3   and p.dimension_code = 'team_structure_role_clarity'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension team_structure_role_clarity'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 4   and p.dimension_code = 'team_structure_role_clarity'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension team_structure_role_clarity'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 5   and p.dimension_code = 'team_structure_role_clarity'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension team_structure_role_clarity'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 6   and p.dimension_code = 'team_structure_role_clarity'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension team_structure_role_clarity'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 7   and p.dimension_code = 'team_structure_role_clarity'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension team_structure_role_clarity'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 8   and p.dimension_code = 'team_structure_role_clarity'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';

-- decision_rights
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension decision_rights'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 1   and p.dimension_code = 'decision_rights'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension decision_rights'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 2   and p.dimension_code = 'decision_rights'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension decision_rights'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 3   and p.dimension_code = 'decision_rights'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension decision_rights'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 4   and p.dimension_code = 'decision_rights'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension decision_rights'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 5   and p.dimension_code = 'decision_rights'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension decision_rights'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 6   and p.dimension_code = 'decision_rights'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension decision_rights'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 7   and p.dimension_code = 'decision_rights'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension decision_rights'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 8   and p.dimension_code = 'decision_rights'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';

-- hiring_repeatability
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension hiring_repeatability'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 1   and p.dimension_code = 'hiring_repeatability'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension hiring_repeatability'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 2   and p.dimension_code = 'hiring_repeatability'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension hiring_repeatability'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 3   and p.dimension_code = 'hiring_repeatability'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension hiring_repeatability'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 4   and p.dimension_code = 'hiring_repeatability'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension hiring_repeatability'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 5   and p.dimension_code = 'hiring_repeatability'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension hiring_repeatability'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 6   and p.dimension_code = 'hiring_repeatability'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension hiring_repeatability'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 7   and p.dimension_code = 'hiring_repeatability'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension hiring_repeatability'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 8   and p.dimension_code = 'hiring_repeatability'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';

-- plan_to_vision_alignment
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension plan_to_vision_alignment'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 1   and p.dimension_code = 'plan_to_vision_alignment'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension plan_to_vision_alignment'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 2   and p.dimension_code = 'plan_to_vision_alignment'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension plan_to_vision_alignment'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 3   and p.dimension_code = 'plan_to_vision_alignment'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension plan_to_vision_alignment'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 4   and p.dimension_code = 'plan_to_vision_alignment'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension plan_to_vision_alignment'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 5   and p.dimension_code = 'plan_to_vision_alignment'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension plan_to_vision_alignment'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 6   and p.dimension_code = 'plan_to_vision_alignment'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension plan_to_vision_alignment'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 7   and p.dimension_code = 'plan_to_vision_alignment'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension plan_to_vision_alignment'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 8   and p.dimension_code = 'plan_to_vision_alignment'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';

-- prioritization_discipline
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension prioritization_discipline'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 1   and p.dimension_code = 'prioritization_discipline'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension prioritization_discipline'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 2   and p.dimension_code = 'prioritization_discipline'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension prioritization_discipline'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 3   and p.dimension_code = 'prioritization_discipline'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension prioritization_discipline'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 4   and p.dimension_code = 'prioritization_discipline'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension prioritization_discipline'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 5   and p.dimension_code = 'prioritization_discipline'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension prioritization_discipline'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 6   and p.dimension_code = 'prioritization_discipline'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension prioritization_discipline'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 7   and p.dimension_code = 'prioritization_discipline'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension prioritization_discipline'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 8   and p.dimension_code = 'prioritization_discipline'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';

-- institutional_memory
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension institutional_memory'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 1   and p.dimension_code = 'institutional_memory'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 0.5, notes = 'batch content: stage relevance curve for dimension institutional_memory'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 2   and p.dimension_code = 'institutional_memory'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension institutional_memory'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 3   and p.dimension_code = 'institutional_memory'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.0, notes = 'batch content: stage relevance curve for dimension institutional_memory'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 4   and p.dimension_code = 'institutional_memory'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension institutional_memory'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 5   and p.dimension_code = 'institutional_memory'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension institutional_memory'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 6   and p.dimension_code = 'institutional_memory'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 2.0, notes = 'batch content: stage relevance curve for dimension institutional_memory'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 7   and p.dimension_code = 'institutional_memory'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';
update root_cause_weights w set stage_weight = 1.5, notes = 'batch content: stage relevance curve for dimension institutional_memory'  from root_causes rc join problems p on p.problem_id = rc.problem_id where w.root_cause_id = rc.root_cause_id and w.stage_id = 8   and p.dimension_code = 'institutional_memory'   and rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$';

-- Self-check: prove the correction landed and that Early Traction is at
-- parity with the original catalogue, or roll the whole thing back.
do $$
declare distinct_s4 int; batch_mean numeric; orig_mean numeric;
begin
  -- The flat curve gave EVERY batch cause the same eight values, so the
  -- signature of it still being in place is that stage 4 has exactly one
  -- distinct weight across the whole batch. After the correction it must have
  -- several. (An earlier version of this check asserted that no cause sits at
  -- 2.0 for stage 4, which was simply wrong: time_allocation_reality and
  -- founder_dependency both peak there, so 120 causes at 2.0 is the curve
  -- working, not the curve failing to apply.)
  select count(distinct w.stage_weight) into distinct_s4
    from root_cause_weights w
    join root_causes rc on rc.root_cause_id = w.root_cause_id
   where rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$'
     and w.stage_id = 4;
  if distinct_s4 < 2 then
    raise exception 'correction did not apply: stage 4 still has only % distinct weight(s) across the batch', distinct_s4;
  end if;

  select round(avg(w.stage_weight),3) into batch_mean
    from root_cause_weights w join root_causes rc on rc.root_cause_id = w.root_cause_id
   where rc.root_cause_code ~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$' and w.stage_id = 4;
  select round(avg(w.stage_weight),3) into orig_mean
    from root_cause_weights w join root_causes rc on rc.root_cause_id = w.root_cause_id
   where rc.root_cause_code !~ '^RC-[A-Z]{3}-[23][0-9][0-9]-[0-9]$' and w.stage_id = 4;

  if abs(batch_mean - orig_mean) > 0.10 then
    raise exception 'Early Traction still not at parity: batch %, original % (want within 0.10)',
      batch_mean, orig_mean;
  end if;

  raise notice 'stage weight curves applied. Early Traction mean: batch %, original % -- at parity.',
    batch_mean, orig_mean;
end $$;

COMMIT;
