"""seed industry batch E: manufacturing, SaaS, logistics

Revision ID: f1e53a6b8c04
Revises: e0d42f5a7b93
Create Date: 2026-09-20

Production pre-audit at e0d42f5a7b93 confirmed zero MFG/SAS/LOG
diagnostic rows. Manufacturing and SaaS master rows already existed;
their rich profile metadata is intentionally preserved.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "f1e53a6b8c04"
down_revision: Union[str, Sequence[str], None] = "e0d42f5a7b93"
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


def _prefix_count(bind, table: str, column: str, pattern: str) -> int:
    return bind.execute(
        text(f"SELECT COUNT(*) FROM {table} WHERE {column} ~ :pattern"),
        {"pattern": pattern},
    ).scalar_one()


def upgrade() -> None:
    bind = op.get_bind()

    _sync_sequence(bind, "industries", "industry_id")
    _sync_sequence(bind, "interventions", "intervention_id")

    # Re-check the exact production state this migration was built for.
    # If another migration/session seeded any of these prefixes meanwhile,
    # stop instead of duplicating or partially reconciling silently.
    preconditions = [
        ("Manufacturing", "MFG", "manufacturing"),
        ("Technology & SaaS", "SAS", "saas"),
        ("Logistics & Supply Chain", "LOG", "logistics"),
    ]
    for label, prefix, industry_code in preconditions:
        existing = {
            "problems": _prefix_count(bind, "problems", "problem_code", rf"^{prefix}-[0-9]{{3}}$"),
            "root_causes": _prefix_count(bind, "root_causes", "root_cause_code", rf"^RC-{prefix}-[0-9]{{3}}$"),
            "questions": _prefix_count(bind, "questions", "question_code", rf"^(S0|S01|S10)-{prefix}-[0-9]{{3}}$"),
            "interventions": _prefix_count(bind, "interventions", "intervention_code", rf"^INT-{prefix}-[0-9]{{3}}$"),
        }
        mapping_count = bind.execute(
            text("SELECT COUNT(*) FROM question_industry_mapping WHERE industry_code = :code"),
            {"code": industry_code},
        ).scalar_one()
        if any(existing.values()) or mapping_count:
            raise RuntimeError(
                f"{label} production state changed after pre-audit: "
                f"{existing}, industry_mappings={mapping_count}. "
                "Stop and reconcile before applying Batch E."
            )

    industry_rows = [
        ('manufacturing', 'Industrial & Manufacturing', 'Industrial manufacturing, factories, production businesses, components, machinery, industrial goods and related operations.'),
        ('saas', 'Technology & SaaS', 'Software products, SaaS, AI platforms, developer tools, cloud products and technology-led businesses.'),
        ('logistics', 'Logistics & Supply Chain', 'Freight, shipping, warehousing, supply-chain technology, fleet, fulfilment and logistics-service businesses.'),
    ]

    for industry_code, industry_name, description in industry_rows:
        bind.execute(
            text(
                """
                INSERT INTO industries (
                    industry_code, industry_name, description, industry_subtitle
                )
                VALUES (
                    :industry_code, :industry_name, :description, :description
                )
                ON CONFLICT (industry_code) DO UPDATE SET
                    industry_name = EXCLUDED.industry_name,
                    industry_subtitle = COALESCE(
                        industries.industry_subtitle,
                        EXCLUDED.industry_subtitle
                    )
                """
            ),
            {
                "industry_code": industry_code,
                "industry_name": industry_name,
                "description": description,
            },
        )

    seeds = [
        ('Industrial & Manufacturing', 'manufacturing', 'MFG', {'problems_inserted': 15, 'root_causes_inserted': 67, 'questions_inserted': 60, 'tags_inserted': 60, 'interventions_inserted': 35}, r"""-- ============================================================================
