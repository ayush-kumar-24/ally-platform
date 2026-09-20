"""seed industry batch C: pharma, services, sports/fitness, retail

Revision ID: d9c31e4f6a82
Revises: c8b20d3e5f71
Create Date: 2026-09-20
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "d9c31e4f6a82"
down_revision: Union[str, Sequence[str], None] = "c8b20d3e5f71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sync_sequence(bind, table_name: str, column_name: str) -> None:
    bind.exec_driver_sql(
        f"""
        SELECT setval(
            pg_get_serial_sequence('{table_name}', '{column_name}'),
            COALESCE((SELECT MAX({column_name}) FROM {table_name}), 1),
            EXISTS (SELECT 1 FROM {table_name})
        )
        """
    )


def upgrade() -> None:
    bind = op.get_bind()

    _sync_sequence(bind, "industries", "industry_id")
    _sync_sequence(bind, "interventions", "intervention_id")

    industry_rows = [
        ('pharma_biotech', 'Pharmaceuticals & Biotech', 'Drug development, biotech research, pharmaceutical manufacturing, clinical research and life-sciences businesses.'),
        ('services', 'Services & Consulting', 'Consulting, professional services, advisory, implementation, specialist and service-led businesses.'),
        ('sports_fitness', 'Sports, Fitness & Wellness', 'Gyms, fitness studios, sports technology, wellness services, nutrition, sports leagues and related businesses.'),
        ('retail', 'Retail', 'Brick-and-mortar retail, franchise, omni-channel, specialty retail and store-led commerce businesses.'),
    ]

    for industry_code, industry_name, description in industry_rows:
        bind.execute(
            text(
                """
                INSERT INTO industries (
                    industry_code, industry_name, description, industry_subtitle
                )
                VALUES (
                    :industry_code, :industry_name, :description, :industry_subtitle
                )
                ON CONFLICT (industry_code) DO UPDATE SET
                    industry_name = EXCLUDED.industry_name,
                    description = EXCLUDED.description,
                    industry_subtitle = EXCLUDED.industry_subtitle
                """
            ),
            {
                "industry_code": industry_code,
                "industry_name": industry_name,
                "description": description,
                "industry_subtitle": description,
            },
        )

    seeds = [
        ('Pharmaceuticals & Biotech', 'pharma_biotech', 'PHM', {'root_causes_inserted': 68}, r"""-- ============================================================================
