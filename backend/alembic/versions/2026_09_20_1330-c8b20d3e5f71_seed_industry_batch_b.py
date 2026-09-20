"""seed industry batch B: legaltech, adtech, ngo, ecommerce/d2c

Revision ID: c8b20d3e5f71
Revises: b7a19c2d4e6f
Create Date: 2026-09-20
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "c8b20d3e5f71"
down_revision: Union[str, Sequence[str], None] = "b7a19c2d4e6f"
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
        ('legaltech', 'Legal & LegalTech', 'Law firms, legal-tech platforms, contract management software, compliance and regulatory technology businesses.'),
        ('adtech_marketing', 'Marketing, Advertising & AdTech', 'Digital marketing agencies, ad-tech platforms, martech tools, influencer marketing platforms and PR businesses.'),
        ('ngo', 'Non-Profit, Social Impact & NGO', 'Non-profits, NGOs, impact-driven social enterprises, CSR-funded ventures and hybrid social-impact organisations.'),
        ('ecommerce_d2c', 'E-Commerce & D2C', 'Online retail brands, marketplace sellers, subscription commerce, quick commerce and D2C consumer brands.'),
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
        ('Legal & LegalTech', 'legaltech', 'LGL', r"""-- ============================================================================
-- Ally :: Industry seed -- LEGAL & LEGALTECH (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: legaltech
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (LGL-001, RC-LGL-014, S0-LGL-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : questions name no bar rules, statutes or professional conduct
--            provisions.  These differ by jurisdiction and change, so the
--            content asks the founder what applies to THEM.  Two durable
--            MECHANISMS are encoded, because they are structural rather than
--            parametric, and both catch founders who plan as if this were an
--            ordinary business:
--              1. Giving legal advice is a RESTRICTED activity -- who may do
--                 it, who may own the business and who may share in fees are
--                 all constrained, so a LegalTech product must know exactly
--                 where it stops short of advice.
--              2. How clients may be APPROACHED is restricted for
--                 practitioners in ways that do not apply elsewhere, so a
--                 growth plan built on ordinary paid advertising may not be
--                 available at all.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (founder capacity, billing, templates,
--            confidentiality, work origination) starts at Stage 0->1; senior
--            talent, client concentration, professional risk, conflicts, the
--            technology shift and knowledge retention at Stage 1->10+.
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
  ('LGL-001', 'Unclear Whether This Is a Law Practice or a Software Business', 'Who may give legal advice, who may own the business and what may be charged differ sharply between the two, and the line has not been drawn.', 'Idea & Validation', 'Legal Regulatory Position', 'external', 3, 6, 10, '["No decision on practising law versus selling software", "Assuming anyone can give legal advice", "Ownership and who may share fees not checked", "Not known whether the offering counts as legal advice", "No plan for who handles compliance"]'::jsonb, '["legaltech"]'::jsonb),
  ('LGL-002', 'How Clients Can Be Approached Has Not Been Checked', 'Marketing and client solicitation are restricted for legal practitioners in ways that do not apply to other businesses, and this has not been looked into.', 'Idea & Validation', 'Legal Client Acquisition Rules', 'external', 2, 6, 10, '["Marketing plan built like any other business", "Restrictions on soliciting clients not checked", "Assuming paid advertising is available", "No idea what a practitioner may say publicly", "Plan depends on tactics that may not be permitted"]'::jsonb, '["legaltech"]'::jsonb),
  ('LGL-003', 'No Clear Client or Type of Work', 'Individuals, small businesses and large companies need completely different legal work, and no one group has been chosen.', 'Idea & Validation', 'Legal Client Clarity', 'external', 2, 4, 8, '["Target client described as everyone", "Willing to take any matter that comes", "No chosen area of law", "No idea where these clients look for help", "No conversation with a real client yet"]'::jsonb, '["legaltech"]'::jsonb),
  ('LGL-004', 'No Thinking About How Work Will Be Priced', 'Charging by the hour, by the matter or by retainer produces completely different businesses, and none has been chosen.', 'Idea & Validation', 'Legal Pricing Model', 'external', 4, 5, 9, '["No decision on hourly, fixed or retainer", "Cost of delivering one matter unknown", "Time spent per matter never measured", "Price set by asking what others charge", "No idea which work is profitable"]'::jsonb, '["legaltech"]'::jsonb),
  ('LGL-005', 'Revenue Stops When the Founder Stops Working', 'Income depends entirely on the founder own billable hours, so there is a hard ceiling and no income during illness or leave.', 'Sales & Revenue', 'Legal Founder Capacity', 'external', 5, 6, 9, '["All revenue tied to founder hours", "No income when the founder is unavailable", "Nobody else can handle a matter", "Hard ceiling on how much can be earned", "Turning work away for lack of time"]'::jsonb, '["legaltech"]'::jsonb),
  ('LGL-006', 'Clients Paying Late or Disputing Bills', 'Work is delivered before payment, and clients question the fee afterwards because expectations were never set.', 'Financial Management', 'Legal Billing and Collection', 'external', 4, 6, 9, '["Fees disputed after delivery", "No advance or retainer taken", "Scope not agreed in writing", "Payments running months late", "No follow up process for unpaid bills"]'::jsonb, '["legaltech"]'::jsonb),
  ('LGL-007', 'Every Matter Handled From Scratch', 'Nothing is reused between similar matters, so the same work is redone at full cost every time.', 'Operations & Systems', 'Legal Process and Templates', 'external', 3, 5, 9, '["No templates or precedent bank", "Same documents redrafted each time", "Each matter run differently", "Nothing captured after a matter closes", "Time spent on repetitive drafting"]'::jsonb, '["legaltech"]'::jsonb),
  ('LGL-008', 'Confidential Material Handled Casually', 'Client documents and information move through personal email and devices with no controls.', 'Operations & Systems', 'Legal Confidentiality', 'external', 3, 6, 10, '["Documents shared over personal accounts", "No access control on client files", "No record of who saw what", "Devices unsecured", "No plan if material leaks"]'::jsonb, '["legaltech"]'::jsonb),
  ('LGL-009', 'Work Comes Only From Who You Already Know', 'Every matter arrives through personal referral, so the pipeline cannot be grown or predicted.', 'Sales & Revenue', 'Legal Work Origination', 'external', 2, 6, 9, '["All work from personal referral", "No predictable flow of enquiries", "Pipeline cannot be forecast", "No visibility beyond existing contacts", "Quiet periods impossible to fill"]'::jsonb, '["legaltech"]'::jsonb),
  ('LGL-010', 'Senior People Are Scarce and Leave', 'Growth needs experienced practitioners, who are hard to find, expensive, and take clients with them when they go.', 'Team & Leadership', 'Legal Senior Talent', 'external', 5, 7, 10, '["Growth blocked by shortage of senior people", "Senior hires expensive and hard to find", "Departures taking clients with them", "No path for juniors to become senior", "No agreement covering what leavers may take"]'::jsonb, '["legaltech"]'::jsonb),
  ('LGL-011', 'Most Fees Come From a Few Clients', 'A handful of clients account for most billing, so they set terms and their departure would be severe.', 'Sales & Revenue', 'Legal Client Concentration', 'external', 4, 7, 10, '["Most fees from a few clients", "Rates pushed down by the largest client", "Payment terms dictated by the client", "No pipeline of replacement work", "Losing one client would threaten the firm"]'::jsonb, '["legaltech"]'::jsonb),
  ('LGL-012', 'One Piece of Bad Advice Could Be Catastrophic', 'As matters get larger, a single error in advice or a missed deadline could bring a claim that the business cannot absorb.', 'Operations & Systems', 'Legal Professional Risk', 'external', 3, 7, 10, '["No second review on significant advice", "Deadlines tracked informally", "Professional indemnity cover not reviewed", "No record of the basis for advice given", "Exposure on past matters unknown"]'::jsonb, '["legaltech"]'::jsonb),
  ('LGL-013', 'Conflicts Not Checked Systematically', 'New matters are taken on without a reliable check against existing and past clients, risking a conflict that forces withdrawal.', 'Operations & Systems', 'Legal Conflicts Management', 'external', 3, 7, 10, '["Conflict checks done from memory", "No central record of all clients and matters", "Past clients not checked", "No documented decision when a conflict is found", "Risk of having to withdraw mid matter"]'::jsonb, '["legaltech"]'::jsonb),
  ('LGL-014', 'Technology Changing What Clients Will Pay For', 'Work that was billed by the hour can increasingly be done faster or by software, and clients know it.', 'Strategy & Planning', 'Legal Technology Shift', 'external', 2, 6, 10, '["Clients questioning time based fees", "Routine drafting and research done faster by tools", "Revenue concentrated in work that is being automated", "No move toward advisory or judgement work", "Competitors pricing the same work lower"]'::jsonb, '["legaltech"]'::jsonb),
  ('LGL-015', 'The Firm Knows Nothing, Only the People Do', 'Expertise, precedents and client relationships live in individuals, so the business itself has little durable value.', 'Operations & Systems', 'Legal Knowledge Retention', 'external', 3, 6, 9, '["Expertise held by individuals not the firm", "Client relationships personal rather than institutional", "Precedents stored on personal drives", "Nothing transfers when someone leaves", "Business would be hard to sell or hand over"]'::jsonb, '["legaltech"]'::jsonb)
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
         t.primary_stage_group, '["legaltech"]'::jsonb, z.v
  FROM (VALUES
  ('RC-LGL-001', 'No Decision on Practice Versus Software', 'Whether this is legal practice or a product has not been settled.', 'LGL-001', 'external', 'Strategic', 0.74, 'Stage 0'),
  ('RC-LGL-002', 'Assuming Anyone Can Give Legal Advice', 'Not knowing that giving legal advice is a restricted activity.', 'LGL-001', 'external', 'Knowledge', 0.73, 'Stage 0'),
  ('RC-LGL-003', 'Ownership and Fee Sharing Not Checked', 'Who may own the business and share in fees has not been established.', 'LGL-001', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-LGL-004', 'Not Known Whether the Offering Counts as Advice', 'Whether the product crosses into legal advice is unexamined.', 'LGL-001', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-LGL-005', 'No Owner for Compliance', 'Nobody has been made responsible for the regulatory position.', 'LGL-001', 'external', 'Operational', 0.64, 'Stage 0'),
  ('RC-LGL-006', 'Marketing Planned Like Any Other Business', 'The plan assumes ordinary advertising and outreach are available.', 'LGL-002', 'external', 'Knowledge', 0.73, 'Stage 0'),
  ('RC-LGL-007', 'Solicitation Restrictions Not Checked', 'Limits on approaching potential clients have not been looked into.', 'LGL-002', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-LGL-008', 'Assuming Paid Advertising Is Available', 'Budget has been planned around channels that may not be permitted.', 'LGL-002', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-LGL-009', 'Plan Depends on Tactics That May Not Be Permitted', 'Growth rests on activity that could be disallowed.', 'LGL-002', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-LGL-010', 'Target Client Described as Everyone', 'No specific client type has been chosen to serve.', 'LGL-003', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-LGL-011', 'Willing to Take Any Matter', 'Work is accepted regardless of fit or expertise.', 'LGL-003', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-LGL-012', 'No Chosen Area of Law', 'Practice is spread across unrelated areas.', 'LGL-003', 'external', 'Strategic', 0.68, 'Stage 0'),
  ('RC-LGL-013', 'Where Clients Look for Help Is Unknown', 'How this client finds a practitioner has not been studied.', 'LGL-003', 'external', 'Knowledge', 0.67, 'Stage 0'),
  ('RC-LGL-014', 'No Conversation With a Real Client', 'Nobody who would actually instruct has been spoken to.', 'LGL-003', 'external', 'Behavioural', 0.66, 'Stage 0'),
  ('RC-LGL-015', 'No Decision on Hourly, Fixed or Retainer', 'The charging model has not been chosen.', 'LGL-004', 'external', 'Strategic', 0.72, 'Stage 0'),
  ('RC-LGL-016', 'Cost of Delivering One Matter Unknown', 'What a single matter costs to complete has never been worked out.', 'LGL-004', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-LGL-017', 'Time Per Matter Never Measured', 'Hours actually spent are not recorded.', 'LGL-004', 'external', 'Operational', 0.70, 'Stage 0'),
  ('RC-LGL-018', 'Price Set by Asking What Others Charge', 'Fees copy the market without knowing own cost.', 'LGL-004', 'external', 'Behavioural', 0.67, 'Stage 0'),
  ('RC-LGL-019', 'All Revenue Tied to Founder Hours', 'Income is a direct function of one person time.', 'LGL-005', 'external', 'Strategic', 0.74, 'Stage 0→1'),
  ('RC-LGL-020', 'Nobody Else Can Handle a Matter', 'No second person is capable of running the work.', 'LGL-005', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-LGL-021', 'No Income When the Founder Is Unavailable', 'Illness or leave stops earnings entirely.', 'LGL-005', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-LGL-022', 'Turning Work Away for Lack of Time', 'Demand exists but capacity does not.', 'LGL-005', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-LGL-023', 'Nothing Delegated to Junior Capacity', 'Work that could be done by others is still done by the founder.', 'LGL-005', 'external', 'Behavioural', 0.70, 'Stage 0→1'),
  ('RC-LGL-024', 'Scope Not Agreed in Writing', 'What is included was never set down before work began.', 'LGL-006', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-LGL-025', 'No Advance or Retainer Taken', 'Work is delivered before any money is received.', 'LGL-006', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-LGL-026', 'Fees Disputed After Delivery', 'Clients question the bill once the work is done.', 'LGL-006', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-LGL-027', 'No Follow Up Process for Unpaid Bills', 'Chasing happens only when someone remembers.', 'LGL-006', 'external', 'Behavioural', 0.69, 'Stage 0→1'),
  ('RC-LGL-028', 'Scope Creep Absorbed Without Charge', 'Extra work is done without revising the fee.', 'LGL-006', 'external', 'Behavioural', 0.71, 'Stage 0→1'),
  ('RC-LGL-029', 'No Templates or Precedent Bank', 'Nothing reusable has been built from past work.', 'LGL-007', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-LGL-030', 'Same Documents Redrafted Each Time', 'Drafting starts from nothing on every similar matter.', 'LGL-007', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-LGL-031', 'Each Matter Run Differently', 'There is no standard way of handling a matter type.', 'LGL-007', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-LGL-032', 'Nothing Captured After a Matter Closes', 'Lessons and documents are not saved for reuse.', 'LGL-007', 'external', 'Behavioural', 0.69, 'Stage 0→1'),
  ('RC-LGL-033', 'Documents Shared Over Personal Accounts', 'Client material moves through unmanaged channels.', 'LGL-008', 'external', 'Operational', 0.74, 'Stage 0→1'),
  ('RC-LGL-034', 'No Access Control on Client Files', 'Anyone in the business can open anything.', 'LGL-008', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-LGL-035', 'No Record of Who Saw What', 'Access to confidential material is not logged.', 'LGL-008', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-LGL-036', 'No Plan If Material Leaks', 'What would happen after a breach has not been considered.', 'LGL-008', 'external', 'Strategic', 0.71, 'Stage 0→1'),
  ('RC-LGL-037', 'All Work From Personal Referral', 'Every matter arrives through someone already known.', 'LGL-009', 'external', 'Strategic', 0.73, 'Stage 0→1'),
  ('RC-LGL-038', 'No Predictable Flow of Enquiries', 'Nothing generates enquiries on a reliable basis.', 'LGL-009', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-LGL-039', 'Pipeline Cannot Be Forecast', 'Future workload is unknown from one month to the next.', 'LGL-009', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-LGL-040', 'No Visibility Beyond Existing Contacts', 'Nobody outside the current network knows the practice exists.', 'LGL-009', 'external', 'Strategic', 0.69, 'Stage 0→1'),
  ('RC-LGL-041', 'Growth Blocked by Shortage of Senior People', 'Expansion depends on hires that cannot be found.', 'LGL-010', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-LGL-042', 'Departures Taking Clients With Them', 'Leavers carry relationships out of the business.', 'LGL-010', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-LGL-043', 'No Path for Juniors to Become Senior', 'Nothing develops the next layer internally.', 'LGL-010', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-LGL-044', 'No Agreement Covering What Leavers May Take', 'Nothing sets out what happens to clients on departure.', 'LGL-010', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-LGL-045', 'Most Fees From a Few Clients', 'A handful of relationships carry the billing.', 'LGL-011', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-LGL-046', 'Rates Pushed Down by the Largest Client', 'The dominant client sets what can be charged.', 'LGL-011', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-LGL-047', 'Payment Terms Dictated by the Client', 'Credit periods are imposed rather than negotiated.', 'LGL-011', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-LGL-048', 'No Pipeline of Replacement Work', 'Nothing is being built that could replace a lost client.', 'LGL-011', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-LGL-049', 'No Second Review on Significant Advice', 'Important advice goes out without another pair of eyes.', 'LGL-012', 'external', 'Operational', 0.74, 'Stage 1→10+'),
  ('RC-LGL-050', 'Deadlines Tracked Informally', 'Critical dates live in memory or scattered notes.', 'LGL-012', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-LGL-051', 'Indemnity Cover Not Reviewed', 'Insurance has not been matched to current exposure.', 'LGL-012', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-LGL-052', 'No Record of the Basis for Advice', 'Why advice was given is not documented.', 'LGL-012', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-LGL-053', 'Conflict Checks Done From Memory', 'New matters are cleared by recollection rather than record.', 'LGL-013', 'external', 'Operational', 0.74, 'Stage 1→10+'),
  ('RC-LGL-054', 'No Central Record of Clients and Matters', 'There is no single list to check against.', 'LGL-013', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-LGL-055', 'Past Clients Not Checked', 'Only current clients are considered when checking conflicts.', 'LGL-013', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-LGL-056', 'No Documented Decision When a Conflict Is Found', 'How a conflict was resolved is not recorded.', 'LGL-013', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-LGL-057', 'Clients Questioning Time Based Fees', 'Buyers increasingly resist paying for hours.', 'LGL-014', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-LGL-058', 'Routine Work Done Faster by Tools', 'Drafting and research no longer take the time they did.', 'LGL-014', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-LGL-059', 'Revenue Concentrated in Automatable Work', 'Most billing sits in exactly the work being automated.', 'LGL-014', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-LGL-060', 'No Move Toward Judgement Work', 'Nothing is shifting the mix toward advice that cannot be automated.', 'LGL-014', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-LGL-061', 'Expertise Held by Individuals Not the Firm', 'Knowledge lives in people rather than in the business.', 'LGL-015', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-LGL-062', 'Client Relationships Personal Rather Than Institutional', 'Clients are loyal to a person, not the firm.', 'LGL-015', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-LGL-063', 'Precedents Stored on Personal Drives', 'Reusable material is not held centrally.', 'LGL-015', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-LGL-064', 'Nothing Transfers When Someone Leaves', 'A departure takes the capability with it.', 'LGL-015', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-LGL-065', 'Exposure on Past Matters Unknown', 'Nobody knows what liability may still sit in closed files.', 'LGL-012', 'external', 'Knowledge', 0.70, 'Stage 1→10+'),
  ('RC-LGL-066', 'Competitors Pricing the Same Work Lower', 'Others are charging less for work that now takes less time.', 'LGL-014', 'external', 'Strategic', 0.70, 'Stage 1→10+')
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
         '["legaltech"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-LGL-001', 'Are you practising law, or selling software to people who do?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-001', 'RC-LGL-001', 1, 'Stage 0'),
  ('S0-LGL-002', 'Do you know who is legally allowed to give advice in your area?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-001', 'RC-LGL-002', 1, 'Stage 0'),
  ('S0-LGL-003', 'Have you checked who may own this business and share in the fees?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-001', 'RC-LGL-003', 2, 'Stage 0'),
  ('S0-LGL-004', 'Could what you plan to offer count as legal advice?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-001', 'RC-LGL-004', 2, 'Stage 0'),
  ('S0-LGL-005', 'Who would handle your regulatory position and filings?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-001', 'RC-LGL-005', 2, 'Stage 0'),
  ('S0-LGL-006', 'Have you checked what rules apply to how you can approach clients?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-002', 'RC-LGL-007', 1, 'Stage 0'),
  ('S0-LGL-007', 'Does your plan assume you can advertise like any other business?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-002', 'RC-LGL-006', 2, 'Stage 0'),
  ('S0-LGL-008', 'Have you budgeted for paid advertising, and is it actually permitted?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-002', 'RC-LGL-008', 2, 'Stage 0'),
  ('S0-LGL-009', 'If a tactic in your plan turned out not to be allowed, what is left?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-002', 'RC-LGL-009', 3, 'Stage 0'),
  ('S0-LGL-010', 'Who exactly is this for, individuals, small businesses or large companies?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-003', 'RC-LGL-010', 1, 'Stage 0'),
  ('S0-LGL-011', 'Have you chosen an area of law, or will you take anything?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-003', 'RC-LGL-012', 1, 'Stage 0'),
  ('S0-LGL-012', 'Where does your kind of client look for legal help today?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-003', 'RC-LGL-013', 2, 'Stage 0'),
  ('S0-LGL-013', 'Will you charge by the hour, per matter, or on a retainer?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-004', 'RC-LGL-015', 1, 'Stage 0'),
  ('S0-LGL-014', 'What does it cost you to complete one matter?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-004', 'RC-LGL-016', 2, 'Stage 0'),
  ('S0-LGL-015', 'Do you record how many hours a matter actually takes?', 'open_text', 'Idea & Validation', 'CORE', 'LGL-004', 'RC-LGL-017', 2, 'Stage 0'),
  ('S01-LGL-001', 'What share of your revenue depends on your own hours?', 'open_text', 'Sales & Revenue', 'CORE', 'LGL-005', 'RC-LGL-019', 2, 'Stage 0→1'),
  ('S01-LGL-002', 'If you took two weeks off, what would you earn?', 'open_text', 'Financial Management', 'CORE', 'LGL-005', 'RC-LGL-021', 2, 'Stage 0→1'),
  ('S01-LGL-003', 'Can anyone else in your team run a matter end to end?', 'open_text', 'Team & Leadership', 'CORE', 'LGL-005', 'RC-LGL-020', 2, 'Stage 0→1'),
  ('S01-LGL-004', 'Have you turned work away because you had no time?', 'open_text', 'Sales & Revenue', 'CORE', 'LGL-005', 'RC-LGL-022', 2, 'Stage 0→1'),
  ('S01-LGL-005', 'What are you still doing yourself that someone junior could do?', 'open_text', 'Team & Leadership', 'CORE', 'LGL-005', 'RC-LGL-023', 2, 'Stage 0→1'),
  ('S01-LGL-006', 'Do you agree the scope in writing before you start work?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-006', 'RC-LGL-024', 2, 'Stage 0→1'),
  ('S01-LGL-007', 'Do you take an advance or retainer before beginning?', 'open_text', 'Financial Management', 'CORE', 'LGL-006', 'RC-LGL-025', 2, 'Stage 0→1'),
  ('S01-LGL-008', 'How often do clients question the bill after delivery?', 'open_text', 'Financial Management', 'CORE', 'LGL-006', 'RC-LGL-026', 2, 'Stage 0→1'),
  ('S01-LGL-009', 'When the work grows beyond what was agreed, do you charge for it?', 'open_text', 'Financial Management', 'CORE', 'LGL-006', 'RC-LGL-028', 2, 'Stage 0→1'),
  ('S01-LGL-010', 'Who chases unpaid bills, and how often?', 'open_text', 'Financial Management', 'CORE', 'LGL-006', 'RC-LGL-027', 2, 'Stage 0→1'),
  ('S01-LGL-011', 'Do you have templates, or do you draft from scratch each time?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-007', 'RC-LGL-029', 2, 'Stage 0→1'),
  ('S01-LGL-012', 'How much of your drafting time is spent redoing similar work?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-007', 'RC-LGL-030', 2, 'Stage 0→1'),
  ('S01-LGL-013', 'Is there a standard way of running each type of matter?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-007', 'RC-LGL-031', 2, 'Stage 0→1'),
  ('S01-LGL-014', 'When a matter closes, is anything saved for next time?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-007', 'RC-LGL-032', 2, 'Stage 0→1'),
  ('S01-LGL-015', 'How do client documents move between you and your team?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-008', 'RC-LGL-033', 3, 'Stage 0→1'),
  ('S01-LGL-016', 'Can everyone in your office open every client file?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-008', 'RC-LGL-034', 3, 'Stage 0→1'),
  ('S01-LGL-017', 'Could you tell who has opened a particular client file?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-008', 'RC-LGL-035', 3, 'Stage 0→1'),
  ('S01-LGL-018', 'What would you do if client material leaked?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-008', 'RC-LGL-036', 3, 'Stage 0→1'),
  ('S01-LGL-019', 'Where did your last ten matters come from?', 'open_text', 'Sales & Revenue', 'CORE', 'LGL-009', 'RC-LGL-037', 2, 'Stage 0→1'),
  ('S01-LGL-020', 'Can you predict how much work you will have next month?', 'open_text', 'Sales & Revenue', 'CORE', 'LGL-009', 'RC-LGL-039', 2, 'Stage 0→1'),
  ('S10-LGL-001', 'Is a shortage of senior people limiting how much work you can take?', 'open_text', 'Team & Leadership', 'CORE', 'LGL-010', 'RC-LGL-041', 2, 'Stage 1→10+'),
  ('S10-LGL-002', 'When someone senior left, did clients go with them?', 'open_text', 'Team & Leadership', 'CORE', 'LGL-010', 'RC-LGL-042', 3, 'Stage 1→10+'),
  ('S10-LGL-003', 'How does a junior in your firm become senior?', 'open_text', 'Team & Leadership', 'CORE', 'LGL-010', 'RC-LGL-043', 2, 'Stage 1→10+'),
  ('S10-LGL-004', 'Is there an agreement covering what a leaver may take?', 'open_text', 'Team & Leadership', 'CORE', 'LGL-010', 'RC-LGL-044', 3, 'Stage 1→10+'),
  ('S10-LGL-005', 'What share of your fees comes from your top three clients?', 'open_text', 'Sales & Revenue', 'CORE', 'LGL-011', 'RC-LGL-045', 2, 'Stage 1→10+'),
  ('S10-LGL-006', 'Who sets your rates, you or your largest client?', 'open_text', 'Sales & Revenue', 'CORE', 'LGL-011', 'RC-LGL-046', 2, 'Stage 1→10+'),
  ('S10-LGL-007', 'Who decides your payment terms?', 'open_text', 'Financial Management', 'CORE', 'LGL-011', 'RC-LGL-047', 2, 'Stage 1→10+'),
  ('S10-LGL-008', 'If your largest client left, how long could you continue?', 'open_text', 'Strategy & Planning', 'CORE', 'LGL-011', 'RC-LGL-048', 3, 'Stage 1→10+'),
  ('S10-LGL-009', 'Does anyone review significant advice before it goes out?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-012', 'RC-LGL-049', 3, 'Stage 1→10+'),
  ('S10-LGL-010', 'How are critical deadlines tracked?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-012', 'RC-LGL-050', 3, 'Stage 1→10+'),
  ('S10-LGL-011', 'When did you last review your indemnity cover against what you now do?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-012', 'RC-LGL-051', 3, 'Stage 1→10+'),
  ('S10-LGL-012', 'Could you show why you gave the advice you gave two years ago?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-012', 'RC-LGL-052', 3, 'Stage 1→10+'),
  ('S10-LGL-013', 'How do you check a new matter for conflicts?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-013', 'RC-LGL-053', 3, 'Stage 1→10+'),
  ('S10-LGL-014', 'Is there one central list of every client and matter you have handled?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-013', 'RC-LGL-054', 3, 'Stage 1→10+'),
  ('S10-LGL-015', 'Do your conflict checks include past clients, not just current ones?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-013', 'RC-LGL-055', 3, 'Stage 1→10+'),
  ('S10-LGL-016', 'When a conflict comes up, is the decision written down?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-013', 'RC-LGL-056', 3, 'Stage 1→10+'),
  ('S10-LGL-017', 'Are clients pushing back on being billed by the hour?', 'open_text', 'Sales & Revenue', 'CORE', 'LGL-014', 'RC-LGL-057', 2, 'Stage 1→10+'),
  ('S10-LGL-018', 'How much of your billing is work that tools now do faster?', 'open_text', 'Strategy & Planning', 'CORE', 'LGL-014', 'RC-LGL-059', 3, 'Stage 1→10+'),
  ('S10-LGL-019', 'Has routine drafting and research got quicker in your firm?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-014', 'RC-LGL-058', 2, 'Stage 1→10+'),
  ('S10-LGL-020', 'Are you shifting toward work that needs judgement rather than hours?', 'open_text', 'Strategy & Planning', 'CORE', 'LGL-014', 'RC-LGL-060', 3, 'Stage 1→10+'),
  ('S10-LGL-021', 'If your most experienced person left, what would the firm lose?', 'open_text', 'Team & Leadership', 'CORE', 'LGL-015', 'RC-LGL-061', 3, 'Stage 1→10+'),
  ('S10-LGL-022', 'Are your clients loyal to you personally or to the firm?', 'open_text', 'Sales & Revenue', 'CORE', 'LGL-015', 'RC-LGL-062', 3, 'Stage 1→10+'),
  ('S10-LGL-023', 'Where are your precedents and templates stored?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-015', 'RC-LGL-063', 2, 'Stage 1→10+'),
  ('S10-LGL-024', 'When someone leaves, what stays behind?', 'open_text', 'Operations & Systems', 'CORE', 'LGL-015', 'RC-LGL-064', 3, 'Stage 1→10+'),
  ('S10-LGL-025', 'Could someone else run this firm if you stepped away?', 'open_text', 'Strategy & Planning', 'CORE', 'LGL-015', 'RC-LGL-061', 3, 'Stage 1→10+')
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
  ('S0-LGL-001', 'technical-quality'),
  ('S0-LGL-002', 'technical-quality'),
  ('S0-LGL-003', 'technical-quality'),
  ('S0-LGL-004', 'technical-quality'),
  ('S0-LGL-005', 'technical-quality'),
  ('S0-LGL-006', 'technical-quality'),
  ('S0-LGL-007', 'technical-quality'),
  ('S0-LGL-008', 'technical-quality'),
  ('S0-LGL-009', 'technical-quality'),
  ('S0-LGL-010', 'icp'),
  ('S0-LGL-011', 'icp'),
  ('S0-LGL-012', 'icp'),
  ('S0-LGL-013', 'willingness-to-pay'),
  ('S0-LGL-014', 'willingness-to-pay'),
  ('S0-LGL-015', 'willingness-to-pay'),
  ('S01-LGL-001', 'technical-quality'),
  ('S01-LGL-002', 'technical-quality'),
  ('S01-LGL-003', 'technical-quality'),
  ('S01-LGL-004', 'technical-quality'),
  ('S01-LGL-005', 'technical-quality'),
  ('S01-LGL-006', 'willingness-to-pay'),
  ('S01-LGL-007', 'willingness-to-pay'),
  ('S01-LGL-008', 'willingness-to-pay'),
  ('S01-LGL-009', 'willingness-to-pay'),
  ('S01-LGL-010', 'willingness-to-pay'),
  ('S01-LGL-011', 'technical-quality'),
  ('S01-LGL-012', 'technical-quality'),
  ('S01-LGL-013', 'technical-quality'),
  ('S01-LGL-014', 'technical-quality'),
  ('S01-LGL-015', 'technical-quality'),
  ('S01-LGL-016', 'technical-quality'),
  ('S01-LGL-017', 'technical-quality'),
  ('S01-LGL-018', 'technical-quality'),
  ('S01-LGL-019', 'icp'),
  ('S01-LGL-020', 'icp'),
  ('S10-LGL-001', 'technical-quality'),
  ('S10-LGL-002', 'technical-quality'),
  ('S10-LGL-003', 'technical-quality'),
  ('S10-LGL-004', 'technical-quality'),
  ('S10-LGL-005', 'willingness-to-pay'),
  ('S10-LGL-006', 'willingness-to-pay'),
  ('S10-LGL-007', 'willingness-to-pay'),
  ('S10-LGL-008', 'willingness-to-pay'),
  ('S10-LGL-009', 'technical-quality'),
  ('S10-LGL-010', 'technical-quality'),
  ('S10-LGL-011', 'technical-quality'),
  ('S10-LGL-012', 'technical-quality'),
  ('S10-LGL-013', 'technical-quality'),
  ('S10-LGL-014', 'technical-quality'),
  ('S10-LGL-015', 'technical-quality'),
  ('S10-LGL-016', 'technical-quality'),
  ('S10-LGL-017', 'icp'),
  ('S10-LGL-018', 'icp'),
  ('S10-LGL-019', 'icp'),
  ('S10-LGL-020', 'icp'),
  ('S10-LGL-021', 'technical-quality'),
  ('S10-LGL-022', 'technical-quality'),
  ('S10-LGL-023', 'technical-quality'),
  ('S10-LGL-024', 'technical-quality'),
  ('S10-LGL-025', 'technical-quality')
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
         '["legaltech"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-LGL-001', 'Ideation — Legal Regulatory Position', 'LGL-001', '["RC-LGL-001", "RC-LGL-004"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Decide clearly whether you are practising law or selling a tool.", "Write down exactly where your offering stops short of advice.", "Get that line confirmed by someone qualified."]'::jsonb, '[{"name": "Draw the Advice Line", "brief": "Deciding whether you practise or provide a tool, and where the boundary sits."}]'::jsonb),
  ('INT-LGL-002', 'Ideation — Legal Regulatory Position', 'LGL-001', '["RC-LGL-002", "RC-LGL-003"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Find out who may lawfully give advice in your area.", "Check who may own the business and who may share in fees.", "Structure the business around those answers, not around convenience."]'::jsonb, '[{"name": "Check Who May Practise and Own", "brief": "Confirming permitted advice, ownership and fee sharing before structuring."}]'::jsonb),
  ('INT-LGL-003', 'Ideation — Legal Regulatory Position', 'LGL-001', '["RC-LGL-005"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Name one person responsible for the regulatory position.", "Keep a dated list of what must be maintained or renewed.", "Review it before any change to the offering."]'::jsonb, '[{"name": "One Compliance Owner", "brief": "A single accountable person and a dated list."}]'::jsonb),
  ('INT-LGL-004', 'Ideation — Legal Client Acquisition Rules', 'LGL-002', '["RC-LGL-006", "RC-LGL-007"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Find out what restrictions apply to approaching and soliciting clients.", "List which of your planned tactics are actually permitted.", "Rebuild the plan around what is allowed."]'::jsonb, '[{"name": "Check Before You Market", "brief": "Confirming which client acquisition tactics are permitted."}]'::jsonb),
  ('INT-LGL-005', 'Ideation — Legal Client Acquisition Rules', 'LGL-002', '["RC-LGL-008", "RC-LGL-009"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Assume paid advertising may not be available to you.", "Build referral, reputation and content routes that are permitted.", "Test one permitted channel before committing."]'::jsonb, '[{"name": "Build a Permitted Channel", "brief": "Growth routes that do not depend on tactics that may be disallowed."}]'::jsonb),
  ('INT-LGL-006', 'Ideation — Legal Client Clarity', 'LGL-003', '["RC-LGL-010", "RC-LGL-012"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Pick one client type and one area of law.", "Write down what you will decline.", "Say no to work outside it for now."]'::jsonb, '[{"name": "One Client, One Area", "brief": "Choosing a single client type and practice area instead of taking everything."}]'::jsonb),
  ('INT-LGL-007', 'Ideation — Legal Client Clarity', 'LGL-003', '["RC-LGL-011", "RC-LGL-013", "RC-LGL-014"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Find out where your chosen client looks for legal help.", "Talk to 10 of them about what they needed and what frustrated them.", "Shape the offering around their answers."]'::jsonb, '[{"name": "Study and Talk to Clients", "brief": "Learning how your client actually finds and chooses help."}]'::jsonb),
  ('INT-LGL-008', 'Ideation — Legal Pricing Model', 'LGL-004', '["RC-LGL-015", "RC-LGL-016"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Choose one charging model and write down why.", "Work out what it costs you to complete one typical matter.", "Compare that against what you plan to charge."]'::jsonb, '[{"name": "Choose and Cost the Model", "brief": "One charging model, tested against the real cost of a matter."}]'::jsonb),
  ('INT-LGL-009', 'Ideation — Legal Pricing Model', 'LGL-004', '["RC-LGL-017"]'::jsonb, '[1]'::jsonb, 'Operations', '["Start recording hours against every matter from day one.", "Review after ten matters to see where time actually goes.", "Use that to price the next ones."]'::jsonb, '[{"name": "Record Time From Day One", "brief": "Measuring hours per matter so pricing has evidence behind it."}]'::jsonb),
  ('INT-LGL-010', 'Ideation — Legal Pricing Model', 'LGL-004', '["RC-LGL-018"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Stop setting fees only by what others charge.", "Price from your own cost and the value to the client.", "Check which types of matter would actually be profitable."]'::jsonb, '[{"name": "Price From Cost, Not Comparison", "brief": "Fees built from your own numbers rather than the market rate."}]'::jsonb),
  ('INT-LGL-011', 'Validation to Traction — Legal Founder Capacity', 'LGL-005', '["RC-LGL-019", "RC-LGL-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Calculate the share of revenue that depends on your own hours.", "Work out your ceiling at full capacity.", "Decide whether that ceiling is acceptable."]'::jsonb, '[{"name": "Find Your Ceiling", "brief": "Knowing the maximum the business can earn on founder hours alone."}]'::jsonb),
  ('INT-LGL-012', 'Validation to Traction — Legal Founder Capacity', 'LGL-005', '["RC-LGL-020", "RC-LGL-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["List the tasks in a matter that do not need your seniority.", "Hand those to someone else with a clear checklist.", "Build towards a second person who can run a matter alone."]'::jsonb, '[{"name": "Delegate the Routine Layer", "brief": "Moving the work that does not need you off your desk."}]'::jsonb),
  ('INT-LGL-013', 'Validation to Traction — Legal Founder Capacity', 'LGL-005', '["RC-LGL-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Work out what the business earns in a month you are absent.", "Build one revenue line that does not require your time.", "Test it before you need it."]'::jsonb, '[{"name": "Income Without You", "brief": "At least one line that does not stop when the founder does."}]'::jsonb),
  ('INT-LGL-014', 'Validation to Traction — Legal Billing and Collection', 'LGL-006', '["RC-LGL-024", "RC-LGL-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Agree scope and fee in writing before any work starts.", "Define what is outside scope and what it costs.", "Raise a revised fee the moment scope changes."]'::jsonb, '[{"name": "Scope in Writing First", "brief": "A written scope and fee before work begins, revised when it grows."}]'::jsonb),
  ('INT-LGL-015', 'Validation to Traction — Legal Billing and Collection', 'LGL-006', '["RC-LGL-025", "RC-LGL-026", "RC-LGL-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Take an advance or retainer before starting.", "Bill on a fixed rhythm rather than at the end.", "Set a weekly routine for chasing overdue fees."]'::jsonb, '[{"name": "Advance, Rhythm and Chase", "brief": "Money up front, regular billing and a routine for collection."}]'::jsonb),
  ('INT-LGL-016', 'Validation to Traction — Legal Process and Templates', 'LGL-007', '["RC-LGL-029", "RC-LGL-030"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Build a template for every document you have drafted twice.", "Keep them in one place the whole team can use.", "Update the template each time you improve it."]'::jsonb, '[{"name": "Build the Precedent Bank", "brief": "Reusable templates so similar work is never redone from nothing."}]'::jsonb),
  ('INT-LGL-017', 'Validation to Traction — Legal Process and Templates', 'LGL-007', '["RC-LGL-031", "RC-LGL-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Write a standard sequence for each matter type.", "Add a short closing step that captures what to reuse.", "Follow it on every matter."]'::jsonb, '[{"name": "Standard Matter Process", "brief": "One defined sequence per matter type, with a capture step at the end."}]'::jsonb),
  ('INT-LGL-018', 'Validation to Traction — Legal Confidentiality', 'LGL-008', '["RC-LGL-033", "RC-LGL-034"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Move client documents off personal accounts and devices.", "Put access controls on client files so people see only their matters.", "Apply it to everyone, including yourself."]'::jsonb, '[{"name": "Control Where Files Live", "brief": "Managed storage with access limited to the matter team."}]'::jsonb),
  ('INT-LGL-019', 'Validation to Traction — Legal Confidentiality', 'LGL-008', '["RC-LGL-035", "RC-LGL-036"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Keep a record of who accessed which client file.", "Write what you would do in the first 24 hours of a leak.", "Review both with the team."]'::jsonb, '[{"name": "Access Log and Breach Plan", "brief": "A record of access plus a decided response before anything happens."}]'::jsonb),
  ('INT-LGL-020', 'Validation to Traction — Legal Work Origination', 'LGL-009', '["RC-LGL-037", "RC-LGL-040"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Record where each matter came from.", "Build one permitted route that reaches beyond your existing contacts.", "Measure enquiries from it every month."]'::jsonb, '[{"name": "One Route Beyond Your Network", "brief": "A permitted channel that does not depend on who you already know."}]'::jsonb),
  ('INT-LGL-021', 'Validation to Traction — Legal Work Origination', 'LGL-009', '["RC-LGL-038", "RC-LGL-039"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Track enquiries, not just matters won.", "Keep a simple pipeline of likely work.", "Use it to see quiet periods before they arrive."]'::jsonb, '[{"name": "Make the Pipeline Visible", "brief": "Tracking enquiries so workload can be seen in advance."}]'::jsonb),
  ('INT-LGL-022', 'Growth to Maturity — Legal Senior Talent', 'LGL-010', '["RC-LGL-041", "RC-LGL-043"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Map what a junior must learn to run matters alone.", "Give each one a named mentor and a timeline.", "Grow seniors rather than only hiring them."]'::jsonb, '[{"name": "Grow Your Own Seniors", "brief": "A defined path from junior to matter owner."}]'::jsonb),
  ('INT-LGL-023', 'Growth to Maturity — Legal Senior Talent', 'LGL-010', '["RC-LGL-042", "RC-LGL-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Put agreements in place covering what a leaver may take.", "Introduce a second person into every major client relationship.", "Do it before anyone signals they are leaving."]'::jsonb, '[{"name": "Two Faces Per Client", "brief": "Agreements plus shared relationships so departures do not empty the book."}]'::jsonb),
  ('INT-LGL-024', 'Growth to Maturity — Legal Client Concentration', 'LGL-011', '["RC-LGL-045", "RC-LGL-048"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Calculate the fee share of your top three clients.", "Set a ceiling and build a pipeline of replacement work.", "Review the share every quarter."]'::jsonb, '[{"name": "Cap Client Concentration", "brief": "Measuring dependence and building beyond the largest clients."}]'::jsonb),
  ('INT-LGL-025', 'Growth to Maturity — Legal Client Concentration', 'LGL-011', '["RC-LGL-046", "RC-LGL-047"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Work out your real margin on each large client after their terms.", "Identify which terms you accept only because of dependence.", "Renegotiate or replace the worst."]'::jsonb, '[{"name": "Margin After Their Terms", "brief": "Seeing what a dominant client really leaves you."}]'::jsonb),
  ('INT-LGL-026', 'Growth to Maturity — Legal Professional Risk', 'LGL-012', '["RC-LGL-049", "RC-LGL-052"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Require a second review on any advice above a set threshold.", "Record the reasoning and sources behind significant advice.", "Keep it retrievable for years, not months."]'::jsonb, '[{"name": "Second Review and a Written Basis", "brief": "Another pair of eyes plus a durable record of why advice was given."}]'::jsonb),
  ('INT-LGL-027', 'Growth to Maturity — Legal Professional Risk', 'LGL-012', '["RC-LGL-050", "RC-LGL-051"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Move every critical deadline into one system with reminders.", "Review your indemnity cover against the matters you now take.", "Check both every quarter."]'::jsonb, '[{"name": "Deadlines and Cover", "brief": "One deadline system and insurance matched to current exposure."}]'::jsonb),
  ('INT-LGL-028', 'Growth to Maturity — Legal Conflicts Management', 'LGL-013', '["RC-LGL-053", "RC-LGL-054", "RC-LGL-055"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Build one central register of every client and matter, past and present.", "Check every new matter against it before accepting.", "Never clear a conflict from memory."]'::jsonb, '[{"name": "Central Conflicts Register", "brief": "One searchable record covering past and present clients."}]'::jsonb),
  ('INT-LGL-029', 'Growth to Maturity — Legal Conflicts Management', 'LGL-013', '["RC-LGL-056"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Write down the decision every time a possible conflict arises.", "Record what was disclosed and what was agreed.", "Keep it with the matter file."]'::jsonb, '[{"name": "Record the Conflict Decision", "brief": "A written note of what was found, disclosed and decided."}]'::jsonb),
  ('INT-LGL-030', 'Growth to Maturity — Legal Technology Shift', 'LGL-014', '["RC-LGL-057", "RC-LGL-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Work out what share of billing sits in work that tools now do faster.", "Treat that share as revenue at risk.", "Plan how it will be replaced."]'::jsonb, '[{"name": "Measure Revenue at Risk", "brief": "Knowing how much billing sits in work being automated."}]'::jsonb),
  ('INT-LGL-031', 'Growth to Maturity — Legal Technology Shift', 'LGL-014', '["RC-LGL-058", "RC-LGL-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Use tools to do the routine work faster yourself.", "Shift pricing from hours toward the matter or the outcome.", "Move the mix toward advice that needs judgement."]'::jsonb, '[{"name": "Move Up the Value Line", "brief": "Automating the routine and charging for judgement instead of hours."}]'::jsonb),
  ('INT-LGL-032', 'Growth to Maturity — Legal Knowledge Retention', 'LGL-015', '["RC-LGL-061", "RC-LGL-063"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Move precedents and know how into one shared place.", "Require that anything reusable is filed centrally.", "Make it part of closing a matter."]'::jsonb, '[{"name": "Knowledge Into the Firm", "brief": "Central precedents so capability belongs to the business."}]'::jsonb),
  ('INT-LGL-033', 'Growth to Maturity — Legal Knowledge Retention', 'LGL-015', '["RC-LGL-062", "RC-LGL-064"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Introduce a second person into every client relationship.", "Document what each client needs and how they work.", "Test whether the firm could run without any one person."]'::jsonb, '[{"name": "Institutional, Not Personal", "brief": "Relationships and knowledge that survive a departure."}]'::jsonb),
  ('INT-LGL-034', 'Growth to Maturity — Legal Professional Risk', 'LGL-012', '["RC-LGL-065"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Review closed matters for anything that could still give rise to a claim.", "Check your records would support you if one arose.", "Keep files for as long as the risk lasts, not as long as is convenient."]'::jsonb, '[{"name": "Look Back at Closed Files", "brief": "Finding liability that may still sit in past matters."}]'::jsonb)
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
        ('Marketing, Advertising & AdTech', 'adtech_marketing', 'MKT', r"""-- ============================================================================
-- Ally :: Industry seed -- MARKETING, ADVERTISING & ADTECH (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: adtech_marketing
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (MKT-001, RC-MKT-014, S0-MKT-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : questions name no specific privacy law, consent standard or
--            platform policy.  Data rules and platform algorithms change
--            constantly, so the content asks the founder what applies to
--            THEM and whether it has been checked recently, rather than
--            naming a rule that will go stale.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (reporting clarity, platform dependence,
--            delivery standardisation, contract terms, founder capacity)
--            starts at Stage 0->1; client concentration, talent retention,
--            data compliance, attribution reliability, channel evolution and
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
  ('MKT-001', 'No Clear Client or Service Chosen', 'Agency, platform, freelance service and software are treated as the same business, when each needs a completely different model.', 'Idea & Validation', 'Marketing Business Model Clarity', 'external', 2, 5, 9, '["Agency and software business models mixed together", "Willing to serve any client in any industry", "No decision on service versus product", "No idea what makes this different from a freelancer", "No conversation with a real client yet"]'::jsonb, '["adtech_marketing"]'::jsonb),
  ('MKT-002', 'Results Promised Without a Way to Prove Them', 'Clients are told marketing will grow their business, but nothing has been thought through about how that will actually be measured and shown.', 'Idea & Validation', 'Marketing Proof of Results', 'external', 3, 5, 9, '["No measurement plan agreed before starting", "Success defined vaguely as growth or visibility", "No baseline taken before work begins", "Assuming clients will trust results without proof", "No idea how attribution will work"]'::jsonb, '["adtech_marketing"]'::jsonb),
  ('MKT-003', 'No Idea What It Costs to Deliver One Client', 'Time, tools, ad spend and overhead per client have never been added up, so nobody knows if a client is profitable.', 'Idea & Validation', 'Marketing Cost to Serve', 'external', 4, 5, 9, '["Cost per client unknown", "Hours spent per client not tracked", "Tool and software costs not counted", "Price set by asking what others charge", "No idea which clients are actually profitable"]'::jsonb, '["adtech_marketing"]'::jsonb),
  ('MKT-004', 'Client Money and Ad Spend Not Separated', 'Money given by a client to spend on advertising is mixed with the business own funds and fees.', 'Idea & Validation', 'Marketing Client Funds Handling', 'external', 3, 5, 9, '["Client ad spend held in the same account as fees", "No written agreement on how spend is handled", "No record separating client money from company money", "Assuming this is simple because it is common practice", "No plan if a platform account is suspended"]'::jsonb, '["adtech_marketing"]'::jsonb),
  ('MKT-005', 'Clients Cannot See What They Are Paying For', 'Reports go out but clients struggle to connect them to any actual business result, and confidence erodes.', 'Sales & Revenue', 'Marketing Reporting Clarity', 'external', 4, 6, 9, '["Reports full of activity, not outcomes", "Client cannot say what they got for the fee", "Reporting format different every month", "No regular review call with the client", "Renewal conversations starting from scratch"]'::jsonb, '["adtech_marketing"]'::jsonb),
  ('MKT-006', 'Platform Rules Changing the Work Overnight', 'An algorithm or policy change on a platform breaks a campaign or account with no warning and no one watching for it.', 'Operations & Systems', 'Marketing Platform Dependence', 'external', 3, 6, 9, '["Campaigns breaking after a platform update", "No one tracking platform policy changes", "Whole client results tied to one platform", "No plan if an account is suspended", "Platform change discovered from the client first"]'::jsonb, '["adtech_marketing"]'::jsonb),
  ('MKT-007', 'Every Client Wants a Custom Report and Process', 'Each client is serviced in a different way, so nothing built for one client can be reused for the next.', 'Operations & Systems', 'Marketing Delivery Standardisation', 'external', 3, 5, 9, '["No standard reporting template", "Every client run a different way", "Time spent rebuilding the same work each month", "No checklist for onboarding a new client", "Delivery time growing as clients are added"]'::jsonb, '["adtech_marketing"]'::jsonb),
  ('MKT-008', 'Client Contracts Cancel With Almost No Notice', 'Clients can leave at the end of any month, so revenue can disappear with barely any warning.', 'Financial Management', 'Marketing Contract Terms', 'external', 4, 6, 9, '["No minimum term in contracts", "Clients leaving with days of notice", "Revenue forecast unreliable month to month", "No cancellation or notice clause", "Cash planned as if clients stay indefinitely"]'::jsonb, '["adtech_marketing"]'::jsonb),
  ('MKT-009', 'Everything Depends on the Founder Managing Every Account', 'Every client relationship and campaign decision runs through the founder, so growth is capped by their time.', 'Team & Leadership', 'Marketing Founder Capacity', 'external', 5, 6, 9, '["Founder personally manages every account", "No written process others could follow", "Nobody else can run a client relationship", "New clients turned away for lack of capacity", "No account manager layer"]'::jsonb, '["adtech_marketing"]'::jsonb),
  ('MKT-010', 'Revenue Concentrated in a Few Large Clients', 'A handful of clients account for most billing, so they set the terms and their departure would be severe.', 'Sales & Revenue', 'Marketing Client Concentration', 'external', 4, 7, 10, '["Most revenue from a few clients", "Rates pushed down by the largest client", "Roadmap and priorities set by one account", "No pipeline of replacement clients", "Losing one client would threaten the business"]'::jsonb, '["adtech_marketing"]'::jsonb),
  ('MKT-011', 'Talent Is Scarce and Takes Client Relationships When They Leave', 'Skilled strategists and media buyers are hard to find, and when they leave, clients often follow them.', 'Team & Leadership', 'Marketing Talent Retention', 'external', 5, 7, 10, '["Client relationships tied to individual staff", "Skilled hires hard to find and expensive", "Departures taking client accounts with them", "No agreement covering client ownership on exit", "No structured path for junior staff to grow"]'::jsonb, '["adtech_marketing"]'::jsonb),
  ('MKT-012', 'Privacy and Data Rules Now Constrain Every Campaign', 'Consent, tracking and data handling rules affect how campaigns can be built, targeted and measured, and this now needs constant attention.', 'Operations & Systems', 'Marketing Data Compliance', 'external', 3, 7, 10, '["Consent requirements not built into campaign setup", "Tracking methods not reviewed against current rules", "Client data handled without clear agreements", "No process for a rule change reaching every account", "Compliance treated as a one time task"]'::jsonb, '["adtech_marketing"]'::jsonb),
  ('MKT-013', 'Proving Return on Investment Gets Harder as Attribution Breaks Down', 'As tracking becomes less reliable, connecting spend to results becomes harder just as clients demand more proof.', 'Operations & Systems', 'Marketing Attribution Reliability', 'external', 3, 6, 10, '["Attribution data increasingly incomplete", "Clients asking harder questions about ROI", "No alternative measurement approach in place", "Reporting relying on a single tracking method", "Client trust eroding as numbers become fuzzier"]'::jsonb, '["adtech_marketing"]'::jsonb),
  ('MKT-014', 'New Channels and Formats Outpacing the Team', 'New platforms, formats and tools appear constantly, and the team cannot learn and deploy them fast enough to stay competitive.', 'Strategy & Planning', 'Marketing Channel Evolution', 'external', 2, 6, 9, '["Competitors active on channels the team has not tried", "No process for evaluating new channels", "Team skills concentrated in older formats", "Clients asking about channels the agency cannot offer", "No budget set aside for experimentation"]'::jsonb, '["adtech_marketing"]'::jsonb),
  ('MKT-015', 'Nothing Differentiates This From Any Other Agency', 'Clients can leave for a similar agency at similar cost with little friction, because nothing built here is hard to replace.', 'Strategy & Planning', 'Marketing Defensibility', 'external', 2, 6, 10, '["Services easily matched by competitors", "Clients leaving for marginal price differences", "No proprietary process, data or tool", "Pitches won mainly on price", "No compounding advantage from serving more clients"]'::jsonb, '["adtech_marketing"]'::jsonb)
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
         t.primary_stage_group, '["adtech_marketing"]'::jsonb, z.v
  FROM (VALUES
  ('RC-MKT-001', 'Agency and Software Models Mixed Together', 'Two fundamentally different businesses are being run as one.', 'MKT-001', 'external', 'Strategic', 0.72, 'Stage 0'),
  ('RC-MKT-002', 'Willing to Serve Any Client in Any Industry', 'No focus exists on who this is actually built for.', 'MKT-001', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-MKT-003', 'No Decision on Service Versus Product', 'Whether this scales as people time or as software is unresolved.', 'MKT-001', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-MKT-004', 'No Clear Difference From a Freelancer', 'Nothing distinguishes this from one person taking on work alone.', 'MKT-001', 'external', 'Strategic', 0.67, 'Stage 0'),
  ('RC-MKT-005', 'No Conversation With a Real Client', 'Nobody who would actually pay has been spoken to.', 'MKT-001', 'external', 'Behavioural', 0.66, 'Stage 0'),
  ('RC-MKT-006', 'No Measurement Plan Agreed Before Starting', 'What will be tracked was never settled with the client upfront.', 'MKT-002', 'external', 'Operational', 0.72, 'Stage 0'),
  ('RC-MKT-007', 'Success Defined Vaguely as Growth or Visibility', 'Outcomes are described without any specific, checkable number.', 'MKT-002', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-MKT-008', 'No Baseline Taken Before Work Begins', 'There is nothing to compare results against.', 'MKT-002', 'external', 'Operational', 0.70, 'Stage 0'),
  ('RC-MKT-009', 'Assuming Clients Will Trust Results Without Proof', 'Believing a client will simply take the business word for it.', 'MKT-002', 'external', 'Psychological', 0.68, 'Stage 0'),
  ('RC-MKT-010', 'Only Ad Spend Counted as Cost', 'Only ad spend is counted, and labour is treated as free.', 'MKT-003', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-MKT-011', 'Hours Per Client Not Tracked', 'Time actually spent servicing a client is not recorded.', 'MKT-003', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-MKT-012', 'Tool and Software Costs Not Counted', 'Subscriptions used to deliver the work are left out of the cost.', 'MKT-003', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-MKT-013', 'Price Set by Asking What Others Charge', 'Fees copy competitors without knowing own cost.', 'MKT-003', 'external', 'Behavioural', 0.67, 'Stage 0'),
  ('RC-MKT-014', 'Client Ad Spend Held With Company Funds', 'Money meant for advertising sits in the same account as fees.', 'MKT-004', 'external', 'Operational', 0.73, 'Stage 0'),
  ('RC-MKT-015', 'No Written Agreement on Spend Handling', 'Nothing sets out how client money for ads will be managed.', 'MKT-004', 'external', 'Operational', 0.71, 'Stage 0'),
  ('RC-MKT-016', 'No Record Separating Client and Company Money', 'Bookkeeping does not distinguish whose money is whose.', 'MKT-004', 'external', 'Operational', 0.70, 'Stage 0'),
  ('RC-MKT-017', 'Reports Full of Activity Not Outcomes', 'Reports list tasks done rather than results achieved.', 'MKT-005', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-MKT-018', 'Client Cannot Say What They Got for the Fee', 'A client asked directly could not summarise the value received.', 'MKT-005', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-MKT-019', 'Reporting Format Different Every Month', 'Nothing consistent lets a client compare over time.', 'MKT-005', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-MKT-020', 'No Regular Review Call', 'Results are shared without a conversation to explain them.', 'MKT-005', 'external', 'Behavioural', 0.69, 'Stage 0→1'),
  ('RC-MKT-021', 'No Owner Tracking Platform Policy Changes', 'Nobody watches for changes on the platforms being used.', 'MKT-006', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-MKT-022', 'Whole Client Result Tied to One Platform', 'A single channel carries all the risk for a client.', 'MKT-006', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-MKT-023', 'No Plan If an Account Is Suspended', 'Nothing has been prepared for a platform shutting an account.', 'MKT-006', 'external', 'Strategic', 0.71, 'Stage 0→1'),
  ('RC-MKT-024', 'Platform Change Discovered From the Client', 'The business learns about a break only when the client complains.', 'MKT-006', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-MKT-025', 'No Standard Reporting Template', 'Every report is built individually from scratch.', 'MKT-007', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-MKT-026', 'Every Client Run a Different Way', 'There is no consistent process across accounts.', 'MKT-007', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-MKT-027', 'No Onboarding Checklist', 'New clients are set up inconsistently.', 'MKT-007', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-MKT-028', 'Delivery Time Growing as Clients Are Added', 'Each new client takes longer to service than the last.', 'MKT-007', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-MKT-029', 'No Minimum Term in Contracts', 'Clients can leave with essentially no commitment.', 'MKT-008', 'external', 'Strategic', 0.73, 'Stage 0→1'),
  ('RC-MKT-030', 'No Cancellation or Notice Clause', 'Nothing requires advance warning before a client leaves.', 'MKT-008', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-MKT-031', 'Cash Planned as if Clients Stay Indefinitely', 'Forecasts assume no churn at all.', 'MKT-008', 'external', 'Behavioural', 0.70, 'Stage 0→1'),
  ('RC-MKT-032', 'Founder Personally Manages Every Account', 'No account runs without the founder directly involved.', 'MKT-009', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-MKT-033', 'No Written Process Others Could Follow', 'How an account is run exists only in the founder head.', 'MKT-009', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-MKT-034', 'New Clients Turned Away for Lack of Capacity', 'Growth is limited by time, not by demand.', 'MKT-009', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-MKT-035', 'Most Revenue From a Few Clients', 'A handful of accounts carry most of the billing.', 'MKT-010', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-MKT-036', 'Rates Pushed Down by the Largest Client', 'The dominant client dictates what can be charged.', 'MKT-010', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-MKT-037', 'Roadmap Set by One Account', 'Priorities are driven by a single client rather than the business.', 'MKT-010', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-MKT-038', 'No Pipeline of Replacement Clients', 'Nothing is being built that could replace a lost account.', 'MKT-010', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-MKT-039', 'Client Relationships Tied to Individual Staff', 'Clients are loyal to a person, not the agency.', 'MKT-011', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-MKT-040', 'Departures Taking Client Accounts With Them', 'Leavers carry client relationships out of the business.', 'MKT-011', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-MKT-041', 'No Agreement Covering Client Ownership on Exit', 'Nothing sets out what happens to accounts when staff leave.', 'MKT-011', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-MKT-042', 'No Structured Growth Path for Junior Staff', 'Nothing develops the next layer internally.', 'MKT-011', 'external', 'Operational', 0.68, 'Stage 1→10+'),
  ('RC-MKT-043', 'Consent Requirements Not Built Into Campaign Setup', 'Data rules are considered after a campaign is built, not before.', 'MKT-012', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-MKT-044', 'Tracking Methods Not Reviewed Against Current Rules', 'What is being tracked has not been checked against present requirements.', 'MKT-012', 'external', 'Knowledge', 0.72, 'Stage 1→10+'),
  ('RC-MKT-045', 'Client Data Handled Without Clear Agreements', 'Data responsibilities between agency and client are undefined.', 'MKT-012', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-MKT-046', 'No Process for a Rule Change Reaching Every Account', 'A compliance update does not automatically reach every client.', 'MKT-012', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-MKT-047', 'Attribution Data Increasingly Incomplete', 'Tracking captures a shrinking share of what actually happens.', 'MKT-013', 'external', 'Knowledge', 0.72, 'Stage 1→10+'),
  ('RC-MKT-048', 'No Alternative Measurement Approach', 'Nothing has replaced the tracking method that is breaking down.', 'MKT-013', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-MKT-049', 'Reporting Relying on a Single Tracking Method', 'All measurement runs through one fragile source.', 'MKT-013', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-MKT-050', 'No Process for Evaluating New Channels', 'Nothing systematically decides which new channels to test.', 'MKT-014', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-MKT-051', 'Team Skills Concentrated in Older Formats', 'Capability has not kept pace with where channels are moving.', 'MKT-014', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-MKT-052', 'No Budget for Experimentation', 'Nothing is set aside to test new channels or formats.', 'MKT-014', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-MKT-053', 'Services Easily Matched by Competitors', 'What is offered can be replicated without much effort.', 'MKT-015', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-MKT-054', 'No Proprietary Process, Data or Tool', 'Nothing owned makes the agency harder to replace.', 'MKT-015', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-MKT-055', 'Pitches Won Mainly on Price', 'Competitive position rests on being cheaper, not different.', 'MKT-015', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-MKT-056', 'No Idea How Attribution Will Work', 'How results will be traced back to the work has not been thought through.', 'MKT-002', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-MKT-057', 'Assuming This Is Simple Because It Is Common Practice', 'Believing common practice makes proper handling unnecessary.', 'MKT-004', 'external', 'Psychological', 0.67, 'Stage 0'),
  ('RC-MKT-058', 'Renewal Conversations Starting From Scratch', 'Nothing accumulated through the engagement makes renewal easier.', 'MKT-005', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-MKT-059', 'No Backup Channel When Primary Platform Fails', 'There is no second channel ready if the main one breaks.', 'MKT-006', 'external', 'Strategic', 0.69, 'Stage 0→1'),
  ('RC-MKT-060', 'Time Spent Rebuilding the Same Work Each Month', 'Recurring work is redone from nothing every cycle.', 'MKT-007', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-MKT-061', 'No Account Manager Layer', 'Nothing sits between the founder and day to day client work.', 'MKT-009', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-MKT-062', 'Terms Dictated by the Dominant Client', 'Payment and contract terms are imposed rather than negotiated.', 'MKT-010', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-MKT-063', 'Skilled Hires Hard to Find and Expensive', 'The talent needed to grow is scarce and costly.', 'MKT-011', 'external', 'Knowledge', 0.68, 'Stage 1→10+'),
  ('RC-MKT-064', 'Compliance Treated as a One Time Task', 'Data and consent rules are addressed once and not revisited.', 'MKT-012', 'external', 'Behavioural', 0.69, 'Stage 1→10+'),
  ('RC-MKT-065', 'Client Trust Eroding as Numbers Become Fuzzier', 'Confidence falls as measurement gets less precise.', 'MKT-013', 'external', 'Strategic', 0.68, 'Stage 1→10+'),
  ('RC-MKT-066', 'Clients Asking About Channels the Agency Cannot Offer', 'Demand exists for channels the team has not developed.', 'MKT-014', 'external', 'Strategic', 0.68, 'Stage 1→10+')
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
         '["adtech_marketing"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-MKT-001', 'Are you running an agency, a product, or both mixed together?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-001', 'RC-MKT-001', 1, 'Stage 0'),
  ('S0-MKT-002', 'Will you take any client in any industry, or have you chosen a focus?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-001', 'RC-MKT-002', 1, 'Stage 0'),
  ('S0-MKT-003', 'Is this meant to scale as people time or as software?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-001', 'RC-MKT-003', 2, 'Stage 0'),
  ('S0-MKT-004', 'What makes this different from one person freelancing?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-001', 'RC-MKT-004', 2, 'Stage 0'),
  ('S0-MKT-005', 'Have you spoken to a real client who would actually pay?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-001', 'RC-MKT-005', 2, 'Stage 0'),
  ('S0-MKT-006', 'What exact number will you use to prove this worked?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-002', 'RC-MKT-007', 1, 'Stage 0'),
  ('S0-MKT-007', 'Have you agreed what will be measured before starting work?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-002', 'RC-MKT-006', 1, 'Stage 0'),
  ('S0-MKT-008', 'Do you have a baseline from before you started?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-002', 'RC-MKT-008', 2, 'Stage 0'),
  ('S0-MKT-009', 'Do you think a client will trust your results without proof?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-002', 'RC-MKT-009', 2, 'Stage 0'),
  ('S0-MKT-010', 'What does it cost you in time and tools to serve one client?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-003', 'RC-MKT-010', 1, 'Stage 0'),
  ('S0-MKT-011', 'Do you track how many hours you spend per client?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-003', 'RC-MKT-011', 2, 'Stage 0'),
  ('S0-MKT-012', 'Have you counted the software and tools you pay for?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-003', 'RC-MKT-012', 2, 'Stage 0'),
  ('S0-MKT-013', 'Did you set your fee from your own cost or from competitors?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-003', 'RC-MKT-013', 2, 'Stage 0'),
  ('S0-MKT-014', 'Is client ad spend kept separate from your own money?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-004', 'RC-MKT-014', 1, 'Stage 0'),
  ('S0-MKT-015', 'Is there anything written down about how you handle client ad spend?', 'open_text', 'Idea & Validation', 'CORE', 'MKT-004', 'RC-MKT-015', 2, 'Stage 0'),
  ('S01-MKT-001', 'If you asked a client what they got for the fee, what would they say?', 'open_text', 'Sales & Revenue', 'CORE', 'MKT-005', 'RC-MKT-018', 2, 'Stage 0→1'),
  ('S01-MKT-002', 'Do your reports show activity, or business outcomes?', 'open_text', 'Sales & Revenue', 'CORE', 'MKT-005', 'RC-MKT-017', 2, 'Stage 0→1'),
  ('S01-MKT-003', 'Does every client get the same reporting format?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-005', 'RC-MKT-019', 2, 'Stage 0→1'),
  ('S01-MKT-004', 'Do you have a regular call to walk clients through results?', 'open_text', 'Sales & Revenue', 'CORE', 'MKT-005', 'RC-MKT-020', 2, 'Stage 0→1'),
  ('S01-MKT-005', 'Who is watching for policy changes on the platforms you use?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-006', 'RC-MKT-021', 2, 'Stage 0→1'),
  ('S01-MKT-006', 'Does any single client depend entirely on one platform?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-006', 'RC-MKT-022', 2, 'Stage 0→1'),
  ('S01-MKT-007', 'What would you do if a client account was suspended tomorrow?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-006', 'RC-MKT-023', 3, 'Stage 0→1'),
  ('S01-MKT-008', 'Have you ever found out about a platform change from the client?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-006', 'RC-MKT-024', 2, 'Stage 0→1'),
  ('S01-MKT-009', 'Do you have a standard reporting template?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-007', 'RC-MKT-025', 2, 'Stage 0→1'),
  ('S01-MKT-010', 'Is every client run through the same process?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-007', 'RC-MKT-026', 2, 'Stage 0→1'),
  ('S01-MKT-011', 'Is there a checklist for onboarding a new client?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-007', 'RC-MKT-027', 2, 'Stage 0→1'),
  ('S01-MKT-012', 'Is each new client taking longer to deliver than the last?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-007', 'RC-MKT-028', 2, 'Stage 0→1'),
  ('S01-MKT-013', 'Do your contracts require any minimum term?', 'open_text', 'Financial Management', 'CORE', 'MKT-008', 'RC-MKT-029', 2, 'Stage 0→1'),
  ('S01-MKT-014', 'How much notice must a client give before leaving?', 'open_text', 'Financial Management', 'CORE', 'MKT-008', 'RC-MKT-030', 2, 'Stage 0→1'),
  ('S01-MKT-015', 'Is your cash plan built assuming no client ever leaves?', 'open_text', 'Financial Management', 'CORE', 'MKT-008', 'RC-MKT-031', 3, 'Stage 0→1'),
  ('S01-MKT-016', 'How many accounts do you personally manage right now?', 'open_text', 'Team & Leadership', 'CORE', 'MKT-009', 'RC-MKT-032', 2, 'Stage 0→1'),
  ('S01-MKT-017', 'Could someone else run an account the way you do?', 'open_text', 'Team & Leadership', 'CORE', 'MKT-009', 'RC-MKT-033', 2, 'Stage 0→1'),
  ('S01-MKT-018', 'Have you turned away a client because you had no time?', 'open_text', 'Sales & Revenue', 'CORE', 'MKT-009', 'RC-MKT-034', 2, 'Stage 0→1'),
  ('S01-MKT-019', 'How far in advance do you know a renewal conversation is coming up?', 'open_text', 'Sales & Revenue', 'CORE', 'MKT-005', 'RC-MKT-020', 2, 'Stage 0→1'),
  ('S01-MKT-020', 'If your biggest client left this month, when would you find out you had a problem?', 'open_text', 'Financial Management', 'CORE', 'MKT-008', 'RC-MKT-031', 3, 'Stage 0→1'),
  ('S10-MKT-001', 'What share of your revenue comes from your top two or three clients?', 'open_text', 'Sales & Revenue', 'CORE', 'MKT-010', 'RC-MKT-035', 2, 'Stage 1→10+'),
  ('S10-MKT-002', 'Who sets your rates, you or your biggest client?', 'open_text', 'Sales & Revenue', 'CORE', 'MKT-010', 'RC-MKT-036', 2, 'Stage 1→10+'),
  ('S10-MKT-003', 'Is your roadmap being set by one large client?', 'open_text', 'Strategy & Planning', 'CORE', 'MKT-010', 'RC-MKT-037', 3, 'Stage 1→10+'),
  ('S10-MKT-004', 'If your largest client left, how long could you continue?', 'open_text', 'Strategy & Planning', 'CORE', 'MKT-010', 'RC-MKT-038', 3, 'Stage 1→10+'),
  ('S10-MKT-005', 'When someone senior left, did clients go with them?', 'open_text', 'Team & Leadership', 'CORE', 'MKT-011', 'RC-MKT-040', 3, 'Stage 1→10+'),
  ('S10-MKT-006', 'Are your client relationships tied to a person or to the agency?', 'open_text', 'Sales & Revenue', 'CORE', 'MKT-011', 'RC-MKT-039', 2, 'Stage 1→10+'),
  ('S10-MKT-007', 'Is there an agreement covering what happens to accounts when staff leave?', 'open_text', 'Team & Leadership', 'CORE', 'MKT-011', 'RC-MKT-041', 3, 'Stage 1→10+'),
  ('S10-MKT-008', 'How does a junior team member grow into running accounts?', 'open_text', 'Team & Leadership', 'CORE', 'MKT-011', 'RC-MKT-042', 2, 'Stage 1→10+'),
  ('S10-MKT-009', 'Is consent handled before a campaign is built or after?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-012', 'RC-MKT-043', 3, 'Stage 1→10+'),
  ('S10-MKT-010', 'When did you last review your tracking methods against current rules?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-012', 'RC-MKT-044', 3, 'Stage 1→10+'),
  ('S10-MKT-011', 'Are data responsibilities between you and the client written down?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-012', 'RC-MKT-045', 3, 'Stage 1→10+'),
  ('S10-MKT-012', 'When a rule changes, how does it reach every client account?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-012', 'RC-MKT-046', 3, 'Stage 1→10+'),
  ('S10-MKT-013', 'How much of your tracking data is now missing or unreliable?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-013', 'RC-MKT-047', 3, 'Stage 1→10+'),
  ('S10-MKT-014', 'Do you have a second way to measure results if tracking breaks?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-013', 'RC-MKT-048', 3, 'Stage 1→10+'),
  ('S10-MKT-015', 'Does all your reporting depend on one tracking method?', 'open_text', 'Operations & Systems', 'CORE', 'MKT-013', 'RC-MKT-049', 2, 'Stage 1→10+'),
  ('S10-MKT-016', 'How do you decide which new channels to test?', 'open_text', 'Strategy & Planning', 'CORE', 'MKT-014', 'RC-MKT-050', 2, 'Stage 1→10+'),
  ('S10-MKT-017', 'Are your team skills keeping pace with where channels are moving?', 'open_text', 'Team & Leadership', 'CORE', 'MKT-014', 'RC-MKT-051', 2, 'Stage 1→10+'),
  ('S10-MKT-018', 'Is there a budget set aside to test new channels?', 'open_text', 'Financial Management', 'CORE', 'MKT-014', 'RC-MKT-052', 2, 'Stage 1→10+'),
  ('S10-MKT-019', 'Have clients asked for a channel you cannot offer?', 'open_text', 'Sales & Revenue', 'CORE', 'MKT-014', 'RC-MKT-066', 2, 'Stage 1→10+'),
  ('S10-MKT-020', 'What could a competitor copy from you within a month?', 'open_text', 'Strategy & Planning', 'CORE', 'MKT-015', 'RC-MKT-053', 3, 'Stage 1→10+'),
  ('S10-MKT-021', 'Do you own any process, data or tool competitors do not have?', 'open_text', 'Strategy & Planning', 'CORE', 'MKT-015', 'RC-MKT-054', 3, 'Stage 1→10+'),
  ('S10-MKT-022', 'Do you win pitches mainly on price or on something else?', 'open_text', 'Sales & Revenue', 'CORE', 'MKT-015', 'RC-MKT-055', 2, 'Stage 1→10+'),
  ('S10-MKT-023', 'Would a client notice if you were replaced by a similar agency?', 'open_text', 'Strategy & Planning', 'CORE', 'MKT-015', 'RC-MKT-053', 3, 'Stage 1→10+'),
  ('S10-MKT-024', 'Are payment terms set by you or by your largest client?', 'open_text', 'Financial Management', 'CORE', 'MKT-010', 'RC-MKT-062', 2, 'Stage 1→10+'),
  ('S10-MKT-025', 'Is hiring senior talent a bottleneck on your growth?', 'open_text', 'Team & Leadership', 'CORE', 'MKT-011', 'RC-MKT-063', 2, 'Stage 1→10+')
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
  ('S0-MKT-001', 'icp'),
  ('S0-MKT-002', 'icp'),
  ('S0-MKT-003', 'icp'),
  ('S0-MKT-004', 'icp'),
  ('S0-MKT-005', 'icp'),
  ('S0-MKT-006', 'technical-quality'),
  ('S0-MKT-007', 'technical-quality'),
  ('S0-MKT-008', 'technical-quality'),
  ('S0-MKT-009', 'technical-quality'),
  ('S0-MKT-010', 'willingness-to-pay'),
  ('S0-MKT-011', 'willingness-to-pay'),
  ('S0-MKT-012', 'willingness-to-pay'),
  ('S0-MKT-013', 'willingness-to-pay'),
  ('S0-MKT-014', 'technical-quality'),
  ('S0-MKT-015', 'technical-quality'),
  ('S01-MKT-001', 'channel-strategy'),
  ('S01-MKT-002', 'channel-strategy'),
  ('S01-MKT-003', 'channel-strategy'),
  ('S01-MKT-004', 'channel-strategy'),
  ('S01-MKT-005', 'technical-quality'),
  ('S01-MKT-006', 'technical-quality'),
  ('S01-MKT-007', 'technical-quality'),
  ('S01-MKT-008', 'technical-quality'),
  ('S01-MKT-009', 'technical-quality'),
  ('S01-MKT-010', 'technical-quality'),
  ('S01-MKT-011', 'technical-quality'),
  ('S01-MKT-012', 'technical-quality'),
  ('S01-MKT-013', 'willingness-to-pay'),
  ('S01-MKT-014', 'willingness-to-pay'),
  ('S01-MKT-015', 'willingness-to-pay'),
  ('S01-MKT-016', 'technical-quality'),
  ('S01-MKT-017', 'technical-quality'),
  ('S01-MKT-018', 'technical-quality'),
  ('S01-MKT-019', 'channel-strategy'),
  ('S01-MKT-020', 'willingness-to-pay'),
  ('S10-MKT-001', 'willingness-to-pay'),
  ('S10-MKT-002', 'willingness-to-pay'),
  ('S10-MKT-003', 'willingness-to-pay'),
  ('S10-MKT-004', 'willingness-to-pay'),
  ('S10-MKT-005', 'technical-quality'),
  ('S10-MKT-006', 'technical-quality'),
  ('S10-MKT-007', 'technical-quality'),
  ('S10-MKT-008', 'technical-quality'),
  ('S10-MKT-009', 'technical-quality'),
  ('S10-MKT-010', 'technical-quality'),
  ('S10-MKT-011', 'technical-quality'),
  ('S10-MKT-012', 'technical-quality'),
  ('S10-MKT-013', 'technical-quality'),
  ('S10-MKT-014', 'technical-quality'),
  ('S10-MKT-015', 'technical-quality'),
  ('S10-MKT-016', 'icp'),
  ('S10-MKT-017', 'icp'),
  ('S10-MKT-018', 'icp'),
  ('S10-MKT-019', 'icp'),
  ('S10-MKT-020', 'channel-strategy'),
  ('S10-MKT-021', 'channel-strategy'),
  ('S10-MKT-022', 'channel-strategy'),
  ('S10-MKT-023', 'channel-strategy'),
  ('S10-MKT-024', 'willingness-to-pay'),
  ('S10-MKT-025', 'technical-quality')
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
         '["adtech_marketing"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-MKT-001', 'Ideation — Marketing Business Model Clarity', 'MKT-001', '["RC-MKT-001", "RC-MKT-003"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Decide clearly whether you are an agency or a software business.", "Write down how each would actually make money differently.", "Commit to one for the next twelve months."]'::jsonb, '[{"name": "Pick One Business Model", "brief": "Agency and software scale completely differently; choose one."}]'::jsonb),
  ('INT-MKT-002', 'Ideation — Marketing Business Model Clarity', 'MKT-001', '["RC-MKT-002", "RC-MKT-004"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Choose one industry or client type to serve first.", "Write down what makes your offer different from a freelancer.", "Say no to work outside that focus for now."]'::jsonb, '[{"name": "Pick a Focus and a Difference", "brief": "One client type and one clear reason to hire you over a freelancer."}]'::jsonb),
  ('INT-MKT-003', 'Ideation — Marketing Business Model Clarity', 'MKT-001', '["RC-MKT-005"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Talk to 10 real potential clients before building further.", "Ask what they currently do instead of hiring you.", "Get one to commit before scaling the offer."]'::jsonb, '[{"name": "Talk to Real Clients First", "brief": "Validating demand before building the business around assumptions."}]'::jsonb),
  ('INT-MKT-004', 'Ideation — Marketing Proof of Results', 'MKT-002', '["RC-MKT-006", "RC-MKT-007"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Agree the specific number that will define success before starting.", "Write it into the contract or proposal.", "Avoid vague terms like growth or visibility."]'::jsonb, '[{"name": "Define Success as a Number", "brief": "A specific, checkable metric agreed before work begins."}]'::jsonb),
  ('INT-MKT-005', 'Ideation — Marketing Proof of Results', 'MKT-002', '["RC-MKT-008", "RC-MKT-009"]'::jsonb, '[1]'::jsonb, 'Operations', '["Take a measured baseline before any work starts.", "Report against that baseline throughout the engagement.", "Never assume trust replaces proof."]'::jsonb, '[{"name": "Baseline Before You Start", "brief": "A measured starting point so results can actually be shown."}]'::jsonb),
  ('INT-MKT-006', 'Ideation — Marketing Cost to Serve', 'MKT-003', '["RC-MKT-010", "RC-MKT-011"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Track hours spent per client for a month.", "Add tool costs on top of ad spend.", "Build a real cost per client from that."]'::jsonb, '[{"name": "Cost to Serve One Client", "brief": "Time and tools counted, not just ad spend."}]'::jsonb),
  ('INT-MKT-007', 'Ideation — Marketing Cost to Serve', 'MKT-003', '["RC-MKT-012", "RC-MKT-013"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["List every tool and subscription used to deliver the work.", "Load that cost per client.", "Price from your own numbers, not competitor rates."]'::jsonb, '[{"name": "Price From Your Own Cost", "brief": "Fees built from real numbers rather than the market rate."}]'::jsonb),
  ('INT-MKT-008', 'Ideation — Marketing Client Funds Handling', 'MKT-004', '["RC-MKT-014", "RC-MKT-016"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Open a separate account or ledger for client ad spend.", "Never mix it with company fees or funds.", "Reconcile it against platform spend regularly."]'::jsonb, '[{"name": "Separate Client Money", "brief": "Ad spend kept apart from company funds at all times."}]'::jsonb),
  ('INT-MKT-009', 'Ideation — Marketing Client Funds Handling', 'MKT-004', '["RC-MKT-015"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Write a simple agreement covering how ad spend is handled.", "Cover what happens if a platform account is suspended.", "Get it signed before spending a client rupee."]'::jsonb, '[{"name": "Write the Spend Agreement", "brief": "Clear written terms for handling client advertising money."}]'::jsonb),
  ('INT-MKT-010', 'Validation to Traction — Marketing Reporting Clarity', 'MKT-005', '["RC-MKT-017", "RC-MKT-018"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Rebuild reports around outcomes, not activity.", "Ask a client cold what they think they got for the fee.", "Fix the reporting until the answer matches reality."]'::jsonb, '[{"name": "Report Outcomes, Not Activity", "brief": "Reporting that shows business results, not a list of tasks done."}]'::jsonb),
  ('INT-MKT-011', 'Validation to Traction — Marketing Reporting Clarity', 'MKT-005', '["RC-MKT-019", "RC-MKT-020"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Standardise the reporting format across every client.", "Add a regular call to walk through results.", "Use it to surface renewal conversations early."]'::jsonb, '[{"name": "Standard Format and Regular Review", "brief": "Consistent reporting plus a conversation, not just a document."}]'::jsonb),
  ('INT-MKT-012', 'Validation to Traction — Marketing Platform Dependence', 'MKT-006', '["RC-MKT-021", "RC-MKT-024"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Give one person the job of tracking platform policy changes.", "Review changes before clients notice a break.", "Warn clients ahead of a known change where possible."]'::jsonb, '[{"name": "Watch the Platforms", "brief": "One owner tracking changes before they surprise a client."}]'::jsonb),
  ('INT-MKT-013', 'Validation to Traction — Marketing Platform Dependence', 'MKT-006', '["RC-MKT-022", "RC-MKT-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Avoid putting all of a client result on one platform.", "Write a response plan for an account suspension.", "Test the plan before you need it."]'::jsonb, '[{"name": "Reduce Single Platform Risk", "brief": "Diversifying channels and preparing for a suspension in advance."}]'::jsonb),
  ('INT-MKT-014', 'Validation to Traction — Marketing Delivery Standardisation', 'MKT-007', '["RC-MKT-025", "RC-MKT-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Build one standard reporting template.", "Build one onboarding checklist for every new client.", "Use both without exception."]'::jsonb, '[{"name": "Standard Template and Onboarding", "brief": "One reusable format and one onboarding checklist for every client."}]'::jsonb),
  ('INT-MKT-015', 'Validation to Traction — Marketing Delivery Standardisation', 'MKT-007', '["RC-MKT-026", "RC-MKT-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Write down the standard process for running an account.", "Apply it consistently across clients.", "Measure whether delivery time per client stops growing."]'::jsonb, '[{"name": "One Process, Every Client", "brief": "A consistent delivery process so growth does not slow delivery."}]'::jsonb),
  ('INT-MKT-016', 'Validation to Traction — Marketing Contract Terms', 'MKT-008', '["RC-MKT-029", "RC-MKT-030"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Add a minimum term to every new contract.", "Require a notice period before cancellation.", "Apply it to renewals as well as new clients."]'::jsonb, '[{"name": "Add Term and Notice", "brief": "Contract terms that give the business real warning before revenue leaves."}]'::jsonb),
  ('INT-MKT-017', 'Validation to Traction — Marketing Contract Terms', 'MKT-008', '["RC-MKT-031"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Build cash plans assuming a realistic churn rate.", "Track actual churn against that assumption.", "Adjust the plan as real numbers come in."]'::jsonb, '[{"name": "Plan Cash With Churn Built In", "brief": "Forecasting on realistic retention, not on nobody ever leaving."}]'::jsonb),
  ('INT-MKT-018', 'Validation to Traction — Marketing Founder Capacity', 'MKT-009', '["RC-MKT-032", "RC-MKT-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Write down how you actually run an account, step by step.", "Train one other person against it.", "Hand them a smaller account to run alone."]'::jsonb, '[{"name": "Document and Delegate an Account", "brief": "Turning founder-only account management into something transferable."}]'::jsonb),
  ('INT-MKT-019', 'Validation to Traction — Marketing Founder Capacity', 'MKT-009', '["RC-MKT-034"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Track how many clients you have turned away for lack of time.", "Use that number to justify hiring or delegating.", "Fix capacity before it costs more revenue."]'::jsonb, '[{"name": "Measure Turned Away Work", "brief": "Making the cost of limited capacity visible."}]'::jsonb),
  ('INT-MKT-020', 'Growth to Maturity — Marketing Client Concentration', 'MKT-010', '["RC-MKT-035", "RC-MKT-038"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Calculate the revenue share of your top three clients.", "Set a ceiling and build a pipeline of smaller clients.", "Review the share every quarter."]'::jsonb, '[{"name": "Cap Client Concentration", "brief": "Measuring dependence and building beyond the dominant few."}]'::jsonb),
  ('INT-MKT-021', 'Growth to Maturity — Marketing Client Concentration', 'MKT-010', '["RC-MKT-036", "RC-MKT-037", "RC-MKT-062"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Work out your real margin on the dominant client after their terms.", "Identify which terms and priorities you accept only because of dependence.", "Renegotiate or replace the worst."]'::jsonb, '[{"name": "Margin and Roadmap After Their Terms", "brief": "Seeing what a dominant client really leaves you, in money and priorities."}]'::jsonb),
  ('INT-MKT-022', 'Growth to Maturity — Marketing Talent Retention', 'MKT-011', '["RC-MKT-039", "RC-MKT-040"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Introduce a second person into every major client relationship.", "Put agreements in place covering client ownership on exit.", "Do it before anyone signals they are leaving."]'::jsonb, '[{"name": "Two Faces Per Client", "brief": "Shared relationships and exit agreements so departures do not empty the book."}]'::jsonb),
  ('INT-MKT-023', 'Growth to Maturity — Marketing Talent Retention', 'MKT-011', '["RC-MKT-041", "RC-MKT-042", "RC-MKT-063"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Build a growth path from junior to account owner.", "Grow seniors internally rather than only hiring them.", "Give each one a mentor and a timeline."]'::jsonb, '[{"name": "Grow Your Own Seniors", "brief": "A defined path so scarce senior talent is developed, not only bought."}]'::jsonb),
  ('INT-MKT-024', 'Growth to Maturity — Marketing Data Compliance', 'MKT-012', '["RC-MKT-043", "RC-MKT-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Build consent and tracking checks into campaign setup, not after.", "Review tracking methods against current rules regularly.", "Fix any campaign that does not pass."]'::jsonb, '[{"name": "Build Compliance Into Setup", "brief": "Consent and tracking checked before launch, not discovered after."}]'::jsonb),
  ('INT-MKT-025', 'Growth to Maturity — Marketing Data Compliance', 'MKT-012', '["RC-MKT-045", "RC-MKT-046", "RC-MKT-064"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Put data responsibilities between agency and client in writing.", "Build a way to push a rule change to every account at once.", "Review the whole compliance approach on a fixed schedule, not once."]'::jsonb, '[{"name": "Written Responsibilities and a Push Mechanism", "brief": "Clear agreements plus a way to update every client together."}]'::jsonb),
  ('INT-MKT-026', 'Growth to Maturity — Marketing Attribution Reliability', 'MKT-013', '["RC-MKT-047", "RC-MKT-049"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Identify how much of your tracking is now unreliable.", "Add a second measurement method that does not depend on the same source.", "Blend both into reporting."]'::jsonb, '[{"name": "Add a Second Measurement Method", "brief": "Reducing reliance on one fragile tracking source."}]'::jsonb),
  ('INT-MKT-027', 'Growth to Maturity — Marketing Attribution Reliability', 'MKT-013', '["RC-MKT-048", "RC-MKT-065"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Explain the measurement shift to clients before they ask.", "Show what you are doing about it.", "Keep the conversation ahead of eroding trust."]'::jsonb, '[{"name": "Get Ahead of the Trust Problem", "brief": "Proactive explanation instead of clients discovering fuzzier numbers themselves."}]'::jsonb),
  ('INT-MKT-028', 'Growth to Maturity — Marketing Channel Evolution', 'MKT-014', '["RC-MKT-050", "RC-MKT-052"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Build a simple process for evaluating new channels.", "Set aside a fixed budget for experimentation.", "Review results and decide what to adopt."]'::jsonb, '[{"name": "A Process and Budget for New Channels", "brief": "Systematic evaluation instead of reacting to whatever is trending."}]'::jsonb),
  ('INT-MKT-029', 'Growth to Maturity — Marketing Channel Evolution', 'MKT-014', '["RC-MKT-051", "RC-MKT-066"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Identify the skill gaps holding the team back on newer channels.", "Train or hire against the gaps clients are actually asking about.", "Track whether lost enquiries for missing channels fall."]'::jsonb, '[{"name": "Close the Skill Gap Clients Are Asking About", "brief": "Training aimed at the channels demand is already showing up for."}]'::jsonb),
  ('INT-MKT-030', 'Growth to Maturity — Marketing Defensibility', 'MKT-015', '["RC-MKT-053", "RC-MKT-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Build one process, dataset or tool that is genuinely yours.", "Make it central to how you deliver, not a side feature.", "Use it as the reason to hire you over a competitor."]'::jsonb, '[{"name": "Build Something Proprietary", "brief": "An owned asset that a competitor cannot simply copy."}]'::jsonb),
  ('INT-MKT-031', 'Growth to Maturity — Marketing Defensibility', 'MKT-015', '["RC-MKT-055"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Track how often pitches are won or lost on price alone.", "Build a case for value beyond cost.", "Stop competing only on being cheaper."]'::jsonb, '[{"name": "Compete on Value, Not Just Price", "brief": "Shifting the pitch away from price as the main differentiator."}]'::jsonb),
  ('INT-MKT-032', 'Ideation — Marketing Proof of Results', 'MKT-002', '["RC-MKT-056", "RC-MKT-057"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Decide before the campaign starts how results will be attributed.", "Do not assume client fund handling is fine just because it is common practice.", "Write both decisions down before work begins."]'::jsonb, '[{"name": "Decide Attribution and Fund Handling Upfront", "brief": "Settling how results are traced and how money is handled before starting, not after."}]'::jsonb),
  ('INT-MKT-033', 'Validation to Traction — Marketing Reporting Clarity', 'MKT-005', '["RC-MKT-058"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Build a running record of value delivered through the engagement.", "Use it to open the renewal conversation early.", "Never start a renewal discussion from a blank page."]'::jsonb, '[{"name": "Build the Renewal Case as You Go", "brief": "Accumulating proof of value instead of starting each renewal from scratch."}]'::jsonb),
  ('INT-MKT-034', 'Validation to Traction — Marketing Platform Dependence', 'MKT-006', '["RC-MKT-059"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Identify a backup channel for every client relying on one platform.", "Test it before it is needed.", "Keep it warm enough to activate quickly."]'::jsonb, '[{"name": "Keep a Backup Channel Ready", "brief": "A tested alternative so one platform failing does not stop delivery."}]'::jsonb)
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
        ('Non-Profit, Social Impact & NGO', 'ngo', 'NGO', r"""-- ============================================================================
-- Ally :: Industry seed -- NON-PROFIT, SOCIAL IMPACT & NGO (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: ngo
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (NGO-001, RC-NGO-014, S0-NGO-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : questions name no specific legal structure (society, trust,
--            section 8 company), tax exemption regime or foreign funding
--            statute.  These vary by activity and change, so the content
--            asks the founder what applies to THEM and what they have
--            checked, rather than naming a rule that will go stale.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (funder reporting, restricted funding, founder
--            fundraising dependency, volunteer management, cash flow timing)
--            starts at Stage 0->1; funder concentration, board governance,
--            regulatory compliance, impact at scale, mission drift and
--            succession readiness at Stage 1->10+.
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
  ('NGO-001', 'Mission Defined Too Broadly to Act On', 'The cause is described in terms so wide that no specific activity, community or measurable change has been chosen.', 'Idea & Validation', 'NGO Mission Clarity', 'external', 2, 5, 9, '["Mission statement could describe almost any cause", "No specific community or group named", "No decision on what activity will actually be run", "Everything sounds important, nothing is prioritised", "No conversation with the people meant to benefit"]'::jsonb, '["ngo"]'::jsonb),
  ('NGO-002', 'Registration and Structure Not Understood', 'What legal form to register as, and what each form allows and requires, has not been looked into.', 'Idea & Validation', 'NGO Registration Basics', 'external', 3, 6, 10, '["No idea which legal structure fits the activity", "Assuming any structure lets you take donations and give receipts", "Compliance obligations after registration not understood", "No plan for who handles filings", "Structure chosen without professional advice"]'::jsonb, '["ngo"]'::jsonb),
  ('NGO-003', 'No Idea Who Would Actually Fund This', 'The idea assumes donors, grants or government funding will appear without knowing which of these fits this cause at this stage.', 'Idea & Validation', 'NGO Funding Model Clarity', 'external', 4, 6, 10, '["No one funding source identified as realistic", "Assuming grants are available without applying to any", "No individual donor identified who has given before", "Budget built without a funding source behind it", "No idea how long funding decisions typically take"]'::jsonb, '["ngo"]'::jsonb),
  ('NGO-004', 'No Way to Show the Change Being Made', 'There is no plan for measuring whether the intended beneficiaries are actually better off.', 'Idea & Validation', 'NGO Impact Measurement Basics', 'external', 3, 5, 9, '["Success described as activity, not outcome", "No baseline data on beneficiaries", "No plan for how change will be tracked", "Assuming good intentions are enough to show impact", "No conversation with a funder about what they would want to see"]'::jsonb, '["ngo"]'::jsonb),
  ('NGO-005', 'Every Grant Comes With Different Reporting Demands', 'Each funder wants different formats, timelines and detail, and preparing reports is consuming time that should go to the work.', 'Operations & Systems', 'NGO Funder Reporting', 'external', 3, 6, 9, '["Different report format for every funder", "Reporting consuming significant staff time", "Same data reformatted repeatedly for each funder", "Late reports damaging funder relationships", "No system for tracking what each funder requires"]'::jsonb, '["ngo"]'::jsonb),
  ('NGO-006', 'Funding Restricted to Specific Projects, Not the Organisation', 'Money can only be spent on named activities, so the organisation itself has no funding for basic overhead and stability.', 'Financial Management', 'NGO Restricted Funding', 'external', 4, 6, 9, '["Overhead and core costs have no funding source", "Every grant tied to a specific project", "No unrestricted funds for emergencies", "Staff paid inconsistently across projects", "Core operations dependent on project surplus"]'::jsonb, '["ngo"]'::jsonb),
  ('NGO-007', 'Donor Relationships Depend Entirely on the Founder', 'Every major donor relationship runs through one person, so fundraising has a hard ceiling and a single point of failure.', 'Sales & Revenue', 'NGO Founder Fundraising Dependency', 'external', 5, 6, 9, '["Founder personally manages every major donor", "No one else can ask for money", "Fundraising stops when the founder is unavailable", "No written record of donor relationship history", "New donors turned away for lack of capacity"]'::jsonb, '["ngo"]'::jsonb),
  ('NGO-008', 'Volunteers Come and Go With No Continuity', 'Volunteers are recruited without a structured onboarding or retention process, so knowledge and capacity are constantly rebuilt.', 'Team & Leadership', 'NGO Volunteer Management', 'external', 3, 5, 9, '["High volunteer turnover", "No onboarding process for new volunteers", "Volunteer knowledge lost when they leave", "No record of who has been trained on what", "Recruitment happening reactively, not planned"]'::jsonb, '["ngo"]'::jsonb),
  ('NGO-009', 'Cash Flow Gaps Between Grant Disbursements', 'Grants are paid on their own schedule, often after costs are incurred, leaving gaps the organisation must somehow bridge.', 'Financial Management', 'NGO Cash Flow Timing', 'external', 4, 6, 9, '["Costs incurred before grant money arrives", "No reserve to bridge the gap", "Grant disbursement timing unpredictable", "Staff or supplier payments delayed waiting for funds", "No plan for a delayed disbursement"]'::jsonb, '["ngo"]'::jsonb),
  ('NGO-010', 'Revenue Concentrated in a Few Large Funders', 'A handful of grants or donors provide most of the budget, so their terms dominate and their loss would be severe.', 'Sales & Revenue', 'NGO Funder Concentration', 'external', 4, 7, 10, '["Most funding from a few large sources", "Programme priorities shaped by the largest funder", "No pipeline of replacement funding", "Losing one funder would threaten operations", "Funder relationship terms dictated one way"]'::jsonb, '["ngo"]'::jsonb),
  ('NGO-011', 'Board Governance Not Keeping Pace With the Organisation', 'The board was formed informally and has not developed the oversight, skills or independence a larger organisation needs.', 'Team & Leadership', 'NGO Board Governance', 'external', 3, 7, 10, '["Board members chosen informally through relationships", "No clear separation between board and staff decisions", "Board lacking skills the organisation now needs", "No regular board meeting rhythm", "Founder holding disproportionate influence over the board"]'::jsonb, '["ngo"]'::jsonb),
  ('NGO-012', 'Compliance and Reporting Obligations Now Constant', 'Statutory filings, tax exemptions, foreign funding rules and audit requirements recur continuously and cannot run on memory at this size.', 'Operations & Systems', 'NGO Regulatory Compliance', 'external', 3, 7, 10, '["Filings and renewals tracked from memory", "No single compliance calendar", "Foreign funding rules not monitored for changes", "Audit findings repeating year after year", "One person holding all the compliance knowledge"]'::jsonb, '["ngo"]'::jsonb),
  ('NGO-013', 'Proving Impact Gets Harder as the Organisation Scales', 'What worked as a simple story for a small programme becomes much harder to demonstrate credibly across multiple sites and larger numbers.', 'Operations & Systems', 'NGO Impact at Scale', 'external', 3, 6, 10, '["Impact data inconsistent across programme sites", "No standard method for measuring outcomes", "Funders asking for rigour the organisation cannot yet provide", "Impact claims not independently verified", "Data collection burden falling on frontline staff"]'::jsonb, '["ngo"]'::jsonb),
  ('NGO-014', 'Mission Drift as Funding Shapes Programme Choices', 'Programmes increasingly follow whatever funders will pay for rather than what the original mission and community need most.', 'Strategy & Planning', 'NGO Mission Drift', 'external', 2, 6, 9, '["New programmes chosen because funding exists, not because of need", "Original mission referenced less in decisions", "Staff unsure how current work connects to the mission", "Funder priorities overriding community priorities", "No process for checking a new programme against the mission"]'::jsonb, '["ngo"]'::jsonb),
  ('NGO-015', 'Nothing Institutional Survives the Founder Leaving', 'Relationships, knowledge and credibility are so tied to the founder that succession would be extremely difficult.', 'Strategy & Planning', 'NGO Succession Readiness', 'external', 2, 7, 10, '["Founder personally holds most external relationships", "No successor identified or being developed", "Institutional knowledge undocumented", "Funders and partners engage because of the founder specifically", "No transition plan of any kind"]'::jsonb, '["ngo"]'::jsonb)
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
         t.primary_stage_group, '["ngo"]'::jsonb, z.v
  FROM (VALUES
  ('RC-NGO-001', 'Mission Could Describe Almost Any Cause', 'The stated purpose is too broad to guide any specific decision.', 'NGO-001', 'external', 'Strategic', 0.72, 'Stage 0'),
  ('RC-NGO-002', 'No Specific Community or Group Named', 'Nobody has been named as the people this actually serves.', 'NGO-001', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-NGO-003', 'No Decision on What Activity Will Be Run', 'The cause is clear but the actual programme is not.', 'NGO-001', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-NGO-004', 'Everything Sounds Important, Nothing Prioritised', 'No hierarchy exists among the many things that could be done.', 'NGO-001', 'external', 'Behavioural', 0.68, 'Stage 0'),
  ('RC-NGO-005', 'No Conversation With Intended Beneficiaries', 'Nobody who would receive the help has been consulted.', 'NGO-001', 'external', 'Behavioural', 0.67, 'Stage 0'),
  ('RC-NGO-006', 'Required Legal Structure Unknown', 'Which registration fits the planned activity has not been established.', 'NGO-002', 'external', 'Knowledge', 0.73, 'Stage 0'),
  ('RC-NGO-007', 'Assuming Any Structure Allows Donation Receipts', 'Believing tax and donation mechanics are the same across all structures.', 'NGO-002', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-NGO-008', 'Ongoing Compliance Obligations Not Understood', 'What must be filed after registration has not been checked.', 'NGO-002', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-NGO-009', 'No Owner for Filings', 'Nobody has been made responsible for registration paperwork.', 'NGO-002', 'external', 'Operational', 0.64, 'Stage 0'),
  ('RC-NGO-010', 'No Realistic Funding Source Identified', 'No specific donor, grant or government scheme has been identified as plausible.', 'NGO-003', 'external', 'Strategic', 0.73, 'Stage 0'),
  ('RC-NGO-011', 'Assuming Grants Are Available Without Applying', 'Believing grant money exists without having approached any funder.', 'NGO-003', 'external', 'Behavioural', 0.70, 'Stage 0'),
  ('RC-NGO-012', 'No Individual Donor Identified', 'Nobody who has actually given before has been named or approached.', 'NGO-003', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-NGO-013', 'Budget Built Without a Funding Source Behind It', 'Spending plans exist before any money is confirmed.', 'NGO-003', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-NGO-014', 'Success Described as Activity Not Outcome', 'What counts as success is the work done, not the change created.', 'NGO-004', 'external', 'Strategic', 0.72, 'Stage 0'),
  ('RC-NGO-015', 'No Baseline Data on Beneficiaries', 'Nothing was measured about beneficiaries before the work began.', 'NGO-004', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-NGO-016', 'No Plan for How Change Will Be Tracked', 'Nothing has been decided about ongoing measurement.', 'NGO-004', 'external', 'Operational', 0.70, 'Stage 0'),
  ('RC-NGO-017', 'Assuming Good Intentions Are Enough', 'Believing that meaning well substitutes for showing results.', 'NGO-004', 'external', 'Psychological', 0.68, 'Stage 0'),
  ('RC-NGO-018', 'Different Report Format for Every Funder', 'Each funder is served a uniquely formatted report built from scratch.', 'NGO-005', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-NGO-019', 'Same Data Reformatted Repeatedly', 'The same underlying figures are re-entered differently for each funder.', 'NGO-005', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-NGO-020', 'No System for Tracking Funder Requirements', 'What each funder needs is not recorded centrally.', 'NGO-005', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-NGO-021', 'Late Reports Damaging Relationships', 'Deadlines are missed, harming trust with funders.', 'NGO-005', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-NGO-022', 'Every Grant Tied to a Specific Project', 'Money can only be spent on named activities, never overhead.', 'NGO-006', 'external', 'Strategic', 0.73, 'Stage 0→1'),
  ('RC-NGO-023', 'No Unrestricted Funds for Emergencies', 'Nothing exists that can be spent flexibly when needed.', 'NGO-006', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-NGO-024', 'Core Operations Dependent on Project Surplus', 'Overhead survives only on leftover money from projects.', 'NGO-006', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-NGO-025', 'Staff Paid Inconsistently Across Projects', 'Salaries depend on which project happens to have funds.', 'NGO-006', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-NGO-026', 'Founder Personally Manages Every Major Donor', 'No donor relationship exists independent of the founder.', 'NGO-007', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-NGO-027', 'No One Else Can Ask for Money', 'Fundraising capability rests entirely with one person.', 'NGO-007', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-NGO-028', 'No Written Record of Donor History', 'Relationship history exists only in the founder memory.', 'NGO-007', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-NGO-029', 'New Donors Turned Away for Lack of Capacity', 'Fundraising growth is limited by time, not opportunity.', 'NGO-007', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-NGO-030', 'No Onboarding Process for Volunteers', 'New volunteers start with no structured introduction.', 'NGO-008', 'external', 'Operational', 0.72, 'Stage 0→1'),
  ('RC-NGO-031', 'Volunteer Knowledge Lost on Departure', 'What a volunteer learned leaves with them.', 'NGO-008', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-NGO-032', 'No Record of Who Is Trained on What', 'Skills and training history are not tracked.', 'NGO-008', 'external', 'Operational', 0.69, 'Stage 0→1'),
  ('RC-NGO-033', 'Recruitment Happening Reactively', 'Volunteers are found only when a gap becomes urgent.', 'NGO-008', 'external', 'Behavioural', 0.68, 'Stage 0→1'),
  ('RC-NGO-034', 'Costs Incurred Before Grant Money Arrives', 'Spending happens ahead of when funds actually land.', 'NGO-009', 'external', 'Operational', 0.73, 'Stage 0→1'),
  ('RC-NGO-035', 'No Reserve to Bridge the Gap', 'Nothing has been set aside to cover the timing mismatch.', 'NGO-009', 'external', 'Strategic', 0.72, 'Stage 0→1'),
  ('RC-NGO-036', 'Disbursement Timing Unpredictable', 'When grant money will actually arrive is not known in advance.', 'NGO-009', 'external', 'Knowledge', 0.70, 'Stage 0→1'),
  ('RC-NGO-037', 'Most Funding From a Few Large Sources', 'A handful of funders provide most of the budget.', 'NGO-010', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-NGO-038', 'Programme Priorities Shaped by the Largest Funder', 'What gets done is decided by the biggest source of money.', 'NGO-010', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-NGO-039', 'No Pipeline of Replacement Funding', 'Nothing is being built that could replace a lost funder.', 'NGO-010', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-NGO-040', 'Terms Dictated One Way by the Funder', 'Conditions are imposed rather than negotiated.', 'NGO-010', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-NGO-041', 'Board Chosen Informally Through Relationships', 'Board composition reflects personal networks, not needed skills.', 'NGO-011', 'external', 'Strategic', 0.72, 'Stage 1→10+'),
  ('RC-NGO-042', 'No Separation Between Board and Staff Decisions', 'Governance and operations are not clearly distinguished.', 'NGO-011', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-NGO-043', 'Board Lacking Skills the Organisation Now Needs', 'Financial, legal or sector expertise the board needs is absent.', 'NGO-011', 'external', 'Knowledge', 0.70, 'Stage 1→10+'),
  ('RC-NGO-044', 'No Regular Board Meeting Rhythm', 'Oversight happens irregularly rather than on a set schedule.', 'NGO-011', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-NGO-045', 'Founder Holding Disproportionate Board Influence', 'The founder dominates governance rather than being overseen by it.', 'NGO-011', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-NGO-046', 'Filings and Renewals Tracked From Memory', 'Compliance dates live in memory rather than a system.', 'NGO-012', 'external', 'Operational', 0.73, 'Stage 1→10+'),
  ('RC-NGO-047', 'No Single Compliance Calendar', 'Nothing brings every obligation into one dated place.', 'NGO-012', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-NGO-048', 'Foreign Funding Rules Not Monitored', 'Changes to rules on receiving funds from abroad are not tracked.', 'NGO-012', 'external', 'Knowledge', 0.71, 'Stage 1→10+'),
  ('RC-NGO-049', 'Audit Findings Repeating Year After Year', 'The same issues are raised without ever being fixed.', 'NGO-012', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-NGO-050', 'One Person Holding All the Compliance Knowledge', 'Nobody else understands the organisation compliance position.', 'NGO-012', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-NGO-051', 'Impact Data Inconsistent Across Sites', 'Different programme locations measure things differently.', 'NGO-013', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-NGO-052', 'No Standard Method for Measuring Outcomes', 'There is no single, repeatable way to assess change.', 'NGO-013', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-NGO-053', 'Data Collection Burden Falling on Frontline Staff', 'Measurement work is added to already stretched staff.', 'NGO-013', 'external', 'Operational', 0.68, 'Stage 1→10+'),
  ('RC-NGO-054', 'Impact Claims Not Independently Verified', 'Nobody outside the organisation checks the numbers reported.', 'NGO-013', 'external', 'Strategic', 0.69, 'Stage 1→10+'),
  ('RC-NGO-055', 'New Programmes Chosen Because Funding Exists', 'Activity follows available money rather than assessed need.', 'NGO-014', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-NGO-056', 'Original Mission Referenced Less in Decisions', 'The founding purpose has faded from actual decision making.', 'NGO-014', 'external', 'Behavioural', 0.70, 'Stage 1→10+'),
  ('RC-NGO-057', 'No Process for Checking Programmes Against the Mission', 'New activity is not tested against the original purpose before starting.', 'NGO-014', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-NGO-058', 'Founder Personally Holds Most External Relationships', 'Funders and partners engage because of the founder specifically.', 'NGO-015', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-NGO-059', 'No Successor Identified or Being Developed', 'Nobody is being prepared to take over.', 'NGO-015', 'external', 'Strategic', 0.73, 'Stage 1→10+'),
  ('RC-NGO-060', 'Institutional Knowledge Undocumented', 'What the founder knows exists nowhere else.', 'NGO-015', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-NGO-061', 'No Transition Plan of Any Kind', 'Nothing has been thought through for a founder departure.', 'NGO-015', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-NGO-062', 'No Idea How Long Funding Decisions Take', 'How long a grant or donor decision typically takes has not been found out.', 'NGO-003', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-NGO-063', 'No Conversation With a Funder About Evidence Needs', 'Nobody has asked a funder directly what proof they would want to see.', 'NGO-004', 'external', 'Behavioural', 0.66, 'Stage 0'),
  ('RC-NGO-064', 'No Backup Plan for a Delayed Disbursement', 'Nothing has been prepared for a grant arriving later than expected.', 'NGO-009', 'external', 'Strategic', 0.68, 'Stage 0→1'),
  ('RC-NGO-065', 'No Written Record of Funder Requirements Changing', 'When a funder updates its rules, nothing captures the change for next time.', 'NGO-005', 'external', 'Operational', 0.67, 'Stage 0→1'),
  ('RC-NGO-066', 'No Diversification Target for Funding Sources', 'Nobody has set a goal for how spread out funding should become.', 'NGO-010', 'external', 'Strategic', 0.68, 'Stage 1→10+')
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
         '["ngo"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-NGO-001', 'Could your mission statement describe almost any cause?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-001', 'RC-NGO-001', 1, 'Stage 0'),
  ('S0-NGO-002', 'Who exactly are you trying to help, named specifically?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-001', 'RC-NGO-002', 1, 'Stage 0'),
  ('S0-NGO-003', 'What is the actual activity you will run day to day?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-001', 'RC-NGO-003', 1, 'Stage 0'),
  ('S0-NGO-004', 'Have you talked to the people you want to help about what they actually need?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-001', 'RC-NGO-005', 2, 'Stage 0'),
  ('S0-NGO-005', 'Out of everything you could do, what is the one thing you will do first?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-001', 'RC-NGO-004', 2, 'Stage 0'),
  ('S0-NGO-006', 'Do you know which legal structure fits what you want to do?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-002', 'RC-NGO-006', 1, 'Stage 0'),
  ('S0-NGO-007', 'Do you think any structure lets you give donation receipts?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-002', 'RC-NGO-007', 1, 'Stage 0'),
  ('S0-NGO-008', 'Do you know what you must file every year after registering?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-002', 'RC-NGO-008', 2, 'Stage 0'),
  ('S0-NGO-009', 'Who would handle your registrations and filings?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-002', 'RC-NGO-009', 2, 'Stage 0'),
  ('S0-NGO-010', 'Which specific donor, grant or scheme do you expect to fund this?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-003', 'RC-NGO-010', 1, 'Stage 0'),
  ('S0-NGO-011', 'Have you actually applied to any grant, or are you assuming one exists?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-003', 'RC-NGO-011', 2, 'Stage 0'),
  ('S0-NGO-012', 'Has anyone specific said they would donate to this?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-003', 'RC-NGO-012', 2, 'Stage 0'),
  ('S0-NGO-013', 'Did you build your budget before or after confirming any funding?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-003', 'RC-NGO-013', 2, 'Stage 0'),
  ('S0-NGO-014', 'What number would prove this is working?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-004', 'RC-NGO-014', 1, 'Stage 0'),
  ('S0-NGO-015', 'Do you have any baseline data on the people you plan to help?', 'open_text', 'Idea & Validation', 'CORE', 'NGO-004', 'RC-NGO-015', 2, 'Stage 0'),
  ('S01-NGO-001', 'How many different report formats do you prepare across your funders?', 'open_text', 'Operations & Systems', 'CORE', 'NGO-005', 'RC-NGO-018', 2, 'Stage 0→1'),
  ('S01-NGO-002', 'How much staff time goes into funder reporting each month?', 'open_text', 'Operations & Systems', 'CORE', 'NGO-005', 'RC-NGO-019', 2, 'Stage 0→1'),
  ('S01-NGO-003', 'Is there one place that tracks what each funder requires and when?', 'open_text', 'Operations & Systems', 'CORE', 'NGO-005', 'RC-NGO-020', 2, 'Stage 0→1'),
  ('S01-NGO-004', 'Have you ever sent a funder report late?', 'open_text', 'Operations & Systems', 'CORE', 'NGO-005', 'RC-NGO-021', 2, 'Stage 0→1'),
  ('S01-NGO-005', 'What share of your funding can be spent on overhead rather than a named project?', 'open_text', 'Financial Management', 'CORE', 'NGO-006', 'RC-NGO-022', 2, 'Stage 0→1'),
  ('S01-NGO-006', 'Do you have any money that is not tied to a specific project?', 'open_text', 'Financial Management', 'CORE', 'NGO-006', 'RC-NGO-023', 2, 'Stage 0→1'),
  ('S01-NGO-007', 'Does your core team get paid consistently, or does it depend on which project has funds?', 'open_text', 'Financial Management', 'CORE', 'NGO-006', 'RC-NGO-025', 2, 'Stage 0→1'),
  ('S01-NGO-008', 'If all project grants ended tomorrow, could you keep the lights on?', 'open_text', 'Financial Management', 'CORE', 'NGO-006', 'RC-NGO-024', 3, 'Stage 0→1'),
  ('S01-NGO-009', 'How many major donors do you personally manage?', 'open_text', 'Sales & Revenue', 'CORE', 'NGO-007', 'RC-NGO-026', 2, 'Stage 0→1'),
  ('S01-NGO-010', 'Could anyone else in your organisation ask a donor for money?', 'open_text', 'Sales & Revenue', 'CORE', 'NGO-007', 'RC-NGO-027', 2, 'Stage 0→1'),
  ('S01-NGO-011', 'Is donor relationship history written down anywhere?', 'open_text', 'Sales & Revenue', 'CORE', 'NGO-007', 'RC-NGO-028', 2, 'Stage 0→1'),
  ('S01-NGO-012', 'Have you turned away a potential donor for lack of time?', 'open_text', 'Sales & Revenue', 'CORE', 'NGO-007', 'RC-NGO-029', 2, 'Stage 0→1'),
  ('S01-NGO-013', 'What happens when a new volunteer joins?', 'open_text', 'Team & Leadership', 'CORE', 'NGO-008', 'RC-NGO-030', 2, 'Stage 0→1'),
  ('S01-NGO-014', 'When a volunteer leaves, does their knowledge leave with them?', 'open_text', 'Team & Leadership', 'CORE', 'NGO-008', 'RC-NGO-031', 2, 'Stage 0→1'),
  ('S01-NGO-015', 'Do you know who has been trained on what?', 'open_text', 'Team & Leadership', 'CORE', 'NGO-008', 'RC-NGO-032', 2, 'Stage 0→1'),
  ('S01-NGO-016', 'Do you recruit volunteers ahead of need, or only when a gap becomes urgent?', 'open_text', 'Team & Leadership', 'CORE', 'NGO-008', 'RC-NGO-033', 2, 'Stage 0→1'),
  ('S01-NGO-017', 'How often do you spend money before the related grant has actually arrived?', 'open_text', 'Financial Management', 'CORE', 'NGO-009', 'RC-NGO-034', 2, 'Stage 0→1'),
  ('S01-NGO-018', 'Do you have any reserve to cover a gap in disbursement timing?', 'open_text', 'Financial Management', 'CORE', 'NGO-009', 'RC-NGO-035', 2, 'Stage 0→1'),
  ('S01-NGO-019', 'Can you predict when a grant will actually be paid?', 'open_text', 'Financial Management', 'CORE', 'NGO-009', 'RC-NGO-036', 3, 'Stage 0→1'),
  ('S01-NGO-020', 'Has a delayed disbursement ever forced you to delay paying staff or suppliers?', 'open_text', 'Financial Management', 'CORE', 'NGO-009', 'RC-NGO-034', 3, 'Stage 0→1'),
  ('S10-NGO-001', 'What share of your funding comes from your top two or three sources?', 'open_text', 'Sales & Revenue', 'CORE', 'NGO-010', 'RC-NGO-037', 2, 'Stage 1→10+'),
  ('S10-NGO-002', 'Are your programme choices shaped by your largest funder?', 'open_text', 'Strategy & Planning', 'CORE', 'NGO-010', 'RC-NGO-038', 3, 'Stage 1→10+'),
  ('S10-NGO-003', 'If your largest funder left, how long could you continue?', 'open_text', 'Strategy & Planning', 'CORE', 'NGO-010', 'RC-NGO-039', 3, 'Stage 1→10+'),
  ('S10-NGO-004', 'Who sets the terms with your dominant funder, you or them?', 'open_text', 'Sales & Revenue', 'CORE', 'NGO-010', 'RC-NGO-040', 2, 'Stage 1→10+'),
  ('S10-NGO-005', 'How were your current board members chosen?', 'open_text', 'Team & Leadership', 'CORE', 'NGO-011', 'RC-NGO-041', 2, 'Stage 1→10+'),
  ('S10-NGO-006', 'Is there a clear line between what the board decides and what staff decide?', 'open_text', 'Team & Leadership', 'CORE', 'NGO-011', 'RC-NGO-042', 3, 'Stage 1→10+'),
  ('S10-NGO-007', 'Does your board have the financial or legal skills the organisation now needs?', 'open_text', 'Team & Leadership', 'CORE', 'NGO-011', 'RC-NGO-043', 3, 'Stage 1→10+'),
  ('S10-NGO-008', 'How often does your board actually meet?', 'open_text', 'Team & Leadership', 'CORE', 'NGO-011', 'RC-NGO-044', 2, 'Stage 1→10+'),
  ('S10-NGO-009', 'Does the founder hold more influence over the board than a normal member would?', 'open_text', 'Team & Leadership', 'CORE', 'NGO-011', 'RC-NGO-045', 3, 'Stage 1→10+'),
  ('S10-NGO-010', 'Can you list every filing and renewal you are responsible for, with dates?', 'open_text', 'Operations & Systems', 'CORE', 'NGO-012', 'RC-NGO-047', 2, 'Stage 1→10+'),
  ('S10-NGO-011', 'Who is watching for changes to rules on receiving funds from abroad?', 'open_text', 'Operations & Systems', 'CORE', 'NGO-012', 'RC-NGO-048', 3, 'Stage 1→10+'),
  ('S10-NGO-012', 'Have the same audit findings come up more than once?', 'open_text', 'Operations & Systems', 'CORE', 'NGO-012', 'RC-NGO-049', 3, 'Stage 1→10+'),
  ('S10-NGO-013', 'If the person who tracks compliance left, what would happen?', 'open_text', 'Team & Leadership', 'CORE', 'NGO-012', 'RC-NGO-050', 3, 'Stage 1→10+'),
  ('S10-NGO-014', 'Do all your programme sites measure impact the same way?', 'open_text', 'Operations & Systems', 'CORE', 'NGO-013', 'RC-NGO-051', 3, 'Stage 1→10+'),
  ('S10-NGO-015', 'Is there a standard method you use to measure outcomes?', 'open_text', 'Operations & Systems', 'CORE', 'NGO-013', 'RC-NGO-052', 2, 'Stage 1→10+'),
  ('S10-NGO-016', 'Has anyone outside the organisation verified your impact numbers?', 'open_text', 'Operations & Systems', 'CORE', 'NGO-013', 'RC-NGO-054', 3, 'Stage 1→10+'),
  ('S10-NGO-017', 'Is data collection adding a real burden to frontline staff?', 'open_text', 'Team & Leadership', 'CORE', 'NGO-013', 'RC-NGO-053', 2, 'Stage 1→10+'),
  ('S10-NGO-018', 'Have you started a programme mainly because funding existed for it?', 'open_text', 'Strategy & Planning', 'CORE', 'NGO-014', 'RC-NGO-055', 3, 'Stage 1→10+'),
  ('S10-NGO-019', 'How often does your original mission come up in decisions now?', 'open_text', 'Strategy & Planning', 'CORE', 'NGO-014', 'RC-NGO-056', 3, 'Stage 1→10+'),
  ('S10-NGO-020', 'Is a new programme ever tested against your mission before you start it?', 'open_text', 'Strategy & Planning', 'CORE', 'NGO-014', 'RC-NGO-057', 2, 'Stage 1→10+'),
  ('S10-NGO-021', 'How many funders or partners are engaged mainly because of the founder?', 'open_text', 'Strategy & Planning', 'CORE', 'NGO-015', 'RC-NGO-058', 3, 'Stage 1→10+'),
  ('S10-NGO-022', 'Is anyone being prepared to take over from the founder?', 'open_text', 'Team & Leadership', 'CORE', 'NGO-015', 'RC-NGO-059', 3, 'Stage 1→10+'),
  ('S10-NGO-023', 'Is what the founder knows written down anywhere?', 'open_text', 'Operations & Systems', 'CORE', 'NGO-015', 'RC-NGO-060', 2, 'Stage 1→10+'),
  ('S10-NGO-024', 'Is there any plan for what happens if the founder leaves suddenly?', 'open_text', 'Strategy & Planning', 'CORE', 'NGO-015', 'RC-NGO-061', 3, 'Stage 1→10+'),
  ('S10-NGO-025', 'Would a funder notice a difference in rigour between your smallest and largest programme?', 'open_text', 'Operations & Systems', 'CORE', 'NGO-013', 'RC-NGO-051', 3, 'Stage 1→10+')
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
  ('S0-NGO-001', 'icp'),
  ('S0-NGO-002', 'icp'),
  ('S0-NGO-003', 'icp'),
  ('S0-NGO-004', 'icp'),
  ('S0-NGO-005', 'icp'),
  ('S0-NGO-006', 'technical-quality'),
  ('S0-NGO-007', 'technical-quality'),
  ('S0-NGO-008', 'technical-quality'),
  ('S0-NGO-009', 'technical-quality'),
  ('S0-NGO-010', 'willingness-to-pay'),
  ('S0-NGO-011', 'willingness-to-pay'),
  ('S0-NGO-012', 'willingness-to-pay'),
  ('S0-NGO-013', 'willingness-to-pay'),
  ('S0-NGO-014', 'technical-quality'),
  ('S0-NGO-015', 'technical-quality'),
  ('S01-NGO-001', 'technical-quality'),
  ('S01-NGO-002', 'technical-quality'),
  ('S01-NGO-003', 'technical-quality'),
  ('S01-NGO-004', 'technical-quality'),
  ('S01-NGO-005', 'willingness-to-pay'),
  ('S01-NGO-006', 'willingness-to-pay'),
  ('S01-NGO-007', 'willingness-to-pay'),
  ('S01-NGO-008', 'willingness-to-pay'),
  ('S01-NGO-009', 'icp'),
  ('S01-NGO-010', 'icp'),
  ('S01-NGO-011', 'icp'),
  ('S01-NGO-012', 'icp'),
  ('S01-NGO-013', 'technical-quality'),
  ('S01-NGO-014', 'technical-quality'),
  ('S01-NGO-015', 'technical-quality'),
  ('S01-NGO-016', 'technical-quality'),
  ('S01-NGO-017', 'willingness-to-pay'),
  ('S01-NGO-018', 'willingness-to-pay'),
  ('S01-NGO-019', 'willingness-to-pay'),
  ('S01-NGO-020', 'willingness-to-pay'),
  ('S10-NGO-001', 'willingness-to-pay'),
  ('S10-NGO-002', 'willingness-to-pay'),
  ('S10-NGO-003', 'willingness-to-pay'),
  ('S10-NGO-004', 'willingness-to-pay'),
  ('S10-NGO-005', 'technical-quality'),
  ('S10-NGO-006', 'technical-quality'),
  ('S10-NGO-007', 'technical-quality'),
  ('S10-NGO-008', 'technical-quality'),
  ('S10-NGO-009', 'technical-quality'),
  ('S10-NGO-010', 'technical-quality'),
  ('S10-NGO-011', 'technical-quality'),
  ('S10-NGO-012', 'technical-quality'),
  ('S10-NGO-013', 'technical-quality'),
  ('S10-NGO-014', 'technical-quality'),
  ('S10-NGO-015', 'technical-quality'),
  ('S10-NGO-016', 'technical-quality'),
  ('S10-NGO-017', 'technical-quality'),
  ('S10-NGO-018', 'technical-quality'),
  ('S10-NGO-019', 'technical-quality'),
  ('S10-NGO-020', 'technical-quality'),
  ('S10-NGO-021', 'technical-quality'),
  ('S10-NGO-022', 'technical-quality'),
  ('S10-NGO-023', 'technical-quality'),
  ('S10-NGO-024', 'technical-quality'),
  ('S10-NGO-025', 'technical-quality')
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
         '["ngo"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-NGO-001', 'Ideation — NGO Mission Clarity', 'NGO-001', '["RC-NGO-001", "RC-NGO-002"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Name the specific community or group you serve.", "Rewrite your mission so it could not describe any other cause.", "Test it by asking whether it rules anything out."]'::jsonb, '[{"name": "Narrow the Mission", "brief": "A mission specific enough to actually guide decisions."}]'::jsonb),
  ('INT-NGO-002', 'Ideation — NGO Mission Clarity', 'NGO-001', '["RC-NGO-003", "RC-NGO-004"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Choose the one activity you will run first.", "Write down what you will not do yet.", "Say no to everything outside that for now."]'::jsonb, '[{"name": "Pick One Activity", "brief": "One concrete programme instead of everything the cause could include."}]'::jsonb),
  ('INT-NGO-003', 'Ideation — NGO Mission Clarity', 'NGO-001', '["RC-NGO-005"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Talk to the people you intend to help before designing the programme.", "Ask what they actually need, not what you assume they need.", "Adjust the plan based on what they say."]'::jsonb, '[{"name": "Talk to Beneficiaries First", "brief": "Designing the programme around what beneficiaries say, not assumptions."}]'::jsonb),
  ('INT-NGO-004', 'Ideation — NGO Registration Basics', 'NGO-002', '["RC-NGO-006", "RC-NGO-007"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Find out which legal structure actually fits your activity.", "Check what each structure allows for donations and receipts.", "Get this confirmed before registering."]'::jsonb, '[{"name": "Match Structure to Activity", "brief": "Choosing a legal form based on what it actually permits."}]'::jsonb),
  ('INT-NGO-005', 'Ideation — NGO Registration Basics', 'NGO-002', '["RC-NGO-008", "RC-NGO-009"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Find out what must be filed every year after registration.", "Name one person responsible for filings.", "Keep a dated list of what is due and when."]'::jsonb, '[{"name": "Know the Ongoing Obligations", "brief": "Understanding what registration commits you to every year, not just once."}]'::jsonb),
  ('INT-NGO-006', 'Ideation — NGO Funding Model Clarity', 'NGO-003', '["RC-NGO-010", "RC-NGO-011"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Identify a specific, realistic funding source before building a budget.", "Actually apply to a grant instead of assuming one is available.", "Track what real funders say back."]'::jsonb, '[{"name": "Find a Real Funding Source", "brief": "A specific funder identified and approached, not assumed."}]'::jsonb),
  ('INT-NGO-007', 'Ideation — NGO Funding Model Clarity', 'NGO-003', '["RC-NGO-012", "RC-NGO-013"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Approach at least one specific individual donor.", "Build your budget only after funding is confirmed, not before.", "Scale the plan to match what is actually committed."]'::jsonb, '[{"name": "Budget After Funding, Not Before", "brief": "Sizing the plan to confirmed money rather than hoped for money."}]'::jsonb),
  ('INT-NGO-008', 'Ideation — NGO Impact Measurement Basics', 'NGO-004', '["RC-NGO-014", "RC-NGO-017"]'::jsonb, '[1]'::jsonb, 'Operations', '["Define success as a change in beneficiaries, not a count of activities.", "Stop assuming good intentions are proof enough.", "Write down the number that would show it worked."]'::jsonb, '[{"name": "Define Success as Outcome", "brief": "Measuring change in people, not just activity delivered."}]'::jsonb),
  ('INT-NGO-009', 'Ideation — NGO Impact Measurement Basics', 'NGO-004', '["RC-NGO-015", "RC-NGO-016"]'::jsonb, '[1]'::jsonb, 'Operations', '["Collect baseline data on beneficiaries before starting.", "Decide now how change will be tracked going forward.", "Ask a funder what evidence they would want to see."]'::jsonb, '[{"name": "Baseline Before You Start", "brief": "A measured starting point so change can actually be shown later."}]'::jsonb),
  ('INT-NGO-010', 'Validation to Traction — NGO Funder Reporting', 'NGO-005', '["RC-NGO-018", "RC-NGO-019"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Build one internal master record of your data.", "Generate each funder report from that single source.", "Reformat only the output, never redo the underlying work."]'::jsonb, '[{"name": "One Source, Many Formats", "brief": "A single internal record that every funder report is built from."}]'::jsonb),
  ('INT-NGO-011', 'Validation to Traction — NGO Funder Reporting', 'NGO-005', '["RC-NGO-020", "RC-NGO-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Keep one calendar of every funder deadline and requirement.", "Review it monthly, not when a deadline is close.", "Never let a report go out late again."]'::jsonb, '[{"name": "One Funder Calendar", "brief": "Tracking every requirement and deadline in one place."}]'::jsonb),
  ('INT-NGO-012', 'Validation to Traction — NGO Restricted Funding', 'NGO-006', '["RC-NGO-022", "RC-NGO-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Actively seek at least one source of unrestricted funding.", "Build a small reserve from any flexible money you get.", "Use it only for genuine emergencies or core costs."]'::jsonb, '[{"name": "Build Unrestricted Reserves", "brief": "Seeking flexible money to fund what project grants cannot."}]'::jsonb),
  ('INT-NGO-013', 'Validation to Traction — NGO Restricted Funding', 'NGO-006', '["RC-NGO-024", "RC-NGO-025"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Work out what core operations actually cost every month.", "Negotiate a fair overhead allocation into every grant you seek.", "Stop relying on project surplus to fund the organisation."]'::jsonb, '[{"name": "Cost and Claim Your Overhead", "brief": "Knowing core costs and building them into every funding ask."}]'::jsonb),
  ('INT-NGO-014', 'Validation to Traction — NGO Founder Fundraising Dependency', 'NGO-007', '["RC-NGO-026", "RC-NGO-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Introduce a second person into donor conversations.", "Write down how you actually approach and steward a donor.", "Let them run a smaller relationship alone."]'::jsonb, '[{"name": "Bring in a Second Fundraiser", "brief": "Documenting the approach and training someone else to use it."}]'::jsonb),
  ('INT-NGO-015', 'Validation to Traction — NGO Founder Fundraising Dependency', 'NGO-007', '["RC-NGO-028", "RC-NGO-029"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Keep a written record of every donor relationship and its history.", "Track donors turned away for lack of time.", "Use that record to justify more fundraising capacity."]'::jsonb, '[{"name": "Record Donor History", "brief": "Written relationship records so knowledge does not live only in one head."}]'::jsonb),
  ('INT-NGO-016', 'Validation to Traction — NGO Volunteer Management', 'NGO-008', '["RC-NGO-030", "RC-NGO-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Build a simple onboarding process for every new volunteer.", "Keep a record of who is trained on what.", "Use it before assigning any task."]'::jsonb, '[{"name": "Onboarding and Training Record", "brief": "A structured start and a record of who can do what."}]'::jsonb),
  ('INT-NGO-017', 'Validation to Traction — NGO Volunteer Management', 'NGO-008', '["RC-NGO-031", "RC-NGO-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Team', '["Capture what a volunteer learned before they leave.", "Recruit ahead of need rather than reactively.", "Build a small pipeline of prospective volunteers."]'::jsonb, '[{"name": "Capture Knowledge, Recruit Ahead", "brief": "Preserving what leavers know and planning recruitment in advance."}]'::jsonb),
  ('INT-NGO-018', 'Validation to Traction — NGO Cash Flow Timing', 'NGO-009', '["RC-NGO-034", "RC-NGO-035"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Measure the typical gap between spending and disbursement.", "Build a small reserve sized to that gap.", "Use it only to bridge timing, not to fund new spending."]'::jsonb, '[{"name": "Reserve Sized to the Gap", "brief": "A buffer matched to the real timing mismatch between cost and payment."}]'::jsonb),
  ('INT-NGO-019', 'Validation to Traction — NGO Cash Flow Timing', 'NGO-009', '["RC-NGO-036"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Ask funders directly about their typical disbursement timeline.", "Plan cash flow around the realistic answer, not the hoped for one.", "Flag risk early if a disbursement is running late."]'::jsonb, '[{"name": "Ask and Plan for Real Timelines", "brief": "Planning cash around what funders actually confirm, not assumptions."}]'::jsonb),
  ('INT-NGO-020', 'Growth to Maturity — NGO Funder Concentration', 'NGO-010', '["RC-NGO-037", "RC-NGO-039"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Calculate the funding share of your top three sources.", "Set a ceiling and build a pipeline of smaller or new funders.", "Review the share every year."]'::jsonb, '[{"name": "Cap Funder Concentration", "brief": "Measuring dependence and building beyond the dominant few."}]'::jsonb),
  ('INT-NGO-021', 'Growth to Maturity — NGO Funder Concentration', 'NGO-010', '["RC-NGO-038", "RC-NGO-040"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Identify which programme decisions are driven by the largest funder.", "Distinguish funder priorities from community priorities.", "Negotiate terms rather than simply accepting them."]'::jsonb, '[{"name": "Separate Funder Priorities From Mission Priorities", "brief": "Keeping programme decisions grounded in need, not just in who pays."}]'::jsonb),
  ('INT-NGO-022', 'Growth to Maturity — NGO Board Governance', 'NGO-011', '["RC-NGO-041", "RC-NGO-043"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Assess what skills the board actually needs now.", "Recruit board members deliberately against those gaps.", "Move away from relationship only selection."]'::jsonb, '[{"name": "Recruit the Board You Need", "brief": "Deliberate board recruitment against real skill gaps."}]'::jsonb),
  ('INT-NGO-023', 'Growth to Maturity — NGO Board Governance', 'NGO-011', '["RC-NGO-042", "RC-NGO-044", "RC-NGO-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Set a regular board meeting schedule and keep it.", "Clarify what the board decides versus what staff decide.", "Balance founder influence with genuine independent oversight."]'::jsonb, '[{"name": "Real Oversight, Real Rhythm", "brief": "A functioning governance rhythm with genuine independence from the founder."}]'::jsonb),
  ('INT-NGO-024', 'Growth to Maturity — NGO Regulatory Compliance', 'NGO-012', '["RC-NGO-046", "RC-NGO-047"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Build one calendar covering every filing, renewal and obligation.", "Set reminders well ahead of each date.", "Review it monthly."]'::jsonb, '[{"name": "One Compliance Calendar", "brief": "Every recurring obligation and deadline in one dated place."}]'::jsonb),
  ('INT-NGO-025', 'Growth to Maturity — NGO Regulatory Compliance', 'NGO-012', '["RC-NGO-048", "RC-NGO-049", "RC-NGO-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Assign someone to track rules on foreign funding specifically.", "Close audit findings permanently instead of repeating them.", "Train a second person on the whole compliance picture."]'::jsonb, '[{"name": "Watch, Fix, and Cross Train", "brief": "Active monitoring, permanent fixes, and compliance knowledge held by more than one person."}]'::jsonb),
  ('INT-NGO-026', 'Growth to Maturity — NGO Impact at Scale', 'NGO-013', '["RC-NGO-051", "RC-NGO-052"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Build one standard method for measuring outcomes across every site.", "Train all sites to use it consistently.", "Compare results across sites using the same method."]'::jsonb, '[{"name": "One Standard Measurement Method", "brief": "Consistent outcome measurement across every programme site."}]'::jsonb),
  ('INT-NGO-027', 'Growth to Maturity — NGO Impact at Scale', 'NGO-013', '["RC-NGO-053", "RC-NGO-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Design data collection to minimise burden on frontline staff.", "Seek independent verification of key impact claims.", "Use both to build credibility with funders."]'::jsonb, '[{"name": "Lighter Collection, Independent Checks", "brief": "Reducing staff burden while adding outside verification."}]'::jsonb),
  ('INT-NGO-028', 'Growth to Maturity — NGO Mission Drift', 'NGO-014', '["RC-NGO-055", "RC-NGO-057"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Build a simple test that checks any new programme against the mission.", "Apply it before accepting funding tied to a new activity.", "Decline funding that fails the test."]'::jsonb, '[{"name": "Test Programmes Against the Mission", "brief": "A deliberate check before funding shapes what the organisation does."}]'::jsonb),
  ('INT-NGO-029', 'Growth to Maturity — NGO Mission Drift', 'NGO-014', '["RC-NGO-056"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Bring the original mission back into regular decision conversations.", "Review current programmes against it.", "Retire or adjust anything that no longer fits."]'::jsonb, '[{"name": "Bring the Mission Back In", "brief": "Reconnecting current decisions to the founding purpose."}]'::jsonb),
  ('INT-NGO-030', 'Growth to Maturity — NGO Succession Readiness', 'NGO-015', '["RC-NGO-058", "RC-NGO-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Introduce a second person into key external relationships.", "Document what the founder knows about partners and funders.", "Do this well before a transition is needed."]'::jsonb, '[{"name": "Share the Relationships and the Knowledge", "brief": "Spreading external relationships and institutional knowledge beyond one person."}]'::jsonb),
  ('INT-NGO-031', 'Growth to Maturity — NGO Succession Readiness', 'NGO-015', '["RC-NGO-059", "RC-NGO-061"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Identify and begin developing a potential successor.", "Write a basic transition plan, even a simple one.", "Review and update it periodically."]'::jsonb, '[{"name": "Identify a Successor and a Plan", "brief": "Starting succession preparation before it becomes urgent."}]'::jsonb),
  ('INT-NGO-032', 'Ideation — NGO Funding Model Clarity', 'NGO-003', '["RC-NGO-062"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Ask funders directly how long their decision process typically takes.", "Plan your runway around that realistic timeline.", "Never assume a fast yes."]'::jsonb, '[{"name": "Know the Real Decision Timeline", "brief": "Planning around how long funders actually take, not hope."}]'::jsonb),
  ('INT-NGO-033', 'Ideation — NGO Impact Measurement Basics', 'NGO-004', '["RC-NGO-063"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Ask a realistic funder what evidence they would want to see.", "Design your measurement plan around that answer.", "Confirm it before committing to a method."]'::jsonb, '[{"name": "Ask a Funder What They Would Want to See", "brief": "Designing measurement around real funder expectations, not guesses."}]'::jsonb),
  ('INT-NGO-034', 'Validation to Traction — NGO Cash Flow Timing', 'NGO-009', '["RC-NGO-064"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Write a specific plan for what happens if a disbursement is delayed.", "Identify who would need to be told and what would be cut first.", "Test the plan against your worst realistic delay."]'::jsonb, '[{"name": "Plan for a Delayed Disbursement", "brief": "A specific response ready before a delay actually happens."}]'::jsonb)
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
        ('E-Commerce & D2C', 'ecommerce_d2c', 'ECM', r"""-- ============================================================================
-- Ally :: Industry seed -- E-COMMERCE & D2C (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: ecommerce_d2c
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (ECM-001, RC-ECM-014, S0-ECM-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Trading depth (ad payback, returns/RTO, stock health) starts at
--            Stage 0->1.
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
  ('ECM-001', 'Selling Something Nobody Is Looking For', 'The founder wants to sell a product but has never checked whether people are actually searching for it or how anyone would find the store.', 'Idea & Validation', 'E-commerce Demand Validation', 'external', 2, 3, 7, '["Never checked whether anyone searches for this product", "Assuming a good product will sell itself", "No idea what similar products sell for online", "Copying a product seen doing well elsewhere without checking local demand", "No evidence anyone wants to buy this"]'::jsonb, '["ecommerce_d2c"]'::jsonb),
  ('ECM-002', 'No Idea How Customers Will Be Reached', 'The plan is to put the store online and hope people arrive, with no thought given to how a stranger would ever discover it.', 'Idea & Validation', 'E-commerce Customer Reach', 'external', 2, 4, 8, '["No plan for how the first customers will find the store", "Assuming a website alone brings visitors", "No single channel chosen to start with", "No idea what it costs to get one visitor", "Expecting word of mouth before anyone has bought"]'::jsonb, '["ecommerce_d2c"]'::jsonb),
  ('ECM-003', 'Product Sourcing Not Thought Through', 'There is no clarity on where the product comes from, what it costs to buy, or whether more can be obtained quickly if it sells.', 'Idea & Validation', 'E-commerce Sourcing Basics', 'external', 3, 4, 8, '["No supplier identified yet", "Buying cost unknown", "No idea how long restocking would take", "Assuming any supplier can be swapped for another", "No thought given to how much stock to start with"]'::jsonb, '["ecommerce_d2c"]'::jsonb),
  ('ECM-004', 'Shipping and Returns Never Considered', 'The idea stops at the sale, with no thought about how the product reaches the customer or what happens when they send it back.', 'Idea & Validation', 'E-commerce Fulfilment Basics', 'external', 3, 4, 8, '["Delivery cost not counted in the price", "No idea who arranges shipping", "No rule for what happens with a return", "Packaging not considered at all", "Assuming returns will be rare"]'::jsonb, '["ecommerce_d2c"]'::jsonb),
  ('ECM-005', 'Customers Buy Once and Never Return', 'Orders are coming in but nearly every one is from a new customer, and almost nobody buys a second time.', 'Sales & Revenue', 'E-commerce Repeat Purchase', 'external', 4, 5, 9, '["Repeat purchase rate never measured", "Nothing sent to the customer after delivery", "No reason given for a customer to come back", "Growth depends entirely on new buyers", "No idea which customers are the best ones"]'::jsonb, '["ecommerce_d2c"]'::jsonb),
  ('ECM-006', 'Ad Spend Eats the Whole Margin', 'Paid ads bring orders, but the cost of getting each order is close to or higher than the profit that order makes.', 'Financial Management', 'E-commerce Acquisition Economics', 'external', 4, 6, 9, '["Cost per order from ads not known", "Profit per order never compared against ad cost", "Ad spend increased without checking returns", "Revenue growing while profit is flat or falling", "No channel level view of what actually pays back"]'::jsonb, '["ecommerce_d2c"]'::jsonb),
  ('ECM-007', 'Returns and RTO Not Under Control', 'Returns and failed cash on delivery deliveries are quietly destroying profit, and nobody is tracking how much.', 'Operations & Systems', 'E-commerce Returns and RTO', 'external', 3, 6, 9, '["Return and RTO percentage not tracked", "Reasons for returns never collected", "Cash on delivery failures treated as normal", "Cost of a failed delivery never calculated", "No action taken on products that get returned most"]'::jsonb, '["ecommerce_d2c"]'::jsonb),
  ('ECM-008', 'Cash Stuck in the Wrong Stock', 'Money is tied up in products that do not sell while the fast moving ones keep going out of stock.', 'Financial Management', 'E-commerce Inventory Health', 'external', 4, 5, 9, '["Slow moving stock never identified", "Best sellers regularly out of stock", "Reordering done by feel rather than sell through", "Cash locked in inventory not measured", "No stock age or turnover view"]'::jsonb, '["ecommerce_d2c"]'::jsonb),
  ('ECM-009', 'Channel Choice Made by Default', 'Selling on a marketplace or on an own store happened by accident, and the trade off between reach and margin was never worked out.', 'Strategy & Planning', 'E-commerce Channel Strategy', 'external', 2, 5, 9, '["Channel chosen without comparing margins", "Marketplace commission and fees not counted", "No plan to build direct customers", "Customer data sitting with the marketplace, not the brand", "Pricing same across channels despite different costs"]'::jsonb, '["ecommerce_d2c"]'::jsonb),
  ('ECM-010', 'Warehouse and Fulfilment Straining at Volume', 'Order volume has outgrown the packing setup, so delays, wrong items and mis-shipments are rising.', 'Operations & Systems', 'E-commerce Fulfilment at Scale', 'external', 3, 6, 9, '["Pick and pack process not written down", "Order accuracy never measured", "Warehouse layout unchanged since the early days", "No capacity plan for peak season", "Dispatch delays becoming normal"]'::jsonb, '["ecommerce_d2c"]'::jsonb),
  ('ECM-011', 'Rising Acquisition Cost With No Retention Cushion', 'Ad costs climb every year while the business has no strong repeat customer base to absorb the increase.', 'Sales & Revenue', 'E-commerce Acquisition Pressure', 'external', 4, 6, 9, '["Cost per customer rising year on year", "No measurement of customer lifetime value", "Retention never improved to offset rising ad cost", "Growth entirely dependent on paid traffic", "Margins shrinking as ad rates rise"]'::jsonb, '["ecommerce_d2c"]'::jsonb),
  ('ECM-012', 'Discounting Has Become the Default', 'Sales now depend on constant offers, and selling at full price has quietly stopped working.', 'Sales & Revenue', 'E-commerce Pricing Discipline', 'external', 4, 5, 9, '["Sales drop sharply whenever offers stop", "Customers wait for the next sale before buying", "Discount depth increasing over time", "Full price selling never tested recently", "Margin per order falling steadily"]'::jsonb, '["ecommerce_d2c"]'::jsonb),
  ('ECM-013', 'SKU Count Out of Control', 'Too many products are carried, most revenue comes from a few, and the long tail eats cash, space and attention.', 'Operations & Systems', 'E-commerce Assortment Control', 'external', 3, 5, 9, '["Product count grown without review", "Most revenue from a small share of products", "Long tail products holding cash and space", "No process for retiring a product", "Team attention spread across too many items"]'::jsonb, '["ecommerce_d2c"]'::jsonb),
  ('ECM-014', 'Dependence on One Platform or Ad Channel', 'Most orders arrive through a single marketplace or single ad platform, so one policy or algorithm change could halt the business.', 'Strategy & Planning', 'E-commerce Channel Risk', 'external', 2, 7, 10, '["Majority of orders from one source", "No second channel built up", "No plan if the platform changes rules or blocks the account", "Pricing and promotion dictated by the platform", "Growth stops whenever that channel dips"]'::jsonb, '["ecommerce_d2c"]'::jsonb),
  ('ECM-015', 'No Real Customer Data Ownership', 'The brand still cannot contact its own buyers directly because the customer relationship sits with the platforms.', 'Strategy & Planning', 'E-commerce Customer Ownership', 'external', 2, 5, 9, '["No own customer contact list", "Buyer details held by the marketplace", "No direct channel to reach past customers", "Repeat selling depends on paying the platform again", "No consent collected for direct contact"]'::jsonb, '["ecommerce_d2c"]'::jsonb)
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
         t.primary_stage_group, '["ecommerce_d2c"]'::jsonb, z.v
  FROM (VALUES
  ('RC-ECM-001', 'Never Checked If Anyone Searches For This', 'No one has looked at whether people actually search online for this kind of product.', 'ECM-001', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-ECM-002', 'Assuming a Good Product Sells Itself', 'The founder believes quality alone will bring buyers, without any push.', 'ECM-001', 'external', 'Psychological', 0.64, 'Stage 0'),
  ('RC-ECM-003', 'Online Prices of Similar Products Unknown', 'No idea what comparable products already sell for, so pricing is guesswork.', 'ECM-001', 'external', 'Knowledge', 0.62, 'Stage 0'),
  ('RC-ECM-004', 'Copying Something Seen Working Elsewhere', 'The idea was taken from another market without checking demand here.', 'ECM-001', 'external', 'Behavioural', 0.61, 'Stage 0'),
  ('RC-ECM-005', 'No Evidence Anyone Wants to Buy', 'Nobody outside the founder has shown any intent to purchase.', 'ECM-001', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-ECM-006', 'No Plan for the First Customers', 'There is no thought about where the very first buyers will come from.', 'ECM-002', 'external', 'Strategic', 0.68, 'Stage 0'),
  ('RC-ECM-007', 'Assuming a Website Brings Visitors', 'The founder believes having a store online is the same as having traffic.', 'ECM-002', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-ECM-008', 'No Single Starting Channel Chosen', 'Effort will be spread thin because no one channel has been picked to start with.', 'ECM-002', 'external', 'Strategic', 0.62, 'Stage 0'),
  ('RC-ECM-009', 'Cost of Getting One Visitor Unknown', 'No idea what it costs to bring one person to the store, so budgets are guesses.', 'ECM-002', 'external', 'Knowledge', 0.63, 'Stage 0'),
  ('RC-ECM-010', 'Expecting Word of Mouth Too Early', 'Relying on referrals before a single customer has bought anything.', 'ECM-002', 'external', 'Psychological', 0.60, 'Stage 0'),
  ('RC-ECM-011', 'No Supplier Identified', 'There is no named source for the product yet.', 'ECM-003', 'external', 'Operational', 0.67, 'Stage 0'),
  ('RC-ECM-012', 'Buying Cost Unknown', 'What the product costs to buy has never been confirmed with a supplier.', 'ECM-003', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-ECM-013', 'Restocking Time Unknown', 'No idea how long it takes to get more stock once the first lot sells.', 'ECM-003', 'external', 'Operational', 0.62, 'Stage 0'),
  ('RC-ECM-014', 'Assuming Suppliers Are Interchangeable', 'Believing any supplier can replace another without checking quality or price.', 'ECM-003', 'external', 'Knowledge', 0.59, 'Stage 0'),
  ('RC-ECM-015', 'Delivery Cost Not in the Price', 'Shipping has not been counted in what the customer will be charged.', 'ECM-004', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-ECM-016', 'No Clarity on Who Ships the Order', 'It is unclear whether the founder, a courier or a partner handles delivery.', 'ECM-004', 'external', 'Operational', 0.64, 'Stage 0'),
  ('RC-ECM-017', 'No Rule for Returns', 'Nothing has been decided about what happens when a customer sends something back.', 'ECM-004', 'external', 'Operational', 0.63, 'Stage 0'),
  ('RC-ECM-018', 'Packaging Not Considered', 'No thought given to how the product is packed, protected or presented.', 'ECM-004', 'external', 'Operational', 0.58, 'Stage 0'),
  ('RC-ECM-019', 'Repeat Purchase Rate Never Measured', 'Nobody tracks how many customers buy a second time, so retention is invisible.', 'ECM-005', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-ECM-020', 'Nothing Sent After Delivery', 'The relationship ends at delivery, with no follow up of any kind.', 'ECM-005', 'external', 'Behavioural', 0.67, 'Stage 0→1'),
  ('RC-ECM-021', 'No Reason Given to Come Back', 'Nothing in the product, price or offer gives a customer a reason to return.', 'ECM-005', 'external', 'Strategic', 0.66, 'Stage 0→1'),
  ('RC-ECM-022', 'Growth Depends Entirely on New Buyers', 'Every month starts from zero because no base of returning customers exists.', 'ECM-005', 'external', 'Strategic', 0.68, 'Stage 0→1'),
  ('RC-ECM-023', 'Best Customers Not Identified', 'There is no view of which customers spend most or buy most often.', 'ECM-005', 'external', 'Operational', 0.62, 'Stage 0→1'),
  ('RC-ECM-024', 'Cost Per Order From Ads Unknown', 'How much is spent to win one order has never been calculated.', 'ECM-006', 'external', 'Knowledge', 0.72, 'Stage 0→1'),
  ('RC-ECM-025', 'Profit Per Order Never Compared to Ad Cost', 'The two numbers are never put side by side, so losses stay hidden.', 'ECM-006', 'external', 'Knowledge', 0.70, 'Stage 0→1'),
  ('RC-ECM-026', 'Ad Spend Raised Without Checking Returns', 'More money is pushed into ads without confirming the last increase worked.', 'ECM-006', 'external', 'Behavioural', 0.66, 'Stage 0→1'),
  ('RC-ECM-027', 'Revenue Watched Instead of Profit', 'Growth is judged by sales value while profit quietly falls.', 'ECM-006', 'external', 'Psychological', 0.64, 'Stage 0→1'),
  ('RC-ECM-028', 'No Channel Level Payback View', 'It is unknown which ad channel actually pays for itself.', 'ECM-006', 'external', 'Operational', 0.65, 'Stage 0→1'),
  ('RC-ECM-029', 'Return and RTO Percentage Not Tracked', 'The share of orders that come back or fail delivery is not measured.', 'ECM-007', 'external', 'Operational', 0.71, 'Stage 0→1'),
  ('RC-ECM-030', 'Return Reasons Never Collected', 'Customers are not asked why they returned, so the cause is never fixed.', 'ECM-007', 'external', 'Operational', 0.67, 'Stage 0→1'),
  ('RC-ECM-031', 'Cash on Delivery Failures Treated as Normal', 'Failed deliveries are accepted as a cost of doing business rather than reduced.', 'ECM-007', 'external', 'Behavioural', 0.64, 'Stage 0→1'),
  ('RC-ECM-032', 'Cost of a Failed Delivery Not Calculated', 'Nobody has worked out what one RTO actually costs in shipping and packaging.', 'ECM-007', 'external', 'Knowledge', 0.66, 'Stage 0→1'),
  ('RC-ECM-033', 'No Action on Worst Returning Products', 'Products with the highest return rates keep being sold unchanged.', 'ECM-007', 'external', 'Operational', 0.62, 'Stage 0→1'),
  ('RC-ECM-034', 'Slow Moving Stock Never Identified', 'No one separates what sells from what sits, so dead stock keeps being reordered.', 'ECM-008', 'external', 'Operational', 0.70, 'Stage 0→1'),
  ('RC-ECM-035', 'Best Sellers Regularly Out of Stock', 'The products that actually sell are unavailable when customers want them.', 'ECM-008', 'external', 'Operational', 0.68, 'Stage 0→1'),
  ('RC-ECM-036', 'Reordering Done by Feel', 'Purchase decisions are made on instinct rather than on sell through data.', 'ECM-008', 'external', 'Behavioural', 0.65, 'Stage 0→1'),
  ('RC-ECM-037', 'Cash Locked in Inventory Not Measured', 'How much money is sitting in stock is never put on paper.', 'ECM-008', 'external', 'Knowledge', 0.64, 'Stage 0→1'),
  ('RC-ECM-038', 'Channel Chosen Without Comparing Margins', 'Where to sell was decided before working out what each channel leaves behind.', 'ECM-009', 'external', 'Strategic', 0.69, 'Stage 0→1'),
  ('RC-ECM-039', 'Marketplace Fees Not Counted in Margin', 'Commission, shipping and ad fees on the marketplace are missing from the numbers.', 'ECM-009', 'external', 'Knowledge', 0.67, 'Stage 0→1'),
  ('RC-ECM-040', 'No Plan to Build Direct Customers', 'All customer relationships sit with the marketplace, not with the brand.', 'ECM-009', 'external', 'Strategic', 0.66, 'Stage 0→1'),
  ('RC-ECM-041', 'Pick and Pack Process Not Written Down', 'Each person packs differently because no standard process exists.', 'ECM-010', 'external', 'Operational', 0.71, 'Stage 1→10+'),
  ('RC-ECM-042', 'Order Accuracy Never Measured', 'Nobody tracks how many orders go out wrong, so errors stay invisible.', 'ECM-010', 'external', 'Operational', 0.69, 'Stage 1→10+'),
  ('RC-ECM-043', 'Warehouse Layout Unchanged Since Early Days', 'The space is arranged for a much smaller order volume than today.', 'ECM-010', 'external', 'Operational', 0.65, 'Stage 1→10+'),
  ('RC-ECM-044', 'No Capacity Plan for Peak Season', 'Busy periods are handled by working harder rather than by planning ahead.', 'ECM-010', 'external', 'Strategic', 0.66, 'Stage 1→10+'),
  ('RC-ECM-045', 'Dispatch Delays Treated as Normal', 'Late shipping is accepted instead of being measured and fixed.', 'ECM-010', 'external', 'Behavioural', 0.63, 'Stage 1→10+'),
  ('RC-ECM-046', 'Cost Per Customer Rising Year on Year', 'Acquisition keeps getting more expensive without any offsetting change.', 'ECM-011', 'external', 'Operational', 0.72, 'Stage 1→10+'),
  ('RC-ECM-047', 'Customer Lifetime Value Never Measured', 'What a customer is worth over time has never been calculated.', 'ECM-011', 'external', 'Knowledge', 0.70, 'Stage 1→10+'),
  ('RC-ECM-048', 'Retention Never Improved to Offset Ad Cost', 'No effort goes into repeat buying even as acquisition gets costlier.', 'ECM-011', 'external', 'Strategic', 0.68, 'Stage 1→10+'),
  ('RC-ECM-049', 'Growth Entirely Dependent on Paid Traffic', 'Every order traces back to an ad, with no organic base underneath.', 'ECM-011', 'external', 'Strategic', 0.67, 'Stage 1→10+'),
  ('RC-ECM-050', 'Margins Shrinking as Ad Rates Rise', 'Rising ad rates are absorbed silently instead of being priced or planned for.', 'ECM-011', 'external', 'Operational', 0.64, 'Stage 1→10+'),
  ('RC-ECM-051', 'Sales Collapse When Offers Stop', 'Demand only appears when a discount is running.', 'ECM-012', 'external', 'Strategic', 0.71, 'Stage 1→10+'),
  ('RC-ECM-052', 'Customers Trained to Wait for a Sale', 'Frequent offers have taught buyers never to pay full price.', 'ECM-012', 'external', 'Behavioural', 0.69, 'Stage 1→10+'),
  ('RC-ECM-053', 'Discount Depth Increasing Over Time', 'Each round of offers has to be bigger than the last to work.', 'ECM-012', 'external', 'Behavioural', 0.66, 'Stage 1→10+'),
  ('RC-ECM-054', 'Full Price Selling Never Tested Recently', 'Nobody has checked lately whether the product sells without a discount.', 'ECM-012', 'external', 'Operational', 0.64, 'Stage 1→10+'),
  ('RC-ECM-055', 'Margin Per Order Falling Steadily', 'Profit on each order keeps dropping without anyone acting on it.', 'ECM-012', 'external', 'Operational', 0.65, 'Stage 1→10+'),
  ('RC-ECM-056', 'Product Count Grown Without Review', 'New products keep being added while nothing is ever removed.', 'ECM-013', 'external', 'Behavioural', 0.68, 'Stage 1→10+'),
  ('RC-ECM-057', 'Most Revenue From a Few Products', 'A small share of the catalogue carries nearly all the sales.', 'ECM-013', 'external', 'Operational', 0.67, 'Stage 1→10+'),
  ('RC-ECM-058', 'Long Tail Holding Cash and Space', 'Slow products tie up money and warehouse room for little return.', 'ECM-013', 'external', 'Operational', 0.66, 'Stage 1→10+'),
  ('RC-ECM-059', 'No Process for Retiring a Product', 'There is no rule or moment at which a product is dropped.', 'ECM-013', 'external', 'Operational', 0.63, 'Stage 1→10+'),
  ('RC-ECM-060', 'Team Attention Spread Too Thin', 'Effort is split across too many products to do any of them well.', 'ECM-013', 'external', 'Strategic', 0.62, 'Stage 1→10+'),
  ('RC-ECM-061', 'Majority of Orders From One Source', 'A single platform or channel carries most of the demand.', 'ECM-014', 'external', 'Strategic', 0.74, 'Stage 1→10+'),
  ('RC-ECM-062', 'No Second Channel Built Up', 'Nothing has been developed that could take over if the main one fails.', 'ECM-014', 'external', 'Strategic', 0.70, 'Stage 1→10+'),
  ('RC-ECM-063', 'No Plan If the Platform Changes Rules', 'A policy change, suspension or algorithm shift has no prepared response.', 'ECM-014', 'external', 'Strategic', 0.68, 'Stage 1→10+'),
  ('RC-ECM-064', 'Pricing Dictated by the Platform', 'Promotions and price points are set by the channel rather than the brand.', 'ECM-014', 'external', 'Operational', 0.64, 'Stage 1→10+'),
  ('RC-ECM-065', 'No Own Customer Contact List', 'The brand holds no list it can reach out to on its own.', 'ECM-015', 'external', 'Operational', 0.70, 'Stage 1→10+'),
  ('RC-ECM-066', 'Repeat Selling Requires Paying the Platform Again', 'Reaching a past customer means buying the same traffic a second time.', 'ECM-015', 'external', 'Strategic', 0.67, 'Stage 1→10+')
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
         '["ecommerce_d2c"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-ECM-001', 'Do you know if people are already searching online for a product like yours?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-001', 'RC-ECM-001', 1, 'Stage 0'),
  ('S0-ECM-002', 'Do you believe a good product will sell on its own, or does it need pushing?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-001', 'RC-ECM-002', 1, 'Stage 0'),
  ('S0-ECM-003', 'What do similar products already sell for online right now?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-001', 'RC-ECM-003', 1, 'Stage 0'),
  ('S0-ECM-004', 'Did you see this idea working somewhere else? Have you checked if people here want it too?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-001', 'RC-ECM-004', 2, 'Stage 0'),
  ('S0-ECM-005', 'Has anyone apart from you said they would actually buy this?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-001', 'RC-ECM-005', 1, 'Stage 0'),
  ('S0-ECM-006', 'If your store went live today, how would the very first stranger find it?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-002', 'RC-ECM-006', 1, 'Stage 0'),
  ('S0-ECM-007', 'Do you think having a website means people will visit it?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-002', 'RC-ECM-007', 1, 'Stage 0'),
  ('S0-ECM-008', 'Which one place will you use to reach customers first, and why that one?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-002', 'RC-ECM-008', 2, 'Stage 0'),
  ('S0-ECM-009', 'Do you have any idea what it costs to get one person to visit your store?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-002', 'RC-ECM-009', 2, 'Stage 0'),
  ('S0-ECM-010', 'Are you counting on people telling their friends before anyone has bought yet?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-002', 'RC-ECM-010', 2, 'Stage 0'),
  ('S0-ECM-011', 'Where would you actually get your product from?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-003', 'RC-ECM-011', 1, 'Stage 0'),
  ('S0-ECM-012', 'Do you know what one piece would cost you to buy?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-003', 'RC-ECM-012', 1, 'Stage 0'),
  ('S0-ECM-013', 'If your product sells well, how quickly could you get more of it?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-003', 'RC-ECM-013', 2, 'Stage 0'),
  ('S0-ECM-014', 'How would the product reach the customer, and who pays for that?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-004', 'RC-ECM-015', 1, 'Stage 0'),
  ('S0-ECM-015', 'What happens if a customer wants to return the product?', 'open_text', 'Idea & Validation', 'CORE', 'ECM-004', 'RC-ECM-017', 1, 'Stage 0'),
  ('S01-ECM-001', 'Out of your last 100 orders, how many were from people who had bought before?', 'open_text', 'Sales & Revenue', 'CORE', 'ECM-005', 'RC-ECM-019', 2, 'Stage 0→1'),
  ('S01-ECM-002', 'Does a customer hear anything from you after the parcel is delivered?', 'open_text', 'Sales & Revenue', 'CORE', 'ECM-005', 'RC-ECM-020', 2, 'Stage 0→1'),
  ('S01-ECM-003', 'What reason does a customer have to buy from you a second time?', 'open_text', 'Sales & Revenue', 'CORE', 'ECM-005', 'RC-ECM-021', 2, 'Stage 0→1'),
  ('S01-ECM-004', 'If you stopped all ads this month, how many orders would still come in?', 'open_text', 'Sales & Revenue', 'CORE', 'ECM-005', 'RC-ECM-022', 3, 'Stage 0→1'),
  ('S01-ECM-005', 'Can you name your top 10 customers by how much they have spent?', 'open_text', 'Sales & Revenue', 'CORE', 'ECM-005', 'RC-ECM-023', 2, 'Stage 0→1'),
  ('S01-ECM-006', 'Do you know what it costs you in ads to get one order?', 'open_text', 'Financial Management', 'CORE', 'ECM-006', 'RC-ECM-024', 2, 'Stage 0→1'),
  ('S01-ECM-007', 'After you take out ad cost, how much profit is left on one order?', 'open_text', 'Financial Management', 'CORE', 'ECM-006', 'RC-ECM-025', 2, 'Stage 0→1'),
  ('S01-ECM-008', 'The last time you increased ad spend, did you check whether it actually worked?', 'open_text', 'Financial Management', 'CORE', 'ECM-006', 'RC-ECM-026', 2, 'Stage 0→1'),
  ('S01-ECM-009', 'Do you watch your sales number or your profit number more closely?', 'open_text', 'Financial Management', 'CORE', 'ECM-006', 'RC-ECM-027', 2, 'Stage 0→1'),
  ('S01-ECM-010', 'Which of your ad channels actually pays for itself, and which does not?', 'open_text', 'Financial Management', 'CORE', 'ECM-006', 'RC-ECM-028', 3, 'Stage 0→1'),
  ('S01-ECM-011', 'What percentage of your orders come back as returns or failed deliveries?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-007', 'RC-ECM-029', 2, 'Stage 0→1'),
  ('S01-ECM-012', 'Do you ask customers why they returned something?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-007', 'RC-ECM-030', 2, 'Stage 0→1'),
  ('S01-ECM-013', 'How many of your cash on delivery orders fail, and what do you do about it?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-007', 'RC-ECM-031', 2, 'Stage 0→1'),
  ('S01-ECM-014', 'What does one failed delivery actually cost you in shipping and packing?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-007', 'RC-ECM-032', 3, 'Stage 0→1'),
  ('S01-ECM-015', 'Which product gets returned the most, and has anything changed about it?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-007', 'RC-ECM-033', 2, 'Stage 0→1'),
  ('S01-ECM-016', 'Which of your products are sitting unsold, and how much money is stuck in them?', 'open_text', 'Financial Management', 'CORE', 'ECM-008', 'RC-ECM-034', 2, 'Stage 0→1'),
  ('S01-ECM-017', 'How often does your best selling product go out of stock?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-008', 'RC-ECM-035', 2, 'Stage 0→1'),
  ('S01-ECM-018', 'When you reorder stock, is it based on actual sales numbers or on a feeling?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-008', 'RC-ECM-036', 2, 'Stage 0→1'),
  ('S01-ECM-019', 'Did you choose to sell where you sell, or did it just happen that way?', 'open_text', 'Strategy & Planning', 'CORE', 'ECM-009', 'RC-ECM-038', 2, 'Stage 0→1'),
  ('S01-ECM-020', 'After marketplace commission and fees, how much is actually left per order?', 'open_text', 'Financial Management', 'CORE', 'ECM-009', 'RC-ECM-039', 3, 'Stage 0→1'),
  ('S10-ECM-001', 'Is your packing process written down, or does everyone do it their own way?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-010', 'RC-ECM-041', 2, 'Stage 1→10+'),
  ('S10-ECM-002', 'How many orders go out wrong or late in a normal week?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-010', 'RC-ECM-042', 2, 'Stage 1→10+'),
  ('S10-ECM-003', 'Has your warehouse layout changed since your order volume grew?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-010', 'RC-ECM-043', 2, 'Stage 1→10+'),
  ('S10-ECM-004', 'What is your plan for handling your busiest season this year?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-010', 'RC-ECM-044', 3, 'Stage 1→10+'),
  ('S10-ECM-005', 'Are dispatch delays something you measure, or something you have got used to?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-010', 'RC-ECM-045', 2, 'Stage 1→10+'),
  ('S10-ECM-006', 'Has your cost of getting a customer gone up over the last year? By how much?', 'open_text', 'Sales & Revenue', 'CORE', 'ECM-011', 'RC-ECM-046', 2, 'Stage 1→10+'),
  ('S10-ECM-007', 'Do you know what a customer is worth to you over their whole lifetime?', 'open_text', 'Sales & Revenue', 'CORE', 'ECM-011', 'RC-ECM-047', 3, 'Stage 1→10+'),
  ('S10-ECM-008', 'As ads got more expensive, what did you change to keep customers coming back?', 'open_text', 'Sales & Revenue', 'CORE', 'ECM-011', 'RC-ECM-048', 3, 'Stage 1→10+'),
  ('S10-ECM-009', 'What share of your orders comes from people who found you without an ad?', 'open_text', 'Sales & Revenue', 'CORE', 'ECM-011', 'RC-ECM-049', 2, 'Stage 1→10+'),
  ('S10-ECM-010', 'Has your profit per order gone down as ad rates went up?', 'open_text', 'Financial Management', 'CORE', 'ECM-011', 'RC-ECM-050', 2, 'Stage 1→10+'),
  ('S10-ECM-011', 'What happens to your sales in a week when you run no offer at all?', 'open_text', 'Sales & Revenue', 'CORE', 'ECM-012', 'RC-ECM-051', 2, 'Stage 1→10+'),
  ('S10-ECM-012', 'Do your customers buy when they need something, or when you run a sale?', 'open_text', 'Sales & Revenue', 'CORE', 'ECM-012', 'RC-ECM-052', 2, 'Stage 1→10+'),
  ('S10-ECM-013', 'Are your discounts bigger now than they were a year ago?', 'open_text', 'Sales & Revenue', 'CORE', 'ECM-012', 'RC-ECM-053', 2, 'Stage 1→10+'),
  ('S10-ECM-014', 'When did you last sell well without running any offer?', 'open_text', 'Sales & Revenue', 'CORE', 'ECM-012', 'RC-ECM-054', 2, 'Stage 1→10+'),
  ('S10-ECM-015', 'Is your profit per order today higher or lower than last year?', 'open_text', 'Financial Management', 'CORE', 'ECM-012', 'RC-ECM-055', 3, 'Stage 1→10+'),
  ('S10-ECM-016', 'How many products do you sell today, and how many did you sell two years ago?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-013', 'RC-ECM-056', 2, 'Stage 1→10+'),
  ('S10-ECM-017', 'How many of your products make up most of your revenue?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-013', 'RC-ECM-057', 2, 'Stage 1→10+'),
  ('S10-ECM-018', 'How much cash and space is taken up by products that barely sell?', 'open_text', 'Financial Management', 'CORE', 'ECM-013', 'RC-ECM-058', 3, 'Stage 1→10+'),
  ('S10-ECM-019', 'Do you have any rule for when a product gets dropped?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-013', 'RC-ECM-059', 2, 'Stage 1→10+'),
  ('S10-ECM-020', 'Does your team have enough time to do justice to every product you carry?', 'open_text', 'Operations & Systems', 'CORE', 'ECM-013', 'RC-ECM-060', 2, 'Stage 1→10+'),
  ('S10-ECM-021', 'What share of your orders comes from your single biggest channel?', 'open_text', 'Strategy & Planning', 'CORE', 'ECM-014', 'RC-ECM-061', 2, 'Stage 1→10+'),
  ('S10-ECM-022', 'If your main platform or ad account was blocked tomorrow, what happens?', 'open_text', 'Strategy & Planning', 'CORE', 'ECM-014', 'RC-ECM-062', 3, 'Stage 1→10+'),
  ('S10-ECM-023', 'Do you have any written plan for a sudden platform rule change?', 'open_text', 'Strategy & Planning', 'CORE', 'ECM-014', 'RC-ECM-063', 3, 'Stage 1→10+'),
  ('S10-ECM-024', 'Who decides your pricing and promotions, you or the platform?', 'open_text', 'Strategy & Planning', 'CORE', 'ECM-014', 'RC-ECM-064', 2, 'Stage 1→10+'),
  ('S10-ECM-025', 'Can you contact your past customers directly, without paying a platform?', 'open_text', 'Strategy & Planning', 'CORE', 'ECM-015', 'RC-ECM-065', 2, 'Stage 1→10+')
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
  ('S0-ECM-001', 'problem-clarity'),
  ('S0-ECM-002', 'problem-clarity'),
  ('S0-ECM-003', 'problem-clarity'),
  ('S0-ECM-004', 'problem-clarity'),
  ('S0-ECM-005', 'problem-clarity'),
  ('S0-ECM-006', 'channel-strategy'),
  ('S0-ECM-007', 'channel-strategy'),
  ('S0-ECM-008', 'channel-strategy'),
  ('S0-ECM-009', 'channel-strategy'),
  ('S0-ECM-010', 'channel-strategy'),
  ('S0-ECM-011', 'customer-discovery'),
  ('S0-ECM-012', 'customer-discovery'),
  ('S0-ECM-013', 'customer-discovery'),
  ('S0-ECM-014', 'customer-discovery'),
  ('S0-ECM-015', 'customer-discovery'),
  ('S01-ECM-001', 'customer-discovery'),
  ('S01-ECM-002', 'customer-discovery'),
  ('S01-ECM-003', 'customer-discovery'),
  ('S01-ECM-004', 'customer-discovery'),
  ('S01-ECM-005', 'customer-discovery'),
  ('S01-ECM-006', 'willingness-to-pay'),
  ('S01-ECM-007', 'willingness-to-pay'),
  ('S01-ECM-008', 'willingness-to-pay'),
  ('S01-ECM-009', 'willingness-to-pay'),
  ('S01-ECM-010', 'willingness-to-pay'),
  ('S01-ECM-011', 'technical-quality'),
  ('S01-ECM-012', 'technical-quality'),
  ('S01-ECM-013', 'technical-quality'),
  ('S01-ECM-014', 'technical-quality'),
  ('S01-ECM-015', 'technical-quality'),
  ('S01-ECM-016', 'willingness-to-pay'),
  ('S01-ECM-017', 'willingness-to-pay'),
  ('S01-ECM-018', 'willingness-to-pay'),
  ('S01-ECM-019', 'channel-strategy'),
  ('S01-ECM-020', 'channel-strategy'),
  ('S10-ECM-001', 'technical-quality'),
  ('S10-ECM-002', 'technical-quality'),
  ('S10-ECM-003', 'technical-quality'),
  ('S10-ECM-004', 'technical-quality'),
  ('S10-ECM-005', 'technical-quality'),
  ('S10-ECM-006', 'willingness-to-pay'),
  ('S10-ECM-007', 'willingness-to-pay'),
  ('S10-ECM-008', 'willingness-to-pay'),
  ('S10-ECM-009', 'willingness-to-pay'),
  ('S10-ECM-010', 'willingness-to-pay'),
  ('S10-ECM-011', 'willingness-to-pay'),
  ('S10-ECM-012', 'willingness-to-pay'),
  ('S10-ECM-013', 'willingness-to-pay'),
  ('S10-ECM-014', 'willingness-to-pay'),
  ('S10-ECM-015', 'willingness-to-pay'),
  ('S10-ECM-016', 'technical-quality'),
  ('S10-ECM-017', 'technical-quality'),
  ('S10-ECM-018', 'technical-quality'),
  ('S10-ECM-019', 'technical-quality'),
  ('S10-ECM-020', 'technical-quality'),
  ('S10-ECM-021', 'channel-strategy'),
  ('S10-ECM-022', 'channel-strategy'),
  ('S10-ECM-023', 'channel-strategy'),
  ('S10-ECM-024', 'channel-strategy'),
  ('S10-ECM-025', 'channel-strategy')
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
         '["ecommerce_d2c"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-ECM-001', 'Ideation — E-commerce Demand Basics', 'ECM-001', '["RC-ECM-001", "RC-ECM-003"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Search online for the product you want to sell.", "Note how many sellers already come up and what they charge.", "Write down where your price would sit among them."]'::jsonb, '[{"name": "Online Demand Scan", "brief": "Checking what already sells online and at what price before committing."}]'::jsonb),
  ('INT-ECM-002', 'Ideation — E-commerce Demand Basics', 'ECM-001', '["RC-ECM-002", "RC-ECM-005"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Show your product idea to 10 people who are not friends or family.", "Ask if they would pay for it, and at what price.", "Count how many say yes without being persuaded."]'::jsonb, '[{"name": "Ten Stranger Test", "brief": "Getting buying intent from people with no personal connection to the founder."}]'::jsonb),
  ('INT-ECM-003', 'Ideation — E-commerce Demand Basics', 'ECM-001', '["RC-ECM-004"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Write down where you first saw this idea working.", "Check whether the same customers and conditions exist here.", "Note one thing that is clearly different in your market."]'::jsonb, '[{"name": "Local Demand Check", "brief": "Testing whether an idea copied from elsewhere fits the local market."}]'::jsonb),
  ('INT-ECM-004', 'Ideation — E-commerce Customer Reach', 'ECM-002', '["RC-ECM-006", "RC-ECM-007"]'::jsonb, '[1]'::jsonb, 'Customer Acquisition', '["Write down exactly how your first 10 customers will find you.", "Be specific, name the place, not just online.", "If you cannot write it, you do not have a plan yet."]'::jsonb, '[{"name": "First Ten Customers Plan", "brief": "Naming the exact route the first buyers will come through."}]'::jsonb),
  ('INT-ECM-005', 'Ideation — E-commerce Customer Reach', 'ECM-002', '["RC-ECM-008", "RC-ECM-010"]'::jsonb, '[1]'::jsonb, 'Customer Acquisition', '["Pick one channel to start with and ignore the rest for now.", "Write down why that one suits your customer.", "Set a small budget and a date to review it."]'::jsonb, '[{"name": "One Channel First", "brief": "Concentrating early effort on a single reach channel instead of spreading thin."}]'::jsonb),
  ('INT-ECM-006', 'Ideation — E-commerce Customer Reach', 'ECM-002', '["RC-ECM-009"]'::jsonb, '[1]'::jsonb, 'Customer Acquisition', '["Find out roughly what one visitor costs on your chosen channel.", "Work out how many visitors you need for one sale.", "Check whether your price can cover that."]'::jsonb, '[{"name": "Cost Per Visitor Basics", "brief": "Understanding what traffic costs before planning on it."}]'::jsonb),
  ('INT-ECM-007', 'Ideation — E-commerce Sourcing Basics', 'ECM-003', '["RC-ECM-011", "RC-ECM-012"]'::jsonb, '[1]'::jsonb, 'Supply Chain', '["Find one real supplier for your product.", "Ask them the price for a small first quantity.", "Write that cost down before you fix your selling price."]'::jsonb, '[{"name": "One Real Supplier", "brief": "Getting a real buying price from an actual supplier, not an estimate."}]'::jsonb),
  ('INT-ECM-008', 'Ideation — E-commerce Sourcing Basics', 'ECM-003', '["RC-ECM-013", "RC-ECM-014"]'::jsonb, '[1]'::jsonb, 'Supply Chain', '["Ask your supplier how long a repeat order takes.", "Find a second supplier who could step in.", "Note any difference in price or quality between the two."]'::jsonb, '[{"name": "Restock and Backup Check", "brief": "Knowing repeat order times and having a second source before selling."}]'::jsonb),
  ('INT-ECM-009', 'Ideation — E-commerce Fulfilment Basics', 'ECM-004', '["RC-ECM-015", "RC-ECM-016"]'::jsonb, '[1]'::jsonb, 'Operations', '["Get a delivery price for one order to a nearby city.", "Decide whether the customer or you pays for it.", "Add that number into your price before you launch."]'::jsonb, '[{"name": "Delivery Cost In The Price", "brief": "Counting real shipping cost per order before setting a selling price."}]'::jsonb),
  ('INT-ECM-010', 'Ideation — E-commerce Fulfilment Basics', 'ECM-004', '["RC-ECM-017", "RC-ECM-018"]'::jsonb, '[1]'::jsonb, 'Operations', '["Write your return rule in one line a customer can understand.", "Decide who pays return shipping.", "Pick packaging that survives the journey and write down its cost."]'::jsonb, '[{"name": "Simple Return Rule", "brief": "A one line returns policy and a packaging decision made before launch."}]'::jsonb),
  ('INT-ECM-011', 'Validation to Traction — E-commerce Repeat Purchase', 'ECM-005', '["RC-ECM-019", "RC-ECM-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Customer Retention', '["Take your last 90 days of orders and count how many customers bought twice.", "Write that number as a percentage.", "List your top 10 customers by total spend."]'::jsonb, '[{"name": "Repeat Rate Baseline", "brief": "Measuring what share of customers buy a second time before trying to improve it."}]'::jsonb),
  ('INT-ECM-012', 'Validation to Traction — E-commerce Repeat Purchase', 'ECM-005', '["RC-ECM-020", "RC-ECM-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Customer Retention', '["Send one message to every customer a week after delivery.", "Ask one question and give one clear reason to buy again.", "Track how many come back over the next month."]'::jsonb, '[{"name": "Post Delivery Follow Up", "brief": "A single planned message after delivery to reopen the customer relationship."}]'::jsonb),
  ('INT-ECM-013', 'Validation to Traction — E-commerce Repeat Purchase', 'ECM-005', '["RC-ECM-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Customer Retention', '["Work out how many orders would come in with no ads running.", "Set a target for that number to grow each month.", "Review it before increasing ad spend again."]'::jsonb, '[{"name": "Organic Order Floor", "brief": "Knowing how much of the business survives without paid acquisition."}]'::jsonb),
  ('INT-ECM-014', 'Validation to Traction — E-commerce Acquisition Economics', 'ECM-006', '["RC-ECM-024", "RC-ECM-025"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Divide last month ad spend by the number of orders it brought.", "Put that number next to your profit per order.", "If ad cost is higher, stop scaling until it is fixed."]'::jsonb, '[{"name": "Cost Per Order vs Profit", "brief": "Putting acquisition cost and order profit side by side before spending more."}]'::jsonb),
  ('INT-ECM-015', 'Validation to Traction — E-commerce Acquisition Economics', 'ECM-006', '["RC-ECM-026", "RC-ECM-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Split ad spend and orders by channel.", "Mark which channels pay back and which do not.", "Cut or fix the ones that do not before raising budget."]'::jsonb, '[{"name": "Channel Payback Split", "brief": "Judging each ad channel on whether it actually returns its own cost."}]'::jsonb),
  ('INT-ECM-016', 'Validation to Traction — E-commerce Acquisition Economics', 'ECM-006', '["RC-ECM-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Put monthly profit next to monthly revenue on one line.", "Track both every month, not just revenue.", "Decide on profit, not on sales value."]'::jsonb, '[{"name": "Profit Beside Revenue", "brief": "Reviewing profit alongside sales so growth does not hide losses."}]'::jsonb),
  ('INT-ECM-017', 'Validation to Traction — E-commerce Returns and RTO', 'ECM-007', '["RC-ECM-029", "RC-ECM-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Count returns and failed deliveries as a percentage of orders each week.", "Work out what one failed delivery costs you.", "Multiply the two to see the real monthly loss."]'::jsonb, '[{"name": "Return and RTO Baseline", "brief": "Measuring failed orders as a weekly percentage and a real rupee cost."}]'::jsonb),
  ('INT-ECM-018', 'Validation to Traction — E-commerce Returns and RTO', 'ECM-007', '["RC-ECM-030", "RC-ECM-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Ask every returning customer one question about why.", "Group the answers after 20 returns.", "Fix the top reason on your worst returning product first."]'::jsonb, '[{"name": "Return Reason Capture", "brief": "Collecting why customers return so the cause can be fixed at source."}]'::jsonb),
  ('INT-ECM-019', 'Validation to Traction — E-commerce Returns and RTO', 'ECM-007', '["RC-ECM-031"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Look at how many cash on delivery orders fail.", "Try one change, such as confirming the order before dispatch.", "Compare the failure rate before and after."]'::jsonb, '[{"name": "Cash on Delivery Confirmation", "brief": "One simple step before dispatch to cut failed cash on delivery orders."}]'::jsonb),
  ('INT-ECM-020', 'Validation to Traction — E-commerce Inventory Health', 'ECM-008', '["RC-ECM-034", "RC-ECM-037"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["List every product with how many units sold in the last 60 days.", "Mark anything that barely moved as slow stock.", "Write down how much cash is sitting in that slow stock."]'::jsonb, '[{"name": "Fast and Dead Stock Split", "brief": "Separating what sells from what sits, and the cash trapped in each."}]'::jsonb),
  ('INT-ECM-021', 'Validation to Traction — E-commerce Inventory Health', 'ECM-008', '["RC-ECM-035", "RC-ECM-036"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Set a reorder point for your top sellers based on real sell through.", "Stop reordering anything on your slow list.", "Clear slow stock with a discount to free the cash."]'::jsonb, '[{"name": "Reorder on Sell Through", "brief": "Ordering stock from actual sales data instead of instinct."}]'::jsonb),
  ('INT-ECM-022', 'Validation to Traction — E-commerce Channel Strategy', 'ECM-009', '["RC-ECM-038", "RC-ECM-039", "RC-ECM-040"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Work out profit per order on the marketplace and on your own store.", "Include commission, shipping, returns and ad cost in both.", "Decide where you push next based on that number, and start collecting your own customer list."]'::jsonb, '[{"name": "Channel Margin Comparison", "brief": "Comparing true profit per order across channels before choosing where to grow."}]'::jsonb),
  ('INT-ECM-023', 'Growth to Maturity — E-commerce Fulfilment at Scale', 'ECM-010', '["RC-ECM-041", "RC-ECM-042"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write your pick and pack steps on one page.", "Start recording how many orders go out wrong each week.", "Review the number every Monday and fix the top cause."]'::jsonb, '[{"name": "Pack Process and Accuracy", "brief": "A written packing standard plus a weekly order accuracy number."}]'::jsonb),
  ('INT-ECM-024', 'Growth to Maturity — E-commerce Fulfilment at Scale', 'ECM-010', '["RC-ECM-043", "RC-ECM-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Move your fastest selling items closest to the packing table.", "Measure how long an order takes from placed to dispatched.", "Set a dispatch time you will not cross."]'::jsonb, '[{"name": "Layout and Dispatch Time", "brief": "Rearranging for todays volume and holding a promised dispatch time."}]'::jsonb),
  ('INT-ECM-025', 'Growth to Maturity — E-commerce Fulfilment at Scale', 'ECM-010', '["RC-ECM-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Look at last years peak week order count.", "Work out the people, space and stock needed for that again.", "Arrange it a month before the season starts."]'::jsonb, '[{"name": "Peak Season Capacity Plan", "brief": "Planning people, space and stock ahead of the busiest weeks."}]'::jsonb),
  ('INT-ECM-026', 'Growth to Maturity — E-commerce Acquisition Pressure', 'ECM-011', '["RC-ECM-046", "RC-ECM-047"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Compare this years cost per customer with last years.", "Work out what an average customer spends with you over a year.", "Check whether the second number is comfortably bigger than the first."]'::jsonb, '[{"name": "Acquisition Cost vs Customer Value", "brief": "Comparing what a customer costs to win against what they are worth over time."}]'::jsonb),
  ('INT-ECM-027', 'Growth to Maturity — E-commerce Acquisition Pressure', 'ECM-011', '["RC-ECM-048", "RC-ECM-049"]'::jsonb, '[5, 6, 7]'::jsonb, 'Customer Retention', '["Pick one retention action and run it for 90 days.", "Track repeat purchase rate before and after.", "Set a target for organic orders to grow each quarter."]'::jsonb, '[{"name": "Retention as the Answer to Rising Ads", "brief": "Improving repeat buying so the business is less exposed to ad rates."}]'::jsonb),
  ('INT-ECM-028', 'Growth to Maturity — E-commerce Pricing Discipline', 'ECM-012', '["RC-ECM-051", "RC-ECM-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Run one full week with no discount at all.", "Record what happens to orders and to profit.", "Use that number to decide how much discounting you actually need."]'::jsonb, '[{"name": "Full Price Week Test", "brief": "Testing real demand without any offer running."}]'::jsonb),
  ('INT-ECM-029', 'Growth to Maturity — E-commerce Pricing Discipline', 'ECM-012', '["RC-ECM-052", "RC-ECM-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["List every offer run in the last six months and its depth.", "Set a maximum discount you will not go past.", "Space offers further apart so buying stops depending on them."]'::jsonb, '[{"name": "Discount Ceiling and Spacing", "brief": "Capping discount depth and frequency so customers stop waiting for sales."}]'::jsonb),
  ('INT-ECM-030', 'Growth to Maturity — E-commerce Pricing Discipline', 'ECM-012', '["RC-ECM-055"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Track profit per order month by month for the last year.", "Mark the months where it dropped and what you were running then.", "Decide one change to stop the slide."]'::jsonb, '[{"name": "Margin Trend Watch", "brief": "Following profit per order over time instead of only sales value."}]'::jsonb),
  ('INT-ECM-031', 'Growth to Maturity — E-commerce Assortment Control', 'ECM-013', '["RC-ECM-056", "RC-ECM-057", "RC-ECM-058"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["List every product with its revenue for the last six months.", "Mark the bottom 20 percent by sales.", "Stop reordering them and clear what is left."]'::jsonb, '[{"name": "Bottom Twenty Percent Cut", "brief": "Removing the weakest products to free cash, space and attention."}]'::jsonb),
  ('INT-ECM-032', 'Growth to Maturity — E-commerce Assortment Control', 'ECM-013', '["RC-ECM-059", "RC-ECM-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write one rule for when a product gets dropped.", "Review the full product list against it every quarter.", "Keep the list small enough for the team to handle well."]'::jsonb, '[{"name": "Product Retirement Rule", "brief": "A standing rule for removing products so the range does not keep growing."}]'::jsonb),
  ('INT-ECM-033', 'Growth to Maturity — E-commerce Channel Risk', 'ECM-014', '["RC-ECM-061", "RC-ECM-062", "RC-ECM-063", "RC-ECM-064"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Work out what share of orders comes from your biggest channel.", "Pick one second channel and grow it deliberately this quarter.", "Write a one page plan for what you do if the main channel stops."]'::jsonb, '[{"name": "Second Channel Before You Need It", "brief": "Reducing single platform dependence while there is still time."}]'::jsonb),
  ('INT-ECM-034', 'Growth to Maturity — E-commerce Customer Ownership', 'ECM-015', '["RC-ECM-065", "RC-ECM-066"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Start collecting customer contact details with consent on every order.", "Build one list you own outright.", "Send something useful to that list once a month and track what it earns."]'::jsonb, '[{"name": "Own Your Customer List", "brief": "Building a direct, consented customer list the brand controls itself."}]'::jsonb)
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
        "Migration c8b20d3e5f71 is intentionally irreversible. "
        "Roll back application code without deleting production seed history."
    )
