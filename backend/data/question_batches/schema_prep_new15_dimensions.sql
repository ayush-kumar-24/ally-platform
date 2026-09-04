-- ============================================================
-- Ally / Founder Alley -- Schema prep for the new 15-dimension layer
-- (Product/Sales/Marketing/Finance/HR x People/Process/Technology)
--
-- This creates the underlying reference data the question batches
-- depend on. Run this FIRST, before any of the question INSERT files
-- for this layer (Stage 0, Stage 0->1, Stage 1->10+ batches).
--
-- Contents:
--   10 new tags        (question_tags,      IDs 79-88)
--   6 new problems     (problems,            IDs 270-275)
--   36 new root causes (root_causes,         IDs 1976-2011)
--
-- VERIFIED: every row generated directly from a live Supabase query
-- via Postgres string_agg (not retyped/reconstructed), so the SQL
-- text below is byte-identical to what's live on Supabase.
--
-- Idempotency: this uses explicit IDs (not nextval defaults) so it
-- stays in sync with Supabase. Only run once against a given target;
-- running twice will fail on primary key conflicts, which is the
-- correct/safe behavior here (better a clear error than duplicates).
--
-- Question 2756-2965 (Stage 0->1, new 15-dim layer) directly depend
-- on this: those questions reference tag_id 79 and 84, and their
-- question_tag_mapping rows will fail without this file applied first.
-- Later batches (Stage 1->10+) depend on all of it.
-- ============================================================

BEGIN;

-- ---- 1. Tags ----
INSERT INTO question_tags (tag_id, tag_name)
VALUES
(79, 'sales-team-capability'),
(80, 'sales-tooling'),
(81, 'marketing-team-capability'),
(82, 'marketing-tooling'),
(83, 'financial-oversight-capability'),
(84, 'financial-process'),
(85, 'financial-tooling'),
(86, 'hr-capability'),
(87, 'hr-process'),
(88, 'hr-tooling')
;

SELECT setval('question_tags_tag_id_seq', (SELECT MAX(tag_id) FROM question_tags));

-- ---- 2. Problems ----
INSERT INTO problems (problem_id, problem_code, problem_name, category, subcategory, layer,
  description, severity_min, severity_max, symptoms, pillar_id, embedding,
  embedding_model, embedding_version, embedding_dimension)
