-- ===========================================================================
-- Industry pain-point weights for the 26 industries that shipped without them.
--
-- Run AFTER 001_industry_selection_tables.sql, against the production RDS
-- instance, the same way:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f 002_industry_pain_point_weights.sql
--
-- Additive and idempotent: the WHERE clause only touches rows that are still
-- empty, so a re-run is a no-op and any value hand-tuned in production later is
-- never overwritten.
--
-- ---------------------------------------------------------------------------
-- WHAT THIS COLUMN DOES
--
-- `industries.top_pain_point_weights` maps a GENERIC problem code to how much
-- more than average that problem matters in this industry. It is the second of
-- two industry signals in question selection:
--
--   question_industry_mapping  -- this question was WRITTEN for this industry
--   top_pain_point_weights     -- this UNIVERSAL question's problem is one this
--                                 industry reports more than average
--
-- The second is what puts the general churn question ahead of the general
-- supply-chain one for a SaaS founder, without either being industry-owned.
-- Without it an industry still works: it gets its own 60 questions first, then
-- everything else in the default order. With it, the general bank is ordered
-- for them too.
--
-- ---------------------------------------------------------------------------
-- HOW THESE WERE BUILT, AND THEIR STATUS
--
-- Four industries (saas, services, manufacturing, ngo) shipped with weights and
-- are NOT touched here. The other 26 carried the '{}' default because the seed
-- migrations wrote only code, name and description for them.
--
-- These 26 follow the shape of those four exactly:
--   * 8 problem codes each
--   * values drawn only from 1.05 / 1.15 / 1.3 / 1.5, two at each level
--   * spread across at least three pillars, so no industry stacks its whole
--     weight in one subject
--   * every code verified to exist in `problems` before writing
--
-- 1.3 is the threshold the ranking treats as "strong" (see
-- app/api/v1/diagnosis/industry_scope.normalise_weight), so the two 1.5s and
-- two 1.3s are the deliberate statement of what goes wrong in that industry,
-- and the 1.15/1.05 pairs are the softer nudges.
--
-- THESE ARE A STARTING POINT, NOT A VERDICT. They are reasoned from each
-- industry's documented failure modes, not measured from founder outcomes.
-- They are data, editable with an UPDATE and no deploy, and they should be
-- revised once real diagnoses show which problems actually recur per industry.
-- Getting them wrong costs question ORDER, never eligibility: a wrong weight
-- can make a good question come later, it can never withhold one.
-- ===========================================================================

\set ON_ERROR_STOP on

BEGIN;

UPDATE industries i
   SET top_pain_point_weights = w.weights,
       updated_at             = now()