-- Ally :: Industry seed -- PHARMACEUTICALS & BIOTECH (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 68 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: pharma_biotech
--
-- COUNTS   : 68 root causes, not the usual 66. Two top-up passes added
--            root causes not covered elsewhere (a written-confirmation gap
--            in the regulatory pathway, learning from a real comparable
--            launch, a manufacturing-failure buffer, and regular buyer
--            contract renegotiation). Every row is properly linked and
--            every problem has intervention coverage.
--
-- SCOPE    : this content stays at the business and regulatory-strategy
--            level throughout -- approval pathways, IP, development cost,
--            manufacturing readiness, funding, distribution, compliance
--            operations, patent risk and market defensibility. It contains
--            NO clinical, dosing, formulation-chemistry or medical-practice
--            content of any kind, by design.
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (PHM-001, RC-PHM-014, S0-PHM-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : questions name no specific regulatory agency, approval category,
--            patent term or safety-reporting statute.  These vary by product
--            type and jurisdiction and change, so the content asks the
--            founder what applies to THEM and what has actually been
--            confirmed, rather than naming a rule that will go stale.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (submission delays, manufacturing readiness,
--            milestone funding, distribution, safety reporting) starts at
--            Stage 0->1; customer concentration, patent expiry, manufacturing
--            at scale, post approval compliance, international expansion and
--            post patent defensibility at Stage 1->10+.
-- ============================================================================

WITH z AS (
  SELECT ('[' || array_to_string(array_fill(0, ARRAY[1536]), ',') || ']')::vector AS v
),

-- 1. PROBLEMS -----------------------------------------------------------------
new_problems AS (
  INSERT INTO problems
    (problem_code, problem_name, description, category, subcategory, layer,
     pillar_id, severity_min, severity_max, symptoms, industry_relevance,
     related_problem_ids, embedding)
  SELECT t.problem_code, t.problem_name, t.description, t.category, t.subcategory,
         t.layer, t.pillar_id, t.severity_min, t.severity_max, t.symptoms,
         t.industry_relevance, '[]'::jsonb, z.v
  FROM (VALUES
  ('PHM-001', 'No Idea What Regulatory Path This Actually Needs', 'A drug, device or diagnostic each face completely different approval routes, and which one applies here has not been established.', 'Idea & Validation', 'Pharma Regulatory Path Clarity', 'external', 3, 6, 10, '["No idea which regulatory category this falls into", "Assuming approval will be quick because the idea seems simple", "Timeline built without checking real approval timeframes", "No regulatory consultant or advisor involved yet", "Development started before the pathway was confirmed"]'::jsonb, '["pharma_biotech"]'::jsonb),
  ('PHM-002', 'Underestimating How Much Development Actually Costs', 'Formulation, testing, trials and approval all cost far more than a first estimate typically assumes, and the budget has not been checked against reality.', 'Idea & Validation', 'Pharma Development Cost Reality', 'external', 4, 7, 10, '["Budget based on the idea alone, not the full development path", "Testing and trial costs not researched", "No allowance for repeated attempts or failures", "Timeline to revenue assumed to be short", "No comparison against a similar product real cost"]'::jsonb, '["pharma_biotech"]'::jsonb),
  ('PHM-003', 'Intellectual Property Position Not Established', 'Whether this can be patented, whether it infringes existing patents, and who owns the underlying science have not been checked.', 'Idea & Validation', 'Pharma IP Position', 'external', 3, 6, 10, '["No patent search done on the core idea", "Ownership of underlying research or formulation unclear", "Assuming an idea is protectable without checking", "No plan for filing before public disclosure", "No advice taken on freedom to operate"]'::jsonb, '["pharma_biotech"]'::jsonb),
  ('PHM-004', 'No Realistic View of Who Would Actually Buy or Prescribe This', 'The product assumes doctors, patients, distributors or payers will adopt it without knowing how any of those groups actually decide.', 'Idea & Validation', 'Pharma Market Adoption Clarity', 'external', 2, 5, 9, '["No decision on which buyer group this targets first", "No conversation with a prescriber or purchaser", "Assuming clinical benefit alone drives adoption", "Distribution and payer pathways not considered", "No idea how a similar product reached the market"]'::jsonb, '["pharma_biotech"]'::jsonb),
  ('PHM-005', 'Regulatory Submission Delays Burning Through Runway', 'Queries, resubmissions and review cycles are taking far longer than planned, and cash is running out before approval arrives.', 'Operations & Systems', 'Pharma Submission Delays', 'external', 4, 7, 10, '["Submission queries taking longer to resolve than expected", "Runway calculated on the optimistic timeline only", "No contingency plan for a delayed approval", "Repeated resubmissions consuming cash and time", "No one dedicated to managing the regulatory process"]'::jsonb, '["pharma_biotech"]'::jsonb),
  ('PHM-006', 'Manufacturing and Quality Standards Harder Than Expected', 'Producing at the quality and consistency required for approval and sale is proving far more demanding than early production runs suggested.', 'Operations & Systems', 'Pharma Manufacturing Readiness', 'external', 3, 6, 9, '["Batch to batch consistency not yet reliable", "Quality standards required for approval not yet met", "No qualified manufacturing partner secured", "Scale up revealing problems not seen at small scale", "No plan for the cost of manufacturing at required quality"]'::jsonb, '["pharma_biotech"]'::jsonb),
  ('PHM-007', 'Raising Money Between Every Development Milestone', 'The business needs a new funding round to reach each stage of development, and any gap or delay threatens survival.', 'Financial Management', 'Pharma Milestone Funding Dependency', 'external', 4, 7, 10, '["Cash runs out before the next milestone is reached", "Every raise dependent on hitting the previous milestone", "No buffer between funding rounds", "Investor terms worsening with each successive raise", "No plan if a milestone is delayed or missed"]'::jsonb, '["pharma_biotech"]'::jsonb),
  ('PHM-008', 'Distribution and Supply Chain Not Actually Set Up', 'Getting the product to where it will be used involves cold chain, licensed distributors or hospital procurement that has not been arranged.', 'Operations & Systems', 'Pharma Distribution Readiness', 'external', 3, 6, 9, '["No distributor relationship secured", "Cold chain or storage requirements not planned for", "Hospital or pharmacy procurement process not understood", "Assuming approval automatically means availability", "No plan for getting product to the first real customer"]'::jsonb, '["pharma_biotech"]'::jsonb),
  ('PHM-009', 'Adverse Event and Safety Reporting Not Set Up', 'Once real people are using the product, safety issues must be captured, assessed and reported, and no system for this exists yet.', 'Operations & Systems', 'Pharma Safety Reporting Systems', 'external', 3, 7, 10, '["No system for capturing adverse events", "Reporting timelines and obligations not understood", "No one responsible for safety monitoring", "No process for escalating a serious event", "Assuming safety reporting can be handled informally"]'::jsonb, '["pharma_biotech"]'::jsonb),
  ('PHM-010', 'Revenue Concentrated in a Few Large Buyers', 'A handful of hospital systems, distributors or government programmes account for most sales, so they set terms and their loss would be severe.', 'Sales & Revenue', 'Pharma Customer Concentration', 'external', 4, 7, 10, '["Most revenue from a few large buyers", "Pricing dictated by the dominant purchaser", "No pipeline of smaller or new accounts", "Losing one buyer would threaten the business", "Contract terms set one way by the buyer"]'::jsonb, '["pharma_biotech"]'::jsonb),
  ('PHM-011', 'Patent Cliff and Competitive Entry Risk', 'Protection has a defined expiry, and competitors are preparing to enter the moment it lapses, threatening the core revenue line.', 'Strategy & Planning', 'Pharma Patent Expiry Risk', 'external', 2, 7, 10, '["Patent expiry date approaching with no response plan", "Competitors known to be preparing alternatives", "Revenue heavily dependent on the protected product", "No pipeline of follow on products", "No strategy for life beyond the current patent"]'::jsonb, '["pharma_biotech"]'::jsonb),
  ('PHM-012', 'Scaling Manufacturing While Holding Quality Constant', 'Producing far more volume without any drop in the consistency and quality that approval and buyers depend on is proving difficult.', 'Operations & Systems', 'Pharma Manufacturing at Scale', 'external', 3, 7, 10, '["Quality variation increasing with higher volume", "Second manufacturing site not matching the first", "Supply chain now involving many more inputs and suppliers", "Capacity constraints limiting how much can be sold", "No redundancy if one manufacturing site fails"]'::jsonb, '["pharma_biotech"]'::jsonb),
  ('PHM-013', 'Post Approval Compliance Now a Constant Operation', 'Ongoing safety reporting, manufacturing audits, labelling updates and renewals recur continuously and cannot be handled informally at this size.', 'Operations & Systems', 'Pharma Post Approval Compliance', 'external', 3, 7, 10, '["Compliance obligations tracked from memory", "No single calendar of renewals and audits", "Labelling or documentation updates handled reactively", "Audit findings repeating across cycles", "One person holding all the compliance knowledge"]'::jsonb, '["pharma_biotech"]'::jsonb),
  ('PHM-014', 'International Expansion Means Starting Approval Again', 'Each new country has its own regulatory process, and expansion is far slower and more expensive than assumed.', 'Strategy & Planning', 'Pharma International Expansion', 'external', 2, 6, 10, '["Assuming one approval covers multiple markets", "Each new country requiring its own submission and timeline", "Local partner or distributor requirements not understood", "Cost of multi market expansion underestimated", "No prioritisation of which markets to enter first"]'::jsonb, '["pharma_biotech"]'::jsonb),
  ('PHM-015', 'Nothing Proprietary Left Once Patents and Exclusivity End', 'Beyond the patent itself, nothing has been built that keeps buyers loyal once cheaper alternatives can legally compete.', 'Strategy & Planning', 'Pharma Post Patent Defensibility', 'external', 2, 6, 10, '["No brand loyalty independent of exclusivity", "No proprietary formulation or delivery advantage", "No service or relationship layer beyond the product", "Price expected to be the only competitive factor after expiry", "No plan for what the business becomes after the patent ends"]'::jsonb, '["pharma_biotech"]'::jsonb)
  ) AS t(problem_code, problem_name, description, category, subcategory, layer,
         pillar_id, severity_min, severity_max, symptoms, industry_relevance), z
  RETURNING problem_id, problem_code
),

-- 2. ROOT CAUSES --------------------------------------------------------------
new_root_causes AS (
  INSERT INTO root_causes
    (root_cause_code, root_cause_name, explanation, problem_id, layer,
     root_cause_category, confidence_weight, primary_stage_group,
     industry_relevance, embedding)
  SELECT t.root_cause_code, t.root_cause_name, t.explanation, np.problem_id,
         t.layer, t.root_cause_category, t.confidence_weight,
         t.primary_stage_group, '["pharma_biotech"]'::jsonb, z.v
  FROM (VALUES
  ('RC-PHM-001', 'Regulatory Category Not Established', 'Which approval route applies has not been determined.', 'PHM-001', 'external', 'Knowledge', 0.74, 'Stage 0'),
  ('RC-PHM-002', 'Assuming Approval Will Be Quick', 'Believing a simple sounding idea means a simple approval process.', 'PHM-001', 'external', 'Psychological', 0.71, 'Stage 0'),
  ('RC-PHM-003', 'Timeline Built Without Checking Real Timeframes', 'Plans assume speed that has not been verified against actual cases.', 'PHM-001', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-PHM-004', 'No Regulatory Advisor Involved', 'Nobody with real regulatory expertise has been consulted.', 'PHM-001', 'external', 'Operational', 0.69, 'Stage 0'),
  ('RC-PHM-005', 'Development Started Before Pathway Confirmed', 'Work began without knowing what approval will actually require.', 'PHM-001', 'external', 'Strategic', 0.72, 'Stage 0'),
  ('RC-PHM-006', 'Budget Based on the Idea Alone', 'Costing reflects the concept, not the full development path.', 'PHM-002', 'external', 'Knowledge', 0.73, 'Stage 0'),
  ('RC-PHM-007', 'Testing and Trial Costs Not Researched', 'What testing or trials would actually cost has not been found out.', 'PHM-002', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-PHM-008', 'No Allowance for Repeated Attempts', 'The plan assumes success on the first try.', 'PHM-002', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-PHM-009', 'Timeline to Revenue Assumed Short', 'How long until money comes back has been underestimated.', 'PHM-002', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-PHM-010', 'No Comparison Against a Real Product Cost', 'Nobody has checked what a similar product actually cost to develop.', 'PHM-002', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-PHM-011', 'No Patent Search Done', 'Whether the idea is novel has not been checked against existing patents.', 'PHM-003', 'external', 'Knowledge', 0.73, 'Stage 0'),
  ('RC-PHM-012', 'Ownership of Underlying Research Unclear', 'Who owns the science this is built on has not been established.', 'PHM-003', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-PHM-013', 'Assuming an Idea Is Protectable', 'Believing something is patentable without checking.', 'PHM-003', 'external', 'Psychological', 0.68, 'Stage 0'),
  ('RC-PHM-014', 'No Plan for Filing Before Disclosure', 'Public disclosure could happen before any protection is filed.', 'PHM-003', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-PHM-015', 'No Freedom to Operate Advice Taken', 'Whether this infringes an existing patent has not been checked.', 'PHM-003', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-PHM-016', 'No Decision on Target Buyer Group', 'Whether this targets doctors, patients, distributors or payers first is unresolved.', 'PHM-004', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-PHM-017', 'No Conversation With a Prescriber or Purchaser', 'Nobody who would actually decide to adopt this has been spoken to.', 'PHM-004', 'external', 'Behavioural', 0.70, 'Stage 0'),
  ('RC-PHM-018', 'Assuming Clinical Benefit Alone Drives Adoption', 'Believing that working well is enough to guarantee uptake.', 'PHM-004', 'external', 'Psychological', 0.69, 'Stage 0'),
  ('RC-PHM-019', 'Runway Calculated on Optimistic Timeline Only', 'Cash planning assumed the best case approval date.', 'PHM-005', 'external', 'Strategic', 0.73, 'Stage 0→1'),
  ('RC-PHM-020', 'No Contingency for a Delayed Approval', 'Nothing was set aside for a slower than expected process.', 'PHM-005', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-PHM-021', 'Repeated Resubmissions Consuming Cash and Time', 'Each round of queries and resubmission adds unplanned cost.', 'PHM-005', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-PHM-022', 'No One Dedicated to Managing the Regulatory Process', 'The submission is handled alongside everything else, not as its own job.', 'PHM-005', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-PHM-023', 'Batch to Batch Consistency Not Reliable', 'Output varies between production runs in ways that matter.', 'PHM-006', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-PHM-024', 'Quality Standards Required Not Yet Met', 'What approval or sale actually requires has not been achieved.', 'PHM-006', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-PHM-025', 'No Qualified Manufacturing Partner Secured', 'Nobody capable of producing at the required standard has been engaged.', 'PHM-006', 'external', 'Strategic', 0.71, 'Stage 0→1'),
  ('RC-PHM-026', 'Scale Up Revealing New Problems', 'Issues invisible at small scale appear once volume increases.', 'PHM-006', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-PHM-027', 'No Plan for Cost of Required Manufacturing Quality', 'What it actually costs to manufacture to standard has not been budgeted.', 'PHM-006', 'external', 'Knowledge', 0.69, 'Stage 0→1'),
  ('RC-PHM-028', 'Every Raise Dependent on the Previous Milestone', 'Funding is contingent, so any slip threatens the next round.', 'PHM-007', 'external', 'Strategic', 0.73, 'Stage 0→1'),
  ('RC-PHM-029', 'No Buffer Between Funding Rounds', 'Cash runs out right at the point the next raise must close.', 'PHM-007', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-PHM-030', 'Investor Terms Worsening Each Round', 'Each successive raise costs more equity or worse terms.', 'PHM-007', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-PHM-031', 'No Plan if a Milestone Is Delayed', 'Nothing has been prepared for a slip in the development timeline.', 'PHM-007', 'external', 'Strategic', 0.71, 'Stage 0→1'),
  ('RC-PHM-032', 'No Distributor Relationship Secured', 'Nobody has been lined up to get the product to users.', 'PHM-008', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-PHM-033', 'Cold Chain or Storage Requirements Not Planned', 'Physical handling needs have not been arranged for.', 'PHM-008', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-PHM-034', 'Procurement Process Not Understood', 'How hospitals or pharmacies actually buy has not been studied.', 'PHM-008', 'external', 'Knowledge', 0.70, 'Stage 0→1'),
  ('RC-PHM-035', 'Assuming Approval Means Availability', 'Believing regulatory clearance automatically gets the product to users.', 'PHM-008', 'external', 'Psychological', 0.69, 'Stage 0→1'),
  ('RC-PHM-036', 'No System for Capturing Adverse Events', 'Nothing exists to record safety issues as they occur.', 'PHM-009', 'external', 'Operational', 0.74, 'Stage 0→1'),
  ('RC-PHM-037', 'Reporting Timelines Not Understood', 'How quickly a safety issue must be reported is unknown.', 'PHM-009', 'external', 'Knowledge', 0.73, 'Stage 0→1'),
  ('RC-PHM-038', 'No One Responsible for Safety Monitoring', 'Nobody owns watching for and acting on safety signals.', 'PHM-009', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-PHM-039', 'No Escalation Process for a Serious Event', 'What happens when something serious is found is undefined.', 'PHM-009', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-PHM-040', 'Most Revenue From a Few Large Buyers', 'A handful of purchasers carry most of the business.', 'PHM-010', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-PHM-041', 'Pricing Dictated by the Dominant Purchaser', 'The largest buyer sets what can be charged.', 'PHM-010', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-PHM-042', 'No Pipeline of Smaller or New Accounts', 'Nothing is being built that could replace a lost buyer.', 'PHM-010', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-PHM-043', 'Contract Terms Set One Way by the Buyer', 'Conditions are imposed rather than negotiated.', 'PHM-010', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-PHM-044', 'Patent Expiry Approaching With No Response Plan', 'Nothing has been prepared for the moment protection lapses.', 'PHM-011', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-PHM-045', 'Competitors Known to Be Preparing Alternatives', 'Rivals are visibly getting ready to enter once possible.', 'PHM-011', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-PHM-046', 'Revenue Heavily Dependent on the Protected Product', 'Most income sits behind one expiring protection.', 'PHM-011', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-PHM-047', 'No Pipeline of Follow On Products', 'Nothing new is being developed to replace declining revenue.', 'PHM-011', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-PHM-048', 'Quality Variation Increasing With Volume', 'Consistency degrades as production scales up.', 'PHM-012', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-PHM-049', 'Second Site Not Matching the First', 'A new manufacturing location produces different results.', 'PHM-012', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-PHM-050', 'Supply Chain Now Involving Many More Inputs', 'Growth has multiplied the number of suppliers and dependencies.', 'PHM-012', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-PHM-051', 'No Redundancy if One Site Fails', 'A single manufacturing failure would stop all supply.', 'PHM-012', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-PHM-052', 'Compliance Obligations Tracked From Memory', 'Renewals and audits are not managed through any system.', 'PHM-013', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-PHM-053', 'No Single Compliance Calendar', 'Nothing brings every obligation into one dated place.', 'PHM-013', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-PHM-054', 'Labelling Updates Handled Reactively', 'Documentation changes are made only after a problem surfaces.', 'PHM-013', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-PHM-055', 'Audit Findings Repeating Across Cycles', 'The same issues are raised without being permanently fixed.', 'PHM-013', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-PHM-056', 'One Person Holding All the Compliance Knowledge', 'Nobody else understands the full compliance position.', 'PHM-013', 'external', 'Operational', 0.68, 'Stage 1→10+'),
  ('RC-PHM-057', 'Assuming One Approval Covers Multiple Markets', 'Believing regulatory clearance in one country transfers elsewhere.', 'PHM-014', 'external', 'Knowledge', 0.74, 'Stage 1→10+'),
  ('RC-PHM-058', 'Local Partner Requirements Not Understood', 'What each new market needs from a local partner has not been studied.', 'PHM-014', 'external', 'Knowledge', 0.71, 'Stage 1→10+'),
  ('RC-PHM-059', 'Cost of Multi Market Expansion Underestimated', 'What entering several countries actually costs has been underpriced.', 'PHM-014', 'external', 'Knowledge', 0.70, 'Stage 1→10+'),
  ('RC-PHM-060', 'No Prioritisation of Which Markets to Enter First', 'Expansion targets have not been ranked by attractiveness or ease.', 'PHM-014', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-PHM-061', 'No Brand Loyalty Independent of Exclusivity', 'Buyers stay only because there has been no legal alternative.', 'PHM-015', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-PHM-062', 'No Proprietary Advantage Beyond the Patent', 'Nothing about the formulation or delivery is hard to copy.', 'PHM-015', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-PHM-063', 'No Service Layer Beyond the Product', 'Nothing besides the product itself creates buyer attachment.', 'PHM-015', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-PHM-064', 'No Plan for Life After the Patent', 'Nothing has been decided about what the business becomes once exclusivity ends.', 'PHM-015', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-PHM-065', 'No Idea How a Similar Product Reached the Market', 'Nobody has studied the actual path a comparable product took to adoption.', 'PHM-004', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-PHM-066', 'Assuming Development Started Before Pathway Was Truly Confirmed', 'Work continued on the assumption an informal confirmation was sufficient.', 'PHM-001', 'external', 'Behavioural', 0.65, 'Stage 0'),
  ('RC-PHM-067', 'No Insurance or Buffer Against a Manufacturing Failure', 'Nothing is arranged to cover lost production if a batch fails inspection.', 'PHM-006', 'external', 'Strategic', 0.66, 'Stage 0→1'),
  ('RC-PHM-068', 'No Regular Renegotiation of Buyer Contracts', 'Contract terms are never revisited once signed, even as leverage changes.', 'PHM-010', 'external', 'Operational', 0.67, 'Stage 1→10+')
  ) AS t(root_cause_code, root_cause_name, explanation, problem_code, layer,
         root_cause_category, confidence_weight, primary_stage_group)
  JOIN new_problems np ON np.problem_code = t.problem_code
  CROSS JOIN z
  RETURNING root_cause_id, root_cause_code
),

-- 3. QUESTIONS ----------------------------------------------------------------
new_questions AS (
  INSERT INTO questions
    (question_code, question_text, question_type, category, priority,
     problem_id, root_cause_id, difficulty_level, primary_stage_group,
     industry_relevance, is_distress_tagged, embedding)
  SELECT t.question_code, t.question_text, t.question_type, t.category, t.priority,
         np.problem_id, nr.root_cause_id, t.difficulty_level, t.primary_stage_group,
         '["pharma_biotech"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-PHM-001', 'Do you know which regulatory category your product falls into?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-001', 'RC-PHM-001', 1, 'Stage 0'),
  ('S0-PHM-002', 'Have you checked how long a similar approval has actually taken?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-001', 'RC-PHM-003', 1, 'Stage 0'),
  ('S0-PHM-003', 'Has anyone with real regulatory expertise reviewed your plan?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-001', 'RC-PHM-004', 2, 'Stage 0'),
  ('S0-PHM-004', 'Did you confirm the approval pathway before starting development?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-001', 'RC-PHM-005', 2, 'Stage 0'),
  ('S0-PHM-005', 'Do you believe this will be approved quickly because the idea seems simple?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-001', 'RC-PHM-002', 2, 'Stage 0'),
  ('S0-PHM-006', 'Is your budget based on the full development path, or just the idea?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-002', 'RC-PHM-006', 1, 'Stage 0'),
  ('S0-PHM-007', 'Have you researched what testing or trials would actually cost?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-002', 'RC-PHM-007', 2, 'Stage 0'),
  ('S0-PHM-008', 'Does your plan allow for more than one attempt?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-002', 'RC-PHM-008', 2, 'Stage 0'),
  ('S0-PHM-009', 'Have you compared your budget against what a similar product really cost?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-002', 'RC-PHM-010', 2, 'Stage 0'),
  ('S0-PHM-010', 'Have you searched for existing patents that cover this idea?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-003', 'RC-PHM-011', 1, 'Stage 0'),
  ('S0-PHM-011', 'Do you know who owns the underlying research or formulation?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-003', 'RC-PHM-012', 2, 'Stage 0'),
  ('S0-PHM-012', 'Have you filed anything before disclosing this publicly?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-003', 'RC-PHM-014', 2, 'Stage 0'),
  ('S0-PHM-013', 'Has anyone checked whether this infringes an existing patent?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-003', 'RC-PHM-015', 2, 'Stage 0'),
  ('S0-PHM-014', 'Who is the first buyer group you are targeting, doctors, patients, distributors or payers?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-004', 'RC-PHM-016', 1, 'Stage 0'),
  ('S0-PHM-015', 'Have you spoken to a real prescriber or purchaser about this?', 'open_text', 'Idea & Validation', 'CORE', 'PHM-004', 'RC-PHM-017', 2, 'Stage 0'),
  ('S01-PHM-001', 'Is your runway calculated on the best case approval date only?', 'open_text', 'Financial Management', 'CORE', 'PHM-005', 'RC-PHM-019', 2, 'Stage 0→1'),
  ('S01-PHM-002', 'Do you have a contingency plan if approval is delayed?', 'open_text', 'Strategy & Planning', 'CORE', 'PHM-005', 'RC-PHM-020', 2, 'Stage 0→1'),
  ('S01-PHM-003', 'How many resubmissions have you had, and what did each cost?', 'open_text', 'Financial Management', 'CORE', 'PHM-005', 'RC-PHM-021', 2, 'Stage 0→1'),
  ('S01-PHM-004', 'Is anyone dedicated to managing the regulatory process, or is it a side task?', 'open_text', 'Team & Leadership', 'CORE', 'PHM-005', 'RC-PHM-022', 2, 'Stage 0→1'),
  ('S01-PHM-005', 'Is your production consistent from one batch to the next?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-006', 'RC-PHM-023', 2, 'Stage 0→1'),
  ('S01-PHM-006', 'Have you actually met the quality standard approval or sale requires?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-006', 'RC-PHM-024', 3, 'Stage 0→1'),
  ('S01-PHM-007', 'Do you have a qualified manufacturing partner secured?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-006', 'RC-PHM-025', 2, 'Stage 0→1'),
  ('S01-PHM-008', 'Has scaling up revealed problems you did not see at small scale?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-006', 'RC-PHM-026', 2, 'Stage 0→1'),
  ('S01-PHM-009', 'Have you budgeted what manufacturing to the required quality actually costs?', 'open_text', 'Financial Management', 'CORE', 'PHM-006', 'RC-PHM-027', 3, 'Stage 0→1'),
  ('S01-PHM-010', 'Is your next funding round dependent on hitting a specific milestone?', 'open_text', 'Financial Management', 'CORE', 'PHM-007', 'RC-PHM-028', 2, 'Stage 0→1'),
  ('S01-PHM-011', 'Do you have any cash buffer between funding rounds?', 'open_text', 'Financial Management', 'CORE', 'PHM-007', 'RC-PHM-029', 2, 'Stage 0→1'),
  ('S01-PHM-012', 'Have your investor terms gotten worse with each raise?', 'open_text', 'Financial Management', 'CORE', 'PHM-007', 'RC-PHM-030', 2, 'Stage 0→1'),
  ('S01-PHM-013', 'What happens to the business if a milestone slips?', 'open_text', 'Strategy & Planning', 'CORE', 'PHM-007', 'RC-PHM-031', 3, 'Stage 0→1'),
  ('S01-PHM-014', 'Do you have a distributor relationship in place?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-008', 'RC-PHM-032', 2, 'Stage 0→1'),
  ('S01-PHM-015', 'Have you planned for cold chain or storage requirements?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-008', 'RC-PHM-033', 2, 'Stage 0→1'),
  ('S01-PHM-016', 'Do you understand how hospitals or pharmacies actually procure?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-008', 'RC-PHM-034', 3, 'Stage 0→1'),
  ('S01-PHM-017', 'Are you assuming approval means the product will simply be available?', 'open_text', 'Strategy & Planning', 'CORE', 'PHM-008', 'RC-PHM-035', 2, 'Stage 0→1'),
  ('S01-PHM-018', 'Do you have a system for capturing adverse events?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-009', 'RC-PHM-036', 3, 'Stage 0→1'),
  ('S01-PHM-019', 'Do you know how quickly a safety issue must be reported?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-009', 'RC-PHM-037', 3, 'Stage 0→1'),
  ('S01-PHM-020', 'Is anyone specifically responsible for safety monitoring?', 'open_text', 'Team & Leadership', 'CORE', 'PHM-009', 'RC-PHM-038', 2, 'Stage 0→1'),
  ('S10-PHM-001', 'What share of your revenue comes from your top two or three buyers?', 'open_text', 'Sales & Revenue', 'CORE', 'PHM-010', 'RC-PHM-040', 2, 'Stage 1→10+'),
  ('S10-PHM-002', 'Who sets your price, you or your largest buyer?', 'open_text', 'Sales & Revenue', 'CORE', 'PHM-010', 'RC-PHM-041', 2, 'Stage 1→10+'),
  ('S10-PHM-003', 'If your largest buyer left, how long could you continue?', 'open_text', 'Strategy & Planning', 'CORE', 'PHM-010', 'RC-PHM-042', 3, 'Stage 1→10+'),
  ('S10-PHM-004', 'Who decides your contract terms, you or them?', 'open_text', 'Financial Management', 'CORE', 'PHM-010', 'RC-PHM-043', 2, 'Stage 1→10+'),
  ('S10-PHM-005', 'How much time is left before your key protection expires?', 'open_text', 'Strategy & Planning', 'CORE', 'PHM-011', 'RC-PHM-044', 2, 'Stage 1→10+'),
  ('S10-PHM-006', 'Do you know what competitors are preparing for that date?', 'open_text', 'Strategy & Planning', 'CORE', 'PHM-011', 'RC-PHM-045', 3, 'Stage 1→10+'),
  ('S10-PHM-007', 'What share of your revenue depends on the product losing protection?', 'open_text', 'Financial Management', 'CORE', 'PHM-011', 'RC-PHM-046', 3, 'Stage 1→10+'),
  ('S10-PHM-008', 'Do you have another product in development to follow this one?', 'open_text', 'Strategy & Planning', 'CORE', 'PHM-011', 'RC-PHM-047', 3, 'Stage 1→10+'),
  ('S10-PHM-009', 'Has quality variation increased as you have scaled production?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-012', 'RC-PHM-048', 2, 'Stage 1→10+'),
  ('S10-PHM-010', 'Does a second manufacturing site match the first in output?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-012', 'RC-PHM-049', 3, 'Stage 1→10+'),
  ('S10-PHM-011', 'How many suppliers is your supply chain now depending on?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-012', 'RC-PHM-050', 2, 'Stage 1→10+'),
  ('S10-PHM-012', 'If one manufacturing site failed, could you still supply?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-012', 'RC-PHM-051', 3, 'Stage 1→10+'),
  ('S10-PHM-013', 'Are your compliance obligations tracked on a calendar or in someone head?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-013', 'RC-PHM-052', 2, 'Stage 1→10+'),
  ('S10-PHM-014', 'Can you list every renewal and audit you are due for, with dates?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-013', 'RC-PHM-053', 2, 'Stage 1→10+'),
  ('S10-PHM-015', 'Have the same audit findings come up more than once?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-013', 'RC-PHM-055', 3, 'Stage 1→10+'),
  ('S10-PHM-016', 'If the person who tracks compliance left, what would happen?', 'open_text', 'Team & Leadership', 'CORE', 'PHM-013', 'RC-PHM-056', 3, 'Stage 1→10+'),
  ('S10-PHM-017', 'Are you assuming one approval will work in every market you enter?', 'open_text', 'Strategy & Planning', 'CORE', 'PHM-014', 'RC-PHM-057', 2, 'Stage 1→10+'),
  ('S10-PHM-018', 'Do you know what each new market requires from a local partner?', 'open_text', 'Operations & Systems', 'CORE', 'PHM-014', 'RC-PHM-058', 3, 'Stage 1→10+'),
  ('S10-PHM-019', 'Have you priced what expanding into several countries actually costs?', 'open_text', 'Financial Management', 'CORE', 'PHM-014', 'RC-PHM-059', 3, 'Stage 1→10+'),
  ('S10-PHM-020', 'Have you ranked which markets to enter first, and why?', 'open_text', 'Strategy & Planning', 'CORE', 'PHM-014', 'RC-PHM-060', 2, 'Stage 1→10+'),
  ('S10-PHM-021', 'Would buyers stay if a cheaper alternative became legal tomorrow?', 'open_text', 'Strategy & Planning', 'CORE', 'PHM-015', 'RC-PHM-061', 3, 'Stage 1→10+'),
  ('S10-PHM-022', 'What about your product would be hard for a competitor to copy?', 'open_text', 'Strategy & Planning', 'CORE', 'PHM-015', 'RC-PHM-062', 3, 'Stage 1→10+'),
  ('S10-PHM-023', 'Is there anything besides the product itself that keeps buyers with you?', 'open_text', 'Sales & Revenue', 'CORE', 'PHM-015', 'RC-PHM-063', 2, 'Stage 1→10+'),
  ('S10-PHM-024', 'What does this business become once the patent ends?', 'open_text', 'Strategy & Planning', 'CORE', 'PHM-015', 'RC-PHM-064', 3, 'Stage 1→10+'),
  ('S10-PHM-025', 'Have you started building a pipeline of new markets or products?', 'open_text', 'Strategy & Planning', 'CORE', 'PHM-014', 'RC-PHM-060', 2, 'Stage 1→10+')
  ) AS t(question_code, question_text, question_type, category, priority,
         problem_code, root_cause_code, difficulty_level, primary_stage_group)
  JOIN new_problems np ON np.problem_code = t.problem_code
  JOIN new_root_causes nr ON nr.root_cause_code = t.root_cause_code
  CROSS JOIN z
  RETURNING question_id, question_code
),

-- 4. QUESTION TAG LINKS -------------------------------------------------------
new_tag_links AS (
  INSERT INTO question_tag_mapping (question_id, tag_id)
  SELECT nq.question_id, qt.tag_id
  FROM (VALUES
  ('S0-PHM-001', 'technical-quality'),
  ('S0-PHM-002', 'technical-quality'),
  ('S0-PHM-003', 'technical-quality'),
  ('S0-PHM-004', 'technical-quality'),
  ('S0-PHM-005', 'technical-quality'),
  ('S0-PHM-006', 'willingness-to-pay'),
  ('S0-PHM-007', 'willingness-to-pay'),
  ('S0-PHM-008', 'willingness-to-pay'),
  ('S0-PHM-009', 'willingness-to-pay'),
  ('S0-PHM-010', 'technical-quality'),
  ('S0-PHM-011', 'technical-quality'),
  ('S0-PHM-012', 'technical-quality'),
  ('S0-PHM-013', 'technical-quality'),
  ('S0-PHM-014', 'icp'),
  ('S0-PHM-015', 'icp'),
  ('S01-PHM-001', 'technical-quality'),
  ('S01-PHM-002', 'technical-quality'),
  ('S01-PHM-003', 'technical-quality'),
  ('S01-PHM-004', 'technical-quality'),
  ('S01-PHM-005', 'technical-quality'),
  ('S01-PHM-006', 'technical-quality'),
  ('S01-PHM-007', 'technical-quality'),
  ('S01-PHM-008', 'technical-quality'),
  ('S01-PHM-009', 'technical-quality'),
  ('S01-PHM-010', 'willingness-to-pay'),
  ('S01-PHM-011', 'willingness-to-pay'),
  ('S01-PHM-012', 'willingness-to-pay'),
  ('S01-PHM-013', 'willingness-to-pay'),
  ('S01-PHM-014', 'icp'),
  ('S01-PHM-015', 'icp'),
  ('S01-PHM-016', 'icp'),
  ('S01-PHM-017', 'icp'),
  ('S01-PHM-018', 'technical-quality'),
  ('S01-PHM-019', 'technical-quality'),
  ('S01-PHM-020', 'technical-quality'),
  ('S10-PHM-001', 'willingness-to-pay'),
  ('S10-PHM-002', 'willingness-to-pay'),
  ('S10-PHM-003', 'willingness-to-pay'),
  ('S10-PHM-004', 'willingness-to-pay'),
  ('S10-PHM-005', 'technical-quality'),
  ('S10-PHM-006', 'technical-quality'),
  ('S10-PHM-007', 'technical-quality'),
  ('S10-PHM-008', 'technical-quality'),
  ('S10-PHM-009', 'technical-quality'),
  ('S10-PHM-010', 'technical-quality'),
  ('S10-PHM-011', 'technical-quality'),
  ('S10-PHM-012', 'technical-quality'),
  ('S10-PHM-013', 'technical-quality'),
  ('S10-PHM-014', 'technical-quality'),
  ('S10-PHM-015', 'technical-quality'),
  ('S10-PHM-016', 'technical-quality'),
  ('S10-PHM-017', 'icp'),
  ('S10-PHM-018', 'icp'),
  ('S10-PHM-019', 'icp'),
  ('S10-PHM-020', 'icp'),
  ('S10-PHM-021', 'technical-quality'),
  ('S10-PHM-022', 'technical-quality'),
  ('S10-PHM-023', 'technical-quality'),
  ('S10-PHM-024', 'technical-quality'),
  ('S10-PHM-025', 'icp')
  ) AS t(question_code, tag_name)
  JOIN new_questions nq ON nq.question_code = t.question_code
  JOIN question_tags qt ON qt.tag_name = t.tag_name
  RETURNING question_id
),

-- 5. INTERVENTIONS ------------------------------------------------------------
new_interventions AS (
  INSERT INTO interventions
    (intervention_code, section, problem_id, root_cause_ids, stage_relevance,
     capability_domain, design_principles, immediate_next_steps,
     recommended_frameworks, industry_relevance, secondary_root_cause_ids)
  SELECT t.intervention_code, t.section, np.problem_id, t.root_cause_ids,
         t.stage_relevance, t.capability_domain,
         '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb,
         t.immediate_next_steps, t.recommended_frameworks,
         '["pharma_biotech"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-PHM-001', 'Ideation — Pharma Regulatory Path Clarity', 'PHM-001', '["RC-PHM-001", "RC-PHM-005"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Establish which regulatory category your product falls into.", "Confirm the approval pathway before doing further development.", "Get this in writing from someone qualified."]'::jsonb, '[{"name": "Confirm the Pathway First", "brief": "Establishing the regulatory category before committing to development."}]'::jsonb),
  ('INT-PHM-002', 'Ideation — Pharma Regulatory Path Clarity', 'PHM-001', '["RC-PHM-002", "RC-PHM-003", "RC-PHM-004"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Find real timelines from similar approvals, not assumptions.", "Bring in a regulatory advisor before building further.", "Rebuild your plan around the real timeline."]'::jsonb, '[{"name": "Get Real Timelines and Advice", "brief": "Grounding the plan in actual approval history, not hope."}]'::jsonb),
  ('INT-PHM-003', 'Ideation — Pharma Development Cost Reality', 'PHM-002', '["RC-PHM-006", "RC-PHM-010"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Find the real development cost of a comparable product.", "Rebuild your budget from the full path, not the idea alone.", "Treat the comparison figure as a floor, not a ceiling."]'::jsonb, '[{"name": "Cost From a Real Comparable", "brief": "Anchoring the budget to what similar products actually cost."}]'::jsonb),
  ('INT-PHM-004', 'Ideation — Pharma Development Cost Reality', 'PHM-002', '["RC-PHM-007", "RC-PHM-008", "RC-PHM-009"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Research what testing and trials actually cost at each stage.", "Build in the cost and time of at least one failed attempt.", "Push your revenue timeline out to a realistic date."]'::jsonb, '[{"name": "Budget for Failure and Delay", "brief": "Planning cost and time for setbacks, not just the best case."}]'::jsonb),
  ('INT-PHM-005', 'Ideation — Pharma IP Position', 'PHM-003', '["RC-PHM-011", "RC-PHM-013"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Run a proper patent search on the core idea.", "Do not assume something is protectable without checking.", "Get the result reviewed by someone qualified."]'::jsonb, '[{"name": "Search Before You Assume", "brief": "Checking patentability instead of assuming it."}]'::jsonb),
  ('INT-PHM-006', 'Ideation — Pharma IP Position', 'PHM-003', '["RC-PHM-012", "RC-PHM-014", "RC-PHM-015"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Confirm who owns the underlying research or formulation.", "File for protection before any public disclosure.", "Get a freedom to operate opinion before proceeding."]'::jsonb, '[{"name": "Secure Ownership and Freedom to Operate", "brief": "Confirming ownership, filing in time, and checking against existing patents."}]'::jsonb),
  ('INT-PHM-007', 'Ideation — Pharma Market Adoption Clarity', 'PHM-004', '["RC-PHM-016", "RC-PHM-018"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Choose one buyer group to target first.", "Stop assuming clinical benefit alone will drive adoption.", "Map out what would actually make that group adopt it."]'::jsonb, '[{"name": "Pick a Buyer, Not Just a Benefit", "brief": "Choosing a specific adopter group instead of relying on the product being good."}]'::jsonb),
  ('INT-PHM-008', 'Ideation — Pharma Market Adoption Clarity', 'PHM-004', '["RC-PHM-017"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Talk to a real prescriber or purchaser before going further.", "Ask what would actually make them choose this.", "Adjust the plan around their answer."]'::jsonb, '[{"name": "Talk to the Real Decision Maker", "brief": "Learning from an actual buyer, not assumptions about clinical merit."}]'::jsonb),
  ('INT-PHM-009', 'Validation to Traction — Pharma Submission Delays', 'PHM-005', '["RC-PHM-019", "RC-PHM-020"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Rebuild your runway on a realistic, not optimistic, approval date.", "Build a contingency for delay into the cash plan.", "Review it every time a milestone moves."]'::jsonb, '[{"name": "Plan Runway on Realistic Timing", "brief": "Cash planning built on real timelines, with contingency for delay."}]'::jsonb),
  ('INT-PHM-010', 'Validation to Traction — Pharma Submission Delays', 'PHM-005', '["RC-PHM-021", "RC-PHM-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Give one person clear ownership of the regulatory process.", "Track the cost and time of every query and resubmission.", "Use that record to improve the next submission."]'::jsonb, '[{"name": "Own the Regulatory Process", "brief": "A dedicated owner and a record of what queries actually cost."}]'::jsonb),
  ('INT-PHM-011', 'Validation to Traction — Pharma Manufacturing Readiness', 'PHM-006', '["RC-PHM-023", "RC-PHM-026"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Investigate the cause of batch to batch variation.", "Test at a scale close to what you will actually need.", "Fix issues before they appear at full scale."]'::jsonb, '[{"name": "Test Near Real Scale", "brief": "Finding scale up problems before they become a full scale crisis."}]'::jsonb),
  ('INT-PHM-012', 'Validation to Traction — Pharma Manufacturing Readiness', 'PHM-006', '["RC-PHM-024", "RC-PHM-025", "RC-PHM-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Secure a manufacturing partner qualified to the required standard.", "Confirm you can actually meet the quality bar needed.", "Budget the true cost of manufacturing at that quality."]'::jsonb, '[{"name": "Secure Qualified Manufacturing", "brief": "A capable partner and an honest cost for the quality required."}]'::jsonb),
  ('INT-PHM-013', 'Validation to Traction — Pharma Milestone Funding Dependency', 'PHM-007', '["RC-PHM-028", "RC-PHM-029"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Raise with a buffer beyond the next milestone, not exactly to it.", "Start the next raise before cash is critical.", "Track runway against the realistic timeline, not the fast one."]'::jsonb, '[{"name": "Raise With a Buffer", "brief": "Funding that covers more than just the next milestone."}]'::jsonb),
  ('INT-PHM-014', 'Validation to Traction — Pharma Milestone Funding Dependency', 'PHM-007', '["RC-PHM-030", "RC-PHM-031"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Write a specific plan for what happens if a milestone is delayed.", "Talk to investors early if a slip looks likely.", "Do not let worsening terms go unexamined."]'::jsonb, '[{"name": "Plan for a Missed Milestone", "brief": "A specific response ready before a delay forces a bad deal."}]'::jsonb),
  ('INT-PHM-015', 'Validation to Traction — Pharma Distribution Readiness', 'PHM-008', '["RC-PHM-032", "RC-PHM-035"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Start distributor conversations well before approval.", "Do not assume approval means automatic availability.", "Treat distribution as its own workstream."]'::jsonb, '[{"name": "Start Distribution Early", "brief": "Building the distribution route before approval, not after."}]'::jsonb),
  ('INT-PHM-016', 'Validation to Traction — Pharma Distribution Readiness', 'PHM-008', '["RC-PHM-033", "RC-PHM-034"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Plan cold chain or storage requirements in advance.", "Learn how your target buyers actually procure.", "Build the process around their real purchasing path."]'::jsonb, '[{"name": "Plan the Physical and Procurement Path", "brief": "Understanding storage needs and real buyer procurement in advance."}]'::jsonb),
  ('INT-PHM-017', 'Validation to Traction — Pharma Safety Reporting Systems', 'PHM-009', '["RC-PHM-036", "RC-PHM-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Set up a system for capturing adverse events from day one of real use.", "Name one person responsible for safety monitoring.", "Do not wait for a serious event to build this."]'::jsonb, '[{"name": "Build Safety Reporting Before Launch", "brief": "A capture system and a named owner in place before real world use."}]'::jsonb),
  ('INT-PHM-018', 'Validation to Traction — Pharma Safety Reporting Systems', 'PHM-009', '["RC-PHM-037", "RC-PHM-039"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Confirm exactly how quickly a safety issue must be reported.", "Write a clear escalation process for serious events.", "Test the process before it is needed for real."]'::jsonb, '[{"name": "Know Timelines, Define Escalation", "brief": "Clear reporting timelines and a tested escalation path."}]'::jsonb),
  ('INT-PHM-019', 'Growth to Maturity — Pharma Customer Concentration', 'PHM-010', '["RC-PHM-040", "RC-PHM-042"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Calculate the revenue share of your top three buyers.", "Set a ceiling and build a pipeline of smaller accounts.", "Review the share every year."]'::jsonb, '[{"name": "Cap Buyer Concentration", "brief": "Measuring dependence and building beyond the dominant few."}]'::jsonb),
  ('INT-PHM-020', 'Growth to Maturity — Pharma Customer Concentration', 'PHM-010', '["RC-PHM-041", "RC-PHM-043"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Work out your real margin on the dominant buyer after their terms.", "Identify which terms you accept only because of dependence.", "Renegotiate or diversify away from the worst."]'::jsonb, '[{"name": "Margin After Their Terms", "brief": "Seeing what a dominant buyer really leaves you."}]'::jsonb),
  ('INT-PHM-021', 'Growth to Maturity — Pharma Patent Expiry Risk', 'PHM-011', '["RC-PHM-044", "RC-PHM-046"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Mark the expiry date and work backward from it.", "Model what revenue looks like without that protection.", "Start planning the response years in advance, not months."]'::jsonb, '[{"name": "Plan Backward From Expiry", "brief": "Preparing for the revenue impact years before protection ends."}]'::jsonb),
  ('INT-PHM-022', 'Growth to Maturity — Pharma Patent Expiry Risk', 'PHM-011', '["RC-PHM-045", "RC-PHM-047"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Track what competitors are visibly preparing for that date.", "Build a pipeline of follow on products now.", "Do not wait until expiry to start the next thing."]'::jsonb, '[{"name": "Build the Next Thing Now", "brief": "A follow on pipeline started well before the current patent ends."}]'::jsonb),
  ('INT-PHM-023', 'Growth to Maturity — Pharma Manufacturing at Scale', 'PHM-012', '["RC-PHM-048", "RC-PHM-049"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Investigate the specific cause of quality variation at higher volume.", "Bring a second site to match the first before scaling further.", "Do not scale ahead of proven consistency."]'::jsonb, '[{"name": "Match Quality Before You Scale", "brief": "Proven consistency across sites before adding more volume."}]'::jsonb),
  ('INT-PHM-024', 'Growth to Maturity — Pharma Manufacturing at Scale', 'PHM-012', '["RC-PHM-050", "RC-PHM-051"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Map every supplier your supply chain now depends on.", "Build redundancy so one site or supplier failure does not stop supply.", "Test the redundancy plan before you need it."]'::jsonb, '[{"name": "Build Supply Redundancy", "brief": "Backup capacity so a single failure does not halt the business."}]'::jsonb),
  ('INT-PHM-025', 'Growth to Maturity — Pharma Post Approval Compliance', 'PHM-013', '["RC-PHM-052", "RC-PHM-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Build one calendar covering every renewal, audit and reporting obligation.", "Set reminders well ahead of each date.", "Review it monthly."]'::jsonb, '[{"name": "One Compliance Calendar", "brief": "Every recurring obligation and deadline in one dated place."}]'::jsonb),
  ('INT-PHM-026', 'Growth to Maturity — Pharma Post Approval Compliance', 'PHM-013', '["RC-PHM-054", "RC-PHM-055", "RC-PHM-056"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Update labelling and documentation proactively, not reactively.", "Close audit findings permanently instead of repeating them.", "Train a second person on the whole compliance picture."]'::jsonb, '[{"name": "Fix Permanently, Cross Train", "brief": "Proactive documentation, permanent fixes, and shared compliance knowledge."}]'::jsonb),
  ('INT-PHM-027', 'Growth to Maturity — Pharma International Expansion', 'PHM-014', '["RC-PHM-057", "RC-PHM-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Treat every new market as its own approval process.", "Rank target markets by attractiveness and ease of entry.", "Enter in that order, not all at once."]'::jsonb, '[{"name": "Rank and Sequence Markets", "brief": "Prioritised, sequential expansion instead of assuming one approval travels."}]'::jsonb),
  ('INT-PHM-028', 'Growth to Maturity — Pharma International Expansion', 'PHM-014', '["RC-PHM-058", "RC-PHM-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Research local partner requirements for each target market.", "Price the real cost of multi market expansion before committing.", "Budget for it as its own initiative, not an afterthought."]'::jsonb, '[{"name": "Research Partners, Price It Properly", "brief": "Understanding local requirements and true expansion cost upfront."}]'::jsonb),
  ('INT-PHM-029', 'Growth to Maturity — Pharma Post Patent Defensibility', 'PHM-015', '["RC-PHM-061", "RC-PHM-062"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Identify what could make buyers loyal beyond legal protection.", "Invest in a genuine formulation, delivery or service advantage.", "Start before the patent ends, not after."]'::jsonb, '[{"name": "Build an Advantage Beyond the Patent", "brief": "A real reason to stay loyal once exclusivity is gone."}]'::jsonb),
  ('INT-PHM-030', 'Growth to Maturity — Pharma Post Patent Defensibility', 'PHM-015', '["RC-PHM-063", "RC-PHM-064"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Build a service or relationship layer around the product.", "Decide deliberately what the business becomes after the patent ends.", "Test the plan against a scenario where price is the only lever left."]'::jsonb, '[{"name": "Decide What Comes After", "brief": "A deliberate plan for life beyond the current patent."}]'::jsonb),
  ('INT-PHM-031', 'Ideation — Pharma Regulatory Path Clarity', 'PHM-001', '["RC-PHM-066"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Get pathway confirmation in writing, not an informal understanding.", "Do not proceed on a verbal assurance alone.", "Revisit the confirmation if anything about the product changes."]'::jsonb, '[{"name": "Get Written Confirmation", "brief": "A formal pathway confirmation, not an assumption based on an informal chat."}]'::jsonb),
  ('INT-PHM-032', 'Ideation — Pharma Market Adoption Clarity', 'PHM-004', '["RC-PHM-065"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Study the actual path a comparable product took to market.", "Note what worked and what took longer than expected.", "Use it to set realistic expectations for your own launch."]'::jsonb, '[{"name": "Study a Real Comparable Launch", "brief": "Learning from how a similar product actually reached the market."}]'::jsonb),
  ('INT-PHM-033', 'Validation to Traction — Pharma Manufacturing Readiness', 'PHM-006', '["RC-PHM-067"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Work out what a failed batch or inspection would cost you.", "Arrange a buffer or insurance against that scenario.", "Do not assume every batch will pass."]'::jsonb, '[{"name": "Buffer Against Manufacturing Failure", "brief": "Financial and operational cover for a batch that does not pass."}]'::jsonb),
  ('INT-PHM-034', 'Growth to Maturity — Pharma Customer Concentration', 'PHM-010', '["RC-PHM-068"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Set a fixed schedule to review every major buyer contract.", "Renegotiate as your leverage or their needs change.", "Never let a contract run untouched for years by default."]'::jsonb, '[{"name": "Review Contracts on a Schedule", "brief": "Regular renegotiation instead of static terms that go stale."}]'::jsonb)
  ) AS t(intervention_code, section, problem_code, root_cause_ids, stage_relevance,
         capability_domain, immediate_next_steps, recommended_frameworks)
  JOIN new_problems np ON np.problem_code = t.problem_code
  RETURNING intervention_id
)
SELECT
  (SELECT COUNT(*) FROM new_problems)     AS problems_inserted,      -- expect 15
  (SELECT COUNT(*) FROM new_root_causes)  AS root_causes_inserted,   -- expect 68
  (SELECT COUNT(*) FROM new_questions)    AS questions_inserted,     -- expect 60
  (SELECT COUNT(*) FROM new_tag_links)    AS tag_links_inserted,     -- expect 60
  (SELECT COUNT(*) FROM new_interventions) AS interventions_inserted;-- expect 34

-- ============================================================================
-- After running, the single result row above must read:  15 | 68 | 60 | 60 | 34
-- If any number differs, something did not link -- roll back and check.
-- ============================================================================"""),
        ('Services & Consulting', 'services', 'SVC', {}, r"""-- ============================================================================
-- Ally :: Industry seed -- SERVICES & CONSULTING (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: services
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (SVC-001, RC-SVC-014, S0-SVC-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (founder dependency, delivery standardisation,
--            billing clarity, capacity management, talent retention) starts
--            at Stage 0->1; client concentration, utilisation tracking,
--            quality consistency, senior talent pipeline, defensibility and
--            scale consistency at Stage 1->10+.
-- ============================================================================

WITH z AS (
  SELECT ('[' || array_to_string(array_fill(0, ARRAY[1536]), ',') || ']')::vector AS v
),

-- 1. PROBLEMS -----------------------------------------------------------------
new_problems AS (
  INSERT INTO problems
    (problem_code, problem_name, description, category, subcategory, layer,
     pillar_id, severity_min, severity_max, symptoms, industry_relevance,
     related_problem_ids, embedding)
  SELECT t.problem_code, t.problem_name, t.description, t.category, t.subcategory,
         t.layer, t.pillar_id, t.severity_min, t.severity_max, t.symptoms,
         t.industry_relevance, '[]'::jsonb, z.v
  FROM (VALUES
  ('SVC-001', 'No Clear Service or Client Type Chosen', 'The business offers to help with almost anything for almost anyone, so nothing about the practice is distinctive or repeatable.', 'Idea & Validation', 'Services Practice Clarity', 'external', 2, 4, 8, '["Willing to take on any type of client work", "No specific industry or problem specialised in", "Scope described differently for every client", "No conversation with a real potential client", "Services list grows with every enquiry, not by design"]'::jsonb, '["services"]'::jsonb),
  ('SVC-002', 'No Idea What It Actually Costs to Deliver an Engagement', 'Hours, tools, overhead and rework are not tracked, so nobody knows if a project is actually profitable once delivered.', 'Idea & Validation', 'Services Cost to Deliver', 'external', 4, 5, 9, '["Fee set without knowing hours required", "Overhead not loaded into project cost", "Rework and revisions not counted as cost", "Price set by asking what others charge", "No idea which past projects were actually profitable"]'::jsonb, '["services"]'::jsonb),
  ('SVC-003', 'Scope and Deliverables Not Defined Before Starting', 'Engagements begin without a written scope, so what is included keeps expanding after the work has already started.', 'Idea & Validation', 'Services Scope Definition', 'external', 3, 5, 9, '["No written scope of work before starting", "Deliverables described vaguely or verbally only", "No process for handling requests outside scope", "Client expectations set informally in conversation", "Scope creep discovered only when the budget runs out"]'::jsonb, '["services"]'::jsonb),
  ('SVC-004', 'No Realistic View of How a Client Actually Buys This', 'The offer assumes a client will simply recognise the value and pay, without knowing who actually approves spend or how the decision gets made.', 'Idea & Validation', 'Services Buyer Clarity', 'external', 2, 5, 9, '["No decision on who the economic buyer actually is", "No conversation with someone who has bought similar services", "Assuming expertise alone will close the sale", "No idea how long buying decisions typically take", "Pricing model chosen without checking what buyers expect"]'::jsonb, '["services"]'::jsonb),
  ('SVC-005', 'Revenue Stops the Moment the Founder Stops Working', 'Every engagement runs through the founder personally, so income is capped by their hours and stops entirely if they cannot work.', 'Sales & Revenue', 'Services Founder Dependency', 'external', 5, 6, 9, '["Founder personally delivers every engagement", "No one else billable to clients yet", "Revenue directly tied to founder hours", "New clients turned away for lack of capacity", "No plan for income if the founder is unavailable"]'::jsonb, '["services"]'::jsonb),
  ('SVC-006', 'Every Client Engagement Run From Scratch', 'Each project is delivered as a bespoke build, so nothing from one engagement carries over to speed up the next.', 'Operations & Systems', 'Services Delivery Standardisation', 'external', 3, 5, 9, '["No templates or reusable frameworks across clients", "Each engagement designed from a blank page", "Time spent rebuilding similar deliverables repeatedly", "No documented methodology to hand to a new hire", "Delivery time not shrinking as experience grows"]'::jsonb, '["services"]'::jsonb),
  ('SVC-007', 'Invoices Disputed or Delayed Because Value Was Never Agreed', 'Clients push back on bills because what counted as done, and what it was worth, was never pinned down before the work happened.', 'Financial Management', 'Services Billing Clarity', 'external', 4, 6, 9, '["Invoices regularly questioned or delayed", "No agreement on what done actually means", "Client and provider disagree on value delivered", "Payment terms not enforced consistently", "Collections taking longer than the engagement itself"]'::jsonb, '["services"]'::jsonb),
  ('SVC-008', 'No System for Managing Multiple Engagements at Once', 'As client count grows, work is tracked informally, and priorities, deadlines and deliverables start slipping between projects.', 'Operations & Systems', 'Services Capacity Management', 'external', 3, 6, 9, '["No central view of what is due for which client", "Deadlines slipping as client count grows", "Team unsure what to prioritise on a given day", "Capacity commitments made without checking availability", "Overpromising because there is no true view of workload"]'::jsonb, '["services"]'::jsonb),
  ('SVC-009', 'Senior Talent Leaving Takes Client Relationships With Them', 'Client trust sits with the individual consultant, so when a senior person leaves, the client relationship is at real risk of leaving too.', 'Team & Leadership', 'Services Talent Retention', 'external', 4, 6, 9, '["Client relationships tied to a specific consultant", "No agreement on client ownership if someone leaves", "Departures followed by client attrition", "No second person introduced into key relationships", "Knowledge of the client relationship undocumented"]'::jsonb, '["services"]'::jsonb),
  ('SVC-010', 'Revenue Concentrated in a Few Large Clients', 'A handful of clients account for most billing, so they set the terms and their departure would be severe.', 'Sales & Revenue', 'Services Client Concentration', 'external', 4, 7, 10, '["Most revenue from a few clients", "Rates pushed down by the largest client", "No pipeline of replacement clients", "Losing one client would threaten the business", "Scope and priorities set by one account"]'::jsonb, '["services"]'::jsonb),
  ('SVC-011', 'Utilisation and Margin Not Actually Tracked', 'As the team grows, nobody can say which consultants or engagements are actually profitable, so pricing and staffing decisions are made blind.', 'Financial Management', 'Services Utilisation Tracking', 'external', 4, 7, 10, '["Utilisation rate not measured per consultant", "Margin per engagement not calculated", "Staffing decisions made without profitability data", "Some clients quietly unprofitable for years", "No target utilisation rate set"]'::jsonb, '["services"]'::jsonb),
  ('SVC-012', 'Quality Varies Depending on Which Team Member Delivers', 'Client experience and output quality differ noticeably by consultant, and nothing systematically catches or corrects the gap.', 'Operations & Systems', 'Services Quality Consistency', 'external', 3, 6, 9, '["Client feedback varying widely by consultant", "No standard quality review before delivery", "New hires producing inconsistent output", "No feedback loop from client to delivery team", "Reputation resting on a few strong individuals"]'::jsonb, '["services"]'::jsonb),
  ('SVC-013', 'Recruiting and Retaining Senior Consultants Is a Constant Struggle', 'Experienced consultants are expensive, hard to find, and often leave to start their own practice using relationships built here.', 'Team & Leadership', 'Services Senior Talent Pipeline', 'external', 4, 7, 10, '["Senior hires expensive and hard to find", "No structured path from junior to senior", "Departures often starting a competing practice", "No non compete or client protection in place", "Compensation not competitive enough to retain seniors"]'::jsonb, '["services"]'::jsonb),
  ('SVC-014', 'Nothing Differentiates This Firm From Any Other Consultancy', 'Clients can switch to a similar firm at similar cost with little friction, because nothing proprietary has been built here.', 'Strategy & Planning', 'Services Defensibility', 'external', 2, 6, 10, '["Methodology easily replicated by competitors", "Pitches won mainly on relationship or price", "No proprietary framework, tool or data asset", "Clients leaving for marginal price differences", "No compounding advantage from serving more clients"]'::jsonb, '["services"]'::jsonb),
  ('SVC-015', 'Scaling Delivery Quality Across a Growing Team Is Breaking Down', 'What worked when the founder and a few seniors delivered everything cannot be maintained as headcount grows past what anyone can personally oversee.', 'Operations & Systems', 'Services Scale Consistency', 'external', 3, 7, 10, '["Oversight capacity not scaling with headcount", "New consultants ramping up slower than the business needs", "No layer of management between founder and delivery staff", "Client complaints increasing as the team grows", "No defined career or accountability structure at scale"]'::jsonb, '["services"]'::jsonb)
  ) AS t(problem_code, problem_name, description, category, subcategory, layer,
         pillar_id, severity_min, severity_max, symptoms, industry_relevance), z
  RETURNING problem_id, problem_code
),

-- 2. ROOT CAUSES --------------------------------------------------------------
new_root_causes AS (
  INSERT INTO root_causes
    (root_cause_code, root_cause_name, explanation, problem_id, layer,
     root_cause_category, confidence_weight, primary_stage_group,
     industry_relevance, embedding)
  SELECT t.root_cause_code, t.root_cause_name, t.explanation, np.problem_id,
         t.layer, t.root_cause_category, t.confidence_weight,
         t.primary_stage_group, '["services"]'::jsonb, z.v
  FROM (VALUES
  ('RC-SVC-001', 'Willing to Take on Any Type of Client Work', 'No focus exists on a specific problem or industry.', 'SVC-001', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-SVC-002', 'No Specific Industry or Problem Specialised In', 'Nothing distinguishes what this practice is actually known for.', 'SVC-001', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-SVC-003', 'Scope Described Differently Every Time', 'Each client hears a different version of what is offered.', 'SVC-001', 'external', 'Behavioural', 0.68, 'Stage 0'),
  ('RC-SVC-004', 'No Conversation With a Real Potential Client', 'Nobody who would actually hire has been spoken to.', 'SVC-001', 'external', 'Behavioural', 0.66, 'Stage 0'),
  ('RC-SVC-005', 'Services List Grows With Every Enquiry', 'The offer expands reactively rather than by deliberate choice.', 'SVC-001', 'external', 'Behavioural', 0.67, 'Stage 0'),
  ('RC-SVC-006', 'Fee Set Without Knowing Hours Required', 'Pricing does not reflect the actual time an engagement takes.', 'SVC-002', 'external', 'Knowledge', 0.73, 'Stage 0'),
  ('RC-SVC-007', 'Overhead Not Loaded Into Project Cost', 'Office, tools and admin costs are missing from project pricing.', 'SVC-002', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-SVC-008', 'Rework Not Counted as Cost', 'Revisions and corrections are treated as free.', 'SVC-002', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-SVC-009', 'Price Set by Asking What Others Charge', 'Fees copy competitors without knowing own true cost.', 'SVC-002', 'external', 'Behavioural', 0.67, 'Stage 0'),
  ('RC-SVC-010', 'No Idea Which Projects Were Actually Profitable', 'Nobody has gone back and checked project profitability after delivery.', 'SVC-002', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-SVC-011', 'No Written Scope Before Starting', 'Work begins without an agreed, documented scope.', 'SVC-003', 'external', 'Operational', 0.73, 'Stage 0'),
  ('RC-SVC-012', 'Deliverables Described Vaguely or Verbally', 'What will actually be delivered is not written down clearly.', 'SVC-003', 'external', 'Operational', 0.71, 'Stage 0'),
  ('RC-SVC-013', 'No Process for Out of Scope Requests', 'Nothing defines how a request beyond the original scope is handled.', 'SVC-003', 'external', 'Operational', 0.70, 'Stage 0'),
  ('RC-SVC-014', 'Client Expectations Set Informally', 'What the client expects comes from conversation, not a document.', 'SVC-003', 'external', 'Behavioural', 0.68, 'Stage 0'),
  ('RC-SVC-015', 'No Decision on the Economic Buyer', 'Who actually approves spend has not been identified.', 'SVC-004', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-SVC-016', 'No Conversation With a Past Buyer', 'Nobody who has bought a similar service has been asked how they decided.', 'SVC-004', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-SVC-017', 'Assuming Expertise Alone Closes the Sale', 'Believing being good at the work is enough to win business.', 'SVC-004', 'external', 'Psychological', 0.68, 'Stage 0'),
  ('RC-SVC-018', 'No Idea How Long Buying Decisions Take', 'How long a client actually takes to decide has not been found out.', 'SVC-004', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-SVC-019', 'Founder Personally Delivers Every Engagement', 'No engagement runs without the founder directly doing the work.', 'SVC-005', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-SVC-020', 'No One Else Billable to Clients', 'Nobody besides the founder generates billable revenue.', 'SVC-005', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-SVC-021', 'New Clients Turned Away for Lack of Capacity', 'Growth is limited by time, not by demand.', 'SVC-005', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-SVC-022', 'No Plan for Income if Founder Is Unavailable', 'Nothing has been prepared for the founder being unable to work.', 'SVC-005', 'external', 'Strategic', 0.69, 'Stage 0→1'),
  ('RC-SVC-023', 'No Templates or Reusable Frameworks', 'Each engagement starts with nothing carried over from the last.', 'SVC-006', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-SVC-024', 'Each Engagement Designed From a Blank Page', 'Delivery approach is invented fresh every time.', 'SVC-006', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-SVC-025', 'No Documented Methodology', 'How the work is actually done exists only in people heads.', 'SVC-006', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-SVC-026', 'Delivery Time Not Shrinking With Experience', 'Efficiency gains from experience are not being captured.', 'SVC-006', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-SVC-027', 'No Agreement on What Done Means', 'Completion criteria were never defined before starting.', 'SVC-007', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-SVC-028', 'Client and Provider Disagree on Value Delivered', 'What the work was worth is a source of dispute after the fact.', 'SVC-007', 'external', 'Behavioural', 0.71, 'Stage 0→1'),
  ('RC-SVC-029', 'Payment Terms Not Enforced Consistently', 'Late payment is tolerated differently client to client.', 'SVC-007', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-SVC-030', 'Collections Taking Longer Than the Engagement', 'Getting paid takes more effort than doing the work.', 'SVC-007', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-SVC-031', 'No Central View of What Is Due for Which Client', 'Deadlines and deliverables are tracked informally or not at all.', 'SVC-008', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-SVC-032', 'Team Unsure What to Prioritise', 'Nobody has a clear view of what matters most today.', 'SVC-008', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-SVC-033', 'Commitments Made Without Checking Availability', 'New work is promised without confirming the team has capacity.', 'SVC-008', 'external', 'Behavioural', 0.70, 'Stage 0→1'),
  ('RC-SVC-034', 'Overpromising From No True Workload View', 'Sales commitments outpace what delivery can actually support.', 'SVC-008', 'external', 'Strategic', 0.69, 'Stage 0→1'),
  ('RC-SVC-035', 'Client Relationships Tied to a Specific Consultant', 'Trust sits with the individual, not the firm.', 'SVC-009', 'external', 'Strategic', 0.73, 'Stage 0→1'),
  ('RC-SVC-036', 'No Agreement on Client Ownership on Exit', 'Nothing sets out what happens to a relationship when someone leaves.', 'SVC-009', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-SVC-037', 'No Second Person in Key Relationships', 'Only one person at the firm actually knows the client well.', 'SVC-009', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-SVC-038', 'Client Relationship Knowledge Undocumented', 'What matters to the client exists only in one person memory.', 'SVC-009', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-SVC-039', 'Most Revenue From a Few Clients', 'A handful of accounts carry most of the billing.', 'SVC-010', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-SVC-040', 'Rates Pushed Down by the Largest Client', 'The dominant client dictates what can be charged.', 'SVC-010', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-SVC-041', 'No Pipeline of Replacement Clients', 'Nothing is being built that could replace a lost account.', 'SVC-010', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-SVC-042', 'Scope and Priorities Set by One Account', 'The dominant client shapes the firm agenda, not the firm itself.', 'SVC-010', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-SVC-043', 'Utilisation Rate Not Measured Per Consultant', 'Nobody tracks how much of each consultant time is billable.', 'SVC-011', 'external', 'Knowledge', 0.73, 'Stage 1→10+'),
  ('RC-SVC-044', 'Margin Per Engagement Not Calculated', 'Profitability by project is unknown.', 'SVC-011', 'external', 'Knowledge', 0.72, 'Stage 1→10+'),
  ('RC-SVC-045', 'Staffing Decisions Made Without Profitability Data', 'Who works on what is decided blind to what actually makes money.', 'SVC-011', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-SVC-046', 'Some Clients Quietly Unprofitable for Years', 'Loss making accounts persist because nobody checked the numbers.', 'SVC-011', 'external', 'Knowledge', 0.71, 'Stage 1→10+'),
  ('RC-SVC-047', 'Client Feedback Varying Widely by Consultant', 'Experience quality depends heavily on who is assigned.', 'SVC-012', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-SVC-048', 'No Standard Quality Review Before Delivery', 'Work goes to the client without a consistent check.', 'SVC-012', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-SVC-049', 'No Feedback Loop From Client to Delivery Team', 'Client input does not reliably reach the people doing the work.', 'SVC-012', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-SVC-050', 'Reputation Resting on a Few Strong Individuals', 'The firm brand depends on specific people, not a system.', 'SVC-012', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-SVC-051', 'No Structured Path From Junior to Senior', 'Nothing develops the next generation of senior talent internally.', 'SVC-013', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-SVC-052', 'Departures Often Starting a Competing Practice', 'Leavers frequently become direct competitors using firm relationships.', 'SVC-013', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-SVC-053', 'No Client Protection on Exit', 'Nothing in place prevents a departing consultant from taking clients.', 'SVC-013', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-SVC-054', 'Compensation Not Competitive Enough', 'Pay is not enough to retain the seniors who are hardest to replace.', 'SVC-013', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-SVC-055', 'Methodology Easily Replicated', 'What is done here can be copied by a competitor without much effort.', 'SVC-014', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-SVC-056', 'Pitches Won Mainly on Relationship or Price', 'Nothing structural differentiates the firm in a pitch.', 'SVC-014', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-SVC-057', 'No Proprietary Framework, Tool or Data Asset', 'Nothing owned makes the firm harder to replace.', 'SVC-014', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-SVC-058', 'No Compounding Advantage From More Clients', 'Serving more clients does not make the firm better at serving the next one.', 'SVC-014', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-SVC-059', 'Oversight Capacity Not Scaling With Headcount', 'Nobody has enough time to review the growing volume of work.', 'SVC-015', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-SVC-060', 'No Management Layer Between Founder and Delivery Staff', 'Every issue routes straight to the founder with nothing in between.', 'SVC-015', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-SVC-061', 'New Consultants Ramping Up Too Slowly', 'Onboarding does not get people productive fast enough for the pace of growth.', 'SVC-015', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-SVC-062', 'No Defined Accountability Structure at Scale', 'Nobody owns quality or outcomes at a team level as headcount grows.', 'SVC-015', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-SVC-063', 'No Idea What Buyers Expect on Pricing Model', 'Whether buyers expect hourly, fixed fee or retainer pricing has not been checked.', 'SVC-004', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-SVC-064', 'No Regular Review of Scope Against Actual Hours', 'Nobody checks whether delivered scope still matches what was originally priced.', 'SVC-003', 'external', 'Operational', 0.66, 'Stage 0'),
  ('RC-SVC-065', 'No Cross Selling Between Engagements', 'Opportunities to expand work with an existing client are not systematically pursued.', 'SVC-008', 'external', 'Operational', 0.66, 'Stage 0→1'),
  ('RC-SVC-066', 'No Regular Review of Which Clients to Prioritise', 'Nobody periodically reassesses which clients deserve the most attention.', 'SVC-010', 'external', 'Operational', 0.66, 'Stage 1→10+')
  ) AS t(root_cause_code, root_cause_name, explanation, problem_code, layer,
         root_cause_category, confidence_weight, primary_stage_group)
  JOIN new_problems np ON np.problem_code = t.problem_code
  CROSS JOIN z
  RETURNING root_cause_id, root_cause_code
),

-- 3. QUESTIONS ----------------------------------------------------------------
new_questions AS (
  INSERT INTO questions
    (question_code, question_text, question_type, category, priority,
     problem_id, root_cause_id, difficulty_level, primary_stage_group,
     industry_relevance, is_distress_tagged, embedding)
  SELECT t.question_code, t.question_text, t.question_type, t.category, t.priority,
         np.problem_id, nr.root_cause_id, t.difficulty_level, t.primary_stage_group,
         '["services"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-SVC-001', 'Will you take on any type of client work, or have you specialised?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-001', 'RC-SVC-001', 1, 'Stage 0'),
  ('S0-SVC-002', 'What specific industry or problem are you known for?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-001', 'RC-SVC-002', 1, 'Stage 0'),
  ('S0-SVC-003', 'Do you describe your services the same way every time?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-001', 'RC-SVC-003', 2, 'Stage 0'),
  ('S0-SVC-004', 'Have you talked to a real potential client who would actually hire you?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-001', 'RC-SVC-004', 2, 'Stage 0'),
  ('S0-SVC-005', 'Has your service list grown by design, or by reacting to whatever comes in?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-001', 'RC-SVC-005', 2, 'Stage 0'),
  ('S0-SVC-006', 'Do you know how many hours an engagement actually takes?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-002', 'RC-SVC-006', 1, 'Stage 0'),
  ('S0-SVC-007', 'Have you loaded overhead into your project pricing?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-002', 'RC-SVC-007', 2, 'Stage 0'),
  ('S0-SVC-008', 'Do you count revisions and rework as a cost?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-002', 'RC-SVC-008', 2, 'Stage 0'),
  ('S0-SVC-009', 'Did you set your fee from your own cost or from competitors?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-002', 'RC-SVC-009', 2, 'Stage 0'),
  ('S0-SVC-010', 'Do you know which past projects were actually profitable?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-002', 'RC-SVC-010', 2, 'Stage 0'),
  ('S0-SVC-011', 'Do you have a written scope before starting work?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-003', 'RC-SVC-011', 1, 'Stage 0'),
  ('S0-SVC-012', 'Are your deliverables written down clearly, or described verbally?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-003', 'RC-SVC-012', 2, 'Stage 0'),
  ('S0-SVC-013', 'What happens when a client asks for something outside the original scope?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-003', 'RC-SVC-013', 2, 'Stage 0'),
  ('S0-SVC-014', 'Who actually approves the spend for this kind of service at your target client?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-004', 'RC-SVC-015', 1, 'Stage 0'),
  ('S0-SVC-015', 'Have you talked to someone who has bought a similar service about how they decided?', 'open_text', 'Idea & Validation', 'CORE', 'SVC-004', 'RC-SVC-016', 2, 'Stage 0'),
  ('S01-SVC-001', 'How many engagements are running right now without you personally delivering them?', 'open_text', 'Team & Leadership', 'CORE', 'SVC-005', 'RC-SVC-019', 2, 'Stage 0→1'),
  ('S01-SVC-002', 'Is anyone besides you billable to clients?', 'open_text', 'Team & Leadership', 'CORE', 'SVC-005', 'RC-SVC-020', 2, 'Stage 0→1'),
  ('S01-SVC-003', 'Have you turned away a client because you had no capacity?', 'open_text', 'Sales & Revenue', 'CORE', 'SVC-005', 'RC-SVC-021', 2, 'Stage 0→1'),
  ('S01-SVC-004', 'What happens to revenue if you cannot work for a month?', 'open_text', 'Strategy & Planning', 'CORE', 'SVC-005', 'RC-SVC-022', 3, 'Stage 0→1'),
  ('S01-SVC-005', 'Do you have templates or frameworks you reuse across engagements?', 'open_text', 'Operations & Systems', 'CORE', 'SVC-006', 'RC-SVC-023', 2, 'Stage 0→1'),
  ('S01-SVC-006', 'Does every engagement start from a blank page?', 'open_text', 'Operations & Systems', 'CORE', 'SVC-006', 'RC-SVC-024', 2, 'Stage 0→1'),
  ('S01-SVC-007', 'Is your delivery method written down anywhere a new hire could learn from?', 'open_text', 'Operations & Systems', 'CORE', 'SVC-006', 'RC-SVC-025', 2, 'Stage 0→1'),
  ('S01-SVC-008', 'Is delivery getting faster as you gain experience, or staying the same?', 'open_text', 'Operations & Systems', 'CORE', 'SVC-006', 'RC-SVC-026', 2, 'Stage 0→1'),
  ('S01-SVC-009', 'Was completion criteria agreed with the client before starting?', 'open_text', 'Financial Management', 'CORE', 'SVC-007', 'RC-SVC-027', 2, 'Stage 0→1'),
  ('S01-SVC-010', 'Do clients ever push back on what an invoice is for?', 'open_text', 'Financial Management', 'CORE', 'SVC-007', 'RC-SVC-028', 2, 'Stage 0→1'),
  ('S01-SVC-011', 'Are your payment terms enforced consistently across clients?', 'open_text', 'Financial Management', 'CORE', 'SVC-007', 'RC-SVC-029', 2, 'Stage 0→1'),
  ('S01-SVC-012', 'How long does collections usually take compared to the engagement itself?', 'open_text', 'Financial Management', 'CORE', 'SVC-007', 'RC-SVC-030', 3, 'Stage 0→1'),
  ('S01-SVC-013', 'Can you see everything due across every client in one place?', 'open_text', 'Operations & Systems', 'CORE', 'SVC-008', 'RC-SVC-031', 2, 'Stage 0→1'),
  ('S01-SVC-014', 'Does your team know what to prioritise on a given day?', 'open_text', 'Team & Leadership', 'CORE', 'SVC-008', 'RC-SVC-032', 2, 'Stage 0→1'),
  ('S01-SVC-015', 'Do you check team availability before committing to new work?', 'open_text', 'Operations & Systems', 'CORE', 'SVC-008', 'RC-SVC-033', 2, 'Stage 0→1'),
  ('S01-SVC-016', 'Have you overpromised delivery because you did not have a true view of workload?', 'open_text', 'Strategy & Planning', 'CORE', 'SVC-008', 'RC-SVC-034', 3, 'Stage 0→1'),
  ('S01-SVC-017', 'Are your client relationships tied to a specific consultant or to the firm?', 'open_text', 'Sales & Revenue', 'CORE', 'SVC-009', 'RC-SVC-035', 2, 'Stage 0→1'),
  ('S01-SVC-018', 'Is there an agreement covering what happens to a client relationship if a consultant leaves?', 'open_text', 'Team & Leadership', 'CORE', 'SVC-009', 'RC-SVC-036', 3, 'Stage 0→1'),
  ('S01-SVC-019', 'Is there a second person who knows each key client well?', 'open_text', 'Team & Leadership', 'CORE', 'SVC-009', 'RC-SVC-037', 2, 'Stage 0→1'),
  ('S01-SVC-020', 'Is what matters to each client written down anywhere?', 'open_text', 'Operations & Systems', 'CORE', 'SVC-009', 'RC-SVC-038', 2, 'Stage 0→1'),
  ('S10-SVC-001', 'What share of your revenue comes from your top two or three clients?', 'open_text', 'Sales & Revenue', 'CORE', 'SVC-010', 'RC-SVC-039', 2, 'Stage 1→10+'),
  ('S10-SVC-002', 'Who sets your rates, you or your biggest client?', 'open_text', 'Sales & Revenue', 'CORE', 'SVC-010', 'RC-SVC-040', 2, 'Stage 1→10+'),
  ('S10-SVC-003', 'If your largest client left, how long could you continue?', 'open_text', 'Strategy & Planning', 'CORE', 'SVC-010', 'RC-SVC-041', 3, 'Stage 1→10+'),
  ('S10-SVC-004', 'Is your firm agenda being set by one dominant account?', 'open_text', 'Strategy & Planning', 'CORE', 'SVC-010', 'RC-SVC-042', 3, 'Stage 1→10+'),
  ('S10-SVC-005', 'Do you track utilisation rate for each consultant?', 'open_text', 'Financial Management', 'CORE', 'SVC-011', 'RC-SVC-043', 2, 'Stage 1→10+'),
  ('S10-SVC-006', 'Do you know the margin on each engagement?', 'open_text', 'Financial Management', 'CORE', 'SVC-011', 'RC-SVC-044', 3, 'Stage 1→10+'),
  ('S10-SVC-007', 'Are staffing decisions made with or without profitability data?', 'open_text', 'Team & Leadership', 'CORE', 'SVC-011', 'RC-SVC-045', 3, 'Stage 1→10+'),
  ('S10-SVC-008', 'Could a client be unprofitable and you would not know?', 'open_text', 'Financial Management', 'CORE', 'SVC-011', 'RC-SVC-046', 3, 'Stage 1→10+'),
  ('S10-SVC-009', 'Does client feedback vary a lot depending on who delivered the work?', 'open_text', 'Operations & Systems', 'CORE', 'SVC-012', 'RC-SVC-047', 2, 'Stage 1→10+'),
  ('S10-SVC-010', 'Is there a quality review before work goes to the client?', 'open_text', 'Operations & Systems', 'CORE', 'SVC-012', 'RC-SVC-048', 2, 'Stage 1→10+'),
  ('S10-SVC-011', 'Does client feedback reliably reach the delivery team?', 'open_text', 'Operations & Systems', 'CORE', 'SVC-012', 'RC-SVC-049', 3, 'Stage 1→10+'),
  ('S10-SVC-012', 'Does your reputation rest on a few specific people?', 'open_text', 'Strategy & Planning', 'CORE', 'SVC-012', 'RC-SVC-050', 3, 'Stage 1→10+'),
  ('S10-SVC-013', 'Is there a clear path from junior to senior consultant?', 'open_text', 'Team & Leadership', 'CORE', 'SVC-013', 'RC-SVC-051', 2, 'Stage 1→10+'),
  ('S10-SVC-014', 'Have departures ever turned into a competing practice?', 'open_text', 'Team & Leadership', 'CORE', 'SVC-013', 'RC-SVC-052', 3, 'Stage 1→10+'),
  ('S10-SVC-015', 'Is there anything protecting client relationships if a consultant leaves?', 'open_text', 'Team & Leadership', 'CORE', 'SVC-013', 'RC-SVC-053', 3, 'Stage 1→10+'),
  ('S10-SVC-016', 'Is your compensation competitive enough to retain your best people?', 'open_text', 'Team & Leadership', 'CORE', 'SVC-013', 'RC-SVC-054', 2, 'Stage 1→10+'),
  ('S10-SVC-017', 'How easily could a competitor copy your methodology?', 'open_text', 'Strategy & Planning', 'CORE', 'SVC-014', 'RC-SVC-055', 3, 'Stage 1→10+'),
  ('S10-SVC-018', 'Do you win pitches mainly on relationship or price?', 'open_text', 'Sales & Revenue', 'CORE', 'SVC-014', 'RC-SVC-056', 2, 'Stage 1→10+'),
  ('S10-SVC-019', 'Do you own any framework, tool or data asset a competitor does not have?', 'open_text', 'Strategy & Planning', 'CORE', 'SVC-014', 'RC-SVC-057', 3, 'Stage 1→10+'),
  ('S10-SVC-020', 'Does serving more clients actually make you better at serving the next one?', 'open_text', 'Strategy & Planning', 'CORE', 'SVC-014', 'RC-SVC-058', 3, 'Stage 1→10+'),
  ('S10-SVC-026', 'Can anyone still review the quality of every engagement as headcount grows?', 'open_text', 'Operations & Systems', 'CORE', 'SVC-015', 'RC-SVC-059', 3, 'Stage 1→10+'),
  ('S10-SVC-027', 'Is there a management layer between you and delivery staff?', 'open_text', 'Team & Leadership', 'CORE', 'SVC-015', 'RC-SVC-060', 3, 'Stage 1→10+'),
  ('S10-SVC-028', 'Are new consultants becoming productive fast enough for how quickly you are hiring?', 'open_text', 'Team & Leadership', 'CORE', 'SVC-015', 'RC-SVC-061', 2, 'Stage 1→10+'),
  ('S10-SVC-029', 'Is anyone accountable for quality at a team level, or does it all trace back to you?', 'open_text', 'Team & Leadership', 'CORE', 'SVC-015', 'RC-SVC-062', 3, 'Stage 1→10+'),
  ('S10-SVC-030', 'Have client complaints increased as your team has grown?', 'open_text', 'Sales & Revenue', 'CORE', 'SVC-015', 'RC-SVC-059', 2, 'Stage 1→10+')
  ) AS t(question_code, question_text, question_type, category, priority,
         problem_code, root_cause_code, difficulty_level, primary_stage_group)
  JOIN new_problems np ON np.problem_code = t.problem_code
  JOIN new_root_causes nr ON nr.root_cause_code = t.root_cause_code
  CROSS JOIN z
  RETURNING question_id, question_code
),

-- 4. QUESTION TAG LINKS -------------------------------------------------------
new_tag_links AS (
  INSERT INTO question_tag_mapping (question_id, tag_id)
  SELECT nq.question_id, qt.tag_id
  FROM (VALUES
  ('S0-SVC-001', 'icp'),
  ('S0-SVC-002', 'icp'),
  ('S0-SVC-003', 'icp'),
  ('S0-SVC-004', 'icp'),
  ('S0-SVC-005', 'icp'),
  ('S0-SVC-006', 'willingness-to-pay'),
  ('S0-SVC-007', 'willingness-to-pay'),
  ('S0-SVC-008', 'willingness-to-pay'),
  ('S0-SVC-009', 'willingness-to-pay'),
  ('S0-SVC-010', 'willingness-to-pay'),
  ('S0-SVC-011', 'technical-quality'),
  ('S0-SVC-012', 'technical-quality'),
  ('S0-SVC-013', 'technical-quality'),
  ('S0-SVC-014', 'icp'),
  ('S0-SVC-015', 'icp'),
  ('S01-SVC-001', 'technical-quality'),
  ('S01-SVC-002', 'technical-quality'),
  ('S01-SVC-003', 'technical-quality'),
  ('S01-SVC-004', 'technical-quality'),
  ('S01-SVC-005', 'technical-quality'),
  ('S01-SVC-006', 'technical-quality'),
  ('S01-SVC-007', 'technical-quality'),
  ('S01-SVC-008', 'technical-quality'),
  ('S01-SVC-009', 'willingness-to-pay'),
  ('S01-SVC-010', 'willingness-to-pay'),
  ('S01-SVC-011', 'willingness-to-pay'),
  ('S01-SVC-012', 'willingness-to-pay'),
  ('S01-SVC-013', 'technical-quality'),
  ('S01-SVC-014', 'technical-quality'),
  ('S01-SVC-015', 'technical-quality'),
  ('S01-SVC-016', 'technical-quality'),
  ('S01-SVC-017', 'technical-quality'),
  ('S01-SVC-018', 'technical-quality'),
  ('S01-SVC-019', 'technical-quality'),
  ('S01-SVC-020', 'technical-quality'),
  ('S10-SVC-001', 'willingness-to-pay'),
  ('S10-SVC-002', 'willingness-to-pay'),
  ('S10-SVC-003', 'willingness-to-pay'),
  ('S10-SVC-004', 'willingness-to-pay'),
  ('S10-SVC-005', 'willingness-to-pay'),
  ('S10-SVC-006', 'willingness-to-pay'),
  ('S10-SVC-007', 'willingness-to-pay'),
  ('S10-SVC-008', 'willingness-to-pay'),
  ('S10-SVC-009', 'technical-quality'),
  ('S10-SVC-010', 'technical-quality'),
  ('S10-SVC-011', 'technical-quality'),
  ('S10-SVC-012', 'technical-quality'),
  ('S10-SVC-013', 'technical-quality'),
  ('S10-SVC-014', 'technical-quality'),
  ('S10-SVC-015', 'technical-quality'),
  ('S10-SVC-016', 'technical-quality'),
  ('S10-SVC-017', 'technical-quality'),
  ('S10-SVC-018', 'technical-quality'),
  ('S10-SVC-019', 'technical-quality'),
  ('S10-SVC-020', 'technical-quality'),
  ('S10-SVC-026', 'technical-quality'),
  ('S10-SVC-027', 'technical-quality'),
  ('S10-SVC-028', 'technical-quality'),
  ('S10-SVC-029', 'technical-quality'),
  ('S10-SVC-030', 'technical-quality')
  ) AS t(question_code, tag_name)
  JOIN new_questions nq ON nq.question_code = t.question_code
  JOIN question_tags qt ON qt.tag_name = t.tag_name
  RETURNING question_id
),

-- 5. INTERVENTIONS ------------------------------------------------------------
new_interventions AS (
  INSERT INTO interventions
    (intervention_code, section, problem_id, root_cause_ids, stage_relevance,
     capability_domain, design_principles, immediate_next_steps,
     recommended_frameworks, industry_relevance, secondary_root_cause_ids)
  SELECT t.intervention_code, t.section, np.problem_id, t.root_cause_ids,
         t.stage_relevance, t.capability_domain,
         '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb,
         t.immediate_next_steps, t.recommended_frameworks,
         '["services"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-SVC-001', 'Ideation — Services Practice Clarity', 'SVC-001', '["RC-SVC-001", "RC-SVC-002"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Choose one industry or problem to specialise in.", "Write down what you will say no to for now.", "Turn down work outside that focus."]'::jsonb, '[{"name": "Pick a Specialisation", "brief": "One clear focus instead of taking on any client work."}]'::jsonb),
  ('INT-SVC-002', 'Ideation — Services Practice Clarity', 'SVC-001', '["RC-SVC-003", "RC-SVC-005"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Write down a single, consistent description of your services.", "Use it the same way with every prospect.", "Stop letting the offer expand by accident."]'::jsonb, '[{"name": "One Consistent Offer Description", "brief": "A single way of describing services instead of a different pitch each time."}]'::jsonb),
  ('INT-SVC-003', 'Ideation — Services Practice Clarity', 'SVC-001', '["RC-SVC-004"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Talk to 10 real potential clients in your chosen focus.", "Ask what they would actually pay to have solved.", "Adjust your offer around their answers."]'::jsonb, '[{"name": "Talk to Real Prospects First", "brief": "Validating the offer with real conversations before committing further."}]'::jsonb),
  ('INT-SVC-004', 'Ideation — Services Cost to Deliver', 'SVC-002', '["RC-SVC-006", "RC-SVC-007"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Track actual hours spent on a project from start to finish.", "Load overhead into your cost calculation.", "Compare that total against what you charged."]'::jsonb, '[{"name": "Track Real Hours and Overhead", "brief": "A true cost per engagement, not a guess based on the fee alone."}]'::jsonb),
  ('INT-SVC-005', 'Ideation — Services Cost to Deliver', 'SVC-002', '["RC-SVC-008", "RC-SVC-009", "RC-SVC-010"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Count rework and revisions as real cost.", "Price from your own cost, not competitor rates.", "Review past projects to see which were actually profitable."]'::jsonb, '[{"name": "Price From Real Cost, Check Past Profitability", "brief": "Fees grounded in real cost, checked against what past work actually returned."}]'::jsonb),
  ('INT-SVC-006', 'Ideation — Services Scope Definition', 'SVC-003', '["RC-SVC-011", "RC-SVC-012"]'::jsonb, '[1]'::jsonb, 'Operations', '["Write a scope of work before starting any engagement.", "Describe deliverables specifically, not vaguely.", "Get it agreed in writing before work begins."]'::jsonb, '[{"name": "Written Scope Before Starting", "brief": "A documented scope and clear deliverables agreed upfront."}]'::jsonb),
  ('INT-SVC-007', 'Ideation — Services Scope Definition', 'SVC-003', '["RC-SVC-013", "RC-SVC-014"]'::jsonb, '[1]'::jsonb, 'Operations', '["Define a clear process for requests outside the original scope.", "Put expectations in writing, not just in conversation.", "Use the process the first time scope creep appears."]'::jsonb, '[{"name": "A Process for Out of Scope Work", "brief": "A defined way to handle requests beyond what was agreed."}]'::jsonb),
  ('INT-SVC-008', 'Ideation — Services Buyer Clarity', 'SVC-004', '["RC-SVC-015", "RC-SVC-017"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Identify who actually approves spend for this kind of service.", "Stop assuming expertise alone will close the deal.", "Build your pitch around that decision maker."]'::jsonb, '[{"name": "Find the Real Economic Buyer", "brief": "Selling to the person who approves spend, not just the person who likes the work."}]'::jsonb),
  ('INT-SVC-009', 'Ideation — Services Buyer Clarity', 'SVC-004', '["RC-SVC-016", "RC-SVC-018"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Talk to someone who has bought a similar service.", "Ask how long their decision actually took.", "Set realistic sales cycle expectations from that answer."]'::jsonb, '[{"name": "Learn From a Real Past Buyer", "brief": "Realistic sales cycle expectations from someone who has actually bought."}]'::jsonb),
  ('INT-SVC-010', 'Validation to Traction — Services Founder Dependency', 'SVC-005', '["RC-SVC-019", "RC-SVC-020"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Write down how you actually deliver an engagement, step by step.", "Train one other person against it.", "Hand them a smaller engagement to run alone."]'::jsonb, '[{"name": "Document and Delegate Delivery", "brief": "Turning founder-only delivery into something transferable."}]'::jsonb),
  ('INT-SVC-011', 'Validation to Traction — Services Founder Dependency', 'SVC-005', '["RC-SVC-021", "RC-SVC-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Track how many clients you have turned away for lack of time.", "Use that to justify hiring or delegating.", "Write a basic plan for income if you are unavailable."]'::jsonb, '[{"name": "Measure Turned Away Work, Plan for Absence", "brief": "Making the cost of limited capacity visible and preparing for founder downtime."}]'::jsonb),
  ('INT-SVC-012', 'Validation to Traction — Services Delivery Standardisation', 'SVC-006', '["RC-SVC-023", "RC-SVC-025"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Build templates from your best past engagements.", "Write down your delivery methodology.", "Use both on the next engagement instead of starting blank."]'::jsonb, '[{"name": "Build Reusable Templates", "brief": "Turning bespoke delivery into a documented, reusable method."}]'::jsonb),
  ('INT-SVC-013', 'Validation to Traction — Services Delivery Standardisation', 'SVC-006', '["RC-SVC-024", "RC-SVC-026"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Stop designing every engagement from scratch.", "Track delivery time per engagement over time.", "Look for it to shrink as templates and experience build up."]'::jsonb, '[{"name": "Track Delivery Time Over Time", "brief": "Measuring whether experience is actually compounding into speed."}]'::jsonb),
  ('INT-SVC-014', 'Validation to Traction — Services Billing Clarity', 'SVC-007', '["RC-SVC-027", "RC-SVC-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Agree what done means with the client before starting.", "Put it in writing alongside the scope.", "Refer back to it if a dispute arises."]'::jsonb, '[{"name": "Define Done Before You Start", "brief": "Written completion criteria to prevent disputes over value."}]'::jsonb),
  ('INT-SVC-015', 'Validation to Traction — Services Billing Clarity', 'SVC-007', '["RC-SVC-029", "RC-SVC-030"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Enforce payment terms consistently across every client.", "Follow up on overdue invoices on a fixed schedule.", "Track how long collections actually take."]'::jsonb, '[{"name": "Enforce Terms Consistently", "brief": "The same payment discipline applied to every client, without exception."}]'::jsonb),
  ('INT-SVC-016', 'Validation to Traction — Services Capacity Management', 'SVC-008', '["RC-SVC-031", "RC-SVC-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Build one central view of what is due for every client.", "Use it to set daily priorities for the team.", "Review it every morning."]'::jsonb, '[{"name": "One Central Workload View", "brief": "A single place showing everything due, across every client."}]'::jsonb),
  ('INT-SVC-017', 'Validation to Traction — Services Capacity Management', 'SVC-008', '["RC-SVC-033", "RC-SVC-034"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Check team availability before committing to new work.", "Stop promising delivery dates without checking capacity.", "Say no or push back timelines when capacity is not there."]'::jsonb, '[{"name": "Check Capacity Before You Promise", "brief": "Sales commitments grounded in a real view of what delivery can support."}]'::jsonb),
  ('INT-SVC-018', 'Validation to Traction — Services Talent Retention', 'SVC-009', '["RC-SVC-035", "RC-SVC-037"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Introduce a second person into every key client relationship.", "Do it before anyone signals they are leaving.", "Make sure the client knows both people."]'::jsonb, '[{"name": "Two Faces Per Client", "brief": "Shared relationships so trust does not rest on one consultant."}]'::jsonb),
  ('INT-SVC-019', 'Validation to Traction — Services Talent Retention', 'SVC-009', '["RC-SVC-036", "RC-SVC-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Put agreements in place covering client ownership on exit.", "Document what matters to each key client.", "Keep that record updated as the relationship evolves."]'::jsonb, '[{"name": "Document Ownership and Client Knowledge", "brief": "Written agreements and client knowledge that survive a departure."}]'::jsonb),
  ('INT-SVC-020', 'Growth to Maturity — Services Client Concentration', 'SVC-010', '["RC-SVC-039", "RC-SVC-041"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Calculate the revenue share of your top three clients.", "Set a ceiling and build a pipeline of smaller clients.", "Review the share every quarter."]'::jsonb, '[{"name": "Cap Client Concentration", "brief": "Measuring dependence and building beyond the dominant few."}]'::jsonb),
  ('INT-SVC-021', 'Growth to Maturity — Services Client Concentration', 'SVC-010', '["RC-SVC-040", "RC-SVC-042"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Work out your real margin on the dominant client after their terms.", "Identify which priorities you accept only because of dependence.", "Renegotiate or diversify away from the worst."]'::jsonb, '[{"name": "Margin and Agenda After Their Terms", "brief": "Seeing what a dominant client really leaves you, in money and priorities."}]'::jsonb),
  ('INT-SVC-022', 'Growth to Maturity — Services Utilisation Tracking', 'SVC-011', '["RC-SVC-043", "RC-SVC-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Track utilisation rate for every consultant.", "Calculate margin per engagement.", "Set a target utilisation rate and measure against it."]'::jsonb, '[{"name": "Track Utilisation and Margin", "brief": "Real numbers behind staffing and pricing decisions."}]'::jsonb),
  ('INT-SVC-023', 'Growth to Maturity — Services Utilisation Tracking', 'SVC-011', '["RC-SVC-045", "RC-SVC-046"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Review every client for actual profitability.", "Fix or exit accounts that are quietly losing money.", "Base staffing decisions on the profitability data."]'::jsonb, '[{"name": "Find and Fix Unprofitable Clients", "brief": "Checking the numbers instead of assuming every client is worth keeping."}]'::jsonb),
  ('INT-SVC-024', 'Growth to Maturity — Services Quality Consistency', 'SVC-012', '["RC-SVC-047", "RC-SVC-048"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Build a standard quality review before any deliverable goes out.", "Apply it consistently across every consultant.", "Track feedback variance by consultant."]'::jsonb, '[{"name": "Standard Quality Review", "brief": "A consistent check before delivery, regardless of who did the work."}]'::jsonb),
  ('INT-SVC-025', 'Growth to Maturity — Services Quality Consistency', 'SVC-012', '["RC-SVC-049", "RC-SVC-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Build a reliable feedback loop from client to delivery team.", "Reduce dependence on a few strong individuals.", "Turn what makes them strong into a shared standard."]'::jsonb, '[{"name": "Close the Feedback Loop", "brief": "Client input reaching delivery, and strengths turned into shared practice."}]'::jsonb),
  ('INT-SVC-026', 'Growth to Maturity — Services Senior Talent Pipeline', 'SVC-013', '["RC-SVC-051", "RC-SVC-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Build a structured path from junior to senior consultant.", "Review compensation against what it takes to retain seniors.", "Invest in developing talent internally, not only hiring it."]'::jsonb, '[{"name": "Build the Senior Pipeline", "brief": "A structured growth path and competitive pay to retain scarce senior talent."}]'::jsonb),
  ('INT-SVC-027', 'Growth to Maturity — Services Senior Talent Pipeline', 'SVC-013', '["RC-SVC-052", "RC-SVC-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Put client protection terms in place for senior hires.", "Introduce a second person into every key relationship.", "Reduce the risk a departure becomes a competing practice."]'::jsonb, '[{"name": "Protect Client Relationships on Exit", "brief": "Terms and shared relationships that reduce the risk of losing clients to a departure."}]'::jsonb),
  ('INT-SVC-028', 'Growth to Maturity — Services Defensibility', 'SVC-014', '["RC-SVC-055", "RC-SVC-057"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Build a proprietary framework, tool or data asset.", "Make it central to how you deliver, not a side feature.", "Use it as the reason to choose you over a competitor."]'::jsonb, '[{"name": "Build Something Proprietary", "brief": "An owned asset that a competitor cannot simply copy."}]'::jsonb),
  ('INT-SVC-029', 'Growth to Maturity — Services Defensibility', 'SVC-014', '["RC-SVC-056", "RC-SVC-058"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Track how often pitches are won on relationship or price alone.", "Build a mechanism that gets better as you serve more clients.", "Compete on that compounding advantage instead."]'::jsonb, '[{"name": "Build a Compounding Advantage", "brief": "An asset that improves with scale instead of staying flat."}]'::jsonb),
  ('INT-SVC-030', 'Growth to Maturity — Services Scale Consistency', 'SVC-015', '["RC-SVC-059", "RC-SVC-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Build a management layer between founder and delivery staff.", "Give managers real authority over quality and review.", "Stop routing every issue straight to the founder."]'::jsonb, '[{"name": "Build a Management Layer", "brief": "Delegated oversight so quality does not depend on the founder personally checking everything."}]'::jsonb),
  ('INT-SVC-031', 'Growth to Maturity — Services Scale Consistency', 'SVC-015', '["RC-SVC-061", "RC-SVC-062"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Speed up onboarding so new consultants ramp up faster.", "Assign clear accountability for quality at the team level.", "Track client complaints as a signal of where this is breaking down."]'::jsonb, '[{"name": "Faster Ramp, Clear Accountability", "brief": "Onboarding and ownership structured to keep pace with headcount growth."}]'::jsonb),
  ('INT-SVC-032', 'Ideation — Services Buyer Clarity', 'SVC-004', '["RC-SVC-063"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Find out what pricing model your target buyers actually expect.", "Check whether hourly, fixed fee or retainer fits their norms.", "Choose your pricing model based on that, not habit."]'::jsonb, '[{"name": "Match Pricing Model to Buyer Expectations", "brief": "Choosing a pricing structure buyers already expect, not one picked at random."}]'::jsonb),
  ('INT-SVC-033', 'Ideation — Services Scope Definition', 'SVC-003', '["RC-SVC-064"]'::jsonb, '[1]'::jsonb, 'Operations', '["Check delivered scope against original hours periodically.", "Flag drift as soon as it appears, not at the end.", "Use it to price the next similar engagement more accurately."]'::jsonb, '[{"name": "Review Scope Against Hours", "brief": "Catching scope drift early instead of discovering it at project close."}]'::jsonb),
  ('INT-SVC-034', 'Validation to Traction — Services Capacity Management', 'SVC-008', '["RC-SVC-065"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Look systematically for ways to expand work with existing clients.", "Raise it at natural checkpoints in the engagement.", "Track how much revenue comes from expansion versus new clients."]'::jsonb, '[{"name": "Systematic Cross Selling", "brief": "Deliberately looking for expansion opportunities instead of leaving them to chance."}]'::jsonb)
  ) AS t(intervention_code, section, problem_code, root_cause_ids, stage_relevance,
         capability_domain, immediate_next_steps, recommended_frameworks)
  JOIN new_problems np ON np.problem_code = t.problem_code
  RETURNING intervention_id
)
SELECT
  (SELECT COUNT(*) FROM new_problems)     AS problems_inserted,      -- expect 15
  (SELECT COUNT(*) FROM new_root_causes)  AS root_causes_inserted,   -- expect 66
  (SELECT COUNT(*) FROM new_questions)    AS questions_inserted,     -- expect 60
  (SELECT COUNT(*) FROM new_tag_links)    AS tag_links_inserted,     -- expect 60
  (SELECT COUNT(*) FROM new_interventions) AS interventions_inserted;-- expect 34

-- ============================================================================
-- After running, the single result row above must read:  15 | 66 | 60 | 60 | 34
-- If any number differs, something did not link -- roll back and check.
-- ============================================================================"""),
        ('Sports, Fitness & Wellness', 'sports_fitness', 'SPF', {}, r"""-- ============================================================================
-- Ally :: Industry seed -- SPORTS, FITNESS & WELLNESS (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: sports_fitness
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (SPF-001, RC-SPF-014, S0-SPF-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (member retention, instructor turnover, facility
--            maintenance, seasonal demand, liability management) starts at
--            Stage 0->1; account concentration, multi site consistency,
--            compliance operations, technology gap, defensibility and
--            compensation scaling at Stage 1->10+.
-- ============================================================================

WITH z AS (
  SELECT ('[' || array_to_string(array_fill(0, ARRAY[1536]), ',') || ']')::vector AS v
),

-- 1. PROBLEMS -----------------------------------------------------------------
new_problems AS (
  INSERT INTO problems
    (problem_code, problem_name, description, category, subcategory, layer,
     pillar_id, severity_min, severity_max, symptoms, industry_relevance,
     related_problem_ids, embedding)
  SELECT t.problem_code, t.problem_name, t.description, t.category, t.subcategory,
         t.layer, t.pillar_id, t.severity_min, t.severity_max, t.symptoms,
         t.industry_relevance, '[]'::jsonb, z.v
  FROM (VALUES
  ('SPF-001', 'No Clear Member or Client Type Chosen', 'The gym, studio or wellness offering tries to serve beginners, athletes and casual visitors all at once, so nothing about the experience is designed for anyone specific.', 'Idea & Validation', 'Sports Client Clarity', 'external', 2, 4, 8, '["Target member described as anyone who wants to get fit", "No specific fitness level or goal designed for", "Class or programme mix decided without a theme", "No conversation with a real potential member", "Facility layout serving everyone averagely, no one well"]'::jsonb, '["sports_fitness"]'::jsonb),
  ('SPF-002', 'Real Cost of Running a Session or Class Not Worked Out', 'Trainer time, space cost, equipment wear and no shows are not built into pricing, so nobody knows if a class or session is actually profitable.', 'Idea & Validation', 'Sports Session Cost Reality', 'external', 4, 5, 9, '["Only trainer hourly rate counted as cost", "Space and equipment cost not factored in", "No shows and cancellations not counted as lost revenue", "Price set by looking at competitors only", "No idea what attendance is needed to break even"]'::jsonb, '["sports_fitness"]'::jsonb),
  ('SPF-003', 'No Idea How Many Members Are Needed to Survive', 'Membership pricing and capacity were set without working out how many paying members the business actually needs each month.', 'Idea & Validation', 'Sports Membership Math', 'external', 3, 5, 9, '["No break even membership number calculated", "Capacity planned without a revenue target behind it", "Assuming members will simply show up over time", "No test period before committing to a full facility", "No idea what a realistic signup rate looks like"]'::jsonb, '["sports_fitness"]'::jsonb),
  ('SPF-004', 'Location or Format Chosen Without Testing Real Demand', 'A facility location or programme format was picked before confirming that the target member actually wants it there or in that form.', 'Idea & Validation', 'Sports Format and Location Clarity', 'external', 3, 5, 9, '["Location chosen for rent price, not proven demand", "No foot traffic or catchment data checked", "No small pilot class before committing to a lease", "Assuming a good workout format sells itself", "No conversation with a real member about where and how they train"]'::jsonb, '["sports_fitness"]'::jsonb),
  ('SPF-005', 'Members Signing Up but Not Coming Back', 'New members join at a healthy rate but attendance and renewal drop off quickly, and nobody has traced why.', 'Sales & Revenue', 'Sports Member Retention', 'external', 4, 6, 9, '["High signup rate but low renewal rate", "Attendance dropping sharply after the first few weeks", "No onboarding process for new members", "No tracking of who has stopped attending", "Cancellations discovered only at renewal time"]'::jsonb, '["sports_fitness"]'::jsonb),
  ('SPF-006', 'Trainer and Instructor Turnover Disrupting the Member Experience', 'Trainers and instructors leave frequently, and members lose the relationship and consistency that kept them coming.', 'Team & Leadership', 'Sports Instructor Turnover', 'external', 3, 6, 9, '["High trainer or instructor turnover", "Members leaving shortly after a favourite trainer leaves", "No standard onboarding for new instructors", "Class quality varying by who teaches it", "Recruitment happening reactively, not planned"]'::jsonb, '["sports_fitness"]'::jsonb),
  ('SPF-007', 'Equipment and Facility Maintenance Handled Reactively', 'Equipment breaks or facilities degrade before anyone notices, disrupting sessions and creating safety risk.', 'Operations & Systems', 'Sports Facility Maintenance', 'external', 3, 6, 9, '["Equipment repaired only after it fails", "No scheduled maintenance programme", "Facility issues discovered by members before staff", "No budget set aside for equipment replacement", "Safety incidents traced back to poor maintenance"]'::jsonb, '["sports_fitness"]'::jsonb),
  ('SPF-008', 'Seasonal Demand Swings Not Planned For', 'Attendance and signups swing heavily across the year, and staffing, cash flow and programming are not adjusted for it.', 'Financial Management', 'Sports Seasonal Demand', 'external', 4, 6, 9, '["Attendance dropping sharply in certain months", "Staffing levels not adjusted for low season", "Cash flow strained during predictable slow periods", "No promotional plan for off peak months", "Same pricing and programming used year round"]'::jsonb, '["sports_fitness"]'::jsonb),
  ('SPF-009', 'Liability and Injury Risk Not Properly Managed', 'Waivers, insurance and incident response are handled informally, exposing the business to real risk when something goes wrong.', 'Operations & Systems', 'Sports Liability Management', 'external', 3, 7, 10, '["Waivers not consistently collected or updated", "Insurance coverage not reviewed against actual activities", "No standard incident response process", "Injury incidents not logged or tracked", "Staff not trained on emergency response"]'::jsonb, '["sports_fitness"]'::jsonb),
  ('SPF-010', 'Revenue Concentrated in a Few Corporate or Group Accounts', 'A handful of corporate wellness contracts or group bookings account for most revenue, so their loss would be severe and they set the terms.', 'Sales & Revenue', 'Sports Account Concentration', 'external', 4, 7, 10, '["Most revenue from a few corporate or group accounts", "Rates dictated by the largest account", "No pipeline of replacement accounts or individual members", "Losing one account would threaten the business", "Programming shaped by one account rather than the wider member base"]'::jsonb, '["sports_fitness"]'::jsonb),
  ('SPF-011', 'New Location Does Not Match the First', 'A second facility or franchise site underperforms the original, and nothing was systemised before expanding.', 'Operations & Systems', 'Sports Multi Site Consistency', 'external', 3, 6, 9, '["New location underperforming the original in signups or retention", "Nothing written down to replicate the first site culture and process", "Different standards or equipment per location", "Founder or lead trainer still needed at the original site", "Member experience differing noticeably across sites"]'::jsonb, '["sports_fitness"]'::jsonb),
  ('SPF-012', 'Certification and Safety Compliance Now a Constant Burden', 'Trainer certifications, facility inspections and safety standards recur continuously and cannot be tracked informally at this scale.', 'Operations & Systems', 'Sports Compliance Operations', 'external', 3, 7, 10, '["Trainer certifications tracked from memory", "No single compliance calendar for inspections and renewals", "Certification lapses discovered too late", "Safety incidents repeating without being permanently fixed", "One person holding all the compliance knowledge"]'::jsonb, '["sports_fitness"]'::jsonb),
  ('SPF-013', 'Technology and Data Expectations Outpacing the Business', 'Members increasingly expect app booking, progress tracking and digital engagement that the business has not built.', 'Strategy & Planning', 'Sports Technology Gap', 'external', 2, 6, 10, '["Members asking for app based booking and tracking", "Competitors offering digital features this business lacks", "Booking and check in still handled manually", "No data on member behaviour to act on", "No budget allocated for technology investment"]'::jsonb, '["sports_fitness"]'::jsonb),
  ('SPF-014', 'Nothing Differentiates This From Any Other Gym or Studio', 'Members can switch to a similar facility at similar cost with little friction, because nothing built here creates real loyalty.', 'Strategy & Planning', 'Sports Defensibility', 'external', 2, 6, 10, '["Programming easily matched by competitors", "Price the main basis of member decisions", "No community or brand connection beyond convenience", "No proprietary method or format", "Member churn to marginally cheaper alternatives"]'::jsonb, '["sports_fitness"]'::jsonb),
  ('SPF-015', 'Instructor and Trainer Compensation Model Not Scaling Fairly', 'Pay structures built for a small handful of trainers create resentment, disputes or unsustainable cost as the roster and class volume grow.', 'Financial Management', 'Sports Compensation Scaling', 'external', 3, 6, 10, '["Pay model designed for a handful of trainers now causing disputes", "Top trainers underpaid relative to revenue they generate", "No clear structure for raises or advancement", "Compensation costs growing faster than revenue", "Inconsistent pay for similar work across the roster"]'::jsonb, '["sports_fitness"]'::jsonb)
  ) AS t(problem_code, problem_name, description, category, subcategory, layer,
         pillar_id, severity_min, severity_max, symptoms, industry_relevance), z
  RETURNING problem_id, problem_code
),

-- 2. ROOT CAUSES --------------------------------------------------------------
new_root_causes AS (
  INSERT INTO root_causes
    (root_cause_code, root_cause_name, explanation, problem_id, layer,
     root_cause_category, confidence_weight, primary_stage_group,
     industry_relevance, embedding)
  SELECT t.root_cause_code, t.root_cause_name, t.explanation, np.problem_id,
         t.layer, t.root_cause_category, t.confidence_weight,
         t.primary_stage_group, '["sports_fitness"]'::jsonb, z.v
  FROM (VALUES
  ('RC-SPF-001', 'Target Member Described as Anyone Wanting Fitness', 'No specific member type has been chosen to design for.', 'SPF-001', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-SPF-002', 'No Specific Fitness Level or Goal Designed For', 'Programming does not target a defined starting point or outcome.', 'SPF-001', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-SPF-003', 'Class Mix Decided Without a Theme', 'Offerings do not connect around a coherent member journey.', 'SPF-001', 'external', 'Behavioural', 0.68, 'Stage 0'),
  ('RC-SPF-004', 'No Conversation With a Real Potential Member', 'Nobody who would actually join has been spoken to.', 'SPF-001', 'external', 'Behavioural', 0.66, 'Stage 0'),
  ('RC-SPF-005', 'Facility Serving Everyone Averagely', 'Design compromises mean nobody gets an excellent experience.', 'SPF-001', 'external', 'Strategic', 0.67, 'Stage 0'),
  ('RC-SPF-006', 'Only Trainer Rate Counted as Cost', 'The cost of a session is taken as trainer pay alone.', 'SPF-002', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-SPF-007', 'Space and Equipment Cost Not Factored In', 'Rent, utilities and equipment wear are missing from session cost.', 'SPF-002', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-SPF-008', 'No Shows Not Counted as Lost Revenue', 'Cancellations and absences are not treated as a real cost.', 'SPF-002', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-SPF-009', 'Price Set by Looking at Competitors', 'Pricing copies others without knowing own true cost.', 'SPF-002', 'external', 'Behavioural', 0.67, 'Stage 0'),
  ('RC-SPF-010', 'No Break Even Attendance Known', 'What attendance is needed to cover cost has not been calculated.', 'SPF-002', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-SPF-011', 'No Break Even Membership Number Calculated', 'How many paying members are needed monthly is unknown.', 'SPF-003', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-SPF-012', 'Capacity Planned Without a Revenue Target', 'Facility size was chosen without a number of members behind it.', 'SPF-003', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-SPF-013', 'Assuming Members Will Simply Show Up', 'Believing growth will happen without a specific acquisition plan.', 'SPF-003', 'external', 'Psychological', 0.68, 'Stage 0'),
  ('RC-SPF-014', 'No Test Period Before Full Commitment', 'A trial phase was skipped in favour of committing fully.', 'SPF-003', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-SPF-015', 'Location Chosen for Rent Price Not Demand', 'The site was picked because it was affordable, not because members wanted it.', 'SPF-004', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-SPF-016', 'No Foot Traffic or Catchment Data Checked', 'Real demand near the location was never measured.', 'SPF-004', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-SPF-017', 'No Small Pilot Before Committing', 'A lease or format was committed to without a low cost trial first.', 'SPF-004', 'external', 'Strategic', 0.69, 'Stage 0'),
  ('RC-SPF-018', 'Assuming a Good Format Sells Itself', 'Believing quality alone will bring members without marketing.', 'SPF-004', 'external', 'Psychological', 0.67, 'Stage 0'),
  ('RC-SPF-019', 'No Onboarding Process for New Members', 'New members are left to figure out the facility and community alone.', 'SPF-005', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-SPF-020', 'No Tracking of Who Has Stopped Attending', 'Declining attendance is not flagged until renewal time.', 'SPF-005', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-SPF-021', 'Attendance Dropping Sharply After First Weeks', 'Early engagement fades without anything catching it.', 'SPF-005', 'external', 'Behavioural', 0.70, 'Stage 0→1'),
  ('RC-SPF-022', 'Cancellations Discovered Only at Renewal', 'Nobody checks in with a member before they decide to leave.', 'SPF-005', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-SPF-023', 'No Standard Onboarding for New Instructors', 'New trainers start without a structured introduction.', 'SPF-006', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-SPF-024', 'Members Tied to a Specific Trainer', 'Loyalty sits with the individual instructor, not the facility.', 'SPF-006', 'external', 'Strategic', 0.73, 'Stage 0→1'),
  ('RC-SPF-025', 'Class Quality Varying by Instructor', 'Consistency across instructors has not been standardised.', 'SPF-006', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-SPF-026', 'Instructor Recruitment Happening Reactively', 'Hiring starts only once a gap becomes urgent.', 'SPF-006', 'external', 'Behavioural', 0.68, 'Stage 0→1'),
  ('RC-SPF-027', 'Equipment Repaired Only After Failure', 'Nothing catches wear before it becomes a breakdown.', 'SPF-007', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-SPF-028', 'No Scheduled Maintenance Programme', 'Equipment and facility upkeep is not on any calendar.', 'SPF-007', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-SPF-029', 'Facility Issues Found by Members First', 'Problems are discovered through complaints, not inspection.', 'SPF-007', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-SPF-030', 'No Budget for Equipment Replacement', 'Nothing is set aside for replacing aging equipment.', 'SPF-007', 'external', 'Strategic', 0.69, 'Stage 0→1'),
  ('RC-SPF-031', 'Staffing Not Adjusted for Low Season', 'The same staffing level runs regardless of demand swings.', 'SPF-008', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-SPF-032', 'Cash Flow Strained During Predictable Slow Periods', 'Known seasonal dips are not planned for financially.', 'SPF-008', 'external', 'Strategic', 0.71, 'Stage 0→1'),
  ('RC-SPF-033', 'No Promotional Plan for Off Peak Months', 'Nothing is done to fill capacity during slow periods.', 'SPF-008', 'external', 'Strategic', 0.70, 'Stage 0→1'),
  ('RC-SPF-034', 'Same Pricing and Programming Year Round', 'Offerings do not flex with known seasonal demand.', 'SPF-008', 'external', 'Strategic', 0.68, 'Stage 0→1'),
  ('RC-SPF-035', 'Waivers Not Consistently Collected', 'Legal protection is inconsistent across members and activities.', 'SPF-009', 'external', 'Operational', 0.74, 'Stage 0→1'),
  ('RC-SPF-036', 'Insurance Not Reviewed Against Actual Activities', 'Coverage may not match what the business actually does.', 'SPF-009', 'external', 'Knowledge', 0.72, 'Stage 0→1'),
  ('RC-SPF-037', 'No Standard Incident Response Process', 'What happens after an injury is not clearly defined.', 'SPF-009', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-SPF-038', 'Staff Not Trained on Emergency Response', 'Nobody is prepared to handle a real emergency correctly.', 'SPF-009', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-SPF-039', 'Most Revenue From a Few Corporate or Group Accounts', 'A handful of accounts carry most of the business.', 'SPF-010', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-SPF-040', 'Rates Dictated by the Largest Account', 'The dominant account sets what can be charged.', 'SPF-010', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-SPF-041', 'No Pipeline of Replacement Accounts', 'Nothing is being built that could replace a lost account.', 'SPF-010', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-SPF-042', 'Programming Shaped by One Account', 'The dominant account decides offerings rather than the wider membership.', 'SPF-010', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-SPF-043', 'Nothing Written Down to Replicate the First Site', 'The original location runs on knowledge nobody has recorded.', 'SPF-011', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-SPF-044', 'Founder or Lead Trainer Still Needed at Original Site', 'The first location cannot run without a specific person present.', 'SPF-011', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-SPF-045', 'Different Standards or Equipment Per Location', 'Each site operates differently from the others.', 'SPF-011', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-SPF-046', 'Expanded Before the First Was Systemised', 'A second site opened before the first was repeatable.', 'SPF-011', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-SPF-047', 'Certifications Tracked From Memory', 'Renewal dates for trainer certifications live in memory, not a system.', 'SPF-012', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-SPF-048', 'No Single Compliance Calendar', 'Nothing brings every inspection and renewal into one dated place.', 'SPF-012', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-SPF-049', 'Certification Lapses Discovered Too Late', 'A lapse is found only after it has already caused a problem.', 'SPF-012', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-SPF-050', 'Safety Incidents Repeating', 'The same safety issue recurs without being permanently fixed.', 'SPF-012', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-SPF-051', 'Booking and Check In Handled Manually', 'No digital system exists for members to book or check in.', 'SPF-013', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-SPF-052', 'No Data on Member Behaviour', 'Nothing is tracked about how members actually use the facility.', 'SPF-013', 'external', 'Knowledge', 0.71, 'Stage 1→10+'),
  ('RC-SPF-053', 'No Budget for Technology Investment', 'Nothing has been set aside to close the digital gap.', 'SPF-013', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-SPF-054', 'Programming Easily Matched by Competitors', 'What is offered can be replicated without much effort.', 'SPF-014', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-SPF-055', 'Price the Main Basis of Member Decisions', 'Differentiation has collapsed into being cheaper.', 'SPF-014', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-SPF-056', 'No Proprietary Method or Format', 'Nothing owned makes the facility harder to leave.', 'SPF-014', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-SPF-057', 'Pay Model Designed for a Handful of Trainers', 'Compensation structure has not been rebuilt for a larger roster.', 'SPF-015', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-SPF-058', 'Top Trainers Underpaid Relative to Revenue Generated', 'Pay does not reflect the value the best trainers actually bring in.', 'SPF-015', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-SPF-059', 'No Clear Structure for Raises or Advancement', 'Nothing defines how a trainer progresses in pay or role.', 'SPF-015', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-SPF-060', 'Compensation Costs Growing Faster Than Revenue', 'Pay is scaling out of proportion to what the business brings in.', 'SPF-015', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-SPF-061', 'No Idea What a Realistic Signup Rate Looks Like', 'How quickly members typically sign up for a comparable facility has not been researched.', 'SPF-003', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-SPF-062', 'No Conversation With a Member About Where and How They Train', 'Nobody has asked a real member what format or location they actually want.', 'SPF-004', 'external', 'Behavioural', 0.65, 'Stage 0'),
  ('RC-SPF-063', 'No Referral or Word of Mouth Programme', 'Existing members are not systematically encouraged to bring in new ones.', 'SPF-005', 'external', 'Strategic', 0.66, 'Stage 0→1'),
  ('RC-SPF-064', 'No Cross Training Between Locations', 'Staff at one site cannot easily cover or learn from another.', 'SPF-011', 'external', 'Operational', 0.66, 'Stage 1→10+'),
  ('RC-SPF-065', 'No Regular Review of Which Accounts to Prioritise', 'Nobody periodically reassesses which accounts deserve the most attention.', 'SPF-010', 'external', 'Operational', 0.66, 'Stage 1→10+'),
  ('RC-SPF-066', 'No Exit Interview Process for Departing Trainers', 'Nobody captures why a trainer actually left before they go.', 'SPF-015', 'external', 'Operational', 0.65, 'Stage 1→10+')
  ) AS t(root_cause_code, root_cause_name, explanation, problem_code, layer,
         root_cause_category, confidence_weight, primary_stage_group)
  JOIN new_problems np ON np.problem_code = t.problem_code
  CROSS JOIN z
  RETURNING root_cause_id, root_cause_code
),

-- 3. QUESTIONS ----------------------------------------------------------------
new_questions AS (
  INSERT INTO questions
    (question_code, question_text, question_type, category, priority,
     problem_id, root_cause_id, difficulty_level, primary_stage_group,
     industry_relevance, is_distress_tagged, embedding)
  SELECT t.question_code, t.question_text, t.question_type, t.category, t.priority,
         np.problem_id, nr.root_cause_id, t.difficulty_level, t.primary_stage_group,
         '["sports_fitness"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-SPF-001', 'Who exactly is your target member?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-001', 'RC-SPF-001', 1, 'Stage 0'),
  ('S0-SPF-002', 'What specific fitness level or goal are you designed for?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-001', 'RC-SPF-002', 1, 'Stage 0'),
  ('S0-SPF-003', 'Do your classes connect around one clear theme or journey?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-001', 'RC-SPF-003', 2, 'Stage 0'),
  ('S0-SPF-004', 'Have you talked to a real potential member who would actually join?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-001', 'RC-SPF-004', 2, 'Stage 0'),
  ('S0-SPF-005', 'Are you trying to serve everyone averagely instead of someone excellently?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-001', 'RC-SPF-005', 2, 'Stage 0'),
  ('S0-SPF-006', 'What does one class or session actually cost you, beyond trainer pay?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-002', 'RC-SPF-006', 1, 'Stage 0'),
  ('S0-SPF-007', 'Have you factored in space and equipment cost per session?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-002', 'RC-SPF-007', 2, 'Stage 0'),
  ('S0-SPF-008', 'Do you count no shows and cancellations as lost revenue?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-002', 'RC-SPF-008', 2, 'Stage 0'),
  ('S0-SPF-009', 'Did you set your price from your own cost or from competitors?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-002', 'RC-SPF-009', 2, 'Stage 0'),
  ('S0-SPF-010', 'Do you know what attendance you need to break even on a class?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-002', 'RC-SPF-010', 2, 'Stage 0'),
  ('S0-SPF-011', 'Do you know how many paying members you need each month to survive?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-003', 'RC-SPF-011', 1, 'Stage 0'),
  ('S0-SPF-012', 'Was your capacity planned around a specific revenue target?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-003', 'RC-SPF-012', 2, 'Stage 0'),
  ('S0-SPF-013', 'Are you assuming members will simply show up over time?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-003', 'RC-SPF-013', 2, 'Stage 0'),
  ('S0-SPF-014', 'Did you run a test period before committing to the full facility?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-003', 'RC-SPF-014', 2, 'Stage 0'),
  ('S0-SPF-015', 'Did you check real foot traffic or demand before choosing this location?', 'open_text', 'Idea & Validation', 'CORE', 'SPF-004', 'RC-SPF-016', 1, 'Stage 0'),
  ('S01-SPF-001', 'What share of new members are still coming after 60 days?', 'open_text', 'Sales & Revenue', 'CORE', 'SPF-005', 'RC-SPF-021', 2, 'Stage 0→1'),
  ('S01-SPF-002', 'Is there a structured onboarding process for new members?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-005', 'RC-SPF-019', 2, 'Stage 0→1'),
  ('S01-SPF-003', 'Do you track who has stopped attending before renewal comes up?', 'open_text', 'Sales & Revenue', 'CORE', 'SPF-005', 'RC-SPF-020', 2, 'Stage 0→1'),
  ('S01-SPF-004', 'Do you reach out to a member before they decide to cancel, or only after?', 'open_text', 'Sales & Revenue', 'CORE', 'SPF-005', 'RC-SPF-022', 2, 'Stage 0→1'),
  ('S01-SPF-005', 'How many trainers or instructors have left in the last year?', 'open_text', 'Team & Leadership', 'CORE', 'SPF-006', 'RC-SPF-026', 2, 'Stage 0→1'),
  ('S01-SPF-006', 'Have members left shortly after a favourite trainer left?', 'open_text', 'Sales & Revenue', 'CORE', 'SPF-006', 'RC-SPF-024', 3, 'Stage 0→1'),
  ('S01-SPF-007', 'How does a new instructor learn your standards and style?', 'open_text', 'Team & Leadership', 'CORE', 'SPF-006', 'RC-SPF-023', 2, 'Stage 0→1'),
  ('S01-SPF-008', 'Does class quality vary noticeably depending on who teaches it?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-006', 'RC-SPF-025', 2, 'Stage 0→1'),
  ('S01-SPF-009', 'Is equipment serviced on a schedule or only after it breaks?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-007', 'RC-SPF-027', 2, 'Stage 0→1'),
  ('S01-SPF-010', 'Is there a maintenance calendar for equipment and facility?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-007', 'RC-SPF-028', 2, 'Stage 0→1'),
  ('S01-SPF-011', 'Do members find facility problems before staff do?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-007', 'RC-SPF-029', 2, 'Stage 0→1'),
  ('S01-SPF-012', 'Is there a budget set aside for replacing equipment?', 'open_text', 'Financial Management', 'CORE', 'SPF-007', 'RC-SPF-030', 2, 'Stage 0→1'),
  ('S01-SPF-013', 'Does your attendance swing heavily across the year?', 'open_text', 'Financial Management', 'CORE', 'SPF-008', 'RC-SPF-031', 2, 'Stage 0→1'),
  ('S01-SPF-014', 'Do you adjust staffing levels for low season?', 'open_text', 'Team & Leadership', 'CORE', 'SPF-008', 'RC-SPF-031', 2, 'Stage 0→1'),
  ('S01-SPF-015', 'Does cash flow get strained during predictable slow months?', 'open_text', 'Financial Management', 'CORE', 'SPF-008', 'RC-SPF-032', 3, 'Stage 0→1'),
  ('S01-SPF-016', 'Do you have a promotional plan for off peak months?', 'open_text', 'Financial Management', 'CORE', 'SPF-008', 'RC-SPF-033', 2, 'Stage 0→1'),
  ('S01-SPF-017', 'Do you collect and update waivers consistently?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-009', 'RC-SPF-035', 2, 'Stage 0→1'),
  ('S01-SPF-018', 'Has your insurance been reviewed against what you actually do?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-009', 'RC-SPF-036', 3, 'Stage 0→1'),
  ('S01-SPF-019', 'Is there a standard process for responding to an injury?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-009', 'RC-SPF-037', 3, 'Stage 0→1'),
  ('S01-SPF-020', 'Are your staff trained on emergency response?', 'open_text', 'Team & Leadership', 'CORE', 'SPF-009', 'RC-SPF-038', 3, 'Stage 0→1'),
  ('S10-SPF-001', 'What share of your revenue comes from your top two or three corporate or group accounts?', 'open_text', 'Sales & Revenue', 'CORE', 'SPF-010', 'RC-SPF-039', 2, 'Stage 1→10+'),
  ('S10-SPF-002', 'Who sets your rates, you or your largest account?', 'open_text', 'Sales & Revenue', 'CORE', 'SPF-010', 'RC-SPF-040', 2, 'Stage 1→10+'),
  ('S10-SPF-003', 'If your largest account left, how long could you continue?', 'open_text', 'Strategy & Planning', 'CORE', 'SPF-010', 'RC-SPF-041', 3, 'Stage 1→10+'),
  ('S10-SPF-004', 'Is your programming shaped by one account rather than your wider membership?', 'open_text', 'Strategy & Planning', 'CORE', 'SPF-010', 'RC-SPF-042', 3, 'Stage 1→10+'),
  ('S10-SPF-005', 'Does your newest location match the performance of the first?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-011', 'RC-SPF-043', 2, 'Stage 1→10+'),
  ('S10-SPF-006', 'Is there anything written down that a new site could run from?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-011', 'RC-SPF-043', 2, 'Stage 1→10+'),
  ('S10-SPF-007', 'Can your original location run without a specific person present?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-011', 'RC-SPF-044', 3, 'Stage 1→10+'),
  ('S10-SPF-008', 'Do all your locations use the same standards and equipment?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-011', 'RC-SPF-045', 2, 'Stage 1→10+'),
  ('S10-SPF-009', 'Was your first site fully systemised before you opened the second?', 'open_text', 'Strategy & Planning', 'CORE', 'SPF-011', 'RC-SPF-046', 3, 'Stage 1→10+'),
  ('S10-SPF-010', 'Can you list every trainer certification and its expiry date?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-012', 'RC-SPF-047', 2, 'Stage 1→10+'),
  ('S10-SPF-011', 'Is there one calendar covering every inspection and renewal?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-012', 'RC-SPF-048', 2, 'Stage 1→10+'),
  ('S10-SPF-012', 'Have you ever discovered a lapsed certification only after it caused a problem?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-012', 'RC-SPF-049', 3, 'Stage 1→10+'),
  ('S10-SPF-013', 'Have the same safety incidents come up more than once?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-012', 'RC-SPF-050', 3, 'Stage 1→10+'),
  ('S10-SPF-014', 'Can members book and check in digitally, or is it still manual?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-013', 'RC-SPF-051', 2, 'Stage 1→10+'),
  ('S10-SPF-015', 'Do you have any data on how members actually use the facility?', 'open_text', 'Strategy & Planning', 'CORE', 'SPF-013', 'RC-SPF-052', 3, 'Stage 1→10+'),
  ('S10-SPF-016', 'Is there a budget set aside to close your technology gap?', 'open_text', 'Financial Management', 'CORE', 'SPF-013', 'RC-SPF-053', 2, 'Stage 1→10+'),
  ('S10-SPF-017', 'How easily could a competitor copy your programming?', 'open_text', 'Strategy & Planning', 'CORE', 'SPF-014', 'RC-SPF-054', 3, 'Stage 1→10+'),
  ('S10-SPF-018', 'Do members choose you mainly on price or on something else?', 'open_text', 'Sales & Revenue', 'CORE', 'SPF-014', 'RC-SPF-055', 2, 'Stage 1→10+'),
  ('S10-SPF-019', 'Do you have any proprietary method or format members cannot get elsewhere?', 'open_text', 'Strategy & Planning', 'CORE', 'SPF-014', 'RC-SPF-056', 3, 'Stage 1→10+'),
  ('S10-SPF-020', 'Is your current pay structure causing disputes as your roster grows?', 'open_text', 'Team & Leadership', 'CORE', 'SPF-015', 'RC-SPF-057', 2, 'Stage 1→10+'),
  ('S10-SPF-021', 'Are your top trainers paid in line with the revenue they generate?', 'open_text', 'Financial Management', 'CORE', 'SPF-015', 'RC-SPF-058', 3, 'Stage 1→10+'),
  ('S10-SPF-022', 'Is there a clear path for a trainer to earn more or advance?', 'open_text', 'Team & Leadership', 'CORE', 'SPF-015', 'RC-SPF-059', 2, 'Stage 1→10+'),
  ('S10-SPF-023', 'Is your compensation cost growing faster than your revenue?', 'open_text', 'Financial Management', 'CORE', 'SPF-015', 'RC-SPF-060', 3, 'Stage 1→10+'),
  ('S10-SPF-024', 'Have you lost a member to a marginally cheaper competitor?', 'open_text', 'Sales & Revenue', 'CORE', 'SPF-014', 'RC-SPF-055', 2, 'Stage 1→10+'),
  ('S10-SPF-025', 'Would a member notice a difference in quality between your locations?', 'open_text', 'Operations & Systems', 'CORE', 'SPF-011', 'RC-SPF-045', 2, 'Stage 1→10+')
  ) AS t(question_code, question_text, question_type, category, priority,
         problem_code, root_cause_code, difficulty_level, primary_stage_group)
  JOIN new_problems np ON np.problem_code = t.problem_code
  JOIN new_root_causes nr ON nr.root_cause_code = t.root_cause_code
  CROSS JOIN z
  RETURNING question_id, question_code
),

-- 4. QUESTION TAG LINKS -------------------------------------------------------
new_tag_links AS (
  INSERT INTO question_tag_mapping (question_id, tag_id)
  SELECT nq.question_id, qt.tag_id
  FROM (VALUES
  ('S0-SPF-001', 'icp'),
  ('S0-SPF-002', 'icp'),
  ('S0-SPF-003', 'icp'),
  ('S0-SPF-004', 'icp'),
  ('S0-SPF-005', 'icp'),
  ('S0-SPF-006', 'willingness-to-pay'),
  ('S0-SPF-007', 'willingness-to-pay'),
  ('S0-SPF-008', 'willingness-to-pay'),
  ('S0-SPF-009', 'willingness-to-pay'),
  ('S0-SPF-010', 'willingness-to-pay'),
  ('S0-SPF-011', 'technical-quality'),
  ('S0-SPF-012', 'technical-quality'),
  ('S0-SPF-013', 'technical-quality'),
  ('S0-SPF-014', 'technical-quality'),
  ('S0-SPF-015', 'icp'),
  ('S01-SPF-001', 'technical-quality'),
  ('S01-SPF-002', 'technical-quality'),
  ('S01-SPF-003', 'technical-quality'),
  ('S01-SPF-004', 'technical-quality'),
  ('S01-SPF-005', 'technical-quality'),
  ('S01-SPF-006', 'technical-quality'),
  ('S01-SPF-007', 'technical-quality'),
  ('S01-SPF-008', 'technical-quality'),
  ('S01-SPF-009', 'technical-quality'),
  ('S01-SPF-010', 'technical-quality'),
  ('S01-SPF-011', 'technical-quality'),
  ('S01-SPF-012', 'technical-quality'),
  ('S01-SPF-013', 'willingness-to-pay'),
  ('S01-SPF-014', 'willingness-to-pay'),
  ('S01-SPF-015', 'willingness-to-pay'),
  ('S01-SPF-016', 'willingness-to-pay'),
  ('S01-SPF-017', 'technical-quality'),
  ('S01-SPF-018', 'technical-quality'),
  ('S01-SPF-019', 'technical-quality'),
  ('S01-SPF-020', 'technical-quality'),
  ('S10-SPF-001', 'willingness-to-pay'),
  ('S10-SPF-002', 'willingness-to-pay'),
  ('S10-SPF-003', 'willingness-to-pay'),
  ('S10-SPF-004', 'willingness-to-pay'),
  ('S10-SPF-005', 'technical-quality'),
  ('S10-SPF-006', 'technical-quality'),
  ('S10-SPF-007', 'technical-quality'),
  ('S10-SPF-008', 'technical-quality'),
  ('S10-SPF-009', 'technical-quality'),
  ('S10-SPF-010', 'technical-quality'),
  ('S10-SPF-011', 'technical-quality'),
  ('S10-SPF-012', 'technical-quality'),
  ('S10-SPF-013', 'technical-quality'),
  ('S10-SPF-014', 'technical-quality'),
  ('S10-SPF-015', 'technical-quality'),
  ('S10-SPF-016', 'technical-quality'),
  ('S10-SPF-017', 'technical-quality'),
  ('S10-SPF-018', 'technical-quality'),
  ('S10-SPF-019', 'technical-quality'),
  ('S10-SPF-020', 'willingness-to-pay'),
  ('S10-SPF-021', 'willingness-to-pay'),
  ('S10-SPF-022', 'willingness-to-pay'),
  ('S10-SPF-023', 'willingness-to-pay'),
  ('S10-SPF-024', 'technical-quality'),
  ('S10-SPF-025', 'technical-quality')
  ) AS t(question_code, tag_name)
  JOIN new_questions nq ON nq.question_code = t.question_code
  JOIN question_tags qt ON qt.tag_name = t.tag_name
  RETURNING question_id
),

-- 5. INTERVENTIONS ------------------------------------------------------------
new_interventions AS (
  INSERT INTO interventions
    (intervention_code, section, problem_id, root_cause_ids, stage_relevance,
     capability_domain, design_principles, immediate_next_steps,
     recommended_frameworks, industry_relevance, secondary_root_cause_ids)
  SELECT t.intervention_code, t.section, np.problem_id, t.root_cause_ids,
         t.stage_relevance, t.capability_domain,
         '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb,
         t.immediate_next_steps, t.recommended_frameworks,
         '["sports_fitness"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-SPF-001', 'Ideation — Sports Client Clarity', 'SPF-001', '["RC-SPF-001", "RC-SPF-002"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Pick one member type and one fitness level or goal to design for.", "Write down what you will not try to serve for now.", "Build the experience specifically around that member."]'::jsonb, '[{"name": "One Member, One Goal", "brief": "Designing for a specific member instead of anyone who wants fitness."}]'::jsonb),
  ('INT-SPF-002', 'Ideation — Sports Client Clarity', 'SPF-001', '["RC-SPF-003", "RC-SPF-005"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Build a class or programme mix around one clear journey.", "Stop adding offerings that do not fit the theme.", "Aim to be excellent for your chosen member, not average for everyone."]'::jsonb, '[{"name": "One Theme, Not Everything", "brief": "A coherent programme instead of a scattered mix trying to please everyone."}]'::jsonb),
  ('INT-SPF-003', 'Ideation — Sports Client Clarity', 'SPF-001', '["RC-SPF-004"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Talk to 10 real potential members in your chosen segment.", "Ask what would actually make them join and stay.", "Adjust your offer around their answers."]'::jsonb, '[{"name": "Talk to Real Prospective Members", "brief": "Validating the offer with real conversations before building further."}]'::jsonb),
  ('INT-SPF-004', 'Ideation — Sports Session Cost Reality', 'SPF-002', '["RC-SPF-006", "RC-SPF-007"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Build a true cost sheet for one class or session.", "Include space, equipment and utilities, not just trainer pay.", "Compare that total against your planned price."]'::jsonb, '[{"name": "True Cost Per Session", "brief": "A real cost that includes space and equipment, not just trainer pay."}]'::jsonb),
  ('INT-SPF-005', 'Ideation — Sports Session Cost Reality', 'SPF-002', '["RC-SPF-008", "RC-SPF-009", "RC-SPF-010"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Count no shows and cancellations as real lost revenue.", "Price from your own cost, not competitor rates.", "Calculate the attendance needed to break even."]'::jsonb, '[{"name": "Price and Break Even From Real Cost", "brief": "Pricing and break even math built from real numbers, not guesses."}]'::jsonb),
  ('INT-SPF-006', 'Ideation — Sports Membership Math', 'SPF-003', '["RC-SPF-011", "RC-SPF-012"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Calculate the number of paying members needed to break even monthly.", "Plan capacity around that number, not the other way round.", "Revisit the number as pricing or costs change."]'::jsonb, '[{"name": "Calculate Your Break Even Membership", "brief": "Sizing the business around a real membership target."}]'::jsonb),
  ('INT-SPF-007', 'Ideation — Sports Membership Math', 'SPF-003', '["RC-SPF-013", "RC-SPF-014"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Run a test period before committing to the full facility.", "Track a real signup rate during the test.", "Use that data instead of assuming members will show up."]'::jsonb, '[{"name": "Test Before Full Commitment", "brief": "A trial period to learn real signup rates before scaling up."}]'::jsonb),
  ('INT-SPF-008', 'Ideation — Sports Format and Location Clarity', 'SPF-004', '["RC-SPF-015", "RC-SPF-017"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Test the format or location on a small scale first.", "Confirm real demand before signing a lease.", "Only commit fully once the test proves out."]'::jsonb, '[{"name": "Test the Format Small First", "brief": "A low cost trial before committing to a lease or location."}]'::jsonb),
  ('INT-SPF-009', 'Ideation — Sports Format and Location Clarity', 'SPF-004', '["RC-SPF-016", "RC-SPF-018"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Check real foot traffic or catchment demand before committing.", "Do not assume a good workout format markets itself.", "Base the decision on evidence, not rent price alone."]'::jsonb, '[{"name": "Check Real Demand First", "brief": "Evidence of actual catchment demand instead of assuming quality is enough."}]'::jsonb),
  ('INT-SPF-010', 'Validation to Traction — Sports Member Retention', 'SPF-005', '["RC-SPF-019", "RC-SPF-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Build a structured onboarding process for new members.", "Check in during the first few weeks specifically.", "Track whether early engagement improves as a result."]'::jsonb, '[{"name": "Structured Member Onboarding", "brief": "A deliberate first weeks experience instead of leaving new members to figure it out."}]'::jsonb),
  ('INT-SPF-011', 'Validation to Traction — Sports Member Retention', 'SPF-005', '["RC-SPF-020", "RC-SPF-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Track attendance drop off before renewal comes up.", "Reach out to a member showing disengagement early.", "Never let a cancellation be the first sign of a problem."]'::jsonb, '[{"name": "Catch Disengagement Early", "brief": "Tracking attendance so a cancellation is not the first signal."}]'::jsonb),
  ('INT-SPF-012', 'Validation to Traction — Sports Instructor Turnover', 'SPF-006', '["RC-SPF-023", "RC-SPF-025"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Build a standard onboarding process for new instructors.", "Set a consistent quality standard across all classes.", "Use it to reduce variation by who teaches."]'::jsonb, '[{"name": "Standard Instructor Onboarding", "brief": "Consistent training so class quality does not depend on who teaches."}]'::jsonb),
  ('INT-SPF-013', 'Validation to Traction — Sports Instructor Turnover', 'SPF-006', '["RC-SPF-024", "RC-SPF-026"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Build member loyalty to the facility, not just to one trainer.", "Recruit instructors ahead of need, not reactively.", "Introduce members to more than one instructor over time."]'::jsonb, '[{"name": "Shift Loyalty to the Facility", "brief": "Reducing the risk that one trainer leaving takes members with them."}]'::jsonb),
  ('INT-SPF-014', 'Validation to Traction — Sports Facility Maintenance', 'SPF-007', '["RC-SPF-027", "RC-SPF-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Build a scheduled maintenance programme for equipment and facility.", "Service on the schedule, not after failure.", "Track what breaks most often and address it specifically."]'::jsonb, '[{"name": "Scheduled Maintenance", "brief": "Planned servicing instead of waiting for equipment to fail."}]'::jsonb),
  ('INT-SPF-015', 'Validation to Traction — Sports Facility Maintenance', 'SPF-007', '["RC-SPF-029", "RC-SPF-030"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Set up regular staff inspection ahead of member complaints.", "Set aside a budget for equipment replacement.", "Track equipment age against expected lifespan."]'::jsonb, '[{"name": "Inspect Ahead of Complaints, Budget Replacement", "brief": "Staff catching issues first, with money set aside to replace aging equipment."}]'::jsonb),
  ('INT-SPF-016', 'Validation to Traction — Sports Seasonal Demand', 'SPF-008', '["RC-SPF-031", "RC-SPF-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Adjust staffing levels to match known seasonal demand.", "Plan cash flow around predictable slow periods in advance.", "Build a reserve ahead of the low season."]'::jsonb, '[{"name": "Plan Staffing and Cash for the Season", "brief": "Adjusting resources ahead of known demand swings, not reacting to them."}]'::jsonb),
  ('INT-SPF-017', 'Validation to Traction — Sports Seasonal Demand', 'SPF-008', '["RC-SPF-033", "RC-SPF-034"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Build a promotional plan specifically for off peak months.", "Adjust pricing or programming to fit seasonal demand.", "Measure whether it fills capacity during slow periods."]'::jsonb, '[{"name": "Promote and Adjust for the Off Season", "brief": "Deliberate seasonal programming instead of running the same offer year round."}]'::jsonb),
  ('INT-SPF-018', 'Validation to Traction — Sports Liability Management', 'SPF-009', '["RC-SPF-035", "RC-SPF-036"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Collect and update waivers consistently for every member and activity.", "Review insurance coverage against what you actually do.", "Fix any gap between coverage and real activities."]'::jsonb, '[{"name": "Consistent Waivers, Reviewed Insurance", "brief": "Legal protection that actually matches the activities being run."}]'::jsonb),
  ('INT-SPF-019', 'Validation to Traction — Sports Liability Management', 'SPF-009', '["RC-SPF-037", "RC-SPF-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Build a standard incident response process.", "Train every staff member on emergency response.", "Test the process before it is needed for real."]'::jsonb, '[{"name": "Standard Incident Response and Training", "brief": "A tested process and trained staff ready before an emergency happens."}]'::jsonb),
  ('INT-SPF-020', 'Growth to Maturity — Sports Account Concentration', 'SPF-010', '["RC-SPF-039", "RC-SPF-041"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Calculate the revenue share of your top accounts.", "Set a ceiling and build a pipeline of individual members and new accounts.", "Review the share every quarter."]'::jsonb, '[{"name": "Cap Account Concentration", "brief": "Measuring dependence and building beyond the dominant few accounts."}]'::jsonb),
  ('INT-SPF-021', 'Growth to Maturity — Sports Account Concentration', 'SPF-010', '["RC-SPF-040", "RC-SPF-042"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Separate programming decisions from any single dominant account.", "Work out your real margin on that account after their terms.", "Design offerings for your wider membership, not just one client."]'::jsonb, '[{"name": "Design for the Membership, Not One Account", "brief": "Keeping programming grounded in the wider member base, not one dominant client."}]'::jsonb),
  ('INT-SPF-022', 'Growth to Maturity — Sports Multi Site Consistency', 'SPF-011', '["RC-SPF-043", "RC-SPF-046"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write down how the original site actually runs.", "Use that document to set up every new site.", "Do not open another until it exists."]'::jsonb, '[{"name": "Systemise Before You Expand", "brief": "Documenting the first site so the next one can copy it."}]'::jsonb),
  ('INT-SPF-023', 'Growth to Maturity — Sports Multi Site Consistency', 'SPF-011', '["RC-SPF-044", "RC-SPF-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Use the same standards and equipment at every location.", "Spend time away from the original site and see what breaks.", "Fix that before opening further sites."]'::jsonb, '[{"name": "Same Standards, No Single Point of Failure", "brief": "Common standards and a site that runs without one specific person present."}]'::jsonb),
  ('INT-SPF-024', 'Growth to Maturity — Sports Compliance Operations', 'SPF-012', '["RC-SPF-047", "RC-SPF-048"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Build one calendar covering every certification and inspection.", "Set reminders well ahead of each expiry.", "Review it monthly."]'::jsonb, '[{"name": "One Compliance Calendar", "brief": "Every certification and inspection deadline in one dated place."}]'::jsonb),
  ('INT-SPF-025', 'Growth to Maturity — Sports Compliance Operations', 'SPF-012', '["RC-SPF-049", "RC-SPF-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Catch lapses before they cause a problem, not after.", "Fix safety incidents permanently instead of letting them repeat.", "Train a second person on the whole compliance picture."]'::jsonb, '[{"name": "Catch Lapses Early, Fix Permanently", "brief": "Proactive tracking and permanent fixes instead of repeated incidents."}]'::jsonb),
  ('INT-SPF-026', 'Growth to Maturity — Sports Technology Gap', 'SPF-013', '["RC-SPF-051", "RC-SPF-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Product Design', '["Give members a way to book and check in digitally.", "Budget for the technology investment as its own line item.", "Start with the simplest version that removes manual booking."]'::jsonb, '[{"name": "Digitise Booking and Check In", "brief": "A basic digital system instead of manual processes members increasingly expect to skip."}]'::jsonb),
  ('INT-SPF-027', 'Growth to Maturity — Sports Technology Gap', 'SPF-013', '["RC-SPF-052"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Start capturing basic data on member behaviour and attendance.", "Use it to spot disengagement and demand patterns.", "Act on what the data actually shows."]'::jsonb, '[{"name": "Start Capturing Member Data", "brief": "Basic behavioural data to inform retention and programming decisions."}]'::jsonb),
  ('INT-SPF-028', 'Growth to Maturity — Sports Defensibility', 'SPF-014', '["RC-SPF-054", "RC-SPF-056"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Develop a proprietary method or format members cannot get elsewhere.", "Make it central to the member experience, not a side feature.", "Use it as the reason to choose you over a competitor."]'::jsonb, '[{"name": "Build a Proprietary Method", "brief": "An owned format or method that a competitor cannot simply copy."}]'::jsonb),
  ('INT-SPF-029', 'Growth to Maturity — Sports Defensibility', 'SPF-014', '["RC-SPF-055"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Track how often members leave for a marginally cheaper competitor.", "Build a case for value beyond price.", "Compete on community and results, not just cost."]'::jsonb, '[{"name": "Compete on Value, Not Just Price", "brief": "Shifting retention efforts away from price as the main lever."}]'::jsonb),
  ('INT-SPF-030', 'Growth to Maturity — Sports Compensation Scaling', 'SPF-015', '["RC-SPF-057", "RC-SPF-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Rebuild your pay structure for the current size of your roster.", "Define a clear path for raises and advancement.", "Apply it consistently across every trainer."]'::jsonb, '[{"name": "Rebuild the Pay Structure", "brief": "A compensation model designed for the current roster, not the original handful."}]'::jsonb),
  ('INT-SPF-031', 'Growth to Maturity — Sports Compensation Scaling', 'SPF-015', '["RC-SPF-058", "RC-SPF-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Check whether top trainers are paid in line with revenue they generate.", "Track compensation cost against revenue growth.", "Adjust pay before the gap causes a departure."]'::jsonb, '[{"name": "Align Pay With Revenue Generated", "brief": "Making sure compensation growth tracks revenue, and top performers are paid accordingly."}]'::jsonb),
  ('INT-SPF-032', 'Ideation — Sports Membership Math', 'SPF-003', '["RC-SPF-061"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Research what signup rate a comparable facility has actually achieved.", "Use that as a realistic planning baseline, not a guess.", "Adjust your break even timeline around it."]'::jsonb, '[{"name": "Use a Real Comparable Signup Rate", "brief": "Planning around researched numbers, not an optimistic assumption."}]'::jsonb),
  ('INT-SPF-033', 'Validation to Traction — Sports Member Retention', 'SPF-005', '["RC-SPF-063"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Build a simple referral programme for existing members.", "Make it easy for members to bring a friend.", "Track how much new signups come from referrals."]'::jsonb, '[{"name": "Build a Referral Programme", "brief": "Turning existing members into a systematic source of new ones."}]'::jsonb),
  ('INT-SPF-034', 'Growth to Maturity — Sports Multi Site Consistency', 'SPF-011', '["RC-SPF-064"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Set up cross training between locations.", "Let staff learn from how other sites operate.", "Use it to spread best practice, not just cover shifts."]'::jsonb, '[{"name": "Cross Train Across Locations", "brief": "Staff learning from other sites, not just working in isolation."}]'::jsonb)
  ) AS t(intervention_code, section, problem_code, root_cause_ids, stage_relevance,
         capability_domain, immediate_next_steps, recommended_frameworks)
  JOIN new_problems np ON np.problem_code = t.problem_code
  RETURNING intervention_id
)
SELECT
  (SELECT COUNT(*) FROM new_problems)     AS problems_inserted,      -- expect 15
  (SELECT COUNT(*) FROM new_root_causes)  AS root_causes_inserted,   -- expect 66
  (SELECT COUNT(*) FROM new_questions)    AS questions_inserted,     -- expect 60
  (SELECT COUNT(*) FROM new_tag_links)    AS tag_links_inserted,     -- expect 60
  (SELECT COUNT(*) FROM new_interventions) AS interventions_inserted;-- expect 34

-- ============================================================================
-- After running, the single result row above must read:  15 | 66 | 60 | 60 | 34
-- If any number differs, something did not link -- roll back and check.
-- ============================================================================"""),
        ('Retail', 'retail', 'RTL', {'root_causes_inserted': 68}, r"""-- ============================================================================
-- Ally :: Industry seed -- RETAIL (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 68 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: retail
--
-- COUNTS   : 68 root causes, not the usual 66 (two small top-up passes
--            covering competitor price checks, seasonal demand planning,
--            regular stock audits, cross training between locations, and
--            periodic account/location prioritisation). Every row is
--            properly linked and every problem has intervention coverage.
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (RTL-001, RC-RTL-014, S0-RTL-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (inventory balance, channel consistency, staff
--            turnover, discount dependency, supplier dependency) starts at
--            Stage 0->1; revenue concentration, multi site consistency,
--            working capital, loss prevention, platform dependence and
--            defensibility at Stage 1->10+.
-- ============================================================================

WITH z AS (
  SELECT ('[' || array_to_string(array_fill(0, ARRAY[1536]), ',') || ']')::vector AS v
),

-- 1. PROBLEMS -----------------------------------------------------------------
new_problems AS (
  INSERT INTO problems
    (problem_code, problem_name, description, category, subcategory, layer,
     pillar_id, severity_min, severity_max, symptoms, industry_relevance,
     related_problem_ids, embedding)
  SELECT t.problem_code, t.problem_name, t.description, t.category, t.subcategory,
         t.layer, t.pillar_id, t.severity_min, t.severity_max, t.symptoms,
         t.industry_relevance, '[]'::jsonb, z.v
  FROM (VALUES
  ('RTL-001', 'No Clear Customer or Category Chosen', 'The store or catalogue tries to cover several unrelated customer types and categories at once, so nothing about the offer is distinctive.', 'Idea & Validation', 'Retail Customer Clarity', 'external', 2, 4, 8, '["Target customer described as everyone", "Product categories chosen without a clear theme", "No idea where this customer currently shops", "Assortment decided by what suppliers offer, not what customers want", "No conversation with a real target customer"]'::jsonb, '["retail"]'::jsonb),
  ('RTL-002', 'Real Cost of Getting a Product to the Shelf Not Worked Out', 'Landed cost, shrinkage, returns and holding cost are not built into the price, so nobody knows the true margin.', 'Idea & Validation', 'Retail Margin Reality', 'external', 4, 5, 9, '["Only the supplier price counted as cost", "Shrinkage and damage not factored in", "Returns cost not counted", "Cost of holding unsold stock ignored", "Price set by looking at competitors only"]'::jsonb, '["retail"]'::jsonb),
  ('RTL-003', 'No Idea How Much Inventory to Actually Buy', 'Stock is ordered on guesswork, with no read on how fast items will actually sell.', 'Idea & Validation', 'Retail Demand Forecasting Basics', 'external', 3, 5, 9, '["Order quantities based on gut feel", "No sales history to work from", "No plan for slow moving stock", "Assuming popular items will always be available from suppliers", "No test order before a full commitment"]'::jsonb, '["retail"]'::jsonb),
  ('RTL-004', 'Location or Channel Chosen Without Testing Demand', 'A store location or primary sales channel was picked before confirming that the target customer actually shows up there.', 'Idea & Validation', 'Retail Channel and Location Clarity', 'external', 3, 5, 9, '["Location or channel chosen on convenience, not evidence", "No footfall or traffic data checked", "No small test before committing to a lease or channel", "Assuming a good product will draw its own traffic", "No conversation with a real customer about where they shop"]'::jsonb, '["retail"]'::jsonb),
  ('RTL-005', 'Stockouts and Overstock Happening at the Same Time', 'Popular items run out while slow movers pile up, because ordering is not matched to what actually sells.', 'Operations & Systems', 'Retail Inventory Balance', 'external', 4, 6, 9, '["Bestsellers running out regularly", "Slow movers taking up shelf and cash", "No system tracking sell through rate", "Reordering done reactively, not on a schedule", "Cash tied up in the wrong stock"]'::jsonb, '["retail"]'::jsonb),
  ('RTL-006', 'Online and In Store Experience Not Connected', 'A customer buying online and one buying in store get inconsistent stock, pricing or service, and returns across channels are confusing.', 'Operations & Systems', 'Retail Channel Consistency', 'external', 3, 6, 9, '["Stock levels not visible across channels", "Pricing inconsistent between online and store", "Returns from one channel hard to process in another", "No single view of a customer across channels", "Promotions not synced between channels"]'::jsonb, '["retail"]'::jsonb),
  ('RTL-007', 'Staff Turnover Resetting Customer Experience', 'Frontline staff leave frequently, and each departure takes product knowledge and service quality with it.', 'Team & Leadership', 'Retail Staff Turnover', 'external', 3, 6, 9, '["High frontline staff turnover", "No standard training for new staff", "Customer experience varying by who is working", "Product knowledge lost when staff leave", "Recruitment happening reactively"]'::jsonb, '["retail"]'::jsonb),
  ('RTL-008', 'Discounting Becoming the Default Way to Sell', 'Promotions and markdowns are used so often that customers wait for a sale, and margin quietly erodes.', 'Financial Management', 'Retail Discount Dependency', 'external', 4, 6, 9, '["Discounting used to move most inventory", "Customers waiting for the next sale", "Margin falling without anyone tracking why", "No clear promotion calendar or strategy", "Full price sales becoming rare"]'::jsonb, '["retail"]'::jsonb),
  ('RTL-009', 'Supplier Dependency Creating Fragile Supply', 'Key products come from one or two suppliers, so a delay, price rise or quality issue on their end disrupts the whole range.', 'Operations & Systems', 'Retail Supplier Dependency', 'external', 3, 6, 9, '["Key products sourced from a single supplier", "No backup supplier identified", "Supplier price increases passed through unmanaged", "Quality issues traced back to one source repeatedly", "No visibility into supplier lead times"]'::jsonb, '["retail"]'::jsonb),
  ('RTL-010', 'Revenue Concentrated in a Few Large Accounts or Locations', 'A handful of wholesale accounts or store locations generate most revenue, so their loss would be severe and they set the terms.', 'Sales & Revenue', 'Retail Revenue Concentration', 'external', 4, 7, 10, '["Most revenue from a few accounts or locations", "Terms dictated by the largest account", "No pipeline of new accounts or sites", "Losing one account or location would threaten the business", "Expansion decisions driven by one relationship"]'::jsonb, '["retail"]'::jsonb),
  ('RTL-011', 'New Store or Site Does Not Match the First', 'A second location or new channel produces different sales and experience results from the original, and nothing was systemised before expanding.', 'Operations & Systems', 'Retail Multi Site Consistency', 'external', 3, 6, 9, '["New location underperforming the original", "Nothing written down to replicate the first site", "Different suppliers or standards per location", "Founder still needed at the original site", "Customer experience differing across sites"]'::jsonb, '["retail"]'::jsonb),
  ('RTL-012', 'Working Capital Locked in Growing Inventory', 'As the range and store count grow, more and more cash sits in stock, straining the ability to fund anything else.', 'Financial Management', 'Retail Working Capital', 'external', 4, 7, 10, '["Inventory growing faster than sales", "Cash increasingly tied up in stock across locations", "No inventory turnover target being tracked", "Growth funded by squeezing supplier terms", "No credit facility sized to the real need"]'::jsonb, '["retail"]'::jsonb),
  ('RTL-013', 'Loss Prevention and Shrinkage Rising With Scale', 'As headcount, locations and transaction volume grow, theft, fraud and process errors increase faster than the business can absorb.', 'Operations & Systems', 'Retail Loss Prevention', 'external', 3, 6, 9, '["Shrinkage rate rising with scale", "No consistent loss prevention process across locations", "Internal theft not systematically detected", "Point of sale errors not reconciled regularly", "No accountability for shrinkage by location"]'::jsonb, '["retail"]'::jsonb),
  ('RTL-014', 'E-commerce and Marketplace Rules Changing the Economics', 'Platform fees, algorithm changes and marketplace policies increasingly determine margin and visibility, and the business has little control over them.', 'Strategy & Planning', 'Retail Platform Dependence', 'external', 2, 6, 10, '["Growing share of sales through a marketplace or platform", "Platform fees eating into margin", "Visibility dependent on algorithm changes outside your control", "No direct customer relationship independent of the platform", "Policy changes discovered after they affect sales"]'::jsonb, '["retail"]'::jsonb),
  ('RTL-015', 'Nothing Differentiates This From Any Other Retailer', 'Products and prices are easily matched by competitors, and nothing built here creates a reason to choose this business specifically.', 'Strategy & Planning', 'Retail Defensibility', 'external', 2, 6, 10, '["Assortment easily copied by competitors", "Price the main basis of competition", "No loyalty or repeat purchase advantage", "No private label or exclusive product", "No community or brand connection beyond price"]'::jsonb, '["retail"]'::jsonb)
  ) AS t(problem_code, problem_name, description, category, subcategory, layer,
         pillar_id, severity_min, severity_max, symptoms, industry_relevance), z
  RETURNING problem_id, problem_code
),

-- 2. ROOT CAUSES --------------------------------------------------------------
new_root_causes AS (
  INSERT INTO root_causes
    (root_cause_code, root_cause_name, explanation, problem_id, layer,
     root_cause_category, confidence_weight, primary_stage_group,
     industry_relevance, embedding)
  SELECT t.root_cause_code, t.root_cause_name, t.explanation, np.problem_id,
         t.layer, t.root_cause_category, t.confidence_weight,
         t.primary_stage_group, '["retail"]'::jsonb, z.v
  FROM (VALUES
  ('RC-RTL-001', 'Target Customer Described as Everyone', 'No specific customer type has been chosen to serve.', 'RTL-001', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-RTL-002', 'Categories Chosen Without a Clear Theme', 'Product ranges do not connect around a single customer need.', 'RTL-001', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-RTL-003', 'Assortment Driven by Supplier Offer', 'What gets stocked follows what suppliers push, not customer demand.', 'RTL-001', 'external', 'Behavioural', 0.68, 'Stage 0'),
  ('RC-RTL-004', 'Where the Customer Shops Today Is Unknown', 'How this customer currently buys has not been studied.', 'RTL-001', 'external', 'Knowledge', 0.67, 'Stage 0'),
  ('RC-RTL-005', 'No Conversation With a Real Target Customer', 'Nobody who would actually buy has been spoken to.', 'RTL-001', 'external', 'Behavioural', 0.66, 'Stage 0'),
  ('RC-RTL-006', 'Only Supplier Price Counted as Cost', 'The cost is taken as the price paid to the supplier alone.', 'RTL-002', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-RTL-007', 'Shrinkage and Damage Not Factored In', 'Loss from theft, breakage or spoilage is missing from the numbers.', 'RTL-002', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-RTL-008', 'Returns Cost Not Counted', 'What it costs to process and absorb returns is left out.', 'RTL-002', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-RTL-009', 'Cost of Holding Unsold Stock Ignored', 'Capital and storage cost tied up in inventory is not counted.', 'RTL-002', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-RTL-010', 'Price Set by Looking at Competitors', 'Pricing copies others without knowing own true cost.', 'RTL-002', 'external', 'Behavioural', 0.66, 'Stage 0'),
  ('RC-RTL-011', 'Order Quantities Based on Gut Feel', 'How much to buy is decided without data behind it.', 'RTL-003', 'external', 'Behavioural', 0.72, 'Stage 0'),
  ('RC-RTL-012', 'No Sales History to Work From', 'There is no past data to base ordering decisions on.', 'RTL-003', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-RTL-013', 'No Plan for Slow Moving Stock', 'Nothing has been decided about items that do not sell.', 'RTL-003', 'external', 'Strategic', 0.69, 'Stage 0'),
  ('RC-RTL-014', 'No Test Order Before Full Commitment', 'A small trial was skipped in favour of a full order.', 'RTL-003', 'external', 'Behavioural', 0.68, 'Stage 0'),
  ('RC-RTL-015', 'Location or Channel Chosen on Convenience', 'The decision was made for ease, not evidence of demand.', 'RTL-004', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-RTL-016', 'No Footfall or Traffic Data Checked', 'Real customer flow at the location or channel was never measured.', 'RTL-004', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-RTL-017', 'No Small Test Before Committing', 'A lease or channel was committed to without a low cost trial first.', 'RTL-004', 'external', 'Strategic', 0.69, 'Stage 0'),
  ('RC-RTL-018', 'Assuming a Good Product Draws Its Own Traffic', 'Believing quality alone will bring customers to a location or channel.', 'RTL-004', 'external', 'Psychological', 0.67, 'Stage 0'),
  ('RC-RTL-019', 'No System Tracking Sell Through Rate', 'How fast items actually sell is not measured.', 'RTL-005', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-RTL-020', 'Reordering Done Reactively', 'Stock is reordered only when someone notices it is gone.', 'RTL-005', 'external', 'Behavioural', 0.71, 'Stage 0→1'),
  ('RC-RTL-021', 'Bestsellers and Slow Movers Not Distinguished', 'No system separates what should be reordered from what should not.', 'RTL-005', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-RTL-022', 'Cash Tied Up in the Wrong Stock', 'Money sits in items that are not moving.', 'RTL-005', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-RTL-023', 'Stock Levels Not Visible Across Channels', 'Online and store do not share a real time view of inventory.', 'RTL-006', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-RTL-024', 'Pricing Inconsistent Between Channels', 'The same item costs different amounts depending on where it is bought.', 'RTL-006', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-RTL-025', 'No Single View of a Customer Across Channels', 'A customer buying in both channels looks like two different people.', 'RTL-006', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-RTL-026', 'Returns Hard to Process Across Channels', 'A return does not move cleanly between online and in store.', 'RTL-006', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-RTL-027', 'No Standard Training for New Staff', 'New hires learn informally with no defined process.', 'RTL-007', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-RTL-028', 'Product Knowledge Lost on Departure', 'What a staff member knew leaves with them.', 'RTL-007', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-RTL-029', 'Customer Experience Varying by Staff Member', 'Service quality depends on who happens to be working.', 'RTL-007', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-RTL-030', 'Recruitment Happening Reactively', 'Hiring starts only once a gap becomes urgent.', 'RTL-007', 'external', 'Behavioural', 0.68, 'Stage 0→1'),
  ('RC-RTL-031', 'Discounting Used to Move Most Inventory', 'Sales rely on markdowns rather than full price demand.', 'RTL-008', 'external', 'Behavioural', 0.73, 'Stage 0→1'),
  ('RC-RTL-032', 'No Clear Promotion Calendar or Strategy', 'Discounts happen ad hoc rather than by plan.', 'RTL-008', 'external', 'Strategic', 0.71, 'Stage 0→1'),
  ('RC-RTL-033', 'Customers Trained to Wait for a Sale', 'Repeated discounting has taught customers to delay purchase.', 'RTL-008', 'external', 'Behavioural', 0.70, 'Stage 0→1'),
  ('RC-RTL-034', 'Margin Erosion Not Tracked', 'Nobody is measuring how much discounting is costing.', 'RTL-008', 'external', 'Knowledge', 0.69, 'Stage 0→1'),
  ('RC-RTL-035', 'Key Products From a Single Supplier', 'Critical items have only one source.', 'RTL-009', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-RTL-036', 'No Backup Supplier Identified', 'Nothing has been arranged if the main supplier fails.', 'RTL-009', 'external', 'Strategic', 0.71, 'Stage 0→1'),
  ('RC-RTL-037', 'Supplier Price Increases Passed Through Unmanaged', 'Cost rises are absorbed or passed on without negotiation.', 'RTL-009', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-RTL-038', 'No Visibility Into Supplier Lead Times', 'How long a supplier actually takes to deliver is unknown.', 'RTL-009', 'external', 'Knowledge', 0.68, 'Stage 0→1'),
  ('RC-RTL-039', 'Most Revenue From a Few Accounts or Locations', 'A handful of sources carry most of the business.', 'RTL-010', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-RTL-040', 'Terms Dictated by the Largest Account', 'The dominant account or location sets the conditions.', 'RTL-010', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-RTL-041', 'No Pipeline of New Accounts or Sites', 'Nothing is being built that could replace a lost source.', 'RTL-010', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-RTL-042', 'Expansion Driven by One Relationship', 'Growth decisions follow a single partner rather than a plan.', 'RTL-010', 'external', 'Behavioural', 0.69, 'Stage 1→10+'),
  ('RC-RTL-043', 'Nothing Written Down to Replicate the First Site', 'The original location runs on knowledge nobody has recorded.', 'RTL-011', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-RTL-044', 'Founder Still Needed at the Original Site', 'The first location cannot run without the founder present.', 'RTL-011', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-RTL-045', 'Different Suppliers or Standards Per Location', 'Each site buys and operates differently.', 'RTL-011', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-RTL-046', 'Expanded Before the First Was Systemised', 'A second site opened before the first was repeatable.', 'RTL-011', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-RTL-047', 'Inventory Growing Faster Than Sales', 'Stock is expanding out of proportion to actual demand.', 'RTL-012', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-RTL-048', 'No Inventory Turnover Target Tracked', 'Nobody has set or measured a target for how fast stock should move.', 'RTL-012', 'external', 'Knowledge', 0.71, 'Stage 1→10+'),
  ('RC-RTL-049', 'Growth Funded by Squeezing Supplier Terms', 'Expansion relies on stretching payment terms rather than real capital.', 'RTL-012', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-RTL-050', 'No Credit Facility Sized to Real Need', 'Financing has not been matched to the actual working capital gap.', 'RTL-012', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-RTL-051', 'Shrinkage Rate Rising With Scale', 'Loss increases faster than the business can absorb it.', 'RTL-013', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-RTL-052', 'No Consistent Loss Prevention Process', 'Each location handles loss prevention differently or not at all.', 'RTL-013', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-RTL-053', 'Internal Theft Not Systematically Detected', 'Nothing is set up to catch theft from within.', 'RTL-013', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-RTL-054', 'No Accountability for Shrinkage by Location', 'Nobody at each site owns the loss number.', 'RTL-013', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-RTL-055', 'Growing Share of Sales Through a Marketplace', 'Increasing dependence on a platform outside your control.', 'RTL-014', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-RTL-056', 'Platform Fees Eating Into Margin', 'What the platform charges is consuming an increasing share of profit.', 'RTL-014', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-RTL-057', 'No Direct Customer Relationship Independent of the Platform', 'The business does not own its own customer relationships.', 'RTL-014', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-RTL-058', 'Policy Changes Discovered After They Affect Sales', 'Platform rule changes are learned about only once revenue drops.', 'RTL-014', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-RTL-059', 'Assortment Easily Copied by Competitors', 'What is stocked can be replicated without much effort.', 'RTL-015', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-RTL-060', 'Price the Main Basis of Competition', 'Differentiation has collapsed into being cheaper.', 'RTL-015', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-RTL-061', 'No Loyalty or Repeat Purchase Advantage', 'Nothing keeps customers coming back beyond convenience.', 'RTL-015', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-RTL-062', 'No Private Label or Exclusive Product', 'Nothing sold here cannot be bought elsewhere.', 'RTL-015', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-RTL-063', 'No Idea What Competitors Charge for the Same Item', 'Pricing decisions are made without checking what similar retailers charge nearby.', 'RTL-002', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-RTL-064', 'No Plan for Seasonal Demand Swings', 'How demand changes across the year has not been factored into ordering.', 'RTL-003', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-RTL-065', 'No Regular Stock Audit Process', 'Physical counts are not reconciled against system records on any schedule.', 'RTL-005', 'external', 'Operational', 0.66, 'Stage 0→1'),
  ('RC-RTL-066', 'No Cross Training Between Locations', 'Staff at one site cannot easily cover or learn from another.', 'RTL-007', 'external', 'Operational', 0.66, 'Stage 0→1'),
  ('RC-RTL-067', 'No Regular Review of Which Accounts to Prioritise', 'Nobody periodically reassesses which accounts or locations deserve the most attention.', 'RTL-010', 'external', 'Operational', 0.66, 'Stage 1→10+'),
  ('RC-RTL-068', 'No Plan for Diversifying Beyond the Dominant Platform', 'Nothing has been decided about building presence on additional channels.', 'RTL-014', 'external', 'Strategic', 0.67, 'Stage 1→10+')
  ) AS t(root_cause_code, root_cause_name, explanation, problem_code, layer,
         root_cause_category, confidence_weight, primary_stage_group)
  JOIN new_problems np ON np.problem_code = t.problem_code
  CROSS JOIN z
  RETURNING root_cause_id, root_cause_code
),

-- 3. QUESTIONS ----------------------------------------------------------------
new_questions AS (
  INSERT INTO questions
    (question_code, question_text, question_type, category, priority,
     problem_id, root_cause_id, difficulty_level, primary_stage_group,
     industry_relevance, is_distress_tagged, embedding)
  SELECT t.question_code, t.question_text, t.question_type, t.category, t.priority,
         np.problem_id, nr.root_cause_id, t.difficulty_level, t.primary_stage_group,
         '["retail"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-RTL-001', 'Who exactly is your target customer?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-001', 'RC-RTL-001', 1, 'Stage 0'),
  ('S0-RTL-002', 'Do your product categories connect around one clear theme?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-001', 'RC-RTL-002', 1, 'Stage 0'),
  ('S0-RTL-003', 'Do you stock what suppliers offer or what customers ask for?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-001', 'RC-RTL-003', 2, 'Stage 0'),
  ('S0-RTL-004', 'Where does your target customer buy this kind of thing today?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-001', 'RC-RTL-004', 2, 'Stage 0'),
  ('S0-RTL-005', 'Have you spoken to a real customer who would actually buy from you?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-001', 'RC-RTL-005', 2, 'Stage 0'),
  ('S0-RTL-006', 'What does one unit actually cost you by the time it reaches the shelf?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-002', 'RC-RTL-006', 1, 'Stage 0'),
  ('S0-RTL-007', 'Have you accounted for shrinkage, damage and theft?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-002', 'RC-RTL-007', 2, 'Stage 0'),
  ('S0-RTL-008', 'Have you counted the cost of returns?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-002', 'RC-RTL-008', 2, 'Stage 0'),
  ('S0-RTL-009', 'Have you counted what it costs to hold unsold stock?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-002', 'RC-RTL-009', 2, 'Stage 0'),
  ('S0-RTL-010', 'Did you set your price from your own cost or from competitors?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-002', 'RC-RTL-010', 2, 'Stage 0'),
  ('S0-RTL-011', 'How did you decide how much stock to order?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-003', 'RC-RTL-011', 1, 'Stage 0'),
  ('S0-RTL-012', 'Do you have any sales history to base ordering on?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-003', 'RC-RTL-012', 2, 'Stage 0'),
  ('S0-RTL-013', 'What is your plan for stock that does not sell?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-003', 'RC-RTL-013', 2, 'Stage 0'),
  ('S0-RTL-014', 'Did you place a small test order before the full commitment?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-003', 'RC-RTL-014', 2, 'Stage 0'),
  ('S0-RTL-015', 'Did you check real footfall or traffic before committing to this location or channel?', 'open_text', 'Idea & Validation', 'CORE', 'RTL-004', 'RC-RTL-016', 1, 'Stage 0'),
  ('S01-RTL-001', 'How often do your bestsellers run out?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-005', 'RC-RTL-019', 2, 'Stage 0→1'),
  ('S01-RTL-002', 'How much of your shelf and cash is tied up in slow movers?', 'open_text', 'Financial Management', 'CORE', 'RTL-005', 'RC-RTL-022', 2, 'Stage 0→1'),
  ('S01-RTL-003', 'Do you reorder on a schedule or only when you notice something is gone?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-005', 'RC-RTL-020', 2, 'Stage 0→1'),
  ('S01-RTL-004', 'Is there a system that separates bestsellers from slow movers?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-005', 'RC-RTL-021', 2, 'Stage 0→1'),
  ('S01-RTL-005', 'Can you see your stock levels across every channel in real time?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-006', 'RC-RTL-023', 2, 'Stage 0→1'),
  ('S01-RTL-006', 'Does the same item cost the same online and in store?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-006', 'RC-RTL-024', 2, 'Stage 0→1'),
  ('S01-RTL-007', 'Can a customer return an online purchase in store, or vice versa, easily?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-006', 'RC-RTL-026', 2, 'Stage 0→1'),
  ('S01-RTL-008', 'Do you have one view of a customer across channels, or two separate ones?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-006', 'RC-RTL-025', 3, 'Stage 0→1'),
  ('S01-RTL-009', 'How many frontline staff have left in the last year?', 'open_text', 'Team & Leadership', 'CORE', 'RTL-007', 'RC-RTL-027', 2, 'Stage 0→1'),
  ('S01-RTL-010', 'How does a new staff member learn your products and standards?', 'open_text', 'Team & Leadership', 'CORE', 'RTL-007', 'RC-RTL-027', 2, 'Stage 0→1'),
  ('S01-RTL-011', 'Does customer experience change depending on who is working?', 'open_text', 'Team & Leadership', 'CORE', 'RTL-007', 'RC-RTL-029', 2, 'Stage 0→1'),
  ('S01-RTL-012', 'Do you recruit ahead of need, or only once someone has already left?', 'open_text', 'Team & Leadership', 'CORE', 'RTL-007', 'RC-RTL-030', 2, 'Stage 0→1'),
  ('S01-RTL-013', 'What share of your sales happen at full price versus discounted?', 'open_text', 'Financial Management', 'CORE', 'RTL-008', 'RC-RTL-031', 2, 'Stage 0→1'),
  ('S01-RTL-014', 'Do you have a planned promotion calendar, or do discounts happen ad hoc?', 'open_text', 'Financial Management', 'CORE', 'RTL-008', 'RC-RTL-032', 2, 'Stage 0→1'),
  ('S01-RTL-015', 'Do customers seem to wait for your next sale?', 'open_text', 'Sales & Revenue', 'CORE', 'RTL-008', 'RC-RTL-033', 2, 'Stage 0→1'),
  ('S01-RTL-016', 'Do you track how much discounting is costing you in margin?', 'open_text', 'Financial Management', 'CORE', 'RTL-008', 'RC-RTL-034', 3, 'Stage 0→1'),
  ('S01-RTL-017', 'Is there any product you can only get from one supplier?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-009', 'RC-RTL-035', 2, 'Stage 0→1'),
  ('S01-RTL-018', 'Do you have a backup supplier for your key products?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-009', 'RC-RTL-036', 2, 'Stage 0→1'),
  ('S01-RTL-019', 'When a supplier raises prices, how do you respond?', 'open_text', 'Financial Management', 'CORE', 'RTL-009', 'RC-RTL-037', 2, 'Stage 0→1'),
  ('S01-RTL-020', 'Do you know how long your suppliers actually take to deliver?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-009', 'RC-RTL-038', 2, 'Stage 0→1'),
  ('S10-RTL-001', 'What share of revenue comes from your top two or three accounts or locations?', 'open_text', 'Sales & Revenue', 'CORE', 'RTL-010', 'RC-RTL-039', 2, 'Stage 1→10+'),
  ('S10-RTL-002', 'Who sets the terms, you or your largest account?', 'open_text', 'Sales & Revenue', 'CORE', 'RTL-010', 'RC-RTL-040', 2, 'Stage 1→10+'),
  ('S10-RTL-003', 'If your largest account or location disappeared, how long could you continue?', 'open_text', 'Strategy & Planning', 'CORE', 'RTL-010', 'RC-RTL-041', 3, 'Stage 1→10+'),
  ('S10-RTL-004', 'Are your expansion decisions following a plan or one relationship?', 'open_text', 'Strategy & Planning', 'CORE', 'RTL-010', 'RC-RTL-042', 3, 'Stage 1→10+'),
  ('S10-RTL-005', 'Does your newest location match the performance of the first?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-011', 'RC-RTL-043', 2, 'Stage 1→10+'),
  ('S10-RTL-006', 'Is there anything written down that a new site could run from?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-011', 'RC-RTL-043', 2, 'Stage 1→10+'),
  ('S10-RTL-007', 'Can your original location run without you there?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-011', 'RC-RTL-044', 3, 'Stage 1→10+'),
  ('S10-RTL-008', 'Do all your locations use the same suppliers and standards?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-011', 'RC-RTL-045', 2, 'Stage 1→10+'),
  ('S10-RTL-009', 'Was your first site fully systemised before you opened the second?', 'open_text', 'Strategy & Planning', 'CORE', 'RTL-011', 'RC-RTL-046', 3, 'Stage 1→10+'),
  ('S10-RTL-010', 'Is your inventory growing faster than your sales?', 'open_text', 'Financial Management', 'CORE', 'RTL-012', 'RC-RTL-047', 2, 'Stage 1→10+'),
  ('S10-RTL-011', 'Do you track how fast your stock actually turns over?', 'open_text', 'Financial Management', 'CORE', 'RTL-012', 'RC-RTL-048', 2, 'Stage 1→10+'),
  ('S10-RTL-012', 'Is growth being funded by stretching supplier payment terms?', 'open_text', 'Financial Management', 'CORE', 'RTL-012', 'RC-RTL-049', 3, 'Stage 1→10+'),
  ('S10-RTL-013', 'Do you have a credit facility sized to your real working capital gap?', 'open_text', 'Financial Management', 'CORE', 'RTL-012', 'RC-RTL-050', 3, 'Stage 1→10+'),
  ('S10-RTL-014', 'Has your shrinkage rate risen as you have grown?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-013', 'RC-RTL-051', 2, 'Stage 1→10+'),
  ('S10-RTL-015', 'Is loss prevention handled the same way at every location?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-013', 'RC-RTL-052', 2, 'Stage 1→10+'),
  ('S10-RTL-016', 'Do you have any way of detecting internal theft?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-013', 'RC-RTL-053', 3, 'Stage 1→10+'),
  ('S10-RTL-017', 'Is anyone at each location accountable for the shrinkage number?', 'open_text', 'Team & Leadership', 'CORE', 'RTL-013', 'RC-RTL-054', 2, 'Stage 1→10+'),
  ('S10-RTL-018', 'What share of your sales now go through a marketplace or platform?', 'open_text', 'Sales & Revenue', 'CORE', 'RTL-014', 'RC-RTL-055', 2, 'Stage 1→10+'),
  ('S10-RTL-019', 'How much of your margin is going to platform fees?', 'open_text', 'Financial Management', 'CORE', 'RTL-014', 'RC-RTL-056', 2, 'Stage 1→10+'),
  ('S10-RTL-020', 'Do you have a customer relationship independent of that platform?', 'open_text', 'Sales & Revenue', 'CORE', 'RTL-014', 'RC-RTL-057', 3, 'Stage 1→10+'),
  ('S10-RTL-021', 'Have you ever been surprised by a platform policy change affecting sales?', 'open_text', 'Operations & Systems', 'CORE', 'RTL-014', 'RC-RTL-058', 3, 'Stage 1→10+'),
  ('S10-RTL-022', 'How easily could a competitor copy your assortment?', 'open_text', 'Strategy & Planning', 'CORE', 'RTL-015', 'RC-RTL-059', 3, 'Stage 1→10+'),
  ('S10-RTL-023', 'Do you compete mainly on price or on something else?', 'open_text', 'Strategy & Planning', 'CORE', 'RTL-015', 'RC-RTL-060', 2, 'Stage 1→10+'),
  ('S10-RTL-024', 'What keeps a customer coming back to you specifically?', 'open_text', 'Strategy & Planning', 'CORE', 'RTL-015', 'RC-RTL-061', 3, 'Stage 1→10+'),
  ('S10-RTL-025', 'Do you sell anything that cannot be bought elsewhere?', 'open_text', 'Strategy & Planning', 'CORE', 'RTL-015', 'RC-RTL-062', 2, 'Stage 1→10+')
  ) AS t(question_code, question_text, question_type, category, priority,
         problem_code, root_cause_code, difficulty_level, primary_stage_group)
  JOIN new_problems np ON np.problem_code = t.problem_code
  JOIN new_root_causes nr ON nr.root_cause_code = t.root_cause_code
  CROSS JOIN z
  RETURNING question_id, question_code
),

-- 4. QUESTION TAG LINKS -------------------------------------------------------
new_tag_links AS (
  INSERT INTO question_tag_mapping (question_id, tag_id)
  SELECT nq.question_id, qt.tag_id
  FROM (VALUES
  ('S0-RTL-001', 'icp'),
  ('S0-RTL-002', 'icp'),
  ('S0-RTL-003', 'icp'),
  ('S0-RTL-004', 'icp'),
  ('S0-RTL-005', 'icp'),
  ('S0-RTL-006', 'willingness-to-pay'),
  ('S0-RTL-007', 'willingness-to-pay'),
  ('S0-RTL-008', 'willingness-to-pay'),
  ('S0-RTL-009', 'willingness-to-pay'),
  ('S0-RTL-010', 'willingness-to-pay'),
  ('S0-RTL-011', 'technical-quality'),
  ('S0-RTL-012', 'technical-quality'),
  ('S0-RTL-013', 'technical-quality'),
  ('S0-RTL-014', 'technical-quality'),
  ('S0-RTL-015', 'icp'),
  ('S01-RTL-001', 'technical-quality'),
  ('S01-RTL-002', 'technical-quality'),
  ('S01-RTL-003', 'technical-quality'),
  ('S01-RTL-004', 'technical-quality'),
  ('S01-RTL-005', 'technical-quality'),
  ('S01-RTL-006', 'technical-quality'),
  ('S01-RTL-007', 'technical-quality'),
  ('S01-RTL-008', 'technical-quality'),
  ('S01-RTL-009', 'technical-quality'),
  ('S01-RTL-010', 'technical-quality'),
  ('S01-RTL-011', 'technical-quality'),
  ('S01-RTL-012', 'technical-quality'),
  ('S01-RTL-013', 'willingness-to-pay'),
  ('S01-RTL-014', 'willingness-to-pay'),
  ('S01-RTL-015', 'willingness-to-pay'),
  ('S01-RTL-016', 'willingness-to-pay'),
  ('S01-RTL-017', 'technical-quality'),
  ('S01-RTL-018', 'technical-quality'),
  ('S01-RTL-019', 'technical-quality'),
  ('S01-RTL-020', 'technical-quality'),
  ('S10-RTL-001', 'icp'),
  ('S10-RTL-002', 'icp'),
  ('S10-RTL-003', 'icp'),
  ('S10-RTL-004', 'icp'),
  ('S10-RTL-005', 'technical-quality'),
  ('S10-RTL-006', 'technical-quality'),
  ('S10-RTL-007', 'technical-quality'),
  ('S10-RTL-008', 'technical-quality'),
  ('S10-RTL-009', 'technical-quality'),
  ('S10-RTL-010', 'willingness-to-pay'),
  ('S10-RTL-011', 'willingness-to-pay'),
  ('S10-RTL-012', 'willingness-to-pay'),
  ('S10-RTL-013', 'willingness-to-pay'),
  ('S10-RTL-014', 'technical-quality'),
  ('S10-RTL-015', 'technical-quality'),
  ('S10-RTL-016', 'technical-quality'),
  ('S10-RTL-017', 'technical-quality'),
  ('S10-RTL-018', 'willingness-to-pay'),
  ('S10-RTL-019', 'willingness-to-pay'),
  ('S10-RTL-020', 'willingness-to-pay'),
  ('S10-RTL-021', 'willingness-to-pay'),
  ('S10-RTL-022', 'technical-quality'),
  ('S10-RTL-023', 'technical-quality'),
  ('S10-RTL-024', 'technical-quality'),
  ('S10-RTL-025', 'technical-quality')
  ) AS t(question_code, tag_name)
  JOIN new_questions nq ON nq.question_code = t.question_code
  JOIN question_tags qt ON qt.tag_name = t.tag_name
  RETURNING question_id
),

-- 5. INTERVENTIONS ------------------------------------------------------------
new_interventions AS (
  INSERT INTO interventions
    (intervention_code, section, problem_id, root_cause_ids, stage_relevance,
     capability_domain, design_principles, immediate_next_steps,
     recommended_frameworks, industry_relevance, secondary_root_cause_ids)
  SELECT t.intervention_code, t.section, np.problem_id, t.root_cause_ids,
         t.stage_relevance, t.capability_domain,
         '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb,
         t.immediate_next_steps, t.recommended_frameworks,
         '["retail"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-RTL-001', 'Ideation — Retail Customer Clarity', 'RTL-001', '["RC-RTL-001", "RC-RTL-002"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Pick one customer type and one clear theme for your categories.", "Write down what you will not stock because it does not fit.", "Say no to categories outside that theme for now."]'::jsonb, '[{"name": "One Customer, One Theme", "brief": "Choosing a single customer and a coherent assortment instead of everything."}]'::jsonb),
  ('INT-RTL-002', 'Ideation — Retail Customer Clarity', 'RTL-001', '["RC-RTL-003", "RC-RTL-004", "RC-RTL-005"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Find out where your chosen customer buys today.", "Talk to 10 of them about what they actually want stocked.", "Build your assortment around their answers, not supplier offers."]'::jsonb, '[{"name": "Stock What Customers Want", "brief": "Building assortment from real customer demand, not supplier push."}]'::jsonb),
  ('INT-RTL-003', 'Ideation — Retail Margin Reality', 'RTL-002', '["RC-RTL-006", "RC-RTL-007"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Build a true cost sheet for one unit.", "Include shrinkage, damage and theft as a percentage.", "Compare that total against your planned price."]'::jsonb, '[{"name": "True Cost Per Unit", "brief": "A real cost that includes loss, not just the supplier invoice."}]'::jsonb),
  ('INT-RTL-004', 'Ideation — Retail Margin Reality', 'RTL-002', '["RC-RTL-008", "RC-RTL-009", "RC-RTL-010"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Add the cost of returns and holding unsold stock.", "Price from your own true cost, not competitor prices.", "Check which products are actually profitable."]'::jsonb, '[{"name": "Price From Your Own Cost", "brief": "Margin built from real numbers rather than the market rate."}]'::jsonb),
  ('INT-RTL-005', 'Ideation — Retail Demand Forecasting Basics', 'RTL-003', '["RC-RTL-011", "RC-RTL-014"]'::jsonb, '[1]'::jsonb, 'Operations', '["Place a small test order before committing to a full one.", "Watch how fast it actually sells.", "Use that data to size the next order."]'::jsonb, '[{"name": "Test Before You Commit", "brief": "A small trial order to learn real sell-through before scaling up."}]'::jsonb),
  ('INT-RTL-006', 'Ideation — Retail Demand Forecasting Basics', 'RTL-003', '["RC-RTL-012", "RC-RTL-013"]'::jsonb, '[1]'::jsonb, 'Operations', '["Start recording sales data from day one.", "Decide in advance what happens to stock that does not move.", "Review slow movers on a fixed schedule."]'::jsonb, '[{"name": "Build Sales History and a Slow Mover Plan", "brief": "Data from the start plus a decided response to stock that does not sell."}]'::jsonb),
  ('INT-RTL-007', 'Ideation — Retail Channel and Location Clarity', 'RTL-004', '["RC-RTL-015", "RC-RTL-017"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Test the channel or location on a small, low commitment scale first.", "Confirm real demand before signing a lease or major commitment.", "Only scale up once the test proves out."]'::jsonb, '[{"name": "Test the Location Small First", "brief": "A low cost trial before committing to a lease or channel."}]'::jsonb),
  ('INT-RTL-008', 'Ideation — Retail Channel and Location Clarity', 'RTL-004', '["RC-RTL-016", "RC-RTL-018"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Check real footfall or traffic data before committing.", "Do not assume a good product will draw its own customers.", "Base the decision on evidence, not convenience."]'::jsonb, '[{"name": "Check Real Traffic First", "brief": "Evidence of actual customer flow instead of assuming quality is enough."}]'::jsonb),
  ('INT-RTL-009', 'Validation to Traction — Retail Inventory Balance', 'RTL-005', '["RC-RTL-019", "RC-RTL-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Track sell through rate for every item.", "Separate bestsellers from slow movers explicitly.", "Reorder bestsellers on a schedule, not by memory."]'::jsonb, '[{"name": "Track Sell Through", "brief": "Knowing what actually sells so ordering follows real demand."}]'::jsonb),
  ('INT-RTL-010', 'Validation to Traction — Retail Inventory Balance', 'RTL-005', '["RC-RTL-020", "RC-RTL-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Move from reactive reordering to a fixed schedule.", "Measure how much cash is tied up in slow movers.", "Clear that stock deliberately rather than letting it sit."]'::jsonb, '[{"name": "Free the Cash in Slow Stock", "brief": "A reorder schedule and a deliberate plan to clear what is not moving."}]'::jsonb),
  ('INT-RTL-011', 'Validation to Traction — Retail Channel Consistency', 'RTL-006', '["RC-RTL-023", "RC-RTL-024"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Build a single real time view of stock across channels.", "Keep pricing consistent between online and in store.", "Fix the biggest visible inconsistency first."]'::jsonb, '[{"name": "One Stock View, One Price", "brief": "Consistent inventory visibility and pricing across every channel."}]'::jsonb),
  ('INT-RTL-012', 'Validation to Traction — Retail Channel Consistency', 'RTL-006', '["RC-RTL-025", "RC-RTL-026"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Build one customer view that spans every channel.", "Make returns processable regardless of where the purchase happened.", "Test both from the customer side."]'::jsonb, '[{"name": "One Customer, Any Channel Return", "brief": "A unified customer view and returns that work across channels."}]'::jsonb),
  ('INT-RTL-013', 'Validation to Traction — Retail Staff Turnover', 'RTL-007', '["RC-RTL-027", "RC-RTL-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Build simple training material covering products and standards.", "Capture key knowledge before someone leaves, not after.", "Use the material for every new hire."]'::jsonb, '[{"name": "Written Training and Knowledge Capture", "brief": "Reusable training so product knowledge does not leave with staff."}]'::jsonb),
  ('INT-RTL-014', 'Validation to Traction — Retail Staff Turnover', 'RTL-007', '["RC-RTL-029", "RC-RTL-030"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Set a consistent service standard every staff member follows.", "Recruit ahead of need rather than after a gap appears.", "Keep a small pipeline of prospective hires."]'::jsonb, '[{"name": "Consistent Standard, Proactive Hiring", "brief": "A defined service standard and recruitment that does not wait for a crisis."}]'::jsonb),
  ('INT-RTL-015', 'Validation to Traction — Retail Discount Dependency', 'RTL-008', '["RC-RTL-031", "RC-RTL-034"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Measure what discounting is actually costing in margin.", "Set a target for full price sales share.", "Track progress against that target monthly."]'::jsonb, '[{"name": "Measure the Cost of Discounting", "brief": "Putting a real number on markdown-driven revenue."}]'::jsonb),
  ('INT-RTL-016', 'Validation to Traction — Retail Discount Dependency', 'RTL-008', '["RC-RTL-032", "RC-RTL-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Build a planned promotion calendar instead of ad hoc discounts.", "Use scarcity or timing instead of price to create urgency.", "Watch whether customers stop waiting for the next sale."]'::jsonb, '[{"name": "Plan Promotions, Do Not Improvise Them", "brief": "A deliberate calendar to break the habit of training customers to wait."}]'::jsonb),
  ('INT-RTL-017', 'Validation to Traction — Retail Supplier Dependency', 'RTL-009', '["RC-RTL-035", "RC-RTL-036"]'::jsonb, '[2, 3, 4]'::jsonb, 'Supply Chain', '["List every product with only one supplier.", "Qualify a backup supplier for the critical few.", "Test the backup before you actually need it."]'::jsonb, '[{"name": "Second Source the Critical Few", "brief": "A backup supplier for products that could otherwise disappear from the range."}]'::jsonb),
  ('INT-RTL-018', 'Validation to Traction — Retail Supplier Dependency', 'RTL-009', '["RC-RTL-037", "RC-RTL-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Supply Chain', '["Track supplier lead times so delays are visible in advance.", "Negotiate rather than automatically absorbing price rises.", "Use the data to plan reorders realistically."]'::jsonb, '[{"name": "Track Lead Times, Negotiate Price", "brief": "Visibility into delivery timing and active management of cost increases."}]'::jsonb),
  ('INT-RTL-019', 'Growth to Maturity — Retail Revenue Concentration', 'RTL-010', '["RC-RTL-039", "RC-RTL-041"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Calculate the revenue share of your top accounts or locations.", "Set a ceiling and build a pipeline of new ones.", "Review the share every quarter."]'::jsonb, '[{"name": "Cap Revenue Concentration", "brief": "Measuring dependence and building beyond the dominant few."}]'::jsonb),
  ('INT-RTL-020', 'Growth to Maturity — Retail Revenue Concentration', 'RTL-010', '["RC-RTL-040", "RC-RTL-042"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Separate expansion decisions from any single relationship.", "Identify which terms you accept only because of dependence.", "Build expansion criteria that do not depend on one partner."]'::jsonb, '[{"name": "Decouple Growth From One Relationship", "brief": "Expansion driven by a plan, not by whoever the current biggest partner is."}]'::jsonb),
  ('INT-RTL-021', 'Growth to Maturity — Retail Multi Site Consistency', 'RTL-011', '["RC-RTL-043", "RC-RTL-046"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write down how the original site actually runs.", "Use that document to set up every new site.", "Do not open another until it exists."]'::jsonb, '[{"name": "Systemise Before You Expand", "brief": "Documenting the first site so the next one can copy it."}]'::jsonb),
  ('INT-RTL-022', 'Growth to Maturity — Retail Multi Site Consistency', 'RTL-011', '["RC-RTL-044", "RC-RTL-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Use the same suppliers and standards at every location.", "Spend time away from the original site and see what breaks.", "Fix that before opening further sites."]'::jsonb, '[{"name": "Same Standards, No Founder", "brief": "Common standards and a site that runs without the founder present."}]'::jsonb),
  ('INT-RTL-023', 'Growth to Maturity — Retail Working Capital', 'RTL-012', '["RC-RTL-047", "RC-RTL-048"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Set and track an inventory turnover target.", "Compare inventory growth against sales growth monthly.", "Slow purchasing when the gap widens."]'::jsonb, '[{"name": "Track Turnover Against Sales Growth", "brief": "Keeping stock growth honest against actual demand growth."}]'::jsonb),
  ('INT-RTL-024', 'Growth to Maturity — Retail Working Capital', 'RTL-012', '["RC-RTL-049", "RC-RTL-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Arrange financing sized to your real working capital need.", "Stop funding growth by squeezing supplier terms alone.", "Review the facility as the business scales."]'::jsonb, '[{"name": "Fund Working Capital Properly", "brief": "Real financing instead of stretching suppliers to cover growth."}]'::jsonb),
  ('INT-RTL-025', 'Growth to Maturity — Retail Loss Prevention', 'RTL-013', '["RC-RTL-051", "RC-RTL-052"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Build one consistent loss prevention process for every location.", "Track shrinkage rate by site.", "Apply the same standard everywhere."]'::jsonb, '[{"name": "One Loss Prevention Standard", "brief": "Consistent process and tracked shrinkage across every site."}]'::jsonb),
  ('INT-RTL-026', 'Growth to Maturity — Retail Loss Prevention', 'RTL-013', '["RC-RTL-053", "RC-RTL-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Set up a way to detect internal theft systematically.", "Make someone at each location accountable for the shrinkage number.", "Review the numbers regularly, not only when something goes wrong."]'::jsonb, '[{"name": "Detect and Assign Accountability", "brief": "Systematic detection and a named owner for shrinkage at every site."}]'::jsonb),
  ('INT-RTL-027', 'Growth to Maturity — Retail Platform Dependence', 'RTL-014', '["RC-RTL-055", "RC-RTL-057"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Measure what share of sales depends on the platform.", "Build a direct customer relationship independent of it.", "Grow that channel deliberately over time."]'::jsonb, '[{"name": "Build a Direct Relationship", "brief": "Reducing dependence on a platform you do not control."}]'::jsonb),
  ('INT-RTL-028', 'Growth to Maturity — Retail Platform Dependence', 'RTL-014', '["RC-RTL-056", "RC-RTL-058"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Track platform fees as a share of margin explicitly.", "Watch for policy changes ahead of time where possible.", "Factor platform risk into pricing and planning."]'::jsonb, '[{"name": "Track Fees and Watch Policy", "brief": "Making platform cost and risk visible instead of discovering it after the fact."}]'::jsonb),
  ('INT-RTL-029', 'Growth to Maturity — Retail Defensibility', 'RTL-015', '["RC-RTL-059", "RC-RTL-062"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Develop a private label or exclusive product line.", "Make it a meaningful share of the assortment.", "Use it as the reason to choose you specifically."]'::jsonb, '[{"name": "Build Something Exclusive", "brief": "A private label or exclusive product that cannot be bought elsewhere."}]'::jsonb),
  ('INT-RTL-030', 'Growth to Maturity — Retail Defensibility', 'RTL-015', '["RC-RTL-060", "RC-RTL-061"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Build a loyalty or repeat purchase mechanism.", "Compete on something besides price.", "Track whether repeat purchase rate actually improves."]'::jsonb, '[{"name": "Build Repeat Purchase", "brief": "A reason to come back that is not just being cheaper."}]'::jsonb),
  ('INT-RTL-031', 'Ideation — Retail Margin Reality', 'RTL-002', '["RC-RTL-063"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Check what nearby competitors actually charge for the same or similar items.", "Use that alongside your own cost, not instead of it.", "Set price where the two meet, not by either alone."]'::jsonb, '[{"name": "Know the Local Price, Not Just Your Cost", "brief": "Checking competitor prices as one input, never the only one."}]'::jsonb),
  ('INT-RTL-032', 'Ideation — Retail Demand Forecasting Basics', 'RTL-003', '["RC-RTL-064"]'::jsonb, '[1]'::jsonb, 'Operations', '["Map how demand for your category moves across the year.", "Adjust order timing and quantity around that pattern.", "Revisit the pattern each season as you learn more."]'::jsonb, '[{"name": "Plan Around the Season", "brief": "Ordering that follows the real seasonal pattern, not a flat assumption."}]'::jsonb),
  ('INT-RTL-033', 'Validation to Traction — Retail Inventory Balance', 'RTL-005', '["RC-RTL-065"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Set a regular schedule for physical stock counts.", "Reconcile counts against system records every time.", "Investigate discrepancies immediately, not at year end."]'::jsonb, '[{"name": "Regular Stock Audits", "brief": "Scheduled counts that catch discrepancies early, not once a year."}]'::jsonb),
  ('INT-RTL-034', 'Growth to Maturity — Retail Revenue Concentration', 'RTL-010', '["RC-RTL-067"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Review which accounts or locations deserve the most attention on a fixed schedule.", "Reallocate effort as performance shifts.", "Do not let prioritisation freeze around old relationships."]'::jsonb, '[{"name": "Review Priorities on a Schedule", "brief": "Periodic reassessment instead of default loyalty to whoever mattered first."}]'::jsonb)
  ) AS t(intervention_code, section, problem_code, root_cause_ids, stage_relevance,
         capability_domain, immediate_next_steps, recommended_frameworks)
  JOIN new_problems np ON np.problem_code = t.problem_code
  RETURNING intervention_id
)
SELECT
  (SELECT COUNT(*) FROM new_problems)     AS problems_inserted,      -- expect 15
  (SELECT COUNT(*) FROM new_root_causes)  AS root_causes_inserted,   -- expect 68
  (SELECT COUNT(*) FROM new_questions)    AS questions_inserted,     -- expect 60
  (SELECT COUNT(*) FROM new_tag_links)    AS tag_links_inserted,     -- expect 60
  (SELECT COUNT(*) FROM new_interventions) AS interventions_inserted;-- expect 34

-- ============================================================================
-- After running, the single result row above must read:  15 | 68 | 60 | 60 | 34
-- If any number differs, something did not link -- roll back and check.
-- ============================================================================"""),
    ]

    default_expected = {
        "problems_inserted": 15,
        "root_causes_inserted": 66,
        "questions_inserted": 60,
        "tags_inserted": 60,
        "interventions_inserted": 34,
    }

    for label, industry_code, prefix, overrides, sql in seeds:
        sql = sql.replace("\u00e2\u2020\u2019", "\u2192").replace("\u00e2\u20ac\u201d", "\u2014")
        result = dict(bind.exec_driver_sql(sql).mappings().one())
        expected = {**default_expected, **overrides}
        actual = {
            "problems_inserted": result.get("problems_inserted"),
            "root_causes_inserted": result.get("root_causes_inserted"),
            "questions_inserted": result.get("questions_inserted"),
            "tags_inserted": result.get("tags_inserted", result.get("tag_links_inserted")),
            "interventions_inserted": result.get("interventions_inserted"),
        }
        if actual != expected:
            raise RuntimeError(f"{label} seed count mismatch: expected {expected}, got {actual}")

        mapping_count = bind.execute(
            text(
                """
                WITH inserted AS (
                    INSERT INTO question_industry_mapping (
                        question_id, industry_code, stage_group, applicability_type
                    )
                    SELECT
                        q.question_id, :industry_code, q.primary_stage_group, 'primary'
                    FROM questions q
                    WHERE q.question_code ~ :question_pattern
                    ON CONFLICT (question_id, industry_code, stage_group)
                    DO NOTHING
                    RETURNING 1
                )
                SELECT COUNT(*) FROM inserted
                """
            ),
            {
                "industry_code": industry_code,
                "question_pattern": rf"^(S0|S01|S10)-{prefix}-",
            },
        ).scalar_one()
        if mapping_count != 60:
            raise RuntimeError(f"{label} industry mapping mismatch: expected 60, got {mapping_count}")


def downgrade() -> None:
    raise RuntimeError(
        "Migration d9c31e4f6a82 is intentionally irreversible. "
        "Roll back application code without deleting production seed history."
    )