VALUES
(270, 'SLX-196', 'No Sales Tooling or Pipeline Visibility', 'Sales Execution', 'Sales Technology', 'external', 'Without a system to track deals, pipeline health becomes invisible and depends entirely on memory. As deal volume grows, this creates blind spots that surface only when a quarter''s numbers come in short.', 4, 8, '["No CRM or deal-tracking tool in use, even a basic one", "Pipeline exists only in the founder or a rep''s head, or a spreadsheet nobody else updates", "No visibility into how many deals are at each stage at any given time", "Follow-up depends on individual memory rather than a system-driven reminder", "Sales data and relationship history is lost when a salesperson leaves", "No way to report conversion rates or deal velocity without manually reconstructing it"]'::jsonb, 3, NULL, NULL, NULL, NULL),
(271, 'MEX-102', 'No Dedicated Marketing Capability', 'Marketing Execution', 'Marketing Team', 'external', 'Marketing is often the first function founders treat as optional, handled by whoever has spare time rather than someone with real expertise. This produces inconsistent output and no institutional memory of what has or hasn''t worked.', 4, 8, '["No one on the team owns marketing as a defined responsibility", "Marketing tasks get picked up reactively by whoever is free that week", "No one on the team has real marketing skill or prior experience", "Marketing decisions are made without any relevant expertise in the room", "No budget or headcount has ever been deliberately allocated to marketing", "Whoever handles marketing changes frequently, with no continuity between them"]'::jsonb, 2, NULL, NULL, NULL, NULL),
(272, 'MEX-103', 'No Marketing Tools or Performance Tracking', 'Marketing Execution', 'Marketing Technology', 'external', 'Without tooling to track what actually works, marketing spend and effort accumulate without any real feedback loop. Campaigns get repeated or abandoned based on gut feel rather than evidence.', 3, 7, '["No analytics tool tracks whether a campaign actually performed", "No central place holds marketing assets, so things get rebuilt or lost", "Campaign results are never actually measured against a goal", "No tool schedules or automates recurring marketing activity", "Marketing spend is tracked manually, inconsistently, or not at all", "No way to trace a lead back to the specific channel or campaign that produced it"]'::jsonb, 2, NULL, NULL, NULL, NULL),
(273, 'FIN-152', 'No Real Financial Oversight Capability', 'Financial Management', 'Financial Leadership', 'external', 'When no one with real financial expertise is reviewing the numbers, problems compound silently until they become emergencies. The founder often becomes the sole holder of financial understanding, which is itself a risk.', 5, 9, '["No one with real financial training or expertise reviews the numbers regularly", "The founder is the only person who understands the company''s financial position", "Financial decisions get made without consulting anyone qualified to weigh in", "No bookkeeper or accountant has been engaged, even part-time", "Financial reviews happen rarely, or only once something has already gone wrong", "No one besides the founder could explain the business''s financial position if asked"]'::jsonb, 3, NULL, NULL, NULL, NULL),
(274, 'FIN-153', 'No Financial Systems or Tracking Tools', 'Financial Management', 'Financial Technology', 'external', 'Manual, scattered financial tracking makes it impossible to get a real-time read on the business, and small errors compound invisibly until a reconciliation forces them into view.', 4, 8, '["No accounting software is in use, even a basic one", "Expenses and revenue are tracked manually or inconsistently across different places", "There is no real-time view of current cash position", "Invoicing is handled ad hoc, with no consistent system behind it", "No tool reconciles bank transactions against the company''s own records", "Financial records exist scattered across spreadsheets, email, and paper"]'::jsonb, 3, NULL, NULL, NULL, NULL),
(275, 'TM-077', 'No People Systems or HR Tooling', 'Team & Leadership', 'HR Technology', 'external', 'As headcount grows past a handful of people, informal people-management stops scaling. Without systems, basic things like leave tracking and documentation become a source of real operational risk.', 3, 7, '["No system tracks employee records or documents in one place", "Payroll is handled manually or ad hoc rather than through a system", "No tool manages leave, attendance, or time off requests", "Performance reviews, when they happen, are not tracked or documented anywhere", "Onboarding has no checklist or system behind it — it happens differently each time", "No central place holds the company''s actual policies, so nobody is sure what applies"]'::jsonb, 5, NULL, NULL, NULL, NULL)
;

SELECT setval('problems_problem_id_seq', (SELECT MAX(problem_id) FROM problems));

-- ---- 3. Root causes ----
INSERT INTO root_causes (root_cause_id, root_cause_code, problem_id, root_cause_name,
  root_cause_category, explanation, confidence_weight, layer, primary_stage_group,
  embedding, embedding_model, embedding_version, embedding_dimension)
