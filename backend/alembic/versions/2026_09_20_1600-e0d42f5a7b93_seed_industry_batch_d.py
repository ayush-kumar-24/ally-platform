"""seed industry batch D: telecom, textiles, transportation/delivery

Revision ID: e0d42f5a7b93
Revises: d9c31e4f6a82
Create Date: 2026-09-20
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "e0d42f5a7b93"
down_revision: Union[str, Sequence[str], None] = "d9c31e4f6a82"
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
        ('telecom', 'Telecommunications', 'Telecommunications networks, connectivity, operators, infrastructure and communications-service businesses.'),
        ('textiles', 'Textiles', 'Textile manufacturing, processing, sourcing, fabrics, mills, apparel inputs and related businesses.'),
        ('transport_delivery', 'Transportation & Delivery', 'Transportation, mobility, delivery, fleet, last-mile and movement-of-goods or people businesses.'),
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
        ('Telecommunications', 'telecom', 'TEL', r"""-- ============================================================================
-- Ally :: Industry seed -- TELECOMMUNICATIONS (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: telecom
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (TEL-001, RC-TEL-014, S0-TEL-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : questions name no specific spectrum band, licence category,
--            numbering scheme or reporting statute.  These vary by market and
--            change over time, so the content asks the founder what applies
--            to THEM and what has actually been confirmed, rather than
--            naming a rule that will go stale.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (network reliability, activation delays, billing
--            accuracy, churn diagnosis, upstream dependency) starts at
--            Stage 0->1; account concentration, network scaling, regulatory
--            compliance, fraud and leakage, technology evolution and
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
  ('TEL-001', 'No Idea Which Licence or Approval This Business Actually Needs', 'Reselling connectivity, running infrastructure, or offering value added services each require completely different authorisations, and which applies here has not been established.', 'Idea & Validation', 'Telecom Licensing Clarity', 'external', 3, 6, 10, '["No idea which category of authorisation applies", "Assuming a reseller model needs no licence at all", "Timeline built without checking real approval timeframes", "No telecom regulatory advisor consulted", "Operations started before licensing was confirmed"]'::jsonb, '["telecom"]'::jsonb),
  ('TEL-002', 'No Idea What It Actually Costs to Deliver Connectivity', 'Bandwidth, interconnect, infrastructure lease and support costs are not tracked, so nobody knows the true cost of serving one customer.', 'Idea & Validation', 'Telecom Cost to Serve', 'external', 4, 6, 10, '["Only headline bandwidth cost counted", "Interconnect and carrier fees not factored in", "Support and churn cost not counted", "Price set by looking at competitors only", "No idea which customer segments are actually profitable"]'::jsonb, '["telecom"]'::jsonb),
  ('TEL-003', 'No Clear Customer Segment or Use Case Chosen', 'The offer tries to serve consumers, small businesses and enterprises all at once, so nothing about the product or pricing is designed for anyone specific.', 'Idea & Validation', 'Telecom Segment Clarity', 'external', 2, 5, 9, '["Target customer described as anyone needing connectivity", "No specific segment or use case designed for", "Pricing and service level identical across very different buyers", "No conversation with a real target customer", "Feature set decided without a clear buyer in mind"]'::jsonb, '["telecom"]'::jsonb),
  ('TEL-004', 'No Realistic View of How Long Infrastructure Rollout Actually Takes', 'Timelines assume permits, right of way and equipment procurement will move faster than they typically do, without checking against a real comparable rollout.', 'Idea & Validation', 'Telecom Rollout Timeline Reality', 'external', 3, 6, 10, '["Rollout timeline based on best case assumptions", "Permits and right of way approvals not researched", "Equipment lead times not checked with suppliers", "No comparison against a similar real rollout", "Revenue assumed to start before infrastructure is actually ready"]'::jsonb, '["telecom"]'::jsonb),
  ('TEL-005', 'Network Outages and Service Quality Issues Eroding Trust', 'Downtime and quality problems occur without a clear cause being found or fixed, and customers notice before the business does.', 'Operations & Systems', 'Telecom Network Reliability', 'external', 4, 7, 10, '["Outages discovered from customer complaints first", "No monitoring system flagging degradation early", "Root cause of repeat outages not identified", "No service level tracking against a defined standard", "Customers churning after repeated quality issues"]'::jsonb, '["telecom"]'::jsonb),
  ('TEL-006', 'Customer Onboarding and Activation Taking Too Long', 'New customers wait far longer than expected to get connected, and delays are not tracked or explained to them.', 'Operations & Systems', 'Telecom Activation Delays', 'external', 3, 6, 9, '["Activation taking longer than promised", "No visibility into where an order is stuck", "Customers not proactively updated on delay", "Manual handoffs between teams causing drops", "No standard timeline communicated at signup"]'::jsonb, '["telecom"]'::jsonb),
  ('TEL-007', 'Billing Errors and Disputes Consuming Support Capacity', 'Incorrect charges, unclear billing and disputed invoices are common, and resolving them consumes a large share of support time.', 'Financial Management', 'Telecom Billing Accuracy', 'external', 4, 6, 9, '["Billing disputes a large share of support tickets", "Charges not matching what was actually used or agreed", "No reconciliation process catching errors before billing", "Refunds and credits handled inconsistently", "Customers losing trust in the accuracy of invoices"]'::jsonb, '["telecom"]'::jsonb),
  ('TEL-008', 'Churn Concentrated Among a Specific Group but Not Understood', 'A particular segment or plan type churns at a much higher rate, and nobody has traced why or built a response.', 'Sales & Revenue', 'Telecom Churn Diagnosis', 'external', 4, 6, 9, '["Churn rate much higher for one segment or plan", "No system tracking churn by segment", "Exit reasons not captured when a customer leaves", "No retention offer targeted at the at risk group", "Acquisition continuing to pour into a leaky segment"]'::jsonb, '["telecom"]'::jsonb),
  ('TEL-009', 'Dependence on a Single Upstream Provider or Interconnect Partner', 'Core connectivity or interconnect runs through one partner, so a price change, outage or dispute on their end threatens the whole business.', 'Operations & Systems', 'Telecom Upstream Dependency', 'external', 3, 7, 10, '["All core connectivity from a single upstream provider", "No backup interconnect arrangement", "Partner price changes passed through with no negotiation", "No visibility into the partner own reliability track record", "No plan for a sudden partner outage or dispute"]'::jsonb, '["telecom"]'::jsonb),
  ('TEL-010', 'Revenue Concentrated in a Few Large Enterprise Accounts', 'A handful of large accounts account for most revenue, so they set the terms and their loss would be severe.', 'Sales & Revenue', 'Telecom Account Concentration', 'external', 4, 7, 10, '["Most revenue from a few large accounts", "Rates and terms dictated by the largest account", "No pipeline of replacement accounts", "Losing one account would threaten the business", "Network priorities shaped by one account rather than the wider base"]'::jsonb, '["telecom"]'::jsonb),
  ('TEL-011', 'Network Scaling Introducing Congestion and New Failure Points', 'Traffic growth is straining capacity in ways not visible at smaller scale, and new equipment or routes are creating failure points nobody anticipated.', 'Operations & Systems', 'Telecom Network Scaling', 'external', 3, 7, 10, '["Congestion appearing at peak times as traffic grows", "New equipment introducing failures not seen before", "Capacity planning not keeping pace with growth", "No redundancy for newly added critical paths", "Scaling decisions made reactively under pressure"]'::jsonb, '["telecom"]'::jsonb),
  ('TEL-012', 'Regulatory and Compliance Reporting Now a Constant Operation', 'Licence renewals, quality of service reporting, data retention and spectrum or numbering obligations recur continuously and cannot be tracked informally at this size.', 'Operations & Systems', 'Telecom Regulatory Compliance', 'external', 3, 7, 10, '["Renewals and filings tracked from memory", "No single compliance calendar", "Reporting obligations discovered close to deadline", "Compliance findings repeating without being permanently fixed", "One person holding all the regulatory knowledge"]'::jsonb, '["telecom"]'::jsonb),
  ('TEL-013', 'Fraud and Revenue Leakage Increasing With Scale', 'As volume grows, fraudulent usage, unbilled traffic and revenue leakage increase faster than controls can catch them.', 'Financial Management', 'Telecom Fraud and Leakage', 'external', 3, 7, 10, '["Fraudulent usage patterns not systematically detected", "Unbilled or underbilled traffic going unnoticed", "No regular revenue assurance reconciliation", "Losses discovered long after they occurred", "No dedicated ownership of fraud and leakage control"]'::jsonb, '["telecom"]'::jsonb),
  ('TEL-014', 'New Technology and Standards Outpacing the Business', 'Competitors adopt newer network technology and service models faster than this business can evaluate and deploy them.', 'Strategy & Planning', 'Telecom Technology Evolution', 'external', 2, 6, 10, '["Competitors offering newer technology or service tiers", "No process for evaluating new network technology", "Capital tied up in older infrastructure", "Customers asking for capabilities not yet supported", "No budget set aside for technology refresh"]'::jsonb, '["telecom"]'::jsonb),
  ('TEL-015', 'Nothing Differentiates This From Any Other Connectivity Provider', 'Customers can switch to a similar provider at similar cost with little friction, because nothing built here creates real loyalty.', 'Strategy & Planning', 'Telecom Defensibility', 'external', 2, 6, 10, '["Service easily matched by competitors", "Price the main basis of customer decisions", "No bundled service or platform advantage", "No data or relationship asset beyond connectivity", "Customer churn to marginally cheaper alternatives"]'::jsonb, '["telecom"]'::jsonb)
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
         t.primary_stage_group, '["telecom"]'::jsonb, z.v
  FROM (VALUES
  ('RC-TEL-001', 'Authorisation Category Not Established', 'Which licence or approval category applies has not been determined.', 'TEL-001', 'external', 'Knowledge', 0.74, 'Stage 0'),
  ('RC-TEL-002', 'Assuming a Reseller Model Needs No Licence', 'Believing that not owning infrastructure means no authorisation is required.', 'TEL-001', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-TEL-003', 'Timeline Built Without Checking Real Approval Timeframes', 'Plans assume speed that has not been verified against actual cases.', 'TEL-001', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-TEL-004', 'No Telecom Regulatory Advisor Consulted', 'Nobody with real regulatory expertise has reviewed the plan.', 'TEL-001', 'external', 'Operational', 0.69, 'Stage 0'),
  ('RC-TEL-005', 'Operations Started Before Licensing Confirmed', 'Work began without knowing what authorisation will actually require.', 'TEL-001', 'external', 'Strategic', 0.72, 'Stage 0'),
  ('RC-TEL-006', 'Only Headline Bandwidth Cost Counted', 'The cost is taken as the wholesale bandwidth rate alone.', 'TEL-002', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-TEL-007', 'Interconnect and Carrier Fees Not Factored In', 'Fees paid to other networks are missing from the cost picture.', 'TEL-002', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-TEL-008', 'Support and Churn Cost Not Counted', 'The cost of customer support and losing customers is left out.', 'TEL-002', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-TEL-009', 'Price Set by Looking at Competitors', 'Pricing copies others without knowing own true cost.', 'TEL-002', 'external', 'Behavioural', 0.67, 'Stage 0'),
  ('RC-TEL-010', 'No Idea Which Segments Are Profitable', 'Nobody has checked which customer types actually make money.', 'TEL-002', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-TEL-011', 'Target Customer Described as Anyone Needing Connectivity', 'No specific segment has been chosen to design for.', 'TEL-003', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-TEL-012', 'No Specific Segment or Use Case Designed For', 'Product and pricing do not target a defined buyer.', 'TEL-003', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-TEL-013', 'Pricing Identical Across Very Different Buyers', 'The same offer is used for consumers, small business and enterprise alike.', 'TEL-003', 'external', 'Strategic', 0.68, 'Stage 0'),
  ('RC-TEL-014', 'No Conversation With a Real Target Customer', 'Nobody who would actually buy has been spoken to.', 'TEL-003', 'external', 'Behavioural', 0.66, 'Stage 0'),
  ('RC-TEL-015', 'Rollout Timeline Based on Best Case Assumptions', 'Plans assume the fastest possible path with no allowance for delay.', 'TEL-004', 'external', 'Strategic', 0.72, 'Stage 0'),
  ('RC-TEL-016', 'Permits and Right of Way Not Researched', 'What approvals are actually needed for rollout has not been checked.', 'TEL-004', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-TEL-017', 'Equipment Lead Times Not Checked With Suppliers', 'How long equipment actually takes to arrive has not been confirmed.', 'TEL-004', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-TEL-018', 'No Comparison Against a Real Rollout', 'Nobody has checked how long a similar rollout actually took.', 'TEL-004', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-TEL-019', 'Outages Discovered From Customer Complaints', 'Nothing internally flags a problem before customers do.', 'TEL-005', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-TEL-020', 'No Monitoring System Flagging Degradation Early', 'Quality drops are not caught before they become outages.', 'TEL-005', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-TEL-021', 'Root Cause of Repeat Outages Not Identified', 'The same failure keeps happening without being traced.', 'TEL-005', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-TEL-022', 'No Service Level Tracked Against a Standard', 'Nothing defines or measures what acceptable quality actually is.', 'TEL-005', 'external', 'Knowledge', 0.69, 'Stage 0→1'),
  ('RC-TEL-023', 'No Visibility Into Where an Order Is Stuck', 'Nobody can see where an activation is delayed in the process.', 'TEL-006', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-TEL-024', 'Customers Not Proactively Updated on Delay', 'Customers learn about delays only by asking.', 'TEL-006', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-TEL-025', 'Manual Handoffs Causing Drops', 'Orders fall through cracks between teams during handoff.', 'TEL-006', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-TEL-026', 'No Standard Timeline Communicated at Signup', 'Customers are not told what to expect at the point of sale.', 'TEL-006', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-TEL-027', 'No Reconciliation Process Before Billing', 'Nothing checks charges against actual usage before the invoice goes out.', 'TEL-007', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-TEL-028', 'Charges Not Matching Usage or Agreement', 'What is billed does not reflect what was actually used or agreed.', 'TEL-007', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-TEL-029', 'Refunds and Credits Handled Inconsistently', 'Similar disputes get different resolutions depending on who handles them.', 'TEL-007', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-TEL-030', 'Billing Disputes Consuming Support Capacity', 'A large share of support time goes to fixing bills, not helping customers.', 'TEL-007', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-TEL-031', 'No System Tracking Churn by Segment', 'Churn is measured overall but not broken down by segment or plan.', 'TEL-008', 'external', 'Knowledge', 0.73, 'Stage 0→1'),
  ('RC-TEL-032', 'Exit Reasons Not Captured', 'Nobody asks or records why a customer actually left.', 'TEL-008', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-TEL-033', 'No Retention Offer for the At Risk Group', 'Nothing specific is done for the segment that churns most.', 'TEL-008', 'external', 'Strategic', 0.70, 'Stage 0→1'),
  ('RC-TEL-034', 'Acquisition Continuing Into a Leaky Segment', 'New customers keep being acquired into a segment that churns fast.', 'TEL-008', 'external', 'Strategic', 0.69, 'Stage 0→1'),
  ('RC-TEL-035', 'All Core Connectivity From a Single Provider', 'One upstream partner carries the entire business.', 'TEL-009', 'external', 'Strategic', 0.74, 'Stage 0→1'),
  ('RC-TEL-036', 'No Backup Interconnect Arrangement', 'Nothing exists to fall back on if the primary partner fails.', 'TEL-009', 'external', 'Strategic', 0.73, 'Stage 0→1'),
  ('RC-TEL-037', 'Partner Price Changes Passed Through Unmanaged', 'Cost increases from the partner are absorbed or passed on without negotiation.', 'TEL-009', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-TEL-038', 'No Visibility Into Partner Reliability', 'The upstream partner own track record has not been checked.', 'TEL-009', 'external', 'Knowledge', 0.68, 'Stage 0→1'),
  ('RC-TEL-039', 'Most Revenue From a Few Large Accounts', 'A handful of accounts carry most of the business.', 'TEL-010', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-TEL-040', 'Rates and Terms Dictated by the Largest Account', 'The dominant account sets what can be charged and agreed.', 'TEL-010', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-TEL-041', 'No Pipeline of Replacement Accounts', 'Nothing is being built that could replace a lost account.', 'TEL-010', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-TEL-042', 'Network Priorities Shaped by One Account', 'The dominant account decides infrastructure priorities rather than the wider base.', 'TEL-010', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-TEL-043', 'Congestion Appearing as Traffic Grows', 'Peak time capacity is straining in ways not visible before.', 'TEL-011', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-TEL-044', 'New Equipment Introducing Unseen Failures', 'Scaling infrastructure has created failure modes nobody anticipated.', 'TEL-011', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-TEL-045', 'Capacity Planning Not Keeping Pace With Growth', 'Infrastructure investment is lagging behind traffic growth.', 'TEL-011', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-TEL-046', 'No Redundancy for Newly Added Critical Paths', 'New infrastructure lacks the backup older parts of the network have.', 'TEL-011', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-TEL-047', 'Renewals and Filings Tracked From Memory', 'Regulatory dates live in memory rather than a system.', 'TEL-012', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-TEL-048', 'No Single Compliance Calendar', 'Nothing brings every obligation into one dated place.', 'TEL-012', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-TEL-049', 'Reporting Obligations Discovered Close to Deadline', 'Requirements are found too late to prepare properly.', 'TEL-012', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-TEL-050', 'Compliance Findings Repeating', 'The same issue is raised without ever being permanently fixed.', 'TEL-012', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-TEL-051', 'Fraud Patterns Not Systematically Detected', 'Nothing is set up to catch unusual usage patterns.', 'TEL-013', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-TEL-052', 'Unbilled or Underbilled Traffic Unnoticed', 'Some usage is not captured or charged for correctly.', 'TEL-013', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-TEL-053', 'No Regular Revenue Assurance Reconciliation', 'Nobody checks usage against billed revenue on a schedule.', 'TEL-013', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-TEL-054', 'No Dedicated Ownership of Fraud and Leakage', 'Nobody owns finding and closing revenue leaks.', 'TEL-013', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-TEL-055', 'No Process for Evaluating New Network Technology', 'Nothing systematically decides which new technology to adopt.', 'TEL-014', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-TEL-056', 'Capital Tied Up in Older Infrastructure', 'Investment already made makes upgrading harder to justify.', 'TEL-014', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-TEL-057', 'No Budget for Technology Refresh', 'Nothing is set aside to keep infrastructure current.', 'TEL-014', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-TEL-058', 'Service Easily Matched by Competitors', 'What is offered can be replicated without much effort.', 'TEL-015', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-TEL-059', 'No Bundled Service or Platform Advantage', 'Nothing beyond raw connectivity keeps customers attached.', 'TEL-015', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-TEL-060', 'No Data or Relationship Asset Beyond Connectivity', 'Nothing owned makes the provider harder to leave.', 'TEL-015', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-TEL-061', 'No Idea What a Realistic Adoption Rate Looks Like', 'How quickly customers typically adopt a comparable connectivity offer has not been researched.', 'TEL-003', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-TEL-062', 'No Backup Plan for a Missed Rollout Milestone', 'Nothing has been prepared for infrastructure deployment running behind schedule.', 'TEL-004', 'external', 'Strategic', 0.65, 'Stage 0'),
  ('RC-TEL-063', 'No Escalation Path for a Prolonged Outage', 'What happens when an outage runs longer than expected is undefined.', 'TEL-005', 'external', 'Operational', 0.66, 'Stage 0→1'),
  ('RC-TEL-064', 'No Regular Review of Which Accounts to Prioritise', 'Nobody periodically reassesses which accounts deserve the most attention.', 'TEL-010', 'external', 'Operational', 0.66, 'Stage 1→10+'),
  ('RC-TEL-065', 'No Cross Training on Regulatory Filings', 'Only one person understands how to actually complete the required filings.', 'TEL-012', 'external', 'Operational', 0.65, 'Stage 1→10+'),
  ('RC-TEL-066', 'No Regular Benchmarking Against Competitor Offers', 'Nobody checks what competitors are actually offering on price or technology.', 'TEL-015', 'external', 'Knowledge', 0.65, 'Stage 1→10+')
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
         '["telecom"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-TEL-001', 'Do you know which licence or approval category your business falls into?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-001', 'RC-TEL-001', 1, 'Stage 0'),
  ('S0-TEL-002', 'Do you believe a reselling model needs no licence at all?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-001', 'RC-TEL-002', 1, 'Stage 0'),
  ('S0-TEL-003', 'Have you checked how long a similar approval has actually taken?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-001', 'RC-TEL-003', 2, 'Stage 0'),
  ('S0-TEL-004', 'Has anyone with real telecom regulatory expertise reviewed your plan?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-001', 'RC-TEL-004', 2, 'Stage 0'),
  ('S0-TEL-005', 'Did you confirm licensing before starting operations?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-001', 'RC-TEL-005', 2, 'Stage 0'),
  ('S0-TEL-006', 'What does it actually cost you to serve one customer, beyond bandwidth?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-002', 'RC-TEL-006', 1, 'Stage 0'),
  ('S0-TEL-007', 'Have you counted interconnect and carrier fees in your cost?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-002', 'RC-TEL-007', 2, 'Stage 0'),
  ('S0-TEL-008', 'Have you counted support cost and expected churn?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-002', 'RC-TEL-008', 2, 'Stage 0'),
  ('S0-TEL-009', 'Did you set your price from your own cost or from competitors?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-002', 'RC-TEL-009', 2, 'Stage 0'),
  ('S0-TEL-010', 'Do you know which customer segments are actually profitable for you?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-002', 'RC-TEL-010', 2, 'Stage 0'),
  ('S0-TEL-011', 'Who exactly is your target customer, consumers, small business or enterprise?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-003', 'RC-TEL-011', 1, 'Stage 0'),
  ('S0-TEL-012', 'Is your pricing designed for a specific segment or the same for everyone?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-003', 'RC-TEL-013', 2, 'Stage 0'),
  ('S0-TEL-013', 'Have you spoken to a real target customer about this offer?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-003', 'RC-TEL-014', 2, 'Stage 0'),
  ('S0-TEL-014', 'Is your rollout timeline based on the best case, or a realistic case?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-004', 'RC-TEL-015', 1, 'Stage 0'),
  ('S0-TEL-015', 'Have you researched the permits and right of way approvals you actually need?', 'open_text', 'Idea & Validation', 'CORE', 'TEL-004', 'RC-TEL-016', 2, 'Stage 0'),
  ('S01-TEL-001', 'Do you find out about outages from monitoring or from customer complaints?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-005', 'RC-TEL-019', 2, 'Stage 0→1'),
  ('S01-TEL-002', 'Is there a system that flags quality degradation before it becomes an outage?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-005', 'RC-TEL-020', 2, 'Stage 0→1'),
  ('S01-TEL-003', 'Have the same outages happened more than once without the cause being fixed?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-005', 'RC-TEL-021', 3, 'Stage 0→1'),
  ('S01-TEL-004', 'Do you track service quality against a defined standard?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-005', 'RC-TEL-022', 2, 'Stage 0→1'),
  ('S01-TEL-005', 'Can you see where a customer order is stuck in the activation process?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-006', 'RC-TEL-023', 2, 'Stage 0→1'),
  ('S01-TEL-006', 'Are customers proactively told about a delay, or do they have to ask?', 'open_text', 'Sales & Revenue', 'CORE', 'TEL-006', 'RC-TEL-024', 2, 'Stage 0→1'),
  ('S01-TEL-007', 'Do orders drop between teams during manual handoffs?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-006', 'RC-TEL-025', 2, 'Stage 0→1'),
  ('S01-TEL-008', 'Is a standard activation timeline communicated at signup?', 'open_text', 'Sales & Revenue', 'CORE', 'TEL-006', 'RC-TEL-026', 2, 'Stage 0→1'),
  ('S01-TEL-009', 'Is there a reconciliation step checking usage before an invoice goes out?', 'open_text', 'Financial Management', 'CORE', 'TEL-007', 'RC-TEL-027', 2, 'Stage 0→1'),
  ('S01-TEL-010', 'How often do billed charges not match what was actually used or agreed?', 'open_text', 'Financial Management', 'CORE', 'TEL-007', 'RC-TEL-028', 2, 'Stage 0→1'),
  ('S01-TEL-011', 'Are refunds and credits handled consistently across similar disputes?', 'open_text', 'Financial Management', 'CORE', 'TEL-007', 'RC-TEL-029', 2, 'Stage 0→1'),
  ('S01-TEL-012', 'What share of your support tickets are billing disputes?', 'open_text', 'Financial Management', 'CORE', 'TEL-007', 'RC-TEL-030', 2, 'Stage 0→1'),
  ('S01-TEL-013', 'Do you track churn separately for different segments or plans?', 'open_text', 'Sales & Revenue', 'CORE', 'TEL-008', 'RC-TEL-031', 2, 'Stage 0→1'),
  ('S01-TEL-014', 'Do you capture why a customer actually leaves?', 'open_text', 'Sales & Revenue', 'CORE', 'TEL-008', 'RC-TEL-032', 2, 'Stage 0→1'),
  ('S01-TEL-015', 'Is there a specific retention offer for your highest churn group?', 'open_text', 'Sales & Revenue', 'CORE', 'TEL-008', 'RC-TEL-033', 3, 'Stage 0→1'),
  ('S01-TEL-016', 'Are you still acquiring customers into a segment that churns fast?', 'open_text', 'Strategy & Planning', 'CORE', 'TEL-008', 'RC-TEL-034', 3, 'Stage 0→1'),
  ('S01-TEL-017', 'Does all your core connectivity come from one upstream provider?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-009', 'RC-TEL-035', 2, 'Stage 0→1'),
  ('S01-TEL-018', 'Do you have any backup interconnect arrangement?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-009', 'RC-TEL-036', 2, 'Stage 0→1'),
  ('S01-TEL-019', 'When your upstream partner raises prices, how do you respond?', 'open_text', 'Financial Management', 'CORE', 'TEL-009', 'RC-TEL-037', 2, 'Stage 0→1'),
  ('S01-TEL-020', 'Do you know your upstream partner own reliability track record?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-009', 'RC-TEL-038', 3, 'Stage 0→1'),
  ('S10-TEL-001', 'What share of your revenue comes from your top two or three accounts?', 'open_text', 'Sales & Revenue', 'CORE', 'TEL-010', 'RC-TEL-039', 2, 'Stage 1→10+'),
  ('S10-TEL-002', 'Who sets your rates and terms, you or your largest account?', 'open_text', 'Sales & Revenue', 'CORE', 'TEL-010', 'RC-TEL-040', 2, 'Stage 1→10+'),
  ('S10-TEL-003', 'If your largest account left, how long could you continue?', 'open_text', 'Strategy & Planning', 'CORE', 'TEL-010', 'RC-TEL-041', 3, 'Stage 1→10+'),
  ('S10-TEL-004', 'Are your network priorities shaped by one account rather than your wider base?', 'open_text', 'Strategy & Planning', 'CORE', 'TEL-010', 'RC-TEL-042', 3, 'Stage 1→10+'),
  ('S10-TEL-005', 'Has congestion appeared at peak times as your traffic has grown?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-011', 'RC-TEL-043', 2, 'Stage 1→10+'),
  ('S10-TEL-006', 'Has new equipment introduced failures you did not see before?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-011', 'RC-TEL-044', 2, 'Stage 1→10+'),
  ('S10-TEL-007', 'Is your capacity planning keeping pace with traffic growth?', 'open_text', 'Strategy & Planning', 'CORE', 'TEL-011', 'RC-TEL-045', 3, 'Stage 1→10+'),
  ('S10-TEL-008', 'Do newly added critical paths have the same redundancy as the rest of the network?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-011', 'RC-TEL-046', 3, 'Stage 1→10+'),
  ('S10-TEL-009', 'Can you list every regulatory filing and renewal you are responsible for, with dates?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-012', 'RC-TEL-048', 2, 'Stage 1→10+'),
  ('S10-TEL-010', 'Have you discovered a reporting obligation close to its deadline?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-012', 'RC-TEL-049', 3, 'Stage 1→10+'),
  ('S10-TEL-011', 'Have the same compliance findings come up more than once?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-012', 'RC-TEL-050', 3, 'Stage 1→10+'),
  ('S10-TEL-012', 'If the person who tracks compliance left, what would happen?', 'open_text', 'Team & Leadership', 'CORE', 'TEL-012', 'RC-TEL-047', 3, 'Stage 1→10+'),
  ('S10-TEL-013', 'Do you have any system for detecting fraudulent usage patterns?', 'open_text', 'Operations & Systems', 'CORE', 'TEL-013', 'RC-TEL-051', 3, 'Stage 1→10+'),
  ('S10-TEL-014', 'How would you know if some traffic was going unbilled?', 'open_text', 'Financial Management', 'CORE', 'TEL-013', 'RC-TEL-052', 3, 'Stage 1→10+'),
  ('S10-TEL-015', 'Do you reconcile usage against billed revenue on a regular schedule?', 'open_text', 'Financial Management', 'CORE', 'TEL-013', 'RC-TEL-053', 2, 'Stage 1→10+'),
  ('S10-TEL-016', 'Is anyone specifically responsible for fraud and revenue leakage?', 'open_text', 'Team & Leadership', 'CORE', 'TEL-013', 'RC-TEL-054', 2, 'Stage 1→10+'),
  ('S10-TEL-017', 'How do you decide which new network technology to adopt?', 'open_text', 'Strategy & Planning', 'CORE', 'TEL-014', 'RC-TEL-055', 2, 'Stage 1→10+'),
  ('S10-TEL-018', 'Is capital tied up in older infrastructure making upgrades harder to justify?', 'open_text', 'Financial Management', 'CORE', 'TEL-014', 'RC-TEL-056', 3, 'Stage 1→10+'),
  ('S10-TEL-019', 'Is there a budget set aside for technology refresh?', 'open_text', 'Financial Management', 'CORE', 'TEL-014', 'RC-TEL-057', 2, 'Stage 1→10+'),
  ('S10-TEL-020', 'How easily could a competitor match your service?', 'open_text', 'Strategy & Planning', 'CORE', 'TEL-015', 'RC-TEL-058', 3, 'Stage 1→10+'),
  ('S10-TEL-021', 'Do customers choose you mainly on price or on something else?', 'open_text', 'Sales & Revenue', 'CORE', 'TEL-015', 'RC-TEL-058', 2, 'Stage 1→10+'),
  ('S10-TEL-022', 'Do you have any bundled service or platform advantage beyond raw connectivity?', 'open_text', 'Strategy & Planning', 'CORE', 'TEL-015', 'RC-TEL-059', 3, 'Stage 1→10+'),
  ('S10-TEL-023', 'Do you own any data or relationship asset that keeps customers attached?', 'open_text', 'Strategy & Planning', 'CORE', 'TEL-015', 'RC-TEL-060', 3, 'Stage 1→10+'),
  ('S10-TEL-024', 'Have you lost a customer to a marginally cheaper competitor?', 'open_text', 'Sales & Revenue', 'CORE', 'TEL-015', 'RC-TEL-060', 2, 'Stage 1→10+'),
  ('S10-TEL-025', 'Have customers asked for capabilities you do not yet support?', 'open_text', 'Sales & Revenue', 'CORE', 'TEL-014', 'RC-TEL-055', 2, 'Stage 1→10+')
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
  ('S0-TEL-001', 'technical-quality'),
  ('S0-TEL-002', 'technical-quality'),
  ('S0-TEL-003', 'technical-quality'),
  ('S0-TEL-004', 'technical-quality'),
  ('S0-TEL-005', 'technical-quality'),
  ('S0-TEL-006', 'willingness-to-pay'),
  ('S0-TEL-007', 'willingness-to-pay'),
  ('S0-TEL-008', 'willingness-to-pay'),
  ('S0-TEL-009', 'willingness-to-pay'),
  ('S0-TEL-010', 'willingness-to-pay'),
  ('S0-TEL-011', 'icp'),
  ('S0-TEL-012', 'icp'),
  ('S0-TEL-013', 'icp'),
  ('S0-TEL-014', 'technical-quality'),
  ('S0-TEL-015', 'technical-quality'),
  ('S01-TEL-001', 'technical-quality'),
  ('S01-TEL-002', 'technical-quality'),
  ('S01-TEL-003', 'technical-quality'),
  ('S01-TEL-004', 'technical-quality'),
  ('S01-TEL-005', 'icp'),
  ('S01-TEL-006', 'icp'),
  ('S01-TEL-007', 'icp'),
  ('S01-TEL-008', 'icp'),
  ('S01-TEL-009', 'willingness-to-pay'),
  ('S01-TEL-010', 'willingness-to-pay'),
  ('S01-TEL-011', 'willingness-to-pay'),
  ('S01-TEL-012', 'willingness-to-pay'),
  ('S01-TEL-013', 'technical-quality'),
  ('S01-TEL-014', 'technical-quality'),
  ('S01-TEL-015', 'technical-quality'),
  ('S01-TEL-016', 'technical-quality'),
  ('S01-TEL-017', 'technical-quality'),
  ('S01-TEL-018', 'technical-quality'),
  ('S01-TEL-019', 'technical-quality'),
  ('S01-TEL-020', 'technical-quality'),
  ('S10-TEL-001', 'willingness-to-pay'),
  ('S10-TEL-002', 'willingness-to-pay'),
  ('S10-TEL-003', 'willingness-to-pay'),
  ('S10-TEL-004', 'willingness-to-pay'),
  ('S10-TEL-005', 'technical-quality'),
  ('S10-TEL-006', 'technical-quality'),
  ('S10-TEL-007', 'technical-quality'),
  ('S10-TEL-008', 'technical-quality'),
  ('S10-TEL-009', 'technical-quality'),
  ('S10-TEL-010', 'technical-quality'),
  ('S10-TEL-011', 'technical-quality'),
  ('S10-TEL-012', 'technical-quality'),
  ('S10-TEL-013', 'willingness-to-pay'),
  ('S10-TEL-014', 'willingness-to-pay'),
  ('S10-TEL-015', 'willingness-to-pay'),
  ('S10-TEL-016', 'willingness-to-pay'),
  ('S10-TEL-017', 'technical-quality'),
  ('S10-TEL-018', 'technical-quality'),
  ('S10-TEL-019', 'technical-quality'),
  ('S10-TEL-020', 'technical-quality'),
  ('S10-TEL-021', 'technical-quality'),
  ('S10-TEL-022', 'technical-quality'),
  ('S10-TEL-023', 'technical-quality'),
  ('S10-TEL-024', 'technical-quality'),
  ('S10-TEL-025', 'technical-quality')
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
         '["telecom"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-TEL-001', 'Ideation — Telecom Licensing Clarity', 'TEL-001', '["RC-TEL-001", "RC-TEL-005"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Establish which licence or approval category your business falls into.", "Confirm requirements before doing further operational buildout.", "Get this in writing from someone qualified."]'::jsonb, '[{"name": "Confirm Licensing First", "brief": "Establishing the authorisation category before committing to operations."}]'::jsonb),
  ('INT-TEL-002', 'Ideation — Telecom Licensing Clarity', 'TEL-001', '["RC-TEL-002", "RC-TEL-003", "RC-TEL-004"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Do not assume a reseller model is automatically licence free.", "Find real approval timelines from similar cases.", "Bring in a regulatory advisor before building further."]'::jsonb, '[{"name": "Check Assumptions and Get Advice", "brief": "Verifying licensing assumptions instead of taking them on faith."}]'::jsonb),
  ('INT-TEL-003', 'Ideation — Telecom Cost to Serve', 'TEL-002', '["RC-TEL-006", "RC-TEL-007"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Build a true cost sheet for serving one customer.", "Include interconnect and carrier fees, not just bandwidth.", "Compare that total against your planned price."]'::jsonb, '[{"name": "True Cost Per Customer", "brief": "A real cost that includes interconnect fees, not just headline bandwidth."}]'::jsonb),
  ('INT-TEL-004', 'Ideation — Telecom Cost to Serve', 'TEL-002', '["RC-TEL-008", "RC-TEL-009", "RC-TEL-010"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Count support cost and expected churn as real cost.", "Price from your own cost, not competitor rates.", "Check which customer segments are actually profitable."]'::jsonb, '[{"name": "Price From Real Cost, Check Segment Profitability", "brief": "Pricing grounded in real cost, checked against which segments actually pay off."}]'::jsonb),
  ('INT-TEL-005', 'Ideation — Telecom Segment Clarity', 'TEL-003', '["RC-TEL-011", "RC-TEL-012"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Choose one customer segment or use case to serve first.", "Design your product and pricing specifically for that segment.", "Say no to work outside that focus for now."]'::jsonb, '[{"name": "Pick One Segment", "brief": "A specific customer type instead of connectivity for anyone."}]'::jsonb),
  ('INT-TEL-006', 'Ideation — Telecom Segment Clarity', 'TEL-003', '["RC-TEL-013", "RC-TEL-014"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Talk to 10 real potential customers in your chosen segment.", "Adjust pricing and service level to fit what they actually need.", "Stop using the same offer for very different buyers."]'::jsonb, '[{"name": "Talk to Real Customers, Differentiate the Offer", "brief": "Validating and tailoring the offer to a specific segment."}]'::jsonb),
  ('INT-TEL-007', 'Ideation — Telecom Rollout Timeline Reality', 'TEL-004', '["RC-TEL-015", "RC-TEL-018"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Find a real comparable rollout and use its actual timeline.", "Rebuild your plan around that realistic timeline, not the best case.", "Revisit the timeline as you learn more."]'::jsonb, '[{"name": "Plan From a Real Comparable Rollout", "brief": "Grounding the timeline in an actual case, not the fastest imaginable one."}]'::jsonb),
  ('INT-TEL-008', 'Ideation — Telecom Rollout Timeline Reality', 'TEL-004', '["RC-TEL-016", "RC-TEL-017"]'::jsonb, '[1]'::jsonb, 'Operations', '["Research permits and right of way requirements before committing to a timeline.", "Confirm equipment lead times directly with suppliers.", "Build both into your rollout plan explicitly."]'::jsonb, '[{"name": "Confirm Permits and Lead Times", "brief": "Real approval and equipment timelines instead of assumptions."}]'::jsonb),
  ('INT-TEL-009', 'Validation to Traction — Telecom Network Reliability', 'TEL-005', '["RC-TEL-019", "RC-TEL-020"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Set up monitoring that flags degradation before it becomes an outage.", "Stop relying on customer complaints to learn about problems.", "Review monitoring alerts daily."]'::jsonb, '[{"name": "Monitor Before Customers Notice", "brief": "Catching degradation early instead of learning about outages from complaints."}]'::jsonb),
  ('INT-TEL-010', 'Validation to Traction — Telecom Network Reliability', 'TEL-005', '["RC-TEL-021", "RC-TEL-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Trace repeat outages to their actual root cause.", "Fix the cause permanently, not just the symptom.", "Define and track a service level standard."]'::jsonb, '[{"name": "Fix Root Causes, Track a Standard", "brief": "Permanent fixes and a defined quality standard, not repeated firefighting."}]'::jsonb),
  ('INT-TEL-011', 'Validation to Traction — Telecom Activation Delays', 'TEL-006', '["RC-TEL-023", "RC-TEL-025"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Build visibility into where every order sits in the activation process.", "Identify where manual handoffs are causing drops.", "Fix the weakest handoff point first."]'::jsonb, '[{"name": "See Where Orders Get Stuck", "brief": "Visibility into the activation pipeline instead of orders disappearing between teams."}]'::jsonb),
  ('INT-TEL-012', 'Validation to Traction — Telecom Activation Delays', 'TEL-006', '["RC-TEL-024", "RC-TEL-026"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Communicate a standard activation timeline at signup.", "Proactively update customers if a delay happens.", "Never let a customer be the one to ask for status."]'::jsonb, '[{"name": "Set Expectations, Update Proactively", "brief": "Clear timelines upfront and proactive updates instead of customers chasing status."}]'::jsonb),
  ('INT-TEL-013', 'Validation to Traction — Telecom Billing Accuracy', 'TEL-007', '["RC-TEL-027", "RC-TEL-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Build a reconciliation step checking usage before billing.", "Catch mismatches before the invoice goes out, not after.", "Track how often reconciliation catches an error."]'::jsonb, '[{"name": "Reconcile Before You Bill", "brief": "Catching billing errors before the customer sees them."}]'::jsonb),
  ('INT-TEL-014', 'Validation to Traction — Telecom Billing Accuracy', 'TEL-007', '["RC-TEL-029", "RC-TEL-030"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Standardise how refunds and credits are handled.", "Apply the same resolution to similar disputes.", "Track billing disputes as a share of total support load."]'::jsonb, '[{"name": "Standardise Dispute Resolution", "brief": "Consistent handling of refunds and credits across similar cases."}]'::jsonb),
  ('INT-TEL-015', 'Validation to Traction — Telecom Churn Diagnosis', 'TEL-008', '["RC-TEL-031", "RC-TEL-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Track churn separately by segment and plan type.", "Capture the actual reason when a customer leaves.", "Use both to find where churn concentrates."]'::jsonb, '[{"name": "Track Churn by Segment, Capture Exit Reasons", "brief": "Breaking churn down instead of watching one blended number."}]'::jsonb),
  ('INT-TEL-016', 'Validation to Traction — Telecom Churn Diagnosis', 'TEL-008', '["RC-TEL-033", "RC-TEL-034"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Build a specific retention offer for the highest churn group.", "Slow acquisition into a segment that churns fast until it is fixed.", "Measure whether the offer actually reduces churn."]'::jsonb, '[{"name": "Target the At Risk Segment", "brief": "A specific retention response instead of pouring new customers into a leaky segment."}]'::jsonb),
  ('INT-TEL-017', 'Validation to Traction — Telecom Upstream Dependency', 'TEL-009', '["RC-TEL-035", "RC-TEL-036"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Identify a backup interconnect arrangement for critical connectivity.", "Test it before you actually need it.", "Reduce reliance on a single upstream partner over time."]'::jsonb, '[{"name": "Build a Backup Interconnect", "brief": "A tested fallback so one partner failure does not stop the business."}]'::jsonb),
  ('INT-TEL-018', 'Validation to Traction — Telecom Upstream Dependency', 'TEL-009', '["RC-TEL-037", "RC-TEL-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Check your upstream partner reliability track record.", "Negotiate rather than automatically absorbing price rises.", "Use both to inform whether to diversify."]'::jsonb, '[{"name": "Know Partner Reliability, Negotiate Price", "brief": "Visibility into partner performance and active management of cost increases."}]'::jsonb),
  ('INT-TEL-019', 'Growth to Maturity — Telecom Account Concentration', 'TEL-010', '["RC-TEL-039", "RC-TEL-041"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Calculate the revenue share of your top three accounts.", "Set a ceiling and build a pipeline of smaller accounts.", "Review the share every quarter."]'::jsonb, '[{"name": "Cap Account Concentration", "brief": "Measuring dependence and building beyond the dominant few."}]'::jsonb),
  ('INT-TEL-020', 'Growth to Maturity — Telecom Account Concentration', 'TEL-010', '["RC-TEL-040", "RC-TEL-042"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Work out your real margin on the dominant account after their terms.", "Separate network priority decisions from any single account.", "Design capacity plans for your wider base, not just one client."]'::jsonb, '[{"name": "Design for the Base, Not One Account", "brief": "Keeping infrastructure priorities grounded in the wider customer base."}]'::jsonb),
  ('INT-TEL-021', 'Growth to Maturity — Telecom Network Scaling', 'TEL-011', '["RC-TEL-043", "RC-TEL-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Track congestion at peak times as a leading indicator.", "Align capacity investment with actual traffic growth.", "Plan ahead of demand rather than reacting to it."]'::jsonb, '[{"name": "Plan Capacity Ahead of Demand", "brief": "Proactive capacity investment instead of reacting to congestion after it appears."}]'::jsonb),
  ('INT-TEL-022', 'Growth to Maturity — Telecom Network Scaling', 'TEL-011', '["RC-TEL-044", "RC-TEL-046"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Test new equipment thoroughly before full deployment.", "Build redundancy into every newly added critical path.", "Do not treat new infrastructure as exempt from the standards applied to the rest of the network."]'::jsonb, '[{"name": "Test New Equipment, Build In Redundancy", "brief": "Applying the same reliability standards to new infrastructure as to the old."}]'::jsonb),
  ('INT-TEL-023', 'Growth to Maturity — Telecom Regulatory Compliance', 'TEL-012', '["RC-TEL-047", "RC-TEL-048"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Build one calendar covering every filing, renewal and reporting obligation.", "Set reminders well ahead of each date.", "Review it monthly."]'::jsonb, '[{"name": "One Compliance Calendar", "brief": "Every recurring obligation and deadline in one dated place."}]'::jsonb),
  ('INT-TEL-024', 'Growth to Maturity — Telecom Regulatory Compliance', 'TEL-012', '["RC-TEL-049", "RC-TEL-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Identify reporting obligations well ahead of their deadline.", "Close compliance findings permanently instead of letting them repeat.", "Train a second person on the whole compliance picture."]'::jsonb, '[{"name": "Prepare Early, Fix Permanently", "brief": "Advance notice of obligations and lasting fixes instead of repeated findings."}]'::jsonb),
  ('INT-TEL-025', 'Growth to Maturity — Telecom Fraud and Leakage', 'TEL-013', '["RC-TEL-051", "RC-TEL-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Set up systematic detection for unusual usage patterns.", "Reconcile usage against billed revenue on a regular schedule.", "Investigate discrepancies as soon as they appear."]'::jsonb, '[{"name": "Detect and Reconcile Regularly", "brief": "Systematic fraud detection and scheduled revenue assurance checks."}]'::jsonb),
  ('INT-TEL-026', 'Growth to Maturity — Telecom Fraud and Leakage', 'TEL-013', '["RC-TEL-052", "RC-TEL-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Name someone specifically responsible for fraud and leakage control.", "Audit for unbilled or underbilled traffic regularly.", "Track recovered revenue as a measure of success."]'::jsonb, '[{"name": "Own Fraud and Leakage Control", "brief": "A dedicated owner and regular audits instead of losses discovered too late."}]'::jsonb),
  ('INT-TEL-027', 'Growth to Maturity — Telecom Technology Evolution', 'TEL-014', '["RC-TEL-055", "RC-TEL-057"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Build a simple process for evaluating new network technology.", "Set aside a budget for technology refresh.", "Review and adopt on a fixed schedule rather than reactively."]'::jsonb, '[{"name": "A Process and Budget for Technology Refresh", "brief": "Systematic evaluation and funded upgrades instead of falling behind."}]'::jsonb),
  ('INT-TEL-028', 'Growth to Maturity — Telecom Technology Evolution', 'TEL-014', '["RC-TEL-056"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Assess what capital tied up in older infrastructure is really costing you.", "Weigh the cost of holding on against the cost of upgrading.", "Make the decision explicit rather than by default."]'::jsonb, '[{"name": "Face the Sunk Cost Honestly", "brief": "An explicit decision about older infrastructure instead of holding on by default."}]'::jsonb),
  ('INT-TEL-029', 'Growth to Maturity — Telecom Defensibility', 'TEL-015', '["RC-TEL-058", "RC-TEL-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Build a bundled service or platform advantage beyond raw connectivity.", "Make it central to the customer relationship, not a side feature.", "Use it as the reason to choose you over a competitor."]'::jsonb, '[{"name": "Build Beyond Raw Connectivity", "brief": "A bundled advantage that a competitor cannot simply match on price."}]'::jsonb),
  ('INT-TEL-030', 'Growth to Maturity — Telecom Defensibility', 'TEL-015', '["RC-TEL-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Build a data or relationship asset that deepens over time.", "Track how often customers leave for a marginally cheaper competitor.", "Use the asset to reduce that churn."]'::jsonb, '[{"name": "Build an Asset That Deepens Over Time", "brief": "A relationship or data advantage that a new provider cannot replicate on day one."}]'::jsonb),
  ('INT-TEL-031', 'Ideation — Telecom Segment Clarity', 'TEL-003', '["RC-TEL-061"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Research what adoption rate a comparable connectivity offer has actually achieved.", "Use that as a realistic planning baseline.", "Adjust your growth projections around it."]'::jsonb, '[{"name": "Use a Real Comparable Adoption Rate", "brief": "Planning around researched numbers instead of an optimistic guess."}]'::jsonb),
  ('INT-TEL-032', 'Ideation — Telecom Rollout Timeline Reality', 'TEL-004', '["RC-TEL-062"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Write a specific plan for what happens if a rollout milestone is missed.", "Identify what would need to change in the business plan.", "Test the plan against your worst realistic delay."]'::jsonb, '[{"name": "Plan for a Missed Milestone", "brief": "A specific response ready before a rollout delay forces a scramble."}]'::jsonb),
  ('INT-TEL-033', 'Validation to Traction — Telecom Network Reliability', 'TEL-005', '["RC-TEL-063"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Define an escalation path for an outage that runs longer than expected.", "Assign clear ownership at each escalation step.", "Test the path before a real prolonged outage happens."]'::jsonb, '[{"name": "Define Escalation for Prolonged Outages", "brief": "A tested escalation path instead of confusion when an outage drags on."}]'::jsonb),
  ('INT-TEL-034', 'Growth to Maturity — Telecom Account Concentration', 'TEL-010', '["RC-TEL-064"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Review which accounts deserve the most attention on a fixed schedule.", "Reallocate effort as performance shifts.", "Do not let prioritisation freeze around old relationships."]'::jsonb, '[{"name": "Review Priorities on a Schedule", "brief": "Periodic reassessment instead of default loyalty to whoever mattered first."}]'::jsonb)
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
        ('Textiles', 'textiles', 'TXT', r"""-- ============================================================================
-- Ally :: Industry seed -- TEXTILES (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: textiles
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (TXT-001, RC-TXT-014, S0-TXT-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : questions name no specific labour statute, safety standard or
--            sustainability certification scheme.  These vary by market and
--            change, so the content asks the founder what applies to THEM and
--            what has actually been checked, rather than naming a rule that
--            will go stale.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (quality consistency, input cost volatility,
--            skill dependency, working capital, compliance basics) starts at
--            Stage 0->1; buyer concentration, scaling quality, sustainability
--            compliance, supplier dependency, trend responsiveness and
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
  ('TXT-001', 'No Clear Product Category or Customer Chosen', 'The business tries to produce fabric, garments and finished goods for very different buyer types at once, so nothing about the range is distinctive.', 'Idea & Validation', 'Textiles Product Clarity', 'external', 2, 4, 8, '["Willing to produce almost any fabric or garment type", "No specific end customer or use case designed for", "Product range decided without a clear theme", "No conversation with a real buyer", "Assuming any order is a good order"]'::jsonb, '["textiles"]'::jsonb),
  ('TXT-002', 'Real Cost of Production Not Worked Out', 'Raw material, labour, wastage and finishing costs are not tracked, so nobody knows the true cost of a finished unit.', 'Idea & Validation', 'Textiles Cost Reality', 'external', 4, 5, 9, '["Only raw material cost counted", "Labour and finishing cost not factored in", "Wastage and rejects not counted as cost", "Price set by looking at competitors only", "No idea what margin is left after real costs"]'::jsonb, '["textiles"]'::jsonb),
  ('TXT-003', 'No Idea How Much to Produce Before Confirmed Orders', 'Fabric or garments are produced on assumption, with no test run or confirmed demand behind the quantity.', 'Idea & Validation', 'Textiles Production Planning', 'external', 3, 5, 9, '["Production quantity based on gut feel", "No sample or test run before a full batch", "No confirmed order before committing raw material", "Assuming unsold stock can always be discounted later", "No plan for what happens to unsold inventory"]'::jsonb, '["textiles"]'::jsonb),
  ('TXT-004', 'Buyer or Channel Chosen Without Testing Real Demand', 'A wholesale buyer, retail channel or export market was chosen before confirming that real demand exists there.', 'Idea & Validation', 'Textiles Channel Clarity', 'external', 3, 5, 9, '["Channel chosen on convenience, not evidence of demand", "No sample sent to a real buyer before committing", "No conversation with a real buyer about their actual needs", "Assuming a good product sells itself", "No small test order before a full commitment"]'::jsonb, '["textiles"]'::jsonb),
  ('TXT-005', 'Quality Rejections From Buyers Eating Into Margin', 'Finished goods are rejected or discounted by buyers for quality issues at a rate that is quietly destroying profitability.', 'Operations & Systems', 'Textiles Quality Consistency', 'external', 4, 6, 9, '["Rejection rate not tracked systematically", "Quality issues discovered only after buyer inspection", "No standard quality check before shipment", "Rework and rejects consuming unplanned time and cost", "Same defects recurring across batches"]'::jsonb, '["textiles"]'::jsonb),
  ('TXT-006', 'Raw Material Price Swings Not Managed', 'Yarn, fabric and dye prices move sharply, and contracts priced in advance leave no way to pass the change on.', 'Financial Management', 'Textiles Input Cost Volatility', 'external', 4, 6, 9, '["Raw material prices moving after an order is priced", "No hedging or forward buying strategy", "Margin varying unpredictably order to order", "No clause allowing price adjustment with buyers", "Cash flow strained by unexpected input cost spikes"]'::jsonb, '["textiles"]'::jsonb),
  ('TXT-007', 'Everything Depends on a Few Skilled Workers', 'Cutting, stitching or finishing quality depends on a handful of experienced workers, and losing any one disrupts production badly.', 'Team & Leadership', 'Textiles Skill Dependency', 'external', 3, 6, 9, '["Key production steps run by specific workers only", "High skilled worker turnover", "No standard training for new workers", "Customer facing quality tied to individual skill", "No backup when a skilled worker is unavailable"]'::jsonb, '["textiles"]'::jsonb),
  ('TXT-008', 'Working Capital Squeezed by Buyer Payment Terms', 'Buyers pay on long credit while raw material and labour must be paid immediately, straining cash constantly.', 'Financial Management', 'Textiles Working Capital', 'external', 4, 6, 9, '["Long credit given to buyers", "Raw material and labour paid immediately", "No credit facility sized to the real gap", "Growth making the cash position worse", "Payment cycle length never measured"]'::jsonb, '["textiles"]'::jsonb),
  ('TXT-009', 'Compliance and Labour Standards Not Properly Managed', 'Labour law, safety standards and buyer compliance audits are handled informally, creating real risk when an audit or inspection happens.', 'Operations & Systems', 'Textiles Compliance Basics', 'external', 3, 7, 10, '["No consistent process for labour compliance", "Safety standards not checked against requirements", "Buyer compliance audits handled reactively", "Documentation incomplete when an audit occurs", "No one responsible for compliance specifically"]'::jsonb, '["textiles"]'::jsonb),
  ('TXT-010', 'Revenue Concentrated in a Few Large Buyers', 'A handful of buyers account for most revenue, so they set the terms and their loss would be severe.', 'Sales & Revenue', 'Textiles Buyer Concentration', 'external', 4, 7, 10, '["Most revenue from a few large buyers", "Prices dictated by the dominant buyer", "No pipeline of replacement buyers", "Losing one buyer would threaten the business", "Production priorities shaped by one buyer"]'::jsonb, '["textiles"]'::jsonb),
  ('TXT-011', 'Scaling Production While Holding Quality Constant', 'Producing far more volume without any drop in the consistency buyers depend on is proving difficult.', 'Operations & Systems', 'Textiles Scaling Quality', 'external', 3, 7, 10, '["Quality variation increasing with higher volume", "Second production line not matching the first", "Supply chain now involving many more input sources", "Capacity constraints limiting how much can be produced", "No redundancy if one production line fails"]'::jsonb, '["textiles"]'::jsonb),
  ('TXT-012', 'Environmental and Sustainability Requirements Now a Constant Demand', 'Buyers and regulations increasingly require sustainability certifications and environmental compliance that the business cannot yet demonstrate.', 'Operations & Systems', 'Textiles Sustainability Compliance', 'external', 3, 7, 10, '["Buyers asking for sustainability certifications not yet held", "No process for tracking environmental compliance", "Certification costs and timelines underestimated", "Competitors already certified taking preference in bids", "No budget allocated for sustainability investment"]'::jsonb, '["textiles"]'::jsonb),
  ('TXT-013', 'Supplier Dependency Creating Fragile Supply', 'Key raw materials come from one or two suppliers, so a delay, price rise or quality issue on their end disrupts the whole production line.', 'Operations & Systems', 'Textiles Supplier Dependency', 'external', 3, 7, 10, '["Key raw materials sourced from a single supplier", "No backup supplier identified", "Supplier price increases passed through unmanaged", "Quality issues traced back to one source repeatedly", "No visibility into supplier lead times"]'::jsonb, '["textiles"]'::jsonb),
  ('TXT-014', 'Fashion and Trend Cycles Outpacing Production Capability', 'Trends and buyer preferences shift faster than the business can design, sample and produce against them.', 'Strategy & Planning', 'Textiles Trend Responsiveness', 'external', 2, 6, 10, '["Design to production time longer than the trend cycle", "Competitors bringing new designs to market faster", "No process for tracking emerging trends", "Capital tied up in styles that are already dated", "No fast turnaround capability for smaller trend runs"]'::jsonb, '["textiles"]'::jsonb),
  ('TXT-015', 'Nothing Differentiates This From Any Other Manufacturer', 'Buyers can switch to a similar manufacturer at similar cost with little friction, because nothing built here creates real loyalty.', 'Strategy & Planning', 'Textiles Defensibility', 'external', 2, 6, 10, '["Products easily matched by competitors", "Price the main basis of buyer decisions", "No proprietary fabric, technique or design advantage", "No exclusive relationship or capability beyond price", "Buyer churn to marginally cheaper alternatives"]'::jsonb, '["textiles"]'::jsonb)
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
         t.primary_stage_group, '["textiles"]'::jsonb, z.v
  FROM (VALUES
  ('RC-TXT-001', 'Willing to Produce Any Fabric or Garment Type', 'No focus exists on a specific product category.', 'TXT-001', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-TXT-002', 'No Specific End Customer Designed For', 'Nothing distinguishes who this range is actually made for.', 'TXT-001', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-TXT-003', 'Range Decided Without a Clear Theme', 'Products do not connect around a single customer need.', 'TXT-001', 'external', 'Behavioural', 0.68, 'Stage 0'),
  ('RC-TXT-004', 'No Conversation With a Real Buyer', 'Nobody who would actually order has been spoken to.', 'TXT-001', 'external', 'Behavioural', 0.66, 'Stage 0'),
  ('RC-TXT-005', 'Assuming Any Order Is a Good Order', 'Believing volume alone justifies taking any order that comes in.', 'TXT-001', 'external', 'Psychological', 0.67, 'Stage 0'),
  ('RC-TXT-006', 'Only Raw Material Cost Counted', 'The cost is taken as fabric or yarn price alone.', 'TXT-002', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-TXT-007', 'Labour and Finishing Cost Not Factored In', 'Stitching, dyeing and finishing costs are missing from the price.', 'TXT-002', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-TXT-008', 'Wastage and Rejects Not Counted', 'Material lost to cutting waste and defects is not counted as cost.', 'TXT-002', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-TXT-009', 'Price Set by Looking at Competitors', 'Pricing copies others without knowing own true cost.', 'TXT-002', 'external', 'Behavioural', 0.67, 'Stage 0'),
  ('RC-TXT-010', 'No Idea What Margin Is Left', 'Nobody has calculated actual margin after real costs.', 'TXT-002', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-TXT-011', 'Production Quantity Based on Gut Feel', 'How much to produce is decided without data behind it.', 'TXT-003', 'external', 'Behavioural', 0.72, 'Stage 0'),
  ('RC-TXT-012', 'No Sample or Test Run Before Full Batch', 'A trial production run was skipped in favour of a full batch.', 'TXT-003', 'external', 'Behavioural', 0.70, 'Stage 0'),
  ('RC-TXT-013', 'No Confirmed Order Before Committing Material', 'Raw material is bought before a real order is in hand.', 'TXT-003', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-TXT-014', 'Assuming Unsold Stock Can Be Discounted Later', 'Believing markdown will always clear excess inventory.', 'TXT-003', 'external', 'Psychological', 0.68, 'Stage 0'),
  ('RC-TXT-015', 'Channel Chosen on Convenience Not Demand', 'The channel was picked for ease, not evidence of buyers there.', 'TXT-004', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-TXT-016', 'No Sample Sent to a Real Buyer', 'Nobody has tested the product with an actual potential buyer.', 'TXT-004', 'external', 'Behavioural', 0.70, 'Stage 0'),
  ('RC-TXT-017', 'No Conversation About Buyer Actual Needs', 'What the buyer actually wants has not been asked.', 'TXT-004', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-TXT-018', 'Assuming a Good Product Sells Itself', 'Believing quality alone will secure orders without active selling.', 'TXT-004', 'external', 'Psychological', 0.67, 'Stage 0'),
  ('RC-TXT-019', 'Rejection Rate Not Tracked', 'How often buyers reject or discount goods is not measured.', 'TXT-005', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-TXT-020', 'Quality Issues Found Only at Buyer Inspection', 'Nothing internal catches defects before the buyer does.', 'TXT-005', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-TXT-021', 'No Standard Quality Check Before Shipment', 'Goods leave without a consistent internal check.', 'TXT-005', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-TXT-022', 'Same Defects Recurring Across Batches', 'The same quality issue is not being traced or fixed.', 'TXT-005', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-TXT-023', 'Raw Material Prices Moving After Order Priced', 'Input costs change after the price is already committed.', 'TXT-006', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-TXT-024', 'No Hedging or Forward Buying Strategy', 'Nothing protects the business from input price swings.', 'TXT-006', 'external', 'Strategic', 0.71, 'Stage 0→1'),
  ('RC-TXT-025', 'No Price Adjustment Clause With Buyers', 'Contracts do not allow passing on a raw material cost change.', 'TXT-006', 'external', 'Strategic', 0.70, 'Stage 0→1'),
  ('RC-TXT-026', 'Margin Varying Unpredictably by Order', 'Profitability differs order to order with no clear pattern tracked.', 'TXT-006', 'external', 'Knowledge', 0.68, 'Stage 0→1'),
  ('RC-TXT-027', 'Key Production Steps Run by Specific Workers', 'Certain processes work only because one worker knows them.', 'TXT-007', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-TXT-028', 'High Skilled Worker Turnover', 'Experienced workers leave frequently.', 'TXT-007', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-TXT-029', 'No Standard Training for New Workers', 'New workers learn informally with no defined process.', 'TXT-007', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-TXT-030', 'No Backup When a Skilled Worker Is Unavailable', 'Production stops or slows when one key person is out.', 'TXT-007', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-TXT-031', 'Long Credit Given to Buyers', 'Buyers are allowed to pay well after delivery.', 'TXT-008', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-TXT-032', 'Raw Material and Labour Paid Immediately', 'Production costs must be settled with no delay.', 'TXT-008', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-TXT-033', 'No Credit Facility Sized to the Real Gap', 'Financing has not been matched to the actual cash timing gap.', 'TXT-008', 'external', 'Strategic', 0.70, 'Stage 0→1'),
  ('RC-TXT-034', 'Payment Cycle Length Never Measured', 'How many days cash is tied up has not been calculated.', 'TXT-008', 'external', 'Knowledge', 0.68, 'Stage 0→1'),
  ('RC-TXT-035', 'No Consistent Process for Labour Compliance', 'Labour requirements are not tracked or applied systematically.', 'TXT-009', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-TXT-036', 'Safety Standards Not Checked', 'Whether the facility meets required safety standards has not been verified.', 'TXT-009', 'external', 'Knowledge', 0.71, 'Stage 0→1'),
  ('RC-TXT-037', 'Buyer Compliance Audits Handled Reactively', 'Audit preparation happens only once an audit is announced.', 'TXT-009', 'external', 'Behavioural', 0.70, 'Stage 0→1'),
  ('RC-TXT-038', 'No One Responsible for Compliance', 'Nobody owns tracking and maintaining compliance.', 'TXT-009', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-TXT-039', 'Most Revenue From a Few Large Buyers', 'A handful of buyers carry most of the business.', 'TXT-010', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-TXT-040', 'Prices Dictated by the Dominant Buyer', 'The largest buyer sets what can be charged.', 'TXT-010', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-TXT-041', 'No Pipeline of Replacement Buyers', 'Nothing is being built that could replace a lost buyer.', 'TXT-010', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-TXT-042', 'Production Priorities Shaped by One Buyer', 'The dominant buyer decides what gets made rather than the wider business.', 'TXT-010', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-TXT-043', 'Quality Variation Increasing With Volume', 'Consistency degrades as production scales up.', 'TXT-011', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-TXT-044', 'Second Line Not Matching the First', 'A new production line produces different results from the original.', 'TXT-011', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-TXT-045', 'Supply Chain Involving Many More Input Sources', 'Growth has multiplied the number of suppliers and dependencies.', 'TXT-011', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-TXT-046', 'No Redundancy if One Line Fails', 'A single production line failure would stop all output.', 'TXT-011', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-TXT-047', 'Buyers Asking for Certifications Not Yet Held', 'Sustainability requirements are appearing faster than they can be met.', 'TXT-012', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-TXT-048', 'No Process for Tracking Environmental Compliance', 'Nothing systematically monitors environmental requirements.', 'TXT-012', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-TXT-049', 'Certification Costs and Timelines Underestimated', 'What certification actually takes has not been researched properly.', 'TXT-012', 'external', 'Knowledge', 0.70, 'Stage 1→10+'),
  ('RC-TXT-050', 'Competitors Already Certified Taking Preference', 'Rivals with certification are winning bids this business cannot.', 'TXT-012', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-TXT-051', 'Key Materials From a Single Supplier', 'Critical inputs have only one source.', 'TXT-013', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-TXT-052', 'No Backup Supplier Identified', 'Nothing has been arranged if the main supplier fails.', 'TXT-013', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-TXT-053', 'Supplier Price Increases Passed Through Unmanaged', 'Cost rises are absorbed or passed on without negotiation.', 'TXT-013', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-TXT-054', 'No Visibility Into Supplier Lead Times', 'How long a supplier actually takes to deliver is unknown.', 'TXT-013', 'external', 'Knowledge', 0.68, 'Stage 1→10+'),
  ('RC-TXT-055', 'Design to Production Time Longer Than the Trend Cycle', 'The business cannot move fast enough to catch a trend before it passes.', 'TXT-014', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-TXT-056', 'No Process for Tracking Emerging Trends', 'Nothing systematically watches for what is coming next.', 'TXT-014', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-TXT-057', 'No Fast Turnaround Capability', 'There is no way to run a smaller, quicker batch for a fast moving trend.', 'TXT-014', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-TXT-058', 'Products Easily Matched by Competitors', 'What is offered can be replicated without much effort.', 'TXT-015', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-TXT-059', 'No Proprietary Fabric or Technique', 'Nothing about the product is hard for a competitor to copy.', 'TXT-015', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-TXT-060', 'No Exclusive Relationship Beyond Price', 'Nothing besides being cheap keeps a buyer with this business.', 'TXT-015', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-TXT-061', 'No Idea What a Realistic Order Size Looks Like', 'How large a typical first order from a comparable buyer actually is has not been researched.', 'TXT-004', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-TXT-062', 'No Conversation About What Discounting Would Do to the Brand', 'The long term effect of relying on markdowns has not been considered.', 'TXT-003', 'external', 'Behavioural', 0.65, 'Stage 0'),
  ('RC-TXT-063', 'No Regular Quality Audit Independent of Buyer Inspection', 'Nobody checks quality internally on a schedule separate from what the buyer catches.', 'TXT-005', 'external', 'Operational', 0.66, 'Stage 0→1'),
  ('RC-TXT-064', 'No Cross Training Between Production Lines', 'Workers on one line cannot easily cover or learn from another.', 'TXT-011', 'external', 'Operational', 0.66, 'Stage 1→10+'),
  ('RC-TXT-065', 'No Regular Review of Which Buyers to Prioritise', 'Nobody periodically reassesses which buyers deserve the most attention.', 'TXT-010', 'external', 'Operational', 0.66, 'Stage 1→10+'),
  ('RC-TXT-066', 'No Regular Benchmarking Against Competitor Products', 'Nobody checks what competitors are actually offering on design or price.', 'TXT-015', 'external', 'Knowledge', 0.65, 'Stage 1→10+')
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
         '["textiles"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-TXT-001', 'Will you produce any fabric or garment type, or have you chosen a category?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-001', 'RC-TXT-001', 1, 'Stage 0'),
  ('S0-TXT-002', 'Who exactly is your end customer for this range?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-001', 'RC-TXT-002', 1, 'Stage 0'),
  ('S0-TXT-003', 'Does your product range connect around one clear theme?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-001', 'RC-TXT-003', 2, 'Stage 0'),
  ('S0-TXT-004', 'Have you talked to a real buyer who would actually order?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-001', 'RC-TXT-004', 2, 'Stage 0'),
  ('S0-TXT-005', 'Do you take any order that comes in, or only ones that fit your focus?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-001', 'RC-TXT-005', 2, 'Stage 0'),
  ('S0-TXT-006', 'What does one finished unit actually cost you, beyond raw material?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-002', 'RC-TXT-006', 1, 'Stage 0'),
  ('S0-TXT-007', 'Have you factored in labour and finishing cost?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-002', 'RC-TXT-007', 2, 'Stage 0'),
  ('S0-TXT-008', 'Have you counted wastage and rejects as a real cost?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-002', 'RC-TXT-008', 2, 'Stage 0'),
  ('S0-TXT-009', 'Did you set your price from your own cost or from competitors?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-002', 'RC-TXT-009', 2, 'Stage 0'),
  ('S0-TXT-010', 'Do you know what margin is actually left after real costs?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-002', 'RC-TXT-010', 2, 'Stage 0'),
  ('S0-TXT-011', 'How did you decide how much to produce?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-003', 'RC-TXT-011', 1, 'Stage 0'),
  ('S0-TXT-012', 'Did you run a sample or test batch before a full production run?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-003', 'RC-TXT-012', 2, 'Stage 0'),
  ('S0-TXT-013', 'Did you have a confirmed order before committing to raw material?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-003', 'RC-TXT-013', 2, 'Stage 0'),
  ('S0-TXT-014', 'What is your plan for stock that does not sell?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-003', 'RC-TXT-014', 2, 'Stage 0'),
  ('S0-TXT-015', 'Have you sent a sample to a real buyer before committing to this channel?', 'open_text', 'Idea & Validation', 'CORE', 'TXT-004', 'RC-TXT-016', 1, 'Stage 0'),
  ('S01-TXT-001', 'Do you track your rejection rate from buyers?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-005', 'RC-TXT-019', 2, 'Stage 0→1'),
  ('S01-TXT-002', 'Do quality issues get caught internally, or only at buyer inspection?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-005', 'RC-TXT-020', 2, 'Stage 0→1'),
  ('S01-TXT-003', 'Is there a standard quality check before goods ship?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-005', 'RC-TXT-021', 2, 'Stage 0→1'),
  ('S01-TXT-004', 'Have the same defects shown up across more than one batch?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-005', 'RC-TXT-022', 2, 'Stage 0→1'),
  ('S01-TXT-005', 'Have raw material prices moved after you already priced an order?', 'open_text', 'Financial Management', 'CORE', 'TXT-006', 'RC-TXT-023', 2, 'Stage 0→1'),
  ('S01-TXT-006', 'Do you have any strategy to manage input price swings?', 'open_text', 'Financial Management', 'CORE', 'TXT-006', 'RC-TXT-024', 2, 'Stage 0→1'),
  ('S01-TXT-007', 'Do your contracts allow adjusting price when raw material costs change?', 'open_text', 'Financial Management', 'CORE', 'TXT-006', 'RC-TXT-025', 3, 'Stage 0→1'),
  ('S01-TXT-008', 'Does your margin vary a lot from order to order?', 'open_text', 'Financial Management', 'CORE', 'TXT-006', 'RC-TXT-026', 2, 'Stage 0→1'),
  ('S01-TXT-009', 'Are there production steps that only work because of one specific worker?', 'open_text', 'Team & Leadership', 'CORE', 'TXT-007', 'RC-TXT-027', 2, 'Stage 0→1'),
  ('S01-TXT-010', 'How many skilled workers have left in the last year?', 'open_text', 'Team & Leadership', 'CORE', 'TXT-007', 'RC-TXT-028', 2, 'Stage 0→1'),
  ('S01-TXT-011', 'How does a new worker learn your quality standards?', 'open_text', 'Team & Leadership', 'CORE', 'TXT-007', 'RC-TXT-029', 2, 'Stage 0→1'),
  ('S01-TXT-012', 'What happens to production when a key worker is unavailable?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-007', 'RC-TXT-030', 2, 'Stage 0→1'),
  ('S01-TXT-013', 'How long do buyers typically take to pay you?', 'open_text', 'Financial Management', 'CORE', 'TXT-008', 'RC-TXT-031', 2, 'Stage 0→1'),
  ('S01-TXT-014', 'How quickly must you pay for raw material and labour?', 'open_text', 'Financial Management', 'CORE', 'TXT-008', 'RC-TXT-032', 2, 'Stage 0→1'),
  ('S01-TXT-015', 'Do you have a credit facility sized to that gap?', 'open_text', 'Financial Management', 'CORE', 'TXT-008', 'RC-TXT-033', 2, 'Stage 0→1'),
  ('S01-TXT-016', 'Has anyone measured how many days your cash is tied up?', 'open_text', 'Financial Management', 'CORE', 'TXT-008', 'RC-TXT-034', 3, 'Stage 0→1'),
  ('S01-TXT-017', 'Is labour compliance tracked systematically or handled informally?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-009', 'RC-TXT-035', 2, 'Stage 0→1'),
  ('S01-TXT-018', 'Have your safety standards been checked against what is required?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-009', 'RC-TXT-036', 3, 'Stage 0→1'),
  ('S01-TXT-019', 'How do you prepare for a buyer compliance audit?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-009', 'RC-TXT-037', 3, 'Stage 0→1'),
  ('S01-TXT-020', 'Is anyone specifically responsible for compliance?', 'open_text', 'Team & Leadership', 'CORE', 'TXT-009', 'RC-TXT-038', 2, 'Stage 0→1'),
  ('S10-TXT-001', 'What share of your revenue comes from your top two or three buyers?', 'open_text', 'Sales & Revenue', 'CORE', 'TXT-010', 'RC-TXT-039', 2, 'Stage 1→10+'),
  ('S10-TXT-002', 'Who sets your prices, you or your largest buyer?', 'open_text', 'Sales & Revenue', 'CORE', 'TXT-010', 'RC-TXT-040', 2, 'Stage 1→10+'),
  ('S10-TXT-003', 'If your largest buyer left, how long could you continue?', 'open_text', 'Strategy & Planning', 'CORE', 'TXT-010', 'RC-TXT-041', 3, 'Stage 1→10+'),
  ('S10-TXT-004', 'Is your production being shaped by one buyer rather than your wider business?', 'open_text', 'Strategy & Planning', 'CORE', 'TXT-010', 'RC-TXT-042', 3, 'Stage 1→10+'),
  ('S10-TXT-005', 'Has quality variation increased as you have scaled production?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-011', 'RC-TXT-043', 2, 'Stage 1→10+'),
  ('S10-TXT-006', 'Does a second production line match the first in output?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-011', 'RC-TXT-044', 3, 'Stage 1→10+'),
  ('S10-TXT-007', 'How many suppliers is your supply chain now depending on?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-011', 'RC-TXT-045', 2, 'Stage 1→10+'),
  ('S10-TXT-008', 'If one production line failed, could you still fulfil orders?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-011', 'RC-TXT-046', 3, 'Stage 1→10+'),
  ('S10-TXT-009', 'Have buyers asked for sustainability certifications you do not hold?', 'open_text', 'Sales & Revenue', 'CORE', 'TXT-012', 'RC-TXT-047', 2, 'Stage 1→10+'),
  ('S10-TXT-010', 'Do you track environmental compliance requirements systematically?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-012', 'RC-TXT-048', 3, 'Stage 1→10+'),
  ('S10-TXT-011', 'Have you researched what certification actually costs and takes?', 'open_text', 'Financial Management', 'CORE', 'TXT-012', 'RC-TXT-049', 3, 'Stage 1→10+'),
  ('S10-TXT-012', 'Have you lost a bid to a certified competitor?', 'open_text', 'Sales & Revenue', 'CORE', 'TXT-012', 'RC-TXT-050', 2, 'Stage 1→10+'),
  ('S10-TXT-013', 'Is there any raw material you can only get from one supplier?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-013', 'RC-TXT-051', 2, 'Stage 1→10+'),
  ('S10-TXT-014', 'Do you have a backup supplier for your key materials?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-013', 'RC-TXT-052', 2, 'Stage 1→10+'),
  ('S10-TXT-015', 'When a supplier raises prices, how do you respond?', 'open_text', 'Financial Management', 'CORE', 'TXT-013', 'RC-TXT-053', 2, 'Stage 1→10+'),
  ('S10-TXT-016', 'Do you know how long your suppliers actually take to deliver?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-013', 'RC-TXT-054', 2, 'Stage 1→10+'),
  ('S10-TXT-017', 'Is your design to production time longer than the trends you are chasing?', 'open_text', 'Strategy & Planning', 'CORE', 'TXT-014', 'RC-TXT-055', 3, 'Stage 1→10+'),
  ('S10-TXT-018', 'Do you have a process for tracking emerging trends?', 'open_text', 'Strategy & Planning', 'CORE', 'TXT-014', 'RC-TXT-056', 2, 'Stage 1→10+'),
  ('S10-TXT-019', 'Can you run a smaller, quicker batch for a fast moving trend?', 'open_text', 'Operations & Systems', 'CORE', 'TXT-014', 'RC-TXT-057', 3, 'Stage 1→10+'),
  ('S10-TXT-020', 'How easily could a competitor copy your products?', 'open_text', 'Strategy & Planning', 'CORE', 'TXT-015', 'RC-TXT-058', 3, 'Stage 1→10+'),
  ('S10-TXT-021', 'Do buyers choose you mainly on price or on something else?', 'open_text', 'Sales & Revenue', 'CORE', 'TXT-015', 'RC-TXT-058', 2, 'Stage 1→10+'),
  ('S10-TXT-022', 'Do you have any proprietary fabric or technique competitors do not have?', 'open_text', 'Strategy & Planning', 'CORE', 'TXT-015', 'RC-TXT-059', 3, 'Stage 1→10+'),
  ('S10-TXT-023', 'Is there anything besides price that keeps a buyer with you?', 'open_text', 'Sales & Revenue', 'CORE', 'TXT-015', 'RC-TXT-060', 2, 'Stage 1→10+'),
  ('S10-TXT-024', 'Have you lost a buyer to a marginally cheaper competitor?', 'open_text', 'Sales & Revenue', 'CORE', 'TXT-015', 'RC-TXT-060', 2, 'Stage 1→10+'),
  ('S10-TXT-025', 'Have capital or unsold styles been tied up in dated fashion trends?', 'open_text', 'Financial Management', 'CORE', 'TXT-014', 'RC-TXT-055', 2, 'Stage 1→10+')
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
  ('S0-TXT-001', 'icp'),
  ('S0-TXT-002', 'icp'),
  ('S0-TXT-003', 'icp'),
  ('S0-TXT-004', 'icp'),
  ('S0-TXT-005', 'icp'),
  ('S0-TXT-006', 'willingness-to-pay'),
  ('S0-TXT-007', 'willingness-to-pay'),
  ('S0-TXT-008', 'willingness-to-pay'),
  ('S0-TXT-009', 'willingness-to-pay'),
  ('S0-TXT-010', 'willingness-to-pay'),
  ('S0-TXT-011', 'technical-quality'),
  ('S0-TXT-012', 'technical-quality'),
  ('S0-TXT-013', 'technical-quality'),
  ('S0-TXT-014', 'technical-quality'),
  ('S0-TXT-015', 'icp'),
  ('S01-TXT-001', 'technical-quality'),
  ('S01-TXT-002', 'technical-quality'),
  ('S01-TXT-003', 'technical-quality'),
  ('S01-TXT-004', 'technical-quality'),
  ('S01-TXT-005', 'technical-quality'),
  ('S01-TXT-006', 'technical-quality'),
  ('S01-TXT-007', 'technical-quality'),
  ('S01-TXT-008', 'technical-quality'),
  ('S01-TXT-009', 'technical-quality'),
  ('S01-TXT-010', 'technical-quality'),
  ('S01-TXT-011', 'technical-quality'),
  ('S01-TXT-012', 'technical-quality'),
  ('S01-TXT-013', 'willingness-to-pay'),
  ('S01-TXT-014', 'willingness-to-pay'),
  ('S01-TXT-015', 'willingness-to-pay'),
  ('S01-TXT-016', 'willingness-to-pay'),
  ('S01-TXT-017', 'technical-quality'),
  ('S01-TXT-018', 'technical-quality'),
  ('S01-TXT-019', 'technical-quality'),
  ('S01-TXT-020', 'technical-quality'),
  ('S10-TXT-001', 'willingness-to-pay'),
  ('S10-TXT-002', 'willingness-to-pay'),
  ('S10-TXT-003', 'willingness-to-pay'),
  ('S10-TXT-004', 'willingness-to-pay'),
  ('S10-TXT-005', 'technical-quality'),
  ('S10-TXT-006', 'technical-quality'),
  ('S10-TXT-007', 'technical-quality'),
  ('S10-TXT-008', 'technical-quality'),
  ('S10-TXT-009', 'technical-quality'),
  ('S10-TXT-010', 'technical-quality'),
  ('S10-TXT-011', 'technical-quality'),
  ('S10-TXT-012', 'technical-quality'),
  ('S10-TXT-013', 'willingness-to-pay'),
  ('S10-TXT-014', 'willingness-to-pay'),
  ('S10-TXT-015', 'willingness-to-pay'),
  ('S10-TXT-016', 'willingness-to-pay'),
  ('S10-TXT-017', 'technical-quality'),
  ('S10-TXT-018', 'technical-quality'),
  ('S10-TXT-019', 'technical-quality'),
  ('S10-TXT-020', 'technical-quality'),
  ('S10-TXT-021', 'technical-quality'),
  ('S10-TXT-022', 'technical-quality'),
  ('S10-TXT-023', 'technical-quality'),
  ('S10-TXT-024', 'technical-quality'),
  ('S10-TXT-025', 'technical-quality')
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
         '["textiles"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-TXT-001', 'Ideation — Textiles Product Clarity', 'TXT-001', '["RC-TXT-001", "RC-TXT-002"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Pick one product category and one end customer to design for.", "Write down what you will not produce for now.", "Say no to orders outside that focus."]'::jsonb, '[{"name": "One Category, One Customer", "brief": "Choosing a specific product and buyer instead of producing anything for anyone."}]'::jsonb),
  ('INT-TXT-002', 'Ideation — Textiles Product Clarity', 'TXT-001', '["RC-TXT-003", "RC-TXT-005"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Build a product range around one clear theme.", "Stop taking orders just because they come in.", "Evaluate every order against whether it fits your focus."]'::jsonb, '[{"name": "One Theme, Not Every Order", "brief": "A coherent range instead of accepting anything that arrives."}]'::jsonb),
  ('INT-TXT-003', 'Ideation — Textiles Product Clarity', 'TXT-001', '["RC-TXT-004"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Talk to 10 real potential buyers in your chosen category.", "Ask what they would actually order and at what price.", "Adjust your range around their answers."]'::jsonb, '[{"name": "Talk to Real Buyers First", "brief": "Validating the range with real conversations before committing further."}]'::jsonb),
  ('INT-TXT-004', 'Ideation — Textiles Cost Reality', 'TXT-002', '["RC-TXT-006", "RC-TXT-007"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Build a true cost sheet for one finished unit.", "Include labour and finishing, not just raw material.", "Compare that total against your planned price."]'::jsonb, '[{"name": "True Cost Per Unit", "brief": "A real cost that includes labour and finishing, not just material."}]'::jsonb),
  ('INT-TXT-005', 'Ideation — Textiles Cost Reality', 'TXT-002', '["RC-TXT-008", "RC-TXT-009", "RC-TXT-010"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Count wastage and rejects as real cost.", "Price from your own cost, not competitor prices.", "Calculate your actual margin after real costs."]'::jsonb, '[{"name": "Price and Margin From Real Cost", "brief": "Pricing and margin built from real numbers, not guesses."}]'::jsonb),
  ('INT-TXT-006', 'Ideation — Textiles Production Planning', 'TXT-003', '["RC-TXT-011", "RC-TXT-012"]'::jsonb, '[1]'::jsonb, 'Operations', '["Run a sample or test batch before a full production run.", "Watch how it actually sells before committing further.", "Use that data to size the next batch."]'::jsonb, '[{"name": "Test Before You Commit", "brief": "A small trial batch to learn real demand before scaling production."}]'::jsonb),
  ('INT-TXT-007', 'Ideation — Textiles Production Planning', 'TXT-003', '["RC-TXT-013", "RC-TXT-014"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Get a confirmed order before committing to raw material.", "Do not assume unsold stock can always be discounted later.", "Decide in advance what happens to stock that does not sell."]'::jsonb, '[{"name": "Confirm Orders Before Committing Material", "brief": "Buying raw material against real orders, not hope."}]'::jsonb),
  ('INT-TXT-008', 'Ideation — Textiles Channel Clarity', 'TXT-004', '["RC-TXT-015", "RC-TXT-016"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Send a sample to a real buyer before committing to a channel.", "Confirm real demand before scaling into that channel.", "Only commit fully once the sample proves out."]'::jsonb, '[{"name": "Sample Before You Commit", "brief": "A real buyer test before committing to a channel or lease of shelf space."}]'::jsonb),
  ('INT-TXT-009', 'Ideation — Textiles Channel Clarity', 'TXT-004', '["RC-TXT-017", "RC-TXT-018"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Ask the buyer directly what they actually need.", "Do not assume a good product sells itself.", "Build the offer around what they tell you."]'::jsonb, '[{"name": "Ask the Buyer, Do Not Assume", "brief": "Learning real buyer needs instead of assuming quality is enough."}]'::jsonb),
  ('INT-TXT-010', 'Validation to Traction — Textiles Quality Consistency', 'TXT-005', '["RC-TXT-019", "RC-TXT-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Track rejection rate systematically by buyer and batch.", "Build a standard quality check before goods ship.", "Never let a shipment go out without it."]'::jsonb, '[{"name": "Track Rejections, Check Before Shipping", "brief": "Measured rejection rate and a standard internal check before goods leave."}]'::jsonb),
  ('INT-TXT-011', 'Validation to Traction — Textiles Quality Consistency', 'TXT-005', '["RC-TXT-020", "RC-TXT-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Catch quality issues internally before the buyer does.", "Trace recurring defects to their actual cause.", "Fix the cause permanently, not just the symptom."]'::jsonb, '[{"name": "Catch Early, Fix the Cause", "brief": "Internal detection and permanent fixes instead of repeat rejections."}]'::jsonb),
  ('INT-TXT-012', 'Validation to Traction — Textiles Input Cost Volatility', 'TXT-006', '["RC-TXT-023", "RC-TXT-025"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Add a price adjustment clause to contracts with buyers.", "Set the trigger point for when it applies.", "Apply it consistently, not only when convenient."]'::jsonb, '[{"name": "Add a Price Adjustment Clause", "brief": "Contract terms that share input cost risk instead of absorbing every swing."}]'::jsonb),
  ('INT-TXT-013', 'Validation to Traction — Textiles Input Cost Volatility', 'TXT-006', '["RC-TXT-024", "RC-TXT-026"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Explore forward buying or hedging for key raw materials.", "Track margin per order, not just overall margin.", "Use the pattern to price future orders more accurately."]'::jsonb, '[{"name": "Manage Input Risk, Track Margin", "brief": "A hedging approach plus visibility into where margin actually varies."}]'::jsonb),
  ('INT-TXT-014', 'Validation to Traction — Textiles Skill Dependency', 'TXT-007', '["RC-TXT-027", "RC-TXT-029"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Write down what each key worker knows about their process.", "Build simple training material from it.", "Cross train a second worker on every key step."]'::jsonb, '[{"name": "Document and Cross Train", "brief": "Turning specialised skill knowledge into something a second worker can learn."}]'::jsonb),
  ('INT-TXT-015', 'Validation to Traction — Textiles Skill Dependency', 'TXT-007', '["RC-TXT-028", "RC-TXT-030"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Ask leaving workers why they went.", "Build a backup plan for when a key worker is unavailable.", "Reduce single points of failure in production."]'::jsonb, '[{"name": "Understand Turnover, Build Backup", "brief": "Learning why skilled workers leave and preparing for their absence."}]'::jsonb),
  ('INT-TXT-016', 'Validation to Traction — Textiles Working Capital', 'TXT-008', '["RC-TXT-031", "RC-TXT-034"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Measure the days between paying costs and being paid.", "Track it every month.", "Use it to decide how much volume you can safely take."]'::jsonb, '[{"name": "Measure the Cash Cycle", "brief": "Knowing the real number of days your money is out."}]'::jsonb),
  ('INT-TXT-017', 'Validation to Traction — Textiles Working Capital', 'TXT-008', '["RC-TXT-032", "RC-TXT-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Arrange a credit facility sized to the real cycle.", "Shorten buyer credit terms where you can.", "Cap growth at what your cash can carry."]'::jsonb, '[{"name": "Fund the Gap Deliberately", "brief": "Credit and shorter terms sized to the real working capital cycle."}]'::jsonb),
  ('INT-TXT-018', 'Validation to Traction — Textiles Compliance Basics', 'TXT-009', '["RC-TXT-035", "RC-TXT-036"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Build a consistent process for tracking labour compliance.", "Check safety standards against what is actually required.", "Fix any gap found."]'::jsonb, '[{"name": "Systematise Labour and Safety Compliance", "brief": "Consistent tracking instead of handling compliance informally."}]'::jsonb),
  ('INT-TXT-019', 'Validation to Traction — Textiles Compliance Basics', 'TXT-009', '["RC-TXT-037", "RC-TXT-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Prepare documentation ahead of a buyer audit, not reactively.", "Name one person responsible for compliance.", "Keep records ready at all times, not just before an audit."]'::jsonb, '[{"name": "Prepare Proactively, Assign Ownership", "brief": "A named owner and always-ready documentation instead of reactive audit scrambles."}]'::jsonb),
  ('INT-TXT-020', 'Growth to Maturity — Textiles Buyer Concentration', 'TXT-010', '["RC-TXT-039", "RC-TXT-041"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Calculate the revenue share of your top three buyers.", "Set a ceiling and build a pipeline of new buyers.", "Review the share every quarter."]'::jsonb, '[{"name": "Cap Buyer Concentration", "brief": "Measuring dependence and building beyond the dominant few."}]'::jsonb),
  ('INT-TXT-021', 'Growth to Maturity — Textiles Buyer Concentration', 'TXT-010', '["RC-TXT-040", "RC-TXT-042"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Work out your real margin on the dominant buyer after their terms.", "Separate production priorities from any single buyer.", "Design capacity for your wider business, not just one client."]'::jsonb, '[{"name": "Design for the Business, Not One Buyer", "brief": "Keeping production priorities grounded in the wider buyer base."}]'::jsonb),
  ('INT-TXT-022', 'Growth to Maturity — Textiles Scaling Quality', 'TXT-011', '["RC-TXT-043", "RC-TXT-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Investigate the specific cause of quality variation at higher volume.", "Bring a second line to match the first before scaling further.", "Do not scale ahead of proven consistency."]'::jsonb, '[{"name": "Match Quality Before You Scale", "brief": "Proven consistency across lines before adding more volume."}]'::jsonb),
  ('INT-TXT-023', 'Growth to Maturity — Textiles Scaling Quality', 'TXT-011', '["RC-TXT-045", "RC-TXT-046"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Map every supplier your supply chain now depends on.", "Build redundancy so one line or supplier failure does not stop output.", "Test the redundancy plan before you need it."]'::jsonb, '[{"name": "Build Production Redundancy", "brief": "Backup capacity so a single failure does not halt fulfilment."}]'::jsonb),
  ('INT-TXT-024', 'Growth to Maturity — Textiles Sustainability Compliance', 'TXT-012', '["RC-TXT-047", "RC-TXT-049"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Research what certifications your buyers actually require.", "Price the real cost and timeline of getting certified.", "Start the process before it costs you a bid."]'::jsonb, '[{"name": "Research and Start Certification", "brief": "Understanding real certification requirements and cost before losing bids over them."}]'::jsonb),
  ('INT-TXT-025', 'Growth to Maturity — Textiles Sustainability Compliance', 'TXT-012', '["RC-TXT-048", "RC-TXT-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Build a system for tracking environmental compliance requirements.", "Watch what certified competitors are winning that you are not.", "Prioritise certification based on the biggest bid losses."]'::jsonb, '[{"name": "Track Compliance, Prioritise by Impact", "brief": "Systematic tracking and prioritising certification by real business impact."}]'::jsonb),
  ('INT-TXT-026', 'Growth to Maturity — Textiles Supplier Dependency', 'TXT-013', '["RC-TXT-051", "RC-TXT-052"]'::jsonb, '[5, 6, 7]'::jsonb, 'Supply Chain', '["List every material with only one supplier.", "Qualify a backup supplier for the critical few.", "Test the backup before you actually need it."]'::jsonb, '[{"name": "Second Source the Critical Few", "brief": "A backup supplier for materials that could otherwise disappear from production."}]'::jsonb),
  ('INT-TXT-027', 'Growth to Maturity — Textiles Supplier Dependency', 'TXT-013', '["RC-TXT-053", "RC-TXT-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Supply Chain', '["Track supplier lead times so delays are visible in advance.", "Negotiate rather than automatically absorbing price rises.", "Use the data to plan production realistically."]'::jsonb, '[{"name": "Track Lead Times, Negotiate Price", "brief": "Visibility into delivery timing and active management of cost increases."}]'::jsonb),
  ('INT-TXT-028', 'Growth to Maturity — Textiles Trend Responsiveness', 'TXT-014', '["RC-TXT-055", "RC-TXT-057"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Shorten your design to production timeline where possible.", "Build a fast turnaround capability for smaller trend runs.", "Test it on a low risk trend first."]'::jsonb, '[{"name": "Build Fast Turnaround Capability", "brief": "A quicker path from design to shelf for fast moving trends."}]'::jsonb),
  ('INT-TXT-029', 'Growth to Maturity — Textiles Trend Responsiveness', 'TXT-014', '["RC-TXT-056"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Build a process for tracking emerging trends.", "Use it to inform design decisions earlier.", "Avoid getting caught with capital tied up in dated styles."]'::jsonb, '[{"name": "Track Trends Systematically", "brief": "Earlier visibility into emerging trends to avoid dated inventory."}]'::jsonb),
  ('INT-TXT-030', 'Growth to Maturity — Textiles Defensibility', 'TXT-015', '["RC-TXT-058", "RC-TXT-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Develop a proprietary fabric or technique buyers cannot get elsewhere.", "Make it central to your product line, not a side feature.", "Use it as the reason to choose you over a competitor."]'::jsonb, '[{"name": "Build Something Proprietary", "brief": "An owned fabric or technique that a competitor cannot simply copy."}]'::jsonb),
  ('INT-TXT-031', 'Growth to Maturity — Textiles Defensibility', 'TXT-015', '["RC-TXT-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Build an exclusive relationship or capability beyond price.", "Track how often buyers leave for a marginally cheaper competitor.", "Use the relationship to reduce that churn."]'::jsonb, '[{"name": "Build Beyond Price", "brief": "A real reason for buyers to stay that is not just being cheaper."}]'::jsonb),
  ('INT-TXT-032', 'Ideation — Textiles Channel Clarity', 'TXT-004', '["RC-TXT-061"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Research what a realistic first order size looks like for a comparable buyer.", "Use that to set expectations rather than guessing.", "Plan capacity around that realistic number."]'::jsonb, '[{"name": "Use a Real Comparable Order Size", "brief": "Planning around researched order sizes instead of an optimistic guess."}]'::jsonb),
  ('INT-TXT-033', 'Ideation — Textiles Production Planning', 'TXT-003', '["RC-TXT-062"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Think through what relying on discounts would do to your brand over time.", "Decide deliberately whether markdown is a strategy or a habit.", "Build a plan that does not depend on discounting to clear stock."]'::jsonb, '[{"name": "Consider the Brand Cost of Discounting", "brief": "A deliberate decision about markdown instead of defaulting to it."}]'::jsonb),
  ('INT-TXT-034', 'Validation to Traction — Textiles Quality Consistency', 'TXT-005', '["RC-TXT-063"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Run an internal quality audit independent of buyer inspection.", "Schedule it regularly, not only before a shipment.", "Use it to catch issues the buyer would otherwise find."]'::jsonb, '[{"name": "Independent Internal Quality Audit", "brief": "Regular internal checks that do not wait for buyer feedback."}]'::jsonb)
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
        ('Transportation & Delivery', 'transport_delivery', 'DLV', r"""-- ============================================================================
-- Ally :: Industry seed -- TRANSPORTATION & DELIVERY (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: transport_delivery
--
-- CODE NOTE: uses the DLV- prefix (Delivery), not TRD-, because TRD- is
--            already used by the Import/Export & Trade industry seed.
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (DLV-001, RC-DLV-014, S0-DLV-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : questions name no specific driver licensing category, vehicle
--            permit type or insurance regulation.  These vary by market and
--            change, so the content asks the founder what applies to THEM
--            and what has actually been checked, rather than naming a rule
--            that will go stale.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (on time performance, driver turnover, fleet
--            maintenance, cost control, platform dependency) starts at
--            Stage 0->1; account concentration, scaling operations,
--            compliance operations, liability management, technology gap and
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
  ('DLV-001', 'No Clear Delivery Segment Chosen', 'The business tries to serve food delivery, parcel delivery and freight all at once, so nothing about the service is designed for any specific customer.', 'Idea & Validation', 'Delivery Segment Clarity', 'external', 2, 4, 8, '["Willing to deliver almost anything for anyone", "No specific delivery type or customer designed for", "Service level and pricing identical across very different needs", "No conversation with a real customer", "Assuming any delivery job is worth taking"]'::jsonb, '["transport_delivery"]'::jsonb),
  ('DLV-002', 'Real Cost Per Delivery Not Worked Out', 'Fuel, driver time, vehicle wear and failed deliveries are not built into pricing, so nobody knows if a delivery is actually profitable.', 'Idea & Validation', 'Delivery Cost Reality', 'external', 4, 5, 9, '["Only fuel counted as cost", "Driver time and vehicle wear not factored in", "Failed or returned deliveries not counted as cost", "Price set by looking at competitors only", "No idea what volume is needed to break even"]'::jsonb, '["transport_delivery"]'::jsonb),
  ('DLV-003', 'No Idea How Many Drivers or Vehicles Are Actually Needed', 'Fleet size and driver headcount were decided without working out real delivery volume and coverage area needed.', 'Idea & Validation', 'Delivery Capacity Planning', 'external', 3, 5, 9, '["Fleet size chosen without confirmed delivery volume", "No idea how demand varies by time or area", "Assuming drivers will simply be available when needed", "No test period before committing to a full fleet", "No idea what a realistic delivery radius looks like"]'::jsonb, '["transport_delivery"]'::jsonb),
  ('DLV-004', 'Service Area or Model Chosen Without Testing Real Demand', 'A delivery zone, partnership model or platform was chosen before confirming that real demand exists there.', 'Idea & Validation', 'Delivery Model Clarity', 'external', 3, 5, 9, '["Service area chosen for convenience, not evidence of demand", "No small pilot before committing to a full zone", "No conversation with a real customer about their delivery needs", "Assuming a good service sells itself", "No test order volume before scaling commitments"]'::jsonb, '["transport_delivery"]'::jsonb),
  ('DLV-005', 'On Time Delivery Rate Declining as Volume Grows', 'As order volume increases, delivery windows are missed more often, and nobody has traced the specific cause.', 'Operations & Systems', 'Delivery On Time Performance', 'external', 4, 6, 9, '["On time rate declining as volume grows", "No system tracking delivery windows against actual arrival", "Root cause of delays not identified", "Customers churning after repeated late deliveries", "No real time visibility into where a delivery is"]'::jsonb, '["transport_delivery"]'::jsonb),
  ('DLV-006', 'Driver Turnover Disrupting Route Knowledge and Service', 'Drivers leave frequently, and each departure takes route familiarity and customer relationships with them.', 'Team & Leadership', 'Delivery Driver Turnover', 'external', 3, 6, 9, '["High driver turnover", "Routes optimised in a driver head, not documented", "Customer relationships tied to individual drivers", "No standard onboarding for new drivers", "Recruitment happening reactively, not planned"]'::jsonb, '["transport_delivery"]'::jsonb),
  ('DLV-007', 'Vehicle Maintenance Handled Reactively', 'Vehicles break down before anyone notices wear, disrupting deliveries and creating unplanned cost.', 'Operations & Systems', 'Delivery Fleet Maintenance', 'external', 3, 6, 9, '["Vehicles repaired only after breakdown", "No scheduled maintenance programme", "Breakdowns discovered mid route", "No budget set aside for vehicle replacement", "Safety incidents traced back to poor maintenance"]'::jsonb, '["transport_delivery"]'::jsonb),
  ('DLV-008', 'Fuel and Operating Costs Not Controlled', 'Fuel use and operating cost vary widely between drivers and routes, and nothing is done to bring them under control.', 'Financial Management', 'Delivery Cost Control', 'external', 4, 6, 9, '["Fuel use varying widely between drivers", "No comparison of cost between routes or vehicles", "Fuel theft or waste not checked", "Cost per delivery not tracked consistently", "No target set for operating cost per delivery"]'::jsonb, '["transport_delivery"]'::jsonb),
  ('DLV-009', 'Platform or Aggregator Dependency Squeezing Margin', 'A large share of orders come through a third party platform whose fees and policies increasingly determine what is actually earned per delivery.', 'Sales & Revenue', 'Delivery Platform Dependency', 'external', 3, 6, 9, '["Growing share of orders through a platform or aggregator", "Platform fees eating into delivery margin", "No direct customer relationship independent of the platform", "Policy changes discovered after they affect earnings", "No plan for reducing platform dependence"]'::jsonb, '["transport_delivery"]'::jsonb),
  ('DLV-010', 'Revenue Concentrated in a Few Large Accounts', 'A handful of business accounts account for most delivery volume, so they set the terms and their loss would be severe.', 'Sales & Revenue', 'Delivery Account Concentration', 'external', 4, 7, 10, '["Most revenue from a few large accounts", "Rates dictated by the largest account", "No pipeline of replacement accounts", "Losing one account would threaten the business", "Routing priorities shaped by one account rather than the wider base"]'::jsonb, '["transport_delivery"]'::jsonb),
  ('DLV-011', 'Scaling Operations Introducing New Failure Points', 'Adding drivers, vehicles and zones faster than systems can track them is creating breakdowns nobody anticipated.', 'Operations & Systems', 'Delivery Scaling Operations', 'external', 3, 7, 10, '["New zones or drivers introducing failures not seen before", "Dispatch system straining as volume grows", "Capacity planning not keeping pace with growth", "No redundancy for newly added routes or hubs", "Scaling decisions made reactively under pressure"]'::jsonb, '["transport_delivery"]'::jsonb),
  ('DLV-012', 'Regulatory and Safety Compliance Now a Constant Burden', 'Driver licensing, vehicle permits, safety standards and insurance obligations recur continuously and cannot be tracked informally at this size.', 'Operations & Systems', 'Delivery Compliance Operations', 'external', 3, 7, 10, '["Licences and permits tracked from memory", "No single compliance calendar", "Safety incidents repeating without being permanently fixed", "Insurance coverage not reviewed against actual operations", "One person holding all the compliance knowledge"]'::jsonb, '["transport_delivery"]'::jsonb),
  ('DLV-013', 'Insurance and Liability Exposure Not Properly Managed', 'Accidents, cargo damage and third party claims are handled informally, exposing the business to real financial risk.', 'Financial Management', 'Delivery Liability Management', 'external', 3, 7, 10, '["No consistent process for handling accident claims", "Cargo damage liability not clearly defined with customers", "Insurance coverage not matched to actual risk exposure", "Claims history not tracked for patterns", "No one responsible for liability management specifically"]'::jsonb, '["transport_delivery"]'::jsonb),
  ('DLV-014', 'New Delivery Technology and Automation Outpacing the Business', 'Competitors adopt route optimisation, automated dispatch and tracking technology faster than this business can evaluate and deploy it.', 'Strategy & Planning', 'Delivery Technology Gap', 'external', 2, 6, 10, '["Competitors offering technology this business lacks", "No process for evaluating new delivery technology", "Dispatch and routing still handled manually", "Customers expecting tracking capabilities not yet built", "No budget allocated for technology investment"]'::jsonb, '["transport_delivery"]'::jsonb),
  ('DLV-015', 'Nothing Differentiates This From Any Other Delivery Provider', 'Customers can switch to a similar provider at similar cost with little friction, because nothing built here creates real loyalty.', 'Strategy & Planning', 'Delivery Defensibility', 'external', 2, 6, 10, '["Service easily matched by competitors", "Price the main basis of customer decisions", "No proprietary routing or service advantage", "No exclusive relationship beyond price", "Customer churn to marginally cheaper alternatives"]'::jsonb, '["transport_delivery"]'::jsonb)
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
         t.primary_stage_group, '["transport_delivery"]'::jsonb, z.v
  FROM (VALUES
  ('RC-DLV-001', 'Willing to Deliver Anything for Anyone', 'No focus exists on a specific delivery type or customer.', 'DLV-001', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-DLV-002', 'No Specific Delivery Type Designed For', 'Nothing distinguishes what this service is actually built for.', 'DLV-001', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-DLV-003', 'Service Level Identical Across Different Needs', 'The same offer serves food, parcels and freight with no differentiation.', 'DLV-001', 'external', 'Strategic', 0.68, 'Stage 0'),
  ('RC-DLV-004', 'No Conversation With a Real Customer', 'Nobody who would actually use the service has been spoken to.', 'DLV-001', 'external', 'Behavioural', 0.66, 'Stage 0'),
  ('RC-DLV-005', 'Assuming Any Delivery Job Is Worth Taking', 'Believing volume alone justifies taking any job regardless of fit.', 'DLV-001', 'external', 'Psychological', 0.67, 'Stage 0'),
  ('RC-DLV-006', 'Only Fuel Counted as Cost', 'The cost of a delivery is taken as fuel alone.', 'DLV-002', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-DLV-007', 'Driver Time and Vehicle Wear Not Factored In', 'Labour and depreciation are missing from the delivery cost.', 'DLV-002', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-DLV-008', 'Failed Deliveries Not Counted as Cost', 'Returns and failed attempts are not treated as a real cost.', 'DLV-002', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-DLV-009', 'Price Set by Looking at Competitors', 'Pricing copies others without knowing own true cost.', 'DLV-002', 'external', 'Behavioural', 0.67, 'Stage 0'),
  ('RC-DLV-010', 'No Break Even Volume Known', 'What delivery volume is needed to cover cost has not been calculated.', 'DLV-002', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-DLV-011', 'Fleet Size Chosen Without Confirmed Volume', 'Vehicles and drivers were committed to before demand was verified.', 'DLV-003', 'external', 'Strategic', 0.72, 'Stage 0'),
  ('RC-DLV-012', 'Demand Variation by Time or Area Unknown', 'How delivery demand shifts through the day or across zones has not been studied.', 'DLV-003', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-DLV-013', 'Assuming Drivers Will Simply Be Available', 'Believing driver supply will match demand without planning.', 'DLV-003', 'external', 'Psychological', 0.68, 'Stage 0'),
  ('RC-DLV-014', 'No Test Period Before Full Fleet Commitment', 'A trial phase was skipped in favour of committing to a full fleet.', 'DLV-003', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-DLV-015', 'Service Area Chosen for Convenience Not Demand', 'The zone was picked for ease, not evidence of buyers there.', 'DLV-004', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-DLV-016', 'No Small Pilot Before Committing', 'A zone or model was committed to without a low cost trial first.', 'DLV-004', 'external', 'Strategic', 0.69, 'Stage 0'),
  ('RC-DLV-017', 'No Conversation About Customer Delivery Needs', 'What customers actually need from delivery has not been asked.', 'DLV-004', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-DLV-018', 'Assuming a Good Service Sells Itself', 'Believing quality alone will bring customers without active marketing.', 'DLV-004', 'external', 'Psychological', 0.67, 'Stage 0'),
  ('RC-DLV-019', 'No System Tracking Delivery Windows', 'Whether deliveries arrive within the promised window is not measured.', 'DLV-005', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-DLV-020', 'Root Cause of Delays Not Identified', 'Late deliveries are noted but never traced to a cause.', 'DLV-005', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-DLV-021', 'No Real Time Visibility Into Delivery Location', 'Nobody can say where a delivery actually is mid route.', 'DLV-005', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-DLV-022', 'Customers Churning After Late Deliveries', 'Repeated lateness is costing customers without a fix in place.', 'DLV-005', 'external', 'Behavioural', 0.69, 'Stage 0→1'),
  ('RC-DLV-023', 'Routes Optimised in a Driver Head', 'Route knowledge exists only in the memory of individual drivers.', 'DLV-006', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-DLV-024', 'Customer Relationships Tied to Individual Drivers', 'Trust sits with the driver, not the company.', 'DLV-006', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-DLV-025', 'No Standard Onboarding for New Drivers', 'New drivers learn informally with no defined process.', 'DLV-006', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-DLV-026', 'Driver Recruitment Happening Reactively', 'Hiring starts only once a gap becomes urgent.', 'DLV-006', 'external', 'Behavioural', 0.68, 'Stage 0→1'),
  ('RC-DLV-027', 'Vehicles Repaired Only After Breakdown', 'Nothing catches wear before it becomes a failure.', 'DLV-007', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-DLV-028', 'No Scheduled Maintenance Programme', 'Vehicle upkeep is not on any calendar.', 'DLV-007', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-DLV-029', 'Breakdowns Discovered Mid Route', 'Failures happen during delivery rather than being caught ahead of time.', 'DLV-007', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-DLV-030', 'No Budget for Vehicle Replacement', 'Nothing is set aside for replacing aging vehicles.', 'DLV-007', 'external', 'Strategic', 0.69, 'Stage 0→1'),
  ('RC-DLV-031', 'Fuel Use Varying Between Drivers', 'Consumption differs widely for no explained reason.', 'DLV-008', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-DLV-032', 'No Comparison of Cost Between Routes or Vehicles', 'Nobody checks which routes or vehicles cost more to run.', 'DLV-008', 'external', 'Knowledge', 0.70, 'Stage 0→1'),
  ('RC-DLV-033', 'Fuel Theft or Waste Not Checked', 'Nothing monitors for fuel loss beyond normal use.', 'DLV-008', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-DLV-034', 'No Target Set for Cost Per Delivery', 'Nothing defines what an acceptable operating cost should be.', 'DLV-008', 'external', 'Knowledge', 0.68, 'Stage 0→1'),
  ('RC-DLV-035', 'Growing Share of Orders Through a Platform', 'Increasing dependence on a third party outside direct control.', 'DLV-009', 'external', 'Strategic', 0.73, 'Stage 0→1'),
  ('RC-DLV-036', 'Platform Fees Eating Into Margin', 'What the platform charges is consuming an increasing share of earnings.', 'DLV-009', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-DLV-037', 'No Direct Customer Relationship Independent of the Platform', 'The business does not own its own customer relationships.', 'DLV-009', 'external', 'Strategic', 0.71, 'Stage 0→1'),
  ('RC-DLV-038', 'Policy Changes Discovered After They Affect Earnings', 'Platform rule changes are learned about only once earnings drop.', 'DLV-009', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-DLV-039', 'Most Revenue From a Few Large Accounts', 'A handful of accounts carry most of the business.', 'DLV-010', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-DLV-040', 'Rates Dictated by the Largest Account', 'The dominant account sets what can be charged.', 'DLV-010', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-DLV-041', 'No Pipeline of Replacement Accounts', 'Nothing is being built that could replace a lost account.', 'DLV-010', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-DLV-042', 'Routing Priorities Shaped by One Account', 'The dominant account decides routing rather than the wider business.', 'DLV-010', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-DLV-043', 'New Zones Introducing Unseen Failures', 'Expansion has created failure modes nobody anticipated.', 'DLV-011', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-DLV-044', 'Dispatch System Straining as Volume Grows', 'The system for assigning deliveries is not built for current scale.', 'DLV-011', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-DLV-045', 'Capacity Planning Not Keeping Pace With Growth', 'Fleet and hiring investment is lagging behind demand growth.', 'DLV-011', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-DLV-046', 'No Redundancy for Newly Added Routes or Hubs', 'New infrastructure lacks the backup older parts of the network have.', 'DLV-011', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-DLV-047', 'Licences and Permits Tracked From Memory', 'Renewal dates for driver and vehicle authorisations live in memory, not a system.', 'DLV-012', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-DLV-048', 'No Single Compliance Calendar', 'Nothing brings every obligation into one dated place.', 'DLV-012', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-DLV-049', 'Safety Incidents Repeating', 'The same safety issue recurs without being permanently fixed.', 'DLV-012', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-DLV-050', 'Insurance Not Reviewed Against Actual Operations', 'Coverage may not match the scale or type of operations now running.', 'DLV-012', 'external', 'Knowledge', 0.69, 'Stage 1→10+'),
  ('RC-DLV-051', 'No Consistent Process for Accident Claims', 'Claims are handled differently each time with no set process.', 'DLV-013', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-DLV-052', 'Cargo Damage Liability Not Clearly Defined', 'Who is responsible for damaged goods has not been agreed with customers.', 'DLV-013', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-DLV-053', 'Claims History Not Tracked', 'Patterns in accidents or damage claims are not analysed.', 'DLV-013', 'external', 'Knowledge', 0.70, 'Stage 1→10+'),
  ('RC-DLV-054', 'No One Responsible for Liability Management', 'Nobody owns tracking and managing liability exposure.', 'DLV-013', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-DLV-055', 'No Process for Evaluating New Delivery Technology', 'Nothing systematically decides which new technology to adopt.', 'DLV-014', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-DLV-056', 'Dispatch and Routing Still Handled Manually', 'No system automates what is now done by hand.', 'DLV-014', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-DLV-057', 'No Budget for Technology Investment', 'Nothing is set aside to close the technology gap.', 'DLV-014', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-DLV-058', 'Service Easily Matched by Competitors', 'What is offered can be replicated without much effort.', 'DLV-015', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-DLV-059', 'No Proprietary Routing or Service Advantage', 'Nothing about the operation is hard for a competitor to copy.', 'DLV-015', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-DLV-060', 'No Exclusive Relationship Beyond Price', 'Nothing besides being cheap keeps a customer with this business.', 'DLV-015', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-DLV-061', 'No Idea What a Realistic Delivery Radius Looks Like', 'How far a comparable delivery service can realistically cover has not been researched.', 'DLV-003', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-DLV-062', 'No Test Order Volume Before Scaling Commitments', 'Commitments were scaled up before a real test volume confirmed demand.', 'DLV-004', 'external', 'Behavioural', 0.65, 'Stage 0'),
  ('RC-DLV-063', 'No Backup Plan for a Vehicle Going Out of Service Mid Route', 'Nothing has been prepared for a vehicle failing while deliveries are in progress.', 'DLV-007', 'external', 'Strategic', 0.66, 'Stage 0→1'),
  ('RC-DLV-064', 'No Cross Training Between Delivery Zones', 'Drivers in one zone cannot easily cover or learn from another.', 'DLV-011', 'external', 'Operational', 0.66, 'Stage 1→10+'),
  ('RC-DLV-065', 'No Regular Review of Which Accounts to Prioritise', 'Nobody periodically reassesses which accounts deserve the most attention.', 'DLV-010', 'external', 'Operational', 0.66, 'Stage 1→10+'),
  ('RC-DLV-066', 'No Regular Benchmarking Against Competitor Services', 'Nobody checks what competitors are actually offering on speed or price.', 'DLV-015', 'external', 'Knowledge', 0.65, 'Stage 1→10+')
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
         '["transport_delivery"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-DLV-001', 'Will you deliver anything for anyone, or have you chosen a focus?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-001', 'RC-DLV-001', 1, 'Stage 0'),
  ('S0-DLV-002', 'What specific type of delivery are you built for?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-001', 'RC-DLV-002', 1, 'Stage 0'),
  ('S0-DLV-003', 'Is your service level the same across food, parcels and freight?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-001', 'RC-DLV-003', 2, 'Stage 0'),
  ('S0-DLV-004', 'Have you talked to a real customer who would actually use this?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-001', 'RC-DLV-004', 2, 'Stage 0'),
  ('S0-DLV-005', 'Do you take any delivery job that comes in, or only ones that fit your focus?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-001', 'RC-DLV-005', 2, 'Stage 0'),
  ('S0-DLV-006', 'What does one delivery actually cost you, beyond fuel?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-002', 'RC-DLV-006', 1, 'Stage 0'),
  ('S0-DLV-007', 'Have you counted driver time and vehicle wear as cost?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-002', 'RC-DLV-007', 2, 'Stage 0'),
  ('S0-DLV-008', 'Do you count failed or returned deliveries as a cost?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-002', 'RC-DLV-008', 2, 'Stage 0'),
  ('S0-DLV-009', 'Did you set your price from your own cost or from competitors?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-002', 'RC-DLV-009', 2, 'Stage 0'),
  ('S0-DLV-010', 'Do you know what delivery volume you need to break even?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-002', 'RC-DLV-010', 2, 'Stage 0'),
  ('S0-DLV-011', 'Did you confirm delivery volume before choosing your fleet size?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-003', 'RC-DLV-011', 1, 'Stage 0'),
  ('S0-DLV-012', 'Do you know how demand varies by time of day or by area?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-003', 'RC-DLV-012', 2, 'Stage 0'),
  ('S0-DLV-013', 'Are you assuming drivers will simply be available when needed?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-003', 'RC-DLV-013', 2, 'Stage 0'),
  ('S0-DLV-014', 'Did you run a test period before committing to a full fleet?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-003', 'RC-DLV-014', 2, 'Stage 0'),
  ('S0-DLV-015', 'Did you check real demand before choosing this service area?', 'open_text', 'Idea & Validation', 'CORE', 'DLV-004', 'RC-DLV-015', 1, 'Stage 0'),
  ('S01-DLV-001', 'Has your on time rate declined as volume has grown?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-005', 'RC-DLV-019', 2, 'Stage 0→1'),
  ('S01-DLV-002', 'Do you track deliveries against their promised window?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-005', 'RC-DLV-019', 2, 'Stage 0→1'),
  ('S01-DLV-003', 'When a delivery is late, does anyone find out why?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-005', 'RC-DLV-020', 2, 'Stage 0→1'),
  ('S01-DLV-004', 'Can you see where a delivery is in real time?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-005', 'RC-DLV-021', 2, 'Stage 0→1'),
  ('S01-DLV-005', 'How many drivers have left in the last year?', 'open_text', 'Team & Leadership', 'CORE', 'DLV-006', 'RC-DLV-026', 2, 'Stage 0→1'),
  ('S01-DLV-006', 'Is route knowledge written down, or only in drivers heads?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-006', 'RC-DLV-023', 2, 'Stage 0→1'),
  ('S01-DLV-007', 'Do customers trust your company, or trust a specific driver?', 'open_text', 'Sales & Revenue', 'CORE', 'DLV-006', 'RC-DLV-024', 3, 'Stage 0→1'),
  ('S01-DLV-008', 'How does a new driver learn your routes and standards?', 'open_text', 'Team & Leadership', 'CORE', 'DLV-006', 'RC-DLV-025', 2, 'Stage 0→1'),
  ('S01-DLV-009', 'Are vehicles serviced on a schedule or only after they break down?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-007', 'RC-DLV-027', 2, 'Stage 0→1'),
  ('S01-DLV-010', 'Is there a maintenance calendar for your fleet?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-007', 'RC-DLV-028', 2, 'Stage 0→1'),
  ('S01-DLV-011', 'How often do breakdowns happen mid route?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-007', 'RC-DLV-029', 2, 'Stage 0→1'),
  ('S01-DLV-012', 'Is there a budget set aside for vehicle replacement?', 'open_text', 'Financial Management', 'CORE', 'DLV-007', 'RC-DLV-030', 2, 'Stage 0→1'),
  ('S01-DLV-013', 'Does fuel use differ a lot between your drivers?', 'open_text', 'Financial Management', 'CORE', 'DLV-008', 'RC-DLV-031', 2, 'Stage 0→1'),
  ('S01-DLV-014', 'Have you ever compared cost between your routes or vehicles?', 'open_text', 'Financial Management', 'CORE', 'DLV-008', 'RC-DLV-032', 3, 'Stage 0→1'),
  ('S01-DLV-015', 'Do you check for fuel theft or waste?', 'open_text', 'Financial Management', 'CORE', 'DLV-008', 'RC-DLV-033', 2, 'Stage 0→1'),
  ('S01-DLV-016', 'Do you know your cost per delivery?', 'open_text', 'Financial Management', 'CORE', 'DLV-008', 'RC-DLV-034', 2, 'Stage 0→1'),
  ('S01-DLV-017', 'What share of your orders now come through a platform or aggregator?', 'open_text', 'Sales & Revenue', 'CORE', 'DLV-009', 'RC-DLV-035', 2, 'Stage 0→1'),
  ('S01-DLV-018', 'How much of your margin is going to platform fees?', 'open_text', 'Financial Management', 'CORE', 'DLV-009', 'RC-DLV-036', 2, 'Stage 0→1'),
  ('S01-DLV-019', 'Do you have a customer relationship independent of that platform?', 'open_text', 'Sales & Revenue', 'CORE', 'DLV-009', 'RC-DLV-037', 3, 'Stage 0→1'),
  ('S01-DLV-020', 'Have you ever been surprised by a platform policy change affecting earnings?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-009', 'RC-DLV-038', 3, 'Stage 0→1'),
  ('S10-DLV-001', 'What share of your revenue comes from your top two or three accounts?', 'open_text', 'Sales & Revenue', 'CORE', 'DLV-010', 'RC-DLV-039', 2, 'Stage 1→10+'),
  ('S10-DLV-002', 'Who sets your rates, you or your largest account?', 'open_text', 'Sales & Revenue', 'CORE', 'DLV-010', 'RC-DLV-040', 2, 'Stage 1→10+'),
  ('S10-DLV-003', 'If your largest account left, how long could you continue?', 'open_text', 'Strategy & Planning', 'CORE', 'DLV-010', 'RC-DLV-041', 3, 'Stage 1→10+'),
  ('S10-DLV-004', 'Is your routing being shaped by one account rather than your wider base?', 'open_text', 'Strategy & Planning', 'CORE', 'DLV-010', 'RC-DLV-042', 3, 'Stage 1→10+'),
  ('S10-DLV-005', 'Has expanding into new zones introduced problems you did not see before?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-011', 'RC-DLV-043', 2, 'Stage 1→10+'),
  ('S10-DLV-006', 'Is your dispatch system straining as volume grows?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-011', 'RC-DLV-044', 2, 'Stage 1→10+'),
  ('S10-DLV-007', 'Is your capacity planning keeping pace with growth?', 'open_text', 'Strategy & Planning', 'CORE', 'DLV-011', 'RC-DLV-045', 3, 'Stage 1→10+'),
  ('S10-DLV-008', 'Do newly added routes or hubs have the same redundancy as the rest of the network?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-011', 'RC-DLV-046', 3, 'Stage 1→10+'),
  ('S10-DLV-009', 'Can you list every driver and vehicle authorisation and its expiry date?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-012', 'RC-DLV-047', 2, 'Stage 1→10+'),
  ('S10-DLV-010', 'Is there one calendar covering every compliance obligation?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-012', 'RC-DLV-048', 2, 'Stage 1→10+'),
  ('S10-DLV-011', 'Have the same safety incidents come up more than once?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-012', 'RC-DLV-049', 3, 'Stage 1→10+'),
  ('S10-DLV-012', 'If the person who tracks compliance left, what would happen?', 'open_text', 'Team & Leadership', 'CORE', 'DLV-012', 'RC-DLV-047', 3, 'Stage 1→10+'),
  ('S10-DLV-013', 'Has your insurance been reviewed against your actual current operations?', 'open_text', 'Financial Management', 'CORE', 'DLV-012', 'RC-DLV-050', 3, 'Stage 1→10+'),
  ('S10-DLV-014', 'Is there a consistent process for handling accident claims?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-013', 'RC-DLV-051', 2, 'Stage 1→10+'),
  ('S10-DLV-015', 'Is cargo damage liability clearly defined with your customers?', 'open_text', 'Financial Management', 'CORE', 'DLV-013', 'RC-DLV-052', 3, 'Stage 1→10+'),
  ('S10-DLV-016', 'Do you track patterns in accidents or damage claims?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-013', 'RC-DLV-053', 2, 'Stage 1→10+'),
  ('S10-DLV-017', 'Is anyone specifically responsible for liability management?', 'open_text', 'Team & Leadership', 'CORE', 'DLV-013', 'RC-DLV-054', 2, 'Stage 1→10+'),
  ('S10-DLV-018', 'How do you decide which new delivery technology to adopt?', 'open_text', 'Strategy & Planning', 'CORE', 'DLV-014', 'RC-DLV-055', 2, 'Stage 1→10+'),
  ('S10-DLV-019', 'Is dispatch and routing still handled manually?', 'open_text', 'Operations & Systems', 'CORE', 'DLV-014', 'RC-DLV-056', 2, 'Stage 1→10+'),
  ('S10-DLV-020', 'Is there a budget set aside for technology investment?', 'open_text', 'Financial Management', 'CORE', 'DLV-014', 'RC-DLV-057', 2, 'Stage 1→10+'),
  ('S10-DLV-021', 'How easily could a competitor match your service?', 'open_text', 'Strategy & Planning', 'CORE', 'DLV-015', 'RC-DLV-058', 3, 'Stage 1→10+'),
  ('S10-DLV-022', 'Do customers choose you mainly on price or on something else?', 'open_text', 'Sales & Revenue', 'CORE', 'DLV-015', 'RC-DLV-058', 2, 'Stage 1→10+'),
  ('S10-DLV-023', 'Do you have any proprietary routing or service advantage?', 'open_text', 'Strategy & Planning', 'CORE', 'DLV-015', 'RC-DLV-059', 3, 'Stage 1→10+'),
  ('S10-DLV-024', 'Is there anything besides price that keeps a customer with you?', 'open_text', 'Sales & Revenue', 'CORE', 'DLV-015', 'RC-DLV-060', 2, 'Stage 1→10+'),
  ('S10-DLV-025', 'Have you lost a customer to a marginally cheaper competitor?', 'open_text', 'Sales & Revenue', 'CORE', 'DLV-015', 'RC-DLV-060', 2, 'Stage 1→10+')
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
  ('S0-DLV-001', 'icp'),
  ('S0-DLV-002', 'icp'),
  ('S0-DLV-003', 'icp'),
  ('S0-DLV-004', 'icp'),
  ('S0-DLV-005', 'icp'),
  ('S0-DLV-006', 'willingness-to-pay'),
  ('S0-DLV-007', 'willingness-to-pay'),
  ('S0-DLV-008', 'willingness-to-pay'),
  ('S0-DLV-009', 'willingness-to-pay'),
  ('S0-DLV-010', 'willingness-to-pay'),
  ('S0-DLV-011', 'technical-quality'),
  ('S0-DLV-012', 'technical-quality'),
  ('S0-DLV-013', 'technical-quality'),
  ('S0-DLV-014', 'technical-quality'),
  ('S0-DLV-015', 'icp'),
  ('S01-DLV-001', 'technical-quality'),
  ('S01-DLV-002', 'technical-quality'),
  ('S01-DLV-003', 'technical-quality'),
  ('S01-DLV-004', 'technical-quality'),
  ('S01-DLV-005', 'technical-quality'),
  ('S01-DLV-006', 'technical-quality'),
  ('S01-DLV-007', 'technical-quality'),
  ('S01-DLV-008', 'technical-quality'),
  ('S01-DLV-009', 'technical-quality'),
  ('S01-DLV-010', 'technical-quality'),
  ('S01-DLV-011', 'technical-quality'),
  ('S01-DLV-012', 'technical-quality'),
  ('S01-DLV-013', 'willingness-to-pay'),
  ('S01-DLV-014', 'willingness-to-pay'),
  ('S01-DLV-015', 'willingness-to-pay'),
  ('S01-DLV-016', 'willingness-to-pay'),
  ('S01-DLV-017', 'technical-quality'),
  ('S01-DLV-018', 'technical-quality'),
  ('S01-DLV-019', 'technical-quality'),
  ('S01-DLV-020', 'technical-quality'),
  ('S10-DLV-001', 'willingness-to-pay'),
  ('S10-DLV-002', 'willingness-to-pay'),
  ('S10-DLV-003', 'willingness-to-pay'),
  ('S10-DLV-004', 'willingness-to-pay'),
  ('S10-DLV-005', 'technical-quality'),
  ('S10-DLV-006', 'technical-quality'),
  ('S10-DLV-007', 'technical-quality'),
  ('S10-DLV-008', 'technical-quality'),
  ('S10-DLV-009', 'technical-quality'),
  ('S10-DLV-010', 'technical-quality'),
  ('S10-DLV-011', 'technical-quality'),
  ('S10-DLV-012', 'technical-quality'),
  ('S10-DLV-013', 'technical-quality'),
  ('S10-DLV-014', 'willingness-to-pay'),
  ('S10-DLV-015', 'willingness-to-pay'),
  ('S10-DLV-016', 'willingness-to-pay'),
  ('S10-DLV-017', 'willingness-to-pay'),
  ('S10-DLV-018', 'technical-quality'),
  ('S10-DLV-019', 'technical-quality'),
  ('S10-DLV-020', 'technical-quality'),
  ('S10-DLV-021', 'technical-quality'),
  ('S10-DLV-022', 'technical-quality'),
  ('S10-DLV-023', 'technical-quality'),
  ('S10-DLV-024', 'technical-quality'),
  ('S10-DLV-025', 'technical-quality')
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
         '["transport_delivery"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-DLV-001', 'Ideation — Delivery Segment Clarity', 'DLV-001', '["RC-DLV-001", "RC-DLV-002"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Pick one delivery type and one customer to design for.", "Write down what you will not deliver for now.", "Say no to jobs outside that focus."]'::jsonb, '[{"name": "One Delivery Type, One Customer", "brief": "Choosing a specific segment instead of delivering anything for anyone."}]'::jsonb),
  ('INT-DLV-002', 'Ideation — Delivery Segment Clarity', 'DLV-001', '["RC-DLV-003", "RC-DLV-005"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Design service level specifically for your chosen segment.", "Stop taking jobs just because they come in.", "Evaluate every job against whether it fits your focus."]'::jsonb, '[{"name": "Design for One Segment", "brief": "A tailored service instead of the same offer for very different needs."}]'::jsonb),
  ('INT-DLV-003', 'Ideation — Delivery Segment Clarity', 'DLV-001', '["RC-DLV-004"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Talk to 10 real potential customers in your chosen segment.", "Ask what they would actually pay for and expect.", "Adjust your service around their answers."]'::jsonb, '[{"name": "Talk to Real Customers First", "brief": "Validating the service with real conversations before committing further."}]'::jsonb),
  ('INT-DLV-004', 'Ideation — Delivery Cost Reality', 'DLV-002', '["RC-DLV-006", "RC-DLV-007"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Build a true cost sheet for one delivery.", "Include driver time and vehicle wear, not just fuel.", "Compare that total against your planned price."]'::jsonb, '[{"name": "True Cost Per Delivery", "brief": "A real cost that includes labour and vehicle wear, not just fuel."}]'::jsonb),
  ('INT-DLV-005', 'Ideation — Delivery Cost Reality', 'DLV-002', '["RC-DLV-008", "RC-DLV-009", "RC-DLV-010"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Count failed and returned deliveries as real cost.", "Price from your own cost, not competitor prices.", "Calculate the volume needed to break even."]'::jsonb, '[{"name": "Price and Break Even From Real Cost", "brief": "Pricing and break even math built from real numbers, not guesses."}]'::jsonb),
  ('INT-DLV-006', 'Ideation — Delivery Capacity Planning', 'DLV-003', '["RC-DLV-011", "RC-DLV-013"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Confirm real delivery volume before committing to fleet size.", "Do not assume drivers will simply be available.", "Start smaller than feels comfortable and grow with confirmed demand."]'::jsonb, '[{"name": "Confirm Volume Before Fleet Size", "brief": "Buying capacity against confirmed demand, not hope."}]'::jsonb),
  ('INT-DLV-007', 'Ideation — Delivery Capacity Planning', 'DLV-003', '["RC-DLV-012", "RC-DLV-014"]'::jsonb, '[1]'::jsonb, 'Operations', '["Study how delivery demand varies by time and area.", "Run a test period before committing to a full fleet.", "Use that data to size capacity realistically."]'::jsonb, '[{"name": "Test Before Full Fleet Commitment", "brief": "A trial period to learn real demand patterns before scaling capacity."}]'::jsonb),
  ('INT-DLV-008', 'Ideation — Delivery Model Clarity', 'DLV-004', '["RC-DLV-015", "RC-DLV-016"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Test the service area or model on a small scale first.", "Confirm real demand before committing to the full zone.", "Only scale up once the test proves out."]'::jsonb, '[{"name": "Test the Zone Small First", "brief": "A low cost trial before committing to a full service area."}]'::jsonb),
  ('INT-DLV-009', 'Ideation — Delivery Model Clarity', 'DLV-004', '["RC-DLV-017", "RC-DLV-018"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Ask customers directly what they need from delivery.", "Do not assume a good service markets itself.", "Build the offer around what they tell you."]'::jsonb, '[{"name": "Ask Customers, Do Not Assume", "brief": "Learning real delivery needs instead of assuming quality is enough."}]'::jsonb),
  ('INT-DLV-010', 'Validation to Traction — Delivery On Time Performance', 'DLV-005', '["RC-DLV-019", "RC-DLV-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Track every delivery against its promised window.", "Add real time visibility into where a delivery is.", "Review the data weekly to spot patterns."]'::jsonb, '[{"name": "Track Windows and Location", "brief": "Real visibility into delivery timing and location instead of guessing."}]'::jsonb),
  ('INT-DLV-011', 'Validation to Traction — Delivery On Time Performance', 'DLV-005', '["RC-DLV-020", "RC-DLV-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Trace late deliveries to their actual cause.", "Fix the most common cause first.", "Reach out to affected customers before they churn."]'::jsonb, '[{"name": "Trace and Fix the Cause", "brief": "Finding why delays happen instead of only noting that they did."}]'::jsonb),
  ('INT-DLV-012', 'Validation to Traction — Delivery Driver Turnover', 'DLV-006', '["RC-DLV-023", "RC-DLV-025"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Document key routes instead of leaving them in drivers heads.", "Build a standard onboarding process for new drivers.", "Use both to train new hires faster."]'::jsonb, '[{"name": "Document Routes, Standardise Onboarding", "brief": "Turning route knowledge into something a new driver can learn quickly."}]'::jsonb),
  ('INT-DLV-013', 'Validation to Traction — Delivery Driver Turnover', 'DLV-006', '["RC-DLV-024", "RC-DLV-026"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Build customer trust in the company, not just the driver.", "Recruit ahead of need rather than reactively.", "Introduce a second driver into key customer relationships."]'::jsonb, '[{"name": "Shift Trust to the Company", "brief": "Reducing dependence on any one driver for retention and relationships."}]'::jsonb),
  ('INT-DLV-014', 'Validation to Traction — Delivery Fleet Maintenance', 'DLV-007', '["RC-DLV-027", "RC-DLV-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Build a scheduled maintenance programme for the fleet.", "Service on the schedule, not after breakdown.", "Track what fails most often and address it specifically."]'::jsonb, '[{"name": "Scheduled Maintenance", "brief": "Planned servicing instead of waiting for vehicles to break down."}]'::jsonb),
  ('INT-DLV-015', 'Validation to Traction — Delivery Fleet Maintenance', 'DLV-007', '["RC-DLV-029", "RC-DLV-030"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Set up regular inspection ahead of mid route breakdowns.", "Set aside a budget for vehicle replacement.", "Track vehicle age against expected lifespan."]'::jsonb, '[{"name": "Inspect Ahead, Budget Replacement", "brief": "Catching wear before failure and money set aside for aging vehicles."}]'::jsonb),
  ('INT-DLV-016', 'Validation to Traction — Delivery Cost Control', 'DLV-008', '["RC-DLV-031", "RC-DLV-034"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Track fuel use and cost per delivery for every driver and route.", "Set a target operating cost per delivery.", "Investigate the outliers."]'::jsonb, '[{"name": "Track and Target Cost Per Delivery", "brief": "A comparable number and a target across every driver and route."}]'::jsonb),
  ('INT-DLV-017', 'Validation to Traction — Delivery Cost Control', 'DLV-008', '["RC-DLV-032", "RC-DLV-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Compare running cost between routes and vehicles regularly.", "Check for fuel theft or unexplained waste.", "Address the vehicles or routes that cost the most."]'::jsonb, '[{"name": "Compare and Check for Waste", "brief": "Regular comparison and monitoring for fuel loss beyond normal use."}]'::jsonb),
  ('INT-DLV-018', 'Validation to Traction — Delivery Platform Dependency', 'DLV-009', '["RC-DLV-035", "RC-DLV-037"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Measure what share of orders depends on the platform.", "Build a direct customer relationship independent of it.", "Grow that channel deliberately over time."]'::jsonb, '[{"name": "Build a Direct Relationship", "brief": "Reducing dependence on a platform you do not control."}]'::jsonb),
  ('INT-DLV-019', 'Validation to Traction — Delivery Platform Dependency', 'DLV-009', '["RC-DLV-036", "RC-DLV-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Track platform fees as a share of earnings explicitly.", "Watch for policy changes ahead of time where possible.", "Factor platform risk into pricing and planning."]'::jsonb, '[{"name": "Track Fees and Watch Policy", "brief": "Making platform cost and risk visible instead of discovering it after the fact."}]'::jsonb),
  ('INT-DLV-020', 'Growth to Maturity — Delivery Account Concentration', 'DLV-010', '["RC-DLV-039", "RC-DLV-041"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Calculate the revenue share of your top three accounts.", "Set a ceiling and build a pipeline of smaller accounts.", "Review the share every quarter."]'::jsonb, '[{"name": "Cap Account Concentration", "brief": "Measuring dependence and building beyond the dominant few."}]'::jsonb),
  ('INT-DLV-021', 'Growth to Maturity — Delivery Account Concentration', 'DLV-010', '["RC-DLV-040", "RC-DLV-042"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Work out your real margin on the dominant account after their terms.", "Separate routing priorities from any single account.", "Design capacity for your wider business, not just one client."]'::jsonb, '[{"name": "Design for the Business, Not One Account", "brief": "Keeping routing priorities grounded in the wider customer base."}]'::jsonb),
  ('INT-DLV-022', 'Growth to Maturity — Delivery Scaling Operations', 'DLV-011', '["RC-DLV-043", "RC-DLV-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Test new zones thoroughly before full rollout.", "Align capacity investment with actual demand growth.", "Plan ahead of demand rather than reacting to it."]'::jsonb, '[{"name": "Plan Capacity Ahead of Demand", "brief": "Proactive capacity investment instead of reacting to failures after they appear."}]'::jsonb),
  ('INT-DLV-023', 'Growth to Maturity — Delivery Scaling Operations', 'DLV-011', '["RC-DLV-044", "RC-DLV-046"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Upgrade dispatch systems before they strain further under volume.", "Build redundancy into every newly added route or hub.", "Do not treat new infrastructure as exempt from the standards applied to the rest of the network."]'::jsonb, '[{"name": "Upgrade Dispatch, Build In Redundancy", "brief": "Applying the same reliability standards to new infrastructure as to the old."}]'::jsonb),
  ('INT-DLV-024', 'Growth to Maturity — Delivery Compliance Operations', 'DLV-012', '["RC-DLV-047", "RC-DLV-048"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Build one calendar covering every licence, permit and renewal.", "Set reminders well ahead of each expiry.", "Review it monthly."]'::jsonb, '[{"name": "One Compliance Calendar", "brief": "Every recurring obligation and deadline in one dated place."}]'::jsonb),
  ('INT-DLV-025', 'Growth to Maturity — Delivery Compliance Operations', 'DLV-012', '["RC-DLV-049", "RC-DLV-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Fix safety incidents permanently instead of letting them repeat.", "Review insurance coverage against actual current operations.", "Train a second person on the whole compliance picture."]'::jsonb, '[{"name": "Fix Permanently, Review Coverage", "brief": "Permanent fixes and insurance matched to real operations, not repeated incidents."}]'::jsonb),
  ('INT-DLV-026', 'Growth to Maturity — Delivery Liability Management', 'DLV-013', '["RC-DLV-051", "RC-DLV-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Build a standard process for handling accident claims.", "Track claims history to find patterns.", "Fix the most frequent cause first."]'::jsonb, '[{"name": "Standard Claims Process, Track Patterns", "brief": "A defined process and pattern tracking instead of ad hoc handling."}]'::jsonb),
  ('INT-DLV-027', 'Growth to Maturity — Delivery Liability Management', 'DLV-013', '["RC-DLV-052", "RC-DLV-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Clearly define cargo damage liability with every customer.", "Name someone specifically responsible for liability management.", "Review the definition as operations scale."]'::jsonb, '[{"name": "Define Liability, Assign Ownership", "brief": "Clear terms with customers and a named owner for liability exposure."}]'::jsonb),
  ('INT-DLV-028', 'Growth to Maturity — Delivery Technology Gap', 'DLV-014', '["RC-DLV-055", "RC-DLV-057"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Build a simple process for evaluating new delivery technology.", "Set aside a budget for technology investment.", "Review and adopt on a fixed schedule rather than reactively."]'::jsonb, '[{"name": "A Process and Budget for Technology", "brief": "Systematic evaluation and funded upgrades instead of falling behind."}]'::jsonb),
  ('INT-DLV-029', 'Growth to Maturity — Delivery Technology Gap', 'DLV-014', '["RC-DLV-056"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Automate dispatch and routing where manual handling is now the bottleneck.", "Start with the highest volume routes.", "Measure whether it actually improves on time performance."]'::jsonb, '[{"name": "Automate the Highest Volume Routes", "brief": "Targeted automation where manual dispatch is causing the most strain."}]'::jsonb),
  ('INT-DLV-030', 'Growth to Maturity — Delivery Defensibility', 'DLV-015', '["RC-DLV-058", "RC-DLV-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Build a proprietary routing method or service advantage.", "Make it central to the customer experience, not a side feature.", "Use it as the reason to choose you over a competitor."]'::jsonb, '[{"name": "Build Something Proprietary", "brief": "An owned advantage that a competitor cannot simply copy."}]'::jsonb),
  ('INT-DLV-031', 'Growth to Maturity — Delivery Defensibility', 'DLV-015', '["RC-DLV-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Build an exclusive relationship or capability beyond price.", "Track how often customers leave for a marginally cheaper competitor.", "Use the relationship to reduce that churn."]'::jsonb, '[{"name": "Build Beyond Price", "brief": "A real reason for customers to stay that is not just being cheaper."}]'::jsonb),
  ('INT-DLV-032', 'Ideation — Delivery Capacity Planning', 'DLV-003', '["RC-DLV-061"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Research what delivery radius a comparable service actually covers.", "Use that as a realistic planning baseline.", "Adjust your zone size around it."]'::jsonb, '[{"name": "Use a Real Comparable Delivery Radius", "brief": "Planning around researched coverage instead of an optimistic guess."}]'::jsonb),
  ('INT-DLV-033', 'Ideation — Delivery Model Clarity', 'DLV-004', '["RC-DLV-062"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Confirm a real test order volume before scaling commitments.", "Do not commit to a full zone or model based on hope.", "Scale only once the test proves demand."]'::jsonb, '[{"name": "Test Volume Before Scaling", "brief": "Confirmed demand before committing further, not assumptions."}]'::jsonb),
  ('INT-DLV-034', 'Validation to Traction — Delivery Fleet Maintenance', 'DLV-007', '["RC-DLV-063"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Write a specific plan for a vehicle going out of service mid route.", "Identify backup capacity or a response process.", "Test the plan before you actually need it."]'::jsonb, '[{"name": "Plan for a Mid Route Breakdown", "brief": "A tested response ready before a vehicle fails during delivery."}]'::jsonb)
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
    ]

    expected = {
        "problems_inserted": 15,
        "root_causes_inserted": 66,
        "questions_inserted": 60,
        "tags_inserted": 60,
        "interventions_inserted": 34,
    }

    for label, industry_code, prefix, sql in seeds:
        sql = sql.replace("\u00e2\u2020\u2019", "\u2192").replace("\u00e2\u20ac\u201d", "\u2014")
        result = dict(bind.exec_driver_sql(sql).mappings().one())
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
        "Migration e0d42f5a7b93 is intentionally irreversible. "
        "Roll back application code without deleting production seed history."
    )