FROM (VALUES
 -- Agency economics: clients churn, nobody is differentiated, pricing is soft.
 ('adtech_marketing',     '{"SAL-005":1.5,"CMA-020":1.5,"GTM-007":1.3,"PRD-005":1.3,"SAL-003":1.15,"OPS-002":1.15,"TM-004":1.05,"MEX-001":1.05}'::jsonb),
 -- Reaching farmers is the whole problem, and the cash cycle is seasonal.
 ('agritech',             '{"IVA-001":1.5,"GTM-003":1.5,"FIN-001":1.3,"SAL-004":1.3,"TCI-001":1.15,"OPS-001":1.15,"RSK-002":1.05,"PSY-007":1.05}'::jsonb),
 -- Capital-heavy, supplier-dependent, regulated.
 ('automotive',           '{"BMD-001":1.5,"OPS-003":1.5,"RSK-003":1.3,"OPS-006":1.3,"FIN-001":1.15,"SAL-003":1.15,"OPS-001":1.05,"CMA-001":1.05}'::jsonb),
 -- Repeat purchase is everything; the category is crowded and ad-funded.
 ('beauty_personal_care', '{"GTM-007":1.5,"CMA-020":1.5,"SAL-003":1.3,"GTM-002":1.3,"SCL-039":1.15,"PRD-004":1.15,"OPS-004":1.05,"MEX-001":1.05}'::jsonb),
 -- Long cycles, project concentration, customer pays long after you do.
 ('cleantech_energy',     '{"FIN-001":1.5,"SAL-002":1.5,"RSK-003":1.3,"OPS-006":1.3,"BMD-001":1.15,"GTM-005":1.15,"BPL-003":1.05,"OPS-001":1.05}'::jsonb),
 -- Hardware: one factory, and quality is the product.
 ('consumer_electronics', '{"RSK-003":1.5,"PRD-004":1.5,"BMD-001":1.3,"OPS-003":1.3,"FIN-001":1.15,"SAL-003":1.15,"OPS-001":1.05,"CMA-002":1.05}'::jsonb),
 -- Ad spend against margin, and the marketplace owns the customer.
 ('ecommerce_d2c',        '{"GTM-007":1.5,"SAL-003":1.5,"SCL-039":1.3,"CMA-020":1.3,"FIN-001":1.15,"OPS-004":1.15,"PRD-004":1.05,"GTM-002":1.05}'::jsonb),
 -- Completion and renewal, not enrolment.
 ('edtech',               '{"GTM-007":1.5,"IVA-001":1.5,"SAL-005":1.3,"PRD-002":1.3,"SAL-003":1.15,"TCI-002":1.15,"MEX-001":1.05,"OPS-005":1.05}'::jsonb),
 -- Margin after returns, and cash trapped in inventory.
 ('fashion_apparel',      '{"BMD-001":1.5,"GTM-007":1.5,"CMA-020":1.3,"FIN-001":1.3,"PRD-004":1.15,"SCL-039":1.15,"OPS-004":1.05,"MEX-001":1.05}'::jsonb),
 -- Licensing and fraud before anything else.
 ('fintech',              '{"OPS-006":1.5,"RSK-016":1.5,"RSK-002":1.3,"SAL-004":1.3,"OPS-005":1.15,"BMD-001":1.15,"TM-005":1.05,"GTM-002":1.05}'::jsonb),
 -- Thin margins, aggregator dependency, repeat orders.
 ('foodtech',             '{"BMD-001":1.5,"GTM-007":1.5,"OPS-001":1.3,"SCL-039":1.3,"FIN-001":1.15,"PRD-004":1.15,"OPS-006":1.05,"CMA-002":1.05}'::jsonb),
 -- Monetisation and retention, on somebody else's store.
 ('gaming',               '{"SAL-004":1.5,"GTM-007":1.5,"RSK-003":1.3,"SCL-039":1.3,"PRD-002":1.15,"IVA-001":1.15,"PRD-004":1.05,"TM-002":1.05}'::jsonb),
 -- Who pays is rarely who uses, and the category is regulated.
 ('healthtech',           '{"IVA-001":1.5,"OPS-006":1.5,"SAL-004":1.3,"RSK-016":1.3,"TCI-001":1.15,"SAL-002":1.15,"PRD-004":1.05,"OPS-005":1.05}'::jsonb),
 -- B2B SaaS shape: who buys, and do they renew.
 ('hrtech',               '{"GTM-002":1.5,"SAL-005":1.5,"SAL-002":1.3,"IVA-001":1.3,"GTM-007":1.15,"SAL-003":1.15,"PRD-001":1.05,"TCI-002":1.05}'::jsonb),
 -- Conservative buyers, and how the work is billed.
 ('legaltech',            '{"IVA-001":1.5,"SAL-004":1.5,"SAL-002":1.3,"RSK-016":1.3,"GTM-002":1.15,"SAL-005":1.15,"PRD-004":1.05,"OPS-001":1.05}'::jsonb),
 -- Cost per delivery, and operations IS the product.
 ('logistics',            '{"BMD-001":1.5,"OPS-001":1.5,"RSK-003":1.3,"SAL-003":1.3,"OPS-005":1.15,"TM-004":1.15,"OPS-006":1.05,"FIN-001":1.05}'::jsonb),
 -- Who pays for the content, and the platform that sits in between.
 ('media_entertainment',  '{"SAL-004":1.5,"SCL-039":1.5,"GTM-007":1.3,"CMA-020":1.3,"BMD-001":1.15,"MEX-001":1.15,"PRD-002":1.05,"RSK-003":1.05}'::jsonb),
 -- Regulation and the cost of getting to market at all.
 ('pharma_biotech',       '{"OPS-006":1.5,"FIN-001":1.5,"RSK-016":1.3,"BPL-003":1.3,"BMD-001":1.15,"SAL-002":1.15,"PRD-004":1.05,"TM-002":1.05}'::jsonb),
 -- Capital tied up, long high-value cycles, RERA.
 ('proptech',             '{"FIN-001":1.5,"SAL-002":1.5,"RSK-003":1.3,"OPS-006":1.3,"BMD-001":1.15,"GTM-003":1.15,"CMA-002":1.05,"OPS-001":1.05}'::jsonb),
 -- Margin and inventory, then whether anyone comes back.
 ('retail',               '{"BMD-001":1.5,"FIN-001":1.5,"RSK-003":1.3,"GTM-007":1.3,"OPS-001":1.15,"OPS-005":1.15,"CMA-002":1.05,"PRD-004":1.05}'::jsonb),
 -- Memberships churn, and capacity sits idle.
 ('sports_fitness',       '{"SAL-005":1.5,"BMD-001":1.5,"GTM-007":1.3,"RSK-003":1.3,"OPS-001":1.15,"SAL-003":1.15,"CMA-020":1.05,"MEX-001":1.05}'::jsonb),
 -- Churn and one upstream provider.
 ('telecom',              '{"SAL-005":1.5,"RSK-003":1.5,"OPS-006":1.3,"BMD-001":1.3,"FIN-001":1.15,"OPS-005":1.15,"SAL-003":1.05,"CMA-002":1.05}'::jsonb),
 -- A few large buyers, and working capital.
 ('textiles',             '{"RSK-003":1.5,"FIN-001":1.5,"BMD-001":1.3,"PRD-004":1.3,"OPS-001":1.15,"OPS-003":1.15,"GTM-003":1.05,"TM-004":1.05}'::jsonb),
 -- Counterparty risk and landed cost.
 ('trade_import_export',  '{"RSK-002":1.5,"BMD-001":1.5,"FIN-001":1.3,"OPS-006":1.3,"RSK-003":1.15,"RSK-016":1.15,"SAL-003":1.05,"OPS-001":1.05}'::jsonb),
 -- Last mile: cost per drop, and the aggregator squeezing it.
 ('transport_delivery',   '{"BMD-001":1.5,"OPS-001":1.5,"SCL-039":1.3,"RSK-003":1.3,"TM-004":1.15,"OPS-005":1.15,"SAL-003":1.05,"OPS-006":1.05}'::jsonb),
 -- Seasonality, and the OTA that owns the guest.
 ('travel_hospitality',   '{"FIN-001":1.5,"SCL-039":1.5,"BMD-001":1.3,"GTM-007":1.3,"PRD-004":1.15,"CMA-002":1.15,"OPS-001":1.05,"MEX-001":1.05}'::jsonb)
) AS w(code, weights)
WHERE i.industry_code = w.code
  AND (i.top_pain_point_weights = '{}'::jsonb OR i.top_pain_point_weights IS NULL);