-- Ally :: Industry seed -- INDUSTRIAL & MANUFACTURING (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 67 root causes, 60 questions, 60 tag links,
--            35 interventions.  Industry tag: manufacturing
--
-- NAMING   : the industries row for this tag is currently titled
--            "Manufacturing & D2C".  This content is written for MANUFACTURING
--            PROPER -- heavy and light industrial production -- because D2C is
--            already covered by the separate ecommerce_d2c industry.  Consider
--            renaming the row to "Industrial & Manufacturing" so the label
--            matches the content.
--
-- COUNTS   : 67 root causes and 35 interventions, not the usual 66/34.
--            Stage 0->1 carries one extra of each (input risk and quality loss
--            each needed an additional split).  Every row is properly linked
--            and every problem has intervention coverage.
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (MFG-001, RC-MFG-014, S0-MFG-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : questions name no statutes, consent categories, thresholds or
--            certification standards.  Pollution categories, product quality
--            orders and labour rules all change and vary by state, so the
--            content asks the founder what applies to THEM.  Two durable
--            MECHANISMS are encoded, because they are structural rather than
--            parametric: the regulatory category follows the PROCESS chosen
--            (two ways of making the same product can sit in different
--            categories), and some consents must be obtained BEFORE
--            CONSTRUCTION rather than before production.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (capacity use, rejection, input risk, working
--            capital, skill dependency) starts at Stage 0->1; customer
--            concentration, maintenance, safety, certification, multi line
--            and recurring compliance at Stage 1->10+.
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
  ('MFG-001', 'No Idea How Much Setting Up Really Costs', 'Machines, space, power, deposits and working capital are all needed before a single unit is sold, and the scale of it has not been grasped.', 'Idea & Validation', 'Manufacturing Capital Reality', 'external', 4, 6, 10, '["No costing for machinery and installation", "Space, power and utility connection costs not counted", "Working capital for materials not planned", "Assuming production can start small and cheap", "No idea how long before first revenue"]'::jsonb, '["manufacturing"]'::jsonb),
  ('MFG-002', 'Approvals and Site Rules Not Checked', 'Where a unit can legally operate, and what consents it needs before construction, has not been looked into.', 'Idea & Validation', 'Manufacturing Approvals', 'external', 3, 6, 10, '["No idea which approvals are needed", "Assuming any premises can be used", "Consents assumed to come after building", "Category of the process not established", "No plan for who handles compliance"]'::jsonb, '["manufacturing"]'::jsonb),
  ('MFG-003', 'Cost Per Unit Never Worked Out Properly', 'The cost of making one unit has not been built up from materials, labour, power, wastage and overhead.', 'Idea & Validation', 'Manufacturing Unit Cost', 'external', 4, 5, 9, '["Only material cost counted", "Labour and power not included", "Wastage and rejection not allowed for", "Fixed overhead not spread across units", "Price set by looking at competitors only"]'::jsonb, '["manufacturing"]'::jsonb),
  ('MFG-004', 'No Clear Buyer for What Will Be Made', 'Production is being planned before anyone has confirmed who buys it, in what quantity and at what price.', 'Idea & Validation', 'Manufacturing Demand Clarity', 'external', 2, 5, 9, '["No confirmed buyer", "Selling to businesses and consumers treated the same", "Order size and frequency unknown", "No conversation with a real buyer yet", "Assuming a good product will find buyers"]'::jsonb, '["manufacturing"]'::jsonb),
  ('MFG-005', 'Machines Sitting Idle Most of the Time', 'Expensive equipment was bought and is running far below capacity, so the fixed cost per unit stays high.', 'Operations & Systems', 'Manufacturing Capacity Use', 'external', 3, 6, 9, '["Machines running well below capacity", "Fixed cost per unit staying high", "Capacity utilisation never measured", "Orders too small or irregular to fill the line", "Capacity bought ahead of demand"]'::jsonb, '["manufacturing"]'::jsonb),
  ('MFG-006', 'Rejection and Rework Eating the Margin', 'A meaningful share of output fails inspection or needs reworking, and nobody has measured what that costs.', 'Operations & Systems', 'Manufacturing Quality Loss', 'external', 3, 6, 9, '["Rejection rate not measured", "Rework treated as normal", "Causes of defects not investigated", "Inspection only at the final stage", "Cost of scrap not in the unit cost"]'::jsonb, '["manufacturing"]'::jsonb),
  ('MFG-007', 'Raw Material Price and Supply Unpredictable', 'Input prices move and deliveries arrive late, but selling prices and delivery promises are already fixed.', 'Operations & Systems', 'Manufacturing Input Risk', 'external', 3, 6, 9, '["Material prices moving between quote and purchase", "Deliveries arriving late", "Single supplier for key inputs", "No buffer stock of critical material", "Selling price fixed before input cost is known"]'::jsonb, '["manufacturing"]'::jsonb),
  ('MFG-008', 'Customers Paying Late While Suppliers Want Cash', 'Buyers take long credit while material must be paid for up front, so the business funds everyone else.', 'Financial Management', 'Manufacturing Working Capital', 'external', 4, 7, 10, '["Long credit given to customers", "Suppliers demanding advance or short terms", "Cash tied up in material and finished goods", "No credit line for the gap", "Growth worsening the cash position"]'::jsonb, '["manufacturing"]'::jsonb),
  ('MFG-009', 'Everything Depends on a Few Skilled Workers', 'Production quality rests on a handful of experienced people, and nothing is written down.', 'Team & Leadership', 'Manufacturing Skill Dependency', 'external', 5, 6, 9, '["Output depends on specific individuals", "No written process for each operation", "New workers trained by watching", "Quality falls when key people are absent", "No second person able to run a machine"]'::jsonb, '["manufacturing"]'::jsonb),
  ('MFG-010', 'Revenue Concentrated in a Few Large Buyers', 'A small number of customers take most of the output, so they set the price and their loss would be fatal.', 'Sales & Revenue', 'Manufacturing Customer Concentration', 'external', 4, 7, 10, '["Most output going to two or three buyers", "Prices dictated by the large customer", "Payment terms set by the buyer", "No pipeline of smaller customers", "Losing one buyer would threaten the business"]'::jsonb, '["manufacturing"]'::jsonb),
  ('MFG-011', 'Breakdowns Stopping Production Without Warning', 'Machines fail unexpectedly, orders are missed, and maintenance happens only after something breaks.', 'Operations & Systems', 'Manufacturing Maintenance', 'external', 3, 6, 9, '["Maintenance done only after failure", "Downtime not measured", "Spare parts not stocked", "No maintenance schedule", "Deliveries missed because of breakdowns"]'::jsonb, '["manufacturing"]'::jsonb),
  ('MFG-012', 'Worker Safety and Statutory Obligations at Scale', 'More people, machines and shifts mean one accident or inspection failure could stop the unit and bring liability.', 'Operations & Systems', 'Manufacturing Safety and Labour', 'external', 3, 7, 10, '["No documented safety procedures", "Workers not trained on machine safety", "Incidents not recorded", "Statutory registers and returns not maintained", "Contract labour arrangements undocumented"]'::jsonb, '["manufacturing"]'::jsonb),
  ('MFG-013', 'Buyers Now Demand Certification and Audits', 'Larger customers require quality certification, process documentation and factory audits the unit cannot yet pass.', 'Operations & Systems', 'Manufacturing Certification', 'external', 3, 6, 10, '["Orders lost for lack of certification", "Customer audits failed or avoided", "Process documentation incomplete", "No traceability from batch to material", "Certification treated as paperwork"]'::jsonb, '["manufacturing"]'::jsonb),
  ('MFG-014', 'Second Plant or Line Does Not Match the First', 'Capacity was added but the new line produces different quality and cost from the original.', 'Operations & Systems', 'Manufacturing Multi Site', 'external', 3, 6, 9, '["New line quality below the original", "Nothing written down to replicate", "Different suppliers and settings per line", "Founder still needed on the first line", "Cost per unit differing between lines"]'::jsonb, '["manufacturing"]'::jsonb),
  ('MFG-015', 'Compliance Burden Now Recurring and Heavy', 'Environmental, labour, tax and product filings all recur on cycles, and at this size they cannot run on memory.', 'Operations & Systems', 'Manufacturing Compliance Operations', 'external', 3, 7, 10, '["Filings and renewals done from memory", "Consent validity periods not tracked", "Product standards changing without notice reaching the floor", "No single compliance calendar", "One person holding all the knowledge"]'::jsonb, '["manufacturing"]'::jsonb)
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
         t.primary_stage_group, '["manufacturing"]'::jsonb, z.v
  FROM (VALUES
  ('RC-MFG-001', 'No Costing for Machinery and Installation', 'What the equipment costs to buy and install has not been priced.', 'MFG-001', 'external', 'Knowledge', 0.73, 'Stage 0'),
  ('RC-MFG-002', 'Space, Power and Utility Costs Not Counted', 'Premises, electrical load and connections are missing from the numbers.', 'MFG-001', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-MFG-003', 'Working Capital for Materials Not Planned', 'Money to buy raw material before selling has not been arranged.', 'MFG-001', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-MFG-004', 'Assuming It Can Start Small and Cheap', 'Believing production scales down to a hobby budget.', 'MFG-001', 'external', 'Psychological', 0.69, 'Stage 0'),
  ('RC-MFG-005', 'Time to First Revenue Unknown', 'How many months until the first sale has not been worked out.', 'MFG-001', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-MFG-006', 'Required Approvals Unknown', 'Which consents the unit needs has not been established.', 'MFG-002', 'external', 'Knowledge', 0.73, 'Stage 0'),
  ('RC-MFG-007', 'Assuming Any Premises Can Be Used', 'Believing a unit can operate wherever space is available.', 'MFG-002', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-MFG-008', 'Consents Assumed to Come After Building', 'Not knowing some approvals must be obtained before construction.', 'MFG-002', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-MFG-009', 'Process Category Not Established', 'Which regulatory category the chosen process falls into is unknown.', 'MFG-002', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-MFG-010', 'No Owner for Compliance', 'Nobody has been made responsible for approvals and renewals.', 'MFG-002', 'external', 'Operational', 0.64, 'Stage 0'),
  ('RC-MFG-011', 'Only Material Cost Counted', 'The unit cost is taken as the price of raw material.', 'MFG-003', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-MFG-012', 'Labour and Power Not Included', 'The people and energy consumed per unit are left out.', 'MFG-003', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-MFG-013', 'Wastage and Rejection Not Allowed For', 'The cost is built assuming nothing is scrapped.', 'MFG-003', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-MFG-014', 'Fixed Overhead Not Spread Across Units', 'Rent, salaries and depreciation are not loaded onto each unit.', 'MFG-003', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-MFG-015', 'Price Set by Looking at Competitors', 'Pricing copies others without knowing own cost.', 'MFG-003', 'external', 'Behavioural', 0.67, 'Stage 0'),
  ('RC-MFG-016', 'No Confirmed Buyer', 'Nobody has committed to purchasing anything.', 'MFG-004', 'external', 'Behavioural', 0.72, 'Stage 0'),
  ('RC-MFG-017', 'Business and Consumer Buyers Treated the Same', 'Two very different buying processes are assumed identical.', 'MFG-004', 'external', 'Strategic', 0.68, 'Stage 0'),
  ('RC-MFG-018', 'Order Size and Frequency Unknown', 'How much a buyer would take and how often has not been asked.', 'MFG-004', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-MFG-019', 'Capacity Utilisation Never Measured', 'How much of the available capacity is actually used is unknown.', 'MFG-005', 'external', 'Knowledge', 0.73, 'Stage 0→1'),
  ('RC-MFG-020', 'Capacity Bought Ahead of Demand', 'Equipment was purchased before orders existed to fill it.', 'MFG-005', 'external', 'Strategic', 0.71, 'Stage 0→1'),
  ('RC-MFG-021', 'Orders Too Small or Irregular', 'Demand arrives in quantities that cannot fill a production run.', 'MFG-005', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-MFG-022', 'Fixed Cost Per Unit Staying High', 'Low volume keeps overhead per unit uncompetitive.', 'MFG-005', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-MFG-023', 'No Job Work or Contract Volume', 'Spare capacity is not being sold to anyone else.', 'MFG-005', 'external', 'Strategic', 0.67, 'Stage 0→1'),
  ('RC-MFG-024', 'Rejection Rate Not Measured', 'How much output fails is not tracked.', 'MFG-006', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-MFG-025', 'Rework Treated as Normal', 'Fixing defects is accepted as part of the process.', 'MFG-006', 'external', 'Behavioural', 0.71, 'Stage 0→1'),
  ('RC-MFG-026', 'Defect Causes Not Investigated', 'Failures are corrected but their cause is never found.', 'MFG-006', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-MFG-027', 'Inspection Only at the Final Stage', 'Problems are caught after all the value has been added.', 'MFG-006', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-MFG-028', 'Cost of Scrap Not in the Unit Cost', 'Wasted material and time are not loaded onto good units.', 'MFG-006', 'external', 'Knowledge', 0.69, 'Stage 0→1'),
  ('RC-MFG-029', 'Material Prices Moving Between Quote and Purchase', 'Input cost changes after the selling price is committed.', 'MFG-007', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-MFG-030', 'Single Supplier for Key Inputs', 'Critical material comes from only one source.', 'MFG-007', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-MFG-031', 'No Buffer Stock of Critical Material', 'Nothing is held against a delivery failure.', 'MFG-007', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-MFG-032', 'Deliveries Arriving Late', 'Suppliers are not meeting agreed dates.', 'MFG-007', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-MFG-033', 'Selling Price Fixed Before Input Cost Known', 'Quotes are committed before material is secured.', 'MFG-007', 'external', 'Behavioural', 0.71, 'Stage 0→1'),
  ('RC-MFG-034', 'Long Credit Given to Customers', 'Buyers are allowed to pay well after delivery.', 'MFG-008', 'external', 'Strategic', 0.73, 'Stage 0→1'),
  ('RC-MFG-035', 'Suppliers Demanding Advance or Short Terms', 'Material must be paid for before or soon after receipt.', 'MFG-008', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-MFG-036', 'Cash Tied Up in Material and Finished Goods', 'Value sits as stock rather than money.', 'MFG-008', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-MFG-037', 'No Credit Line for the Gap', 'Nothing has been arranged to bridge the cycle.', 'MFG-008', 'external', 'Strategic', 0.70, 'Stage 0→1'),
  ('RC-MFG-038', 'Growth Worsening the Cash Position', 'Each new order deepens the cash strain.', 'MFG-008', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-MFG-039', 'No Written Process for Each Operation', 'How each job is done exists only in individual heads.', 'MFG-009', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-MFG-040', 'New Workers Trained by Watching', 'Skills pass by observation rather than instruction.', 'MFG-009', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-MFG-041', 'Quality Falls When Key People Are Absent', 'Output depends on specific individuals being present.', 'MFG-009', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-MFG-042', 'Most Output Going to Few Buyers', 'A handful of customers absorb nearly all production.', 'MFG-010', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-MFG-043', 'Prices Dictated by the Large Customer', 'The dominant buyer sets what the business can charge.', 'MFG-010', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-MFG-044', 'Payment Terms Set by the Buyer', 'Credit periods are imposed rather than negotiated.', 'MFG-010', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-MFG-045', 'No Pipeline of Smaller Customers', 'Nothing is being built that could replace a lost large buyer.', 'MFG-010', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-MFG-046', 'Maintenance Done Only After Failure', 'Machines are repaired when they break rather than serviced.', 'MFG-011', 'external', 'Behavioural', 0.73, 'Stage 1→10+'),
  ('RC-MFG-047', 'Downtime Not Measured', 'How many hours are lost to breakdowns is unknown.', 'MFG-011', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-MFG-048', 'Spare Parts Not Stocked', 'Critical parts must be sourced after a failure.', 'MFG-011', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-MFG-049', 'No Maintenance Schedule', 'Nothing defines what is serviced and when.', 'MFG-011', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-MFG-050', 'Deliveries Missed Because of Breakdowns', 'Customer commitments fail when machines stop.', 'MFG-011', 'external', 'Operational', 0.68, 'Stage 1→10+'),
  ('RC-MFG-051', 'No Documented Safety Procedures', 'How to work safely on each machine is not written down.', 'MFG-012', 'external', 'Operational', 0.74, 'Stage 1→10+'),
  ('RC-MFG-052', 'Workers Not Trained on Machine Safety', 'People operate equipment without formal safety instruction.', 'MFG-012', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-MFG-053', 'Incidents Not Recorded', 'Accidents and near misses are not captured anywhere.', 'MFG-012', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-MFG-054', 'Statutory Registers Not Maintained', 'Required records and returns are incomplete.', 'MFG-012', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-MFG-055', 'Contract Labour Arrangements Undocumented', 'Workers engaged through contractors have unclear status.', 'MFG-012', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-MFG-056', 'Orders Lost for Lack of Certification', 'Buyers are choosing certified competitors.', 'MFG-013', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-MFG-057', 'Process Documentation Incomplete', 'What an auditor would ask for cannot be produced.', 'MFG-013', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-MFG-058', 'No Traceability From Batch to Material', 'You cannot trace a finished batch back to its inputs.', 'MFG-013', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-MFG-059', 'Certification Treated as Paperwork', 'The standard is seen as a form rather than a way of working.', 'MFG-013', 'external', 'Behavioural', 0.69, 'Stage 1→10+'),
  ('RC-MFG-060', 'Nothing Written Down to Replicate', 'The original line runs on knowledge nobody has recorded.', 'MFG-014', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-MFG-061', 'Different Suppliers and Settings Per Line', 'Each line buys and runs differently.', 'MFG-014', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-MFG-062', 'Founder Still Needed on the First Line', 'The original line cannot run without the founder present.', 'MFG-014', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-MFG-063', 'Cost Per Unit Differing Between Lines', 'The same product costs different amounts to make.', 'MFG-014', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-MFG-064', 'Filings and Renewals Done From Memory', 'Compliance depends on somebody remembering.', 'MFG-015', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-MFG-065', 'Consent Validity Periods Not Tracked', 'When each approval expires is not recorded.', 'MFG-015', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-MFG-066', 'Standards Changing Without Reaching the Floor', 'Rule changes are not communicated to production.', 'MFG-015', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-MFG-067', 'One Person Holding All the Knowledge', 'Compliance capability sits with a single individual.', 'MFG-015', 'external', 'Operational', 0.70, 'Stage 1→10+')
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
         '["manufacturing"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-MFG-001', 'What would the machinery cost to buy and install?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-001', 'RC-MFG-001', 1, 'Stage 0'),
  ('S0-MFG-002', 'Have you counted the space, power connection and utilities?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-001', 'RC-MFG-002', 2, 'Stage 0'),
  ('S0-MFG-003', 'How much money do you need just to buy raw material before selling?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-001', 'RC-MFG-003', 1, 'Stage 0'),
  ('S0-MFG-004', 'How many months before your first rupee of revenue?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-001', 'RC-MFG-005', 1, 'Stage 0'),
  ('S0-MFG-005', 'Do you think you can start production on a small budget?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-001', 'RC-MFG-004', 2, 'Stage 0'),
  ('S0-MFG-006', 'Do you know which approvals your kind of unit needs?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-002', 'RC-MFG-006', 1, 'Stage 0'),
  ('S0-MFG-007', 'Do you think you can set up a unit on any premises you find?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-002', 'RC-MFG-007', 1, 'Stage 0'),
  ('S0-MFG-008', 'Do you know which approvals must come before you start building?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-002', 'RC-MFG-008', 2, 'Stage 0'),
  ('S0-MFG-009', 'Do you know which category your process falls into?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-002', 'RC-MFG-009', 2, 'Stage 0'),
  ('S0-MFG-010', 'Who would handle your approvals and renewals?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-002', 'RC-MFG-010', 2, 'Stage 0'),
  ('S0-MFG-011', 'What does it cost you to make one unit?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-003', 'RC-MFG-011', 1, 'Stage 0'),
  ('S0-MFG-012', 'Have you included labour and power in that cost?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-003', 'RC-MFG-012', 2, 'Stage 0'),
  ('S0-MFG-013', 'Have you allowed for wastage and rejected pieces?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-003', 'RC-MFG-013', 2, 'Stage 0'),
  ('S0-MFG-014', 'Have you spread rent, salaries and machine cost across each unit?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-003', 'RC-MFG-014', 2, 'Stage 0'),
  ('S0-MFG-015', 'Has anyone confirmed they would buy this, and how much?', 'open_text', 'Idea & Validation', 'CORE', 'MFG-004', 'RC-MFG-016', 1, 'Stage 0'),
  ('S01-MFG-001', 'What share of your machine capacity is actually being used?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-005', 'RC-MFG-019', 2, 'Stage 0→1'),
  ('S01-MFG-002', 'Did you buy the machine before you had the orders to fill it?', 'open_text', 'Strategy & Planning', 'CORE', 'MFG-005', 'RC-MFG-020', 2, 'Stage 0→1'),
  ('S01-MFG-003', 'Are your orders big enough to make a full production run worthwhile?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-005', 'RC-MFG-021', 2, 'Stage 0→1'),
  ('S01-MFG-004', 'How much does low volume add to your cost per unit?', 'open_text', 'Financial Management', 'CORE', 'MFG-005', 'RC-MFG-022', 3, 'Stage 0→1'),
  ('S01-MFG-005', 'Could you sell your spare capacity to someone else?', 'open_text', 'Sales & Revenue', 'CORE', 'MFG-005', 'RC-MFG-023', 2, 'Stage 0→1'),
  ('S01-MFG-006', 'Out of 100 pieces you make, how many are rejected or reworked?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-006', 'RC-MFG-024', 2, 'Stage 0→1'),
  ('S01-MFG-007', 'Is rework treated as normal here?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-006', 'RC-MFG-025', 2, 'Stage 0→1'),
  ('S01-MFG-008', 'When something is rejected, does anyone find out why?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-006', 'RC-MFG-026', 2, 'Stage 0→1'),
  ('S01-MFG-009', 'At what stage do you check quality, at the end or during?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-006', 'RC-MFG-027', 2, 'Stage 0→1'),
  ('S01-MFG-010', 'Is the cost of scrap included in the price of the good pieces?', 'open_text', 'Financial Management', 'CORE', 'MFG-006', 'RC-MFG-028', 3, 'Stage 0→1'),
  ('S01-MFG-011', 'How much have your material prices moved in the last year?', 'open_text', 'Financial Management', 'CORE', 'MFG-007', 'RC-MFG-029', 2, 'Stage 0→1'),
  ('S01-MFG-012', 'Is there any material you can only get from one supplier?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-007', 'RC-MFG-030', 2, 'Stage 0→1'),
  ('S01-MFG-013', 'How many days of critical material do you keep in stock?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-007', 'RC-MFG-031', 2, 'Stage 0→1'),
  ('S01-MFG-014', 'How often do supplier deliveries arrive late?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-007', 'RC-MFG-032', 2, 'Stage 0→1'),
  ('S01-MFG-015', 'Do you fix your selling price before you have secured the material?', 'open_text', 'Financial Management', 'CORE', 'MFG-007', 'RC-MFG-033', 3, 'Stage 0→1'),
  ('S01-MFG-016', 'How long do your customers take to pay?', 'open_text', 'Financial Management', 'CORE', 'MFG-008', 'RC-MFG-034', 2, 'Stage 0→1'),
  ('S01-MFG-017', 'How soon do your suppliers want their money?', 'open_text', 'Financial Management', 'CORE', 'MFG-008', 'RC-MFG-035', 2, 'Stage 0→1'),
  ('S01-MFG-018', 'How much of your money is sitting as material and finished stock?', 'open_text', 'Financial Management', 'CORE', 'MFG-008', 'RC-MFG-036', 2, 'Stage 0→1'),
  ('S01-MFG-019', 'Do you have a credit line covering that gap?', 'open_text', 'Financial Management', 'CORE', 'MFG-008', 'RC-MFG-037', 2, 'Stage 0→1'),
  ('S01-MFG-020', 'If your most skilled worker did not come in for a week, what would happen?', 'open_text', 'Team & Leadership', 'CORE', 'MFG-009', 'RC-MFG-041', 2, 'Stage 0→1'),
  ('S10-MFG-001', 'What share of your output goes to your top two or three buyers?', 'open_text', 'Sales & Revenue', 'CORE', 'MFG-010', 'RC-MFG-042', 2, 'Stage 1→10+'),
  ('S10-MFG-002', 'Who sets your price, you or your biggest customer?', 'open_text', 'Sales & Revenue', 'CORE', 'MFG-010', 'RC-MFG-043', 2, 'Stage 1→10+'),
  ('S10-MFG-003', 'Who decides your payment terms?', 'open_text', 'Financial Management', 'CORE', 'MFG-010', 'RC-MFG-044', 2, 'Stage 1→10+'),
  ('S10-MFG-004', 'If your largest buyer left, how long could you continue?', 'open_text', 'Strategy & Planning', 'CORE', 'MFG-010', 'RC-MFG-045', 3, 'Stage 1→10+'),
  ('S10-MFG-005', 'Do you service machines on a schedule or only when they break?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-011', 'RC-MFG-046', 2, 'Stage 1→10+'),
  ('S10-MFG-006', 'How many production hours did you lose to breakdowns last month?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-011', 'RC-MFG-047', 2, 'Stage 1→10+'),
  ('S10-MFG-007', 'Do you keep spares for the parts that fail most often?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-011', 'RC-MFG-048', 2, 'Stage 1→10+'),
  ('S10-MFG-008', 'Is there a written maintenance schedule for each machine?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-011', 'RC-MFG-049', 2, 'Stage 1→10+'),
  ('S10-MFG-009', 'Have you missed a customer delivery because a machine stopped?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-011', 'RC-MFG-050', 2, 'Stage 1→10+'),
  ('S10-MFG-010', 'Is there a written safety procedure for each machine?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-012', 'RC-MFG-051', 3, 'Stage 1→10+'),
  ('S10-MFG-011', 'What safety training does a new worker get before touching a machine?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-012', 'RC-MFG-052', 3, 'Stage 1→10+'),
  ('S10-MFG-012', 'Where do you record accidents and near misses?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-012', 'RC-MFG-053', 2, 'Stage 1→10+'),
  ('S10-MFG-013', 'Are your statutory registers and returns up to date?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-012', 'RC-MFG-054', 3, 'Stage 1→10+'),
  ('S10-MFG-014', 'Is the status of your contract workers documented?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-012', 'RC-MFG-055', 3, 'Stage 1→10+'),
  ('S10-MFG-015', 'Have you lost an order because you lacked a certification?', 'open_text', 'Sales & Revenue', 'CORE', 'MFG-013', 'RC-MFG-056', 2, 'Stage 1→10+'),
  ('S10-MFG-016', 'If a customer audited your factory next week, would you pass?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-013', 'RC-MFG-057', 3, 'Stage 1→10+'),
  ('S10-MFG-017', 'Can you trace a finished batch back to the material it came from?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-013', 'RC-MFG-058', 3, 'Stage 1→10+'),
  ('S10-MFG-018', 'Is certification something you do, or something you have on paper?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-013', 'RC-MFG-059', 3, 'Stage 1→10+'),
  ('S10-MFG-019', 'Does your newest line match the quality of the original?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-014', 'RC-MFG-060', 2, 'Stage 1→10+'),
  ('S10-MFG-020', 'Is there anything written down that a new line could be set up from?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-014', 'RC-MFG-060', 2, 'Stage 1→10+'),
  ('S10-MFG-021', 'Do all your lines use the same suppliers and settings?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-014', 'RC-MFG-061', 2, 'Stage 1→10+'),
  ('S10-MFG-022', 'Can the first line run properly without you there?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-014', 'RC-MFG-062', 3, 'Stage 1→10+'),
  ('S10-MFG-023', 'Does the same product cost the same to make on every line?', 'open_text', 'Financial Management', 'CORE', 'MFG-014', 'RC-MFG-063', 3, 'Stage 1→10+'),
  ('S10-MFG-024', 'Are your filings and renewals on a calendar or in someone head?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-015', 'RC-MFG-064', 2, 'Stage 1→10+'),
  ('S10-MFG-025', 'Do you know when each of your approvals expires?', 'open_text', 'Operations & Systems', 'CORE', 'MFG-015', 'RC-MFG-065', 2, 'Stage 1→10+')
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
  ('S0-MFG-001', 'willingness-to-pay'),
  ('S0-MFG-002', 'willingness-to-pay'),
  ('S0-MFG-003', 'willingness-to-pay'),
  ('S0-MFG-004', 'willingness-to-pay'),
  ('S0-MFG-005', 'willingness-to-pay'),
  ('S0-MFG-006', 'technical-quality'),
  ('S0-MFG-007', 'technical-quality'),
  ('S0-MFG-008', 'technical-quality'),
  ('S0-MFG-009', 'technical-quality'),
  ('S0-MFG-010', 'technical-quality'),
  ('S0-MFG-011', 'willingness-to-pay'),
  ('S0-MFG-012', 'willingness-to-pay'),
  ('S0-MFG-013', 'willingness-to-pay'),
  ('S0-MFG-014', 'willingness-to-pay'),
  ('S0-MFG-015', 'icp'),
  ('S01-MFG-001', 'technical-quality'),
  ('S01-MFG-002', 'technical-quality'),
  ('S01-MFG-003', 'technical-quality'),
  ('S01-MFG-004', 'technical-quality'),
  ('S01-MFG-005', 'technical-quality'),
  ('S01-MFG-006', 'technical-quality'),
  ('S01-MFG-007', 'technical-quality'),
  ('S01-MFG-008', 'technical-quality'),
  ('S01-MFG-009', 'technical-quality'),
  ('S01-MFG-010', 'technical-quality'),
  ('S01-MFG-011', 'technical-quality'),
  ('S01-MFG-012', 'technical-quality'),
  ('S01-MFG-013', 'technical-quality'),
  ('S01-MFG-014', 'technical-quality'),
  ('S01-MFG-015', 'technical-quality'),
  ('S01-MFG-016', 'willingness-to-pay'),
  ('S01-MFG-017', 'willingness-to-pay'),
  ('S01-MFG-018', 'willingness-to-pay'),
  ('S01-MFG-019', 'willingness-to-pay'),
  ('S01-MFG-020', 'technical-quality'),
  ('S10-MFG-001', 'icp'),
  ('S10-MFG-002', 'icp'),
  ('S10-MFG-003', 'icp'),
  ('S10-MFG-004', 'icp'),
  ('S10-MFG-005', 'technical-quality'),
  ('S10-MFG-006', 'technical-quality'),
  ('S10-MFG-007', 'technical-quality'),
  ('S10-MFG-008', 'technical-quality'),
  ('S10-MFG-009', 'technical-quality'),
  ('S10-MFG-010', 'technical-quality'),
  ('S10-MFG-011', 'technical-quality'),
  ('S10-MFG-012', 'technical-quality'),
  ('S10-MFG-013', 'technical-quality'),
  ('S10-MFG-014', 'technical-quality'),
  ('S10-MFG-015', 'technical-quality'),
  ('S10-MFG-016', 'technical-quality'),
  ('S10-MFG-017', 'technical-quality'),
  ('S10-MFG-018', 'technical-quality'),
  ('S10-MFG-019', 'technical-quality'),
  ('S10-MFG-020', 'technical-quality'),
  ('S10-MFG-021', 'technical-quality'),
  ('S10-MFG-022', 'technical-quality'),
  ('S10-MFG-023', 'technical-quality'),
  ('S10-MFG-024', 'technical-quality'),
  ('S10-MFG-025', 'technical-quality')
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
         '["manufacturing"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-MFG-001', 'Ideation — Manufacturing Capital Reality', 'MFG-001', '["RC-MFG-001", "RC-MFG-002"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Price the machinery including installation and commissioning.", "Add premises, power connection and utility deposits.", "Get quotes rather than estimates."]'::jsonb, '[{"name": "Real Setup Cost", "brief": "A quoted figure for equipment, premises and connections."}]'::jsonb),
  ('INT-MFG-002', 'Ideation — Manufacturing Capital Reality', 'MFG-001', '["RC-MFG-003", "RC-MFG-005"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Work out how much material you must buy before the first sale.", "Count the months until money comes back.", "Add both to your setup cost to get what you really need."]'::jsonb, '[{"name": "Setup Plus Working Capital", "brief": "Counting material money and the wait, not just the machines."}]'::jsonb),
  ('INT-MFG-003', 'Ideation — Manufacturing Capital Reality', 'MFG-001', '["RC-MFG-004"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Find someone running a similar unit and ask what it cost them.", "Compare that against what you have.", "Decide honestly whether to proceed, partner or job work first."]'::jsonb, '[{"name": "Check Against a Real Unit", "brief": "Benchmarking your budget against someone who has actually built one."}]'::jsonb),
  ('INT-MFG-004', 'Ideation — Manufacturing Approvals', 'MFG-002', '["RC-MFG-006", "RC-MFG-009"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Establish which category your process falls into.", "Find out which approvals that category requires.", "Note that a different process may fall in a different category."]'::jsonb, '[{"name": "Know Your Process Category", "brief": "The category follows the process chosen, and it drives every approval."}]'::jsonb),
  ('INT-MFG-005', 'Ideation — Manufacturing Approvals', 'MFG-002', '["RC-MFG-007", "RC-MFG-008"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Confirm the site is permitted for your kind of unit before committing.", "Find out which consents must be obtained before construction.", "Never build first and apply afterwards."]'::jsonb, '[{"name": "Site and Consent Before Build", "brief": "Some approvals must exist before construction, not before production."}]'::jsonb),
  ('INT-MFG-006', 'Ideation — Manufacturing Approvals', 'MFG-002', '["RC-MFG-010"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Name one person responsible for approvals and renewals.", "Keep a dated list of what must be obtained or renewed.", "Review it every quarter."]'::jsonb, '[{"name": "One Compliance Owner", "brief": "A single accountable person and a dated list."}]'::jsonb),
  ('INT-MFG-007', 'Ideation — Manufacturing Unit Cost', 'MFG-003', '["RC-MFG-011", "RC-MFG-012", "RC-MFG-013"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Build a cost sheet for one unit from material, labour and power.", "Add an allowance for wastage and rejection.", "Use real consumption, not theoretical."]'::jsonb, '[{"name": "Build the Unit Cost Sheet", "brief": "Material, labour, power and scrap for one real unit."}]'::jsonb),
  ('INT-MFG-008', 'Ideation — Manufacturing Unit Cost', 'MFG-003', '["RC-MFG-014", "RC-MFG-015"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Divide rent, salaries and machine cost by realistic monthly volume.", "Add that to your unit cost.", "Compare the total against the price you planned to charge."]'::jsonb, '[{"name": "Load the Overhead", "brief": "Spreading fixed costs across the volume you will really make."}]'::jsonb),
  ('INT-MFG-009', 'Ideation — Manufacturing Demand Clarity', 'MFG-004', '["RC-MFG-016", "RC-MFG-018"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Talk to 10 potential buyers before buying any machine.", "Ask what quantity they would take and how often.", "Get at least one written expression of interest."]'::jsonb, '[{"name": "Confirm Demand First", "brief": "Real buyers and real order sizes before capital is committed."}]'::jsonb),
  ('INT-MFG-010', 'Ideation — Manufacturing Demand Clarity', 'MFG-004', '["RC-MFG-017"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Decide whether you sell to businesses or to consumers.", "Note that they buy in completely different ways.", "Build the plan for one of them."]'::jsonb, '[{"name": "Business or Consumer", "brief": "Choosing one buyer type because the two buy nothing alike."}]'::jsonb),
  ('INT-MFG-011', 'Validation to Traction — Manufacturing Capacity Use', 'MFG-005', '["RC-MFG-019", "RC-MFG-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Measure how many hours your machines actually run against available hours.", "Work out what low utilisation adds to your unit cost.", "Report that figure every month."]'::jsonb, '[{"name": "Measure Utilisation", "brief": "Knowing how much of the capacity you paid for is being used."}]'::jsonb),
  ('INT-MFG-012', 'Validation to Traction — Manufacturing Capacity Use', 'MFG-005', '["RC-MFG-021", "RC-MFG-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Group small orders into fuller production runs.", "Offer spare capacity as job work to others.", "Fill the line before buying any more of it."]'::jsonb, '[{"name": "Fill the Line You Have", "brief": "Batching orders and selling spare capacity before adding more."}]'::jsonb),
  ('INT-MFG-013', 'Validation to Traction — Manufacturing Capacity Use', 'MFG-005', '["RC-MFG-020"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Do not add capacity until the current line is consistently full.", "Tie any new machine to confirmed orders.", "Write down the utilisation level that would justify it."]'::jsonb, '[{"name": "Demand Before Capacity", "brief": "Adding machines only against confirmed demand."}]'::jsonb),
  ('INT-MFG-014', 'Validation to Traction — Manufacturing Quality Loss', 'MFG-006', '["RC-MFG-024", "RC-MFG-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Record rejection and rework as a percentage every day.", "Convert it into a monthly rupee figure.", "Load that cost onto the units that pass."]'::jsonb, '[{"name": "Measure and Cost the Scrap", "brief": "Turning rejection into a number that appears in the unit cost."}]'::jsonb),
  ('INT-MFG-015', 'Validation to Traction — Manufacturing Quality Loss', 'MFG-006', '["RC-MFG-026", "RC-MFG-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Move inspection earlier so defects are caught before more value is added.", "Trace each defect to its cause rather than just fixing it.", "Close the top cause first."]'::jsonb, '[{"name": "Catch It Early, Fix the Cause", "brief": "In process checks and root cause work instead of end of line sorting."}]'::jsonb),
  ('INT-MFG-016', 'Validation to Traction — Manufacturing Quality Loss', 'MFG-006', '["RC-MFG-025"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Set a target rejection rate and make it visible on the floor.", "Stop treating rework as free.", "Review the number weekly with the team."]'::jsonb, '[{"name": "Stop Normalising Rework", "brief": "A visible target so defects stop being accepted as routine."}]'::jsonb),
  ('INT-MFG-017', 'Validation to Traction — Manufacturing Input Risk', 'MFG-007', '["RC-MFG-030", "RC-MFG-031"]'::jsonb, '[2, 3, 4]'::jsonb, 'Supply Chain', '["List every input with only one supplier.", "Qualify a second source for the critical few.", "Hold buffer stock of anything that would stop the line."]'::jsonb, '[{"name": "Second Source the Critical Few", "brief": "A backup supplier and buffer for inputs that could halt production."}]'::jsonb),
  ('INT-MFG-018', 'Validation to Traction — Manufacturing Input Risk', 'MFG-007', '["RC-MFG-029", "RC-MFG-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Secure or price material before committing a selling price.", "Add a validity period to every quote.", "Include a price adjustment clause on long orders."]'::jsonb, '[{"name": "Secure Input Before Fixing Price", "brief": "Never committing a price before the material cost is known."}]'::jsonb),
  ('INT-MFG-019', 'Validation to Traction — Manufacturing Input Risk', 'MFG-007', '["RC-MFG-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Supply Chain', '["Track supplier delivery performance by date.", "Share the record with them.", "Move volume towards suppliers who deliver on time."]'::jsonb, '[{"name": "Track Supplier Delivery", "brief": "Measuring lateness and shifting volume to reliable suppliers."}]'::jsonb),
  ('INT-MFG-020', 'Validation to Traction — Manufacturing Working Capital', 'MFG-008', '["RC-MFG-034", "RC-MFG-035"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Measure the gap between paying suppliers and being paid.", "Shorten customer credit or charge for it.", "Negotiate longer supplier terms where you can."]'::jsonb, '[{"name": "Close the Payment Gap", "brief": "Pulling the two sides of the cycle closer together."}]'::jsonb),
  ('INT-MFG-021', 'Validation to Traction — Manufacturing Working Capital', 'MFG-008', '["RC-MFG-036", "RC-MFG-037", "RC-MFG-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Work out how much cash is held as material and finished stock.", "Arrange a credit line sized to the cycle.", "Check whether growth is improving or worsening cash."]'::jsonb, '[{"name": "Fund the Cycle Deliberately", "brief": "Knowing what stock ties up and arranging cover for it."}]'::jsonb),
  ('INT-MFG-022', 'Validation to Traction — Manufacturing Skill Dependency', 'MFG-009', '["RC-MFG-039", "RC-MFG-040"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Write a simple procedure for each operation.", "Train new workers against it instead of by watching.", "Keep it at the machine."]'::jsonb, '[{"name": "Written Work Instructions", "brief": "A documented method at every station so skill is transferable."}]'::jsonb),
  ('INT-MFG-023', 'Validation to Traction — Manufacturing Skill Dependency', 'MFG-009', '["RC-MFG-041"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Identify every operation only one person can run.", "Cross train a second person on each.", "Test it by having them run the machine alone."]'::jsonb, '[{"name": "Two People Per Machine", "brief": "Cross training so absence does not stop production."}]'::jsonb),
  ('INT-MFG-024', 'Growth to Maturity — Manufacturing Customer Concentration', 'MFG-010', '["RC-MFG-042", "RC-MFG-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Calculate the output share of your top three buyers.", "Set a ceiling and build a pipeline of smaller customers.", "Review the share every quarter."]'::jsonb, '[{"name": "Cap Customer Concentration", "brief": "Measuring dependence and building beyond the few large buyers."}]'::jsonb),
  ('INT-MFG-025', 'Growth to Maturity — Manufacturing Customer Concentration', 'MFG-010', '["RC-MFG-043", "RC-MFG-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Work out your real margin on each large account after their terms.", "Identify which terms you accept only because of dependence.", "Renegotiate or replace the worst."]'::jsonb, '[{"name": "Margin After Their Terms", "brief": "Seeing what a dominant buyer really leaves you."}]'::jsonb),
  ('INT-MFG-026', 'Growth to Maturity — Manufacturing Maintenance', 'MFG-011', '["RC-MFG-046", "RC-MFG-049"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Build a maintenance schedule for every machine.", "Service on the schedule, not after failure.", "Record what was done and when."]'::jsonb, '[{"name": "Planned Maintenance", "brief": "Servicing on a schedule instead of waiting for a breakdown."}]'::jsonb),
  ('INT-MFG-027', 'Growth to Maturity — Manufacturing Maintenance', 'MFG-011', '["RC-MFG-047", "RC-MFG-048", "RC-MFG-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Measure downtime hours and what they cost in lost output.", "Stock spares for the parts that fail most often.", "Use the downtime record to justify the spares."]'::jsonb, '[{"name": "Measure Downtime, Stock Spares", "brief": "Costing lost hours and holding the parts that cause them."}]'::jsonb),
  ('INT-MFG-028', 'Growth to Maturity — Manufacturing Safety and Labour', 'MFG-012', '["RC-MFG-051", "RC-MFG-052"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Write a safety procedure for every machine.", "Train every worker before they operate it and record the training.", "Refresh it periodically."]'::jsonb, '[{"name": "Safety Procedures and Training", "brief": "Written procedures plus recorded training for every operator."}]'::jsonb),
  ('INT-MFG-029', 'Growth to Maturity — Manufacturing Safety and Labour', 'MFG-012', '["RC-MFG-053", "RC-MFG-054", "RC-MFG-055"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Start recording every incident and near miss.", "Bring statutory registers and returns fully up to date.", "Document the status of contract workers."]'::jsonb, '[{"name": "Records That Survive Inspection", "brief": "Incident logs, statutory registers and clear labour documentation."}]'::jsonb),
  ('INT-MFG-030', 'Growth to Maturity — Manufacturing Certification', 'MFG-013', '["RC-MFG-056", "RC-MFG-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["List orders lost for lack of certification and put a value on it.", "Compare that against the cost of getting certified.", "Pursue the standard your buyers actually ask for."]'::jsonb, '[{"name": "Price the Certification Gap", "brief": "Treating certification as a commercial decision with a number."}]'::jsonb),
  ('INT-MFG-031', 'Growth to Maturity — Manufacturing Certification', 'MFG-013', '["RC-MFG-057", "RC-MFG-058"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Build traceability from finished batch back to raw material.", "Document your process as you actually run it.", "Run a mock audit before a customer does a real one."]'::jsonb, '[{"name": "Traceability and Mock Audit", "brief": "Batch traceability and testing yourself before a buyer does."}]'::jsonb),
  ('INT-MFG-032', 'Growth to Maturity — Manufacturing Multi Site', 'MFG-014', '["RC-MFG-060", "RC-MFG-062"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write down how the original line actually runs.", "Use that document to set up any new line.", "Spend a week away and see what breaks."]'::jsonb, '[{"name": "Document Before You Replicate", "brief": "Recording the first line so the next can copy it."}]'::jsonb),
  ('INT-MFG-033', 'Growth to Maturity — Manufacturing Multi Site', 'MFG-014', '["RC-MFG-061", "RC-MFG-063"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Use the same suppliers, settings and checks on every line.", "Compare cost and quality per unit across lines.", "Close the gap before adding a third."]'::jsonb, '[{"name": "Same Inputs, Same Output", "brief": "Common suppliers and settings so lines produce alike."}]'::jsonb),
  ('INT-MFG-034', 'Growth to Maturity — Manufacturing Compliance Operations', 'MFG-015', '["RC-MFG-064", "RC-MFG-065"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Build one calendar of every filing, renewal and consent expiry.", "Set reminders well ahead of each date.", "Review it monthly."]'::jsonb, '[{"name": "One Compliance Calendar", "brief": "Every recurring obligation and expiry in one dated place."}]'::jsonb),
  ('INT-MFG-035', 'Growth to Maturity — Manufacturing Compliance Operations', 'MFG-015', '["RC-MFG-066", "RC-MFG-067"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Give one person the job of tracking standard and rule changes.", "Make sure changes reach the production floor.", "Train a second person so it does not rest on one."]'::jsonb, '[{"name": "Changes Reach the Floor", "brief": "Tracking rule changes and making sure production actually hears them."}]'::jsonb)
  ) AS t(intervention_code, section, problem_code, root_cause_ids, stage_relevance,
         capability_domain, immediate_next_steps, recommended_frameworks)
  JOIN new_problems np ON np.problem_code = t.problem_code
  RETURNING intervention_id
)
SELECT
  (SELECT COUNT(*) FROM new_problems)     AS problems_inserted,      -- expect 15
  (SELECT COUNT(*) FROM new_root_causes)  AS root_causes_inserted,   -- expect 67
  (SELECT COUNT(*) FROM new_questions)    AS questions_inserted,     -- expect 60
  (SELECT COUNT(*) FROM new_tag_links)    AS tag_links_inserted,     -- expect 60
  (SELECT COUNT(*) FROM new_interventions) AS interventions_inserted;-- expect 35

-- ============================================================================
-- After running, the single result row above must read:  15 | 67 | 60 | 60 | 35
-- If any number differs, something did not link -- roll back and check.
-- ============================================================================"""),
        ('Technology & SaaS', 'saas', 'SAS', {'problems_inserted': 15, 'root_causes_inserted': 67, 'questions_inserted': 60, 'tags_inserted': 60, 'interventions_inserted': 36}, r"""-- ============================================================================
-- Ally :: Industry seed -- INFORMATION TECHNOLOGY & SOFTWARE / SaaS
-- ============================================================================
-- Contents : 15 problems, 67 root causes, 60 questions, 60 tag links,
--            36 interventions.  Industry tag: saas
--            (the industries row for this tag is titled "Technology & SaaS")
--
-- COUNTS   : 67 root causes and 36 interventions, not the usual 66/34.
--            Pricing needed a fifth root cause, and demand validation plus
--            defensibility each needed an extra intervention.  Every row is
--            properly linked and every problem has intervention coverage.
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (SAS-001, RC-SAS-014, S0-SAS-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : questions name no data-protection statutes, certification
--            standards or thresholds.  Those change and vary by market, so the
--            content asks the founder what applies to THEM.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (activation, free-to-paid conversion, churn,
--            pricing, founder-led sales) starts at Stage 0->1; unit economics,
--            technical debt, security posture, support load, revenue
--            concentration and defensibility at Stage 1->10+.
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
  ('SAS-001', 'Building Before Anyone Asked For It', 'Months are going into building a product when nobody has confirmed they have the problem or would pay to solve it.', 'Idea & Validation', 'SaaS Demand Validation', 'external', 1, 5, 9, '["Building started before talking to users", "Nobody has confirmed the problem exists", "No paying commitment from anyone", "Feedback only from friends and family", "Assuming people will come once it is built"]'::jsonb, '["saas"]'::jsonb),
  ('SAS-002', 'No Clear User and No Clear Buyer', 'Who this is for has not been narrowed, and in business software the person who uses it is often not the person who pays.', 'Idea & Validation', 'SaaS Buyer Clarity', 'external', 2, 5, 9, '["Target user described as everyone", "Buyer and user assumed to be the same", "No decision on business or consumer", "Company size not chosen", "No conversation with a real buyer yet"]'::jsonb, '["saas"]'::jsonb),
  ('SAS-003', 'No Idea What It Costs to Serve One Customer', 'Hosting, third party services, support and model costs per customer have never been calculated.', 'Idea & Validation', 'SaaS Cost to Serve', 'external', 4, 5, 9, '["Cost per customer unknown", "Hosting and third party service costs not counted", "Support time not costed", "Pricing set by copying competitors", "Assuming software costs nothing to run"]'::jsonb, '["saas"]'::jsonb),
  ('SAS-004', 'Handling Customer Data Without a Plan', 'The product will hold other people data, and nothing has been decided about where it lives, who sees it or what is promised.', 'Idea & Validation', 'SaaS Data Responsibility', 'external', 3, 5, 9, '["No decision on where data is stored", "Anyone on the team able to see customer data", "No privacy policy or terms", "No plan for what happens if data leaks", "Obligations to customers not understood"]'::jsonb, '["saas"]'::jsonb),
  ('SAS-005', 'People Sign Up and Never Come Back', 'Registrations look healthy but almost nobody reaches the point where the product becomes useful.', 'Sales & Revenue', 'SaaS Activation', 'external', 4, 6, 9, '["Large gap between signups and active users", "Most users never complete setup", "No onboarding beyond a signup form", "Point where the product becomes useful not defined", "Drop off point not identified"]'::jsonb, '["saas"]'::jsonb),
  ('SAS-006', 'Free Users Who Never Convert', 'A growing free base costs money to serve while producing no revenue, and nothing pushes anyone to pay.', 'Sales & Revenue', 'SaaS Conversion', 'external', 4, 6, 9, '["Free users growing faster than paying ones", "No clear reason to upgrade", "Free plan covering the main need", "Conversion rate not measured", "Serving cost rising with free signups"]'::jsonb, '["saas"]'::jsonb),
  ('SAS-007', 'Customers Leaving Faster Than They Arrive', 'Accounts cancel after a few months, so growth resets each cycle and the business never compounds.', 'Sales & Revenue', 'SaaS Churn', 'external', 4, 7, 10, '["Customers cancelling within months", "Churn rate not measured", "No warning before a cancellation", "Reasons for leaving not recorded", "Growth offset by losses"]'::jsonb, '["saas"]'::jsonb),
  ('SAS-008', 'Pricing Set Once and Never Tested', 'The price was guessed at launch and has never been revisited against value delivered or willingness to pay.', 'Financial Management', 'SaaS Pricing', 'external', 4, 6, 9, '["Price guessed at launch", "Never tested or changed", "No packaging or tiers", "Discounting to close deals", "Price not linked to value delivered"]'::jsonb, '["saas"]'::jsonb),
  ('SAS-009', 'Everything Depends on the Founder Selling', 'Every deal closes because the founder is in the room, and nobody else can sell the product.', 'Sales & Revenue', 'SaaS Founder Led Sales', 'external', 5, 6, 9, '["Every deal closed by the founder", "No written sales process", "Nobody else able to demo or close", "Pipeline stops when the founder is busy", "No record of why deals are won or lost"]'::jsonb, '["saas"]'::jsonb),
  ('SAS-010', 'Cost of Acquiring a Customer Exceeds What They Return', 'More is spent winning each customer than they ever pay back, so growth destroys money rather than making it.', 'Financial Management', 'SaaS Unit Economics', 'external', 4, 7, 10, '["Acquisition cost not measured", "Lifetime value not calculated", "Growth funded by raising money rather than margin", "Payback period unknown", "Spending more to grow makes losses larger"]'::jsonb, '["saas"]'::jsonb),
  ('SAS-011', 'Old Code Slowing Everything Down', 'Shortcuts taken early now make every change slow and risky, and the team spends more time fighting the codebase than building.', 'Operations & Systems', 'SaaS Technical Debt', 'external', 3, 6, 9, '["Every change takes longer than expected", "Small changes breaking unrelated things", "No automated tests", "Team afraid to touch certain areas", "Rewrites discussed but never scoped"]'::jsonb, '["saas"]'::jsonb),
  ('SAS-012', 'Security and Compliance Demands From Larger Buyers', 'Bigger customers require security reviews, certifications and contractual commitments the business cannot yet meet.', 'Operations & Systems', 'SaaS Security Posture', 'external', 3, 7, 10, '["Security questionnaires stalling deals", "No certification in place", "Access controls informal", "No independent testing", "Contract terms signed without checking they can be met"]'::jsonb, '["saas"]'::jsonb),
  ('SAS-013', 'Support Load Rising Faster Than Revenue', 'Each new customer adds questions and issues, and support is consuming the people who should be building.', 'Operations & Systems', 'SaaS Support Load', 'external', 3, 6, 9, '["Support tickets rising faster than customers", "Same questions asked repeatedly", "No self serve help or documentation", "Engineers pulled into support", "Response times slipping"]'::jsonb, '["saas"]'::jsonb),
  ('SAS-014', 'Revenue Concentrated in a Few Large Accounts', 'A handful of customers carry most of the revenue, so they dictate the roadmap and their loss would be severe.', 'Sales & Revenue', 'SaaS Revenue Concentration', 'external', 4, 7, 10, '["Most revenue from a few accounts", "Roadmap driven by one large customer", "Custom work done to retain them", "Terms dictated by the large account", "Losing one would threaten the business"]'::jsonb, '["saas"]'::jsonb),
  ('SAS-015', 'Nothing Stopping a Competitor Copying This', 'The product can be replicated, buyers can leave easily, and nothing accumulates that makes the business harder to displace.', 'Strategy & Planning', 'SaaS Defensibility', 'external', 2, 6, 10, '["Features copied quickly by competitors", "Nothing that gets better with more customers", "Low cost for a customer to switch away", "Competing mainly on price", "No data, network or integration advantage"]'::jsonb, '["saas"]'::jsonb)
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
         t.primary_stage_group, '["saas"]'::jsonb, z.v
  FROM (VALUES
  ('RC-SAS-001', 'Building Started Before Talking to Users', 'Code was written before anyone outside was asked.', 'SAS-001', 'external', 'Behavioural', 0.73, 'Stage 0'),
  ('RC-SAS-002', 'Problem Existence Not Confirmed', 'Nobody has checked that the problem is real and felt.', 'SAS-001', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-SAS-003', 'No Paying Commitment From Anyone', 'Interest has been expressed but no money promised.', 'SAS-001', 'external', 'Behavioural', 0.71, 'Stage 0'),
  ('RC-SAS-004', 'Feedback Only From Friends and Family', 'The people consulted are not the people who would buy.', 'SAS-001', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-SAS-005', 'Assuming Build It and They Will Come', 'Believing a good product markets itself.', 'SAS-001', 'external', 'Psychological', 0.70, 'Stage 0'),
  ('RC-SAS-006', 'Target User Described as Everyone', 'No specific user type has been chosen.', 'SAS-002', 'external', 'Strategic', 0.72, 'Stage 0'),
  ('RC-SAS-007', 'Buyer and User Assumed to Be the Same', 'The person who uses it is treated as the person who pays.', 'SAS-002', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-SAS-008', 'No Decision on Business or Consumer', 'Whether this sells to companies or individuals is unsettled.', 'SAS-002', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-SAS-009', 'Company Size Not Chosen', 'No decision on serving small firms or large ones.', 'SAS-002', 'external', 'Strategic', 0.68, 'Stage 0'),
  ('RC-SAS-010', 'No Conversation With a Real Buyer', 'Nobody who would actually purchase has been spoken to.', 'SAS-002', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-SAS-011', 'Cost Per Customer Unknown', 'What it costs to serve one account has never been worked out.', 'SAS-003', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-SAS-012', 'Hosting and Service Costs Not Counted', 'Infrastructure and third party bills are missing from the numbers.', 'SAS-003', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-SAS-013', 'Support Time Not Costed', 'The hours spent helping each customer are treated as free.', 'SAS-003', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-SAS-014', 'Assuming Software Costs Nothing to Run', 'Believing there is no marginal cost per customer.', 'SAS-003', 'external', 'Psychological', 0.69, 'Stage 0'),
  ('RC-SAS-015', 'No Decision on Where Data Is Stored', 'Where customer data will live has not been settled.', 'SAS-004', 'external', 'Operational', 0.70, 'Stage 0'),
  ('RC-SAS-016', 'Everyone on the Team Can See Customer Data', 'No limits exist on internal access.', 'SAS-004', 'external', 'Operational', 0.71, 'Stage 0'),
  ('RC-SAS-017', 'No Privacy Policy or Terms', 'Nothing sets out what the business promises about data.', 'SAS-004', 'external', 'Operational', 0.69, 'Stage 0'),
  ('RC-SAS-018', 'No Plan If Data Leaks', 'What would happen after a breach has not been considered.', 'SAS-004', 'external', 'Strategic', 0.68, 'Stage 0'),
  ('RC-SAS-019', 'No Onboarding Beyond a Signup Form', 'Nothing guides a new user to their first useful moment.', 'SAS-005', 'external', 'Operational', 0.74, 'Stage 0→1'),
  ('RC-SAS-020', 'First Useful Moment Not Defined', 'Nobody has decided what a user must do to get value.', 'SAS-005', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-SAS-021', 'Drop Off Point Not Identified', 'Where users abandon setup is not known.', 'SAS-005', 'external', 'Knowledge', 0.71, 'Stage 0→1'),
  ('RC-SAS-022', 'Setup Too Long or Complex', 'Getting started takes more effort than the user will spend.', 'SAS-005', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-SAS-023', 'Signups Counted as Success', 'Registration is treated as the result rather than the start.', 'SAS-005', 'external', 'Behavioural', 0.69, 'Stage 0→1'),
  ('RC-SAS-024', 'Free Plan Covering the Main Need', 'The free tier already solves the problem, so paying is optional.', 'SAS-006', 'external', 'Strategic', 0.73, 'Stage 0→1'),
  ('RC-SAS-025', 'No Clear Reason to Upgrade', 'Nothing meaningful sits behind the paywall.', 'SAS-006', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-SAS-026', 'Conversion Rate Not Measured', 'How many free users become paying is not tracked.', 'SAS-006', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-SAS-027', 'Serving Cost Rising With Free Signups', 'Every free user adds cost without revenue.', 'SAS-006', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-SAS-028', 'Nobody Ever Asked to Pay', 'Free users are never actively invited to upgrade.', 'SAS-006', 'external', 'Behavioural', 0.68, 'Stage 0→1'),
  ('RC-SAS-029', 'Churn Rate Not Measured', 'How many customers leave each month is not tracked.', 'SAS-007', 'external', 'Operational', 0.74, 'Stage 0→1'),
  ('RC-SAS-030', 'No Warning Before a Cancellation', 'There is no signal that an account is about to go.', 'SAS-007', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-SAS-031', 'Reasons for Leaving Not Recorded', 'Departures are not investigated or logged.', 'SAS-007', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-SAS-032', 'Product Not Part of Daily Work', 'The product is useful occasionally rather than habitually.', 'SAS-007', 'external', 'Strategic', 0.70, 'Stage 0→1'),
  ('RC-SAS-033', 'Value Not Visible to the Customer', 'Customers cannot see what they are getting for the money.', 'SAS-007', 'external', 'Strategic', 0.69, 'Stage 0→1'),
  ('RC-SAS-034', 'Price Guessed at Launch', 'The number was chosen without evidence.', 'SAS-008', 'external', 'Knowledge', 0.72, 'Stage 0→1'),
  ('RC-SAS-035', 'Price Never Tested or Changed', 'Nobody has tried a different number since launch.', 'SAS-008', 'external', 'Behavioural', 0.71, 'Stage 0→1'),
  ('RC-SAS-036', 'No Packaging or Tiers', 'Everyone is offered the same thing at the same price.', 'SAS-008', 'external', 'Strategic', 0.69, 'Stage 0→1'),
  ('RC-SAS-037', 'Discounting to Close Deals', 'Price is cut whenever a prospect hesitates.', 'SAS-008', 'external', 'Behavioural', 0.70, 'Stage 0→1'),
  ('RC-SAS-038', 'Price Not Linked to Value Delivered', 'What the customer gains has no bearing on what they pay.', 'SAS-008', 'external', 'Strategic', 0.71, 'Stage 0→1'),
  ('RC-SAS-039', 'No Written Sales Process', 'How a deal is actually won exists only in the founder head.', 'SAS-009', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-SAS-040', 'Nobody Else Able to Demo or Close', 'Only the founder can run the conversation.', 'SAS-009', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-SAS-041', 'No Record of Why Deals Are Won or Lost', 'Outcomes are not analysed, so nothing is learned.', 'SAS-009', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-SAS-042', 'Acquisition Cost Not Measured', 'What it costs to win one customer is unknown.', 'SAS-010', 'external', 'Knowledge', 0.74, 'Stage 1→10+'),
  ('RC-SAS-043', 'Lifetime Value Not Calculated', 'What a customer returns over their life has not been worked out.', 'SAS-010', 'external', 'Knowledge', 0.73, 'Stage 1→10+'),
  ('RC-SAS-044', 'Payback Period Unknown', 'How long a customer takes to repay their acquisition cost is unknown.', 'SAS-010', 'external', 'Knowledge', 0.72, 'Stage 1→10+'),
  ('RC-SAS-045', 'Growth Funded by Raising Rather Than Margin', 'Expansion depends on investor money rather than economics.', 'SAS-010', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-SAS-046', 'Spending More Makes Losses Larger', 'Each additional marketing rupee deepens the loss.', 'SAS-010', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-SAS-047', 'No Automated Tests', 'Nothing catches breakage before customers do.', 'SAS-011', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-SAS-048', 'Small Changes Breaking Unrelated Things', 'The system is entangled enough that edits have side effects.', 'SAS-011', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-SAS-049', 'Team Afraid to Touch Certain Areas', 'Parts of the codebase are avoided because they are fragile.', 'SAS-011', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-SAS-050', 'Debt Never Scoped or Budgeted', 'Cleanup is discussed but never given time.', 'SAS-011', 'external', 'Behavioural', 0.70, 'Stage 1→10+'),
  ('RC-SAS-051', 'Security Questionnaires Stalling Deals', 'Sales stop when buyers ask for security evidence.', 'SAS-012', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-SAS-052', 'No Certification in Place', 'Nothing independent attests to the security posture.', 'SAS-012', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-SAS-053', 'Access Controls Informal', 'Who can reach customer data is managed by trust rather than system.', 'SAS-012', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-SAS-054', 'No Independent Testing', 'Nobody outside has checked the system for weaknesses.', 'SAS-012', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-SAS-055', 'Terms Signed Without Checking', 'Contractual commitments are agreed without confirming they can be met.', 'SAS-012', 'external', 'Behavioural', 0.69, 'Stage 1→10+'),
  ('RC-SAS-056', 'Support Tickets Rising Faster Than Customers', 'Each additional customer adds more load than the last.', 'SAS-013', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-SAS-057', 'Same Questions Asked Repeatedly', 'The same issues recur because the cause is never fixed.', 'SAS-013', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-SAS-058', 'No Self Serve Help or Documentation', 'Every question must be answered by a person.', 'SAS-013', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-SAS-059', 'Engineers Pulled Into Support', 'Build capacity is consumed answering customer issues.', 'SAS-013', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-SAS-060', 'Most Revenue From a Few Accounts', 'A handful of customers carry the business.', 'SAS-014', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-SAS-061', 'Roadmap Driven by One Large Customer', 'Product direction follows a single account requests.', 'SAS-014', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-SAS-062', 'Custom Work Done to Retain Them', 'Bespoke building is used to keep large accounts.', 'SAS-014', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-SAS-063', 'Terms Dictated by the Large Account', 'Price and conditions are imposed by the dominant buyer.', 'SAS-014', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-SAS-064', 'Features Copied Quickly', 'Anything built is replicated by competitors within months.', 'SAS-015', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-SAS-065', 'Nothing Improves With More Customers', 'Scale brings no compounding advantage.', 'SAS-015', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-SAS-066', 'Low Cost for a Customer to Leave', 'Switching away is easy and cheap.', 'SAS-015', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-SAS-067', 'Competing Mainly on Price', 'Differentiation has collapsed into being cheaper.', 'SAS-015', 'external', 'Strategic', 0.70, 'Stage 1→10+')
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
         '["saas"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-SAS-001', 'Did you talk to users before you started building?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-001', 'RC-SAS-001', 1, 'Stage 0'),
  ('S0-SAS-002', 'How do you know this problem is real for someone other than you?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-001', 'RC-SAS-002', 1, 'Stage 0'),
  ('S0-SAS-003', 'Has anyone said they would pay for this?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-001', 'RC-SAS-003', 1, 'Stage 0'),
  ('S0-SAS-004', 'Who gave you feedback so far, and would they actually buy it?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-001', 'RC-SAS-004', 2, 'Stage 0'),
  ('S0-SAS-005', 'Do you believe people will find you once the product is ready?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-001', 'RC-SAS-005', 2, 'Stage 0'),
  ('S0-SAS-006', 'Who exactly is this for?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-002', 'RC-SAS-006', 1, 'Stage 0'),
  ('S0-SAS-007', 'Is the person who uses this the same person who pays for it?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-002', 'RC-SAS-007', 1, 'Stage 0'),
  ('S0-SAS-008', 'Are you selling to companies or to individuals?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-002', 'RC-SAS-008', 1, 'Stage 0'),
  ('S0-SAS-009', 'If companies, are you aiming at small ones or large ones?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-002', 'RC-SAS-009', 2, 'Stage 0'),
  ('S0-SAS-010', 'Have you spoken to even one person who would sign the cheque?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-002', 'RC-SAS-010', 2, 'Stage 0'),
  ('S0-SAS-011', 'What does it cost you to serve one customer for a month?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-003', 'RC-SAS-011', 1, 'Stage 0'),
  ('S0-SAS-012', 'Have you counted hosting and any paid services you depend on?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-003', 'RC-SAS-012', 2, 'Stage 0'),
  ('S0-SAS-013', 'How many hours of support would one customer need?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-003', 'RC-SAS-013', 2, 'Stage 0'),
  ('S0-SAS-014', 'Where would your customer data be stored?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-004', 'RC-SAS-015', 2, 'Stage 0'),
  ('S0-SAS-015', 'Who on your team would be able to see customer data?', 'open_text', 'Idea & Validation', 'CORE', 'SAS-004', 'RC-SAS-016', 1, 'Stage 0'),
  ('S01-SAS-001', 'Out of 100 people who sign up, how many actually use it?', 'open_text', 'Sales & Revenue', 'CORE', 'SAS-005', 'RC-SAS-021', 2, 'Stage 0→1'),
  ('S01-SAS-002', 'What happens after someone signs up?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-005', 'RC-SAS-019', 2, 'Stage 0→1'),
  ('S01-SAS-003', 'What must a user do before your product becomes useful to them?', 'open_text', 'Sales & Revenue', 'CORE', 'SAS-005', 'RC-SAS-020', 3, 'Stage 0→1'),
  ('S01-SAS-004', 'How long does setup take, and where do people give up?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-005', 'RC-SAS-022', 2, 'Stage 0→1'),
  ('S01-SAS-005', 'Are you counting signups as success?', 'open_text', 'Sales & Revenue', 'CORE', 'SAS-005', 'RC-SAS-023', 2, 'Stage 0→1'),
  ('S01-SAS-006', 'What share of your free users have ever paid?', 'open_text', 'Sales & Revenue', 'CORE', 'SAS-006', 'RC-SAS-026', 2, 'Stage 0→1'),
  ('S01-SAS-007', 'Does your free plan already solve the main problem?', 'open_text', 'Strategy & Planning', 'CORE', 'SAS-006', 'RC-SAS-024', 3, 'Stage 0→1'),
  ('S01-SAS-008', 'What does someone get by paying that they cannot get free?', 'open_text', 'Sales & Revenue', 'CORE', 'SAS-006', 'RC-SAS-025', 2, 'Stage 0→1'),
  ('S01-SAS-009', 'What do free users cost you every month?', 'open_text', 'Financial Management', 'CORE', 'SAS-006', 'RC-SAS-027', 2, 'Stage 0→1'),
  ('S01-SAS-010', 'Do you ever actually ask free users to upgrade?', 'open_text', 'Sales & Revenue', 'CORE', 'SAS-006', 'RC-SAS-028', 2, 'Stage 0→1'),
  ('S01-SAS-011', 'How many customers cancelled in the last three months?', 'open_text', 'Sales & Revenue', 'CORE', 'SAS-007', 'RC-SAS-029', 2, 'Stage 0→1'),
  ('S01-SAS-012', 'Do you get any warning before someone cancels?', 'open_text', 'Sales & Revenue', 'CORE', 'SAS-007', 'RC-SAS-030', 3, 'Stage 0→1'),
  ('S01-SAS-013', 'When someone leaves, do you record why?', 'open_text', 'Sales & Revenue', 'CORE', 'SAS-007', 'RC-SAS-031', 2, 'Stage 0→1'),
  ('S01-SAS-014', 'Is your product part of someone daily work, or occasional?', 'open_text', 'Strategy & Planning', 'CORE', 'SAS-007', 'RC-SAS-032', 3, 'Stage 0→1'),
  ('S01-SAS-015', 'Can a customer see what they are getting for the money?', 'open_text', 'Sales & Revenue', 'CORE', 'SAS-007', 'RC-SAS-033', 3, 'Stage 0→1'),
  ('S01-SAS-016', 'How did you decide your price?', 'open_text', 'Financial Management', 'CORE', 'SAS-008', 'RC-SAS-034', 1, 'Stage 0→1'),
  ('S01-SAS-017', 'Have you ever changed or tested your price?', 'open_text', 'Financial Management', 'CORE', 'SAS-008', 'RC-SAS-035', 2, 'Stage 0→1'),
  ('S01-SAS-018', 'Does everyone pay the same, or do you have tiers?', 'open_text', 'Financial Management', 'CORE', 'SAS-008', 'RC-SAS-036', 2, 'Stage 0→1'),
  ('S01-SAS-019', 'How often do you discount to close a deal?', 'open_text', 'Sales & Revenue', 'CORE', 'SAS-008', 'RC-SAS-037', 2, 'Stage 0→1'),
  ('S01-SAS-020', 'Could anyone other than you close a deal?', 'open_text', 'Sales & Revenue', 'CORE', 'SAS-009', 'RC-SAS-040', 2, 'Stage 0→1'),
  ('S10-SAS-001', 'What does it cost you to win one customer?', 'open_text', 'Financial Management', 'CORE', 'SAS-010', 'RC-SAS-042', 2, 'Stage 1→10+'),
  ('S10-SAS-002', 'What does an average customer pay you before they leave?', 'open_text', 'Financial Management', 'CORE', 'SAS-010', 'RC-SAS-043', 3, 'Stage 1→10+'),
  ('S10-SAS-003', 'How many months before a customer repays what you spent to get them?', 'open_text', 'Financial Management', 'CORE', 'SAS-010', 'RC-SAS-044', 3, 'Stage 1→10+'),
  ('S10-SAS-004', 'If you doubled marketing spend, would you make more money or lose more?', 'open_text', 'Financial Management', 'CORE', 'SAS-010', 'RC-SAS-046', 3, 'Stage 1→10+'),
  ('S10-SAS-005', 'Is your growth funded by margin or by raising money?', 'open_text', 'Financial Management', 'CORE', 'SAS-010', 'RC-SAS-045', 3, 'Stage 1→10+'),
  ('S10-SAS-006', 'Do small changes take longer than they used to?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-011', 'RC-SAS-048', 2, 'Stage 1→10+'),
  ('S10-SAS-007', 'Do you have automated tests, and do they catch real problems?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-011', 'RC-SAS-047', 2, 'Stage 1→10+'),
  ('S10-SAS-008', 'Is there any part of the code your team avoids touching?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-011', 'RC-SAS-049', 3, 'Stage 1→10+'),
  ('S10-SAS-009', 'Has cleanup work ever been given actual time in a sprint?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-011', 'RC-SAS-050', 2, 'Stage 1→10+'),
  ('S10-SAS-010', 'Have security questions ever stalled or lost you a deal?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-012', 'RC-SAS-051', 2, 'Stage 1→10+'),
  ('S10-SAS-011', 'Do you have any security certification buyers recognise?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-012', 'RC-SAS-052', 2, 'Stage 1→10+'),
  ('S10-SAS-012', 'Who inside your company can open customer data?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-012', 'RC-SAS-053', 3, 'Stage 1→10+'),
  ('S10-SAS-013', 'Has anyone outside your team tested your system for weaknesses?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-012', 'RC-SAS-054', 3, 'Stage 1→10+'),
  ('S10-SAS-014', 'Have you signed terms you are not sure you can meet?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-012', 'RC-SAS-055', 3, 'Stage 1→10+'),
  ('S10-SAS-015', 'Are support tickets growing faster than your customer count?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-013', 'RC-SAS-056', 2, 'Stage 1→10+'),
  ('S10-SAS-016', 'What are the three questions you get asked over and over?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-013', 'RC-SAS-057', 2, 'Stage 1→10+'),
  ('S10-SAS-017', 'Can a customer find an answer without contacting you?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-013', 'RC-SAS-058', 2, 'Stage 1→10+'),
  ('S10-SAS-018', 'How much engineering time is going into support?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-013', 'RC-SAS-059', 3, 'Stage 1→10+'),
  ('S10-SAS-019', 'What share of your revenue comes from your top three accounts?', 'open_text', 'Sales & Revenue', 'CORE', 'SAS-014', 'RC-SAS-060', 2, 'Stage 1→10+'),
  ('S10-SAS-020', 'Is your roadmap being set by one large customer?', 'open_text', 'Strategy & Planning', 'CORE', 'SAS-014', 'RC-SAS-061', 3, 'Stage 1→10+'),
  ('S10-SAS-021', 'Are you building custom work to keep big accounts?', 'open_text', 'Operations & Systems', 'CORE', 'SAS-014', 'RC-SAS-062', 3, 'Stage 1→10+'),
  ('S10-SAS-022', 'Who sets the terms with your largest customer?', 'open_text', 'Sales & Revenue', 'CORE', 'SAS-014', 'RC-SAS-063', 2, 'Stage 1→10+'),
  ('S10-SAS-023', 'If a competitor copied your product, what would stop customers leaving?', 'open_text', 'Strategy & Planning', 'CORE', 'SAS-015', 'RC-SAS-064', 3, 'Stage 1→10+'),
  ('S10-SAS-024', 'Does anything about your product get better as you add customers?', 'open_text', 'Strategy & Planning', 'CORE', 'SAS-015', 'RC-SAS-065', 3, 'Stage 1→10+'),
  ('S10-SAS-025', 'How hard is it for a customer to switch away from you?', 'open_text', 'Strategy & Planning', 'CORE', 'SAS-015', 'RC-SAS-066', 3, 'Stage 1→10+')
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
  ('S0-SAS-001', 'icp'),
  ('S0-SAS-002', 'icp'),
  ('S0-SAS-003', 'icp'),
  ('S0-SAS-004', 'icp'),
  ('S0-SAS-005', 'icp'),
  ('S0-SAS-006', 'icp'),
  ('S0-SAS-007', 'icp'),
  ('S0-SAS-008', 'icp'),
  ('S0-SAS-009', 'icp'),
  ('S0-SAS-010', 'icp'),
  ('S0-SAS-011', 'willingness-to-pay'),
  ('S0-SAS-012', 'willingness-to-pay'),
  ('S0-SAS-013', 'willingness-to-pay'),
  ('S0-SAS-014', 'technical-quality'),
  ('S0-SAS-015', 'technical-quality'),
  ('S01-SAS-001', 'technical-quality'),
  ('S01-SAS-002', 'technical-quality'),
  ('S01-SAS-003', 'technical-quality'),
  ('S01-SAS-004', 'technical-quality'),
  ('S01-SAS-005', 'technical-quality'),
  ('S01-SAS-006', 'willingness-to-pay'),
  ('S01-SAS-007', 'willingness-to-pay'),
  ('S01-SAS-008', 'willingness-to-pay'),
  ('S01-SAS-009', 'willingness-to-pay'),
  ('S01-SAS-010', 'willingness-to-pay'),
  ('S01-SAS-011', 'technical-quality'),
  ('S01-SAS-012', 'technical-quality'),
  ('S01-SAS-013', 'technical-quality'),
  ('S01-SAS-014', 'technical-quality'),
  ('S01-SAS-015', 'technical-quality'),
  ('S01-SAS-016', 'willingness-to-pay'),
  ('S01-SAS-017', 'willingness-to-pay'),
  ('S01-SAS-018', 'willingness-to-pay'),
  ('S01-SAS-019', 'willingness-to-pay'),
  ('S01-SAS-020', 'technical-quality'),
  ('S10-SAS-001', 'willingness-to-pay'),
  ('S10-SAS-002', 'willingness-to-pay'),
  ('S10-SAS-003', 'willingness-to-pay'),
  ('S10-SAS-004', 'willingness-to-pay'),
  ('S10-SAS-005', 'willingness-to-pay'),
  ('S10-SAS-006', 'technical-quality'),
  ('S10-SAS-007', 'technical-quality'),
  ('S10-SAS-008', 'technical-quality'),
  ('S10-SAS-009', 'technical-quality'),
  ('S10-SAS-010', 'technical-quality'),
  ('S10-SAS-011', 'technical-quality'),
  ('S10-SAS-012', 'technical-quality'),
  ('S10-SAS-013', 'technical-quality'),
  ('S10-SAS-014', 'technical-quality'),
  ('S10-SAS-015', 'technical-quality'),
  ('S10-SAS-016', 'technical-quality'),
  ('S10-SAS-017', 'technical-quality'),
  ('S10-SAS-018', 'technical-quality'),
  ('S10-SAS-019', 'icp'),
  ('S10-SAS-020', 'icp'),
  ('S10-SAS-021', 'icp'),
  ('S10-SAS-022', 'icp'),
  ('S10-SAS-023', 'icp'),
  ('S10-SAS-024', 'icp'),
  ('S10-SAS-025', 'icp')
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
         '["saas"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-SAS-001', 'Ideation — SaaS Demand Validation', 'SAS-001', '["RC-SAS-001", "RC-SAS-002"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Stop building and talk to 15 people who have this problem.", "Ask how they handle it today and what it costs them.", "Only resume building if the problem is real and painful."]'::jsonb, '[{"name": "Talk Before You Build", "brief": "Confirming the problem exists before writing more code."}]'::jsonb),
  ('INT-SAS-002', 'Ideation — SaaS Demand Validation', 'SAS-001', '["RC-SAS-003", "RC-SAS-004"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Ask for money or a written commitment, not just opinions.", "Stop counting friends and family as validation.", "Treat a paid pilot as the only real signal."]'::jsonb, '[{"name": "Money Is the Only Signal", "brief": "Commitment from strangers, not encouragement from people who know you."}]'::jsonb),
  ('INT-SAS-003', 'Ideation — SaaS Demand Validation', 'SAS-001', '["RC-SAS-005"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Write down how the first 100 users will actually hear about you.", "Test one of those channels before launch.", "Budget time and money for distribution, not just build."]'::jsonb, '[{"name": "Plan Distribution Early", "brief": "Deciding how people will find you before the product is ready."}]'::jsonb),
  ('INT-SAS-004', 'Ideation — SaaS Buyer Clarity', 'SAS-002', '["RC-SAS-006", "RC-SAS-008"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Pick one user type and write it down in one sentence.", "Decide whether you sell to businesses or individuals.", "Say no to the other for now."]'::jsonb, '[{"name": "One User, One Market", "brief": "Narrowing to a single user type and a single market."}]'::jsonb),
  ('INT-SAS-005', 'Ideation — SaaS Buyer Clarity', 'SAS-002', '["RC-SAS-007", "RC-SAS-010"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Write down who uses it and who pays for it separately.", "Find out who approves that spending.", "Talk to 10 real buyers, not just users."]'::jsonb, '[{"name": "Separate User From Buyer", "brief": "Naming who uses it and who actually releases the money."}]'::jsonb),
  ('INT-SAS-006', 'Ideation — SaaS Buyer Clarity', 'SAS-002', '["RC-SAS-009"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Choose one company size to serve first.", "Write down why that size and not the others.", "Build the product and pricing for them alone."]'::jsonb, '[{"name": "Pick One Company Size", "brief": "Small and large companies buy completely differently."}]'::jsonb),
  ('INT-SAS-007', 'Ideation — SaaS Cost to Serve', 'SAS-003', '["RC-SAS-011", "RC-SAS-012"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Work out your monthly cost to serve one customer.", "Include hosting, storage and every paid service you rely on.", "Compare it against the price you plan to charge."]'::jsonb, '[{"name": "Cost to Serve One Account", "brief": "A real monthly cost per customer, including infrastructure."}]'::jsonb),
  ('INT-SAS-008', 'Ideation — SaaS Cost to Serve', 'SAS-003', '["RC-SAS-013", "RC-SAS-014"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Estimate the support hours one customer will need.", "Put a rupee value on that time.", "Add it to your cost per customer."]'::jsonb, '[{"name": "Support Is Not Free", "brief": "Costing the human time each customer consumes."}]'::jsonb),
  ('INT-SAS-009', 'Ideation — SaaS Data Responsibility', 'SAS-004', '["RC-SAS-015", "RC-SAS-017"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Decide where customer data will be stored and write it down.", "Put a basic privacy policy and terms in place before launch.", "Be clear about what you promise customers."]'::jsonb, '[{"name": "Decide Storage and Terms", "brief": "Settling where data lives and what you promise, before launch."}]'::jsonb),
  ('INT-SAS-010', 'Ideation — SaaS Data Responsibility', 'SAS-004', '["RC-SAS-016", "RC-SAS-018"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Limit who on your team can open customer data.", "Write down what you would do in the first 24 hours of a leak.", "Review both before you take your first real customer."]'::jsonb, '[{"name": "Access Limits and a Breach Plan", "brief": "Restricting internal access and deciding the response in advance."}]'::jsonb),
  ('INT-SAS-011', 'Validation to Traction — SaaS Activation', 'SAS-005', '["RC-SAS-020", "RC-SAS-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["Define the one action that means a user got value.", "Measure what share of signups reach it.", "Find the exact step where the rest drop off."]'::jsonb, '[{"name": "Define the First Value Moment", "brief": "One measurable action that marks a user as activated."}]'::jsonb),
  ('INT-SAS-012', 'Validation to Traction — SaaS Activation', 'SAS-005', '["RC-SAS-019", "RC-SAS-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["Build a guided path to that first value moment.", "Remove or defer every setup step that is not essential.", "Measure whether activation improves."]'::jsonb, '[{"name": "Shorten the Path to Value", "brief": "Guided onboarding with everything non essential removed."}]'::jsonb),
  ('INT-SAS-013', 'Validation to Traction — SaaS Activation', 'SAS-005', '["RC-SAS-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Stop reporting signups as your headline number.", "Report activated users instead.", "Make that the number the team watches."]'::jsonb, '[{"name": "Report Activation, Not Signups", "brief": "Changing the headline metric to the one that means something."}]'::jsonb),
  ('INT-SAS-014', 'Validation to Traction — SaaS Conversion', 'SAS-006', '["RC-SAS-024", "RC-SAS-025"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Check whether your free plan solves the whole problem.", "Move something people genuinely need behind the paywall.", "Keep free useful enough to attract, not enough to satisfy."]'::jsonb, '[{"name": "Fix the Free Line", "brief": "Free should attract, not fully satisfy."}]'::jsonb),
  ('INT-SAS-015', 'Validation to Traction — SaaS Conversion', 'SAS-006', '["RC-SAS-026", "RC-SAS-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Measure conversion from free to paid every month.", "Work out what free users cost you.", "Cap or tighten free if the cost outruns the benefit."]'::jsonb, '[{"name": "Measure the Free Base", "brief": "Knowing what free costs and what share of it converts."}]'::jsonb),
  ('INT-SAS-016', 'Validation to Traction — SaaS Conversion', 'SAS-006', '["RC-SAS-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Actively ask free users to upgrade at the right moment.", "Trigger the ask when they hit a limit or get value.", "Track how many respond."]'::jsonb, '[{"name": "Actually Ask", "brief": "Prompting the upgrade instead of waiting for it."}]'::jsonb),
  ('INT-SAS-017', 'Validation to Traction — SaaS Churn', 'SAS-007', '["RC-SAS-029", "RC-SAS-031"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Measure monthly churn and report it beside new sales.", "Record the real reason every time someone leaves.", "Fix the most common reason first."]'::jsonb, '[{"name": "Measure and Learn From Churn", "brief": "A monthly number plus a recorded reason for every departure."}]'::jsonb),
  ('INT-SAS-018', 'Validation to Traction — SaaS Churn', 'SAS-007', '["RC-SAS-030", "RC-SAS-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Define early warning signals such as falling usage or no logins.", "Review at risk accounts every month.", "Show each customer the value they have received."]'::jsonb, '[{"name": "Early Warning and Visible Value", "brief": "Spotting at risk accounts and making the value obvious."}]'::jsonb),
  ('INT-SAS-019', 'Validation to Traction — SaaS Churn', 'SAS-007', '["RC-SAS-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["Find one reason a user would open your product weekly.", "Build or highlight that.", "Watch whether repeat usage rises."]'::jsonb, '[{"name": "Make It a Habit", "brief": "Turning an occasional tool into part of the daily routine."}]'::jsonb),
  ('INT-SAS-020', 'Validation to Traction — SaaS Pricing', 'SAS-008', '["RC-SAS-034", "RC-SAS-035"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Ask customers what the product saves or earns them.", "Test a higher price with new customers only.", "Change the price and watch what happens to conversion."]'::jsonb, '[{"name": "Test the Price", "brief": "Treating price as an experiment rather than a fixed decision."}]'::jsonb),
  ('INT-SAS-021', 'Validation to Traction — SaaS Pricing', 'SAS-008', '["RC-SAS-036", "RC-SAS-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Build two or three tiers that match different needs.", "Tie the price to something that grows with customer value.", "Stop offering everyone the same thing."]'::jsonb, '[{"name": "Package by Value", "brief": "Tiers tied to what the customer actually gains."}]'::jsonb),
  ('INT-SAS-022', 'Validation to Traction — SaaS Pricing', 'SAS-008', '["RC-SAS-037"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Track how often and how deeply you discount.", "Work out what that costs you in a year.", "Set a floor nobody can go below without approval."]'::jsonb, '[{"name": "Put a Floor on Discounts", "brief": "Measuring discounting and setting a limit."}]'::jsonb),
  ('INT-SAS-023', 'Validation to Traction — SaaS Founder Led Sales', 'SAS-009', '["RC-SAS-039", "RC-SAS-040"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Write down exactly how you run a deal from first call to close.", "Train one other person against it.", "Let them run deals while you watch."]'::jsonb, '[{"name": "Write the Sales Process", "brief": "Documenting how deals are won so someone else can run them."}]'::jsonb),
  ('INT-SAS-024', 'Validation to Traction — SaaS Founder Led Sales', 'SAS-009', '["RC-SAS-041"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Record why every deal was won or lost.", "Review the pattern monthly.", "Feed it back into the process and the product."]'::jsonb, '[{"name": "Win Loss Record", "brief": "Learning from outcomes instead of repeating them."}]'::jsonb),
  ('INT-SAS-025', 'Growth to Maturity — SaaS Unit Economics', 'SAS-010', '["RC-SAS-042", "RC-SAS-043", "RC-SAS-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Calculate what you spend to win one customer.", "Calculate what an average customer pays before leaving.", "Work out the months to repay acquisition cost."]'::jsonb, '[{"name": "Know Your Three Numbers", "brief": "Acquisition cost, lifetime value and payback period."}]'::jsonb),
  ('INT-SAS-026', 'Growth to Maturity — SaaS Unit Economics', 'SAS-010', '["RC-SAS-045", "RC-SAS-046"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Check whether spending more to grow increases or decreases losses.", "Fix the economics before scaling spend.", "Stop treating fundraising as a substitute for margin."]'::jsonb, '[{"name": "Fix Economics Before Scaling", "brief": "Not pouring money into a model that loses more as it grows."}]'::jsonb),
  ('INT-SAS-027', 'Growth to Maturity — SaaS Technical Debt', 'SAS-011', '["RC-SAS-047", "RC-SAS-048"]'::jsonb, '[5, 6, 7]'::jsonb, 'Engineering', '["Add automated tests around the areas that break most.", "Measure how long a typical change takes.", "Track whether that time improves."]'::jsonb, '[{"name": "Tests Around the Fragile Parts", "brief": "Coverage where breakage actually happens, not everywhere."}]'::jsonb),
  ('INT-SAS-028', 'Growth to Maturity — SaaS Technical Debt', 'SAS-011', '["RC-SAS-049", "RC-SAS-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Engineering', '["List the areas the team avoids touching.", "Give cleanup a fixed share of every sprint.", "Fix the worst area first rather than planning a rewrite."]'::jsonb, '[{"name": "Budget Cleanup Every Sprint", "brief": "A standing share of capacity instead of a rewrite that never comes."}]'::jsonb),
  ('INT-SAS-029', 'Growth to Maturity — SaaS Security Posture', 'SAS-012', '["RC-SAS-051", "RC-SAS-052"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Collect the security questionnaires buyers have sent you.", "Find the common gaps and close them.", "Pursue the certification your buyers keep asking for."]'::jsonb, '[{"name": "Close the Security Gaps", "brief": "Using buyer questionnaires as the roadmap for what to fix."}]'::jsonb),
  ('INT-SAS-030', 'Growth to Maturity — SaaS Security Posture', 'SAS-012', '["RC-SAS-053", "RC-SAS-054", "RC-SAS-055"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Put formal access controls around customer data.", "Get an independent review or test of your system.", "Check every contractual commitment before signing it."]'::jsonb, '[{"name": "Controls, Testing and Contracts", "brief": "Formal access control, outside testing and terms you can honour."}]'::jsonb),
  ('INT-SAS-031', 'Growth to Maturity — SaaS Support Load', 'SAS-013', '["RC-SAS-056", "RC-SAS-057", "RC-SAS-058"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["List the questions you answer most often.", "Fix the product or write help content for each.", "Measure whether tickets per customer fall."]'::jsonb, '[{"name": "Fix the Repeat Questions", "brief": "Removing the causes of recurring support instead of answering again."}]'::jsonb),
  ('INT-SAS-032', 'Growth to Maturity — SaaS Support Load', 'SAS-013', '["RC-SAS-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Measure how much engineering time goes into support.", "Put a support owner between customers and engineers.", "Protect build capacity with a cap."]'::jsonb, '[{"name": "Protect Engineering Time", "brief": "A support layer so build capacity is not consumed by tickets."}]'::jsonb),
  ('INT-SAS-033', 'Growth to Maturity — SaaS Revenue Concentration', 'SAS-014', '["RC-SAS-060", "RC-SAS-063"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Calculate the revenue share of your top three accounts.", "Set a ceiling and build a pipeline of smaller customers.", "Review the share every quarter."]'::jsonb, '[{"name": "Cap Revenue Concentration", "brief": "Measuring dependence and deliberately building beyond it."}]'::jsonb),
  ('INT-SAS-034', 'Growth to Maturity — SaaS Revenue Concentration', 'SAS-014', '["RC-SAS-061", "RC-SAS-062"]'::jsonb, '[5, 6, 7]'::jsonb, 'Product Design', '["Separate what one customer wants from what the market needs.", "Build custom work only when it is paid and reusable.", "Take the roadmap back."]'::jsonb, '[{"name": "Take the Roadmap Back", "brief": "Building for the market rather than for one loud account."}]'::jsonb),
  ('INT-SAS-035', 'Growth to Maturity — SaaS Defensibility', 'SAS-015', '["RC-SAS-064", "RC-SAS-065"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Identify one thing that could get better as you add customers.", "Invest deliberately in that, whether data, network or integrations.", "Stop relying on features alone."]'::jsonb, '[{"name": "Build Something That Compounds", "brief": "An advantage that grows with scale instead of features that copy."}]'::jsonb),
  ('INT-SAS-036', 'Growth to Maturity — SaaS Defensibility', 'SAS-015', '["RC-SAS-066", "RC-SAS-067"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Work out what it would cost a customer to leave you.", "Increase that honestly through integrations, data and workflow depth.", "Compete on that instead of on price."]'::jsonb, '[{"name": "Raise the Cost of Leaving", "brief": "Depth in the customer workflow rather than a lower price."}]'::jsonb)
  ) AS t(intervention_code, section, problem_code, root_cause_ids, stage_relevance,
         capability_domain, immediate_next_steps, recommended_frameworks)
  JOIN new_problems np ON np.problem_code = t.problem_code
  RETURNING intervention_id
)
SELECT
  (SELECT COUNT(*) FROM new_problems)     AS problems_inserted,      -- expect 15
  (SELECT COUNT(*) FROM new_root_causes)  AS root_causes_inserted,   -- expect 67
  (SELECT COUNT(*) FROM new_questions)    AS questions_inserted,     -- expect 60
  (SELECT COUNT(*) FROM new_tag_links)    AS tag_links_inserted,     -- expect 60
  (SELECT COUNT(*) FROM new_interventions) AS interventions_inserted;-- expect 36

-- ============================================================================
-- After running, the single result row above must read:  15 | 67 | 60 | 60 | 36
-- If any number differs, something did not link -- roll back and check.
-- ============================================================================"""),
        ('Logistics & Supply Chain', 'logistics', 'LOG', {'problems_inserted': 15, 'root_causes_inserted': 66, 'questions_inserted': 60, 'tags_inserted': 60, 'interventions_inserted': 34}, r"""-- ============================================================================
-- Ally :: Industry seed -- LOGISTICS & SUPPLY CHAIN (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: logistics
--
-- COMPLETION NOTE: this industry had already been partially seeded by an
-- earlier session (problems, most root causes and all 60 questions existed).
-- That earlier pass was missing 4 root causes, all Stage 1->10+ interventions
-- (0 of 12), 2 Stage 0->1 interventions, and every tag link (0 of 60). This
-- file is the completed, verified whole: the original content plus what was
-- added to reach the standard 66/60/34/60 shape, checksummed end to end.
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (LOG-001, RC-LOG-014, S0-LOG-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (service reliability, shipment visibility, fleet
--            cost, working capital, driver dependency) starts at Stage 0->1;
--            customer concentration, fleet risk, warehouse scaling, recurring
--            compliance, the technology shift and rate volatility at
--            Stage 1->10+.
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
  ('LOG-001', 'Registrations and Permits Not Checked', 'Moving goods for others requires specific registrations and permits that have not been looked into.', 'Idea & Validation', 'Logistics Registration Basics', 'external', 3, 5, 9, '["No idea which registrations are needed", "Assuming a vehicle and a driver are enough to start", "Permits for different states or goods not checked", "No plan for who handles compliance", "Insurance obligations not understood"]'::jsonb, '["logistics"]'::jsonb),
  ('LOG-002', 'Real Cost Per Delivery Never Worked Out', 'Fuel, driver time, vehicle wear, empty return legs and overhead have not been built into a true cost per delivery.', 'Idea & Validation', 'Logistics Cost Reality', 'external', 4, 5, 9, '["Only fuel counted as cost", "Driver time and vehicle wear ignored", "Empty return legs not costed", "Overhead not spread across deliveries", "Price set by looking at competitors only"]'::jsonb, '["logistics"]'::jsonb),
  ('LOG-003', 'No Clear Customer for the Service', 'Retail shippers, manufacturers and individual senders need completely different logistics services, and none has been chosen.', 'Idea & Validation', 'Logistics Customer Clarity', 'external', 2, 4, 8, '["Target customer described as everyone", "Same service pitched to very different shippers", "Route and volume assumptions not tested", "No conversation with a real shipper yet", "Assuming any cargo can be handled the same way"]'::jsonb, '["logistics"]'::jsonb),
  ('LOG-004', 'Capacity and Demand Not Matched', 'Vehicles, drivers and warehouse space are being planned or bought without knowing the volume that will actually need moving.', 'Idea & Validation', 'Logistics Capacity Planning', 'external', 3, 5, 9, '["Fleet size chosen without confirmed volume", "No idea how demand varies through the week or year", "Assuming utilisation will simply work itself out", "No plan for slow periods", "Capital committed before volume is confirmed"]'::jsonb, '["logistics"]'::jsonb),
  ('LOG-005', 'Late and Damaged Deliveries Losing Customers', 'Deliveries arrive late or damaged often enough that customers are leaving, and the causes are not being tracked.', 'Operations & Systems', 'Logistics Service Reliability', 'external', 3, 6, 9, '["On time rate not measured", "Damage rate not measured", "Causes of delay not investigated", "No process when something goes wrong", "Customers leaving after a bad delivery"]'::jsonb, '["logistics"]'::jsonb),
  ('LOG-006', 'No Visibility Once a Shipment Leaves', 'Once a vehicle departs, nobody can say where a shipment is until it arrives or fails to.', 'Operations & Systems', 'Logistics Shipment Visibility', 'external', 3, 6, 9, '["No tracking once a vehicle leaves", "Customer status updates given by guesswork", "Problems discovered only on arrival", "No record of what happened during transit", "Drivers unreachable for hours at a time"]'::jsonb, '["logistics"]'::jsonb),
  ('LOG-007', 'Fuel and Maintenance Costs Not Controlled', 'Fuel use and vehicle upkeep vary widely between drivers and vehicles, and nothing is done to bring them under control.', 'Financial Management', 'Logistics Fleet Cost Control', 'external', 4, 6, 9, '["Fuel use varying widely between drivers", "Maintenance done only after breakdown", "No comparison of cost between vehicles", "Fuel theft or waste not checked", "Cost per kilometre not tracked"]'::jsonb, '["logistics"]'::jsonb),
  ('LOG-008', 'Payment Terms Squeezing Cash', 'Shippers pay on long credit while fuel, drivers and vehicle costs must be paid immediately, straining cash constantly.', 'Financial Management', 'Logistics Working Capital', 'external', 4, 6, 9, '["Long credit given to shippers", "Fuel and driver costs paid immediately", "No credit line for the gap", "Growth making cash position worse", "Cycle length never measured"]'::jsonb, '["logistics"]'::jsonb),
  ('LOG-009', 'Everything Depends on a Few Drivers', 'Reliable delivery rests on a handful of experienced drivers, and losing any one of them disrupts operations badly.', 'Team & Leadership', 'Logistics Driver Dependency', 'external', 5, 6, 9, '["Key routes run by specific drivers only", "High driver turnover", "No standard training for new drivers", "Customer relationships tied to individual drivers", "No backup when a driver is unavailable"]'::jsonb, '["logistics"]'::jsonb),
  ('LOG-010', 'Revenue Concentrated in a Few Large Shippers', 'A handful of shippers account for most volume, so they set rates and their loss would be severe.', 'Sales & Revenue', 'Logistics Customer Concentration', 'external', 4, 7, 10, '["Most volume from a few shippers", "Rates dictated by the largest shipper", "Payment terms set by the shipper", "No pipeline of smaller customers", "Losing one shipper would threaten the business"]'::jsonb, '["logistics"]'::jsonb),
  ('LOG-011', 'Breakdowns and Accidents Stopping Operations', 'Vehicle failures and accidents disrupt schedules without warning, and there is no systematic way of reducing them.', 'Operations & Systems', 'Logistics Fleet Risk', 'external', 3, 7, 10, '["Breakdowns causing missed deliveries", "No preventive maintenance programme", "Accident history not tracked or analysed", "Insurance claims process ad hoc", "Downtime cost not measured"]'::jsonb, '["logistics"]'::jsonb),
  ('LOG-012', 'Warehouse and Handling Errors Multiplying With Volume', 'As throughput grows, picking, sorting and handling mistakes rise faster than volume, and nobody has systemised the process.', 'Operations & Systems', 'Logistics Warehouse Operations', 'external', 3, 6, 9, '["Error rate rising with volume", "No standard picking or sorting process", "Inventory counts not reliable", "Space utilisation not planned", "Peak periods overwhelming the operation"]'::jsonb, '["logistics"]'::jsonb),
  ('LOG-013', 'Regulatory and Safety Compliance Now a Constant Burden', 'Driver hours, vehicle fitness, permits and safety obligations recur constantly, and at this scale they cannot run on memory.', 'Operations & Systems', 'Logistics Compliance Operations', 'external', 3, 7, 10, '["Permit and fitness renewals tracked from memory", "Driver hours not systematically recorded", "Safety incidents not logged", "No single compliance calendar", "One person holding all the knowledge"]'::jsonb, '["logistics"]'::jsonb),
  ('LOG-014', 'Technology Changing What Shippers Expect', 'Shippers increasingly expect real time tracking, automated booking and data integration that the business cannot yet offer.', 'Strategy & Planning', 'Logistics Technology Shift', 'external', 2, 6, 10, '["Shippers asking for real time tracking", "Deals lost for lack of system integration", "Booking still handled manually", "Competitors offering data shippers now expect", "No investment plan for logistics technology"]'::jsonb, '["logistics"]'::jsonb),
  ('LOG-015', 'Fuel and Freight Rate Swings Destroying Margin', 'Fuel prices and freight rates move sharply, and contracts fixed in advance leave no way to pass the change on.', 'Financial Management', 'Logistics Rate Volatility', 'external', 4, 6, 10, '["Fuel prices moving sharply after a rate is fixed", "No fuel surcharge or adjustment clause", "Margin per route varying wildly", "Long contracts locking in stale rates", "No hedging or pricing review mechanism"]'::jsonb, '["logistics"]'::jsonb)
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
         t.primary_stage_group, '["logistics"]'::jsonb, z.v
  FROM (VALUES
  ('RC-LOG-001', 'Required Registrations Unknown', 'Which registrations are needed to move goods for others has not been established.', 'LOG-001', 'external', 'Knowledge', 0.73, 'Stage 0'),
  ('RC-LOG-002', 'Assuming a Vehicle and Driver Are Enough', 'Believing no formal registration is needed to start.', 'LOG-001', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-LOG-003', 'State and Goods Specific Permits Not Checked', 'Permits that vary by state or type of cargo have not been looked into.', 'LOG-001', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-LOG-004', 'No Owner for Compliance', 'Nobody has been made responsible for registrations and renewals.', 'LOG-001', 'external', 'Operational', 0.64, 'Stage 0'),
  ('RC-LOG-005', 'Insurance Obligations Not Understood', 'What cover is legally required has not been checked.', 'LOG-001', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-LOG-006', 'Only Fuel Counted as Cost', 'The cost of a delivery is taken as fuel alone.', 'LOG-002', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-LOG-007', 'Driver Time and Vehicle Wear Ignored', 'Labour and depreciation are missing from the numbers.', 'LOG-002', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-LOG-008', 'Empty Return Legs Not Costed', 'The cost of the vehicle coming back empty is not counted.', 'LOG-002', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-LOG-009', 'Overhead Not Spread Across Deliveries', 'Office, insurance and admin costs are not loaded onto each trip.', 'LOG-002', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-LOG-010', 'Price Set by Looking at Competitors', 'Pricing copies others without knowing own cost.', 'LOG-002', 'external', 'Behavioural', 0.67, 'Stage 0'),
  ('RC-LOG-011', 'Target Customer Described as Everyone', 'No specific shipper type has been chosen to serve.', 'LOG-003', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-LOG-012', 'Same Service Pitched to Different Shippers', 'Retail, manufacturing and individual senders are treated identically.', 'LOG-003', 'external', 'Strategic', 0.68, 'Stage 0'),
  ('RC-LOG-013', 'Route and Volume Assumptions Not Tested', 'Expected lanes and quantities have not been checked against reality.', 'LOG-003', 'external', 'Knowledge', 0.67, 'Stage 0'),
  ('RC-LOG-014', 'No Conversation With a Real Shipper', 'Nobody who would actually book has been spoken to.', 'LOG-003', 'external', 'Behavioural', 0.66, 'Stage 0'),
  ('RC-LOG-015', 'Fleet Size Chosen Without Confirmed Volume', 'Vehicles were bought before demand was verified.', 'LOG-004', 'external', 'Strategic', 0.72, 'Stage 0'),
  ('RC-LOG-016', 'Demand Variation Through Week or Year Unknown', 'How volume swings has not been studied.', 'LOG-004', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-LOG-017', 'Assuming Utilisation Will Work Itself Out', 'Believing capacity and demand will match without planning.', 'LOG-004', 'external', 'Psychological', 0.68, 'Stage 0'),
  ('RC-LOG-018', 'No Plan for Slow Periods', 'Nothing has been decided for quiet weeks or seasons.', 'LOG-004', 'external', 'Strategic', 0.67, 'Stage 0'),
  ('RC-LOG-019', 'On Time Rate Not Measured', 'How often deliveries arrive on schedule is not tracked.', 'LOG-005', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-LOG-020', 'Damage Rate Not Measured', 'How often goods arrive damaged is not tracked.', 'LOG-005', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-LOG-021', 'Causes of Delay Not Investigated', 'Late deliveries are noted but never traced to a cause.', 'LOG-005', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-LOG-022', 'No Process When Something Goes Wrong', 'There is no defined response to a failed delivery.', 'LOG-005', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-LOG-023', 'No Tracking Once a Vehicle Leaves', 'Nothing shows where a shipment is during transit.', 'LOG-006', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-LOG-024', 'Customer Updates Given by Guesswork', 'Status told to customers is not based on real information.', 'LOG-006', 'external', 'Behavioural', 0.71, 'Stage 0→1'),
  ('RC-LOG-025', 'Problems Discovered Only on Arrival', 'Issues surface too late to do anything about them.', 'LOG-006', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-LOG-026', 'Drivers Unreachable for Hours', 'Communication with vehicles in transit is unreliable.', 'LOG-006', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-LOG-027', 'Fuel Use Varying Between Drivers', 'Consumption differs widely for no explained reason.', 'LOG-007', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-LOG-028', 'Maintenance Only After Breakdown', 'Vehicles are serviced when they fail, not on a schedule.', 'LOG-007', 'external', 'Behavioural', 0.71, 'Stage 0→1'),
  ('RC-LOG-029', 'No Comparison of Cost Between Vehicles', 'Nobody checks which vehicles cost more to run.', 'LOG-007', 'external', 'Knowledge', 0.69, 'Stage 0→1'),
  ('RC-LOG-030', 'Cost Per Kilometre Not Tracked', 'The basic unit of fleet cost is not measured.', 'LOG-007', 'external', 'Knowledge', 0.70, 'Stage 0→1'),
  ('RC-LOG-031', 'Long Credit Given to Shippers', 'Customers are allowed to pay well after delivery.', 'LOG-008', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-LOG-032', 'Fuel and Driver Costs Paid Immediately', 'Running costs must be settled with no delay.', 'LOG-008', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-LOG-033', 'No Credit Line for the Gap', 'Nothing has been arranged to bridge the cycle.', 'LOG-008', 'external', 'Strategic', 0.70, 'Stage 0→1'),
  ('RC-LOG-034', 'Cycle Length Never Measured', 'How many days cash is out has not been calculated.', 'LOG-008', 'external', 'Knowledge', 0.68, 'Stage 0→1'),
  ('RC-LOG-035', 'Key Routes Run by Specific Drivers Only', 'Certain routes work only because one driver knows them.', 'LOG-009', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-LOG-036', 'High Driver Turnover', 'Drivers leave frequently.', 'LOG-009', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-LOG-037', 'No Standard Training for New Drivers', 'New drivers learn informally with no defined process.', 'LOG-009', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-LOG-038', 'Customer Relationships Tied to Individual Drivers', 'Customers trust the driver, not the company.', 'LOG-009', 'external', 'Strategic', 0.68, 'Stage 0→1'),
  ('RC-LOG-039', 'Most Volume From a Few Shippers', 'A handful of customers carry most of the business.', 'LOG-010', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-LOG-040', 'Rates Dictated by the Largest Shipper', 'The dominant customer sets what can be charged.', 'LOG-010', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-LOG-041', 'Payment Terms Set by the Shipper', 'Credit periods are imposed rather than negotiated.', 'LOG-010', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-LOG-042', 'No Pipeline of Smaller Customers', 'Nothing is being built that could replace a lost shipper.', 'LOG-010', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-LOG-043', 'No Preventive Maintenance Programme', 'Vehicles are not serviced ahead of likely failure.', 'LOG-011', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-LOG-044', 'Accident History Not Tracked', 'Incidents are not recorded or analysed for patterns.', 'LOG-011', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-LOG-045', 'Insurance Claims Process Ad Hoc', 'Claims are handled differently each time with no set process.', 'LOG-011', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-LOG-046', 'Downtime Cost Not Measured', 'What a breakdown actually costs is unknown.', 'LOG-011', 'external', 'Knowledge', 0.70, 'Stage 1→10+'),
  ('RC-LOG-047', 'No Standard Picking or Sorting Process', 'Warehouse work is not done a consistent way.', 'LOG-012', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-LOG-048', 'Inventory Counts Not Reliable', 'Stock records do not match what is actually there.', 'LOG-012', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-LOG-049', 'Space Utilisation Not Planned', 'Warehouse layout is not designed for the volume moving through it.', 'LOG-012', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-LOG-050', 'Peak Periods Overwhelming the Operation', 'The system that works normally breaks down at peak.', 'LOG-012', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-LOG-051', 'Permit and Fitness Renewals Tracked From Memory', 'Expiry dates live in memory rather than a system.', 'LOG-013', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-LOG-052', 'Driver Hours Not Systematically Recorded', 'Working hours are not captured in a reliable way.', 'LOG-013', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-LOG-053', 'Safety Incidents Not Logged', 'Accidents and near misses are not written down anywhere.', 'LOG-013', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-LOG-054', 'One Person Holding All the Knowledge', 'Compliance capability sits with a single individual.', 'LOG-013', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-LOG-055', 'Shippers Asking for Real Time Tracking', 'Customers expect visibility the business cannot provide.', 'LOG-014', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-LOG-056', 'Booking Still Handled Manually', 'No system exists for shippers to book without a phone call.', 'LOG-014', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-LOG-057', 'Deals Lost for Lack of Integration', 'Buyers choose competitors who connect to their systems.', 'LOG-014', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-LOG-058', 'No Investment Plan for Technology', 'Nothing has been budgeted to close the gap.', 'LOG-014', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-LOG-059', 'Fuel Prices Moving After Rate Is Fixed', 'Input cost changes after the price is committed.', 'LOG-015', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-LOG-060', 'No Fuel Surcharge or Adjustment Clause', 'Nothing in contracts allows passing on a fuel change.', 'LOG-015', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-LOG-061', 'Long Contracts Locking in Stale Rates', 'Agreements run longer than rates stay accurate.', 'LOG-015', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-LOG-062', 'Margin Per Route Varying Wildly', 'Profit on individual routes is unpredictable.', 'LOG-015', 'external', 'Operational', 0.68, 'Stage 1→10+'),
  ('RC-LOG-063', 'No Alert When a Shipment Deviates From Plan', 'Nobody is told when a route or timing goes off track until it is too late.', 'LOG-006', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-LOG-064', 'Growth Worsening the Cash Position', 'Each new booking deepens the cash strain rather than easing it.', 'LOG-008', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-LOG-065', 'Long Term Contracts Locking in the Dominant Shipper', 'Multi year terms with the largest shipper prevent renegotiation even as leverage shifts.', 'LOG-010', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-LOG-066', 'No Single Compliance Calendar', 'Renewals, filings and expiries are scattered rather than tracked in one place.', 'LOG-013', 'external', 'Operational', 0.70, 'Stage 1→10+')
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
         '["logistics"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-LOG-001', 'Do you know which registrations you need to move goods for others?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-001', 'RC-LOG-001', 1, 'Stage 0'),
  ('S0-LOG-002', 'Do you think a vehicle and a driver are enough to legally start?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-001', 'RC-LOG-002', 1, 'Stage 0'),
  ('S0-LOG-003', 'Have you checked permits for the states or goods you plan to carry?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-001', 'RC-LOG-003', 2, 'Stage 0'),
  ('S0-LOG-004', 'Who would handle your registrations and renewals?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-001', 'RC-LOG-004', 2, 'Stage 0'),
  ('S0-LOG-005', 'Do you know what insurance you are required to carry?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-001', 'RC-LOG-005', 2, 'Stage 0'),
  ('S0-LOG-006', 'What does one delivery actually cost you, beyond fuel?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-002', 'RC-LOG-006', 1, 'Stage 0'),
  ('S0-LOG-007', 'Have you counted driver time and vehicle wear in that cost?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-002', 'RC-LOG-007', 2, 'Stage 0'),
  ('S0-LOG-008', 'Have you counted the cost of the return trip when it is empty?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-002', 'RC-LOG-008', 2, 'Stage 0'),
  ('S0-LOG-009', 'Have you spread your office and admin costs across deliveries?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-002', 'RC-LOG-009', 2, 'Stage 0'),
  ('S0-LOG-010', 'Did you set your price from your own cost or from competitors?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-002', 'RC-LOG-010', 2, 'Stage 0'),
  ('S0-LOG-011', 'Who exactly is this service for, retail shippers, manufacturers or individuals?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-003', 'RC-LOG-011', 1, 'Stage 0'),
  ('S0-LOG-012', 'Have you tested your assumed routes and volumes against a real shipper?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-003', 'RC-LOG-013', 2, 'Stage 0'),
  ('S0-LOG-013', 'Have you spoken to at least one real shipper who would actually book you?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-003', 'RC-LOG-014', 2, 'Stage 0'),
  ('S0-LOG-014', 'Did you buy vehicles before or after confirming the volume?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-004', 'RC-LOG-015', 1, 'Stage 0'),
  ('S0-LOG-015', 'Do you know how demand moves through the week or the year?', 'open_text', 'Idea & Validation', 'CORE', 'LOG-004', 'RC-LOG-016', 2, 'Stage 0'),
  ('S01-LOG-001', 'Out of 100 deliveries, how many arrive on time?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-005', 'RC-LOG-019', 2, 'Stage 0→1'),
  ('S01-LOG-002', 'Out of 100 deliveries, how many arrive damaged?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-005', 'RC-LOG-020', 2, 'Stage 0→1'),
  ('S01-LOG-003', 'When a delivery is late, does anyone find out why?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-005', 'RC-LOG-021', 2, 'Stage 0→1'),
  ('S01-LOG-004', 'What happens when a delivery goes wrong?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-005', 'RC-LOG-022', 2, 'Stage 0→1'),
  ('S01-LOG-005', 'Can you say where a shipment is right now, mid transit?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-006', 'RC-LOG-023', 2, 'Stage 0→1'),
  ('S01-LOG-006', 'When you update a customer on status, is it based on real information?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-006', 'RC-LOG-024', 2, 'Stage 0→1'),
  ('S01-LOG-007', 'Do problems only surface when the vehicle arrives?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-006', 'RC-LOG-025', 2, 'Stage 0→1'),
  ('S01-LOG-008', 'Can you reach a driver reliably during a trip?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-006', 'RC-LOG-026', 2, 'Stage 0→1'),
  ('S01-LOG-009', 'Does fuel use differ a lot between your drivers?', 'open_text', 'Financial Management', 'CORE', 'LOG-007', 'RC-LOG-027', 2, 'Stage 0→1'),
  ('S01-LOG-010', 'Do you service vehicles on a schedule or after they break down?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-007', 'RC-LOG-028', 2, 'Stage 0→1'),
  ('S01-LOG-011', 'Do you know your cost per kilometre?', 'open_text', 'Financial Management', 'CORE', 'LOG-007', 'RC-LOG-030', 2, 'Stage 0→1'),
  ('S01-LOG-012', 'Have you ever compared running cost between your vehicles?', 'open_text', 'Financial Management', 'CORE', 'LOG-007', 'RC-LOG-029', 3, 'Stage 0→1'),
  ('S01-LOG-013', 'How long do shippers take to pay you?', 'open_text', 'Financial Management', 'CORE', 'LOG-008', 'RC-LOG-031', 2, 'Stage 0→1'),
  ('S01-LOG-014', 'How quickly must you pay for fuel and drivers?', 'open_text', 'Financial Management', 'CORE', 'LOG-008', 'RC-LOG-032', 2, 'Stage 0→1'),
  ('S01-LOG-015', 'Do you have a credit line covering that gap?', 'open_text', 'Financial Management', 'CORE', 'LOG-008', 'RC-LOG-033', 2, 'Stage 0→1'),
  ('S01-LOG-016', 'Has anyone measured how many days your cash is tied up?', 'open_text', 'Financial Management', 'CORE', 'LOG-008', 'RC-LOG-034', 3, 'Stage 0→1'),
  ('S01-LOG-017', 'Are there routes that only work because one driver knows them?', 'open_text', 'Team & Leadership', 'CORE', 'LOG-009', 'RC-LOG-035', 2, 'Stage 0→1'),
  ('S01-LOG-018', 'How many drivers have left in the last year?', 'open_text', 'Team & Leadership', 'CORE', 'LOG-009', 'RC-LOG-036', 2, 'Stage 0→1'),
  ('S01-LOG-019', 'How does a new driver learn your routes and standards?', 'open_text', 'Team & Leadership', 'CORE', 'LOG-009', 'RC-LOG-037', 2, 'Stage 0→1'),
  ('S01-LOG-020', 'Do customers trust your company, or trust a specific driver?', 'open_text', 'Sales & Revenue', 'CORE', 'LOG-009', 'RC-LOG-038', 3, 'Stage 0→1'),
  ('S10-LOG-001', 'What share of your volume comes from your top two or three shippers?', 'open_text', 'Sales & Revenue', 'CORE', 'LOG-010', 'RC-LOG-039', 2, 'Stage 1→10+'),
  ('S10-LOG-002', 'Who sets your rates, you or your biggest shipper?', 'open_text', 'Sales & Revenue', 'CORE', 'LOG-010', 'RC-LOG-040', 2, 'Stage 1→10+'),
  ('S10-LOG-003', 'Who decides your payment terms?', 'open_text', 'Financial Management', 'CORE', 'LOG-010', 'RC-LOG-041', 2, 'Stage 1→10+'),
  ('S10-LOG-004', 'If your largest shipper left, how long could you continue?', 'open_text', 'Strategy & Planning', 'CORE', 'LOG-010', 'RC-LOG-042', 3, 'Stage 1→10+'),
  ('S10-LOG-005', 'Do you service vehicles ahead of likely failure, or after it happens?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-011', 'RC-LOG-043', 2, 'Stage 1→10+'),
  ('S10-LOG-006', 'Do you track accident history for patterns?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-011', 'RC-LOG-044', 3, 'Stage 1→10+'),
  ('S10-LOG-007', 'Is there a set process for handling an insurance claim?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-011', 'RC-LOG-045', 2, 'Stage 1→10+'),
  ('S10-LOG-008', 'What does an hour of vehicle downtime actually cost you?', 'open_text', 'Financial Management', 'CORE', 'LOG-011', 'RC-LOG-046', 3, 'Stage 1→10+'),
  ('S10-LOG-009', 'Is there a standard way your team picks and sorts goods?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-012', 'RC-LOG-047', 2, 'Stage 1→10+'),
  ('S10-LOG-010', 'Do your inventory counts match what is actually in the warehouse?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-012', 'RC-LOG-048', 3, 'Stage 1→10+'),
  ('S10-LOG-011', 'Was your warehouse layout planned for the volume you now move?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-012', 'RC-LOG-049', 2, 'Stage 1→10+'),
  ('S10-LOG-012', 'Does the operation break down during peak periods?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-012', 'RC-LOG-050', 2, 'Stage 1→10+'),
  ('S10-LOG-013', 'Can you list every permit and its expiry date?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-013', 'RC-LOG-051', 2, 'Stage 1→10+'),
  ('S10-LOG-014', 'Are driver hours recorded reliably?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-013', 'RC-LOG-052', 3, 'Stage 1→10+'),
  ('S10-LOG-015', 'Where do you log safety incidents?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-013', 'RC-LOG-053', 2, 'Stage 1→10+'),
  ('S10-LOG-016', 'If the person who tracks compliance left, what would happen?', 'open_text', 'Team & Leadership', 'CORE', 'LOG-013', 'RC-LOG-054', 3, 'Stage 1→10+'),
  ('S10-LOG-017', 'Are shippers asking for tracking or data you cannot yet provide?', 'open_text', 'Sales & Revenue', 'CORE', 'LOG-014', 'RC-LOG-055', 2, 'Stage 1→10+'),
  ('S10-LOG-018', 'Can a shipper book with you without a phone call?', 'open_text', 'Operations & Systems', 'CORE', 'LOG-014', 'RC-LOG-056', 2, 'Stage 1→10+'),
  ('S10-LOG-019', 'Have you lost a deal because you could not integrate with a shipper system?', 'open_text', 'Sales & Revenue', 'CORE', 'LOG-014', 'RC-LOG-057', 3, 'Stage 1→10+'),
  ('S10-LOG-020', 'Is there a budget for closing your technology gap?', 'open_text', 'Strategy & Planning', 'CORE', 'LOG-014', 'RC-LOG-058', 2, 'Stage 1→10+'),
  ('S10-LOG-021', 'Have fuel prices moved after you fixed a rate with a shipper?', 'open_text', 'Financial Management', 'CORE', 'LOG-015', 'RC-LOG-059', 2, 'Stage 1→10+'),
  ('S10-LOG-022', 'Do your contracts let you adjust price when fuel moves?', 'open_text', 'Financial Management', 'CORE', 'LOG-015', 'RC-LOG-060', 3, 'Stage 1→10+'),
  ('S10-LOG-023', 'How long are your shipper contracts fixed for?', 'open_text', 'Financial Management', 'CORE', 'LOG-015', 'RC-LOG-061', 2, 'Stage 1→10+'),
  ('S10-LOG-024', 'How much does your margin vary from one route to the next?', 'open_text', 'Financial Management', 'CORE', 'LOG-015', 'RC-LOG-062', 2, 'Stage 1→10+'),
  ('S10-LOG-025', 'Do you review contract rates on a fixed schedule?', 'open_text', 'Financial Management', 'CORE', 'LOG-015', 'RC-LOG-061', 3, 'Stage 1→10+')
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
  ('S0-LOG-001', 'technical-quality'),
  ('S0-LOG-002', 'technical-quality'),
  ('S0-LOG-003', 'technical-quality'),
  ('S0-LOG-004', 'technical-quality'),
  ('S0-LOG-005', 'technical-quality'),
  ('S0-LOG-006', 'willingness-to-pay'),
  ('S0-LOG-007', 'willingness-to-pay'),
  ('S0-LOG-008', 'willingness-to-pay'),
  ('S0-LOG-009', 'willingness-to-pay'),
  ('S0-LOG-010', 'willingness-to-pay'),
  ('S0-LOG-011', 'icp'),
  ('S0-LOG-012', 'icp'),
  ('S0-LOG-013', 'icp'),
  ('S0-LOG-014', 'willingness-to-pay'),
  ('S0-LOG-015', 'willingness-to-pay'),
  ('S01-LOG-001', 'technical-quality'),
  ('S01-LOG-002', 'technical-quality'),
  ('S01-LOG-003', 'technical-quality'),
  ('S01-LOG-004', 'technical-quality'),
  ('S01-LOG-005', 'technical-quality'),
  ('S01-LOG-006', 'technical-quality'),
  ('S01-LOG-007', 'technical-quality'),
  ('S01-LOG-008', 'technical-quality'),
  ('S01-LOG-009', 'technical-quality'),
  ('S01-LOG-010', 'technical-quality'),
  ('S01-LOG-011', 'technical-quality'),
  ('S01-LOG-012', 'technical-quality'),
  ('S01-LOG-013', 'willingness-to-pay'),
  ('S01-LOG-014', 'willingness-to-pay'),
  ('S01-LOG-015', 'willingness-to-pay'),
  ('S01-LOG-016', 'willingness-to-pay'),
  ('S01-LOG-017', 'technical-quality'),
  ('S01-LOG-018', 'technical-quality'),
  ('S01-LOG-019', 'technical-quality'),
  ('S01-LOG-020', 'technical-quality'),
  ('S10-LOG-001', 'willingness-to-pay'),
  ('S10-LOG-002', 'willingness-to-pay'),
  ('S10-LOG-003', 'willingness-to-pay'),
  ('S10-LOG-004', 'willingness-to-pay'),
  ('S10-LOG-005', 'technical-quality'),
  ('S10-LOG-006', 'technical-quality'),
  ('S10-LOG-007', 'technical-quality'),
  ('S10-LOG-008', 'technical-quality'),
  ('S10-LOG-009', 'technical-quality'),
  ('S10-LOG-010', 'technical-quality'),
  ('S10-LOG-011', 'technical-quality'),
  ('S10-LOG-012', 'technical-quality'),
  ('S10-LOG-013', 'technical-quality'),
  ('S10-LOG-014', 'technical-quality'),
  ('S10-LOG-015', 'technical-quality'),
  ('S10-LOG-016', 'technical-quality'),
  ('S10-LOG-017', 'icp'),
  ('S10-LOG-018', 'icp'),
  ('S10-LOG-019', 'icp'),
  ('S10-LOG-020', 'icp'),
  ('S10-LOG-021', 'willingness-to-pay'),
  ('S10-LOG-022', 'willingness-to-pay'),
  ('S10-LOG-023', 'willingness-to-pay'),
  ('S10-LOG-024', 'willingness-to-pay'),
  ('S10-LOG-025', 'willingness-to-pay')
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
         '["logistics"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-LOG-001', 'Ideation — Logistics Registration Basics', 'LOG-001', '["RC-LOG-001", "RC-LOG-002"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Find out which registrations are needed to carry goods for others.", "Get them in place before taking any paid booking.", "Write down what each costs and how long it takes."]'::jsonb, '[{"name": "Register Before You Haul", "brief": "Getting the mandatory registrations in place first."}]'::jsonb),
  ('INT-LOG-002', 'Ideation — Logistics Registration Basics', 'LOG-001', '["RC-LOG-003", "RC-LOG-005"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Check permits for every state and goods type you plan to carry.", "Confirm what insurance cover is legally required.", "Do not commit to a route until both are clear."]'::jsonb, '[{"name": "Check Permits and Insurance", "brief": "Confirming state, goods and insurance requirements before committing to a route."}]'::jsonb),
  ('INT-LOG-003', 'Ideation — Logistics Registration Basics', 'LOG-001', '["RC-LOG-004"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Name one person responsible for registrations and renewals.", "Keep a dated list of what must be renewed.", "Review it every quarter."]'::jsonb, '[{"name": "One Compliance Owner", "brief": "A single accountable person and a dated renewal list."}]'::jsonb),
  ('INT-LOG-004', 'Ideation — Logistics Cost Reality', 'LOG-002', '["RC-LOG-006", "RC-LOG-007"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Build a cost sheet for one delivery.", "Include fuel, driver time and vehicle wear.", "Compare that total with the price you planned to charge."]'::jsonb, '[{"name": "Real Cost Per Delivery", "brief": "The true cost of one delivery, not just fuel."}]'::jsonb),
  ('INT-LOG-005', 'Ideation — Logistics Cost Reality', 'LOG-002', '["RC-LOG-008", "RC-LOG-009"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Add the cost of empty return legs to your cost sheet.", "Spread office and overhead costs across deliveries.", "Never quote from fuel cost alone again."]'::jsonb, '[{"name": "Count the Empty Leg and Overhead", "brief": "Loading the costs that vanish from a fuel-only calculation."}]'::jsonb),
  ('INT-LOG-006', 'Ideation — Logistics Cost Reality', 'LOG-002', '["RC-LOG-010"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Stop pricing by copying competitors.", "Price from your own real cost per delivery.", "Check which routes are actually profitable."]'::jsonb, '[{"name": "Price From Your Own Cost", "brief": "Fees built from real numbers rather than the market rate."}]'::jsonb),
  ('INT-LOG-007', 'Ideation — Logistics Customer Clarity', 'LOG-003', '["RC-LOG-011", "RC-LOG-012"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Pick one shipper type to serve first.", "Write down why that type and not the others.", "Build one service for them alone."]'::jsonb, '[{"name": "One Shipper Type", "brief": "Choosing a single customer type instead of serving everyone."}]'::jsonb),
  ('INT-LOG-008', 'Ideation — Logistics Customer Clarity', 'LOG-003', '["RC-LOG-013", "RC-LOG-014"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Talk to 10 real shippers of your chosen type.", "Test your assumed routes and volumes against what they actually need.", "Get at least one to commit before buying capacity."]'::jsonb, '[{"name": "Test Routes With Real Shippers", "brief": "Checking assumed lanes and volumes against real demand."}]'::jsonb),
  ('INT-LOG-009', 'Ideation — Logistics Capacity Planning', 'LOG-004', '["RC-LOG-015", "RC-LOG-017"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Confirm real volume before committing to fleet size.", "Do not assume utilisation will simply appear.", "Start smaller than feels comfortable and grow with confirmed demand."]'::jsonb, '[{"name": "Confirm Volume Before Capacity", "brief": "Buying capacity against confirmed demand, not hope."}]'::jsonb),
  ('INT-LOG-010', 'Ideation — Logistics Capacity Planning', 'LOG-004', '["RC-LOG-016", "RC-LOG-018"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Study how demand moves through the week and the year.", "Plan explicitly for the slow periods.", "Decide now what happens to idle capacity then."]'::jsonb, '[{"name": "Plan for the Slow Periods", "brief": "Understanding demand variation and deciding what happens when it dips."}]'::jsonb),
  ('INT-LOG-011', 'Validation to Traction — Logistics Service Reliability', 'LOG-005', '["RC-LOG-019", "RC-LOG-020"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Measure on time rate and damage rate every week.", "Report both alongside revenue.", "Set a target for each."]'::jsonb, '[{"name": "Measure Reliability", "brief": "On time and damage rate as tracked numbers, not impressions."}]'::jsonb),
  ('INT-LOG-012', 'Validation to Traction — Logistics Service Reliability', 'LOG-005', '["RC-LOG-021", "RC-LOG-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Trace every late or damaged delivery to its cause.", "Fix the most common cause first.", "Write down what happens when something goes wrong."]'::jsonb, '[{"name": "Trace and Fix the Cause", "brief": "Finding why failures happen instead of only noting that they did."}]'::jsonb),
  ('INT-LOG-013', 'Validation to Traction — Logistics Shipment Visibility', 'LOG-006', '["RC-LOG-023", "RC-LOG-026"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Put a simple tracking method on every vehicle.", "Set a fixed check in schedule with drivers.", "Make status genuinely visible, not guessed."]'::jsonb, '[{"name": "Track Every Shipment", "brief": "Real visibility during transit instead of updates by guesswork."}]'::jsonb),
  ('INT-LOG-014', 'Validation to Traction — Logistics Shipment Visibility', 'LOG-006', '["RC-LOG-024", "RC-LOG-025"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Base customer updates on real tracking data.", "Flag problems as soon as they appear, not on arrival.", "Tell the customer before they have to ask."]'::jsonb, '[{"name": "Update From Real Data", "brief": "Customer communication grounded in what is actually happening."}]'::jsonb),
  ('INT-LOG-015', 'Validation to Traction — Logistics Fleet Cost Control', 'LOG-007', '["RC-LOG-027", "RC-LOG-030"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Track fuel use and cost per kilometre for every vehicle.", "Compare drivers and vehicles against each other.", "Investigate the outliers."]'::jsonb, '[{"name": "Track Cost Per Kilometre", "brief": "A comparable number across every vehicle and driver."}]'::jsonb),
  ('INT-LOG-016', 'Validation to Traction — Logistics Fleet Cost Control', 'LOG-007', '["RC-LOG-028", "RC-LOG-029"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Move to scheduled maintenance instead of waiting for failure.", "Compare running cost between vehicles regularly.", "Retire or fix the vehicles that cost the most."]'::jsonb, '[{"name": "Scheduled Maintenance and Comparison", "brief": "Planned servicing plus knowing which vehicles cost more to run."}]'::jsonb),
  ('INT-LOG-017', 'Validation to Traction — Logistics Working Capital', 'LOG-008', '["RC-LOG-031", "RC-LOG-034"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Measure the days between paying costs and being paid.", "Track it every month.", "Use it to decide how much volume you can safely take."]'::jsonb, '[{"name": "Measure the Cash Cycle", "brief": "Knowing the real number of days your money is out."}]'::jsonb),
  ('INT-LOG-018', 'Validation to Traction — Logistics Working Capital', 'LOG-008', '["RC-LOG-032", "RC-LOG-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Arrange a credit line sized to the cycle.", "Shorten shipper credit where you can.", "Cap growth at what your cash can carry."]'::jsonb, '[{"name": "Fund the Gap Deliberately", "brief": "Credit and shorter terms sized to the real cycle."}]'::jsonb),
  ('INT-LOG-019', 'Validation to Traction — Logistics Driver Dependency', 'LOG-009', '["RC-LOG-035", "RC-LOG-037"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Write down what each key driver knows about their route.", "Build simple training material from it.", "Cross train a second driver on every key route."]'::jsonb, '[{"name": "Document the Routes", "brief": "Turning route knowledge into something a second driver can learn."}]'::jsonb),
  ('INT-LOG-020', 'Validation to Traction — Logistics Driver Dependency', 'LOG-009', '["RC-LOG-036", "RC-LOG-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Ask leaving drivers why they went.", "Build customer trust in the company, not just the driver.", "Introduce a second driver into key customer relationships."]'::jsonb, '[{"name": "Shift Trust to the Company", "brief": "Reducing dependence on any one driver for retention and relationships."}]'::jsonb),
  ('INT-LOG-021', 'Validation to Traction — Logistics Shipment Visibility', 'LOG-006', '["RC-LOG-063"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Set a rule for when a deviation triggers an alert.", "Notify the customer proactively when it happens.", "Review deviation causes monthly."]'::jsonb, '[{"name": "Alert on Deviation", "brief": "Flagging a shipment going off plan instead of finding out at arrival."}]'::jsonb),
  ('INT-LOG-022', 'Validation to Traction — Logistics Working Capital', 'LOG-008', '["RC-LOG-064"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Check whether each new booking improves or worsens your cash position.", "Cap volume at what your cash can carry.", "Revisit the cap as the cycle improves."]'::jsonb, '[{"name": "Check Growth Against Cash", "brief": "Confirming that more volume is actually helping, not straining, cash."}]'::jsonb),
  ('INT-LOG-023', 'Growth to Maturity — Logistics Customer Concentration', 'LOG-010', '["RC-LOG-039", "RC-LOG-042"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Calculate the volume share of your top three shippers.", "Set a ceiling and build a pipeline of smaller customers.", "Review the share every quarter."]'::jsonb, '[{"name": "Cap Shipper Concentration", "brief": "Measuring dependence and building beyond the dominant few."}]'::jsonb),
  ('INT-LOG-024', 'Growth to Maturity — Logistics Customer Concentration', 'LOG-010', '["RC-LOG-040", "RC-LOG-041", "RC-LOG-065"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Work out your real margin on the dominant shipper after their terms.", "Avoid renewing long contracts that lock in today weak position.", "Renegotiate at the next natural break point."]'::jsonb, '[{"name": "Do Not Lock In a Bad Position", "brief": "Avoiding long contracts that freeze unfavourable terms with a dominant shipper."}]'::jsonb),
  ('INT-LOG-025', 'Growth to Maturity — Logistics Fleet Reliability', 'LOG-011', '["RC-LOG-043", "RC-LOG-046"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Build a preventive maintenance schedule for every vehicle.", "Measure what an hour of downtime actually costs.", "Service on the schedule, not after failure."]'::jsonb, '[{"name": "Preventive Maintenance and Downtime Cost", "brief": "Scheduled servicing backed by knowing what a breakdown really costs."}]'::jsonb),
  ('INT-LOG-026', 'Growth to Maturity — Logistics Fleet Reliability', 'LOG-011', '["RC-LOG-044", "RC-LOG-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Track accident history to find repeat patterns.", "Build one clear process for handling an insurance claim.", "Close the most frequent cause first."]'::jsonb, '[{"name": "Track Accidents, Fix the Process", "brief": "Pattern tracking and a defined claims process instead of ad hoc handling."}]'::jsonb),
  ('INT-LOG-027', 'Growth to Maturity — Logistics Warehouse Scaling', 'LOG-012', '["RC-LOG-047", "RC-LOG-048"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write a standard picking and sorting sequence.", "Reconcile inventory counts against the standard regularly.", "Fix the gap where counts do not match."]'::jsonb, '[{"name": "Standardise Picking, Reconcile Counts", "brief": "A defined process plus regular checks so counts can be trusted."}]'::jsonb),
  ('INT-LOG-028', 'Growth to Maturity — Logistics Warehouse Scaling', 'LOG-012', '["RC-LOG-049", "RC-LOG-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Replan warehouse layout for current volume, not the volume it was built for.", "Build a specific plan for peak periods.", "Test it before the next peak arrives."]'::jsonb, '[{"name": "Replan for Current Volume", "brief": "Layout and peak planning sized to today demand, not the original design."}]'::jsonb),
  ('INT-LOG-029', 'Growth to Maturity — Logistics Compliance Operations', 'LOG-013', '["RC-LOG-051", "RC-LOG-066"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Build one calendar covering every permit, filing and renewal.", "Set reminders well ahead of each expiry.", "Review it monthly."]'::jsonb, '[{"name": "One Compliance Calendar", "brief": "Every recurring obligation and expiry in one dated place."}]'::jsonb),
  ('INT-LOG-030', 'Growth to Maturity — Logistics Compliance Operations', 'LOG-013', '["RC-LOG-052", "RC-LOG-053", "RC-LOG-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Record driver hours and safety incidents systematically.", "Train a second person on the whole compliance process.", "Write it down so it survives a departure."]'::jsonb, '[{"name": "Records and a Second Person", "brief": "Systematic logging plus cross training so compliance does not rest on one person."}]'::jsonb),
  ('INT-LOG-031', 'Growth to Maturity — Logistics Technology Shift', 'LOG-014', '["RC-LOG-055", "RC-LOG-056"]'::jsonb, '[5, 6, 7]'::jsonb, 'Product Design', '["Give shippers a way to book and track without a phone call.", "Prioritise the tracking data shippers actually ask for.", "Start with the simplest version that removes the phone call."]'::jsonb, '[{"name": "Remove the Phone Call", "brief": "Self serve booking and tracking instead of manual coordination."}]'::jsonb),
  ('INT-LOG-032', 'Growth to Maturity — Logistics Technology Shift', 'LOG-014', '["RC-LOG-057", "RC-LOG-058"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["List deals lost for lack of integration and put a value on it.", "Compare that against the cost of building the integration.", "Budget for the gap that matters most."]'::jsonb, '[{"name": "Price the Technology Gap", "brief": "Treating integration as a commercial decision with a number behind it."}]'::jsonb),
  ('INT-LOG-033', 'Growth to Maturity — Logistics Rate Volatility', 'LOG-015', '["RC-LOG-059", "RC-LOG-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Add a fuel surcharge or adjustment clause to every contract.", "Set the trigger point for when it applies.", "Apply it consistently, not only when convenient."]'::jsonb, '[{"name": "Add a Fuel Adjustment Clause", "brief": "Contract terms that share fuel risk instead of absorbing every swing."}]'::jsonb),
  ('INT-LOG-034', 'Growth to Maturity — Logistics Rate Volatility', 'LOG-015', '["RC-LOG-061", "RC-LOG-062"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Track margin per route, not just overall margin.", "Review contract rates on a fixed schedule rather than leaving them fixed for years.", "Renegotiate the routes that no longer work."]'::jsonb, '[{"name": "Review Rates on a Schedule", "brief": "Regular rate reviews instead of contracts that go stale for years."}]'::jsonb)
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

    for label, industry_code, prefix, expected, sql in seeds:
        result = dict(bind.exec_driver_sql(sql).mappings().one())
        actual = {
            "problems_inserted": result.get("problems_inserted"),
            "root_causes_inserted": result.get("root_causes_inserted"),
            "questions_inserted": result.get("questions_inserted"),
            "tags_inserted": result.get("tags_inserted", result.get("tag_links_inserted")),
            "interventions_inserted": result.get("interventions_inserted"),
        }
        if actual != expected:
            raise RuntimeError(
                f"{label} seed count mismatch: expected {expected}, got {actual}"
            )

        inserted_mappings = bind.execute(
            text(
                """
                WITH inserted AS (
                    INSERT INTO question_industry_mapping (
                        question_id, industry_code, stage_group, applicability_type
                    )
                    SELECT
                        q.question_id,
                        :industry_code,
                        q.primary_stage_group,
                        'primary'
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
                "question_pattern": rf"^(S0|S01|S10)-{prefix}-[0-9]{{3}}$",
            },
        ).scalar_one()

        if inserted_mappings != 60:
            raise RuntimeError(
                f"{label} mapping mismatch: expected 60, got {inserted_mappings}"
            )

        # Final prefix-level integrity checks are independent of the source
        # CTE return row and protect against a malformed/mislinked file.
        final_counts = {
            "problems": _prefix_count(bind, "problems", "problem_code", rf"^{prefix}-[0-9]{{3}}$"),
            "root_causes": _prefix_count(bind, "root_causes", "root_cause_code", rf"^RC-{prefix}-[0-9]{{3}}$"),
            "questions": _prefix_count(bind, "questions", "question_code", rf"^(S0|S01|S10)-{prefix}-[0-9]{{3}}$"),
            "interventions": _prefix_count(bind, "interventions", "intervention_code", rf"^INT-{prefix}-[0-9]{{3}}$"),
        }
        expected_final = {
            "problems": expected["problems_inserted"],
            "root_causes": expected["root_causes_inserted"],
            "questions": expected["questions_inserted"],
            "interventions": expected["interventions_inserted"],
        }
        if final_counts != expected_final:
            raise RuntimeError(
                f"{label} final prefix counts mismatch: "
                f"expected {expected_final}, got {final_counts}"
            )

    _sync_sequence(bind, 'industries', 'industry_id')
    _sync_sequence(bind, 'interventions', 'intervention_id')


def downgrade() -> None:
    raise RuntimeError(
        "Migration f1e53a6b8c04 is intentionally irreversible. "
        "Roll back application code without deleting production seed history."
    )
