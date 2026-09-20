"""seed industry batch A: healthtech, travel, hrtech, trade

Revision ID: b7a19c2d4e6f
Revises: 91c4f0a2bd73
Create Date: 2026-09-20
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "b7a19c2d4e6f"
down_revision: Union[str, Sequence[str], None] = "91c4f0a2bd73"
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

    # Production previously had explicit PK loads; keep known drift-prone
    # SERIAL sequences aligned before inserting this batch.
    _sync_sequence(bind, "industries", "industry_id")
    _sync_sequence(bind, "interventions", "intervention_id")

    industry_rows = [
        ('healthtech', 'Healthcare & HealthTech / MedTech', 'Healthcare, health services, digital health, MedTech, diagnostics, care delivery and healthcare-technology businesses.'),
        ('travel_hospitality', 'Hospitality, Travel & Tourism', 'Hospitality, hotels, stays, travel, tourism, experiences, booking and destination-service businesses.'),
        ('hrtech', 'Human Resources & HRTech', 'Recruitment, HR operations, workforce software, payroll, talent, people analytics and HR-technology businesses.'),
        ('trade_import_export', 'Import / Export & Trade', 'Import, export, cross-border trade, sourcing, distribution, trade operations and international-commerce businesses.'),
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
        ('Healthcare & HealthTech / MedTech', 'healthtech', 'HLT', r"""-- ============================================================================