COMMIT;

-- ===========================================================================
-- VERIFICATION. Expected:
--   industries_with_weights     30
--   total_weight_entries       240
--   codes_that_do_not_exist      0   <- must be 0, a bad code is a silent no-op
--   weights_off_scale            0   <- only 1.05 / 1.15 / 1.3 / 1.5
--   min/max_codes_per_industry 8 / 8
--   pillars_covered              6
-- ===========================================================================
WITH w AS (
  SELECT i.industry_code, k.key AS problem_code, (k.value)::text::numeric AS weight
  FROM industries i, jsonb_each(i.top_pain_point_weights) k
)
SELECT
  (SELECT count(*) FROM industries WHERE top_pain_point_weights <> '{}'::jsonb)   AS industries_with_weights,
  (SELECT count(*) FROM w)                                                        AS total_weight_entries,
  (SELECT count(*) FROM w WHERE NOT EXISTS
      (SELECT 1 FROM problems p WHERE p.problem_code = w.problem_code))            AS codes_that_do_not_exist,
  (SELECT count(*) FROM w WHERE weight NOT IN (1.05,1.15,1.3,1.5))                 AS weights_off_scale,
  (SELECT min(c) FROM (SELECT count(*) c FROM w GROUP BY industry_code) s)         AS min_codes_per_industry,
  (SELECT max(c) FROM (SELECT count(*) c FROM w GROUP BY industry_code) s)         AS max_codes_per_industry,
  (SELECT count(DISTINCT p.pillar_id) FROM w
     JOIN problems p ON p.problem_code = w.problem_code)                           AS pillars_covered;