VALUES
(1976, 'RC-1976', 270, 'No CRM in Use', 'Operational', 'No tool exists to record deals, contacts, or deal stage — everything depends on memory or scattered notes.', 0.65, 'external', NULL, NULL, NULL, NULL, NULL),
(1977, 'RC-1977', 270, 'Pipeline Tracked Only Informally', 'Operational', 'Deal status lives in the founder or a rep''s head, or a spreadsheet nobody else reliably updates.', 0.65, 'external', NULL, NULL, NULL, NULL, NULL),
(1978, 'RC-1978', 270, 'No Visibility into Deal Stage or Conversion', 'Operational', 'There is no way to see, at a glance, how many deals sit at each stage or how they convert.', 0.62, 'external', NULL, NULL, NULL, NULL, NULL),
(1979, 'RC-1979', 270, 'Manual, Untracked Follow-Up', 'Operational', 'Follow-up depends on someone remembering to do it, rather than a system prompting it.', 0.60, 'external', NULL, NULL, NULL, NULL, NULL),
(1980, 'RC-1980', 270, 'No Sales Reporting', 'Operational', 'Nobody can produce a real report on sales activity or outcomes without manually reconstructing it.', 0.60, 'external', NULL, NULL, NULL, NULL, NULL),
(1981, 'RC-1981', 270, 'Sales Knowledge Lost When a Rep Leaves', 'Operational', 'Relationship history and deal context exist only with the individual, not the company.', 0.63, 'external', NULL, NULL, NULL, NULL, NULL),
(1982, 'RC-1982', 271, 'No One Owns Marketing', 'Operational', 'Marketing has no defined owner, so it happens only when someone happens to have spare time.', 0.65, 'external', NULL, NULL, NULL, NULL, NULL),
(1983, 'RC-1983', 271, 'Marketing Treated as a Side Task', 'Operational', 'Marketing work gets picked up reactively rather than planned or resourced deliberately.', 0.62, 'external', NULL, NULL, NULL, NULL, NULL),
(1984, 'RC-1984', 271, 'No Marketing Skill on the Team', 'Knowledge', 'Nobody involved has real marketing training or prior hands-on experience.', 0.65, 'external', NULL, NULL, NULL, NULL, NULL),
(1985, 'RC-1985', 271, 'Marketing Decisions Made Without Expertise', 'Knowledge', 'Choices about positioning, channel, or messaging are made without anyone qualified weighing in.', 0.63, 'external', NULL, NULL, NULL, NULL, NULL),
(1986, 'RC-1986', 271, 'No Budget Allocated to Marketing', 'Strategic', 'Marketing has never been given a deliberate budget or headcount allocation.', 0.60, 'external', NULL, NULL, NULL, NULL, NULL),
(1987, 'RC-1987', 271, 'No Continuity in Who Handles Marketing', 'Operational', 'Whoever owns marketing changes often, so nothing compounds or improves over time.', 0.60, 'external', NULL, NULL, NULL, NULL, NULL),
(1988, 'RC-1988', 272, 'No Analytics Tracking Campaign Performance', 'Operational', 'No tool confirms whether a given campaign actually produced results.', 0.63, 'external', NULL, NULL, NULL, NULL, NULL),
(1989, 'RC-1989', 272, 'No Central Asset Repository', 'Operational', 'Marketing materials live scattered across devices and get rebuilt or lost.', 0.58, 'external', NULL, NULL, NULL, NULL, NULL),
(1990, 'RC-1990', 272, 'Campaign Results Never Measured', 'Operational', 'Campaigns run and end without anyone checking whether they hit a goal.', 0.62, 'external', NULL, NULL, NULL, NULL, NULL),
(1991, 'RC-1991', 272, 'No Scheduling or Automation Tooling', 'Operational', 'Recurring marketing activity depends on someone remembering to do it manually each time.', 0.58, 'external', NULL, NULL, NULL, NULL, NULL),
(1992, 'RC-1992', 272, 'Spend Tracked Inconsistently', 'Operational', 'Marketing spend is not tracked in one consistent place, making ROI impossible to assess.', 0.60, 'external', NULL, NULL, NULL, NULL, NULL),
(1993, 'RC-1993', 272, 'No Lead Source Attribution', 'Operational', 'There is no way to trace which channel or campaign actually produced a given lead.', 0.62, 'external', NULL, NULL, NULL, NULL, NULL),
(1994, 'RC-1994', 273, 'No Financial Expertise Reviewing Numbers', 'Knowledge', 'Nobody with real financial training regularly checks the company''s numbers.', 0.68, 'external', NULL, NULL, NULL, NULL, NULL),
(1995, 'RC-1995', 273, 'Founder Is Sole Financial Understanding', 'Operational', 'Only the founder understands the company''s real financial position, a single point of failure.', 0.65, 'external', NULL, NULL, NULL, NULL, NULL),
(1996, 'RC-1996', 273, 'Financial Decisions Made Without Qualified Input', 'Knowledge', 'Major financial calls get made without anyone qualified reviewing them first.', 0.65, 'external', NULL, NULL, NULL, NULL, NULL),
(1997, 'RC-1997', 273, 'No Bookkeeper or Accountant Engaged', 'Operational', 'Nobody, even part-time, is responsible for keeping the books accurate.', 0.65, 'external', NULL, NULL, NULL, NULL, NULL),
(1998, 'RC-1998', 273, 'Financial Reviews Happen Only Under Pressure', 'Operational', 'The numbers only get a real look once something has already gone wrong.', 0.63, 'external', NULL, NULL, NULL, NULL, NULL),
(1999, 'RC-1999', 273, 'No Successor Understands Finances', 'Operational', 'If the founder were unavailable, nobody else could explain the financial position.', 0.62, 'external', NULL, NULL, NULL, NULL, NULL),
(2000, 'RC-2000', 274, 'No Accounting Software in Use', 'Operational', 'Even basic accounting software has never been adopted.', 0.65, 'external', NULL, NULL, NULL, NULL, NULL),
(2001, 'RC-2001', 274, 'Expenses Tracked Inconsistently', 'Operational', 'Revenue and expenses are recorded manually and inconsistently across different places.', 0.63, 'external', NULL, NULL, NULL, NULL, NULL),
(2002, 'RC-2002', 274, 'No Real-Time Cash Position', 'Operational', 'Nobody can state the current cash position without manually reconstructing it.', 0.65, 'external', NULL, NULL, NULL, NULL, NULL),
(2003, 'RC-2003', 274, 'Invoicing Handled Ad Hoc', 'Operational', 'Invoices are created and sent without a consistent system or template behind them.', 0.58, 'external', NULL, NULL, NULL, NULL, NULL),
(2004, 'RC-2004', 274, 'No Bank Reconciliation Tool', 'Operational', 'Nothing checks bank transactions against the company''s own financial records.', 0.60, 'external', NULL, NULL, NULL, NULL, NULL),
(2005, 'RC-2005', 274, 'Records Scattered Across Multiple Places', 'Operational', 'Financial records live across spreadsheets, email, and paper with no single source of truth.', 0.62, 'external', NULL, NULL, NULL, NULL, NULL),
(2006, 'RC-2006', 275, 'No Employee Records System', 'Operational', 'Employee documents and records are not held in any single, organized system.', 0.60, 'external', NULL, NULL, NULL, NULL, NULL),
(2007, 'RC-2007', 275, 'Payroll Handled Manually', 'Operational', 'Payroll runs manually or ad hoc rather than through a dedicated system.', 0.62, 'external', NULL, NULL, NULL, NULL, NULL),
(2008, 'RC-2008', 275, 'No Leave or Attendance Tool', 'Operational', 'Time off and attendance are tracked informally, if at all.', 0.58, 'external', NULL, NULL, NULL, NULL, NULL),
(2009, 'RC-2009', 275, 'Performance Reviews Undocumented', 'Operational', 'When reviews happen, they are not tracked or recorded anywhere.', 0.60, 'external', NULL, NULL, NULL, NULL, NULL),
(2010, 'RC-2010', 275, 'Onboarding Has No System', 'Operational', 'New hires go through a different, improvised process each time.', 0.60, 'external', NULL, NULL, NULL, NULL, NULL),
(2011, 'RC-2011', 275, 'No Central Policy Repository', 'Operational', 'Company policies exist informally, so nobody is quite sure what currently applies.', 0.58, 'external', NULL, NULL, NULL, NULL, NULL)
;

SELECT setval('root_causes_root_cause_id_seq', (SELECT MAX(root_cause_id) FROM root_causes));

COMMIT;