-- Ally :: Industry seed -- HEALTHCARE & HEALTHTECH / MEDTECH (all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: healthtech
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (HLT-001, RC-HLT-014, S0-HLT-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : questions are written to be durable.  They deliberately do NOT
--            name specific statutes, authorities, scheme names or rupee
--            thresholds, because Indian health regulation changes often and
--            differs by state.  They ask the founder what applies to THEM.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (licensing gaps, clinical capacity, unit
--            economics, records) starts at Stage 0->1; governance, data
--            obligations, empanelment and structural position at Stage 1->10+.
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
  ('HLT-001', 'Which Licence Applies Has Not Been Checked', 'Health businesses are licensed by what they actually do, and the founder has not found out which rules apply to their specific idea.', 'Idea & Validation', 'HealthTech Licensing Basics', 'external', 3, 6, 10, '["No idea which authority regulates this", "Assuming a health app needs no approval", "Device, clinic, pharmacy and teleconsult rules treated as one thing", "State versus central licensing not understood", "No plan for who handles compliance"]'::jsonb, '["healthtech"]'::jsonb),
  ('HLT-002', 'Who Actually Pays Has Not Been Worked Out', 'In Indian healthcare the patient, an employer, an insurer and the government all pay for different things, and no payer has been chosen.', 'Idea & Validation', 'HealthTech Payer Clarity', 'external', 4, 5, 9, '["Payer not identified", "Assuming insurance will cover it", "Assuming government schemes will cover it", "No idea what a patient would pay from their own pocket", "Same offer aimed at patients and employers"]'::jsonb, '["healthtech"]'::jsonb),
  ('HLT-003', 'Clinical Claims Being Made Without Evidence', 'The idea promises to detect, treat, prevent or cure something, and nothing exists to support that claim.', 'Idea & Validation', 'HealthTech Clinical Evidence', 'external', 3, 6, 10, '["Promising to diagnose, treat or cure", "No clinical evidence for the claim", "No doctor involved in the design", "Advertising rules for health claims unknown", "Wellness and medical claims used interchangeably"]'::jsonb, '["healthtech"]'::jsonb),
  ('HLT-004', 'Patient Data Handling Not Thought About', 'The idea will collect health information about real people and nothing has been decided about consent, storage or who can see it.', 'Idea & Validation', 'HealthTech Data Basics', 'external', 3, 5, 9, '["No plan for consent", "No decision on where data is stored", "Anyone on the team able to see patient data", "No thought about data from children", "Assuming health data has its own separate law"]'::jsonb, '["healthtech"]'::jsonb),
  ('HLT-005', 'Licences Still Not in Place While Operating', 'The business is already serving patients while approvals are incomplete, which risks shutdown rather than a fine.', 'Operations & Systems', 'HealthTech Licensing Gap', 'external', 3, 7, 10, '["Operating before approvals are complete", "Renewals missed or nearly missed", "Some sites or services unlicensed", "Rules in a new state assumed to be the same", "No record of what is approved and until when"]'::jsonb, '["healthtech"]'::jsonb),
  ('HLT-006', 'Patients Try It Once and Do Not Return', 'People use the service once and never come back, so there is no repeat revenue and no real health outcome.', 'Sales & Revenue', 'HealthTech Repeat Use', 'external', 4, 6, 9, '["Repeat usage never measured", "No follow up after the first visit or consult", "Nothing that needs ongoing use", "Patients returning to their usual provider", "Growth entirely from new patients"]'::jsonb, '["healthtech"]'::jsonb),
  ('HLT-007', 'Doctors and Clinical Staff Are the Bottleneck', 'Every consultation, report or decision needs a qualified person, so growth is limited by how many clinicians can be found and kept.', 'Team & Leadership', 'HealthTech Clinical Capacity', 'external', 5, 6, 9, '["Growth limited by clinician availability", "Clinicians working part time or ad hoc", "No clinical protocols written down", "Quality varies by which clinician is on", "Recruiting clinicians taking longer than planned"]'::jsonb, '["healthtech"]'::jsonb),
  ('HLT-008', 'Unit Economics Break Once Delivery Is Counted', 'The service looks profitable until collection, logistics, clinician time and support are added in, and then each order loses money.', 'Financial Management', 'HealthTech Unit Economics', 'external', 4, 7, 10, '["Cost per order or consult never fully calculated", "Clinician time not costed in", "Last mile or collection cost ignored", "Margin healthy on paper but cash falling", "Discounting to grow volume"]'::jsonb, '["healthtech"]'::jsonb),
  ('HLT-009', 'Consent and Records Handled Informally', 'Patient records and consent are being managed through chat messages, spreadsheets and personal devices.', 'Operations & Systems', 'HealthTech Records Discipline', 'external', 3, 6, 10, '["Records kept in chat or spreadsheets", "Consent taken verbally and not recorded", "Patient data on personal phones and laptops", "No record of who accessed what", "No process if data is lost or leaked"]'::jsonb, '["healthtech"]'::jsonb),
  ('HLT-010', 'Each New City Starts From Zero', 'Profitability depends on having enough patients close together, so every new city restarts at a deep loss.', 'Financial Management', 'HealthTech City Economics', 'external', 4, 7, 10, '["New cities loss making for long periods", "Profit concentrated in the first city", "Costs per patient higher in new locations", "Expansion funded by the profitable city", "No density target before entering a city"]'::jsonb, '["healthtech"]'::jsonb),
  ('HLT-011', 'Clinical Quality and Safety at Scale', 'With many clinicians and sites, one clinical error or safety failure could cause real patient harm and end the business.', 'Operations & Systems', 'HealthTech Clinical Governance', 'external', 3, 7, 10, '["No clinical audit of cases", "Adverse events not formally recorded", "No named clinical lead accountable for safety", "Protocol adherence not checked", "No process for investigating a serious incident"]'::jsonb, '["healthtech"]'::jsonb),
  ('HLT-012', 'Data Obligations Now Carry Real Penalties', 'With large volumes of patient records, breach reporting, consent records and access controls are now legal obligations with real consequences.', 'Operations & Systems', 'HealthTech Data Compliance', 'external', 3, 7, 10, '["No breach detection or reporting process", "Consent records incomplete at volume", "Access to records not logged", "No handling of requests from patients about their data", "Children data handled the same as adult data"]'::jsonb, '["healthtech"]'::jsonb),
  ('HLT-013', 'Insurer and Hospital Empanelment Controls Growth', 'Volume now depends on being empanelled with insurers, employers or hospitals, and those relationships set the price and the terms.', 'Sales & Revenue', 'HealthTech Empanelment', 'external', 4, 6, 9, '["Volume dependent on a few empanelments", "Rates set by the payer not the business", "Long payment cycles from institutional payers", "Claims rejected or deducted without clear reason", "No direct patient channel alongside"]'::jsonb, '["healthtech"]'::jsonb),
  ('HLT-014', 'Accreditation Becoming a Commercial Requirement', 'Accreditation is voluntary in law but payers and large buyers increasingly require it, so not having it starts costing contracts and rate.', 'Operations & Systems', 'HealthTech Accreditation', 'external', 3, 5, 9, '["Losing contracts for lack of accreditation", "Lower rates than accredited competitors", "No plan or budget for accreditation", "Documentation not at the standard required", "Accreditation treated as optional paperwork"]'::jsonb, '["healthtech"]'::jsonb),
  ('HLT-015', 'Nothing Owned That Creates Durable Advantage', 'The business is a layer on top of other people clinics, labs and pharmacies, so margin and control both sit elsewhere.', 'Strategy & Planning', 'HealthTech Structural Position', 'external', 2, 6, 10, '["All delivery done by third parties", "Margin set by partners not the business", "Partners able to go direct to patients", "No proprietary capability, capacity or data asset", "Competitors with owned capacity undercutting"]'::jsonb, '["healthtech"]'::jsonb)
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
         t.primary_stage_group, '["healthtech"]'::jsonb, z.v
  FROM (VALUES
  ('RC-HLT-001', 'Regulating Authority Unknown', 'It is unclear which body oversees this kind of health business.', 'HLT-001', 'external', 'Knowledge', 0.73, 'Stage 0'),
  ('RC-HLT-002', 'Assuming a Health App Needs No Approval', 'Believing software escapes health regulation entirely.', 'HLT-001', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-HLT-003', 'Different Health Rules Treated as One', 'Device, clinic, pharmacy and teleconsult rules are assumed to be the same thing.', 'HLT-001', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-HLT-004', 'State Versus Central Licensing Not Understood', 'Which approvals come from the state and which from the centre is unknown.', 'HLT-001', 'external', 'Knowledge', 0.67, 'Stage 0'),
  ('RC-HLT-005', 'No Owner for Compliance', 'Nobody has been made responsible for licences and renewals.', 'HLT-001', 'external', 'Operational', 0.64, 'Stage 0'),
  ('RC-HLT-006', 'Payer Not Identified', 'Who actually hands over the money has not been decided.', 'HLT-002', 'external', 'Strategic', 0.72, 'Stage 0'),
  ('RC-HLT-007', 'Assuming Insurance Will Cover It', 'The plan quietly depends on insurers paying for something they may not cover.', 'HLT-002', 'external', 'Psychological', 0.70, 'Stage 0'),
  ('RC-HLT-008', 'Assuming Government Schemes Will Cover It', 'Public schemes are assumed to pay for services they do not fund.', 'HLT-002', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-HLT-009', 'Out of Pocket Willingness Unknown', 'What a patient would pay from their own money has never been tested.', 'HLT-002', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-HLT-010', 'Same Offer Aimed at Patients and Employers', 'One pitch is used for buyers who decide in completely different ways.', 'HLT-002', 'external', 'Strategic', 0.65, 'Stage 0'),
  ('RC-HLT-011', 'Promising to Diagnose, Treat or Cure', 'The claim crosses from wellness into medical territory.', 'HLT-003', 'external', 'Strategic', 0.73, 'Stage 0'),
  ('RC-HLT-012', 'No Clinical Evidence for the Claim', 'Nothing has been done to show the claim is true.', 'HLT-003', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-HLT-013', 'No Doctor Involved in the Design', 'No qualified clinician has reviewed what is being built.', 'HLT-003', 'external', 'Operational', 0.69, 'Stage 0'),
  ('RC-HLT-014', 'Health Advertising Rules Unknown', 'What may legally be claimed in marketing has not been checked.', 'HLT-003', 'external', 'Knowledge', 0.67, 'Stage 0'),
  ('RC-HLT-015', 'Wellness and Medical Claims Used Interchangeably', 'The difference between a wellness claim and a medical one is not understood.', 'HLT-003', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-HLT-016', 'No Plan for Consent', 'How patients will be asked for permission has not been decided.', 'HLT-004', 'external', 'Operational', 0.70, 'Stage 0'),
  ('RC-HLT-017', 'No Decision on Where Data Is Stored', 'Where health records will live has not been settled.', 'HLT-004', 'external', 'Operational', 0.67, 'Stage 0'),
  ('RC-HLT-018', 'Everyone on the Team Can See Patient Data', 'No limits exist on who inside the business can read records.', 'HLT-004', 'external', 'Operational', 0.69, 'Stage 0'),
  ('RC-HLT-019', 'Operating Before Approvals Are Complete', 'Patients are being served while licensing is still pending.', 'HLT-005', 'external', 'Behavioural', 0.74, 'Stage 0→1'),
  ('RC-HLT-020', 'Renewals Missed or Nearly Missed', 'Approval expiry dates are remembered rather than managed.', 'HLT-005', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-HLT-021', 'Some Sites or Services Unlicensed', 'Parts of the operation fall outside what was actually approved.', 'HLT-005', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-HLT-022', 'New State Rules Assumed to Be the Same', 'Expansion assumes one state approval works everywhere.', 'HLT-005', 'external', 'Knowledge', 0.69, 'Stage 0→1'),
  ('RC-HLT-023', 'No Record of What Is Approved', 'Nobody can say what is licensed and until when.', 'HLT-005', 'external', 'Operational', 0.67, 'Stage 0→1'),
  ('RC-HLT-024', 'Repeat Usage Never Measured', 'How many patients come back a second time is not tracked.', 'HLT-006', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-HLT-025', 'No Follow Up After the First Visit', 'The relationship ends once the first consult or test is done.', 'HLT-006', 'external', 'Behavioural', 0.69, 'Stage 0→1'),
  ('RC-HLT-026', 'Nothing That Needs Ongoing Use', 'The product solves a one off need with no reason to return.', 'HLT-006', 'external', 'Strategic', 0.70, 'Stage 0→1'),
  ('RC-HLT-027', 'Patients Returning to Their Usual Provider', 'Trust stays with the doctor or lab they already know.', 'HLT-006', 'external', 'Strategic', 0.67, 'Stage 0→1'),
  ('RC-HLT-028', 'Growth Entirely From New Patients', 'Every month starts from zero with no returning base.', 'HLT-006', 'external', 'Strategic', 0.68, 'Stage 0→1'),
  ('RC-HLT-029', 'Growth Limited by Clinician Availability', 'Capacity is capped by how many qualified people are on hand.', 'HLT-007', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-HLT-030', 'Clinicians Working Part Time or Ad Hoc', 'Clinical cover depends on people with other commitments.', 'HLT-007', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-HLT-031', 'No Clinical Protocols Written Down', 'How cases should be handled exists only in individual heads.', 'HLT-007', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-HLT-032', 'Quality Varies by Clinician', 'The patient experience depends on who happens to be on duty.', 'HLT-007', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-HLT-033', 'Clinician Recruiting Slower Than Planned', 'Hiring qualified staff is taking far longer than the plan assumed.', 'HLT-007', 'external', 'Operational', 0.66, 'Stage 0→1'),
  ('RC-HLT-034', 'Cost Per Order Never Fully Calculated', 'The true all in cost of serving one patient is unknown.', 'HLT-008', 'external', 'Knowledge', 0.73, 'Stage 0→1'),
  ('RC-HLT-035', 'Clinician Time Not Costed In', 'The doctor or technician hours behind each service are left out.', 'HLT-008', 'external', 'Knowledge', 0.71, 'Stage 0→1'),
  ('RC-HLT-036', 'Last Mile or Collection Cost Ignored', 'Home collection, logistics and travel are not in the unit cost.', 'HLT-008', 'external', 'Knowledge', 0.72, 'Stage 0→1'),
  ('RC-HLT-037', 'Margin Healthy on Paper but Cash Falling', 'Reported margin and actual bank balance point in opposite directions.', 'HLT-008', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-HLT-038', 'Discounting to Grow Volume', 'Prices are cut to raise numbers, deepening the loss per order.', 'HLT-008', 'external', 'Behavioural', 0.67, 'Stage 0→1'),
  ('RC-HLT-039', 'Records Kept in Chat or Spreadsheets', 'Patient information lives in tools never built to hold it.', 'HLT-009', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-HLT-040', 'Consent Taken Verbally and Not Recorded', 'Permission is assumed rather than documented.', 'HLT-009', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-HLT-041', 'No Density Target Before Entering a City', 'Cities are entered without knowing how many patients per area make it work.', 'HLT-010', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-HLT-042', 'Profit Concentrated in the First City', 'Only the original location actually makes money.', 'HLT-010', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-HLT-043', 'Cost Per Patient Higher in New Locations', 'Travel and idle capacity make early city economics far worse.', 'HLT-010', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-HLT-044', 'Expansion Funded by the Profitable City', 'One working market is paying for several that are not.', 'HLT-010', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-HLT-045', 'No Clinical Audit of Cases', 'Nobody reviews a sample of cases for clinical quality.', 'HLT-011', 'external', 'Operational', 0.74, 'Stage 1→10+'),
  ('RC-HLT-046', 'Adverse Events Not Formally Recorded', 'Things that went wrong are not captured in any system.', 'HLT-011', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-HLT-047', 'No Named Clinical Lead', 'No qualified person is formally accountable for patient safety.', 'HLT-011', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-HLT-048', 'Protocol Adherence Not Checked', 'Whether clinicians actually follow the protocols is never verified.', 'HLT-011', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-HLT-049', 'No Serious Incident Process', 'There is no defined route for investigating a serious event.', 'HLT-011', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-HLT-050', 'No Breach Detection or Reporting Process', 'A data breach would not be noticed or reported in time.', 'HLT-012', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-HLT-051', 'Consent Records Incomplete at Volume', 'Consent cannot be produced for every patient on file.', 'HLT-012', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-HLT-052', 'Record Access Not Logged', 'There is no trail of who opened which patient record.', 'HLT-012', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-HLT-053', 'No Handling of Patient Data Requests', 'Requests from patients about their own data have no defined route.', 'HLT-012', 'external', 'Operational', 0.68, 'Stage 1→10+'),
  ('RC-HLT-054', 'Children Data Handled Like Adult Data', 'Records of young patients get no additional protection.', 'HLT-012', 'external', 'Knowledge', 0.72, 'Stage 1→10+'),
  ('RC-HLT-055', 'Volume Dependent on Few Empanelments', 'Most patients arrive through a small number of institutional relationships.', 'HLT-013', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-HLT-056', 'Rates Set by the Payer', 'Pricing is dictated by the insurer, employer or hospital.', 'HLT-013', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-HLT-057', 'Long Payment Cycles From Institutional Payers', 'Money from large payers arrives months after the service.', 'HLT-013', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-HLT-058', 'Claims Rejected or Deducted Unclearly', 'Payments come back short with reasons that are hard to contest.', 'HLT-013', 'external', 'Operational', 0.68, 'Stage 1→10+'),
  ('RC-HLT-059', 'No Direct Patient Channel Alongside', 'Nothing exists that reaches patients without going through a payer.', 'HLT-013', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-HLT-060', 'Losing Contracts for Lack of Accreditation', 'Buyers are choosing accredited competitors instead.', 'HLT-014', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-HLT-061', 'Lower Rates Than Accredited Competitors', 'Payers pay less without the certification in place.', 'HLT-014', 'external', 'Strategic', 0.68, 'Stage 1→10+'),
  ('RC-HLT-062', 'No Plan or Budget for Accreditation', 'Certification has not been costed or scheduled.', 'HLT-014', 'external', 'Strategic', 0.67, 'Stage 1→10+'),
  ('RC-HLT-063', 'Documentation Below the Required Standard', 'Records and processes would not survive an assessment.', 'HLT-014', 'external', 'Operational', 0.66, 'Stage 1→10+'),
  ('RC-HLT-064', 'All Delivery Done by Third Parties', 'Every clinic, lab or pharmacy in the chain belongs to someone else.', 'HLT-015', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-HLT-065', 'Margin Set by Partners', 'The partners in the chain decide what is left for the business.', 'HLT-015', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-HLT-066', 'Partners Able to Go Direct', 'Nothing stops suppliers serving the patient without you.', 'HLT-015', 'external', 'Strategic', 0.72, 'Stage 1→10+')
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
         '["healthtech"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-HLT-001', 'Do you know which government body would regulate what you want to do?', 'open_text', 'Idea & Validation', 'CORE', 'HLT-001', 'RC-HLT-001', 1, 'Stage 0'),
  ('S0-HLT-002', 'Do you think a health app can launch without any approval?', 'open_text', 'Idea & Validation', 'CORE', 'HLT-001', 'RC-HLT-002', 1, 'Stage 0'),
  ('S0-HLT-003', 'Is this a device, a clinic, a pharmacy or a consultation service? The rules differ for each.', 'open_text', 'Idea & Validation', 'CORE', 'HLT-001', 'RC-HLT-003', 2, 'Stage 0'),
  ('S0-HLT-004', 'Do you know which approvals come from your state and which from the centre?', 'open_text', 'Idea & Validation', 'CORE', 'HLT-001', 'RC-HLT-004', 2, 'Stage 0'),
  ('S0-HLT-005', 'Who in your team would be responsible for licences and renewals?', 'open_text', 'Idea & Validation', 'CORE', 'HLT-001', 'RC-HLT-005', 2, 'Stage 0'),
  ('S0-HLT-006', 'Who actually hands over the money, the patient, an employer, an insurer or the government?', 'open_text', 'Idea & Validation', 'CORE', 'HLT-002', 'RC-HLT-006', 1, 'Stage 0'),
  ('S0-HLT-007', 'Are you assuming insurance will pay for this? Have you checked?', 'open_text', 'Idea & Validation', 'CORE', 'HLT-002', 'RC-HLT-007', 2, 'Stage 0'),
  ('S0-HLT-008', 'Are you counting on a government scheme to pay? Do you know what it actually covers?', 'open_text', 'Idea & Validation', 'CORE', 'HLT-002', 'RC-HLT-008', 2, 'Stage 0'),
  ('S0-HLT-009', 'How much would an ordinary patient pay for this from their own pocket?', 'open_text', 'Idea & Validation', 'CORE', 'HLT-002', 'RC-HLT-009', 2, 'Stage 0'),
  ('S0-HLT-010', 'Are you pitching the same thing to patients and to companies?', 'open_text', 'Idea & Validation', 'CORE', 'HLT-002', 'RC-HLT-010', 2, 'Stage 0'),
  ('S0-HLT-011', 'Are you promising to detect, treat, prevent or cure anything?', 'open_text', 'Idea & Validation', 'CORE', 'HLT-003', 'RC-HLT-011', 1, 'Stage 0'),
  ('S0-HLT-012', 'What evidence do you have that it actually works?', 'open_text', 'Idea & Validation', 'CORE', 'HLT-003', 'RC-HLT-012', 2, 'Stage 0'),
  ('S0-HLT-013', 'Has any qualified doctor looked at what you are building?', 'open_text', 'Idea & Validation', 'CORE', 'HLT-003', 'RC-HLT-013', 1, 'Stage 0'),
  ('S0-HLT-014', 'Do you know what you are legally allowed to claim in your advertising?', 'open_text', 'Idea & Validation', 'CORE', 'HLT-003', 'RC-HLT-014', 2, 'Stage 0'),
  ('S0-HLT-015', 'How will you ask patients for permission to use their health information?', 'open_text', 'Idea & Validation', 'CORE', 'HLT-004', 'RC-HLT-016', 1, 'Stage 0'),
  ('S01-HLT-001', 'Are you serving patients today while any approval is still pending?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-005', 'RC-HLT-019', 2, 'Stage 0→1'),
  ('S01-HLT-002', 'Who tracks your licence renewal dates?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-005', 'RC-HLT-020', 2, 'Stage 0→1'),
  ('S01-HLT-003', 'Is every site and service you run actually covered by an approval?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-005', 'RC-HLT-021', 3, 'Stage 0→1'),
  ('S01-HLT-004', 'If you opened in another state, would the same approvals apply?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-005', 'RC-HLT-022', 2, 'Stage 0→1'),
  ('S01-HLT-005', 'Can you list what you are licensed for and until when?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-005', 'RC-HLT-023', 2, 'Stage 0→1'),
  ('S01-HLT-006', 'Out of 100 patients, how many use you a second time?', 'open_text', 'Sales & Revenue', 'CORE', 'HLT-006', 'RC-HLT-024', 2, 'Stage 0→1'),
  ('S01-HLT-007', 'Does a patient hear from you after the first consult or test?', 'open_text', 'Sales & Revenue', 'CORE', 'HLT-006', 'RC-HLT-025', 2, 'Stage 0→1'),
  ('S01-HLT-008', 'Is there any reason a patient would need you again?', 'open_text', 'Sales & Revenue', 'CORE', 'HLT-006', 'RC-HLT-026', 2, 'Stage 0→1'),
  ('S01-HLT-009', 'Do patients go back to their usual doctor or lab after trying you?', 'open_text', 'Sales & Revenue', 'CORE', 'HLT-006', 'RC-HLT-027', 2, 'Stage 0→1'),
  ('S01-HLT-010', 'Is your growth coming from new patients or returning ones?', 'open_text', 'Strategy & Planning', 'CORE', 'HLT-006', 'RC-HLT-028', 2, 'Stage 0→1'),
  ('S01-HLT-011', 'What stops you serving twice as many patients tomorrow?', 'open_text', 'Team & Leadership', 'CORE', 'HLT-007', 'RC-HLT-029', 2, 'Stage 0→1'),
  ('S01-HLT-012', 'Are your clinicians full time, or fitting you around other work?', 'open_text', 'Team & Leadership', 'CORE', 'HLT-007', 'RC-HLT-030', 2, 'Stage 0→1'),
  ('S01-HLT-013', 'Is there a written protocol for how a case should be handled?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-007', 'RC-HLT-031', 2, 'Stage 0→1'),
  ('S01-HLT-014', 'Would a patient get the same care whichever clinician they saw?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-007', 'RC-HLT-032', 3, 'Stage 0→1'),
  ('S01-HLT-015', 'How long is it actually taking you to hire a qualified clinician?', 'open_text', 'Team & Leadership', 'CORE', 'HLT-007', 'RC-HLT-033', 2, 'Stage 0→1'),
  ('S01-HLT-016', 'What does it really cost you to serve one patient, all in?', 'open_text', 'Financial Management', 'CORE', 'HLT-008', 'RC-HLT-034', 3, 'Stage 0→1'),
  ('S01-HLT-017', 'Is clinician time included in that cost?', 'open_text', 'Financial Management', 'CORE', 'HLT-008', 'RC-HLT-035', 2, 'Stage 0→1'),
  ('S01-HLT-018', 'Is home collection, travel or delivery included in that cost?', 'open_text', 'Financial Management', 'CORE', 'HLT-008', 'RC-HLT-036', 2, 'Stage 0→1'),
  ('S01-HLT-019', 'Your margin looks fine, so why is cash going down?', 'open_text', 'Financial Management', 'CORE', 'HLT-008', 'RC-HLT-037', 3, 'Stage 0→1'),
  ('S01-HLT-020', 'Are you discounting to bring volume in?', 'open_text', 'Financial Management', 'CORE', 'HLT-008', 'RC-HLT-038', 2, 'Stage 0→1'),
  ('S10-HLT-001', 'How many of your cities actually make money?', 'open_text', 'Financial Management', 'CORE', 'HLT-010', 'RC-HLT-042', 2, 'Stage 1→10+'),
  ('S10-HLT-002', 'How many patients in one area do you need before a city works?', 'open_text', 'Financial Management', 'CORE', 'HLT-010', 'RC-HLT-041', 3, 'Stage 1→10+'),
  ('S10-HLT-003', 'Why does it cost more to serve a patient in a new city?', 'open_text', 'Financial Management', 'CORE', 'HLT-010', 'RC-HLT-043', 3, 'Stage 1→10+'),
  ('S10-HLT-004', 'Is your best city paying for the others?', 'open_text', 'Financial Management', 'CORE', 'HLT-010', 'RC-HLT-044', 3, 'Stage 1→10+'),
  ('S10-HLT-005', 'Does anyone review a sample of cases for clinical quality?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-011', 'RC-HLT-045', 3, 'Stage 1→10+'),
  ('S10-HLT-006', 'When something goes wrong clinically, where is it recorded?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-011', 'RC-HLT-046', 2, 'Stage 1→10+'),
  ('S10-HLT-007', 'Who is formally accountable for patient safety?', 'open_text', 'Team & Leadership', 'CORE', 'HLT-011', 'RC-HLT-047', 2, 'Stage 1→10+'),
  ('S10-HLT-008', 'Do you check whether clinicians actually follow your protocols?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-011', 'RC-HLT-048', 3, 'Stage 1→10+'),
  ('S10-HLT-009', 'If a serious incident happened tomorrow, what is the process?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-011', 'RC-HLT-049', 3, 'Stage 1→10+'),
  ('S10-HLT-010', 'Would you know if patient data leaked, and how fast?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-012', 'RC-HLT-050', 3, 'Stage 1→10+'),
  ('S10-HLT-011', 'Could you produce recorded consent for every patient on your system?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-012', 'RC-HLT-051', 3, 'Stage 1→10+'),
  ('S10-HLT-012', 'Is there a log of who opened which patient record?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-012', 'RC-HLT-052', 2, 'Stage 1→10+'),
  ('S10-HLT-013', 'If a patient asked for their data or asked you to delete it, what happens?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-012', 'RC-HLT-053', 2, 'Stage 1→10+'),
  ('S10-HLT-014', 'Do you treat records of young patients any differently?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-012', 'RC-HLT-054', 3, 'Stage 1→10+'),
  ('S10-HLT-015', 'What share of your patients come through a few institutional relationships?', 'open_text', 'Sales & Revenue', 'CORE', 'HLT-013', 'RC-HLT-055', 2, 'Stage 1→10+'),
  ('S10-HLT-016', 'Who sets your rates, you or the payer?', 'open_text', 'Sales & Revenue', 'CORE', 'HLT-013', 'RC-HLT-056', 2, 'Stage 1→10+'),
  ('S10-HLT-017', 'How long do institutional payers take to pay you?', 'open_text', 'Financial Management', 'CORE', 'HLT-013', 'RC-HLT-057', 2, 'Stage 1→10+'),
  ('S10-HLT-018', 'How much gets deducted from your claims, and do you know why?', 'open_text', 'Financial Management', 'CORE', 'HLT-013', 'RC-HLT-058', 2, 'Stage 1→10+'),
  ('S10-HLT-019', 'Can you reach patients without going through a payer?', 'open_text', 'Sales & Revenue', 'CORE', 'HLT-013', 'RC-HLT-059', 3, 'Stage 1→10+'),
  ('S10-HLT-020', 'Have you lost any contract because you are not accredited?', 'open_text', 'Sales & Revenue', 'CORE', 'HLT-014', 'RC-HLT-060', 2, 'Stage 1→10+'),
  ('S10-HLT-021', 'Do accredited competitors get better rates than you?', 'open_text', 'Sales & Revenue', 'CORE', 'HLT-014', 'RC-HLT-061', 2, 'Stage 1→10+'),
  ('S10-HLT-022', 'Is accreditation budgeted and scheduled, or still a someday item?', 'open_text', 'Strategy & Planning', 'CORE', 'HLT-014', 'RC-HLT-062', 2, 'Stage 1→10+'),
  ('S10-HLT-023', 'Would your documentation survive an assessment tomorrow?', 'open_text', 'Operations & Systems', 'CORE', 'HLT-014', 'RC-HLT-063', 3, 'Stage 1→10+'),
  ('S10-HLT-024', 'Do you own any clinic, lab or capacity, or is it all other people?', 'open_text', 'Strategy & Planning', 'CORE', 'HLT-015', 'RC-HLT-064', 3, 'Stage 1→10+'),
  ('S10-HLT-025', 'What stops your partners serving the patient directly without you?', 'open_text', 'Strategy & Planning', 'CORE', 'HLT-015', 'RC-HLT-066', 3, 'Stage 1→10+')
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
  ('S0-HLT-001', 'technical-quality'),
  ('S0-HLT-002', 'technical-quality'),
  ('S0-HLT-003', 'technical-quality'),
  ('S0-HLT-004', 'technical-quality'),
  ('S0-HLT-005', 'technical-quality'),
  ('S0-HLT-006', 'willingness-to-pay'),
  ('S0-HLT-007', 'willingness-to-pay'),
  ('S0-HLT-008', 'willingness-to-pay'),
  ('S0-HLT-009', 'willingness-to-pay'),
  ('S0-HLT-010', 'willingness-to-pay'),
  ('S0-HLT-011', 'technical-quality'),
  ('S0-HLT-012', 'technical-quality'),
  ('S0-HLT-013', 'technical-quality'),
  ('S0-HLT-014', 'technical-quality'),
  ('S0-HLT-015', 'technical-quality'),
  ('S01-HLT-001', 'technical-quality'),
  ('S01-HLT-002', 'technical-quality'),
  ('S01-HLT-003', 'technical-quality'),
  ('S01-HLT-004', 'technical-quality'),
  ('S01-HLT-005', 'technical-quality'),
  ('S01-HLT-006', 'customer-discovery'),
  ('S01-HLT-007', 'customer-discovery'),
  ('S01-HLT-008', 'customer-discovery'),
  ('S01-HLT-009', 'customer-discovery'),
  ('S01-HLT-010', 'customer-discovery'),
  ('S01-HLT-011', 'technical-quality'),
  ('S01-HLT-012', 'technical-quality'),
  ('S01-HLT-013', 'technical-quality'),
  ('S01-HLT-014', 'technical-quality'),
  ('S01-HLT-015', 'technical-quality'),
  ('S01-HLT-016', 'willingness-to-pay'),
  ('S01-HLT-017', 'willingness-to-pay'),
  ('S01-HLT-018', 'willingness-to-pay'),
  ('S01-HLT-019', 'willingness-to-pay'),
  ('S01-HLT-020', 'willingness-to-pay'),
  ('S10-HLT-001', 'willingness-to-pay'),
  ('S10-HLT-002', 'willingness-to-pay'),
  ('S10-HLT-003', 'willingness-to-pay'),
  ('S10-HLT-004', 'willingness-to-pay'),
  ('S10-HLT-005', 'technical-quality'),
  ('S10-HLT-006', 'technical-quality'),
  ('S10-HLT-007', 'technical-quality'),
  ('S10-HLT-008', 'technical-quality'),
  ('S10-HLT-009', 'technical-quality'),
  ('S10-HLT-010', 'technical-quality'),
  ('S10-HLT-011', 'technical-quality'),
  ('S10-HLT-012', 'technical-quality'),
  ('S10-HLT-013', 'technical-quality'),
  ('S10-HLT-014', 'technical-quality'),
  ('S10-HLT-015', 'willingness-to-pay'),
  ('S10-HLT-016', 'willingness-to-pay'),
  ('S10-HLT-017', 'willingness-to-pay'),
  ('S10-HLT-018', 'willingness-to-pay'),
  ('S10-HLT-019', 'willingness-to-pay'),
  ('S10-HLT-020', 'technical-quality'),
  ('S10-HLT-021', 'technical-quality'),
  ('S10-HLT-022', 'technical-quality'),
  ('S10-HLT-023', 'technical-quality'),
  ('S10-HLT-024', 'technical-quality'),
  ('S10-HLT-025', 'technical-quality')
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
         '["healthtech"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-HLT-001', 'Ideation — HealthTech Licensing Basics', 'HLT-001', '["RC-HLT-001", "RC-HLT-003"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Write in one line exactly what your product does to or for a patient.", "Use that to find which rules apply, device, clinic, pharmacy or consultation.", "Confirm it with someone who has licensed a similar business."]'::jsonb, '[{"name": "Name What You Actually Are", "brief": "Health rules follow the function, so define the function first."}]'::jsonb),
  ('INT-HLT-002', 'Ideation — HealthTech Licensing Basics', 'HLT-001', '["RC-HLT-002", "RC-HLT-004"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Check whether your software would count as a regulated medical device.", "List which approvals come from the state and which from the centre.", "Write down the cost and time for each."]'::jsonb, '[{"name": "Map Your Approvals", "brief": "Separating state and central approvals before building."}]'::jsonb),
  ('INT-HLT-003', 'Ideation — HealthTech Licensing Basics', 'HLT-001', '["RC-HLT-005"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Name one person responsible for licences and renewals.", "Keep a dated list of everything that must be obtained or renewed.", "Review it every quarter."]'::jsonb, '[{"name": "One Compliance Owner", "brief": "A single accountable person and a dated list of obligations."}]'::jsonb),
  ('INT-HLT-004', 'Ideation — HealthTech Payer Clarity', 'HLT-002', '["RC-HLT-006", "RC-HLT-010"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Pick one payer to start with, patient, employer, insurer or government.", "Write why that one first.", "Build one offer for them alone."]'::jsonb, '[{"name": "Choose One Payer", "brief": "Health has four very different buyers; start by choosing one."}]'::jsonb),
  ('INT-HLT-005', 'Ideation — HealthTech Payer Clarity', 'HLT-002', '["RC-HLT-007", "RC-HLT-008"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Check exactly what insurance and government schemes actually cover.", "Note whether they pay for outpatient care, medicines or only hospital admission.", "Redo your numbers assuming they pay nothing."]'::jsonb, '[{"name": "Check What Schemes Really Cover", "brief": "Confirming coverage instead of assuming it."}]'::jsonb),
  ('INT-HLT-006', 'Ideation — HealthTech Payer Clarity', 'HLT-002', '["RC-HLT-009"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Ask 20 real patients what they would pay for this from their own money.", "Compare that with what a family already spends on health each month.", "Decide whether the price is realistic."]'::jsonb, '[{"name": "Out of Pocket Reality Check", "brief": "Testing price against what households actually spend."}]'::jsonb),
  ('INT-HLT-007', 'Ideation — HealthTech Clinical Evidence', 'HLT-003', '["RC-HLT-011", "RC-HLT-015"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Write your claim down in one sentence.", "Decide honestly whether it is a wellness claim or a medical one.", "If it is medical, plan for the evidence and approval that requires."]'::jsonb, '[{"name": "Wellness or Medical", "brief": "Knowing which side of the line your claim sits on."}]'::jsonb),
  ('INT-HLT-008', 'Ideation — HealthTech Clinical Evidence', 'HLT-003', '["RC-HLT-012", "RC-HLT-013"]'::jsonb, '[1]'::jsonb, 'Product Design', '["Bring one qualified doctor in to review the idea.", "Ask what evidence would be needed to support your claim.", "Plan the smallest study that could produce it."]'::jsonb, '[{"name": "Get a Clinician In Early", "brief": "A qualified reviewer and a realistic evidence plan."}]'::jsonb),
  ('INT-HLT-009', 'Ideation — HealthTech Clinical Evidence', 'HLT-003', '["RC-HLT-014"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Read the rules on what health claims may be advertised.", "Remove anything you cannot support.", "Get marketing copy checked before it goes out."]'::jsonb, '[{"name": "Check Your Claims Before You Publish", "brief": "Making advertising match what you can actually prove."}]'::jsonb),
  ('INT-HLT-010', 'Ideation — HealthTech Data Basics', 'HLT-004', '["RC-HLT-016", "RC-HLT-017", "RC-HLT-018"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Decide how you will ask for and record consent.", "Decide where health records will be stored and who can open them.", "Limit access so only people who need records can see them."]'::jsonb, '[{"name": "Consent, Storage and Access", "brief": "The three data decisions to make before collecting anything."}]'::jsonb),
  ('INT-HLT-011', 'Validation to Traction — HealthTech Licensing Gap', 'HLT-005', '["RC-HLT-019", "RC-HLT-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["List every site and service, and the approval that covers it.", "Mark anything running without one.", "Close those gaps before adding any new service."]'::jsonb, '[{"name": "Licence Coverage Map", "brief": "Matching every service you run to the approval that permits it."}]'::jsonb),
  ('INT-HLT-012', 'Validation to Traction — HealthTech Licensing Gap', 'HLT-005', '["RC-HLT-020", "RC-HLT-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Build one register of approvals with expiry dates.", "Set reminders 60 days before each renewal.", "Give one person responsibility for it."]'::jsonb, '[{"name": "Approval Register", "brief": "A dated record so nothing lapses unnoticed."}]'::jsonb),
  ('INT-HLT-013', 'Validation to Traction — HealthTech Licensing Gap', 'HLT-005', '["RC-HLT-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Before entering a new state, check its own health rules.", "Assume nothing carries over.", "Budget the time and cost that adds."]'::jsonb, '[{"name": "Check the Next State Separately", "brief": "Treating each state approval as its own piece of work."}]'::jsonb),
  ('INT-HLT-014', 'Validation to Traction — HealthTech Repeat Use', 'HLT-006', '["RC-HLT-024", "RC-HLT-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Measure how many patients use you a second time.", "Report that number monthly alongside new patients.", "Set a target to improve it."]'::jsonb, '[{"name": "Measure Repeat Use", "brief": "Tracking returning patients, not just new ones."}]'::jsonb),
  ('INT-HLT-015', 'Validation to Traction — HealthTech Repeat Use', 'HLT-006', '["RC-HLT-025", "RC-HLT-026"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["Add one follow up contact after the first consult or test.", "Build one thing that genuinely needs ongoing use.", "Measure whether return visits rise."]'::jsonb, '[{"name": "Give a Reason to Return", "brief": "Follow up plus something that needs continuing care."}]'::jsonb),
  ('INT-HLT-016', 'Validation to Traction — HealthTech Repeat Use', 'HLT-006', '["RC-HLT-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Market Validation', '["Ask 10 patients who did not return why they went back to their usual provider.", "Look for the trust or convenience gap in their answers.", "Fix the biggest one."]'::jsonb, '[{"name": "Ask Why They Left", "brief": "Learning what their existing doctor or lab does better."}]'::jsonb),
  ('INT-HLT-017', 'Validation to Traction — HealthTech Clinical Capacity', 'HLT-007', '["RC-HLT-029", "RC-HLT-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Work out how many patients one clinician can safely handle.", "Use that to set your real growth ceiling.", "Start hiring well before you reach it."]'::jsonb, '[{"name": "Clinical Capacity Ceiling", "brief": "Knowing the real limit set by qualified people."}]'::jsonb),
  ('INT-HLT-018', 'Validation to Traction — HealthTech Clinical Capacity', 'HLT-007', '["RC-HLT-031", "RC-HLT-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Write protocols for your most common cases.", "Have every clinician work to them.", "Review a sample of cases against the protocol each month."]'::jsonb, '[{"name": "Written Clinical Protocols", "brief": "A standard so care does not depend on who is on duty."}]'::jsonb),
  ('INT-HLT-019', 'Validation to Traction — HealthTech Clinical Capacity', 'HLT-007', '["RC-HLT-030"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Move your most critical cover to committed hours.", "Avoid depending on people fitting you around other jobs.", "Have a named backup for every slot."]'::jsonb, '[{"name": "Committed Clinical Cover", "brief": "Reliable hours instead of ad hoc availability."}]'::jsonb),
  ('INT-HLT-020', 'Validation to Traction — HealthTech Unit Economics', 'HLT-008', '["RC-HLT-034", "RC-HLT-035", "RC-HLT-036"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Rebuild the cost of one patient including clinician time and last mile.", "Compare it against what you actually charge.", "Fix the price or the process where it loses money."]'::jsonb, '[{"name": "True Cost Per Patient", "brief": "An all in unit cost including clinical and delivery effort."}]'::jsonb),
  ('INT-HLT-021', 'Validation to Traction — HealthTech Unit Economics', 'HLT-008', '["RC-HLT-037", "RC-HLT-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Compare reported margin against actual monthly cash movement.", "Stop discounts that grow volume at a loss.", "Grow only where the unit is profitable."]'::jsonb, '[{"name": "Margin Versus Cash", "brief": "Checking that reported profit shows up in the bank."}]'::jsonb),
  ('INT-HLT-022', 'Validation to Traction — HealthTech Records Discipline', 'HLT-009', '["RC-HLT-039", "RC-HLT-040"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Move patient records out of chat and spreadsheets into one proper system.", "Record consent in writing every time.", "Limit who can open records and keep a log."]'::jsonb, '[{"name": "Proper Records and Recorded Consent", "brief": "One system, written consent and controlled access."}]'::jsonb),
  ('INT-HLT-023', 'Growth to Maturity — HealthTech City Economics', 'HLT-010', '["RC-HLT-041", "RC-HLT-043"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Work out how many patients per area made your best city profitable.", "Set that as the entry condition for any new city.", "Do not open where you cannot reach it within a set period."]'::jsonb, '[{"name": "Density Before Entry", "brief": "Entering a city only where the patient concentration can support it."}]'::jsonb),
  ('INT-HLT-024', 'Growth to Maturity — HealthTech City Economics', 'HLT-010', '["RC-HLT-042", "RC-HLT-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Report profit separately for every city.", "Cap how many loss making cities one profitable city can carry.", "Fix or exit the weakest before opening another."]'::jsonb, '[{"name": "City by City P and L", "brief": "Seeing each market on its own instead of one blended number."}]'::jsonb),
  ('INT-HLT-025', 'Growth to Maturity — HealthTech Clinical Governance', 'HLT-011', '["RC-HLT-045", "RC-HLT-048"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Review a random sample of cases every month against your protocols.", "Record where care differed and why.", "Feed the findings back into training."]'::jsonb, '[{"name": "Monthly Clinical Audit", "brief": "Sampling real cases to check care matches the protocol."}]'::jsonb),
  ('INT-HLT-026', 'Growth to Maturity — HealthTech Clinical Governance', 'HLT-011', '["RC-HLT-046", "RC-HLT-047", "RC-HLT-049"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Appoint a named clinical lead accountable for patient safety.", "Create one place where adverse events are recorded.", "Write the process for investigating a serious incident before you need it."]'::jsonb, '[{"name": "Clinical Lead and Incident Process", "brief": "One accountable clinician and a defined route for serious events."}]'::jsonb),
  ('INT-HLT-027', 'Growth to Maturity — HealthTech Data Compliance', 'HLT-012', '["RC-HLT-050", "RC-HLT-052"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Put logging in place so you can see who opened which record.", "Define how a breach would be detected and reported, and how fast.", "Test the process once."]'::jsonb, '[{"name": "Detect, Log and Report", "brief": "Access logs plus a tested breach reporting route."}]'::jsonb),
  ('INT-HLT-028', 'Growth to Maturity — HealthTech Data Compliance', 'HLT-012', '["RC-HLT-051", "RC-HLT-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Check you can produce consent for every patient on file.", "Fill the gaps or stop using those records.", "Define how you answer a patient request about their data."]'::jsonb, '[{"name": "Consent and Patient Requests", "brief": "Complete consent records and a route for patient data requests."}]'::jsonb),
  ('INT-HLT-029', 'Growth to Maturity — HealthTech Data Compliance', 'HLT-012', '["RC-HLT-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Identify records belonging to young patients.", "Apply stricter consent and handling to them.", "Check what is required for under eighteens specifically."]'::jsonb, '[{"name": "Handle Children Data Separately", "brief": "Stricter treatment for records of young patients."}]'::jsonb),
  ('INT-HLT-030', 'Growth to Maturity — HealthTech Empanelment', 'HLT-013', '["RC-HLT-055", "RC-HLT-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Measure what share of volume comes from each institutional relationship.", "Build one channel that reaches patients directly.", "Set a target share that should not depend on empanelment."]'::jsonb, '[{"name": "Reduce Empanelment Dependence", "brief": "A direct channel alongside institutional volume."}]'::jsonb),
  ('INT-HLT-031', 'Growth to Maturity — HealthTech Empanelment', 'HLT-013', '["RC-HLT-056", "RC-HLT-057", "RC-HLT-058"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Track payment delays and deductions by payer.", "Work out your real margin after both.", "Renegotiate or drop the payers that fail that test."]'::jsonb, '[{"name": "Real Margin by Payer", "brief": "Counting delay and deduction before calling a payer profitable."}]'::jsonb),
  ('INT-HLT-032', 'Growth to Maturity — HealthTech Accreditation', 'HLT-014', '["RC-HLT-060", "RC-HLT-061"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["List contracts and rates lost for want of accreditation.", "Put a rupee figure on it.", "Compare that against the cost of getting accredited."]'::jsonb, '[{"name": "Price the Accreditation Gap", "brief": "Treating certification as a commercial decision with a number."}]'::jsonb),
  ('INT-HLT-033', 'Growth to Maturity — HealthTech Accreditation', 'HLT-014', '["RC-HLT-062", "RC-HLT-063"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Choose the accreditation your payers actually ask for.", "Budget and schedule it with an owner.", "Bring documentation up to standard before applying."]'::jsonb, '[{"name": "Plan the Accreditation", "brief": "A funded, scheduled route rather than a someday intention."}]'::jsonb),
  ('INT-HLT-034', 'Growth to Maturity — HealthTech Structural Position', 'HLT-015', '["RC-HLT-064", "RC-HLT-065", "RC-HLT-066"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Identify the one part of the chain worth owning.", "Build or acquire capacity there rather than renting it.", "Check what would stop a partner serving your patient directly."]'::jsonb, '[{"name": "Own One Part of the Chain", "brief": "Holding real capacity so margin and control do not sit with partners."}]'::jsonb)
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
        ('Hospitality, Travel & Tourism', 'travel_hospitality', 'TRV', r"""-- ============================================================================
-- Ally :: Industry seed -- HOSPITALITY, TRAVEL & TOURISM (all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: travel_hospitality
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (TRV-001, RC-TRV-014, S0-TRV-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : questions avoid naming specific permissions, authorities or rate
--            figures, because hospitality rules differ by state and city and
--            change often.  They ask the founder what applies to THEM.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (platform dependence, reviews, cancellations,
--            pricing) starts at Stage 0->1; multi property, demand shocks,
--            safety and capital intensity at Stage 1->10+.
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
  ('TRV-001', 'Seasonality Not Thought Through', 'Travel demand rises and falls sharply through the year, and the plan assumes steady bookings every month.', 'Idea & Validation', 'Travel Seasonality Basics', 'external', 4, 5, 9, '["Plan assumes the same bookings every month", "No idea which months are quiet", "Costs continue in the off season but income does not", "Annual numbers built from a good month", "No plan for the lean period"]'::jsonb, '["travel_hospitality"]'::jsonb),
  ('TRV-002', 'Licences and Permissions Not Checked', 'Hotels, homestays, tour operators and transport all need specific permissions, and none have been looked into.', 'Idea & Validation', 'Travel Licensing Basics', 'external', 3, 5, 9, '["No idea which permissions are needed", "Assuming a property can be let to guests freely", "Local or municipal rules not checked", "Guest registration requirements unknown", "No plan for who handles compliance"]'::jsonb, '["travel_hospitality"]'::jsonb),
  ('TRV-003', 'No Clear Traveller This Is For', 'Budget backpackers, families, business travellers and luxury guests want completely different things, and no one type has been chosen.', 'Idea & Validation', 'Travel Guest Clarity', 'external', 2, 4, 8, '["Target guest described as everyone", "Pricing aimed at several very different budgets", "No idea where this traveller currently books", "Same offer for families and solo travellers", "No conversation with a real traveller yet"]'::jsonb, '["travel_hospitality"]'::jsonb),
  ('TRV-004', 'Real Cost of Hosting Never Worked Out', 'The cost of actually serving one guest or running one trip has never been calculated properly.', 'Idea & Validation', 'Travel Cost Reality', 'external', 4, 5, 9, '["Cost per guest or per trip unknown", "Cleaning, linen, utilities and staff not counted", "Platform commission not considered", "Cost of empty nights or unsold seats ignored", "Price set by looking at competitors only"]'::jsonb, '["travel_hospitality"]'::jsonb),
  ('TRV-005', 'Booking Platforms Take Most of the Margin', 'Nearly all guests arrive through booking sites that charge heavy commission and own the guest relationship.', 'Sales & Revenue', 'Travel Platform Dependence', 'external', 4, 6, 9, '["Most bookings through one or two platforms", "Commission taking a large share of the rate", "No direct booking route", "Guest contact details held by the platform", "Platform discounts effectively compulsory"]'::jsonb, '["travel_hospitality"]'::jsonb),
  ('TRV-006', 'Reviews Now Decide Whether Anyone Books', 'Public ratings drive most bookings, and a run of poor reviews cuts demand within weeks.', 'Sales & Revenue', 'Travel Reputation', 'external', 4, 6, 9, '["Most bookings influenced by ratings", "No process for responding to reviews", "Complaints not traced back to a cause", "Rating drops noticed late", "No system for asking happy guests to review"]'::jsonb, '["travel_hospitality"]'::jsonb),
  ('TRV-007', 'Service Quality Depends on Who Is on Shift', 'The guest experience changes depending on which staff member is working, because nothing is written down.', 'Operations & Systems', 'Travel Service Consistency', 'external', 3, 5, 9, '["Experience varies by staff member", "No written standards for service", "Training done by watching others", "Complaints about inconsistency", "No check before a guest arrives"]'::jsonb, '["travel_hospitality"]'::jsonb),
  ('TRV-008', 'Cancellations and No Shows Eating Revenue', 'Guests cancel late or fail to arrive, and the room or seat cannot be resold in time.', 'Financial Management', 'Travel Cancellations', 'external', 4, 5, 9, '["Cancellation rate not measured", "No clear cancellation policy", "No deposit or advance taken", "Late cancellations impossible to resell", "Revenue lost to no shows never quantified"]'::jsonb, '["travel_hospitality"]'::jsonb),
  ('TRV-009', 'Pricing Fixed While Demand Moves', 'One rate is charged all year although demand swings enormously between peak and off season.', 'Financial Management', 'Travel Pricing', 'external', 4, 5, 9, '["Same rate charged all year", "Sold out in peak at too low a price", "Empty in the off season at the same price", "No use of minimum stay or advance rules", "Competitor rates never checked"]'::jsonb, '["travel_hospitality"]'::jsonb),
  ('TRV-010', 'Second Property Does Not Match the First', 'A new property or route has opened and the experience, standards and reviews are not the same as the original.', 'Operations & Systems', 'Travel Multi Property', 'external', 3, 6, 9, '["New property rated below the original", "Founder still needed at the first site", "Nothing written down to hand over", "Different suppliers and staff standards per site", "Guests noticing the difference"]'::jsonb, '["travel_hospitality"]'::jsonb),
  ('TRV-011', 'Staff Turnover Resetting Quality', 'Hospitality staff leave frequently, and each departure takes trained service quality with it.', 'Team & Leadership', 'Travel Staffing', 'external', 5, 6, 9, '["High staff turnover", "Quality drops after each departure", "Training repeated from scratch each time", "Key skills held by one or two people", "Pay and conditions not compared to local market"]'::jsonb, '["travel_hospitality"]'::jsonb),
  ('TRV-012', 'Demand Shocks Can Stop Everything', 'Weather, unrest, transport disruption, regulation or a health scare can halt travel to a destination with no warning.', 'Strategy & Planning', 'Travel Demand Shock', 'external', 2, 7, 10, '["Revenue concentrated in one destination", "No plan for a sudden travel halt", "No reserve for a shut period", "Fixed costs continue when travel stops", "Single source market for guests"]'::jsonb, '["travel_hospitality"]'::jsonb),
  ('TRV-013', 'Fixed Costs Rising Faster Than Rates', 'Rent, salaries, utilities and upkeep keep rising while room rates stay under competitive pressure.', 'Financial Management', 'Travel Cost Pressure', 'external', 4, 6, 9, '["Fixed costs rising each year", "Rates held down by competition", "Margin per room night falling", "Break even occupancy climbing", "Costs not reviewed line by line"]'::jsonb, '["travel_hospitality"]'::jsonb),
  ('TRV-014', 'Safety, Insurance and Liability Exposure', 'With more guests, activities and staff, one accident or safety failure could bring serious legal and reputational damage.', 'Operations & Systems', 'Travel Safety and Liability', 'external', 3, 7, 10, '["No safety checks on premises or activities", "Insurance cover not reviewed against real risk", "Staff not trained for emergencies", "No incident record", "Guest waivers or terms not in place"]'::jsonb, '["travel_hospitality"]'::jsonb),
  ('TRV-015', 'Capacity and Capital Now Limit Growth', 'Growth needs more rooms, vehicles or sites, each requiring large capital long before it earns anything.', 'Financial Management', 'Travel Capital Intensity', 'external', 4, 6, 10, '["Growth requires heavy upfront capital", "Existing capacity fully used in peak", "Payback period on new capacity unknown", "Expansion funded from working capital", "No financing arranged for the next step"]'::jsonb, '["travel_hospitality"]'::jsonb)
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
         t.primary_stage_group, '["travel_hospitality"]'::jsonb, z.v
  FROM (VALUES
  ('RC-TRV-001', 'Plan Assumes Steady Bookings', 'The forecast treats every month as if demand were the same.', 'TRV-001', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-TRV-002', 'Quiet Months Not Identified', 'Which months bring almost no travellers has not been checked.', 'TRV-001', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-TRV-003', 'Costs Continue in the Off Season', 'Rent, staff and upkeep run all year while income stops.', 'TRV-001', 'external', 'Operational', 0.71, 'Stage 0'),
  ('RC-TRV-004', 'Annual Numbers Built From a Good Month', 'One strong month has been multiplied by twelve.', 'TRV-001', 'external', 'Psychological', 0.68, 'Stage 0'),
  ('RC-TRV-005', 'No Plan for the Lean Period', 'Nothing has been decided for how to survive the quiet months.', 'TRV-001', 'external', 'Strategic', 0.67, 'Stage 0'),
  ('RC-TRV-006', 'Required Permissions Unknown', 'Which approvals this kind of business needs has not been found out.', 'TRV-002', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-TRV-007', 'Assuming a Property Can Be Let Freely', 'Believing guests can be hosted without any registration or approval.', 'TRV-002', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-TRV-008', 'Local and Municipal Rules Not Checked', 'Rules that differ by city or locality have not been looked at.', 'TRV-002', 'external', 'Knowledge', 0.67, 'Stage 0'),
  ('RC-TRV-009', 'Guest Registration Requirements Unknown', 'What must be recorded about each guest has not been checked.', 'TRV-002', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-TRV-010', 'No Owner for Compliance', 'Nobody has been made responsible for permissions and renewals.', 'TRV-002', 'external', 'Operational', 0.63, 'Stage 0'),
  ('RC-TRV-011', 'Target Guest Described as Everyone', 'No specific traveller type has been chosen to serve.', 'TRV-003', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-TRV-012', 'Pricing Aimed at Several Budgets', 'One price is meant to suit very different spending levels.', 'TRV-003', 'external', 'Strategic', 0.67, 'Stage 0'),
  ('RC-TRV-013', 'Where the Traveller Books Is Unknown', 'How this guest currently finds and books stays has not been studied.', 'TRV-003', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-TRV-014', 'Same Offer for Very Different Guests', 'Families and solo travellers are offered the same thing.', 'TRV-003', 'external', 'Strategic', 0.65, 'Stage 0'),
  ('RC-TRV-015', 'No Conversation With a Real Traveller', 'Nobody who would actually book has been spoken to.', 'TRV-003', 'external', 'Behavioural', 0.64, 'Stage 0'),
  ('RC-TRV-016', 'Cost Per Guest or Trip Unknown', 'What it costs to serve one guest has never been calculated.', 'TRV-004', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-TRV-017', 'Cleaning, Linen and Utilities Not Counted', 'The recurring costs of hosting are left out of the numbers.', 'TRV-004', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-TRV-018', 'Platform Commission Not Considered', 'The cut booking sites take has not been factored in.', 'TRV-004', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-TRV-019', 'Most Bookings Through One or Two Platforms', 'Nearly all demand arrives through a small number of booking sites.', 'TRV-005', 'external', 'Strategic', 0.73, 'Stage 0→1'),
  ('RC-TRV-020', 'Commission Taking a Large Share', 'Platform fees remove a big part of every booking.', 'TRV-005', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-TRV-021', 'No Direct Booking Route', 'There is no way for a guest to book without the platform.', 'TRV-005', 'external', 'Strategic', 0.70, 'Stage 0→1'),
  ('RC-TRV-022', 'Guest Details Held by the Platform', 'The business cannot contact its own past guests.', 'TRV-005', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-TRV-023', 'Platform Discounts Effectively Compulsory', 'Joining offers is necessary just to stay visible in listings.', 'TRV-005', 'external', 'Strategic', 0.66, 'Stage 0→1'),
  ('RC-TRV-024', 'Most Bookings Influenced by Ratings', 'Whether travellers book at all depends on public review scores.', 'TRV-006', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-TRV-025', 'No Process for Responding to Reviews', 'Feedback goes unanswered and unexamined.', 'TRV-006', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-TRV-026', 'Complaints Not Traced to a Cause', 'Reviews are read but never linked back to an operational failure.', 'TRV-006', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-TRV-027', 'Rating Drops Noticed Late', 'A fall in score is spotted only after bookings have dropped.', 'TRV-006', 'external', 'Operational', 0.66, 'Stage 0→1'),
  ('RC-TRV-028', 'No System for Asking Happy Guests', 'Satisfied guests are never invited to leave a review.', 'TRV-006', 'external', 'Behavioural', 0.67, 'Stage 0→1'),
  ('RC-TRV-029', 'No Written Service Standards', 'What good service means here has never been defined.', 'TRV-007', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-TRV-030', 'Experience Varies by Staff Member', 'What a guest receives depends on who is working.', 'TRV-007', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-TRV-031', 'Training Done by Watching Others', 'New staff learn by copying rather than being taught a standard.', 'TRV-007', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-TRV-032', 'No Check Before a Guest Arrives', 'Nothing is verified before the guest walks in.', 'TRV-007', 'external', 'Operational', 0.67, 'Stage 0→1'),
  ('RC-TRV-033', 'Complaints About Inconsistency', 'Guests report that the experience was not what they expected.', 'TRV-007', 'external', 'Operational', 0.65, 'Stage 0→1'),
  ('RC-TRV-034', 'Cancellation Rate Not Measured', 'How often bookings fall through is not tracked.', 'TRV-008', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-TRV-035', 'No Clear Cancellation Policy', 'Terms are decided case by case rather than set in advance.', 'TRV-008', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-TRV-036', 'No Deposit or Advance Taken', 'Bookings are held without any payment committing the guest.', 'TRV-008', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-TRV-037', 'Late Cancellations Impossible to Resell', 'Rooms or seats free up too late to find another guest.', 'TRV-008', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-TRV-038', 'No Show Losses Never Quantified', 'The revenue lost to guests who do not arrive is unknown.', 'TRV-008', 'external', 'Knowledge', 0.67, 'Stage 0→1'),
  ('RC-TRV-039', 'Same Rate Charged All Year', 'One price is used regardless of how demand moves.', 'TRV-009', 'external', 'Behavioural', 0.72, 'Stage 0→1'),
  ('RC-TRV-040', 'Sold Out in Peak at Too Low a Price', 'Full occupancy in peak season signals the rate was too low.', 'TRV-009', 'external', 'Strategic', 0.70, 'Stage 0→1'),
  ('RC-TRV-041', 'Nothing Written Down to Hand Over', 'The original site runs on knowledge held only in peoples heads.', 'TRV-010', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-TRV-042', 'Founder Still Needed at the First Site', 'The original property cannot run without the founder present.', 'TRV-010', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-TRV-043', 'Different Standards Per Site', 'Each location sets its own suppliers and service habits.', 'TRV-010', 'external', 'Operational', 0.68, 'Stage 1→10+'),
  ('RC-TRV-044', 'Expanded Before the First Was Systemised', 'A second site opened before the first was repeatable.', 'TRV-010', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-TRV-045', 'Guests Noticing the Difference', 'Reviews show the properties are not the same.', 'TRV-010', 'external', 'Operational', 0.66, 'Stage 1→10+'),
  ('RC-TRV-046', 'High Staff Turnover', 'Service staff leave frequently.', 'TRV-011', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-TRV-047', 'Quality Drops After Each Departure', 'Guest experience falls noticeably whenever someone leaves.', 'TRV-011', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-TRV-048', 'Training Repeated From Scratch', 'Every new hire is taught from nothing with no materials.', 'TRV-011', 'external', 'Operational', 0.68, 'Stage 1→10+'),
  ('RC-TRV-049', 'Key Skills Held by One or Two People', 'Critical capability sits with very few individuals.', 'TRV-011', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-TRV-050', 'Pay Not Compared to Local Market', 'Nobody has checked what competing employers offer.', 'TRV-011', 'external', 'Knowledge', 0.66, 'Stage 1→10+'),
  ('RC-TRV-051', 'Revenue Concentrated in One Destination', 'All income depends on travellers coming to a single place.', 'TRV-012', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-TRV-052', 'No Plan for a Sudden Travel Halt', 'Nothing has been prepared for demand stopping without warning.', 'TRV-012', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-TRV-053', 'No Reserve for a Shut Period', 'There is no cash held back to survive a closure.', 'TRV-012', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-TRV-054', 'Fixed Costs Continue When Travel Stops', 'Rent, salaries and upkeep run on with no revenue.', 'TRV-012', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-TRV-055', 'Single Source Market for Guests', 'Guests come overwhelmingly from one region or country.', 'TRV-012', 'external', 'Strategic', 0.68, 'Stage 1→10+'),
  ('RC-TRV-056', 'Fixed Costs Rising Each Year', 'Rent, salaries and utilities climb steadily.', 'TRV-013', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-TRV-057', 'Rates Held Down by Competition', 'Price cannot rise because competitors hold theirs low.', 'TRV-013', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-TRV-058', 'Break Even Occupancy Climbing', 'A higher share of rooms must sell just to cover costs.', 'TRV-013', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-TRV-059', 'Costs Not Reviewed Line by Line', 'Nobody has gone through the cost base looking for waste.', 'TRV-013', 'external', 'Behavioural', 0.67, 'Stage 1→10+'),
  ('RC-TRV-060', 'No Safety Checks on Premises or Activities', 'Nothing is inspected on a fixed schedule for guest safety.', 'TRV-014', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-TRV-061', 'Insurance Not Reviewed Against Real Risk', 'Cover was taken once and never matched to what the business now does.', 'TRV-014', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-TRV-062', 'Staff Not Trained for Emergencies', 'Nobody knows what to do if something serious happens.', 'TRV-014', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-TRV-063', 'No Incident Record', 'Accidents and near misses are not written down anywhere.', 'TRV-014', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-TRV-064', 'Growth Requires Heavy Upfront Capital', 'Each additional room, vehicle or site needs large money first.', 'TRV-015', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-TRV-065', 'Payback Period on New Capacity Unknown', 'How long new capacity takes to repay itself has not been worked out.', 'TRV-015', 'external', 'Knowledge', 0.70, 'Stage 1→10+'),
  ('RC-TRV-066', 'Expansion Funded From Working Capital', 'Growth is being paid for out of money needed to operate.', 'TRV-015', 'external', 'Operational', 0.71, 'Stage 1→10+')
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
         '["travel_hospitality"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-TRV-001', 'Which months of the year will be busy, and which will be almost empty?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-001', 'RC-TRV-002', 1, 'Stage 0'),
  ('S0-TRV-002', 'Does your plan assume the same number of bookings every month?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-001', 'RC-TRV-001', 1, 'Stage 0'),
  ('S0-TRV-003', 'What costs keep running in the quiet months when nobody is coming?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-001', 'RC-TRV-003', 2, 'Stage 0'),
  ('S0-TRV-004', 'Did you build your yearly numbers from one good month?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-001', 'RC-TRV-004', 2, 'Stage 0'),
  ('S0-TRV-005', 'How will you get through the lean season?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-001', 'RC-TRV-005', 2, 'Stage 0'),
  ('S0-TRV-006', 'Do you know which permissions you need to host guests or run trips?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-002', 'RC-TRV-006', 1, 'Stage 0'),
  ('S0-TRV-007', 'Do you think you can let out a property to guests without any approval?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-002', 'RC-TRV-007', 1, 'Stage 0'),
  ('S0-TRV-008', 'Have you checked the rules for your particular city or locality?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-002', 'RC-TRV-008', 2, 'Stage 0'),
  ('S0-TRV-009', 'Do you know what details you must record about every guest?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-002', 'RC-TRV-009', 2, 'Stage 0'),
  ('S0-TRV-010', 'Who would handle your permissions and renewals?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-002', 'RC-TRV-010', 2, 'Stage 0'),
  ('S0-TRV-011', 'Who exactly is this for, budget travellers, families, business guests or luxury?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-003', 'RC-TRV-011', 1, 'Stage 0'),
  ('S0-TRV-012', 'Where does that kind of traveller book their stay today?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-003', 'RC-TRV-013', 2, 'Stage 0'),
  ('S0-TRV-013', 'Is one price meant to suit very different budgets?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-003', 'RC-TRV-012', 2, 'Stage 0'),
  ('S0-TRV-014', 'Do you know what it costs you to host one guest for one night?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-004', 'RC-TRV-016', 1, 'Stage 0'),
  ('S0-TRV-015', 'Have you counted cleaning, linen, utilities and staff in that cost?', 'open_text', 'Idea & Validation', 'CORE', 'TRV-004', 'RC-TRV-017', 2, 'Stage 0'),
  ('S01-TRV-001', 'What share of your bookings comes through booking platforms?', 'open_text', 'Sales & Revenue', 'CORE', 'TRV-005', 'RC-TRV-019', 2, 'Stage 0→1'),
  ('S01-TRV-002', 'After commission, how much of the rate actually reaches you?', 'open_text', 'Financial Management', 'CORE', 'TRV-005', 'RC-TRV-020', 2, 'Stage 0→1'),
  ('S01-TRV-003', 'Can a guest book with you directly without the platform?', 'open_text', 'Sales & Revenue', 'CORE', 'TRV-005', 'RC-TRV-021', 2, 'Stage 0→1'),
  ('S01-TRV-004', 'Do you have contact details for guests who stayed with you?', 'open_text', 'Sales & Revenue', 'CORE', 'TRV-005', 'RC-TRV-022', 2, 'Stage 0→1'),
  ('S01-TRV-005', 'Do you join platform offers by choice or to stay visible?', 'open_text', 'Sales & Revenue', 'CORE', 'TRV-005', 'RC-TRV-023', 3, 'Stage 0→1'),
  ('S01-TRV-006', 'How much of your business depends on your rating?', 'open_text', 'Sales & Revenue', 'CORE', 'TRV-006', 'RC-TRV-024', 2, 'Stage 0→1'),
  ('S01-TRV-007', 'When a bad review comes in, what happens next?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-006', 'RC-TRV-025', 2, 'Stage 0→1'),
  ('S01-TRV-008', 'Do you trace complaints back to what actually went wrong?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-006', 'RC-TRV-026', 2, 'Stage 0→1'),
  ('S01-TRV-009', 'How quickly would you notice your rating falling?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-006', 'RC-TRV-027', 2, 'Stage 0→1'),
  ('S01-TRV-010', 'Do you ask happy guests to leave a review?', 'open_text', 'Sales & Revenue', 'CORE', 'TRV-006', 'RC-TRV-028', 2, 'Stage 0→1'),
  ('S01-TRV-011', 'Would a guest get the same experience whoever was on shift?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-007', 'RC-TRV-030', 2, 'Stage 0→1'),
  ('S01-TRV-012', 'Is there anything written down about how guests should be looked after?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-007', 'RC-TRV-029', 2, 'Stage 0→1'),
  ('S01-TRV-013', 'How does a new staff member learn your way of doing things?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-007', 'RC-TRV-031', 2, 'Stage 0→1'),
  ('S01-TRV-014', 'Does anyone check the room or arrangement before the guest arrives?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-007', 'RC-TRV-032', 2, 'Stage 0→1'),
  ('S01-TRV-015', 'Out of 100 bookings, how many cancel or never arrive?', 'open_text', 'Financial Management', 'CORE', 'TRV-008', 'RC-TRV-034', 2, 'Stage 0→1'),
  ('S01-TRV-016', 'Do you have a clear cancellation policy guests agree to?', 'open_text', 'Financial Management', 'CORE', 'TRV-008', 'RC-TRV-035', 2, 'Stage 0→1'),
  ('S01-TRV-017', 'Do you take any advance or deposit when someone books?', 'open_text', 'Financial Management', 'CORE', 'TRV-008', 'RC-TRV-036', 2, 'Stage 0→1'),
  ('S01-TRV-018', 'When someone cancels late, can you fill that room again?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-008', 'RC-TRV-037', 2, 'Stage 0→1'),
  ('S01-TRV-019', 'Do you charge the same rate in peak season as in the quiet months?', 'open_text', 'Financial Management', 'CORE', 'TRV-009', 'RC-TRV-039', 2, 'Stage 0→1'),
  ('S01-TRV-020', 'If you sell out every peak weekend, was your price too low?', 'open_text', 'Financial Management', 'CORE', 'TRV-009', 'RC-TRV-040', 3, 'Stage 0→1'),
  ('S10-TRV-001', 'Does your newest property match the rating of your first one?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-010', 'RC-TRV-045', 2, 'Stage 1→10+'),
  ('S10-TRV-002', 'Is there anything written down that a new site could run from?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-010', 'RC-TRV-041', 2, 'Stage 1→10+'),
  ('S10-TRV-003', 'Can your original property run properly without you there?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-010', 'RC-TRV-042', 3, 'Stage 1→10+'),
  ('S10-TRV-004', 'Do all your sites use the same suppliers and standards?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-010', 'RC-TRV-043', 2, 'Stage 1→10+'),
  ('S10-TRV-005', 'Was the first site fully systemised before you opened the second?', 'open_text', 'Strategy & Planning', 'CORE', 'TRV-010', 'RC-TRV-044', 3, 'Stage 1→10+'),
  ('S10-TRV-006', 'How many service staff have left in the last year?', 'open_text', 'Team & Leadership', 'CORE', 'TRV-011', 'RC-TRV-046', 2, 'Stage 1→10+'),
  ('S10-TRV-007', 'Does guest experience dip for a while after someone leaves?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-011', 'RC-TRV-047', 2, 'Stage 1→10+'),
  ('S10-TRV-008', 'Do you have training material, or does each new hire start from nothing?', 'open_text', 'Team & Leadership', 'CORE', 'TRV-011', 'RC-TRV-048', 2, 'Stage 1→10+'),
  ('S10-TRV-009', 'If your best staff member left tomorrow, what would break?', 'open_text', 'Team & Leadership', 'CORE', 'TRV-011', 'RC-TRV-049', 3, 'Stage 1→10+'),
  ('S10-TRV-010', 'Do you know what other employers nearby pay for the same roles?', 'open_text', 'Team & Leadership', 'CORE', 'TRV-011', 'RC-TRV-050', 2, 'Stage 1→10+'),
  ('S10-TRV-011', 'What share of your revenue depends on one destination?', 'open_text', 'Strategy & Planning', 'CORE', 'TRV-012', 'RC-TRV-051', 2, 'Stage 1→10+'),
  ('S10-TRV-012', 'If travel to your area stopped for three months, what would you do?', 'open_text', 'Strategy & Planning', 'CORE', 'TRV-012', 'RC-TRV-052', 3, 'Stage 1→10+'),
  ('S10-TRV-013', 'How many months could you cover costs with no guests at all?', 'open_text', 'Financial Management', 'CORE', 'TRV-012', 'RC-TRV-053', 3, 'Stage 1→10+'),
  ('S10-TRV-014', 'Which costs keep running even when nobody is travelling?', 'open_text', 'Financial Management', 'CORE', 'TRV-012', 'RC-TRV-054', 2, 'Stage 1→10+'),
  ('S10-TRV-015', 'Where do most of your guests come from, and is it one place?', 'open_text', 'Sales & Revenue', 'CORE', 'TRV-012', 'RC-TRV-055', 2, 'Stage 1→10+'),
  ('S10-TRV-016', 'How much have your fixed costs risen in the last two years?', 'open_text', 'Financial Management', 'CORE', 'TRV-013', 'RC-TRV-056', 2, 'Stage 1→10+'),
  ('S10-TRV-017', 'Have your rates risen in the same period?', 'open_text', 'Financial Management', 'CORE', 'TRV-013', 'RC-TRV-057', 2, 'Stage 1→10+'),
  ('S10-TRV-018', 'What occupancy do you now need just to break even?', 'open_text', 'Financial Management', 'CORE', 'TRV-013', 'RC-TRV-058', 3, 'Stage 1→10+'),
  ('S10-TRV-019', 'When did you last go through your costs line by line?', 'open_text', 'Financial Management', 'CORE', 'TRV-013', 'RC-TRV-059', 2, 'Stage 1→10+'),
  ('S10-TRV-020', 'Is anything checked for guest safety on a fixed schedule?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-014', 'RC-TRV-060', 3, 'Stage 1→10+'),
  ('S10-TRV-021', 'Does your insurance actually cover what you do today?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-014', 'RC-TRV-061', 3, 'Stage 1→10+'),
  ('S10-TRV-022', 'Would your staff know what to do in an emergency?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-014', 'RC-TRV-062', 3, 'Stage 1→10+'),
  ('S10-TRV-023', 'Where do you record accidents and near misses?', 'open_text', 'Operations & Systems', 'CORE', 'TRV-014', 'RC-TRV-063', 2, 'Stage 1→10+'),
  ('S10-TRV-024', 'How much money would adding your next room or vehicle need?', 'open_text', 'Financial Management', 'CORE', 'TRV-015', 'RC-TRV-064', 2, 'Stage 1→10+'),
  ('S10-TRV-025', 'How long would that new capacity take to pay for itself?', 'open_text', 'Financial Management', 'CORE', 'TRV-015', 'RC-TRV-065', 3, 'Stage 1→10+')
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
  ('S0-TRV-001', 'willingness-to-pay'),
  ('S0-TRV-002', 'willingness-to-pay'),
  ('S0-TRV-003', 'willingness-to-pay'),
  ('S0-TRV-004', 'willingness-to-pay'),
  ('S0-TRV-005', 'willingness-to-pay'),
  ('S0-TRV-006', 'technical-quality'),
  ('S0-TRV-007', 'technical-quality'),
  ('S0-TRV-008', 'technical-quality'),
  ('S0-TRV-009', 'technical-quality'),
  ('S0-TRV-010', 'technical-quality'),
  ('S0-TRV-011', 'icp'),
  ('S0-TRV-012', 'icp'),
  ('S0-TRV-013', 'icp'),
  ('S0-TRV-014', 'willingness-to-pay'),
  ('S0-TRV-015', 'willingness-to-pay'),
  ('S01-TRV-001', 'channel-strategy'),
  ('S01-TRV-002', 'channel-strategy'),
  ('S01-TRV-003', 'channel-strategy'),
  ('S01-TRV-004', 'channel-strategy'),
  ('S01-TRV-005', 'channel-strategy'),
  ('S01-TRV-006', 'channel-strategy'),
  ('S01-TRV-007', 'channel-strategy'),
  ('S01-TRV-008', 'channel-strategy'),
  ('S01-TRV-009', 'channel-strategy'),
  ('S01-TRV-010', 'channel-strategy'),
  ('S01-TRV-011', 'technical-quality'),
  ('S01-TRV-012', 'technical-quality'),
  ('S01-TRV-013', 'technical-quality'),
  ('S01-TRV-014', 'technical-quality'),
  ('S01-TRV-015', 'willingness-to-pay'),
  ('S01-TRV-016', 'willingness-to-pay'),
  ('S01-TRV-017', 'willingness-to-pay'),
  ('S01-TRV-018', 'willingness-to-pay'),
  ('S01-TRV-019', 'willingness-to-pay'),
  ('S01-TRV-020', 'willingness-to-pay'),
  ('S10-TRV-001', 'technical-quality'),
  ('S10-TRV-002', 'technical-quality'),
  ('S10-TRV-003', 'technical-quality'),
  ('S10-TRV-004', 'technical-quality'),
  ('S10-TRV-005', 'technical-quality'),
  ('S10-TRV-006', 'technical-quality'),
  ('S10-TRV-007', 'technical-quality'),
  ('S10-TRV-008', 'technical-quality'),
  ('S10-TRV-009', 'technical-quality'),
  ('S10-TRV-010', 'technical-quality'),
  ('S10-TRV-011', 'channel-strategy'),
  ('S10-TRV-012', 'channel-strategy'),
  ('S10-TRV-013', 'channel-strategy'),
  ('S10-TRV-014', 'channel-strategy'),
  ('S10-TRV-015', 'channel-strategy'),
  ('S10-TRV-016', 'willingness-to-pay'),
  ('S10-TRV-017', 'willingness-to-pay'),
  ('S10-TRV-018', 'willingness-to-pay'),
  ('S10-TRV-019', 'willingness-to-pay'),
  ('S10-TRV-020', 'technical-quality'),
  ('S10-TRV-021', 'technical-quality'),
  ('S10-TRV-022', 'technical-quality'),
  ('S10-TRV-023', 'technical-quality'),
  ('S10-TRV-024', 'willingness-to-pay'),
  ('S10-TRV-025', 'willingness-to-pay')
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
         '["travel_hospitality"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-TRV-001', 'Ideation — Travel Seasonality Basics', 'TRV-001', '["RC-TRV-001", "RC-TRV-002", "RC-TRV-004"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Find out month by month when travellers actually come to your area.", "Build your yearly numbers from that pattern, not from one good month.", "Mark the months that will bring almost nothing."]'::jsonb, '[{"name": "Month by Month Demand", "brief": "Building the year from the real seasonal pattern."}]'::jsonb),
  ('INT-TRV-002', 'Ideation — Travel Seasonality Basics', 'TRV-001', '["RC-TRV-003", "RC-TRV-005"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Add up what you must spend in a month with no guests.", "Multiply by the number of lean months.", "Decide now how that will be funded."]'::jsonb, '[{"name": "Survive the Off Season", "brief": "Knowing the cost of the quiet months before they arrive."}]'::jsonb),
  ('INT-TRV-003', 'Ideation — Travel Licensing Basics', 'TRV-002', '["RC-TRV-006", "RC-TRV-007"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Find out which permissions your kind of business needs.", "Ask someone already running one locally.", "Write down the cost and time for each."]'::jsonb, '[{"name": "Find Your Permissions", "brief": "Identifying what is legally required before hosting anyone."}]'::jsonb),
  ('INT-TRV-004', 'Ideation — Travel Licensing Basics', 'TRV-002', '["RC-TRV-008", "RC-TRV-009"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Check the rules for your specific city or locality.", "Find out what must be recorded about each guest.", "Set up that record keeping before your first booking."]'::jsonb, '[{"name": "Local Rules and Guest Records", "brief": "Checking local requirements and guest registration duties."}]'::jsonb),
  ('INT-TRV-005', 'Ideation — Travel Licensing Basics', 'TRV-002', '["RC-TRV-010"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Name one person responsible for permissions and renewals.", "Keep a dated list of what must be obtained or renewed.", "Review it before every season."]'::jsonb, '[{"name": "One Compliance Owner", "brief": "A single accountable person and a dated list."}]'::jsonb),
  ('INT-TRV-006', 'Ideation — Travel Guest Clarity', 'TRV-003', '["RC-TRV-011", "RC-TRV-012"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Pick one traveller type to serve first.", "Set your price for that one group.", "Stop trying to suit every budget at once."]'::jsonb, '[{"name": "One Traveller, One Price Band", "brief": "Choosing a single guest type instead of serving all budgets."}]'::jsonb),
  ('INT-TRV-007', 'Ideation — Travel Guest Clarity', 'TRV-003', '["RC-TRV-013", "RC-TRV-014", "RC-TRV-015"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Find out where your chosen traveller books today.", "Talk to 10 of them about what they look for and what annoys them.", "Shape the offer around their answers."]'::jsonb, '[{"name": "Study and Talk to Travellers", "brief": "Learning how your guest actually chooses and books."}]'::jsonb),
  ('INT-TRV-008', 'Ideation — Travel Cost Reality', 'TRV-004', '["RC-TRV-016", "RC-TRV-017"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Work out the full cost of hosting one guest for one night.", "Include cleaning, linen, utilities, staff and upkeep.", "Compare it against the price you had in mind."]'::jsonb, '[{"name": "Cost of One Night", "brief": "A complete cost for serving a single guest."}]'::jsonb),
  ('INT-TRV-009', 'Ideation — Travel Cost Reality', 'TRV-004', '["RC-TRV-018"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Find out what booking platforms charge per booking.", "Subtract that from your price.", "Check what is actually left."]'::jsonb, '[{"name": "Count the Platform Cut", "brief": "Knowing what the booking site takes before pricing."}]'::jsonb),
  ('INT-TRV-010', 'Ideation — Travel Cost Reality', 'TRV-004', '["RC-TRV-016", "RC-TRV-018"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Work out what an empty night or unsold seat costs you.", "Include that in your average.", "Price so that partly full months still work."]'::jsonb, '[{"name": "Cost of an Empty Night", "brief": "Pricing with realistic occupancy rather than a full house."}]'::jsonb),
  ('INT-TRV-011', 'Validation to Traction — Travel Platform Dependence', 'TRV-005', '["RC-TRV-019", "RC-TRV-020"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Work out what you actually keep per booking on each platform.", "Compare that with a direct booking.", "Decide how much platform volume you really want."]'::jsonb, '[{"name": "What You Keep Per Booking", "brief": "Comparing net rate across platform and direct."}]'::jsonb),
  ('INT-TRV-012', 'Validation to Traction — Travel Platform Dependence', 'TRV-005', '["RC-TRV-021", "RC-TRV-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Set up one simple direct booking route.", "Collect guest contact details with consent at check in.", "Give past guests a reason to book direct next time."]'::jsonb, '[{"name": "Build a Direct Channel", "brief": "One booking route the business owns outright."}]'::jsonb),
  ('INT-TRV-013', 'Validation to Traction — Travel Platform Dependence', 'TRV-005', '["RC-TRV-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["List every platform offer you are currently in.", "Work out what each costs you per booking.", "Exit the ones that lose money and watch what happens."]'::jsonb, '[{"name": "Audit Platform Offers", "brief": "Checking which visibility deals actually cost more than they bring."}]'::jsonb),
  ('INT-TRV-014', 'Validation to Traction — Travel Reputation', 'TRV-006', '["RC-TRV-024", "RC-TRV-025", "RC-TRV-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Give one person responsibility for reading and replying to reviews.", "Check your rating weekly, not when bookings fall.", "Reply to every review, good or bad."]'::jsonb, '[{"name": "Watch and Answer Reviews", "brief": "One owner, a weekly check and a reply to every review."}]'::jsonb),
  ('INT-TRV-015', 'Validation to Traction — Travel Reputation', 'TRV-006', '["RC-TRV-026", "RC-TRV-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Trace each complaint back to what actually went wrong.", "Fix the cause, not just the review.", "Ask satisfied guests to leave a review before they leave."]'::jsonb, '[{"name": "Fix the Cause, Ask the Happy", "brief": "Tracing complaints to their source and gathering good reviews."}]'::jsonb),
  ('INT-TRV-016', 'Validation to Traction — Travel Service Consistency', 'TRV-007', '["RC-TRV-029", "RC-TRV-030", "RC-TRV-031"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Write down what good service looks like here, step by step.", "Train every staff member against it.", "Stop letting people learn by watching."]'::jsonb, '[{"name": "Written Service Standard", "brief": "A defined standard so the guest experience does not depend on the shift."}]'::jsonb),
  ('INT-TRV-017', 'Validation to Traction — Travel Service Consistency', 'TRV-007', '["RC-TRV-032", "RC-TRV-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Add one check before every guest arrives.", "Use a short list covering cleanliness, supplies and readiness.", "Nobody checks in until it is done."]'::jsonb, '[{"name": "Pre Arrival Check", "brief": "One fixed check before every guest walks in."}]'::jsonb),
  ('INT-TRV-018', 'Validation to Traction — Travel Cancellations', 'TRV-008', '["RC-TRV-034", "RC-TRV-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Record how many bookings cancel or fail to arrive.", "Work out what that costs you in a month.", "Track it alongside occupancy."]'::jsonb, '[{"name": "Measure Cancellations", "brief": "Putting a real number on lost bookings and no shows."}]'::jsonb),
  ('INT-TRV-019', 'Validation to Traction — Travel Cancellations', 'TRV-008', '["RC-TRV-035", "RC-TRV-036"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Write one clear cancellation policy and show it before booking.", "Take an advance or deposit on every booking.", "Apply it consistently."]'::jsonb, '[{"name": "Deposit and Clear Policy", "brief": "Commitment at the point of booking and terms set in advance."}]'::jsonb),
  ('INT-TRV-020', 'Validation to Traction — Travel Cancellations', 'TRV-008', '["RC-TRV-037"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Set a cut off after which cancellation is not free.", "Keep a waiting list for busy dates.", "Offer freed up rooms to that list immediately."]'::jsonb, '[{"name": "Refill Late Cancellations", "brief": "A cut off plus a waiting list so freed rooms get resold."}]'::jsonb),
  ('INT-TRV-021', 'Validation to Traction — Travel Pricing', 'TRV-009', '["RC-TRV-039", "RC-TRV-040"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Set different rates for peak, normal and quiet periods.", "Raise the peak rate until you are no longer instantly full.", "Review rates every season."]'::jsonb, '[{"name": "Rates That Follow Demand", "brief": "Separate pricing for peak, normal and lean periods."}]'::jsonb),
  ('INT-TRV-022', 'Validation to Traction — Travel Pricing', 'TRV-009', '["RC-TRV-039"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Use minimum stay or advance booking rules on busy dates.", "Offer lower rates only in genuinely quiet periods.", "Check what comparable places nearby are charging."]'::jsonb, '[{"name": "Rules on Busy Dates", "brief": "Minimum stay and advance rules instead of one flat rate."}]'::jsonb),
  ('INT-TRV-023', 'Growth to Maturity — Travel Multi Property', 'TRV-010', '["RC-TRV-041", "RC-TRV-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write down how the original property actually runs, step by step.", "Use that to set up every new site.", "Do not open another until it exists."]'::jsonb, '[{"name": "Systemise Before You Expand", "brief": "Documenting the first site so the next can copy it."}]'::jsonb),
  ('INT-TRV-024', 'Growth to Maturity — Travel Multi Property', 'TRV-010', '["RC-TRV-042", "RC-TRV-043", "RC-TRV-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Use the same suppliers and standards across every site.", "Spend a week away from the first property and see what breaks.", "Fix that before expanding further."]'::jsonb, '[{"name": "Same Standards, No Founder", "brief": "Common standards and a site that runs without the founder."}]'::jsonb),
  ('INT-TRV-025', 'Growth to Maturity — Travel Staffing', 'TRV-011', '["RC-TRV-048", "RC-TRV-049"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Build simple training material for each role.", "Cross train so no single person holds a critical skill.", "Use the material for every new hire."]'::jsonb, '[{"name": "Training Material and Cross Training", "brief": "Reusable training so quality does not reset with each hire."}]'::jsonb),
  ('INT-TRV-026', 'Growth to Maturity — Travel Staffing', 'TRV-011', '["RC-TRV-046", "RC-TRV-047", "RC-TRV-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Ask leavers why they went.", "Compare your pay and conditions against nearby employers.", "Fix the biggest reason before hiring again."]'::jsonb, '[{"name": "Understand Why They Leave", "brief": "Exit reasons and a market pay comparison."}]'::jsonb),
  ('INT-TRV-027', 'Growth to Maturity — Travel Demand Shock', 'TRV-012', '["RC-TRV-052", "RC-TRV-053", "RC-TRV-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["List the costs that continue if travel stops entirely.", "Hold or arrange enough to cover several months of those.", "Write what you would do in the first week of a shutdown."]'::jsonb, '[{"name": "Shutdown Plan and Reserve", "brief": "Knowing the cost of a stoppage and holding cover for it."}]'::jsonb),
  ('INT-TRV-028', 'Growth to Maturity — Travel Demand Shock', 'TRV-012', '["RC-TRV-051", "RC-TRV-055"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Measure what share of guests come from one region or market.", "Build demand from at least one other source.", "Track the mix every quarter."]'::jsonb, '[{"name": "Widen Your Source Markets", "brief": "Reducing dependence on one destination or one guest origin."}]'::jsonb),
  ('INT-TRV-029', 'Growth to Maturity — Travel Cost Pressure', 'TRV-013', '["RC-TRV-056", "RC-TRV-058"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Work out the occupancy you need just to break even.", "Track it every month as costs move.", "Act when it climbs, not after a bad season."]'::jsonb, '[{"name": "Break Even Occupancy", "brief": "One number that shows when the cost base has outgrown the rate."}]'::jsonb),
  ('INT-TRV-030', 'Growth to Maturity — Travel Cost Pressure', 'TRV-013', '["RC-TRV-057", "RC-TRV-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Go through every cost line and question it.", "Remove or renegotiate the largest avoidable ones.", "Look for value you can charge for instead of cutting rate."]'::jsonb, '[{"name": "Line by Line Cost Review", "brief": "Questioning every cost rather than competing only on price."}]'::jsonb),
  ('INT-TRV-031', 'Growth to Maturity — Travel Safety and Liability', 'TRV-014', '["RC-TRV-060", "RC-TRV-062"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Set a fixed schedule for safety checks on premises and activities.", "Train every staff member on what to do in an emergency.", "Keep a signed record of both."]'::jsonb, '[{"name": "Safety Checks and Emergency Training", "brief": "Scheduled inspections and staff who know what to do."}]'::jsonb),
  ('INT-TRV-032', 'Growth to Maturity — Travel Safety and Liability', 'TRV-014', '["RC-TRV-061", "RC-TRV-063"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Review your insurance against what the business actually does now.", "Start recording every accident and near miss.", "Use those records to close the repeat causes."]'::jsonb, '[{"name": "Match Cover to Real Risk", "brief": "Insurance reviewed against current activity, plus an incident log."}]'::jsonb),
  ('INT-TRV-033', 'Growth to Maturity — Travel Capital Intensity', 'TRV-015', '["RC-TRV-064", "RC-TRV-065"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Work out the full cost of your next room, vehicle or site.", "Calculate how many months of real occupancy repay it.", "Only commit if that period is acceptable."]'::jsonb, '[{"name": "Payback Before You Build", "brief": "Knowing how long new capacity takes to repay itself."}]'::jsonb),
  ('INT-TRV-034', 'Growth to Maturity — Travel Capital Intensity', 'TRV-015', '["RC-TRV-066"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Stop funding expansion from money you need to operate.", "Arrange proper financing before committing.", "Keep a minimum operating balance untouched."]'::jsonb, '[{"name": "Fund Growth Separately", "brief": "Keeping expansion money apart from working capital."}]'::jsonb)
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
        ('Human Resources & HRTech', 'hrtech', 'HRT', r"""-- ============================================================================
-- Ally :: Industry seed -- HUMAN RESOURCES & HRTECH (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: hrtech
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (HRT-001, RC-HRT-014, S0-HRT-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : questions avoid naming specific labour statutes, deduction rates
--            or thresholds, because these differ by state and change often.
--            They ask the founder what applies to THEM.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (adoption, sales cycle, customisation load,
--            implementation, accuracy) starts at Stage 0->1; churn, support
--            load, security, regulatory change and competition at 1->10+.
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
  ('HRT-001', 'Nobody Has Checked Who Actually Buys HR Tools', 'In most companies HR uses the tool, finance approves the spend and leadership decides, and none of that has been worked out.', 'Idea & Validation', 'HRTech Buyer Clarity', 'external', 4, 5, 9, '["Buyer and user assumed to be the same person", "No idea who signs off HR spending", "Pitch aimed at whoever will listen", "Company size not chosen", "No conversation with a real HR buyer yet"]'::jsonb, '["hrtech"]'::jsonb),
  ('HRT-002', 'Solving a Problem Companies Live With Happily', 'The problem is real but companies have tolerated it for years, so nobody will pay to fix it.', 'Idea & Validation', 'HRTech Problem Urgency', 'external', 1, 5, 9, '["Problem described as inefficiency rather than pain", "Companies already coping with spreadsheets", "No cost attached to the problem", "Nobody has asked to be rid of it", "Assuming annoyance equals willingness to pay"]'::jsonb, '["hrtech"]'::jsonb),
  ('HRT-003', 'Employee Data Sensitivity Not Considered', 'The idea will hold salary, performance and personal details about real employees, and nothing has been decided about handling it.', 'Idea & Validation', 'HRTech Data Basics', 'external', 3, 5, 9, '["No plan for consent or employee notice", "No decision on where data is stored", "Anyone on the team able to see employee records", "Salary and performance data treated casually", "No thought about what happens on exit"]'::jsonb, '["hrtech"]'::jsonb),
  ('HRT-004', 'Payroll and Labour Rules Not Understood', 'Anything touching pay, attendance, contracts or statutory deductions runs into labour law, and none of it has been checked.', 'Idea & Validation', 'HRTech Compliance Basics', 'external', 3, 6, 10, '["Payroll rules assumed to be simple", "Statutory deductions not understood", "Rules differ by state and this is not known", "Contract and employment type distinctions unclear", "No plan for who handles compliance"]'::jsonb, '["hrtech"]'::jsonb),
  ('HRT-005', 'Bought but Barely Used', 'Companies sign up and then employees never log in, so the tool gets dropped at renewal.', 'Sales & Revenue', 'HRTech Adoption', 'external', 4, 6, 9, '["Logins drop sharply after the first weeks", "Only HR uses it, not employees", "No onboarding for the client team", "Usage not measured per account", "Renewal decided on usage nobody tracked"]'::jsonb, '["hrtech"]'::jsonb),
  ('HRT-006', 'Sales Cycle Far Longer Than Planned', 'HR purchases pass through multiple approvers and budget cycles, so deals take months longer than the cash plan assumed.', 'Sales & Revenue', 'HRTech Sales Cycle', 'external', 4, 6, 9, '["Deals taking far longer than expected", "Multiple approvers appearing late", "Budget cycles blocking decisions", "Pipeline forecast repeatedly wrong", "Cash planned on optimistic close dates"]'::jsonb, '["hrtech"]'::jsonb),
  ('HRT-007', 'Every Client Wants It Slightly Different', 'Each company has its own policies and processes, so every sale turns into custom work.', 'Operations & Systems', 'HRTech Customisation Load', 'external', 3, 6, 9, '["Every deal needs custom changes", "Product diverging per client", "Engineering time consumed by one off work", "No standard configuration", "Delivery time growing with each client"]'::jsonb, '["hrtech"]'::jsonb),
  ('HRT-008', 'Getting Data Out of Their Existing Systems', 'Client employee data sits in spreadsheets and legacy systems, and migrating it is slow, messy and unbudgeted.', 'Operations & Systems', 'HRTech Implementation', 'external', 3, 5, 9, '["Data migration taking far longer than quoted", "Client data messy or incomplete", "No standard import process", "Go live dates repeatedly slipping", "Implementation cost not charged for"]'::jsonb, '["hrtech"]'::jsonb),
  ('HRT-009', 'One Payroll or Compliance Error Breaks Trust', 'A single mistake in pay, deduction or a statutory filing destroys client confidence permanently.', 'Operations & Systems', 'HRTech Accuracy', 'external', 3, 7, 10, '["Errors reaching client payroll", "No checking step before processing", "Rule changes not tracked or applied", "No process when an error is found", "Client trust lost after one mistake"]'::jsonb, '["hrtech"]'::jsonb),
  ('HRT-010', 'Churn Hidden Behind New Sales', 'Growth looks healthy because new clients keep arriving, while existing ones quietly leave at renewal.', 'Sales & Revenue', 'HRTech Churn', 'external', 4, 7, 10, '["Churn rate not measured separately", "Growth reported only as new revenue", "Clients leaving at renewal without warning", "No reason recorded when a client leaves", "Net growth far below gross growth"]'::jsonb, '["hrtech"]'::jsonb),
  ('HRT-011', 'Support Load Rising Faster Than Revenue', 'Every new client adds queries, fixes and hand holding, and the support team cannot keep up.', 'Operations & Systems', 'HRTech Support Load', 'external', 3, 6, 9, '["Support tickets rising faster than clients", "Same questions asked repeatedly", "No self serve help or documentation", "Engineers pulled into support", "Response times slipping"]'::jsonb, '["hrtech"]'::jsonb),
  ('HRT-012', 'Security Expectations From Larger Buyers', 'Bigger clients now demand security reviews, certifications and contractual assurances the business cannot yet meet.', 'Operations & Systems', 'HRTech Security Posture', 'external', 3, 7, 10, '["Security questionnaires failing or stalling deals", "No certification in place", "Access controls informal", "No penetration testing or review", "Contract security terms accepted without checking"]'::jsonb, '["hrtech"]'::jsonb),
  ('HRT-013', 'Statutory Changes Now Hit Every Client at Once', 'A change in labour or tax rules must be applied across the whole client base quickly and correctly.', 'Operations & Systems', 'HRTech Regulatory Change', 'external', 3, 7, 10, '["Rule changes applied client by client", "No system for pushing a change everywhere", "Some clients left on old rules", "Change turnaround time not measured", "No testing before a rule change goes live"]'::jsonb, '["hrtech"]'::jsonb),
  ('HRT-014', 'Integrations With Client Systems Multiplying', 'Clients expect the product to connect to their payroll, accounting, attendance and identity systems, and each connection needs building and maintaining.', 'Operations & Systems', 'HRTech Integrations', 'external', 3, 5, 9, '["Growing list of requested integrations", "Each integration built bespoke", "Breaking when the other system changes", "No owner for integration maintenance", "Deals lost for lack of a connection"]'::jsonb, '["hrtech"]'::jsonb),
  ('HRT-015', 'Competing With Free or Bundled Alternatives', 'Large suites and accounting packages bundle basic HR features for free, squeezing what a standalone product can charge.', 'Strategy & Planning', 'HRTech Competitive Squeeze', 'external', 2, 6, 10, '["Buyers citing a bundled free alternative", "Price pressure on renewal", "Feature set overlapping with large suites", "No clear reason to buy separately", "Discounting to retain clients"]'::jsonb, '["hrtech"]'::jsonb)
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
         t.primary_stage_group, '["hrtech"]'::jsonb, z.v
  FROM (VALUES
  ('RC-HRT-001', 'Buyer and User Assumed to Be the Same', 'The person who uses the tool is treated as the person who buys it.', 'HRT-001', 'external', 'Strategic', 0.72, 'Stage 0'),
  ('RC-HRT-002', 'Approval Path Unknown', 'Who signs off spending on this has never been established.', 'HRT-001', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-HRT-003', 'Company Size Not Chosen', 'No decision on whether this serves small firms or large ones.', 'HRT-001', 'external', 'Strategic', 0.68, 'Stage 0'),
  ('RC-HRT-004', 'Pitch Aimed at Whoever Will Listen', 'The same message goes to users, finance and leadership.', 'HRT-001', 'external', 'Strategic', 0.66, 'Stage 0'),
  ('RC-HRT-005', 'No Conversation With a Real HR Buyer', 'Nobody who would actually purchase has been spoken to.', 'HRT-001', 'external', 'Behavioural', 0.67, 'Stage 0'),
  ('RC-HRT-006', 'Problem Described as Inefficiency', 'The pain is framed as wasted time rather than real loss.', 'HRT-002', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-HRT-007', 'Companies Already Coping', 'Spreadsheets and existing habits handle it well enough today.', 'HRT-002', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-HRT-008', 'No Cost Attached to the Problem', 'Nobody has worked out what the problem costs a company.', 'HRT-002', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-HRT-009', 'Nobody Has Asked to Be Rid of It', 'No company has actively gone looking for a solution.', 'HRT-002', 'external', 'Behavioural', 0.68, 'Stage 0'),
  ('RC-HRT-010', 'Assuming Annoyance Equals Payment', 'Believing irritation will translate into a purchase.', 'HRT-002', 'external', 'Psychological', 0.67, 'Stage 0'),
  ('RC-HRT-011', 'No Plan for Consent or Employee Notice', 'How employees will be told or asked has not been decided.', 'HRT-003', 'external', 'Operational', 0.70, 'Stage 0'),
  ('RC-HRT-012', 'No Decision on Where Data Is Stored', 'Where employee records will live has not been settled.', 'HRT-003', 'external', 'Operational', 0.67, 'Stage 0'),
  ('RC-HRT-013', 'Everyone on the Team Can See Records', 'No limits exist on who inside the business can read employee data.', 'HRT-003', 'external', 'Operational', 0.71, 'Stage 0'),
  ('RC-HRT-014', 'Salary and Performance Data Treated Casually', 'The most sensitive fields get no special handling.', 'HRT-003', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-HRT-015', 'Payroll Rules Assumed Simple', 'The complexity of pay calculation has been underestimated.', 'HRT-004', 'external', 'Knowledge', 0.73, 'Stage 0'),
  ('RC-HRT-016', 'Statutory Deductions Not Understood', 'What must be deducted and remitted is unknown.', 'HRT-004', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-HRT-017', 'State Differences Not Known', 'Rules that vary by state are assumed to be uniform.', 'HRT-004', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-HRT-018', 'Employment Type Distinctions Unclear', 'The difference between employees, contractors and consultants is blurred.', 'HRT-004', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-HRT-019', 'Usage Not Measured Per Account', 'Nobody tracks whether each client is actually using the tool.', 'HRT-005', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-HRT-020', 'No Onboarding for the Client Team', 'Employees are never shown how or why to use it.', 'HRT-005', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-HRT-021', 'Only HR Uses It', 'Adoption stops at the person who bought it.', 'HRT-005', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-HRT-022', 'Nothing That Needs Regular Use', 'The product solves an occasional need, so logins fade.', 'HRT-005', 'external', 'Strategic', 0.68, 'Stage 0→1'),
  ('RC-HRT-023', 'Renewal Decided on Untracked Usage', 'Renewal conversations happen with no usage evidence in hand.', 'HRT-005', 'external', 'Operational', 0.67, 'Stage 0→1'),
  ('RC-HRT-024', 'Multiple Approvers Appearing Late', 'New decision makers surface after the deal seemed agreed.', 'HRT-006', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-HRT-025', 'Budget Cycles Blocking Decisions', 'Purchases wait for an annual budget window.', 'HRT-006', 'external', 'Knowledge', 0.70, 'Stage 0→1'),
  ('RC-HRT-026', 'Pipeline Forecast Repeatedly Wrong', 'Close dates are consistently optimistic.', 'HRT-006', 'external', 'Behavioural', 0.69, 'Stage 0→1'),
  ('RC-HRT-027', 'Cash Planned on Optimistic Close Dates', 'Spending assumes deals land when hoped rather than when typical.', 'HRT-006', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-HRT-028', 'Real Sales Cycle Length Unknown', 'How long a deal actually takes has never been measured.', 'HRT-006', 'external', 'Knowledge', 0.68, 'Stage 0→1'),
  ('RC-HRT-029', 'Every Deal Needs Custom Changes', 'Each sale is closed by promising something bespoke.', 'HRT-007', 'external', 'Behavioural', 0.73, 'Stage 0→1'),
  ('RC-HRT-030', 'No Standard Configuration', 'There is no defined set of options clients choose from.', 'HRT-007', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-HRT-031', 'Engineering Consumed by One Off Work', 'Build capacity goes to single client requests.', 'HRT-007', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-HRT-032', 'Product Diverging Per Client', 'Different clients now run meaningfully different versions.', 'HRT-007', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-HRT-033', 'Delivery Time Growing Per Client', 'Each new client takes longer to get live than the last.', 'HRT-007', 'external', 'Operational', 0.66, 'Stage 0→1'),
  ('RC-HRT-034', 'No Standard Import Process', 'Every client migration is built from scratch.', 'HRT-008', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-HRT-035', 'Client Data Messy or Incomplete', 'What arrives from the client is not usable as given.', 'HRT-008', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-HRT-036', 'Go Live Dates Repeatedly Slipping', 'Implementation keeps taking longer than promised.', 'HRT-008', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-HRT-037', 'Implementation Not Charged For', 'Heavy setup work is given away free.', 'HRT-008', 'external', 'Strategic', 0.69, 'Stage 0→1'),
  ('RC-HRT-038', 'No Checking Step Before Processing', 'Nothing verifies output before it reaches the client.', 'HRT-009', 'external', 'Operational', 0.74, 'Stage 0→1'),
  ('RC-HRT-039', 'Rule Changes Not Tracked', 'Changes in statutory rules are learned about late.', 'HRT-009', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-HRT-040', 'No Process When an Error Is Found', 'Each mistake is handled differently and ad hoc.', 'HRT-009', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-HRT-041', 'Churn Not Measured Separately', 'Losses are hidden inside a single net growth figure.', 'HRT-010', 'external', 'Operational', 0.74, 'Stage 1→10+'),
  ('RC-HRT-042', 'Growth Reported Only as New Revenue', 'Reporting celebrates additions and ignores departures.', 'HRT-010', 'external', 'Behavioural', 0.71, 'Stage 1→10+'),
  ('RC-HRT-043', 'Clients Leaving Without Warning', 'There is no early signal before a client decides to go.', 'HRT-010', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-HRT-044', 'No Reason Recorded When a Client Leaves', 'Departures are not investigated or logged.', 'HRT-010', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-HRT-045', 'Support Tickets Rising Faster Than Clients', 'Each additional client adds more load than the last.', 'HRT-011', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-HRT-046', 'Same Questions Asked Repeatedly', 'The same issues recur because the cause is never fixed.', 'HRT-011', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-HRT-047', 'No Self Serve Help or Documentation', 'Every question must be answered by a person.', 'HRT-011', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-HRT-048', 'Engineers Pulled Into Support', 'Build capacity is consumed answering client issues.', 'HRT-011', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-HRT-049', 'Security Questionnaires Stalling Deals', 'Sales stop when buyers ask for security evidence.', 'HRT-012', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-HRT-050', 'No Certification in Place', 'Nothing independent attests to the security posture.', 'HRT-012', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-HRT-051', 'Access Controls Informal', 'Who can reach client data is managed by trust rather than system.', 'HRT-012', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-HRT-052', 'No Testing or Independent Review', 'Nobody outside has checked the system for weaknesses.', 'HRT-012', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-HRT-053', 'Security Terms Accepted Without Checking', 'Contractual commitments are signed without confirming they can be met.', 'HRT-012', 'external', 'Behavioural', 0.69, 'Stage 1→10+'),
  ('RC-HRT-054', 'Rule Changes Applied Client by Client', 'Each client is updated separately and manually.', 'HRT-013', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-HRT-055', 'No System for Pushing a Change Everywhere', 'There is no mechanism to apply one change across all accounts.', 'HRT-013', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-HRT-056', 'Some Clients Left on Old Rules', 'Parts of the base are running outdated calculations.', 'HRT-013', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-HRT-057', 'No Testing Before a Rule Change Goes Live', 'Changes reach clients without verification.', 'HRT-013', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-HRT-058', 'Each Integration Built Bespoke', 'Every connection is written from scratch for one client.', 'HRT-014', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-HRT-059', 'Integrations Breaking on Other Side Changes', 'Connections fail when the other system updates.', 'HRT-014', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-HRT-060', 'No Owner for Integration Maintenance', 'Nobody is responsible for keeping connections working.', 'HRT-014', 'external', 'Operational', 0.68, 'Stage 1→10+'),
  ('RC-HRT-061', 'Deals Lost for Lack of a Connection', 'Buyers choose competitors that already integrate.', 'HRT-014', 'external', 'Strategic', 0.67, 'Stage 1→10+'),
  ('RC-HRT-062', 'Buyers Citing a Bundled Free Alternative', 'Prospects point to features already included in software they own.', 'HRT-015', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-HRT-063', 'Feature Set Overlapping With Large Suites', 'What the product does is largely covered by bigger platforms.', 'HRT-015', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-HRT-064', 'No Clear Reason to Buy Separately', 'Nothing explains why a standalone tool is worth extra spend.', 'HRT-015', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-HRT-065', 'Discounting to Retain Clients', 'Price is being cut to stop clients leaving.', 'HRT-015', 'external', 'Behavioural', 0.69, 'Stage 1→10+'),
  ('RC-HRT-066', 'Price Pressure at Renewal', 'Existing clients push rates down each cycle.', 'HRT-015', 'external', 'Operational', 0.68, 'Stage 1→10+')
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
         '["hrtech"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-HRT-001', 'Who uses this, and who actually signs off the money for it?', 'open_text', 'Idea & Validation', 'CORE', 'HRT-001', 'RC-HRT-001', 1, 'Stage 0'),
  ('S0-HRT-002', 'In a company you want to sell to, who has to say yes?', 'open_text', 'Idea & Validation', 'CORE', 'HRT-001', 'RC-HRT-002', 2, 'Stage 0'),
  ('S0-HRT-003', 'Are you building for small companies or large ones? Pick one.', 'open_text', 'Idea & Validation', 'CORE', 'HRT-001', 'RC-HRT-003', 1, 'Stage 0'),
  ('S0-HRT-004', 'Have you spoken to even one real HR buyer?', 'open_text', 'Idea & Validation', 'CORE', 'HRT-001', 'RC-HRT-005', 1, 'Stage 0'),
  ('S0-HRT-005', 'Do you use the same pitch for HR, finance and the founder?', 'open_text', 'Idea & Validation', 'CORE', 'HRT-001', 'RC-HRT-004', 2, 'Stage 0'),
  ('S0-HRT-006', 'How are companies handling this problem today?', 'open_text', 'Idea & Validation', 'CORE', 'HRT-002', 'RC-HRT-007', 1, 'Stage 0'),
  ('S0-HRT-007', 'What does this problem actually cost a company in money or people?', 'open_text', 'Idea & Validation', 'CORE', 'HRT-002', 'RC-HRT-008', 2, 'Stage 0'),
  ('S0-HRT-008', 'Has any company ever gone looking for a solution to this?', 'open_text', 'Idea & Validation', 'CORE', 'HRT-002', 'RC-HRT-009', 2, 'Stage 0'),
  ('S0-HRT-009', 'Is this a real pain, or just something mildly annoying?', 'open_text', 'Idea & Validation', 'CORE', 'HRT-002', 'RC-HRT-006', 2, 'Stage 0'),
  ('S0-HRT-010', 'Do you think being annoyed is enough to make someone pay?', 'open_text', 'Idea & Validation', 'CORE', 'HRT-002', 'RC-HRT-010', 2, 'Stage 0'),
  ('S0-HRT-011', 'How will employees be told that their data is being collected?', 'open_text', 'Idea & Validation', 'CORE', 'HRT-003', 'RC-HRT-011', 2, 'Stage 0'),
  ('S0-HRT-012', 'Where would employee records be stored?', 'open_text', 'Idea & Validation', 'CORE', 'HRT-003', 'RC-HRT-012', 2, 'Stage 0'),
  ('S0-HRT-013', 'Who on your team would be able to see salary and performance data?', 'open_text', 'Idea & Validation', 'CORE', 'HRT-003', 'RC-HRT-013', 1, 'Stage 0'),
  ('S0-HRT-014', 'If your product touches pay or attendance, do you know the rules that apply?', 'open_text', 'Idea & Validation', 'CORE', 'HRT-004', 'RC-HRT-015', 1, 'Stage 0'),
  ('S0-HRT-015', 'Do you know that labour rules differ from state to state?', 'open_text', 'Idea & Validation', 'CORE', 'HRT-004', 'RC-HRT-017', 2, 'Stage 0'),
  ('S01-HRT-001', 'Do you know how much each client actually uses your product?', 'open_text', 'Sales & Revenue', 'CORE', 'HRT-005', 'RC-HRT-019', 2, 'Stage 0→1'),
  ('S01-HRT-002', 'What happens in the first two weeks after a company signs up?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-005', 'RC-HRT-020', 2, 'Stage 0→1'),
  ('S01-HRT-003', 'Does anyone beyond the HR team ever log in?', 'open_text', 'Sales & Revenue', 'CORE', 'HRT-005', 'RC-HRT-021', 2, 'Stage 0→1'),
  ('S01-HRT-004', 'Is there a reason someone would open your product every week?', 'open_text', 'Sales & Revenue', 'CORE', 'HRT-005', 'RC-HRT-022', 2, 'Stage 0→1'),
  ('S01-HRT-005', 'When renewal comes up, what evidence do you have that it was used?', 'open_text', 'Sales & Revenue', 'CORE', 'HRT-005', 'RC-HRT-023', 3, 'Stage 0→1'),
  ('S01-HRT-006', 'How long does a deal actually take from first call to payment?', 'open_text', 'Sales & Revenue', 'CORE', 'HRT-006', 'RC-HRT-028', 2, 'Stage 0→1'),
  ('S01-HRT-007', 'How many people have to approve before you get paid?', 'open_text', 'Sales & Revenue', 'CORE', 'HRT-006', 'RC-HRT-024', 2, 'Stage 0→1'),
  ('S01-HRT-008', 'Are your deals waiting on a budget cycle?', 'open_text', 'Sales & Revenue', 'CORE', 'HRT-006', 'RC-HRT-025', 2, 'Stage 0→1'),
  ('S01-HRT-009', 'How often do deals close when your forecast said they would?', 'open_text', 'Sales & Revenue', 'CORE', 'HRT-006', 'RC-HRT-026', 2, 'Stage 0→1'),
  ('S01-HRT-010', 'Is your spending planned on hoped for close dates or typical ones?', 'open_text', 'Financial Management', 'CORE', 'HRT-006', 'RC-HRT-027', 3, 'Stage 0→1'),
  ('S01-HRT-011', 'Does every new client ask for something custom?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-007', 'RC-HRT-029', 2, 'Stage 0→1'),
  ('S01-HRT-012', 'Is there a standard set of options, or does each client get their own build?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-007', 'RC-HRT-030', 2, 'Stage 0→1'),
  ('S01-HRT-013', 'How much of your engineering time goes to single client requests?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-007', 'RC-HRT-031', 3, 'Stage 0→1'),
  ('S01-HRT-014', 'Are your clients now running meaningfully different versions?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-007', 'RC-HRT-032', 3, 'Stage 0→1'),
  ('S01-HRT-015', 'Is each new client taking longer to get live than the last?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-007', 'RC-HRT-033', 2, 'Stage 0→1'),
  ('S01-HRT-016', 'How long does it really take to get a client live?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-008', 'RC-HRT-036', 2, 'Stage 0→1'),
  ('S01-HRT-017', 'What condition does client data arrive in?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-008', 'RC-HRT-035', 2, 'Stage 0→1'),
  ('S01-HRT-018', 'Do you have a standard way of importing their data?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-008', 'RC-HRT-034', 2, 'Stage 0→1'),
  ('S01-HRT-019', 'Do you charge for implementation, or is it free?', 'open_text', 'Financial Management', 'CORE', 'HRT-008', 'RC-HRT-037', 2, 'Stage 0→1'),
  ('S01-HRT-020', 'Does anything get checked before your output reaches the client?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-009', 'RC-HRT-038', 3, 'Stage 0→1'),
  ('S10-HRT-001', 'How many clients did you lose last year, and how many did you win?', 'open_text', 'Sales & Revenue', 'CORE', 'HRT-010', 'RC-HRT-041', 2, 'Stage 1→10+'),
  ('S10-HRT-002', 'Do you report growth as a net number or only as new sales?', 'open_text', 'Sales & Revenue', 'CORE', 'HRT-010', 'RC-HRT-042', 2, 'Stage 1→10+'),
  ('S10-HRT-003', 'Do you get any warning before a client decides to leave?', 'open_text', 'Sales & Revenue', 'CORE', 'HRT-010', 'RC-HRT-043', 3, 'Stage 1→10+'),
  ('S10-HRT-004', 'When a client leaves, do you record why?', 'open_text', 'Sales & Revenue', 'CORE', 'HRT-010', 'RC-HRT-044', 2, 'Stage 1→10+'),
  ('S10-HRT-005', 'Are support tickets growing faster than your client count?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-011', 'RC-HRT-045', 2, 'Stage 1→10+'),
  ('S10-HRT-006', 'What are the three questions you get asked over and over?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-011', 'RC-HRT-046', 2, 'Stage 1→10+'),
  ('S10-HRT-007', 'Can a client find an answer without contacting you?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-011', 'RC-HRT-047', 2, 'Stage 1→10+'),
  ('S10-HRT-008', 'How much engineering time is going into support?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-011', 'RC-HRT-048', 3, 'Stage 1→10+'),
  ('S10-HRT-009', 'Have security questions ever stalled or lost you a deal?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-012', 'RC-HRT-049', 2, 'Stage 1→10+'),
  ('S10-HRT-010', 'Do you have any security certification buyers recognise?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-012', 'RC-HRT-050', 2, 'Stage 1→10+'),
  ('S10-HRT-011', 'Who inside your company can open client employee data?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-012', 'RC-HRT-051', 3, 'Stage 1→10+'),
  ('S10-HRT-012', 'Has anyone outside your team ever tested your system for weaknesses?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-012', 'RC-HRT-052', 3, 'Stage 1→10+'),
  ('S10-HRT-013', 'Have you signed security terms you are not sure you meet?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-012', 'RC-HRT-053', 3, 'Stage 1→10+'),
  ('S10-HRT-014', 'When a rule changes, how do you apply it to every client?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-013', 'RC-HRT-055', 3, 'Stage 1→10+'),
  ('S10-HRT-015', 'Do you update clients one by one or all at once?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-013', 'RC-HRT-054', 2, 'Stage 1→10+'),
  ('S10-HRT-016', 'Could any client still be running on old rules?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-013', 'RC-HRT-056', 3, 'Stage 1→10+'),
  ('S10-HRT-017', 'Is a rule change tested before it reaches clients?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-013', 'RC-HRT-057', 3, 'Stage 1→10+'),
  ('S10-HRT-018', 'How many integrations do clients ask for, and how many do you have?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-014', 'RC-HRT-058', 2, 'Stage 1→10+'),
  ('S10-HRT-019', 'What happens when a system you connect to changes?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-014', 'RC-HRT-059', 2, 'Stage 1→10+'),
  ('S10-HRT-020', 'Who is responsible for keeping your integrations working?', 'open_text', 'Operations & Systems', 'CORE', 'HRT-014', 'RC-HRT-060', 2, 'Stage 1→10+'),
  ('S10-HRT-021', 'Have you lost a deal because you did not connect to something?', 'open_text', 'Sales & Revenue', 'CORE', 'HRT-014', 'RC-HRT-061', 2, 'Stage 1→10+'),
  ('S10-HRT-022', 'Do buyers tell you they already get this free in something else?', 'open_text', 'Strategy & Planning', 'CORE', 'HRT-015', 'RC-HRT-062', 2, 'Stage 1→10+'),
  ('S10-HRT-023', 'What do you do that a large bundled suite does not?', 'open_text', 'Strategy & Planning', 'CORE', 'HRT-015', 'RC-HRT-064', 3, 'Stage 1→10+'),
  ('S10-HRT-024', 'How much of your feature set overlaps with what they already own?', 'open_text', 'Strategy & Planning', 'CORE', 'HRT-015', 'RC-HRT-063', 3, 'Stage 1→10+'),
  ('S10-HRT-025', 'Are you cutting price to keep clients from leaving?', 'open_text', 'Financial Management', 'CORE', 'HRT-015', 'RC-HRT-065', 2, 'Stage 1→10+')
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
  ('S0-HRT-001', 'icp'),
  ('S0-HRT-002', 'icp'),
  ('S0-HRT-003', 'icp'),
  ('S0-HRT-004', 'icp'),
  ('S0-HRT-005', 'icp'),
  ('S0-HRT-006', 'icp'),
  ('S0-HRT-007', 'icp'),
  ('S0-HRT-008', 'icp'),
  ('S0-HRT-009', 'icp'),
  ('S0-HRT-010', 'icp'),
  ('S0-HRT-011', 'technical-quality'),
  ('S0-HRT-012', 'technical-quality'),
  ('S0-HRT-013', 'technical-quality'),
  ('S0-HRT-014', 'technical-quality'),
  ('S0-HRT-015', 'technical-quality'),
  ('S01-HRT-001', 'technical-quality'),
  ('S01-HRT-002', 'technical-quality'),
  ('S01-HRT-003', 'technical-quality'),
  ('S01-HRT-004', 'technical-quality'),
  ('S01-HRT-005', 'technical-quality'),
  ('S01-HRT-006', 'willingness-to-pay'),
  ('S01-HRT-007', 'willingness-to-pay'),
  ('S01-HRT-008', 'willingness-to-pay'),
  ('S01-HRT-009', 'willingness-to-pay'),
  ('S01-HRT-010', 'willingness-to-pay'),
  ('S01-HRT-011', 'technical-quality'),
  ('S01-HRT-012', 'technical-quality'),
  ('S01-HRT-013', 'technical-quality'),
  ('S01-HRT-014', 'technical-quality'),
  ('S01-HRT-015', 'technical-quality'),
  ('S01-HRT-016', 'technical-quality'),
  ('S01-HRT-017', 'technical-quality'),
  ('S01-HRT-018', 'technical-quality'),
  ('S01-HRT-019', 'technical-quality'),
  ('S01-HRT-020', 'technical-quality'),
  ('S10-HRT-001', 'willingness-to-pay'),
  ('S10-HRT-002', 'willingness-to-pay'),
  ('S10-HRT-003', 'willingness-to-pay'),
  ('S10-HRT-004', 'willingness-to-pay'),
  ('S10-HRT-005', 'technical-quality'),
  ('S10-HRT-006', 'technical-quality'),
  ('S10-HRT-007', 'technical-quality'),
  ('S10-HRT-008', 'technical-quality'),
  ('S10-HRT-009', 'technical-quality'),
  ('S10-HRT-010', 'technical-quality'),
  ('S10-HRT-011', 'technical-quality'),
  ('S10-HRT-012', 'technical-quality'),
  ('S10-HRT-013', 'technical-quality'),
  ('S10-HRT-014', 'technical-quality'),
  ('S10-HRT-015', 'technical-quality'),
  ('S10-HRT-016', 'technical-quality'),
  ('S10-HRT-017', 'technical-quality'),
  ('S10-HRT-018', 'technical-quality'),
  ('S10-HRT-019', 'technical-quality'),
  ('S10-HRT-020', 'technical-quality'),
  ('S10-HRT-021', 'technical-quality'),
  ('S10-HRT-022', 'willingness-to-pay'),
  ('S10-HRT-023', 'willingness-to-pay'),
  ('S10-HRT-024', 'willingness-to-pay'),
  ('S10-HRT-025', 'willingness-to-pay')
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
         '["hrtech"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-HRT-001', 'Ideation — HRTech Buyer Clarity', 'HRT-001', '["RC-HRT-001", "RC-HRT-002"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Write down who uses this and who pays for it separately.", "Find out who has to approve that spending.", "Build your pitch for the approver, not just the user."]'::jsonb, '[{"name": "Separate User From Buyer", "brief": "Naming who uses it and who actually releases the money."}]'::jsonb),
  ('INT-HRT-002', 'Ideation — HRTech Buyer Clarity', 'HRT-001', '["RC-HRT-003", "RC-HRT-004"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Choose one company size to serve first.", "Write why that size and not the others.", "Make one message for that buyer alone."]'::jsonb, '[{"name": "Pick One Company Size", "brief": "Small and large companies buy completely differently."}]'::jsonb),
  ('INT-HRT-003', 'Ideation — HRTech Buyer Clarity', 'HRT-001', '["RC-HRT-005"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Talk to 10 real HR buyers at your chosen company size.", "Ask how they bought their last HR tool.", "Map the steps they describe."]'::jsonb, '[{"name": "Learn the Real Buying Path", "brief": "Understanding how HR tools actually get purchased."}]'::jsonb),
  ('INT-HRT-004', 'Ideation — HRTech Problem Urgency', 'HRT-002', '["RC-HRT-006", "RC-HRT-008"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Put a rupee or hours figure on what this problem costs a company.", "If you cannot, the problem may not be urgent.", "Test that figure with three companies."]'::jsonb, '[{"name": "Price the Problem", "brief": "Turning a vague inefficiency into a number a buyer recognises."}]'::jsonb),
  ('INT-HRT-005', 'Ideation — HRTech Problem Urgency', 'HRT-002', '["RC-HRT-007", "RC-HRT-009", "RC-HRT-010"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Find out exactly how companies cope with this today.", "Ask whether anyone has ever searched for a fix.", "If nobody has looked, reconsider the problem."]'::jsonb, '[{"name": "Has Anyone Gone Looking", "brief": "Checking whether the problem is urgent enough to be searched for."}]'::jsonb),
  ('INT-HRT-006', 'Ideation — HRTech Data Basics', 'HRT-003', '["RC-HRT-011", "RC-HRT-012"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Decide how employees will be told their data is held.", "Decide where records will be stored.", "Write both down before collecting anything."]'::jsonb, '[{"name": "Notice and Storage", "brief": "Deciding employee notice and data location before building."}]'::jsonb),
  ('INT-HRT-007', 'Ideation — HRTech Data Basics', 'HRT-003', '["RC-HRT-013", "RC-HRT-014"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Limit who on your team can see salary and performance data.", "Treat those fields as the most sensitive you hold.", "Record who has access and why."]'::jsonb, '[{"name": "Lock Down the Sensitive Fields", "brief": "Restricting access to pay and performance records."}]'::jsonb),
  ('INT-HRT-008', 'Ideation — HRTech Compliance Basics', 'HRT-004', '["RC-HRT-015", "RC-HRT-016"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Find out exactly which rules apply if you touch pay or attendance.", "List the statutory deductions involved.", "Get it checked by someone who runs payroll professionally."]'::jsonb, '[{"name": "Map the Payroll Rules", "brief": "Understanding pay and deduction obligations before building."}]'::jsonb),
  ('INT-HRT-009', 'Ideation — HRTech Compliance Basics', 'HRT-004', '["RC-HRT-017"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Check how the rules differ in the states you plan to serve.", "Assume nothing carries across.", "Budget the effort that adds per state."]'::jsonb, '[{"name": "Check State by State", "brief": "Treating each state labour regime as its own work."}]'::jsonb),
  ('INT-HRT-010', 'Ideation — HRTech Compliance Basics', 'HRT-004', '["RC-HRT-018"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Learn the difference between employees, contractors and consultants.", "Decide which types your product will support.", "Design the product around that distinction."]'::jsonb, '[{"name": "Know the Employment Types", "brief": "The distinctions that change which rules apply."}]'::jsonb),
  ('INT-HRT-011', 'Validation to Traction — HRTech Adoption', 'HRT-005', '["RC-HRT-019", "RC-HRT-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Track active users per client every month.", "Flag any account where usage is falling.", "Walk into renewals with that number in hand."]'::jsonb, '[{"name": "Usage Per Account", "brief": "Knowing which clients actually use it before renewal comes up."}]'::jsonb),
  ('INT-HRT-012', 'Validation to Traction — HRTech Adoption', 'HRT-005', '["RC-HRT-020", "RC-HRT-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Run a proper onboarding for every new client team.", "Get employees using it in the first two weeks, not just HR.", "Measure how many logged in at least once."]'::jsonb, '[{"name": "Onboard the Whole Team", "brief": "Driving adoption past the buyer in the first fortnight."}]'::jsonb),
  ('INT-HRT-013', 'Validation to Traction — HRTech Adoption', 'HRT-005', '["RC-HRT-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["Find one thing people would need weekly, not yearly.", "Build or highlight that.", "Watch whether repeat logins rise."]'::jsonb, '[{"name": "A Weekly Reason to Open It", "brief": "Turning an occasional tool into a regular habit."}]'::jsonb),
  ('INT-HRT-014', 'Validation to Traction — HRTech Sales Cycle', 'HRT-006', '["RC-HRT-024", "RC-HRT-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Measure how long your last ten deals actually took.", "Map who had to approve each one.", "Identify approvers early instead of meeting them late."]'::jsonb, '[{"name": "Map the Approval Chain", "brief": "Knowing the real cycle length and who must sign."}]'::jsonb),
  ('INT-HRT-015', 'Validation to Traction — HRTech Sales Cycle', 'HRT-006', '["RC-HRT-025", "RC-HRT-026", "RC-HRT-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Plan cash on your actual average cycle, not the best case.", "Ask early whether a budget cycle gates the decision.", "Keep enough runway to survive the real timeline."]'::jsonb, '[{"name": "Plan Cash on the Real Cycle", "brief": "Funding the business for how long deals actually take."}]'::jsonb),
  ('INT-HRT-016', 'Validation to Traction — HRTech Customisation Load', 'HRT-007', '["RC-HRT-029", "RC-HRT-030"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["Define a standard set of configuration options.", "Offer choices within it instead of custom builds.", "Say no to requests outside it unless they are paid and reusable."]'::jsonb, '[{"name": "Configure, Do Not Customise", "brief": "A defined option set instead of bespoke work per client."}]'::jsonb),
  ('INT-HRT-017', 'Validation to Traction — HRTech Customisation Load', 'HRT-007', '["RC-HRT-031", "RC-HRT-032", "RC-HRT-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Measure what share of engineering goes to single client work.", "Bring divergent client versions back to one product.", "Cap custom work at a fixed share of capacity."]'::jsonb, '[{"name": "Reconverge the Product", "brief": "Pulling client specific versions back into one codebase."}]'::jsonb),
  ('INT-HRT-018', 'Validation to Traction — HRTech Implementation', 'HRT-008', '["RC-HRT-034", "RC-HRT-035"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Build one standard import template and process.", "Tell clients exactly what format you need before you start.", "Reject data that does not meet it rather than fixing it yourself."]'::jsonb, '[{"name": "Standard Import Process", "brief": "One defined route for getting client data in."}]'::jsonb),
  ('INT-HRT-019', 'Validation to Traction — HRTech Implementation', 'HRT-008', '["RC-HRT-036", "RC-HRT-037"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Measure how long implementations really take.", "Charge for implementation as a separate line.", "Quote go live dates from actual history, not hope."]'::jsonb, '[{"name": "Charge and Quote Honestly", "brief": "Paid implementation with dates based on real history."}]'::jsonb),
  ('INT-HRT-020', 'Validation to Traction — HRTech Accuracy', 'HRT-009', '["RC-HRT-038", "RC-HRT-040"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Add a checking step before anything reaches a client.", "Write what happens the moment an error is found.", "Tell the client before they find it themselves."]'::jsonb, '[{"name": "Check Before It Goes Out", "brief": "A verification step plus a defined error response."}]'::jsonb),
  ('INT-HRT-021', 'Validation to Traction — HRTech Accuracy', 'HRT-009', '["RC-HRT-039"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Give one person the job of tracking rule changes.", "Set a fixed review before each processing cycle.", "Log what changed and when you applied it."]'::jsonb, '[{"name": "Track the Rule Changes", "brief": "One owner watching for statutory changes that affect output."}]'::jsonb),
  ('INT-HRT-022', 'Validation to Traction — HRTech Accuracy', 'HRT-009', '["RC-HRT-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Keep a record of every error that reached a client.", "Find what caused each one.", "Fix the cause so the same error cannot repeat."]'::jsonb, '[{"name": "Error Log and Root Cause", "brief": "Recording mistakes and closing their causes permanently."}]'::jsonb),
  ('INT-HRT-023', 'Growth to Maturity — HRTech Churn', 'HRT-010', '["RC-HRT-041", "RC-HRT-042"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Report clients lost and revenue lost separately from new sales.", "Calculate net growth after churn every month.", "Stop celebrating gross numbers."]'::jsonb, '[{"name": "Report Churn Separately", "brief": "Seeing losses next to wins instead of buried in one figure."}]'::jsonb),
  ('INT-HRT-024', 'Growth to Maturity — HRTech Churn', 'HRT-010', '["RC-HRT-043", "RC-HRT-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Define early warning signals such as falling usage or unanswered check ins.", "Review at risk accounts monthly.", "Record the real reason every time a client leaves."]'::jsonb, '[{"name": "Early Warning and Exit Reasons", "brief": "Spotting departures before renewal and learning from each one."}]'::jsonb),
  ('INT-HRT-025', 'Growth to Maturity — HRTech Support Load', 'HRT-011', '["RC-HRT-045", "RC-HRT-046", "RC-HRT-047"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["List the questions you answer most often.", "Fix the product or write help content for each.", "Measure whether tickets per client fall."]'::jsonb, '[{"name": "Fix the Repeat Questions", "brief": "Removing the causes of recurring support instead of answering again."}]'::jsonb),
  ('INT-HRT-026', 'Growth to Maturity — HRTech Support Load', 'HRT-011', '["RC-HRT-048"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Measure how much engineering time goes into support.", "Put a support owner between clients and engineers.", "Protect build capacity with a cap."]'::jsonb, '[{"name": "Protect Engineering Time", "brief": "A support layer so build capacity is not consumed by tickets."}]'::jsonb),
  ('INT-HRT-027', 'Growth to Maturity — HRTech Security Posture', 'HRT-012', '["RC-HRT-049", "RC-HRT-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Collect the security questionnaires buyers have sent you.", "Find the common gaps and close them.", "Pursue the certification your buyers keep asking for."]'::jsonb, '[{"name": "Close the Security Gaps", "brief": "Using buyer questionnaires as the roadmap for what to fix."}]'::jsonb),
  ('INT-HRT-028', 'Growth to Maturity — HRTech Security Posture', 'HRT-012', '["RC-HRT-051", "RC-HRT-052", "RC-HRT-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Put formal access controls around client data.", "Get an independent review or test of your system.", "Check every security clause before signing it."]'::jsonb, '[{"name": "Controls, Testing and Contracts", "brief": "Formal access control, outside testing and terms you can honour."}]'::jsonb),
  ('INT-HRT-029', 'Growth to Maturity — HRTech Regulatory Change', 'HRT-013', '["RC-HRT-054", "RC-HRT-055"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Build one mechanism that applies a rule change to every client.", "Stop updating accounts one by one.", "Measure how long a change takes to reach everyone."]'::jsonb, '[{"name": "Push Changes Once", "brief": "One mechanism to apply a rule change across the whole base."}]'::jsonb),
  ('INT-HRT-030', 'Growth to Maturity — HRTech Regulatory Change', 'HRT-013', '["RC-HRT-056", "RC-HRT-057"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Check whether any client is still on outdated rules.", "Test every rule change before it goes live.", "Keep a log of what changed and when."]'::jsonb, '[{"name": "Test and Verify Rule Changes", "brief": "Checking coverage and correctness before a change reaches clients."}]'::jsonb),
  ('INT-HRT-031', 'Growth to Maturity — HRTech Integrations', 'HRT-014', '["RC-HRT-058", "RC-HRT-061"]'::jsonb, '[5, 6, 7]'::jsonb, 'Product Design', '["List every integration clients ask for, with how often.", "Build the top few properly rather than many badly.", "Say no to the long tail."]'::jsonb, '[{"name": "Build the Few That Matter", "brief": "Prioritising integrations by real demand instead of one off requests."}]'::jsonb),
  ('INT-HRT-032', 'Growth to Maturity — HRTech Integrations', 'HRT-014', '["RC-HRT-059", "RC-HRT-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Name an owner for integration maintenance.", "Monitor each connection so you know when it breaks.", "Fix it before the client reports it."]'::jsonb, '[{"name": "Own and Monitor Integrations", "brief": "One accountable person and monitoring so breaks are caught first."}]'::jsonb),
  ('INT-HRT-033', 'Growth to Maturity — HRTech Competitive Squeeze', 'HRT-015', '["RC-HRT-062", "RC-HRT-063", "RC-HRT-064"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["List what the bundled alternatives actually do.", "Find the one thing you do that they cannot.", "Build your pitch and roadmap around that."]'::jsonb, '[{"name": "Find the Gap They Cannot Fill", "brief": "Positioning against bundled suites on a real difference."}]'::jsonb),
  ('INT-HRT-034', 'Growth to Maturity — HRTech Competitive Squeeze', 'HRT-015', '["RC-HRT-065", "RC-HRT-066"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Track how often you discount to keep a client.", "Work out what that costs you annually.", "Compete on the difference instead of on price."]'::jsonb, '[{"name": "Stop Defending With Discounts", "brief": "Measuring retention discounting and replacing it with value."}]'::jsonb)
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
        ('Import / Export & Trade', 'trade_import_export', 'TRD', r"""-- ============================================================================
-- Ally :: Industry seed -- IMPORT/EXPORT & TRADE (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: trade_import_export
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (TRD-001, RC-TRD-014, S0-TRD-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : questions deliberately do NOT name statutes, forms, scheme names,
--            duty rates or realisation periods.  Trade rules change often --
--            realisation periods, incentive rates and product quality orders
--            have all moved repeatedly -- so the content asks the founder what
--            applies to THEM and when it was last checked, rather than stating
--            a parameter that will go stale.  One durable point IS encoded:
--            the realisation time limit runs from the DATE OF EXPORT, not from
--            whatever rule is current today.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (customs holds, payment realisation, working
--            capital, quality disputes, incentive dependence) starts at
--            Stage 0->1; renewals, concentration, rate volatility, recurring
--            compliance, scrutiny and channel dependence at Stage 1->10+.
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
  ('TRD-001', 'No Idea What It Takes to Move Goods Across a Border', 'Registrations, product codes, documents and clearances are all required before anything can legally cross, and none of it has been checked.', 'Idea & Validation', 'Trade Registration Basics', 'external', 3, 5, 9, '["Required registrations not known", "Product classification code not identified", "Assuming goods can simply be shipped", "Documents needed at each step unknown", "No plan for who handles compliance"]'::jsonb, '["trade_import_export"]'::jsonb),
  ('TRD-002', 'Landed Cost Never Worked Out', 'The price at origin is treated as the cost, ignoring duty, freight, insurance, clearing and handling that all land on top.', 'Idea & Validation', 'Trade Landed Cost', 'external', 4, 5, 9, '["Only the supplier price counted", "Duty not included in the cost", "Freight and insurance not counted", "Clearing and handling charges ignored", "Margin calculated on origin price alone"]'::jsonb, '["trade_import_export"]'::jsonb),
  ('TRD-003', 'The Party on the Other Side Is Unverified', 'Money or goods will move to a buyer or supplier in another country who has never been checked in any way.', 'Idea & Validation', 'Trade Counterparty Risk', 'external', 4, 6, 10, '["Counterparty found online and not verified", "No references or trade history checked", "Full payment arranged in advance", "No written contract or terms", "No plan if they do not deliver or pay"]'::jsonb, '["trade_import_export"]'::jsonb),
  ('TRD-004', 'Currency and Payment Route Not Thought About', 'The exchange rate moves between order and payment, and how money will legally come in or go out has not been decided.', 'Idea & Validation', 'Trade Currency and Payment', 'external', 4, 5, 9, '["Exchange rate movement not considered", "Payment method not decided", "No idea how foreign money legally enters or leaves", "Bank charges and conversion costs ignored", "Price quoted without a validity period"]'::jsonb, '["trade_import_export"]'::jsonb),
  ('TRD-005', 'Shipments Getting Stuck at Customs', 'Consignments are being held over classification, valuation or paperwork errors, and every day of delay costs money.', 'Operations & Systems', 'Trade Customs Clearance', 'external', 3, 6, 9, '["Shipments held for documentation errors", "Classification questioned by customs", "Demurrage and detention charges mounting", "Same mistakes repeating across shipments", "No checking of documents before dispatch"]'::jsonb, '["trade_import_export"]'::jsonb),
  ('TRD-006', 'Export Payment Not Coming Back on Time', 'Money owed from abroad is arriving late or not at all, and there are filing obligations attached to bringing it back.', 'Financial Management', 'Trade Payment Realisation', 'external', 4, 7, 10, '["Payments from buyers running late", "Time limits on bringing money back not known", "Filings linked to each shipment not completed", "Old entries still open in the bank record", "No follow up process for overdue payments"]'::jsonb, '["trade_import_export"]'::jsonb),
  ('TRD-007', 'Cash Locked in Goods in Transit', 'Money leaves when the order is placed and returns only long after delivery, so growth constantly starves the business of cash.', 'Financial Management', 'Trade Working Capital', 'external', 4, 6, 9, '["Long gap between paying and getting paid", "Cash tied up in goods on the water", "No credit line for the gap", "Growth making cash position worse", "Cycle length never measured"]'::jsonb, '["trade_import_export"]'::jsonb),
  ('TRD-008', 'Quality Disputes Across a Border Are Hard to Settle', 'Goods arrive not as described, and resolving it with a party in another country is slow, costly and often impossible.', 'Operations & Systems', 'Trade Quality Disputes', 'external', 3, 6, 9, '["Goods arriving different from sample", "No pre shipment inspection", "Rejection terms not agreed in advance", "No practical way to enforce a claim", "Losses absorbed rather than recovered"]'::jsonb, '["trade_import_export"]'::jsonb),
  ('TRD-009', 'Incentives and Refunds Treated as Certain Margin', 'Government incentives and duty refunds are built into pricing although they are notified for limited periods and can change.', 'Financial Management', 'Trade Incentive Dependence', 'external', 4, 6, 10, '["Incentive built into the selling price", "Validity period of the scheme not checked", "Refund timing assumed to be quick", "Margin negative without the incentive", "No plan if a scheme rate is reduced"]'::jsonb, '["trade_import_export"]'::jsonb),
  ('TRD-010', 'Registrations Lapsing Without Anyone Noticing', 'Trade registrations and licences need periodic renewal, and one lapse can block every shipment until it is fixed.', 'Operations & Systems', 'Trade Renewal Discipline', 'external', 3, 6, 10, '["Renewal dates remembered rather than managed", "A registration has lapsed or nearly lapsed", "Shipments blocked by an expired registration", "No single list of what must be renewed", "Nobody accountable for renewals"]'::jsonb, '["trade_import_export"]'::jsonb),
  ('TRD-011', 'Revenue Concentrated in One Market or Buyer', 'Most trade depends on a single country or a single counterparty, so one policy change or lost relationship ends most of the business.', 'Sales & Revenue', 'Trade Concentration', 'external', 4, 7, 10, '["Most revenue from one country", "Most revenue from one buyer or supplier", "No alternative market developed", "Terms dictated by the dominant party", "No plan if that market closes"]'::jsonb, '["trade_import_export"]'::jsonb),
  ('TRD-012', 'Freight and Currency Swings Destroying Margin', 'Shipping rates and exchange rates move sharply, and long order cycles mean the price was fixed before the costs were known.', 'Financial Management', 'Trade Rate Volatility', 'external', 4, 6, 10, '["Freight rates moving sharply between quote and shipment", "Currency movement eating margin", "Prices fixed long before costs are known", "No hedging or price adjustment clause", "Margin per shipment varying wildly"]'::jsonb, '["trade_import_export"]'::jsonb),
  ('TRD-013', 'Compliance Is Now a Recurring Monthly Burden', 'Filings, declarations and reconciliations recur on a cycle, and at volume they can no longer be done by memory.', 'Operations & Systems', 'Trade Compliance Operations', 'external', 3, 7, 10, '["Filings done from memory rather than a calendar", "Volume making manual filing impractical", "Deadlines missed or filed late", "No reconciliation between shipments and filings", "One person holding all the knowledge"]'::jsonb, '["trade_import_export"]'::jsonb),
  ('TRD-014', 'Greater Scrutiny Comes With Greater Volume', 'Larger trade volumes attract closer examination of valuation, origin and classification, and past shortcuts surface as liabilities.', 'Operations & Systems', 'Trade Regulatory Scrutiny', 'external', 3, 7, 10, '["Valuation or origin queried by authorities", "Past declarations inconsistent with each other", "No supporting records for older shipments", "Advice taken informally and not documented", "Exposure from historic shipments unknown"]'::jsonb, '["trade_import_export"]'::jsonb),
  ('TRD-015', 'Foreign Agents and Distributors Control the Market', 'Access to overseas customers runs entirely through agents or distributors who own the relationship and can be replaced only at great cost.', 'Sales & Revenue', 'Trade Channel Dependence', 'external', 4, 6, 9, '["All foreign sales through one agent or distributor", "No direct relationship with end customers", "Agent holding customer information", "Exclusive terms limiting alternatives", "No performance measurement of the agent"]'::jsonb, '["trade_import_export"]'::jsonb)
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
         t.primary_stage_group, '["trade_import_export"]'::jsonb, z.v
  FROM (VALUES
  ('RC-TRD-001', 'Required Registrations Not Known', 'Which registrations are needed before trading has not been established.', 'TRD-001', 'external', 'Knowledge', 0.73, 'Stage 0'),
  ('RC-TRD-002', 'Product Classification Code Not Identified', 'The code that decides duty and rules for this product is unknown.', 'TRD-001', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-TRD-003', 'Assuming Goods Can Simply Be Shipped', 'Believing a border crossing needs no more than a courier.', 'TRD-001', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-TRD-004', 'Documents Needed at Each Step Unknown', 'What paperwork must exist at each stage has not been checked.', 'TRD-001', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-TRD-005', 'No Owner for Compliance', 'Nobody has been made responsible for registrations and filings.', 'TRD-001', 'external', 'Operational', 0.64, 'Stage 0'),
  ('RC-TRD-006', 'Only the Supplier Price Counted', 'The cost is taken as the price quoted at origin.', 'TRD-002', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-TRD-007', 'Duty Not Included in the Cost', 'What the government will charge on entry is left out.', 'TRD-002', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-TRD-008', 'Freight and Insurance Not Counted', 'The cost of moving and covering the goods is missing.', 'TRD-002', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-TRD-009', 'Clearing and Handling Charges Ignored', 'Port, agent and handling costs are not in the numbers.', 'TRD-002', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-TRD-010', 'Margin Calculated on Origin Price', 'Profit is worked out before the real costs of arrival.', 'TRD-002', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-TRD-011', 'Counterparty Found Online and Not Verified', 'The other party is known only through a listing or message.', 'TRD-003', 'external', 'Behavioural', 0.73, 'Stage 0'),
  ('RC-TRD-012', 'No References or Trade History Checked', 'Nobody has confirmed the counterparty has done this before.', 'TRD-003', 'external', 'Behavioural', 0.71, 'Stage 0'),
  ('RC-TRD-013', 'Full Payment Arranged in Advance', 'All the money moves before anything is received.', 'TRD-003', 'external', 'Strategic', 0.72, 'Stage 0'),
  ('RC-TRD-014', 'No Written Contract or Terms', 'Nothing records what was agreed or what happens if it fails.', 'TRD-003', 'external', 'Operational', 0.70, 'Stage 0'),
  ('RC-TRD-015', 'No Plan If They Do Not Deliver or Pay', 'There is no route to recover money or goods across a border.', 'TRD-003', 'external', 'Strategic', 0.69, 'Stage 0'),
  ('RC-TRD-016', 'Exchange Rate Movement Not Considered', 'The rate is assumed to be the same when payment happens.', 'TRD-004', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-TRD-017', 'Payment Route Not Decided', 'How money will legally move in or out has not been settled.', 'TRD-004', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-TRD-018', 'Bank and Conversion Costs Ignored', 'What the bank takes on each transfer is not in the price.', 'TRD-004', 'external', 'Knowledge', 0.67, 'Stage 0'),
  ('RC-TRD-019', 'No Document Check Before Dispatch', 'Paperwork is not verified before the goods move.', 'TRD-005', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-TRD-020', 'Classification Questioned by Customs', 'The code declared is disputed, holding the consignment.', 'TRD-005', 'external', 'Knowledge', 0.71, 'Stage 0→1'),
  ('RC-TRD-021', 'Demurrage and Detention Mounting', 'Each day a shipment sits incurs charges nobody budgeted.', 'TRD-005', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-TRD-022', 'Same Mistakes Repeating', 'Errors recur because their cause is never fixed.', 'TRD-005', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-TRD-023', 'No Relationship With a Competent Clearing Agent', 'Clearance depends on whoever was cheapest.', 'TRD-005', 'external', 'Operational', 0.67, 'Stage 0→1'),
  ('RC-TRD-024', 'Time Limits on Bringing Money Back Not Known', 'The period allowed to realise export proceeds is unknown.', 'TRD-006', 'external', 'Knowledge', 0.74, 'Stage 0→1'),
  ('RC-TRD-025', 'Shipment Linked Filings Not Completed', 'The filings that close each export entry are not being done.', 'TRD-006', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-TRD-026', 'Old Entries Still Open', 'Past shipments remain unreconciled in the bank record.', 'TRD-006', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-TRD-027', 'No Follow Up Process for Overdue Payments', 'Chasing foreign buyers happens only when someone remembers.', 'TRD-006', 'external', 'Behavioural', 0.68, 'Stage 0→1'),
  ('RC-TRD-028', 'Payment Terms Too Generous', 'Credit given to foreign buyers is longer than the business can fund.', 'TRD-006', 'external', 'Strategic', 0.69, 'Stage 0→1'),
  ('RC-TRD-029', 'Long Gap Between Paying and Getting Paid', 'Money goes out months before it comes back.', 'TRD-007', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-TRD-030', 'Cash Tied Up in Goods in Transit', 'Value sits on the water earning nothing.', 'TRD-007', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-TRD-031', 'No Credit Line for the Gap', 'Nothing has been arranged to bridge the cycle.', 'TRD-007', 'external', 'Strategic', 0.70, 'Stage 0→1'),
  ('RC-TRD-032', 'Cycle Length Never Measured', 'How many days the cash cycle actually runs is unknown.', 'TRD-007', 'external', 'Knowledge', 0.69, 'Stage 0→1'),
  ('RC-TRD-033', 'Growth Worsening the Cash Position', 'Each new order deepens the cash strain.', 'TRD-007', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-TRD-034', 'No Pre Shipment Inspection', 'Nothing is checked before the goods leave the origin.', 'TRD-008', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-TRD-035', 'Rejection Terms Not Agreed in Advance', 'What counts as acceptable was never defined in writing.', 'TRD-008', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-TRD-036', 'No Practical Way to Enforce a Claim', 'Legal recourse across a border is too slow or costly to use.', 'TRD-008', 'external', 'Strategic', 0.70, 'Stage 0→1'),
  ('RC-TRD-037', 'Losses Absorbed Rather Than Recovered', 'Bad consignments are written off instead of claimed.', 'TRD-008', 'external', 'Behavioural', 0.67, 'Stage 0→1'),
  ('RC-TRD-038', 'Incentive Built Into the Selling Price', 'The scheme benefit is assumed when quoting the customer.', 'TRD-009', 'external', 'Behavioural', 0.74, 'Stage 0→1'),
  ('RC-TRD-039', 'Validity Period Not Checked', 'Nobody has confirmed how long the scheme rate is notified for.', 'TRD-009', 'external', 'Knowledge', 0.72, 'Stage 0→1'),
  ('RC-TRD-040', 'Refund Timing Assumed Quick', 'Money from a scheme is treated as if it arrives immediately.', 'TRD-009', 'external', 'Knowledge', 0.70, 'Stage 0→1'),
  ('RC-TRD-041', 'Renewal Dates Remembered Not Managed', 'Expiry dates live in memory rather than in a system.', 'TRD-010', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-TRD-042', 'No Single List of Renewals', 'Nothing records everything that must be kept current.', 'TRD-010', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-TRD-043', 'Nobody Accountable for Renewals', 'No named person owns keeping registrations alive.', 'TRD-010', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-TRD-044', 'Intermittent Trading Hides a Lapse', 'Gaps between shipments mean an expired registration is not noticed.', 'TRD-010', 'external', 'Operational', 0.68, 'Stage 1→10+'),
  ('RC-TRD-045', 'Most Revenue From One Country', 'Trade depends overwhelmingly on a single market.', 'TRD-011', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-TRD-046', 'Most Revenue From One Counterparty', 'A single buyer or supplier carries most of the business.', 'TRD-011', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-TRD-047', 'No Alternative Market Developed', 'Nothing has been built that could replace the main market.', 'TRD-011', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-TRD-048', 'Terms Dictated by the Dominant Party', 'The larger side sets price and conditions.', 'TRD-011', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-TRD-049', 'No Plan If That Market Closes', 'Nothing prepared for a policy change or border restriction.', 'TRD-011', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-TRD-050', 'Freight Rates Moving Between Quote and Shipment', 'Shipping costs change after the price is agreed.', 'TRD-012', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-TRD-051', 'Currency Movement Eating Margin', 'Exchange rate shifts remove profit between order and payment.', 'TRD-012', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-TRD-052', 'Prices Fixed Before Costs Are Known', 'Quotes are committed long before the real costs settle.', 'TRD-012', 'external', 'Behavioural', 0.70, 'Stage 1→10+'),
  ('RC-TRD-053', 'No Hedging or Price Adjustment Clause', 'Nothing protects the business when rates move.', 'TRD-012', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-TRD-054', 'Margin Per Shipment Varying Wildly', 'Profit on individual shipments is unpredictable.', 'TRD-012', 'external', 'Operational', 0.67, 'Stage 1→10+'),
  ('RC-TRD-055', 'Filings Done From Memory', 'Compliance depends on somebody remembering.', 'TRD-013', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-TRD-056', 'Volume Making Manual Filing Impractical', 'The number of transactions has outgrown manual handling.', 'TRD-013', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-TRD-057', 'No Reconciliation Between Shipments and Filings', 'Nobody checks that every shipment has its matching filing.', 'TRD-013', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-TRD-058', 'One Person Holding All the Knowledge', 'Compliance capability sits with a single individual.', 'TRD-013', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-TRD-059', 'Valuation or Origin Queried', 'Authorities are challenging declared value or country of origin.', 'TRD-014', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-TRD-060', 'Past Declarations Inconsistent', 'Earlier filings do not agree with each other.', 'TRD-014', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-TRD-061', 'No Supporting Records for Older Shipments', 'Documents backing past declarations cannot be produced.', 'TRD-014', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-TRD-062', 'Advice Taken Informally', 'Decisions were made on verbal guidance with nothing in writing.', 'TRD-014', 'external', 'Behavioural', 0.69, 'Stage 1→10+'),
  ('RC-TRD-063', 'All Foreign Sales Through One Agent', 'A single intermediary controls access to the market.', 'TRD-015', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-TRD-064', 'No Direct Relationship With End Customers', 'The business does not know who finally buys its goods.', 'TRD-015', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-TRD-065', 'Exclusive Terms Limiting Alternatives', 'Contracts prevent building any other route to market.', 'TRD-015', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-TRD-066', 'No Performance Measurement of the Agent', 'Nothing tracks whether the agent is actually performing.', 'TRD-015', 'external', 'Operational', 0.68, 'Stage 1→10+')
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
         '["trade_import_export"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-TRD-001', 'Do you know which registrations you need before you can trade across a border?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-001', 'RC-TRD-001', 1, 'Stage 0'),
  ('S0-TRD-002', 'Do you know the classification code for your product?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-001', 'RC-TRD-002', 2, 'Stage 0'),
  ('S0-TRD-003', 'Do you think you can just courier goods abroad and be done?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-001', 'RC-TRD-003', 1, 'Stage 0'),
  ('S0-TRD-004', 'Do you know what documents are needed at each stage of a shipment?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-001', 'RC-TRD-004', 2, 'Stage 0'),
  ('S0-TRD-005', 'Who in your team would handle the paperwork and filings?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-001', 'RC-TRD-005', 2, 'Stage 0'),
  ('S0-TRD-006', 'What will one unit actually cost you by the time it reaches your warehouse?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-002', 'RC-TRD-006', 1, 'Stage 0'),
  ('S0-TRD-007', 'Have you included duty in that cost?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-002', 'RC-TRD-007', 1, 'Stage 0'),
  ('S0-TRD-008', 'Have you included freight and insurance?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-002', 'RC-TRD-008', 2, 'Stage 0'),
  ('S0-TRD-009', 'Have you included clearing, port and agent charges?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-002', 'RC-TRD-009', 2, 'Stage 0'),
  ('S0-TRD-010', 'Did you work out your margin on the supplier price or on the landed cost?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-002', 'RC-TRD-010', 2, 'Stage 0'),
  ('S0-TRD-011', 'How did you find the party on the other side, and what have you checked about them?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-003', 'RC-TRD-011', 1, 'Stage 0'),
  ('S0-TRD-012', 'Have you seen any proof they have traded before?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-003', 'RC-TRD-012', 2, 'Stage 0'),
  ('S0-TRD-013', 'Are you paying the full amount before you receive anything?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-003', 'RC-TRD-013', 1, 'Stage 0'),
  ('S0-TRD-014', 'Is there a written contract, and what does it say happens if things go wrong?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-003', 'RC-TRD-014', 2, 'Stage 0'),
  ('S0-TRD-015', 'If the exchange rate moved against you before payment, what happens to your margin?', 'open_text', 'Idea & Validation', 'CORE', 'TRD-004', 'RC-TRD-016', 2, 'Stage 0'),
  ('S01-TRD-001', 'How many of your shipments have been held up, and why?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-005', 'RC-TRD-019', 2, 'Stage 0→1'),
  ('S01-TRD-002', 'Has customs ever questioned the code you declared?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-005', 'RC-TRD-020', 2, 'Stage 0→1'),
  ('S01-TRD-003', 'What have delays cost you in demurrage and detention?', 'open_text', 'Financial Management', 'CORE', 'TRD-005', 'RC-TRD-021', 2, 'Stage 0→1'),
  ('S01-TRD-004', 'Are the same paperwork mistakes happening again?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-005', 'RC-TRD-022', 2, 'Stage 0→1'),
  ('S01-TRD-005', 'How did you choose your clearing agent?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-005', 'RC-TRD-023', 2, 'Stage 0→1'),
  ('S01-TRD-006', 'Do you know how long you have to bring export payment back?', 'open_text', 'Financial Management', 'CORE', 'TRD-006', 'RC-TRD-024', 3, 'Stage 0→1'),
  ('S01-TRD-007', 'Are the filings that close each shipment actually being done?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-006', 'RC-TRD-025', 3, 'Stage 0→1'),
  ('S01-TRD-008', 'Are any old shipments still showing as unpaid in your bank record?', 'open_text', 'Financial Management', 'CORE', 'TRD-006', 'RC-TRD-026', 3, 'Stage 0→1'),
  ('S01-TRD-009', 'Who chases a foreign buyer who has not paid, and how often?', 'open_text', 'Financial Management', 'CORE', 'TRD-006', 'RC-TRD-027', 2, 'Stage 0→1'),
  ('S01-TRD-010', 'How much credit are you giving foreign buyers, and can you fund it?', 'open_text', 'Financial Management', 'CORE', 'TRD-006', 'RC-TRD-028', 3, 'Stage 0→1'),
  ('S01-TRD-011', 'How many days pass between paying your supplier and getting paid?', 'open_text', 'Financial Management', 'CORE', 'TRD-007', 'RC-TRD-029', 2, 'Stage 0→1'),
  ('S01-TRD-012', 'How much of your money is sitting in goods in transit right now?', 'open_text', 'Financial Management', 'CORE', 'TRD-007', 'RC-TRD-030', 2, 'Stage 0→1'),
  ('S01-TRD-013', 'Do you have a credit line to cover that gap?', 'open_text', 'Financial Management', 'CORE', 'TRD-007', 'RC-TRD-031', 2, 'Stage 0→1'),
  ('S01-TRD-014', 'Has anyone measured how long your full cash cycle takes?', 'open_text', 'Financial Management', 'CORE', 'TRD-007', 'RC-TRD-032', 3, 'Stage 0→1'),
  ('S01-TRD-015', 'Does taking more orders make your cash position better or worse?', 'open_text', 'Financial Management', 'CORE', 'TRD-007', 'RC-TRD-033', 3, 'Stage 0→1'),
  ('S01-TRD-016', 'Is anything inspected before the goods leave the other country?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-008', 'RC-TRD-034', 2, 'Stage 0→1'),
  ('S01-TRD-017', 'Is it written down what counts as acceptable quality?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-008', 'RC-TRD-035', 2, 'Stage 0→1'),
  ('S01-TRD-018', 'If a consignment arrives wrong, how would you actually recover the money?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-008', 'RC-TRD-036', 3, 'Stage 0→1'),
  ('S01-TRD-019', 'Is any government incentive or refund built into your selling price?', 'open_text', 'Financial Management', 'CORE', 'TRD-009', 'RC-TRD-038', 2, 'Stage 0→1'),
  ('S01-TRD-020', 'Do you know until when that scheme rate is notified?', 'open_text', 'Financial Management', 'CORE', 'TRD-009', 'RC-TRD-039', 3, 'Stage 0→1'),
  ('S10-TRD-001', 'Can you list every registration you hold and when each expires?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-010', 'RC-TRD-042', 2, 'Stage 1→10+'),
  ('S10-TRD-002', 'Who is responsible for keeping them current?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-010', 'RC-TRD-043', 2, 'Stage 1→10+'),
  ('S10-TRD-003', 'Has a registration ever lapsed and blocked a shipment?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-010', 'RC-TRD-041', 2, 'Stage 1→10+'),
  ('S10-TRD-004', 'If you did not trade for six months, would you notice an expiry?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-010', 'RC-TRD-044', 3, 'Stage 1→10+'),
  ('S10-TRD-005', 'What share of your revenue comes from one country?', 'open_text', 'Sales & Revenue', 'CORE', 'TRD-011', 'RC-TRD-045', 2, 'Stage 1→10+'),
  ('S10-TRD-006', 'What share comes from one buyer or supplier?', 'open_text', 'Sales & Revenue', 'CORE', 'TRD-011', 'RC-TRD-046', 2, 'Stage 1→10+'),
  ('S10-TRD-007', 'Have you developed any alternative market?', 'open_text', 'Strategy & Planning', 'CORE', 'TRD-011', 'RC-TRD-047', 2, 'Stage 1→10+'),
  ('S10-TRD-008', 'Who sets the terms in your main relationship, you or them?', 'open_text', 'Sales & Revenue', 'CORE', 'TRD-011', 'RC-TRD-048', 3, 'Stage 1→10+'),
  ('S10-TRD-009', 'If that market closed to you next month, what would you do?', 'open_text', 'Strategy & Planning', 'CORE', 'TRD-011', 'RC-TRD-049', 3, 'Stage 1→10+'),
  ('S10-TRD-010', 'How much have freight rates moved between your quote and your shipment?', 'open_text', 'Financial Management', 'CORE', 'TRD-012', 'RC-TRD-050', 2, 'Stage 1→10+'),
  ('S10-TRD-011', 'How much margin has currency movement taken from you this year?', 'open_text', 'Financial Management', 'CORE', 'TRD-012', 'RC-TRD-051', 3, 'Stage 1→10+'),
  ('S10-TRD-012', 'How long before shipment do you fix your price?', 'open_text', 'Financial Management', 'CORE', 'TRD-012', 'RC-TRD-052', 2, 'Stage 1→10+'),
  ('S10-TRD-013', 'Do your contracts let you adjust price if rates move?', 'open_text', 'Financial Management', 'CORE', 'TRD-012', 'RC-TRD-053', 3, 'Stage 1→10+'),
  ('S10-TRD-014', 'How much does your margin vary from one shipment to the next?', 'open_text', 'Financial Management', 'CORE', 'TRD-012', 'RC-TRD-054', 2, 'Stage 1→10+'),
  ('S10-TRD-015', 'Are your filings driven by a calendar or by memory?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-013', 'RC-TRD-055', 2, 'Stage 1→10+'),
  ('S10-TRD-016', 'Can you still handle your filings manually at this volume?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-013', 'RC-TRD-056', 2, 'Stage 1→10+'),
  ('S10-TRD-017', 'Does anyone check that every shipment has its matching filing?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-013', 'RC-TRD-057', 3, 'Stage 1→10+'),
  ('S10-TRD-018', 'If the person who handles compliance left, what would happen?', 'open_text', 'Team & Leadership', 'CORE', 'TRD-013', 'RC-TRD-058', 3, 'Stage 1→10+'),
  ('S10-TRD-019', 'Have authorities ever questioned your declared value or country of origin?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-014', 'RC-TRD-059', 3, 'Stage 1→10+'),
  ('S10-TRD-020', 'Do your past declarations agree with each other?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-014', 'RC-TRD-060', 3, 'Stage 1→10+'),
  ('S10-TRD-021', 'Could you produce supporting records for a shipment from two years ago?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-014', 'RC-TRD-061', 3, 'Stage 1→10+'),
  ('S10-TRD-022', 'Is the advice you acted on written down anywhere?', 'open_text', 'Operations & Systems', 'CORE', 'TRD-014', 'RC-TRD-062', 2, 'Stage 1→10+'),
  ('S10-TRD-023', 'Do all your foreign sales go through one agent or distributor?', 'open_text', 'Sales & Revenue', 'CORE', 'TRD-015', 'RC-TRD-063', 2, 'Stage 1→10+'),
  ('S10-TRD-024', 'Do you know who your end customers actually are?', 'open_text', 'Sales & Revenue', 'CORE', 'TRD-015', 'RC-TRD-064', 3, 'Stage 1→10+'),
  ('S10-TRD-025', 'How do you measure whether your agent is performing?', 'open_text', 'Sales & Revenue', 'CORE', 'TRD-015', 'RC-TRD-066', 2, 'Stage 1→10+')
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
  ('S0-TRD-001', 'technical-quality'),
  ('S0-TRD-002', 'technical-quality'),
  ('S0-TRD-003', 'technical-quality'),
  ('S0-TRD-004', 'technical-quality'),
  ('S0-TRD-005', 'technical-quality'),
  ('S0-TRD-006', 'willingness-to-pay'),
  ('S0-TRD-007', 'willingness-to-pay'),
  ('S0-TRD-008', 'willingness-to-pay'),
  ('S0-TRD-009', 'willingness-to-pay'),
  ('S0-TRD-010', 'willingness-to-pay'),
  ('S0-TRD-011', 'technical-quality'),
  ('S0-TRD-012', 'technical-quality'),
  ('S0-TRD-013', 'technical-quality'),
  ('S0-TRD-014', 'technical-quality'),
  ('S0-TRD-015', 'willingness-to-pay'),
  ('S01-TRD-001', 'technical-quality'),
  ('S01-TRD-002', 'technical-quality'),
  ('S01-TRD-003', 'technical-quality'),
  ('S01-TRD-004', 'technical-quality'),
  ('S01-TRD-005', 'technical-quality'),
  ('S01-TRD-006', 'willingness-to-pay'),
  ('S01-TRD-007', 'willingness-to-pay'),
  ('S01-TRD-008', 'willingness-to-pay'),
  ('S01-TRD-009', 'willingness-to-pay'),
  ('S01-TRD-010', 'willingness-to-pay'),
  ('S01-TRD-011', 'willingness-to-pay'),
  ('S01-TRD-012', 'willingness-to-pay'),
  ('S01-TRD-013', 'willingness-to-pay'),
  ('S01-TRD-014', 'willingness-to-pay'),
  ('S01-TRD-015', 'willingness-to-pay'),
  ('S01-TRD-016', 'technical-quality'),
  ('S01-TRD-017', 'technical-quality'),
  ('S01-TRD-018', 'technical-quality'),
  ('S01-TRD-019', 'willingness-to-pay'),
  ('S01-TRD-020', 'willingness-to-pay'),
  ('S10-TRD-001', 'technical-quality'),
  ('S10-TRD-002', 'technical-quality'),
  ('S10-TRD-003', 'technical-quality'),
  ('S10-TRD-004', 'technical-quality'),
  ('S10-TRD-005', 'channel-strategy'),
  ('S10-TRD-006', 'channel-strategy'),
  ('S10-TRD-007', 'channel-strategy'),
  ('S10-TRD-008', 'channel-strategy'),
  ('S10-TRD-009', 'channel-strategy'),
  ('S10-TRD-010', 'willingness-to-pay'),
  ('S10-TRD-011', 'willingness-to-pay'),
  ('S10-TRD-012', 'willingness-to-pay'),
  ('S10-TRD-013', 'willingness-to-pay'),
  ('S10-TRD-014', 'willingness-to-pay'),
  ('S10-TRD-015', 'technical-quality'),
  ('S10-TRD-016', 'technical-quality'),
  ('S10-TRD-017', 'technical-quality'),
  ('S10-TRD-018', 'technical-quality'),
  ('S10-TRD-019', 'technical-quality'),
  ('S10-TRD-020', 'technical-quality'),
  ('S10-TRD-021', 'technical-quality'),
  ('S10-TRD-022', 'technical-quality'),
  ('S10-TRD-023', 'channel-strategy'),
  ('S10-TRD-024', 'channel-strategy'),
  ('S10-TRD-025', 'channel-strategy')
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
         '["trade_import_export"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-TRD-001', 'Ideation — Trade Registration Basics', 'TRD-001', '["RC-TRD-001", "RC-TRD-003"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Find out which registrations you must hold before trading.", "Get them before you commit to any order.", "Write down what each costs and how long it takes."]'::jsonb, '[{"name": "Register Before You Trade", "brief": "Getting the mandatory registrations in place first."}]'::jsonb),
  ('INT-TRD-002', 'Ideation — Trade Registration Basics', 'TRD-001', '["RC-TRD-002", "RC-TRD-004"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Identify the classification code for your exact product.", "Use it to find the duty rate and any special rules.", "List the documents needed at each stage of a shipment."]'::jsonb, '[{"name": "Classify Your Product", "brief": "The code that determines duty, restrictions and paperwork."}]'::jsonb),
  ('INT-TRD-003', 'Ideation — Trade Registration Basics', 'TRD-001', '["RC-TRD-005"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Name one person responsible for registrations and filings.", "Keep a dated list of what must be renewed and when.", "Review it at a fixed time each year."]'::jsonb, '[{"name": "One Compliance Owner", "brief": "A single accountable person and a dated renewal list."}]'::jsonb),
  ('INT-TRD-004', 'Ideation — Trade Landed Cost', 'TRD-002', '["RC-TRD-006", "RC-TRD-007", "RC-TRD-008"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Build a landed cost sheet for one unit.", "Include supplier price, duty, freight and insurance.", "Compare that total with the price you planned to charge."]'::jsonb, '[{"name": "Landed Cost Sheet", "brief": "The real cost of one unit by the time it reaches you."}]'::jsonb),
  ('INT-TRD-005', 'Ideation — Trade Landed Cost', 'TRD-002', '["RC-TRD-009", "RC-TRD-010"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Add clearing, port, agent and handling charges to that sheet.", "Recalculate margin on the landed figure.", "Never quote a price from the origin cost again."]'::jsonb, '[{"name": "Margin on Landed, Not Origin", "brief": "Working profit out after every arrival cost is counted."}]'::jsonb),
  ('INT-TRD-006', 'Ideation — Trade Counterparty Risk', 'TRD-003', '["RC-TRD-011", "RC-TRD-012"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Verify the counterparty exists and has traded before.", "Ask for references and check at least two.", "Do a small first transaction before a large one."]'::jsonb, '[{"name": "Verify Before You Commit", "brief": "Checking the other party is real and has a trade history."}]'::jsonb),
  ('INT-TRD-007', 'Ideation — Trade Counterparty Risk', 'TRD-003', '["RC-TRD-013", "RC-TRD-015"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Avoid paying the full amount before receiving anything.", "Use a payment structure that protects both sides.", "Decide in advance what you would do if they fail to deliver."]'::jsonb, '[{"name": "Do Not Pay It All Upfront", "brief": "Structuring payment so risk is shared, not carried alone."}]'::jsonb),
  ('INT-TRD-008', 'Ideation — Trade Counterparty Risk', 'TRD-003', '["RC-TRD-014"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Put the agreement in writing before money moves.", "Cover quantity, quality, timing, payment and what happens on failure.", "Agree which country law applies."]'::jsonb, '[{"name": "Get It in Writing", "brief": "A written contract covering failure, not just the happy case."}]'::jsonb),
  ('INT-TRD-009', 'Ideation — Trade Currency and Payment', 'TRD-004', '["RC-TRD-016"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Work out what happens to margin if the rate moves against you.", "Give every quote a validity period.", "Decide whether you or the buyer carries the currency risk."]'::jsonb, '[{"name": "Price With a Validity Period", "brief": "Protecting margin against rate movement between quote and payment."}]'::jsonb),
  ('INT-TRD-010', 'Ideation — Trade Currency and Payment', 'TRD-004', '["RC-TRD-017", "RC-TRD-018"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Talk to your bank about how money legally moves in and out.", "Find out what they charge per transaction and on conversion.", "Include those costs in your price."]'::jsonb, '[{"name": "Know Your Payment Route", "brief": "Confirming the legal and real cost of moving money abroad."}]'::jsonb),
  ('INT-TRD-011', 'Validation to Traction — Trade Customs Clearance', 'TRD-005', '["RC-TRD-019", "RC-TRD-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Check every document against a fixed list before dispatch.", "Log every hold and what caused it.", "Fix the cause so the same hold cannot repeat."]'::jsonb, '[{"name": "Document Check and Hold Log", "brief": "A pre dispatch check plus a record of why shipments get held."}]'::jsonb),
  ('INT-TRD-012', 'Validation to Traction — Trade Customs Clearance', 'TRD-005', '["RC-TRD-020", "RC-TRD-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Get your classification confirmed by someone qualified.", "Use the same code consistently across shipments.", "Work with a clearing agent chosen on competence, not price."]'::jsonb, '[{"name": "Right Code, Right Agent", "brief": "Consistent classification and a capable clearing partner."}]'::jsonb),
  ('INT-TRD-013', 'Validation to Traction — Trade Customs Clearance', 'TRD-005', '["RC-TRD-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Total what delays have cost you in demurrage and detention.", "Put that number next to your margin.", "Use it to justify better preparation."]'::jsonb, '[{"name": "Price the Delay", "brief": "Making the cost of held shipments visible."}]'::jsonb),
  ('INT-TRD-014', 'Validation to Traction — Trade Payment Realisation', 'TRD-006', '["RC-TRD-024", "RC-TRD-025"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Find out the time limit that applies to your shipments.", "Note that the limit is set by the date of export, not today rules.", "Complete the filings that close each entry, every time."]'::jsonb, '[{"name": "Know Your Realisation Clock", "brief": "The time limit runs from shipment date, and filings must close each entry."}]'::jsonb),
  ('INT-TRD-015', 'Validation to Traction — Trade Payment Realisation', 'TRD-006', '["RC-TRD-026", "RC-TRD-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Ask your bank for a list of open export entries.", "Close or explain every one of them.", "Set a weekly rhythm for chasing overdue payments."]'::jsonb, '[{"name": "Clear the Open Entries", "brief": "Reconciling past shipments and chasing overdue money on a rhythm."}]'::jsonb),
  ('INT-TRD-016', 'Validation to Traction — Trade Payment Realisation', 'TRD-006', '["RC-TRD-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Work out how much credit you are extending abroad.", "Compare it against what your cash can fund.", "Shorten terms or secure the risk before taking more orders."]'::jsonb, '[{"name": "Cap Foreign Credit", "brief": "Limiting buyer credit to what the business can actually carry."}]'::jsonb),
  ('INT-TRD-017', 'Validation to Traction — Trade Working Capital', 'TRD-007', '["RC-TRD-029", "RC-TRD-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Measure the days from paying your supplier to being paid.", "Track it every month.", "Use it to plan how many orders you can run at once."]'::jsonb, '[{"name": "Measure the Cash Cycle", "brief": "Knowing the real number of days your money is out."}]'::jsonb),
  ('INT-TRD-018', 'Validation to Traction — Trade Working Capital', 'TRD-007', '["RC-TRD-030", "RC-TRD-031", "RC-TRD-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Arrange a credit line sized to the cycle.", "Cap concurrent shipments at what your cash can carry.", "Check whether growth is improving or worsening cash."]'::jsonb, '[{"name": "Fund the Gap Deliberately", "brief": "Credit and a concurrency cap sized to the real cycle."}]'::jsonb),
  ('INT-TRD-019', 'Validation to Traction — Trade Quality Disputes', 'TRD-008', '["RC-TRD-034", "RC-TRD-035"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Arrange inspection before goods leave the origin.", "Write down exactly what counts as acceptable.", "Make both part of every contract."]'::jsonb, '[{"name": "Inspect Before It Ships", "brief": "Checking at origin and defining acceptable in writing."}]'::jsonb),
  ('INT-TRD-020', 'Validation to Traction — Trade Quality Disputes', 'TRD-008', '["RC-TRD-036", "RC-TRD-037"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Agree in the contract how disputes will be resolved and where.", "Hold back a payment portion until acceptance.", "Claim on bad consignments rather than absorbing them."]'::jsonb, '[{"name": "Build Recourse Into the Deal", "brief": "Dispute terms and retained payment so claims are possible."}]'::jsonb),
  ('INT-TRD-021', 'Validation to Traction — Trade Incentive Dependence', 'TRD-009', '["RC-TRD-038", "RC-TRD-039"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Check until when your scheme rates are actually notified.", "Recalculate margin with the incentive removed.", "If it goes negative, reprice now rather than later."]'::jsonb, '[{"name": "Price Without the Incentive", "brief": "Testing whether the business works if the scheme changes."}]'::jsonb),
  ('INT-TRD-022', 'Validation to Traction — Trade Incentive Dependence', 'TRD-009', '["RC-TRD-040"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Record how long refunds actually take to arrive.", "Plan cash assuming that delay, not immediate credit.", "Track outstanding claims like any other receivable."]'::jsonb, '[{"name": "Treat Refunds as Receivables", "brief": "Planning cash on when scheme money really arrives."}]'::jsonb),
  ('INT-TRD-023', 'Growth to Maturity — Trade Renewal Discipline', 'TRD-010', '["RC-TRD-041", "RC-TRD-042", "RC-TRD-043"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Build one register of every registration with its expiry date.", "Set reminders well before each renewal window.", "Give one named person responsibility for all of them."]'::jsonb, '[{"name": "Renewal Register", "brief": "One dated list and one owner so nothing lapses."}]'::jsonb),
  ('INT-TRD-024', 'Growth to Maturity — Trade Renewal Discipline', 'TRD-010', '["RC-TRD-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Put renewals on a calendar rather than relying on trading activity.", "Check status even in months with no shipments.", "Confirm before quoting, not after winning an order."]'::jsonb, '[{"name": "Check Even When Idle", "brief": "Renewals on a calendar so quiet periods do not hide a lapse."}]'::jsonb),
  ('INT-TRD-025', 'Growth to Maturity — Trade Concentration', 'TRD-011', '["RC-TRD-045", "RC-TRD-046", "RC-TRD-047"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Measure revenue share by country and by counterparty.", "Set a ceiling for each.", "Start developing one alternative market before you need it."]'::jsonb, '[{"name": "Measure and Cap Concentration", "brief": "Knowing the dependence and deliberately building beyond it."}]'::jsonb),
  ('INT-TRD-026', 'Growth to Maturity — Trade Concentration', 'TRD-011', '["RC-TRD-048", "RC-TRD-049"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Write what you would do if your main market closed.", "Note which terms you accept only because of that dependence.", "Build the leverage to change them."]'::jsonb, '[{"name": "Plan for the Market Closing", "brief": "A written response to losing the dominant market."}]'::jsonb),
  ('INT-TRD-027', 'Growth to Maturity — Trade Rate Volatility', 'TRD-012', '["RC-TRD-050", "RC-TRD-052", "RC-TRD-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Track margin per shipment, not just overall.", "Shorten the gap between fixing price and shipping.", "Find where the variation actually comes from."]'::jsonb, '[{"name": "Margin Per Shipment", "brief": "Seeing which shipments make money and why they differ."}]'::jsonb),
  ('INT-TRD-028', 'Growth to Maturity — Trade Rate Volatility', 'TRD-012', '["RC-TRD-051", "RC-TRD-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Add a price adjustment clause for freight and currency movement.", "Talk to your bank about protecting against rate movement.", "Decide deliberately who carries the risk."]'::jsonb, '[{"name": "Share the Rate Risk", "brief": "Adjustment clauses and cover instead of absorbing every swing."}]'::jsonb),
  ('INT-TRD-029', 'Growth to Maturity — Trade Compliance Operations', 'TRD-013', '["RC-TRD-055", "RC-TRD-056"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Put every recurring filing on a calendar with an owner.", "Move from memory to a system as volume grows.", "Review the calendar monthly."]'::jsonb, '[{"name": "Compliance Calendar", "brief": "Recurring obligations on a schedule rather than in someone head."}]'::jsonb),
  ('INT-TRD-030', 'Growth to Maturity — Trade Compliance Operations', 'TRD-013', '["RC-TRD-057", "RC-TRD-058"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Reconcile shipments against filings every month.", "Train a second person on the whole compliance process.", "Write the process down so it survives a departure."]'::jsonb, '[{"name": "Reconcile and Cross Train", "brief": "Monthly matching plus a second person who knows the process."}]'::jsonb),
  ('INT-TRD-031', 'Growth to Maturity — Trade Regulatory Scrutiny', 'TRD-014', '["RC-TRD-059", "RC-TRD-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Review past declarations for consistency.", "Correct anything that does not hold up before it is questioned.", "Use one consistent basis going forward."]'::jsonb, '[{"name": "Review Your Own History", "brief": "Finding inconsistencies before an authority does."}]'::jsonb),
  ('INT-TRD-032', 'Growth to Maturity — Trade Regulatory Scrutiny', 'TRD-014', '["RC-TRD-061", "RC-TRD-062"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Keep supporting records for every shipment for the required period.", "Get significant positions confirmed in writing by a qualified adviser.", "Stop relying on verbal guidance."]'::jsonb, '[{"name": "Records and Written Advice", "brief": "Documentation you could produce years later, and advice on paper."}]'::jsonb),
  ('INT-TRD-033', 'Growth to Maturity — Trade Channel Dependence', 'TRD-015', '["RC-TRD-063", "RC-TRD-064"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Find out who your end customers actually are.", "Build at least one direct relationship in the market.", "Measure what share of sales depends on one intermediary."]'::jsonb, '[{"name": "Reach Past the Agent", "brief": "Knowing the end customer instead of only the intermediary."}]'::jsonb),
  ('INT-TRD-034', 'Growth to Maturity — Trade Channel Dependence', 'TRD-015', '["RC-TRD-065", "RC-TRD-066"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Set performance targets for every agent and review them.", "Avoid exclusivity without matching commitments.", "Keep the right to appoint alternatives if targets are missed."]'::jsonb, '[{"name": "Hold Agents to Terms", "brief": "Measured performance and exclusivity only where it is earned."}]'::jsonb)
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
        # Defensive normalization in case the source ever passes through a
        # Windows encoding path before execution.
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
            raise RuntimeError(
                f"{label} seed count mismatch: expected {expected}, got {actual}"
            )

        mapping_count = bind.execute(
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
                "question_pattern": rf"^(S0|S01|S10)-{prefix}-",
            },
        ).scalar_one()

        if mapping_count != 60:
            raise RuntimeError(
                f"{label} industry mapping mismatch: expected 60, got {mapping_count}"
            )


def downgrade() -> None:
    raise RuntimeError(
        "Migration b7a19c2d4e6f is intentionally irreversible. "
        "Roll back application code without deleting production seed history."
    )
