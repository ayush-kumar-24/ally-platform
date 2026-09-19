"""seed twelve industry diagnostic datasets

Revision ID: 91c4f0a2bd73
Revises: 62ebd946ebc0
Create Date: 2026-09-19

Adds the compatibility industry_relevance columns required by the supplied
industry seed files, creates twelve industry master rows, inserts the twelve
complete industry datasets, and maps every new industry-specific question into
question_industry_mapping so none of these questions are treated as universal.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "91c4f0a2bd73"
down_revision: Union[str, Sequence[str], None] = "62ebd946ebc0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Compatibility fields required by the supplied seeds.
    for table_name in ("problems", "root_causes", "questions"):
        bind.exec_driver_sql(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN IF NOT EXISTS industry_relevance jsonb
            DEFAULT '["all"]'::jsonb
            """
        )
        bind.exec_driver_sql(
            f"""
            UPDATE {table_name}
            SET industry_relevance = '["all"]'::jsonb
            WHERE industry_relevance IS NULL
            """
        )

    # Keep the industries SERIAL sequence aligned with existing production rows.
    # Some legacy industry rows were loaded with explicit primary-key values.
    bind.exec_driver_sql(
        """
        SELECT setval(
            pg_get_serial_sequence('industries', 'industry_id'),
            COALESCE((SELECT MAX(industry_id) FROM industries), 1),
            EXISTS (SELECT 1 FROM industries)
        )
        """
    )

    industry_rows = [
        ('agritech', 'Agriculture & AgriTech', 'Agriculture, farm inputs, farmer services, agri marketplaces, precision farming, agri-fintech, cold-chain and post-harvest businesses.'),
        ('automotive', 'Automotive & Mobility', 'Vehicle, EV, mobility, fleet, automotive component and aftermarket businesses.'),
        ('fintech', 'BFSI / FinTech', 'Banking, payments, lending, insurance, wealth, embedded-finance and other regulated financial-technology businesses.'),
        ('beauty_personal_care', 'Beauty & Personal Care', 'Cosmetics, skincare, haircare, grooming, salon, wellness and personal-care businesses.'),
        ('proptech', 'Construction & Real Estate / PropTech', 'Real-estate, construction, property marketplace, property-management and related built-environment businesses.'),
        ('consumer_electronics', 'Consumer Electronics', 'Consumer hardware, electronics, IoT, wearables, smart-home devices and electronics manufacturing businesses.'),
        ('edtech', 'Education & EdTech', 'Education, training, tutoring, learning platforms, cohort courses, institutional learning and education-technology businesses.'),
        ('cleantech_energy', 'Energy, CleanTech & Renewables', 'Renewable energy, solar, storage, energy efficiency, clean mobility infrastructure, climate-tech and distributed energy businesses.'),
        ('media_entertainment', 'Entertainment & Media', 'Film, television, streaming, music, creator, publishing, digital-media and entertainment businesses.'),
        ('fashion_apparel', 'Fashion & Apparel', 'Fashion, apparel, footwear, accessories, textile, garment, retail and fashion-commerce businesses.'),
        ('foodtech', 'Food & Beverage / FoodTech', 'Food brands, restaurants, cloud kitchens, packaged food, beverages, food delivery, processing and food-technology businesses.'),
        ('gaming', 'Gaming', 'Game studios, mobile and PC games, live-service games, gaming platforms, esports and interactive-entertainment businesses.'),
    ]

    for industry_code, industry_name, description in industry_rows:
        bind.execute(
            text(
                """
                INSERT INTO industries (
                    industry_code,
                    industry_name,
                    description,
                    industry_subtitle
                )
                VALUES (
                    :industry_code,
                    :industry_name,
                    :description,
                    :industry_subtitle
                )
                ON CONFLICT (industry_code) DO NOTHING
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
        ('Agriculture & AgriTech', 'agritech', 'AGR', r"""WITH new_problems AS (
  INSERT INTO problems (problem_code, problem_name, category, subcategory, layer, description, severity_min, severity_max, symptoms, pillar_id, industry_relevance, embedding, embedding_model, embedding_version, embedding_dimension)
  SELECT v.problem_code, v.problem_name, v.category, v.subcategory, v.layer, v.description, v.severity_min, v.severity_max, v.symptoms, v.pillar_id, '["agritech"]'::jsonb, array_fill(0, ARRAY[1536])::vector, NULL, NULL, NULL
  FROM (VALUES
('AGR-001', 'Farmer Adoption Speed Misjudged', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'Founders new to agriculture often assume farmers will adopt a new product or service at the same speed as an app user, without accounting for how much real financial risk a bad outcome represents for a farmer.', 4, 8, '["No direct farmer conversations have happened yet, only assumptions", "Adoption timeline is borrowed from consumer app behaviour, not farming behaviour", "No plan accounts for the cost of a bad outcome for the farmer", "Early-adopter vs cautious-farmer segments have not been identified", "No real estimate of how long trust-building takes in this community"]'::jsonb, 2),
('AGR-002', 'Unclear Farmer, Crop or Region Focus', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'The business idea is still framed as being "for farmers" broadly, without a specific crop, region, or farmer type chosen to build deep understanding around first.', 3, 7, '["Trying to solve for all farmers instead of one clear group", "No specific crop or region has been chosen to start with", "Narrowing the focus is being avoided because it feels risky", "No clear reason has been given for why this particular farmer segment was chosen"]'::jsonb, 2),
('AGR-003', 'Seasonal Dependency Not Thought Through', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'The business plan does not yet account for the fact that farm income and activity arrive in short, harvest-linked bursts rather than spread evenly across the year.', 4, 8, '["Business plan assumes steady activity all year", "No plan exists for the off-season between harvests", "Cash flow model does not reflect harvest-linked income bursts", "Busy versus quiet months for the target crop or region have not been mapped", "The idea does not distinguish between different crop cycles, such as kharif versus rabi"]'::jsonb, 2),
('AGR-004', 'Land or Farmer Data Reliability Ignored', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'The idea depends on knowing things like land size or ownership, but the founder has not checked how unreliable this kind of data typically is in Indian farming contexts.', 3, 7, '["Idea depends on land size or ownership data without checking its accuracy", "No plan exists for verifying farmer-reported information", "Assuming formal land records exist when informal or tenant farming is common", "No fallback plan exists if key data turns out to be wrong or missing"]'::jsonb, 2),
('AGR-005', 'Pilot Results Do Not Reflect Real Paying Behaviour', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'Farmers used the product for free or at a discount during testing, which does not confirm they will pay full price once that support is removed.', 4, 8, '["No paying pilot has been run yet", "Free or discounted users are being treated as validated customers", "No plan exists to test at full price", "Early users may not represent the real target farmer segment", "No repeat-usage data has been collected"]'::jsonb, 2),
('AGR-006', 'Distribution Reality Not Tested', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'The founder has not actually proven how the product physically reaches farmers, through dealers, field agents, or cooperatives.', 4, 8, '["No real distribution partner has been tested yet", "Assuming digital-only reach without a physical delivery plan", "Field agent or dealer costs have not been accounted for", "No test exists of how long it takes to reach a new village or area"]'::jsonb, 2),
('AGR-007', 'Pricing Does Not Match Farmer Cash Flow', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'Pricing assumes farmers can pay upfront, when their available cash is usually tied to harvest payout timing.', 4, 8, '["Pricing is designed around monthly billing, not harvest timing", "No flexible or deferred payment option has been tested", "Farmer''s real disposable cash after input costs has not been estimated", "No comparison has been made against what farmers currently spend on alternatives", "Assuming price sensitivity is the same across different farmer income levels"]'::jsonb, 2),
('AGR-008', 'Aggregator or FPO Dependency Not Validated', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'The business depends on farmer groups or cooperatives to reach farmers, but this relationship has not been tested for reliability.', 3, 7, '["No FPO or cooperative relationship has been tested in practice", "Assuming the aggregator will represent farmer interests reliably", "No backup plan exists if the aggregator relationship breaks down", "The aggregator''s own incentives are not understood"]'::jsonb, 2),
('AGR-009', 'Results Do Not Generalise Across Regions', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'What worked with one soil type, crop, or local practice has not been checked against a different region.', 3, 7, '["Only tested in one region, soil type, or crop", "No plan exists to test a second, different region before scaling", "Local practices or beliefs in other regions have not been researched", "Assuming logistics and infrastructure will be similar elsewhere"]'::jsonb, 2),
('AGR-010', 'Distribution Network Strain at Scale', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'What worked with one region''s dealer setup breaks down when the business has to manage many regions at once.', 4, 8, '["No repeatable regional playbook exists", "Dealer performance is not tracked centrally across regions", "No regional owner structure is in place", "Dealer incentives are inconsistent across regions", "Quality control is degrading as the network grows"]'::jsonb, 2),
('AGR-011', 'Farmer Credit and Input-Financing Risk', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'As the business extends credit or financing to more farmers, default risk grows faster than the ability to manage it.', 5, 9, '["No credit-risk scoring model exists", "Default rates are not tracked systematically", "Lending decisions are based on relationship, not data", "No bad-debt reserve has been set aside", "Growth targets are outpacing risk management capacity"]'::jsonb, 2),
('AGR-012', 'Regulatory and Certification Complexity', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'Expansion into new products or markets brings compliance needs, such as organic certification, export rules, or food safety standards, that the business was not built to handle.', 4, 8, '["No compliance mapping is done before expansion", "Organic or export certification requirements are not understood", "Food safety requirements are not tracked as the business scales", "No dedicated compliance owner exists"]'::jsonb, 2),
('AGR-013', 'Aggregator or Cooperative Network Management', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'Managing many farmer-cooperative or FPO relationships at once is a fundamentally different skill than managing just one.', 3, 7, '["No standard way exists to evaluate cooperative performance", "Underperforming cooperatives are not identified early", "No escalation plan exists when a cooperative relationship weakens", "Cooperative network growth is outpacing relationship management capacity"]'::jsonb, 2),
('AGR-014', 'Technology Infrastructure Not Built for Scale', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'Systems built for a few hundred users or good connectivity start breaking down at real volume or in remote, low-connectivity areas.', 4, 8, '["Systems assume reliable internet connectivity", "No offline functionality exists for low-connectivity regions", "Infrastructure has not been tested at real operating volume", "No plan exists for scaling technology alongside farmer growth"]'::jsonb, 2),
('AGR-015', 'Revenue Concentration in Few Large Partners', 'Idea & Validation', 'Agriculture Market Validation', 'external', 'Too much revenue depends on a small number of large aggregators, government contracts, or distributors.', 4, 9, '["Revenue concentration is not tracked or measured", "No plan exists to diversify beyond top partners", "Heavy dependence exists on a small number of large contracts", "No early-warning system exists for a large partner leaving"]'::jsonb, 2)
  ) AS v(problem_code, problem_name, category, subcategory, layer, description, severity_min, severity_max, symptoms, pillar_id)
  RETURNING problem_id, problem_code
),
new_root_causes AS (
  INSERT INTO root_causes (root_cause_code, problem_id, root_cause_name, root_cause_category, explanation, confidence_weight, layer, primary_stage_group, industry_relevance, embedding, embedding_model, embedding_version, embedding_dimension)
  SELECT v.root_cause_code, p.problem_id, v.root_cause_name, v.root_cause_category, v.explanation, v.confidence_weight, v.layer, v.primary_stage_group, '["agritech"]'::jsonb, array_fill(0, ARRAY[1536])::vector, NULL, NULL, NULL
  FROM (VALUES
('RC-AGR-001', 'AGR-001', 'No Direct Farmer Conversations Yet', 'Behavioural', 'The founder has not yet spoken directly with farmers to validate the idea; everything is based on assumption.', 0.65, 'external', 'Stage 0'),
('RC-AGR-002', 'AGR-001', 'Adoption Speed Borrowed From App Behaviour', 'Knowledge', 'The founder is estimating how fast farmers will adopt this based on consumer app norms, not real farming behaviour.', 0.62, 'external', 'Stage 0'),
('RC-AGR-003', 'AGR-001', 'Cost of a Bad Outcome Not Accounted For', 'Strategic', 'The plan does not consider how much financial risk a bad result represents for the farmer trying it.', 0.65, 'external', 'Stage 0'),
('RC-AGR-004', 'AGR-001', 'Early-Adopter Farmers Not Identified', 'Operational', 'No distinction has been made between farmers likely to try something new early versus those who will wait and watch.', 0.60, 'external', 'Stage 0'),
('RC-AGR-005', 'AGR-001', 'Trust-Building Time Underestimated', 'Behavioural', 'The founder has not accounted for how long it genuinely takes to earn trust within a farming community.', 0.63, 'external', 'Stage 0'),
('RC-AGR-006', 'AGR-002', 'Solving for All Farmers Instead of One Group', 'Strategic', 'The idea is framed broadly as being for "farmers" rather than one specific, well-understood group.', 0.63, 'external', 'Stage 0'),
('RC-AGR-007', 'AGR-002', 'No Specific Crop or Region Chosen', 'Strategic', 'No single crop or region has been picked to begin building deep, specific understanding around.', 0.62, 'external', 'Stage 0'),
('RC-AGR-008', 'AGR-002', 'Narrowing Focus Avoided as Feels Risky', 'Behavioural', 'The founder is avoiding picking a specific segment because narrowing the idea feels like a loss of opportunity.', 0.58, 'external', 'Stage 0'),
('RC-AGR-009', 'AGR-002', 'No Clear Reason for Chosen Segment', 'Knowledge', 'There is no articulated, specific reason why this particular farmer segment was chosen over others.', 0.60, 'external', 'Stage 0'),
('RC-AGR-010', 'AGR-003', 'Plan Assumes Steady Year-Round Activity', 'Operational', 'The business plan implicitly assumes even, month-to-month activity rather than harvest-linked bursts.', 0.65, 'external', 'Stage 0'),
('RC-AGR-011', 'AGR-003', 'No Off-Season Plan Exists', 'Operational', 'There is no plan for what the business does or how it survives in the quiet period between harvests.', 0.65, 'external', 'Stage 0'),
('RC-AGR-012', 'AGR-003', 'Cash Flow Model Ignores Harvest Bursts', 'Operational', 'The financial model does not reflect that income arrives in short, concentrated windows tied to harvest timing.', 0.63, 'external', 'Stage 0'),
('RC-AGR-013', 'AGR-003', 'Busy and Quiet Months Not Mapped', 'Operational', 'The founder has not mapped out which months are naturally busy or quiet for the target crop or region.', 0.60, 'external', 'Stage 0'),
('RC-AGR-014', 'AGR-003', 'Crop Cycle Differences Not Distinguished', 'Knowledge', 'The idea treats all growing seasons the same, without distinguishing between different crop cycles like kharif and rabi.', 0.60, 'external', 'Stage 0'),
('RC-AGR-015', 'AGR-004', 'Land Data Accuracy Never Checked', 'Operational', 'The idea depends on land size or ownership data without having checked how accurate that data typically is.', 0.63, 'external', 'Stage 0'),
('RC-AGR-016', 'AGR-004', 'No Verification Plan for Farmer-Reported Data', 'Operational', 'There is no method planned for cross-checking information that farmers self-report.', 0.60, 'external', 'Stage 0'),
('RC-AGR-017', 'AGR-004', 'Formal Land Records Assumed', 'Knowledge', 'The plan assumes formal land records exist, when informal or tenant farming arrangements are common in many regions.', 0.62, 'external', 'Stage 0'),
('RC-AGR-018', 'AGR-004', 'No Fallback for Incorrect Data', 'Strategic', 'There is no fallback plan for what happens if key farmer or land data turns out to be wrong or missing.', 0.60, 'external', 'Stage 0'),
('RC-AGR-019', 'AGR-005', 'No Paying Pilot Run Yet', 'Operational', 'No test has been run where farmers actually paid for the product.', 0.63, 'external', 'Stage 0â†’1'),
('RC-AGR-020', 'AGR-005', 'Free or Discounted Users Treated as Validated', 'Behavioural', 'Users who got the product free or cheap are being counted as proof of demand.', 0.65, 'external', 'Stage 0â†’1'),
('RC-AGR-021', 'AGR-005', 'No Plan to Test at Full Price', 'Strategic', 'There is no defined plan for when or how full pricing will actually be tested.', 0.62, 'external', 'Stage 0â†’1'),
('RC-AGR-022', 'AGR-005', 'Early Users May Not Represent Target Farmers', 'Knowledge', 'The farmers who tried the product so far may differ meaningfully from the real target customer.', 0.60, 'external', 'Stage 0â†’1'),
('RC-AGR-023', 'AGR-005', 'No Repeat-Usage Data Collected', 'Operational', 'There is no data on whether early users came back to use the product again on their own.', 0.60, 'external', 'Stage 0â†’1'),
('RC-AGR-024', 'AGR-006', 'No Real Distribution Partner Tested', 'Operational', 'No dealer, agent, or cooperative has actually been used to deliver the product.', 0.65, 'external', 'Stage 0â†’1'),
('RC-AGR-025', 'AGR-006', 'Assuming Digital-Only Reach', 'Strategic', 'The plan assumes farmers will be reached online, with no physical distribution component.', 0.63, 'external', 'Stage 0â†’1'),
('RC-AGR-026', 'AGR-006', 'Distribution Costs Not Accounted For', 'Operational', 'The real cost of paying a field agent or dealer to reach one farmer has not been calculated.', 0.62, 'external', 'Stage 0â†’1'),
('RC-AGR-027', 'AGR-006', 'Time-to-Reach New Areas Untested', 'Operational', 'There is no real measurement of how long it takes to enter and reach a brand-new village or area.', 0.60, 'external', 'Stage 0â†’1'),
('RC-AGR-028', 'AGR-007', 'Pricing Modeled on Monthly Billing', 'Strategic', 'Pricing follows a standard monthly billing pattern that does not match harvest-linked income.', 0.63, 'external', 'Stage 0â†’1'),
('RC-AGR-029', 'AGR-007', 'No Deferred Payment Option Tested', 'Operational', 'Letting farmers pay after harvest, rather than upfront, has not been tried.', 0.62, 'external', 'Stage 0â†’1'),
('RC-AGR-030', 'AGR-007', 'Real Disposable Farmer Income Not Estimated', 'Knowledge', 'The amount of cash a farmer actually has left after paying for inputs has not been calculated.', 0.63, 'external', 'Stage 0â†’1'),
('RC-AGR-031', 'AGR-007', 'No Comparison Against Current Alternatives', 'Knowledge', 'There is no comparison between this price and what farmers currently spend on alternatives.', 0.60, 'external', 'Stage 0â†’1'),
('RC-AGR-032', 'AGR-007', 'Price Sensitivity Assumed Uniform', 'Strategic', 'The plan assumes all farmer income levels respond to price the same way.', 0.58, 'external', 'Stage 0â†’1'),
('RC-AGR-033', 'AGR-008', 'No FPO Relationship Tested in Practice', 'Operational', 'No actual working relationship with a farmer cooperative or FPO has been tested.', 0.63, 'external', 'Stage 0â†’1'),
('RC-AGR-034', 'AGR-008', 'Aggregator Assumed to Represent Farmers Reliably', 'Knowledge', 'It is assumed the cooperative genuinely represents farmer interests, without confirming this.', 0.60, 'external', 'Stage 0â†’1'),
('RC-AGR-035', 'AGR-008', 'No Backup Plan if Aggregator Relationship Fails', 'Strategic', 'There is no plan for what happens if the cooperative or aggregator partnership ends.', 0.62, 'external', 'Stage 0â†’1'),
('RC-AGR-036', 'AGR-008', 'Aggregator Incentives Not Understood', 'Knowledge', 'What the aggregator itself gains from this relationship has not been examined.', 0.60, 'external', 'Stage 0â†’1'),
('RC-AGR-037', 'AGR-009', 'Only Tested in One Region or Crop', 'Operational', 'Validation has only happened in one region, soil type, or crop so far.', 0.63, 'external', 'Stage 0â†’1'),
('RC-AGR-038', 'AGR-009', 'No Second-Region Test Planned', 'Strategic', 'There is no plan to validate in a second, different region before scaling.', 0.62, 'external', 'Stage 0â†’1'),
('RC-AGR-039', 'AGR-009', 'Regional Practice Differences Not Researched', 'Knowledge', 'Differences in farming practice or belief in other target regions have not been researched.', 0.60, 'external', 'Stage 0â†’1'),
('RC-AGR-040', 'AGR-009', 'Infrastructure Assumed Similar Elsewhere', 'Strategic', 'It is assumed logistics and infrastructure will be similar in every region the business expands to.', 0.60, 'external', 'Stage 0â†’1'),
('RC-AGR-041', 'AGR-010', 'No Repeatable Regional Playbook', 'Operational', 'There is no documented, repeatable process for setting up distribution in a new region.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-AGR-042', 'AGR-010', 'Dealer Performance Not Tracked Centrally', 'Operational', 'Dealer performance is managed independently per region with no central visibility.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-AGR-043', 'AGR-010', 'No Regional Owner Structure', 'Operational', 'No specific person is accountable for distribution performance in each region.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-AGR-044', 'AGR-010', 'Inconsistent Dealer Incentives', 'Operational', 'Dealer incentive structures vary region to region rather than following one design.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-AGR-045', 'AGR-010', 'Quality Control Degrading With Growth', 'Operational', 'Product or service quality is becoming harder to maintain consistently as the network expands.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-AGR-046', 'AGR-011', 'No Credit-Risk Scoring Model', 'Knowledge', 'There is no systematic way to assess which farmers are higher risk for credit or financing default.', 0.68, 'external', 'Stage 1â†’10+'),
('RC-AGR-047', 'AGR-011', 'Default Rates Not Tracked', 'Operational', 'The actual rate of loan or financing default is not being systematically measured.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-AGR-048', 'AGR-011', 'Lending Decisions Relationship-Based', 'Behavioural', 'Credit decisions are made based on personal trust rather than consistent data criteria.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-AGR-049', 'AGR-011', 'No Bad-Debt Reserve', 'Strategic', 'No financial reserve has been set aside to absorb expected credit losses.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-AGR-050', 'AGR-011', 'Growth Outpacing Risk Capacity', 'Strategic', 'Credit or financing volume is growing faster than the team''s ability to manage that risk.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-AGR-051', 'AGR-012', 'No Compliance Mapping Before Expansion', 'Operational', 'New markets or products are entered without first mapping the compliance requirements involved.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-AGR-052', 'AGR-012', 'Certification Requirements Not Understood', 'Knowledge', 'Organic, export, or other certification requirements are not well understood by the team.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-AGR-053', 'AGR-012', 'Food Safety Requirements Not Tracked', 'Operational', 'Food safety compliance is not being actively tracked as the business scales.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-AGR-054', 'AGR-012', 'No Dedicated Compliance Owner', 'Operational', 'Nobody is specifically responsible for regulatory compliance; it falls to whoever has time.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-AGR-055', 'AGR-013', 'No Cooperative Performance Evaluation', 'Operational', 'There is no consistent method for assessing how well each cooperative or aggregator is performing.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-AGR-056', 'AGR-013', 'Underperformance Identified Too Late', 'Operational', 'Struggling cooperative relationships are typically noticed only once they become a serious problem.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-AGR-057', 'AGR-013', 'No Escalation Plan for Weakening Relationships', 'Strategic', 'There is no defined next step when a cooperative relationship starts to weaken.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-AGR-058', 'AGR-013', 'Network Growth Outpacing Management Capacity', 'Operational', 'The number of cooperative relationships has grown faster than the team''s ability to manage them well.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-AGR-059', 'AGR-014', 'Systems Assume Reliable Connectivity', 'Operational', 'Core systems are built assuming internet connectivity that does not exist in all operating regions.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-AGR-060', 'AGR-014', 'No Offline Functionality', 'Operational', 'The product does not function in areas with poor or no internet signal.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-AGR-061', 'AGR-014', 'Infrastructure Untested at Real Volume', 'Operational', 'Technology infrastructure has not actually been load-tested at the volume the business now operates at.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-AGR-062', 'AGR-014', 'No Technology Scaling Plan', 'Strategic', 'There is no plan for how technology infrastructure will keep pace with continued farmer growth.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-AGR-063', 'AGR-015', 'Revenue Concentration Not Tracked', 'Operational', 'The business does not measure how much revenue depends on its largest partners.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-AGR-064', 'AGR-015', 'No Diversification Plan', 'Strategic', 'There is no active plan to reduce dependence on the largest existing partners.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-AGR-065', 'AGR-015', 'Heavy Dependence on Few Large Contracts', 'Strategic', 'A small number of large contracts or partners account for a disproportionate share of revenue.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-AGR-066', 'AGR-015', 'No Early-Warning System for Partner Loss', 'Operational', 'There is no system in place that would give advance warning if a major partner intended to leave.', 0.60, 'external', 'Stage 1â†’10+')
  ) AS v(root_cause_code, problem_code, root_cause_name, root_cause_category, explanation, confidence_weight, layer, primary_stage_group)
  JOIN new_problems p ON p.problem_code = v.problem_code
  RETURNING root_cause_id, root_cause_code
),
new_questions AS (
  INSERT INTO questions (question_code, category, question_text, problem_id, root_cause_id, question_type, difficulty_level, priority, is_distress_tagged, industry_relevance, embedding, primary_stage_group, embedding_model, embedding_version, embedding_dimension)
  SELECT v.question_code, 'Idea & Validation', v.question_text, p.problem_id, rc.root_cause_id, 'open_text', v.difficulty_level, v.priority, false, '["agritech"]'::jsonb, array_fill(0, ARRAY[1536])::vector, v.stage_group, NULL, NULL, NULL
  FROM (VALUES
('S0-AGR-001', 'AGR-001', 'RC-AGR-001', 'Have you actually spoken to a farmer about this idea, or is this based on what you assume they''d want?', 2, 'CORE', 'Stage 0'),
('S0-AGR-002', 'AGR-001', 'RC-AGR-002', 'Where did you get the idea that farmers would adopt this quickly -- from farmers, or from how people use apps?', 2, 'CORE', 'Stage 0'),
('S0-AGR-003', 'AGR-001', 'RC-AGR-003', 'If a farmer tried this and it went wrong, could it cost them real money they can''t afford to lose?', 2, 'CORE', 'Stage 0'),
('S0-AGR-004', 'AGR-001', 'RC-AGR-004', 'Do you know which farmers are usually first to try something new, versus which ones wait and watch?', 2, 'CORE', 'Stage 0'),
('S0-AGR-005', 'AGR-001', 'RC-AGR-005', 'How much time do you think it takes to earn a farmer''s trust before they''ll actually use something you built?', 3, 'CORE', 'Stage 0'),
('S0-AGR-006', 'AGR-002', 'RC-AGR-006', 'Can you name one specific type of farmer or one specific crop this is built for -- or is it still "farmers" in general?', 2, 'CORE', 'Stage 0'),
('S0-AGR-007', 'AGR-002', 'RC-AGR-007', 'Have you picked one region to start in, or are you still thinking about farmers everywhere?', 2, 'CORE', 'Stage 0'),
('S0-AGR-008', 'AGR-002', 'RC-AGR-009', 'Why did you choose to start with this particular group of farmers, and not another?', 2, 'SUPPLEMENTARY', 'Stage 0'),
('S0-AGR-009', 'AGR-003', 'RC-AGR-010', 'Does your idea assume steady activity all year, even though farm income usually comes in short bursts?', 2, 'CORE', 'Stage 0'),
('S0-AGR-010', 'AGR-003', 'RC-AGR-011', 'What happens to your business between harvests, when farmers have little money to spend?', 2, 'CORE', 'Stage 0'),
('S0-AGR-011', 'AGR-003', 'RC-AGR-013', 'Have you mapped out which months are busy and which are quiet for the crop or region you''re targeting?', 2, 'CORE', 'Stage 0'),
('S0-AGR-012', 'AGR-003', 'RC-AGR-014', 'Does your idea treat all farming seasons the same, or have you accounted for different crop cycles?', 3, 'CORE', 'Stage 0'),
('S0-AGR-013', 'AGR-004', 'RC-AGR-015', 'If you needed to know how much land a farmer owns, how would you find that out reliably?', 2, 'CORE', 'Stage 0'),
('S0-AGR-014', 'AGR-004', 'RC-AGR-017', 'Have you checked whether farmers in your target area actually have formal land records, or is ownership often informal?', 2, 'CORE', 'Stage 0'),
('S0-AGR-015', 'AGR-004', 'RC-AGR-018', 'What would you do if the farmer data you''re relying on turned out to be wrong?', 2, 'SUPPLEMENTARY', 'Stage 0'),
('S01-AGR-001', 'AGR-005', 'RC-AGR-020', 'Did farmers pay full price during your test, or was it free or discounted?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-002', 'AGR-005', 'RC-AGR-021', 'If you asked today''s users to pay full price starting tomorrow, how many would still say yes?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-003', 'AGR-005', 'RC-AGR-022', 'Are the farmers who tried this actually similar to the ones you eventually want as customers?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-004', 'AGR-005', 'RC-AGR-023', 'Have any of your early users come back to use this a second time on their own?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-005', 'AGR-006', 'RC-AGR-024', 'Have you actually delivered this through a real dealer, agent, or cooperative -- or only tested it yourself?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-006', 'AGR-006', 'RC-AGR-025', 'Does your plan assume farmers will find this online, without any physical way to reach them?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-007', 'AGR-006', 'RC-AGR-026', 'Have you worked out what it costs to pay a field agent or dealer to reach one farmer?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-008', 'AGR-006', 'RC-AGR-027', 'How long would it take you to reach a brand-new village you''ve never worked in before?', 3, 'CORE', 'Stage 0â†’1'),
('S01-AGR-009', 'AGR-007', 'RC-AGR-028', 'Does your pricing assume farmers pay upfront, or have you checked when they actually have cash available?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-010', 'AGR-007', 'RC-AGR-029', 'Have you tested letting farmers pay after harvest instead of upfront?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-011', 'AGR-007', 'RC-AGR-030', 'After paying for seeds, fertilizer, and other inputs, how much money does your target farmer actually have left?', 3, 'CORE', 'Stage 0â†’1'),
('S01-AGR-012', 'AGR-007', 'RC-AGR-031', 'What do farmers currently spend money on instead of this, and how does your price compare?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-013', 'AGR-008', 'RC-AGR-033', 'Have you actually worked with a farmer cooperative or FPO in practice, or only assumed they''d help?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-014', 'AGR-008', 'RC-AGR-034', 'Are you confident the cooperative you''re relying on genuinely represents what farmers want?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-015', 'AGR-008', 'RC-AGR-035', 'What would you do if your cooperative or aggregator partnership fell apart tomorrow?', 3, 'CORE', 'Stage 0â†’1'),
('S01-AGR-016', 'AGR-008', 'RC-AGR-036', 'Do you understand what the aggregator gets out of working with you, beyond helping farmers?', 2, 'SUPPLEMENTARY', 'Stage 0â†’1'),
('S01-AGR-017', 'AGR-009', 'RC-AGR-037', 'Has this only been tested in one region, crop, or soil type so far?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-018', 'AGR-009', 'RC-AGR-038', 'Do you have a plan to test this in a second, different region before assuming it will scale?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-019', 'AGR-009', 'RC-AGR-039', 'Have you looked into whether farming practices or beliefs are different in other regions you might expand to?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AGR-020', 'AGR-009', 'RC-AGR-040', 'Are you assuming the same logistics and infrastructure will exist everywhere you expand?', 2, 'SUPPLEMENTARY', 'Stage 0â†’1'),
('S10-AGR-001', 'AGR-010', 'RC-AGR-041', 'Has your dealer or distribution approach been written down as a repeatable process, or does each region get set up differently?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-002', 'AGR-010', 'RC-AGR-042', 'Do you track dealer performance centrally, or does each region manage that on its own?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-003', 'AGR-010', 'RC-AGR-043', 'Is there a specific person accountable for each region''s distribution performance?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-004', 'AGR-010', 'RC-AGR-044', 'Are dealer incentives consistent across regions, or does each one negotiate separately?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-005', 'AGR-010', 'RC-AGR-045', 'Has product or service quality gotten harder to maintain as you''ve added more regions?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-006', 'AGR-011', 'RC-AGR-046', 'Do you have any way to score or predict which farmers are likely to default on credit or financing?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-007', 'AGR-011', 'RC-AGR-047', 'Do you track your actual default rate, or would that require digging to find out?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-008', 'AGR-011', 'RC-AGR-048', 'Are lending decisions made based on data, or mostly on relationship and trust?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-009', 'AGR-011', 'RC-AGR-049', 'Have you set aside a reserve for expected bad debt, or does a default just hit as a surprise?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-010', 'AGR-011', 'RC-AGR-050', 'Is your growth in farmer credit outpacing your ability to actually manage that risk?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-011', 'AGR-012', 'RC-AGR-051', 'Before expanding into a new product or market, do you map out what compliance or certification you''ll need?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-012', 'AGR-012', 'RC-AGR-052', 'Do you understand what organic or export certification would require if you needed it?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-013', 'AGR-012', 'RC-AGR-053', 'Are you confident you''re meeting food safety requirements as you''ve scaled?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-014', 'AGR-012', 'RC-AGR-054', 'Is there someone specifically responsible for compliance, or does it fall on whoever has time?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-015', 'AGR-013', 'RC-AGR-055', 'Do you have a consistent way to evaluate how well each cooperative or aggregator is performing?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-016', 'AGR-013', 'RC-AGR-056', 'Would you know a cooperative was underperforming early, or only once it became a real problem?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-017', 'AGR-013', 'RC-AGR-057', 'If one cooperative started underperforming, would you have a clear next step, or figure it out as you go?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-018', 'AGR-013', 'RC-AGR-058', 'Has managing your growing number of cooperative relationships gotten harder than your team can keep up with?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-019', 'AGR-014', 'RC-AGR-059', 'Do your systems assume internet connectivity that doesn''t actually exist in all your operating regions?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-020', 'AGR-014', 'RC-AGR-060', 'Does your product work at all when a farmer or field agent has no signal?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-021', 'AGR-014', 'RC-AGR-061', 'Has your technology actually been tested at the volume you''re now operating at?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-022', 'AGR-014', 'RC-AGR-062', 'Is there a real plan for your technology to keep up as you keep adding farmers?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-023', 'AGR-015', 'RC-AGR-063', 'What percentage of your revenue comes from just your top two or three partners?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-024', 'AGR-015', 'RC-AGR-064', 'Do you have a real plan to reduce dependence on your largest partners?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AGR-025', 'AGR-015', 'RC-AGR-066', 'If your biggest partner left tomorrow, would you have any advance warning, or would it just happen?', 3, 'CORE', 'Stage 1â†’10+')
  ) AS v(question_code, problem_code, root_cause_code, question_text, difficulty_level, priority, stage_group)
  JOIN new_problems p ON p.problem_code = v.problem_code
  JOIN new_root_causes rc ON rc.root_cause_code = v.root_cause_code
  RETURNING question_id, question_code
),
new_tags AS (
  INSERT INTO question_tag_mapping (question_id, tag_id)
  SELECT q.question_id, v.tag_id
  FROM (VALUES
('S0-AGR-001', 2), ('S0-AGR-002', 2), ('S0-AGR-003', 2), ('S0-AGR-004', 2), ('S0-AGR-005', 2),
('S0-AGR-006', 3), ('S0-AGR-007', 3), ('S0-AGR-008', 3),
('S0-AGR-009', 84), ('S0-AGR-010', 84), ('S0-AGR-011', 84), ('S0-AGR-012', 84),
('S0-AGR-013', 36), ('S0-AGR-014', 36), ('S0-AGR-015', 36),
('S01-AGR-001', 8), ('S01-AGR-002', 8), ('S01-AGR-003', 8), ('S01-AGR-004', 8),
('S01-AGR-005', 12), ('S01-AGR-006', 12), ('S01-AGR-007', 12), ('S01-AGR-008', 12),
('S01-AGR-009', 21), ('S01-AGR-010', 21), ('S01-AGR-011', 21), ('S01-AGR-012', 21),
('S01-AGR-013', 17), ('S01-AGR-014', 17), ('S01-AGR-015', 17), ('S01-AGR-016', 17),
('S01-AGR-017', 2), ('S01-AGR-018', 2), ('S01-AGR-019', 2), ('S01-AGR-020', 2),
('S10-AGR-001', 12), ('S10-AGR-002', 12), ('S10-AGR-003', 12), ('S10-AGR-004', 12), ('S10-AGR-005', 12),
('S10-AGR-006', 84), ('S10-AGR-007', 84), ('S10-AGR-008', 84), ('S10-AGR-009', 84), ('S10-AGR-010', 84),
('S10-AGR-011', 4), ('S10-AGR-012', 4), ('S10-AGR-013', 4), ('S10-AGR-014', 4),
('S10-AGR-015', 17), ('S10-AGR-016', 17), ('S10-AGR-017', 17), ('S10-AGR-018', 17),
('S10-AGR-019', 33), ('S10-AGR-020', 33), ('S10-AGR-021', 33), ('S10-AGR-022', 33),
('S10-AGR-023', 23), ('S10-AGR-024', 23), ('S10-AGR-025', 23)
  ) AS v(question_code, tag_id)
  JOIN new_questions q ON q.question_code = v.question_code
  RETURNING mapping_id
),
new_interventions AS (
  INSERT INTO interventions (intervention_code, problem_id, root_cause_ids, secondary_root_cause_ids, capability_domain, section, recommended_frameworks, framework_codes, immediate_next_steps, stage_relevance, industry_relevance, design_principles)
  SELECT v.intervention_code, p.problem_id, v.root_cause_ids, '[]'::jsonb, v.capability_domain, v.section, v.recommended_frameworks, NULL, v.immediate_next_steps, v.stage_relevance, '["agritech"]'::jsonb, v.design_principles
  FROM (VALUES
('INT-AGR-001', 'AGR-001', '["RC-AGR-001", "RC-AGR-002"]'::jsonb, 'Market Validation', 'Ideation â€” Farmer & Market Validation', '[{"name": "Customer Discovery Interviews", "brief": "Structured conversations to validate assumptions before building."}]'::jsonb, '["Identify 10 farmers matching your target profile.", "Prepare 5 open-ended questions about their current process.", "Conduct and record the conversations before writing any code."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-002', 'AGR-001', '["RC-AGR-003", "RC-AGR-004"]'::jsonb, 'Market Validation', 'Ideation â€” Farmer & Market Validation', '[{"name": "Ethnographic Shadowing", "brief": "Direct observation of a real farmer''s decision points across a full cycle."}]'::jsonb, '["Identify one farmer willing to be shadowed.", "Observe at least one full crop cycle, or as much of it as timing allows.", "Document the specific moments where a wrong decision would cost them the most."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-003', 'AGR-001', '["RC-AGR-005"]'::jsonb, 'Market Validation', 'Ideation â€” Farmer & Market Validation', '[{"name": "Trust-Building Roadmap", "brief": "A simple plan for how credibility gets earned before any ask is made."}]'::jsonb, '["Write one paragraph on how you will earn credibility with this group.", "Identify one trusted local figure who could vouch for you.", "Plan your first interaction to build trust, not to sell."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-004', 'AGR-002', '["RC-AGR-006", "RC-AGR-007"]'::jsonb, 'Strategic Focus', 'Ideation â€” Farmer & Market Validation', '[{"name": "Narrow-Then-Expand Framework", "brief": "Deliberately choosing one segment before broadening later."}]'::jsonb, '["Pick one crop.", "Pick one region.", "Pick one farmer type, and write down who is explicitly NOT your first customer."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-005', 'AGR-002', '["RC-AGR-008", "RC-AGR-009"]'::jsonb, 'Strategic Focus', 'Ideation â€” Farmer & Market Validation', '[{"name": "Segment Justification Exercise", "brief": "Forcing an explicit, written reason for a strategic choice."}]'::jsonb, '["Write one paragraph justifying why this segment, specifically.", "Name two segments you are deliberately NOT choosing right now.", "Revisit this reasoning after your first 10 farmer conversations."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-006', 'AGR-003', '["RC-AGR-010", "RC-AGR-012"]'::jsonb, 'Financial Planning', 'Ideation â€” Farmer & Market Validation', '[{"name": "Harvest-Linked Cash Flow Mapping", "brief": "Aligning a cash flow model to real harvest timing instead of even monthly assumptions."}]'::jsonb, '["List the harvest windows for your target crop.", "Map expected income against those windows, not evenly across months.", "Identify the longest gap between income windows."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-007', 'AGR-003', '["RC-AGR-011"]'::jsonb, 'Financial Planning', 'Ideation â€” Farmer & Market Validation', '[{"name": "Off-Season Survival Plan", "brief": "A concrete plan for the quiet period between harvests."}]'::jsonb, '["Identify your longest expected quiet period.", "Decide what the business does during that window.", "Write down the minimum cash needed to survive it."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-008', 'AGR-003', '["RC-AGR-013", "RC-AGR-014"]'::jsonb, 'Market Validation', 'Ideation â€” Farmer & Market Validation', '[{"name": "Crop Calendar Mapping", "brief": "Mapping the full cycle of a target crop, including regional variations like kharif and rabi."}]'::jsonb, '["Map the full growing calendar for your target crop.", "Note key decision points a farmer faces during that calendar.", "Check whether your product plan fits every phase, or just one."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-009', 'AGR-004', '["RC-AGR-015", "RC-AGR-016"]'::jsonb, 'Data Reliability', 'Ideation â€” Farmer & Market Validation', '[{"name": "Manual Data Verification Method", "brief": "A lightweight, low-tech way to cross-check farmer-reported information before trusting it."}]'::jsonb, '["Pick one data point your idea depends on (e.g. land size).", "Design one simple, low-cost way to verify it.", "Test this verification method with 5 real farmers."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-010', 'AGR-004', '["RC-AGR-017", "RC-AGR-018"]'::jsonb, 'Data Reliability', 'Ideation â€” Farmer & Market Validation', '[{"name": "Data-Failure Fallback Planning", "brief": "Deciding in advance what happens if key assumed data turns out to be wrong."}]'::jsonb, '["List every data point your idea assumes is accurate.", "For each one, write what you would do if it turned out wrong.", "Identify which single data failure would hurt the most."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-011', 'AGR-005', '["RC-AGR-019", "RC-AGR-020", "RC-AGR-021"]'::jsonb, 'Market Validation', 'Validation â€” Farmer Pilot Testing', '[{"name": "Paid Pilot Framework", "brief": "Testing real willingness to pay by removing free or discounted access."}]'::jsonb, '["Pick a small group of farmers for a paid-only pilot.", "Remove all discounts and free access for this group.", "Track how many actually complete payment."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-012', 'AGR-005', '["RC-AGR-022", "RC-AGR-023"]'::jsonb, 'Market Validation', 'Validation â€” Farmer Pilot Testing', '[{"name": "Repeat-Usage Tracking", "brief": "Measuring whether users return on their own, without prompting."}]'::jsonb, '["Track which early users return without being reminded.", "Compare early-user profile against your real target segment.", "Flag any mismatch before treating results as validated."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-013', 'AGR-006', '["RC-AGR-024", "RC-AGR-025"]'::jsonb, 'Distribution Validation', 'Validation â€” Farmer Pilot Testing', '[{"name": "Physical Channel Pilot", "brief": "Running one real delivery cycle through an actual dealer, agent, or cooperative."}]'::jsonb, '["Identify one real dealer, agent, or cooperative to test with.", "Run one complete delivery cycle through them.", "Document every step and delay that happened."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-014', 'AGR-006', '["RC-AGR-026"]'::jsonb, 'Distribution Validation', 'Validation â€” Farmer Pilot Testing', '[{"name": "Cost-to-Reach Calculation", "brief": "Calculating the true cost of physically reaching one farmer."}]'::jsonb, '["List every cost involved in reaching one farmer.", "Calculate a real cost-per-farmer number.", "Compare this against what you can charge."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-015', 'AGR-006', '["RC-AGR-027"]'::jsonb, 'Distribution Validation', 'Validation â€” Farmer Pilot Testing', '[{"name": "New-Area Entry Timing Test", "brief": "Timing exactly how long it takes to enter a brand-new area."}]'::jsonb, '["Pick one new village you have not worked in before.", "Time every step from first contact to first sale.", "Note what specifically slowed you down."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-016', 'AGR-007', '["RC-AGR-028", "RC-AGR-029"]'::jsonb, 'Pricing Strategy', 'Validation â€” Farmer Pilot Testing', '[{"name": "Harvest-Aligned Payment Design", "brief": "Building a payment option tied to harvest payout timing instead of monthly billing."}]'::jsonb, '["Design one deferred or installment payment option.", "Test it with a small group of farmers.", "Compare uptake against your current upfront pricing."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-017', 'AGR-007', '["RC-AGR-030", "RC-AGR-032"]'::jsonb, 'Pricing Strategy', 'Validation â€” Farmer Pilot Testing', '[{"name": "Disposable Income Estimation", "brief": "Estimating real farmer cash available after input costs."}]'::jsonb, '["List a target farmer''s typical input costs.", "Estimate what cash remains after those costs.", "Check your price against that remaining amount."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-018', 'AGR-007', '["RC-AGR-031"]'::jsonb, 'Pricing Strategy', 'Validation â€” Farmer Pilot Testing', '[{"name": "Alternative Spend Comparison", "brief": "Comparing your price against what farmers already spend on substitutes."}]'::jsonb, '["List what farmers currently spend money on instead of this.", "Compare your price directly against those alternatives.", "Adjust pricing or positioning based on the gap."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-019', 'AGR-008', '["RC-AGR-033", "RC-AGR-036"]'::jsonb, 'Partnership Validation', 'Validation â€” Farmer Pilot Testing', '[{"name": "Aggregator Incentive Conversation", "brief": "An honest, direct conversation to understand what the aggregator actually gains from this relationship."}]'::jsonb, '["Schedule one direct conversation with your aggregator/FPO contact.", "Ask explicitly what they gain from working with you.", "Write down anything that surprises you."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-020', 'AGR-008', '["RC-AGR-034", "RC-AGR-035"]'::jsonb, 'Partnership Validation', 'Validation â€” Farmer Pilot Testing', '[{"name": "Aggregator Backup Planning", "brief": "Preparing a fallback plan in case the aggregator relationship ends."}]'::jsonb, '["Identify what breaks if this relationship ends tomorrow.", "Identify one alternative aggregator or direct channel.", "Write a short contingency plan."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-021', 'AGR-009', '["RC-AGR-037", "RC-AGR-038"]'::jsonb, 'Market Validation', 'Validation â€” Farmer Pilot Testing', '[{"name": "Second-Region Validation Test", "brief": "Testing in one new region before assuming results will scale."}]'::jsonb, '["Pick one region different from where you first tested.", "Run the same pilot there.", "Compare results side by side before scaling further."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-022', 'AGR-009', '["RC-AGR-039", "RC-AGR-040"]'::jsonb, 'Market Validation', 'Validation â€” Farmer Pilot Testing', '[{"name": "Regional Practice Research", "brief": "Researching local farming practices and infrastructure before expanding."}]'::jsonb, '["Research farming practices specific to your next target region.", "Check what logistics/infrastructure actually exists there.", "Note any assumption you were carrying over incorrectly."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-023', 'AGR-010', '["RC-AGR-041", "RC-AGR-043"]'::jsonb, 'Distribution Scaling', 'Growth â€” Regional Distribution Management', '[{"name": "Regional Playbook Framework", "brief": "Documenting a repeatable process for entering and running a new region."}]'::jsonb, '["Document your best-performing region''s setup process.", "Assign one accountable owner per region.", "Roll the documented playbook out to your next new region."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-024', 'AGR-010', '["RC-AGR-042", "RC-AGR-044", "RC-AGR-045"]'::jsonb, 'Distribution Scaling', 'Growth â€” Regional Distribution Management', '[{"name": "Centralized Dealer Performance Tracking", "brief": "A shared system to monitor dealer performance and quality across all regions."}]'::jsonb, '["Set up one central dashboard for dealer performance.", "Standardize dealer incentive structure across regions.", "Define one consistent quality checkpoint applied everywhere."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-025', 'AGR-011', '["RC-AGR-046", "RC-AGR-048"]'::jsonb, 'Risk Management', 'Growth â€” Farmer Credit & Risk', '[{"name": "Simple Credit-Risk Scoring Model", "brief": "A basic, data-informed way to assess farmer credit risk instead of relying purely on relationship."}]'::jsonb, '["List 3-5 factors that predict repayment reliability.", "Build a simple scoring method using those factors.", "Test it against your existing loan book to check accuracy."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-026', 'AGR-011', '["RC-AGR-047", "RC-AGR-049", "RC-AGR-050"]'::jsonb, 'Risk Management', 'Growth â€” Farmer Credit & Risk', '[{"name": "Bad-Debt Reserve Planning", "brief": "Setting aside a financial reserve based on real, tracked default data."}]'::jsonb, '["Calculate your actual historical default rate.", "Set aside a reserve based on that real number.", "Set a growth pace that matches your risk management capacity."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-027', 'AGR-012', '["RC-AGR-051", "RC-AGR-052"]'::jsonb, 'Regulatory Compliance', 'Growth â€” Regulatory & Certification', '[{"name": "Pre-Expansion Compliance Checklist", "brief": "Mapping every compliance and certification requirement before entering a new product or market."}]'::jsonb, '["Build a compliance checklist for your next expansion.", "Research certification requirements specific to that market.", "Get sign-off from someone knowledgeable before launching."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-028', 'AGR-012', '["RC-AGR-053", "RC-AGR-054"]'::jsonb, 'Regulatory Compliance', 'Growth â€” Regulatory & Certification', '[{"name": "Dedicated Compliance Ownership", "brief": "Assigning a specific, accountable owner for regulatory compliance as the business scales."}]'::jsonb, '["Assign one person as compliance owner, even part-time.", "Create a running list of applicable regulations.", "Schedule a recurring compliance review."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-029', 'AGR-013', '["RC-AGR-055", "RC-AGR-056"]'::jsonb, 'Partnership Management', 'Growth â€” Cooperative Network Management', '[{"name": "Cooperative Performance Scorecard", "brief": "A standard way to evaluate and compare cooperative or aggregator performance."}]'::jsonb, '["Define 3-4 metrics that indicate cooperative health.", "Score every current cooperative against them.", "Review scores on a regular cadence."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-030', 'AGR-013', '["RC-AGR-057", "RC-AGR-058"]'::jsonb, 'Partnership Management', 'Growth â€” Cooperative Network Management', '[{"name": "Escalation Path for Weakening Partnerships", "brief": "A defined next step for when a cooperative relationship starts to underperform."}]'::jsonb, '["Define what counts as an early warning sign.", "Write a specific escalation step for that trigger.", "Assign someone to own the escalation process."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-031', 'AGR-014', '["RC-AGR-059", "RC-AGR-060"]'::jsonb, 'Technology Infrastructure', 'Growth â€” Technology at Scale', '[{"name": "Offline-First Design", "brief": "Building core functionality to work without a live internet connection."}]'::jsonb, '["Identify your product''s core functions that must work offline.", "Build or adapt those functions to work without connectivity.", "Test in a genuinely low-signal area before rolling out."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-032', 'AGR-014', '["RC-AGR-061", "RC-AGR-062"]'::jsonb, 'Technology Infrastructure', 'Growth â€” Technology at Scale', '[{"name": "Load Testing at Real Volume", "brief": "Testing infrastructure at the actual scale the business now operates at, not the scale it was designed for."}]'::jsonb, '["Run a load test at your current real user volume.", "Identify the first point of failure.", "Build a scaling plan based on what you find."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-033', 'AGR-015', '["RC-AGR-063", "RC-AGR-065"]'::jsonb, 'Revenue Strategy', 'Growth â€” Revenue Concentration Risk', '[{"name": "Revenue Concentration Audit", "brief": "Calculating exactly how much revenue depends on your largest partners."}]'::jsonb, '["Calculate revenue share from your top 3 partners.", "Compare this against a healthy concentration benchmark.", "Present this number to your leadership team."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AGR-034', 'AGR-015', '["RC-AGR-064", "RC-AGR-066"]'::jsonb, 'Revenue Strategy', 'Growth â€” Revenue Concentration Risk', '[{"name": "Partner Diversification Plan", "brief": "An active plan to reduce dependence on the largest existing partners over time."}]'::jsonb, '["Set a target to reduce your top-partner revenue share.", "Identify 2-3 new partner types to pursue.", "Build an early-warning check-in cadence with major partners."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb)
  ) AS v(intervention_code, problem_code, root_cause_ids, capability_domain, section, recommended_frameworks, immediate_next_steps, stage_relevance, design_principles)
  JOIN new_problems p ON p.problem_code = v.problem_code
  RETURNING intervention_id, intervention_code
)
SELECT
  (SELECT COUNT(*) FROM new_problems) as problems_inserted,
  (SELECT COUNT(*) FROM new_root_causes) as root_causes_inserted,
  (SELECT COUNT(*) FROM new_questions) as questions_inserted,
  (SELECT COUNT(*) FROM new_tags) as tags_inserted,
  (SELECT COUNT(*) FROM new_interventions) as interventions_inserted;"""),

        ('Automotive & Mobility', 'automotive', 'AUT', r"""WITH new_problems AS (
  INSERT INTO problems (problem_code, problem_name, category, subcategory, layer, description, severity_min, severity_max, symptoms, pillar_id, industry_relevance, embedding, embedding_model, embedding_version, embedding_dimension)
  SELECT v.problem_code, v.problem_name, v.category, v.subcategory, v.layer, v.description, v.severity_min, v.severity_max, v.symptoms, v.pillar_id, '["automotive"]'::jsonb, array_fill(0, ARRAY[1536])::vector, NULL, NULL, NULL
  FROM (VALUES
('AUT-001', 'Capital Intensity Underestimated', 'Idea & Validation', 'Automotive Market Validation', 'external', 'The founder has not grasped how much money hardware or vehicle work requires before any revenue arrives, unlike a typical software idea.', 4, 8, '["No real cost estimate for tooling or manufacturing exists", "Comparing this idea''s capital needs to a software business instead of automotive", "No plan exists for the cash gap before the first vehicle or unit ships", "Underestimating how long it takes to reach first revenue", "No understanding of typical automotive or hardware burn rates"]'::jsonb, 2),
('AUT-002', 'Safety Certification Blind Spot', 'Idea & Validation', 'Automotive Market Validation', 'external', 'The idea does not yet account for mandatory safety or type-approval processes, such as ARAI or RTO requirements, that vehicles and mobility products must pass before sale.', 4, 9, '["Founder does not know which certifications apply to this product", "No timeline exists for the certification process", "Assuming certification is a quick formality rather than a real gate", "No budget has been set aside for certification costs"]'::jsonb, 2),
('AUT-003', 'Hardware Treated Like Software', 'Idea & Validation', 'Automotive Market Validation', 'external', 'The founder is applying fast, cheap iteration assumptions from software to something that requires physical tooling, molds, or vehicle parts.', 4, 8, '["Assuming fast, cheap iteration is possible, as with a software app", "No understanding of tooling or mold lead times", "Underestimating the cost of design changes once tooling exists", "No prototype-to-production plan distinguishing the two phases", "Founder''s technical background is software, not mechanical or hardware"]'::jsonb, 2),
('AUT-004', 'Supply Chain Dependency Not Mapped', 'Idea & Validation', 'Automotive Market Validation', 'external', 'The idea depends on sourcing components such as batteries, chips, or parts without knowing who supplies them or how reliable that supply actually is.', 4, 8, '["Key component suppliers have not been identified", "No backup supplier identified for critical parts", "Assuming component availability without checking lead times", "No understanding of import or customs dependency for key parts"]'::jsonb, 2),
('AUT-005', 'Prototype Does Not Reflect Manufacturable Design', 'Idea & Validation', 'Automotive Market Validation', 'external', 'The working prototype uses methods, such as 3D printing or hand-assembly, that cannot actually scale to real manufacturing.', 4, 8, '["No transition plan exists from prototype method to production method", "Design has not been reviewed for manufacturability", "No production-volume supplier has been engaged yet", "Assuming the prototype just needs to be scaled up as is", "Prototype relies on hand-assembly or one-off fabrication methods"]'::jsonb, 2),
('AUT-006', 'Real-World Testing Skipped', 'Idea & Validation', 'Automotive Market Validation', 'external', 'The product has not been tested in actual usage conditions, such as weather, terrain, or load, beyond a controlled setting.', 4, 8, '["No real-world testing has been conducted yet", "Testing has only been done in ideal or controlled conditions", "No plan exists to test across weather, terrain, or load variables", "Assuming lab or bench results will hold in the field"]'::jsonb, 2),
('AUT-007', 'Certification Process Not Actually Started', 'Idea & Validation', 'Automotive Market Validation', 'external', 'The founder knows what certification is needed but has not actually begun filing with the certifying body.', 4, 8, '["Certification requirements are known but filing has not started", "No application has been submitted to the certifying body", "Certification is being treated as something to handle later", "No dedicated owner is driving the certification process forward"]'::jsonb, 2),
('AUT-008', 'Early Customers Do Not Represent Real Buyers', 'Idea & Validation', 'Automotive Market Validation', 'external', 'Early testers are friends, family, or enthusiasts rather than the real paying customer base the business will need at scale.', 4, 8, '["Early testers are friends or personal network, not real customers", "Early testers are enthusiasts rather than typical buyers", "No paying customer outside the founder''s network has been converted yet", "Feedback collected is overly positive due to relationship bias", "No plan exists to test with someone outside the founder''s network"]'::jsonb, 2),
('AUT-009', 'Unit Economics Do Not Hold at Real Volume', 'Idea & Validation', 'Automotive Market Validation', 'external', 'Cost per unit at prototype scale has not been checked against what real production-volume costs would actually look like.', 4, 8, '["Cost per unit has only been calculated at prototype scale", "No real supplier quote has been obtained at production volume", "Assuming per-unit costs will drop at scale without verifying by how much", "Margin assumptions have not been tested against real volume pricing"]'::jsonb, 2),
('AUT-010', 'Manufacturing Quality Control at Scale', 'Idea & Validation', 'Automotive Market Validation', 'external', 'Defect rates rise as production volume increases, without a systematic quality control process to catch it.', 4, 8, '["No systematic quality control process exists", "Defect rate is not tracked", "No root-cause process exists for recurring defects", "Quality standards vary by shift or production line", "No quality checkpoint exists before units ship"]'::jsonb, 2),
('AUT-011', 'Service and Warranty Network Gaps', 'Idea & Validation', 'Automotive Market Validation', 'external', 'Vehicles or products already in the field need repair and service infrastructure that has not actually been built out.', 4, 8, '["No authorized service network has been built", "No spare parts distribution plan exists", "Warranty claims are handled ad hoc", "No visibility exists into service issues across the fleet"]'::jsonb, 2),
('AUT-012', 'Multi-Market Regulatory Complexity', 'Idea & Validation', 'Automotive Market Validation', 'external', 'Expanding to new states or countries brings a different regulatory regime each time, and this has not been systematically planned for.', 4, 8, '["No market-entry regulatory checklist exists", "Regulatory differences between markets have not been researched", "Assuming one certification covers multiple markets", "No dedicated owner tracks regulatory changes per market"]'::jsonb, 2),
('AUT-013', 'Recall and Safety Incident Readiness', 'Idea & Validation', 'Automotive Market Validation', 'external', 'No real plan exists for handling an actual safety issue or recall once a meaningful number of units are already in the field.', 5, 9, '["No recall response plan exists", "No way exists to trace which units are affected by a given issue", "No communication plan exists for notifying affected customers", "No process exists for escalating a safety issue internally", "Underestimating the cost and complexity of a real recall"]'::jsonb, 2),
('AUT-014', 'Component Sourcing Risk at Scale', 'Idea & Validation', 'Automotive Market Validation', 'external', 'Single-source component dependencies, which felt manageable at small scale, become genuinely dangerous as production volume grows.', 4, 8, '["Single-source dependency exists on a critical component", "No qualified backup supplier exists for critical components", "No visibility exists into a supplier''s own supply chain risk", "No safety stock exists for critical components"]'::jsonb, 2),
('AUT-015', 'Capital-Intensive Scaling Costs', 'Idea & Validation', 'Automotive Market Validation', 'external', 'Expanding production, including new facilities and tooling, requires large capital that is harder to raise than a typical software funding round.', 4, 9, '["No capital plan is tied to expansion milestones", "Underestimating capital needs for new facilities or tooling", "Assuming software-style funding rounds will cover hardware scaling", "No relationship exists with capital sources suited to hardware or manufacturing"]'::jsonb, 2)
  ) AS v(problem_code, problem_name, category, subcategory, layer, description, severity_min, severity_max, symptoms, pillar_id)
  RETURNING problem_id, problem_code
),
new_root_causes AS (
  INSERT INTO root_causes (root_cause_code, problem_id, root_cause_name, root_cause_category, explanation, confidence_weight, layer, primary_stage_group, industry_relevance, embedding, embedding_model, embedding_version, embedding_dimension)
  SELECT v.root_cause_code, p.problem_id, v.root_cause_name, v.root_cause_category, v.explanation, v.confidence_weight, v.layer, v.primary_stage_group, '["automotive"]'::jsonb, array_fill(0, ARRAY[1536])::vector, NULL, NULL, NULL
  FROM (VALUES
('RC-AUT-001', 'AUT-001', 'No Real Manufacturing Cost Estimate', 'Operational', 'No genuine cost estimate exists for tooling or manufacturing the product.', 0.65, 'external', 'Stage 0'),
('RC-AUT-002', 'AUT-001', 'Capital Needs Compared to Software', 'Knowledge', 'The founder is estimating capital requirements based on software business norms, not automotive or hardware norms.', 0.63, 'external', 'Stage 0'),
('RC-AUT-003', 'AUT-001', 'No Cash-Gap Plan Before First Unit Ships', 'Strategic', 'There is no plan for surviving the period between spending and first real revenue.', 0.65, 'external', 'Stage 0'),
('RC-AUT-004', 'AUT-001', 'Time to First Revenue Underestimated', 'Knowledge', 'The founder is underestimating how long it will realistically take to earn first revenue.', 0.62, 'external', 'Stage 0'),
('RC-AUT-005', 'AUT-001', 'No Understanding of Typical Burn Rates', 'Knowledge', 'The founder has not benchmarked spend against typical automotive or hardware startup burn rates.', 0.60, 'external', 'Stage 0'),
('RC-AUT-006', 'AUT-002', 'Applicable Certifications Unknown', 'Knowledge', 'The founder does not know which safety or regulatory certifications this product would legally require.', 0.68, 'external', 'Stage 0'),
('RC-AUT-007', 'AUT-002', 'No Certification Timeline', 'Operational', 'There is no realistic timeline for how long the certification process will take.', 0.65, 'external', 'Stage 0'),
('RC-AUT-008', 'AUT-002', 'Certification Treated as a Formality', 'Behavioural', 'Certification is being treated as a quick, minor step rather than a real project with its own timeline and cost.', 0.63, 'external', 'Stage 0'),
('RC-AUT-009', 'AUT-002', 'No Certification Budget Set Aside', 'Strategic', 'No specific budget has been allocated for certification costs.', 0.60, 'external', 'Stage 0'),
('RC-AUT-010', 'AUT-003', 'Assuming Software-Speed Iteration', 'Knowledge', 'The founder assumes fast, cheap iteration is possible, the way it is with software.', 0.65, 'external', 'Stage 0'),
('RC-AUT-011', 'AUT-003', 'Tooling Lead Times Not Understood', 'Knowledge', 'The founder does not understand how long it takes to build or modify tooling or molds.', 0.63, 'external', 'Stage 0'),
('RC-AUT-012', 'AUT-003', 'Design-Change Cost After Tooling Underestimated', 'Knowledge', 'The cost of changing a design once tooling exists is not understood.', 0.62, 'external', 'Stage 0'),
('RC-AUT-013', 'AUT-003', 'No Prototype-to-Production Plan', 'Strategic', 'There is no clear plan distinguishing the prototype phase from the production phase.', 0.62, 'external', 'Stage 0'),
('RC-AUT-014', 'AUT-003', 'Founder Background Is Software, Not Hardware', 'Knowledge', 'The founder''s own technical background is in software rather than mechanical or hardware engineering.', 0.58, 'external', 'Stage 0'),
('RC-AUT-015', 'AUT-004', 'Key Suppliers Not Identified', 'Operational', 'The suppliers for critical components have not actually been identified.', 0.65, 'external', 'Stage 0'),
('RC-AUT-016', 'AUT-004', 'No Backup Supplier for Critical Parts', 'Strategic', 'There is no alternative supplier identified for parts that are critical to the product.', 0.63, 'external', 'Stage 0'),
('RC-AUT-017', 'AUT-004', 'Component Lead Times Not Checked', 'Operational', 'Availability and lead time of key components has been assumed rather than verified.', 0.62, 'external', 'Stage 0'),
('RC-AUT-018', 'AUT-004', 'Import or Customs Dependency Not Understood', 'Knowledge', 'Dependency on imported parts, and the customs process involved, is not understood.', 0.60, 'external', 'Stage 0'),
('RC-AUT-019', 'AUT-005', 'No Prototype-to-Production Transition Plan', 'Strategic', 'There is no documented plan for moving from the prototype method to a real production method.', 0.65, 'external', 'Stage 0â†’1'),
('RC-AUT-020', 'AUT-005', 'Design Not Reviewed for Manufacturability', 'Operational', 'The design has not been reviewed by anyone with real manufacturing expertise.', 0.65, 'external', 'Stage 0â†’1'),
('RC-AUT-021', 'AUT-005', 'No Production-Volume Supplier Engaged', 'Operational', 'No supplier capable of production-volume manufacturing has actually been engaged.', 0.63, 'external', 'Stage 0â†’1'),
('RC-AUT-022', 'AUT-005', 'Assuming Prototype Just Needs Scaling Up', 'Knowledge', 'The founder assumes the current prototype method can simply be scaled without changing how it is made.', 0.62, 'external', 'Stage 0â†’1'),
('RC-AUT-023', 'AUT-005', 'Prototype Relies on One-Off Fabrication', 'Operational', 'The prototype depends on hand-assembly or one-off fabrication methods that cannot scale.', 0.63, 'external', 'Stage 0â†’1'),
('RC-AUT-024', 'AUT-006', 'No Real-World Testing Conducted', 'Operational', 'No testing has been done outside of a controlled setting.', 0.65, 'external', 'Stage 0â†’1'),
('RC-AUT-025', 'AUT-006', 'Testing Limited to Ideal Conditions', 'Operational', 'All testing so far has happened under best-case, ideal conditions.', 0.63, 'external', 'Stage 0â†’1'),
('RC-AUT-026', 'AUT-006', 'No Plan for Weather, Terrain, or Load Variation', 'Strategic', 'There is no plan to test the product across realistic variation in operating conditions.', 0.62, 'external', 'Stage 0â†’1'),
('RC-AUT-027', 'AUT-006', 'Assuming Lab Results Hold in the Field', 'Knowledge', 'The founder assumes results from lab or bench testing will translate directly to real-world use.', 0.62, 'external', 'Stage 0â†’1'),
('RC-AUT-028', 'AUT-007', 'Certification Requirements Known but Filing Not Started', 'Operational', 'The founder knows what is required but has not actually begun the filing process.', 0.65, 'external', 'Stage 0â†’1'),
('RC-AUT-029', 'AUT-007', 'No Application Submitted', 'Operational', 'No formal application has actually been submitted to the certifying body.', 0.65, 'external', 'Stage 0â†’1'),
('RC-AUT-030', 'AUT-007', 'Certification Treated as a Later Task', 'Behavioural', 'Certification keeps getting deferred as something to handle later rather than now.', 0.62, 'external', 'Stage 0â†’1'),
('RC-AUT-031', 'AUT-007', 'No Dedicated Certification Owner', 'Operational', 'Nobody is specifically responsible for pushing the certification process forward.', 0.60, 'external', 'Stage 0â†’1'),
('RC-AUT-032', 'AUT-008', 'Early Testers Are Personal Network', 'Operational', 'The people testing the product so far are mostly friends or the founder''s own network.', 0.65, 'external', 'Stage 0â†’1'),
('RC-AUT-033', 'AUT-008', 'Early Testers Are Enthusiasts, Not Typical Buyers', 'Knowledge', 'Current testers are enthusiasts rather than representative of the real target buyer.', 0.62, 'external', 'Stage 0â†’1'),
('RC-AUT-034', 'AUT-008', 'No Outside Paying Customer Converted', 'Operational', 'No paying customer outside the founder''s own network has been converted yet.', 0.65, 'external', 'Stage 0â†’1'),
('RC-AUT-035', 'AUT-008', 'Feedback Skewed by Relationship Bias', 'Behavioural', 'Feedback from testers may be overly positive because they do not want to disappoint the founder.', 0.60, 'external', 'Stage 0â†’1'),
('RC-AUT-036', 'AUT-008', 'No Plan to Test Outside the Network', 'Strategic', 'There is no plan to specifically test with someone outside the founder''s existing network.', 0.60, 'external', 'Stage 0â†’1'),
('RC-AUT-037', 'AUT-009', 'Unit Cost Only Calculated at Prototype Scale', 'Operational', 'Cost per unit has only ever been calculated at the small, prototype scale.', 0.65, 'external', 'Stage 0â†’1'),
('RC-AUT-038', 'AUT-009', 'No Production-Volume Supplier Quote', 'Operational', 'No real quote has been obtained from a supplier at the actual production volume needed.', 0.65, 'external', 'Stage 0â†’1'),
('RC-AUT-039', 'AUT-009', 'Assuming Costs Drop at Scale Without Verification', 'Knowledge', 'The founder assumes per-unit cost will fall at scale without confirming by how much.', 0.62, 'external', 'Stage 0â†’1'),
('RC-AUT-040', 'AUT-009', 'Margin Assumptions Untested at Real Pricing', 'Strategic', 'Margin assumptions have not been checked against what real volume pricing would actually deliver.', 0.62, 'external', 'Stage 0â†’1'),
('RC-AUT-041', 'AUT-010', 'No Systematic QC Process', 'Operational', 'There is no consistent, documented quality control process applied to production.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-AUT-042', 'AUT-010', 'Defect Rate Not Tracked', 'Operational', 'The actual defect rate is not being systematically measured.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-AUT-043', 'AUT-010', 'No Root-Cause Process for Defects', 'Operational', 'Recurring defects are not traced back to a root cause in any systematic way.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-AUT-044', 'AUT-010', 'Quality Standards Vary by Shift or Line', 'Operational', 'Quality outcomes differ depending on which shift or production line handled the unit.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-AUT-045', 'AUT-010', 'No Pre-Ship Quality Checkpoint', 'Operational', 'There is no final quality checkpoint before a unit ships to a customer.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-AUT-046', 'AUT-011', 'No Authorized Service Network', 'Operational', 'No formal network of authorized service providers has been built out.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-AUT-047', 'AUT-011', 'No Spare Parts Distribution Plan', 'Operational', 'There is no plan for getting spare parts to wherever the product actually is.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-AUT-048', 'AUT-011', 'Warranty Claims Handled Ad Hoc', 'Operational', 'Warranty claims are processed case by case rather than through a defined process.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-AUT-049', 'AUT-011', 'No Fleet-Wide Service Visibility', 'Operational', 'There is no visibility into service issues occurring across the whole fleet of units.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-AUT-050', 'AUT-012', 'No Market-Entry Regulatory Checklist', 'Strategic', 'There is no checklist defining what regulatory work is needed before entering a new market.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-AUT-051', 'AUT-012', 'Market Regulatory Differences Not Researched', 'Knowledge', 'Differences in regulation between target markets have not been researched.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-AUT-052', 'AUT-012', 'Assuming One Certification Covers Multiple Markets', 'Knowledge', 'It is assumed a single certification will be valid across multiple markets, without confirming this.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-AUT-053', 'AUT-012', 'No Per-Market Regulatory Owner', 'Operational', 'Nobody specifically tracks regulatory changes for each market the business operates in.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-AUT-054', 'AUT-013', 'No Recall Response Plan', 'Strategic', 'There is no plan for how a recall would actually be executed if one were needed.', 0.68, 'external', 'Stage 1â†’10+'),
('RC-AUT-055', 'AUT-013', 'No Unit Traceability', 'Operational', 'There is no way to trace which specific units are affected by a given issue.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-AUT-056', 'AUT-013', 'No Customer Communication Plan for Safety Issues', 'Strategic', 'There is no plan for communicating with affected customers if a safety issue arose.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-AUT-057', 'AUT-013', 'No Internal Escalation Process for Safety Issues', 'Operational', 'There is no clear process for escalating a safety concern internally before it grows.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-AUT-058', 'AUT-013', 'Recall Cost and Complexity Underestimated', 'Knowledge', 'The true cost and operational complexity of a real recall is not well understood.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-AUT-059', 'AUT-014', 'Single-Source Dependency on Critical Component', 'Strategic', 'A critical component depends entirely on a single supplier.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-AUT-060', 'AUT-014', 'No Qualified Backup Supplier', 'Operational', 'No alternative, qualified supplier exists for critical components.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-AUT-061', 'AUT-014', 'Supplier''s Own Risk Not Understood', 'Knowledge', 'There is no visibility into the risks within the supplier''s own supply chain.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-AUT-062', 'AUT-014', 'No Safety Stock for Critical Components', 'Operational', 'No buffer stock exists for components that are critical to production continuity.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-AUT-063', 'AUT-015', 'No Capital Plan Tied to Expansion Milestones', 'Strategic', 'There is no capital plan explicitly linked to specific expansion milestones.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-AUT-064', 'AUT-015', 'Facility or Tooling Capital Needs Underestimated', 'Knowledge', 'The capital required for new facilities or tooling has been underestimated.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-AUT-065', 'AUT-015', 'Assuming Software-Style Funding Will Cover Hardware Scaling', 'Knowledge', 'The founder assumes typical software startup funding patterns will cover hardware scaling needs.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-AUT-066', 'AUT-015', 'No Relationships With Hardware-Suited Capital Sources', 'Operational', 'No relationships exist with capital sources genuinely suited to hardware or manufacturing scaling.', 0.60, 'external', 'Stage 1â†’10+')
  ) AS v(root_cause_code, problem_code, root_cause_name, root_cause_category, explanation, confidence_weight, layer, primary_stage_group)
  JOIN new_problems p ON p.problem_code = v.problem_code
  RETURNING root_cause_id, root_cause_code
),
new_questions AS (
  INSERT INTO questions (question_code, category, question_text, problem_id, root_cause_id, question_type, difficulty_level, priority, is_distress_tagged, industry_relevance, embedding, primary_stage_group, embedding_model, embedding_version, embedding_dimension)
  SELECT v.question_code, 'Idea & Validation', v.question_text, p.problem_id, rc.root_cause_id, 'open_text', v.difficulty_level, v.priority, false, '["automotive"]'::jsonb, array_fill(0, ARRAY[1536])::vector, v.stage_group, NULL, NULL, NULL
  FROM (VALUES
('S0-AUT-001', 'AUT-001', 'RC-AUT-001', 'Do you know roughly how much money it takes to get from prototype to your first sellable vehicle or unit?', 2, 'CORE', 'Stage 0'),
('S0-AUT-002', 'AUT-001', 'RC-AUT-002', 'Are you estimating this business''s costs based on what a software idea would need?', 2, 'CORE', 'Stage 0'),
('S0-AUT-003', 'AUT-001', 'RC-AUT-003', 'Do you have a plan for surviving the cash gap between building this and actually selling it?', 2, 'CORE', 'Stage 0'),
('S0-AUT-004', 'AUT-001', 'RC-AUT-004', 'How long do you realistically think it will take to get your first paying customer?', 2, 'CORE', 'Stage 0'),
('S0-AUT-005', 'AUT-001', 'RC-AUT-005', 'Have you looked at what similar hardware or automotive companies typically spend before earning revenue?', 3, 'CORE', 'Stage 0'),
('S0-AUT-006', 'AUT-002', 'RC-AUT-006', 'Have you checked which safety certifications your product would legally need before it can be sold?', 2, 'CORE', 'Stage 0'),
('S0-AUT-007', 'AUT-002', 'RC-AUT-007', 'Do you know how long the certification process actually takes for something like this?', 2, 'CORE', 'Stage 0'),
('S0-AUT-008', 'AUT-002', 'RC-AUT-008', 'Are you treating certification as a quick formality, or as a real project with its own timeline and cost?', 2, 'CORE', 'Stage 0'),
('S0-AUT-009', 'AUT-003', 'RC-AUT-010', 'Are you assuming you can iterate on this as fast as a software app, even though it involves physical parts?', 2, 'CORE', 'Stage 0'),
('S0-AUT-010', 'AUT-003', 'RC-AUT-011', 'Do you know how long it takes to build or modify a mold or tool once you''ve committed to a design?', 2, 'CORE', 'Stage 0'),
('S0-AUT-011', 'AUT-003', 'RC-AUT-012', 'If you needed to change the design after tooling was built, do you know what that would cost you?', 3, 'CORE', 'Stage 0'),
('S0-AUT-012', 'AUT-003', 'RC-AUT-013', 'Do you have a clear plan for what happens between a working prototype and something you can actually manufacture at volume?', 2, 'CORE', 'Stage 0'),
('S0-AUT-013', 'AUT-004', 'RC-AUT-015', 'Do you know who would actually supply the key components this idea depends on?', 2, 'CORE', 'Stage 0'),
('S0-AUT-014', 'AUT-004', 'RC-AUT-016', 'If your main supplier couldn''t deliver, do you have another one in mind?', 2, 'SUPPLEMENTARY', 'Stage 0'),
('S0-AUT-015', 'AUT-004', 'RC-AUT-017', 'Have you checked how long it actually takes to get the parts you need, or are you assuming they''re readily available?', 2, 'CORE', 'Stage 0'),
('S01-AUT-001', 'AUT-005', 'RC-AUT-019', 'Can your current prototype actually be manufactured at volume, or does it rely on methods that won''t scale?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AUT-002', 'AUT-005', 'RC-AUT-020', 'Has anyone with real manufacturing experience reviewed your design for manufacturability?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AUT-003', 'AUT-005', 'RC-AUT-021', 'Have you engaged a supplier who can actually produce at the volume you''ll eventually need?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AUT-004', 'AUT-005', 'RC-AUT-022', 'Are you assuming your prototype just needs to be built bigger or faster, without changing how it''s made?', 3, 'CORE', 'Stage 0â†’1'),
('S01-AUT-005', 'AUT-006', 'RC-AUT-024', 'Has this been tested in real-world conditions, or only in a controlled setting?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AUT-006', 'AUT-006', 'RC-AUT-025', 'Has your testing so far only happened under ideal, best-case conditions?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AUT-007', 'AUT-006', 'RC-AUT-026', 'Do you have a plan to test this across different weather, terrain, or load conditions?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AUT-008', 'AUT-006', 'RC-AUT-027', 'Are you assuming your lab or bench results will hold up once this is used in the real world?', 3, 'CORE', 'Stage 0â†’1'),
('S01-AUT-009', 'AUT-007', 'RC-AUT-029', 'Have you actually filed anything with the certifying body, or is this still just research?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AUT-010', 'AUT-007', 'RC-AUT-030', 'Is certification something you''re actively working on, or something you keep planning to start?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AUT-011', 'AUT-007', 'RC-AUT-031', 'Is there someone specifically responsible for pushing your certification forward?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AUT-012', 'AUT-007', 'RC-AUT-028', 'What''s actually stopping you from submitting your certification application this month?', 3, 'SUPPLEMENTARY', 'Stage 0â†’1'),
('S01-AUT-013', 'AUT-008', 'RC-AUT-032', 'Are your early testers real potential customers, or mostly friends and your own network?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AUT-014', 'AUT-008', 'RC-AUT-033', 'Are the people testing this enthusiasts, or the kind of buyer you''d actually need at scale?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AUT-015', 'AUT-008', 'RC-AUT-034', 'Have you converted a single paying customer who wasn''t already connected to you personally?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AUT-016', 'AUT-008', 'RC-AUT-035', 'Could the positive feedback you''re getting be because people testing this don''t want to disappoint you?', 3, 'CORE', 'Stage 0â†’1'),
('S01-AUT-017', 'AUT-008', 'RC-AUT-036', 'Do you have a plan to test this with someone completely outside your existing network?', 2, 'SUPPLEMENTARY', 'Stage 0â†’1'),
('S01-AUT-018', 'AUT-009', 'RC-AUT-037', 'Does your cost per unit at prototype scale look anything like what it would be at real production volume?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AUT-019', 'AUT-009', 'RC-AUT-038', 'Have you gotten a real supplier quote at the volume you''d actually need to sell at?', 2, 'CORE', 'Stage 0â†’1'),
('S01-AUT-020', 'AUT-009', 'RC-AUT-039', 'Are you assuming your per-unit cost will drop at scale without knowing by how much?', 2, 'CORE', 'Stage 0â†’1'),
('S10-AUT-001', 'AUT-010', 'RC-AUT-041', 'Do you have any systematic quality control process, or does it depend on who''s checking that day?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-002', 'AUT-010', 'RC-AUT-042', 'Do you track your defect rate, or would you have to go find out?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-003', 'AUT-010', 'RC-AUT-043', 'When a defect shows up, is there a process to trace it back to its root cause?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-004', 'AUT-010', 'RC-AUT-044', 'Does quality look the same across every shift or production line, or does it vary?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-005', 'AUT-010', 'RC-AUT-045', 'Is there a checkpoint that catches quality problems before a unit ships?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-006', 'AUT-011', 'RC-AUT-046', 'If your product breaks in a city you don''t have a service center in, what happens to that customer?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-007', 'AUT-011', 'RC-AUT-047', 'Do you have a plan for getting spare parts to wherever your product actually is?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-008', 'AUT-011', 'RC-AUT-048', 'Are warranty claims handled through a real process, or dealt with case by case?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-009', 'AUT-011', 'RC-AUT-049', 'Do you have visibility into service issues happening across your whole fleet, or only what gets reported to you directly?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-010', 'AUT-012', 'RC-AUT-050', 'Do you have a checklist for what regulatory work is needed before entering a new market?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-011', 'AUT-012', 'RC-AUT-051', 'Have you researched what changes when you sell into a new state or country?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-012', 'AUT-012', 'RC-AUT-052', 'Are you assuming one certification will cover you in multiple markets?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-013', 'AUT-012', 'RC-AUT-053', 'Is someone specifically tracking regulatory changes in each market you operate in?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-014', 'AUT-013', 'RC-AUT-054', 'If you had to recall units already sold, do you have any plan for how that would actually work?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-015', 'AUT-013', 'RC-AUT-055', 'If one unit had a defect, could you trace exactly which other units share that same issue?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-016', 'AUT-013', 'RC-AUT-056', 'Do you have a plan for how you''d communicate with affected customers if a safety issue came up?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-017', 'AUT-013', 'RC-AUT-057', 'Is there a clear process for escalating a safety concern internally before it becomes a crisis?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-018', 'AUT-013', 'RC-AUT-058', 'Have you thought through how much a real recall would actually cost you, in money and time?', 3, 'SUPPLEMENTARY', 'Stage 1â†’10+'),
('S10-AUT-019', 'AUT-014', 'RC-AUT-059', 'Is there a single supplier that, if they failed, would stop your whole production line?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-020', 'AUT-014', 'RC-AUT-060', 'Do you have a qualified backup supplier for your most critical components?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-021', 'AUT-014', 'RC-AUT-061', 'Do you know how vulnerable your own suppliers are to their own supply chain risks?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-022', 'AUT-014', 'RC-AUT-062', 'Do you keep any safety stock of critical components, or do you rely on just-in-time delivery?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-023', 'AUT-015', 'RC-AUT-063', 'Do you know how much capital your next expansion phase will need, and where it will come from?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-024', 'AUT-015', 'RC-AUT-064', 'Have you underestimated what it costs to add new facilities or tooling as you''ve scaled?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-AUT-025', 'AUT-015', 'RC-AUT-065', 'Are you assuming your funding approach can look like a typical software startup''s, even though this is hardware?', 3, 'CORE', 'Stage 1â†’10+')
  ) AS v(question_code, problem_code, root_cause_code, question_text, difficulty_level, priority, stage_group)
  JOIN new_problems p ON p.problem_code = v.problem_code
  JOIN new_root_causes rc ON rc.root_cause_code = v.root_cause_code
  RETURNING question_id, question_code
),
new_tags AS (
  INSERT INTO question_tag_mapping (question_id, tag_id)
  SELECT q.question_id, v.tag_id
  FROM (VALUES
('S0-AUT-001', 84), ('S0-AUT-002', 84), ('S0-AUT-003', 84), ('S0-AUT-004', 84), ('S0-AUT-005', 84),
('S0-AUT-006', 33), ('S0-AUT-007', 33), ('S0-AUT-008', 33),
('S0-AUT-009', 30), ('S0-AUT-010', 30), ('S0-AUT-011', 30), ('S0-AUT-012', 30),
('S0-AUT-013', 12), ('S0-AUT-014', 12), ('S0-AUT-015', 12),
('S01-AUT-001', 33), ('S01-AUT-002', 33), ('S01-AUT-003', 33), ('S01-AUT-004', 33),
('S01-AUT-005', 36), ('S01-AUT-006', 36), ('S01-AUT-007', 36), ('S01-AUT-008', 36),
('S01-AUT-009', 4), ('S01-AUT-010', 4), ('S01-AUT-011', 4), ('S01-AUT-012', 4),
('S01-AUT-013', 2), ('S01-AUT-014', 2), ('S01-AUT-015', 2), ('S01-AUT-016', 2), ('S01-AUT-017', 2),
('S01-AUT-018', 84), ('S01-AUT-019', 84), ('S01-AUT-020', 84),
('S10-AUT-001', 33), ('S10-AUT-002', 33), ('S10-AUT-003', 33), ('S10-AUT-004', 33), ('S10-AUT-005', 33),
('S10-AUT-006', 12), ('S10-AUT-007', 12), ('S10-AUT-008', 12), ('S10-AUT-009', 12),
('S10-AUT-010', 4), ('S10-AUT-011', 4), ('S10-AUT-012', 4), ('S10-AUT-013', 4),
('S10-AUT-014', 36), ('S10-AUT-015', 36), ('S10-AUT-016', 36), ('S10-AUT-017', 36), ('S10-AUT-018', 36),
('S10-AUT-019', 12), ('S10-AUT-020', 12), ('S10-AUT-021', 12), ('S10-AUT-022', 12),
('S10-AUT-023', 84), ('S10-AUT-024', 84), ('S10-AUT-025', 84)
  ) AS v(question_code, tag_id)
  JOIN new_questions q ON q.question_code = v.question_code
  RETURNING mapping_id
),
new_interventions AS (
  INSERT INTO interventions (intervention_code, problem_id, root_cause_ids, secondary_root_cause_ids, capability_domain, section, recommended_frameworks, framework_codes, immediate_next_steps, stage_relevance, industry_relevance, design_principles)
  SELECT v.intervention_code, p.problem_id, v.root_cause_ids, '[]'::jsonb, v.capability_domain, v.section, v.recommended_frameworks, NULL, v.immediate_next_steps, v.stage_relevance, '["automotive"]'::jsonb, v.design_principles
  FROM (VALUES
('INT-AUT-001', 'AUT-001', '["RC-AUT-001", "RC-AUT-002"]'::jsonb, 'Financial Planning', 'Ideation â€” Automotive Capital Planning', '[{"name": "Manufacturing Cost Estimation", "brief": "Getting a real, quoted cost estimate before writing a business plan."}]'::jsonb, '["Get a real quote for tooling and manufacturing from at least one vendor.", "Compare that number against your current assumptions.", "Revise your business plan based on the real number."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-002', 'AUT-001', '["RC-AUT-003", "RC-AUT-004"]'::jsonb, 'Financial Planning', 'Ideation â€” Automotive Capital Planning', '[{"name": "Hardware Runway Planning", "brief": "Building a cash runway plan that accounts for realistic hardware development timelines."}]'::jsonb, '["Map your expected timeline to first revenue.", "Calculate the cash needed to survive that full period.", "Build a 12-18 month runway plan around that number."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-003', 'AUT-001', '["RC-AUT-005"]'::jsonb, 'Financial Planning', 'Ideation â€” Automotive Capital Planning', '[{"name": "Burn Rate Benchmarking", "brief": "Comparing your spend plan against real hardware and automotive startup benchmarks."}]'::jsonb, '["Find 2-3 comparable hardware or automotive startups.", "Research their known spend before first revenue.", "Adjust your own plan based on that benchmark."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-004', 'AUT-002', '["RC-AUT-006", "RC-AUT-007"]'::jsonb, 'Regulatory Compliance', 'Ideation â€” Automotive Capital Planning', '[{"name": "Certification Requirement Mapping", "brief": "Listing every certification legally required and its real timeline."}]'::jsonb, '["List every certification your product legally needs.", "Research the real timeline for each one.", "Build these timelines into your overall project plan."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-005', 'AUT-002', '["RC-AUT-008", "RC-AUT-009"]'::jsonb, 'Regulatory Compliance', 'Ideation â€” Automotive Capital Planning', '[{"name": "Certification as Core Workstream", "brief": "Treating certification as a real, budgeted, resourced project rather than an afterthought."}]'::jsonb, '["Assign a specific budget for certification costs.", "Assign someone accountable for the certification process.", "Treat certification as a core milestone, not a formality."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-006', 'AUT-003', '["RC-AUT-013", "RC-AUT-014"]'::jsonb, 'Product Development', 'Ideation â€” Automotive Capital Planning', '[{"name": "Prototype-to-Production Roadmap", "brief": "Explicitly mapping the two distinct phases of hardware development."}]'::jsonb, '["Define what counts as your prototype milestone.", "Define what counts as your production milestone.", "Identify the specific gap work needed between the two."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-007', 'AUT-003', '["RC-AUT-010", "RC-AUT-011"]'::jsonb, 'Product Development', 'Ideation â€” Automotive Capital Planning', '[{"name": "Tooling Lead Time Quote", "brief": "Getting a real quote on tooling timeline and cost before finalizing a design."}]'::jsonb, '["Get a real tooling quote before finalizing your design.", "Ask specifically about lead time, not just cost.", "Build this lead time into your overall project timeline."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-008', 'AUT-003', '["RC-AUT-012"]'::jsonb, 'Product Development', 'Ideation â€” Automotive Capital Planning', '[{"name": "Hardware Expertise Advisory", "brief": "Bringing in real mechanical or hardware experience before committing further."}]'::jsonb, '["Identify one person with real hardware or mechanical experience.", "Have them review your current design and plan.", "Act on at least one piece of feedback before proceeding."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-009', 'AUT-004', '["RC-AUT-015", "RC-AUT-017"]'::jsonb, 'Supply Chain', 'Ideation â€” Automotive Capital Planning', '[{"name": "Supply Chain Mapping", "brief": "Mapping every critical component and its real supplier before building."}]'::jsonb, '["List every critical component your product depends on.", "Identify a real supplier for each one.", "Check real lead times, not assumed ones."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-010', 'AUT-004', '["RC-AUT-016", "RC-AUT-018"]'::jsonb, 'Supply Chain', 'Ideation â€” Automotive Capital Planning', '[{"name": "Backup Supplier Identification", "brief": "Identifying an alternative supplier for every critical, hard-to-source component."}]'::jsonb, '["Identify your single most critical, hardest-to-source component.", "Find at least one backup supplier for it.", "Note any import or customs dependency involved."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-011', 'AUT-005', '["RC-AUT-020", "RC-AUT-023"]'::jsonb, 'Manufacturing Readiness', 'Validation â€” Automotive Prototype Testing', '[{"name": "Manufacturability Review", "brief": "Getting a real manufacturer to review the design before proceeding."}]'::jsonb, '["Find one real manufacturer to review your design.", "Get specific feedback on what would need to change for volume production.", "Revise your design based on that feedback."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-012', 'AUT-005', '["RC-AUT-021"]'::jsonb, 'Manufacturing Readiness', 'Validation â€” Automotive Prototype Testing', '[{"name": "Production-Volume Supplier Quote", "brief": "Getting a real quote from a supplier capable of actual production volume."}]'::jsonb, '["Identify a supplier capable of your target volume.", "Request a real quote at that volume.", "Compare it against your current cost assumptions."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-013', 'AUT-005', '["RC-AUT-019", "RC-AUT-022"]'::jsonb, 'Manufacturing Readiness', 'Validation â€” Automotive Prototype Testing', '[{"name": "Prototype-to-Production Transition Plan", "brief": "Documenting the specific changes needed to move from prototype method to production method."}]'::jsonb, '["List every part of your prototype made using a non-scalable method.", "Identify the real production method for each.", "Document the transition plan and timeline."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-014', 'AUT-006', '["RC-AUT-024", "RC-AUT-025"]'::jsonb, 'Product Validation', 'Validation â€” Automotive Prototype Testing', '[{"name": "Real-World Field Test", "brief": "Running one genuine field test under actual operating conditions."}]'::jsonb, '["Identify one real-world condition your lab testing hasn''t covered.", "Run a field test under that specific condition.", "Document what broke or underperformed versus lab results."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-015', 'AUT-006', '["RC-AUT-026", "RC-AUT-027"]'::jsonb, 'Product Validation', 'Validation â€” Automotive Prototype Testing', '[{"name": "Variability Test Plan", "brief": "Designing a structured test plan covering weather, terrain, and load variation."}]'::jsonb, '["List the realistic range of conditions this product will face.", "Design a specific test for each condition.", "Prioritize testing the conditions most likely to cause failure."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-016', 'AUT-007', '["RC-AUT-028", "RC-AUT-029"]'::jsonb, 'Regulatory Compliance', 'Validation â€” Automotive Prototype Testing', '[{"name": "Certification Filing Action", "brief": "Actually submitting the certification application rather than continuing to research it."}]'::jsonb, '["Identify exactly what''s needed to submit your application today.", "Submit the application this month.", "Set a follow-up date to check on progress."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-017', 'AUT-007', '["RC-AUT-030", "RC-AUT-031"]'::jsonb, 'Regulatory Compliance', 'Validation â€” Automotive Prototype Testing', '[{"name": "Certification Ownership Assignment", "brief": "Assigning a specific, accountable owner to drive certification progress weekly."}]'::jsonb, '["Assign one person to own certification progress.", "Set a weekly check-in on certification status.", "Track this as a core milestone, not a side task."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-018', 'AUT-008', '["RC-AUT-032", "RC-AUT-034"]'::jsonb, 'Customer Validation', 'Validation â€” Automotive Prototype Testing', '[{"name": "Outside-Network Customer Conversion", "brief": "Finding and converting one paying customer entirely outside the founder''s personal network."}]'::jsonb, '["Identify one prospect with no personal connection to you.", "Pitch and attempt to close them as a paying customer.", "Document what was different about this conversation."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-019', 'AUT-008', '["RC-AUT-033", "RC-AUT-035"]'::jsonb, 'Customer Validation', 'Validation â€” Automotive Prototype Testing', '[{"name": "Blind Feedback Session", "brief": "Getting feedback from a tester who does not know the founder personally, to remove relationship bias."}]'::jsonb, '["Find a tester with no personal relationship to you.", "Have someone else run the feedback session, if possible.", "Compare this feedback against feedback from your personal network."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-020', 'AUT-008', '["RC-AUT-036"]'::jsonb, 'Customer Validation', 'Validation â€” Automotive Prototype Testing', '[{"name": "Network vs Non-Network Conversion Tracking", "brief": "Explicitly tracking conversion rates separately for inside-network versus outside-network prospects."}]'::jsonb, '["Tag every prospect as inside or outside your network.", "Track conversion rate separately for each group.", "Use the outside-network number as your real validation signal."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-021', 'AUT-009', '["RC-AUT-037", "RC-AUT-038"]'::jsonb, 'Financial Planning', 'Validation â€” Automotive Prototype Testing', '[{"name": "Real Volume Cost Quote", "brief": "Getting a real supplier quote at your actual target production volume."}]'::jsonb, '["Identify your realistic target production volume.", "Get a real quote from a supplier at that volume.", "Recalculate your unit economics using that number."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-022', 'AUT-009', '["RC-AUT-039", "RC-AUT-040"]'::jsonb, 'Financial Planning', 'Validation â€” Automotive Prototype Testing', '[{"name": "Real-Pricing Margin Recalculation", "brief": "Recalculating margin assumptions using real volume pricing instead of prototype-scale pricing."}]'::jsonb, '["Replace prototype-scale costs with real volume-quote costs.", "Recalculate your margin using those real numbers.", "Flag any margin assumption that no longer holds."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-023', 'AUT-010', '["RC-AUT-041", "RC-AUT-045"]'::jsonb, 'Quality Management', 'Growth â€” Manufacturing Quality at Scale', '[{"name": "Quality Checkpoint System", "brief": "Building a systematic quality control process with a defined pre-ship checkpoint."}]'::jsonb, '["Define one clear quality checkpoint before shipping.", "Document the standard every unit must meet.", "Train whoever checks quality against that standard."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-024', 'AUT-010', '["RC-AUT-042", "RC-AUT-043", "RC-AUT-044"]'::jsonb, 'Quality Management', 'Growth â€” Manufacturing Quality at Scale', '[{"name": "Defect Tracking and Root Cause Analysis", "brief": "Systematically tracking defects and tracing recurring ones to their root cause."}]'::jsonb, '["Start tracking defect rate as a real number.", "Investigate the root cause of your most frequent defect.", "Standardize quality practice across every shift and line."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-025', 'AUT-011', '["RC-AUT-046", "RC-AUT-049"]'::jsonb, 'Service Operations', 'Growth â€” Service & Warranty Network', '[{"name": "Minimum Viable Service Network", "brief": "Building the smallest workable service network before expanding into a new region."}]'::jsonb, '["Identify the minimum service coverage needed for your next region.", "Set up at least one authorized service point there.", "Build a way to see service issues across your fleet."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-026', 'AUT-011', '["RC-AUT-047", "RC-AUT-048"]'::jsonb, 'Service Operations', 'Growth â€” Service & Warranty Network', '[{"name": "Centralized Spare Parts and Warranty Tracking", "brief": "A shared system to track spare parts distribution and warranty claims consistently."}]'::jsonb, '["Set up one central system for tracking warranty claims.", "Map your spare parts distribution against where customers actually are.", "Standardize the warranty claim process."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-027', 'AUT-012', '["RC-AUT-050", "RC-AUT-051"]'::jsonb, 'Regulatory Compliance', 'Growth â€” Multi-Market Regulatory Readiness', '[{"name": "Market-Entry Regulatory Checklist", "brief": "Building a reusable checklist for regulatory requirements before entering any new market."}]'::jsonb, '["Research the regulatory requirements for your next target market.", "Build a reusable checklist template from that research.", "Confirm this differs from your current market''s requirements."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-028', 'AUT-012', '["RC-AUT-052", "RC-AUT-053"]'::jsonb, 'Regulatory Compliance', 'Growth â€” Multi-Market Regulatory Readiness', '[{"name": "Per-Market Regulatory Ownership", "brief": "Assigning a dedicated owner to track regulatory changes in each active market."}]'::jsonb, '["Confirm whether your current certification actually covers your next market.", "Assign someone to track regulatory changes per market.", "Set a recurring review of regulatory status."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-029', 'AUT-013', '["RC-AUT-054", "RC-AUT-058"]'::jsonb, 'Safety & Risk Management', 'Growth â€” Recall & Safety Readiness', '[{"name": "Recall Response Plan", "brief": "Writing a real recall response plan before it is ever needed."}]'::jsonb, '["Draft a step-by-step recall response plan.", "Estimate the real cost and time a recall would take.", "Review this plan with your leadership team."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-030', 'AUT-013', '["RC-AUT-055", "RC-AUT-056", "RC-AUT-057"]'::jsonb, 'Safety & Risk Management', 'Growth â€” Recall & Safety Readiness', '[{"name": "Unit Traceability and Escalation System", "brief": "Building the ability to trace affected units and escalate safety issues quickly."}]'::jsonb, '["Build a system to trace units by batch or serial number.", "Define a clear internal escalation path for safety concerns.", "Draft a customer communication template for a safety issue."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-031', 'AUT-014', '["RC-AUT-059", "RC-AUT-060"]'::jsonb, 'Supply Chain', 'Growth â€” Component Sourcing Risk', '[{"name": "Single-Source Risk Mitigation", "brief": "Identifying and de-risking every component with only one qualified supplier."}]'::jsonb, '["List every component with only one supplier.", "Qualify at least one backup supplier for the riskiest one.", "Prioritize the rest based on risk and cost."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-032', 'AUT-014', '["RC-AUT-061", "RC-AUT-062"]'::jsonb, 'Supply Chain', 'Growth â€” Component Sourcing Risk', '[{"name": "Safety Stock Policy", "brief": "Establishing a buffer stock policy for components critical to production continuity."}]'::jsonb, '["Identify your most production-critical components.", "Set a safety stock level for each.", "Ask your key suppliers about their own supply chain risk."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-033', 'AUT-015', '["RC-AUT-063", "RC-AUT-064"]'::jsonb, 'Financial Planning', 'Growth â€” Capital-Intensive Scaling', '[{"name": "Milestone-Linked Capital Plan", "brief": "Building a capital plan explicitly tied to specific expansion milestones."}]'::jsonb, '["List your next 2-3 expansion milestones.", "Estimate the real capital needed for each.", "Build a funding plan tied directly to those milestones."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-AUT-034', 'AUT-015', '["RC-AUT-065", "RC-AUT-066"]'::jsonb, 'Financial Planning', 'Growth â€” Capital-Intensive Scaling', '[{"name": "Hardware-Suited Capital Relationships", "brief": "Building relationships with capital sources genuinely suited to hardware and manufacturing scaling."}]'::jsonb, '["Identify capital sources with real hardware/manufacturing experience.", "Build a relationship with at least one before you need funding.", "Reassess whether software-style funding assumptions actually apply to you."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb)
  ) AS v(intervention_code, problem_code, root_cause_ids, capability_domain, section, recommended_frameworks, immediate_next_steps, stage_relevance, design_principles)
  JOIN new_problems p ON p.problem_code = v.problem_code
  RETURNING intervention_id, intervention_code
)
SELECT
  (SELECT COUNT(*) FROM new_problems) as problems_inserted,
  (SELECT COUNT(*) FROM new_root_causes) as root_causes_inserted,
  (SELECT COUNT(*) FROM new_questions) as questions_inserted,
  (SELECT COUNT(*) FROM new_tags) as tags_inserted,
  (SELECT COUNT(*) FROM new_interventions) as interventions_inserted;"""),

        ('BFSI / FinTech', 'fintech', 'BFS', r"""WITH new_problems AS (
  INSERT INTO problems (problem_code, problem_name, category, subcategory, layer, description, severity_min, severity_max, symptoms, pillar_id, industry_relevance, embedding, embedding_model, embedding_version, embedding_dimension)
  SELECT v.problem_code, v.problem_name, v.category, v.subcategory, v.layer, v.description, v.severity_min, v.severity_max, v.symptoms, v.pillar_id, '["fintech"]'::jsonb, array_fill(0, ARRAY[1536])::vector, NULL, NULL, NULL
  FROM (VALUES
('BFS-001', 'Regulatory Licensing Blind Spot', 'Idea & Validation', 'FinTech Market Validation', 'external', 'The founder does not know what license or registration, such as NBFC status, payment aggregator authorization, or an insurance broker license, is legally required to operate this idea.', 5, 9, '["Founder does not know which regulator applies to this idea", "No research has been done on the licensing category needed", "Assuming a lighter registration will suffice without confirming this", "No understanding of how long licensing actually takes", "No understanding of ongoing compliance obligations tied to the license"]'::jsonb, 2),
('BFS-002', 'Trust and Security Threshold Underestimated', 'Idea & Validation', 'FinTech Market Validation', 'external', 'Financial products need dramatically higher security and trust than a typical app, and the founder has not grasped that a single breach or trust failure can be fatal here in a way it would not be elsewhere.', 5, 9, '["Comparing security bar to a typical consumer app, not a financial product", "No understanding of what a trust failure actually costs in FinTech", "Underestimating regulatory and user scrutiny financial products face", "No security-by-design thinking built into the idea from the start"]'::jsonb, 2),
('BFS-003', 'Data Compliance Obligations Not Understood', 'Idea & Validation', 'FinTech Market Validation', 'external', 'Handling financial data triggers specific obligations, such as KYC and AML requirements and RBI data localization rules, that have not been factored into the idea.', 4, 9, '["KYC or AML obligations have not been researched", "RBI data localization rules are not understood", "No plan exists for handling sensitive financial data securely", "Assuming general data practices are sufficient for financial data"]'::jsonb, 2),
('BFS-004', 'Capital and Compliance Cost Not Modeled', 'Idea & Validation', 'FinTech Market Validation', 'external', 'Regulatory capital requirements, compliance overhead, and insurance costs are missing entirely from the founder''s financial model.', 4, 8, '["Regulatory capital requirements are missing from the financial model", "Compliance overhead cost has not been estimated", "Insurance or bond requirements have not been accounted for", "No understanding of ongoing audit or reporting costs", "Underestimating the total cost of becoming compliant before launch"]'::jsonb, 2),
('BFS-005', 'License Application Not Actually Filed', 'Idea & Validation', 'FinTech Market Validation', 'external', 'The founder knows what license is needed but has not actually submitted the application yet.', 4, 8, '["Application requirements are known but not submitted", "No dedicated person is driving the filing forward", "Application is being treated as a someday task", "Missing documentation is delaying submission"]'::jsonb, 2),
('BFS-006', 'Real Money Testing Skipped', 'Idea & Validation', 'FinTech Market Validation', 'external', 'The product has only been tested with dummy data, never with real transactions or real money.', 4, 8, '["No real transaction testing has been conducted", "Testing environment uses fake or dummy money only", "No plan exists to test with real, small-value transactions", "Assuming dummy-data results will hold once real money is involved", "Fear of regulatory risk is preventing any real-money testing"]'::jsonb, 2),
('BFS-007', 'Security Audit Never Conducted', 'Idea & Validation', 'FinTech Market Validation', 'external', 'No third-party security audit or penetration test has been done, despite the product handling financial data.', 5, 9, '["No third-party security audit has been done", "No penetration testing has been conducted", "Assuming internal review is sufficient", "No budget has been allocated for a real security audit"]'::jsonb, 2),
('BFS-008', 'Early Users Are Not Financially Representative', 'Idea & Validation', 'FinTech Market Validation', 'external', 'Testers are using play money or are not in a genuine financial situation, so their behavior does not reflect real usage.', 4, 8, '["Test users are using play money, not real money", "Test users are not in a genuine financial situation matching real customers", "No real financial stress or urgency is present in testing", "Feedback is collected under artificial, low-stakes conditions", "No plan exists to test with users facing real financial decisions"]'::jsonb, 2),
('BFS-009', 'Regulatory Sandbox Not Explored', 'Idea & Validation', 'FinTech Market Validation', 'external', 'The founder has not looked into RBI''s regulatory sandbox or similar pilot programs that would allow compliant testing before full licensing.', 3, 7, '["Founder is unaware regulatory sandbox programs exist", "No research has been done on sandbox eligibility for this category", "Assuming full licensing is the only path to legal testing", "No application has been submitted to any sandbox program"]'::jsonb, 2),
('BFS-010', 'Fraud Detection and Loss Management', 'Idea & Validation', 'FinTech Market Validation', 'external', 'As transaction volume grows, fraud attempts scale with it, and losses mount without a real detection system in place.', 5, 9, '["No fraud detection system is in place", "Fraud losses are not tracked separately from other losses", "No fraud rate benchmark exists to measure against", "Manual review cannot keep pace with transaction volume", "No process exists for investigating suspected fraud"]'::jsonb, 2),
('BFS-011', 'Regulatory Reporting and Audit Burden', 'Idea & Validation', 'FinTech Market Validation', 'external', 'Ongoing reporting obligations to regulators grow heavier and more frequent as the business scales.', 4, 8, '["Reporting is handled reactively at each deadline", "No dedicated compliance or reporting owner exists", "No audit trail is built into core systems", "Reporting requires significant manual data compilation each time"]'::jsonb, 2),
('BFS-012', 'Customer Complaint and Grievance Handling', 'Idea & Validation', 'FinTech Market Validation', 'external', 'Financial regulators mandate specific grievance redressal timelines and processes that informal, ad hoc handling will not satisfy.', 4, 8, '["No formal grievance redressal process exists", "Mandated resolution timelines are not tracked", "No grievance officer has been appointed", "Complaints are handled informally, case by case", "No record exists proving complaint resolution timelines were met"]'::jsonb, 2),
('BFS-013', 'Multi-Product Licensing Complexity', 'Idea & Validation', 'FinTech Market Validation', 'external', 'Adding a new financial product, such as moving from lending into insurance or investments, usually requires an entirely new license rather than an extension of the existing one.', 4, 8, '["Assuming new products fall under the existing license", "No licensing research done before planning a new product line", "No timeline built in for new product licensing", "Product roadmap does not account for regulatory approval gates"]'::jsonb, 2),
('BFS-014', 'Capital Adequacy and Liquidity Risk', 'Idea & Validation', 'FinTech Market Validation', 'external', 'Lending money or holding customer funds creates regulatory capital and liquidity requirements that tighten as volume grows.', 5, 9, '["Current capital adequacy position is not tracked", "No early warning exists for approaching regulatory limits", "Liquidity risk under stress conditions has not been modeled", "Growth targets are not checked against capital constraints", "No plan exists for raising capital before hitting the limit"]'::jsonb, 2),
('BFS-015', 'Partner Bank or NBFC Dependency', 'Idea & Validation', 'FinTech Market Validation', 'external', 'Many FinTech businesses operate on top of a partner bank or NBFC relationship that, if it ends, stops the business entirely.', 5, 9, '["Business depends entirely on one partner bank or NBFC", "No backup partner relationship has been established", "Partner relationship terms and exit clauses are not well understood", "No contingency plan exists if the partnership ends"]'::jsonb, 2)
  ) AS v(problem_code, problem_name, category, subcategory, layer, description, severity_min, severity_max, symptoms, pillar_id)
  RETURNING problem_id, problem_code
),
new_root_causes AS (
  INSERT INTO root_causes (root_cause_code, problem_id, root_cause_name, root_cause_category, explanation, confidence_weight, layer, primary_stage_group, industry_relevance, embedding, embedding_model, embedding_version, embedding_dimension)
  SELECT v.root_cause_code, p.problem_id, v.root_cause_name, v.root_cause_category, v.explanation, v.confidence_weight, v.layer, v.primary_stage_group, '["fintech"]'::jsonb, array_fill(0, ARRAY[1536])::vector, NULL, NULL, NULL
  FROM (VALUES
('RC-BFS-001', 'BFS-001', 'Applicable Regulator Unknown', 'Knowledge', 'The founder does not know which regulator, such as RBI, IRDAI, or SEBI, would govern this idea.', 0.68, 'external', 'Stage 0'),
('RC-BFS-002', 'BFS-001', 'Licensing Category Not Researched', 'Knowledge', 'No research has been done on which specific licensing category this idea would fall under.', 0.65, 'external', 'Stage 0'),
('RC-BFS-003', 'BFS-001', 'Assuming a Lighter Registration Suffices', 'Knowledge', 'The founder assumes a simpler, lighter registration will be enough without confirming this.', 0.62, 'external', 'Stage 0'),
('RC-BFS-004', 'BFS-001', 'Licensing Timeline Unknown', 'Knowledge', 'There is no realistic understanding of how long the licensing process actually takes.', 0.62, 'external', 'Stage 0'),
('RC-BFS-005', 'BFS-001', 'Ongoing Compliance Obligations Unknown', 'Knowledge', 'The ongoing compliance obligations that come with the license have not been understood.', 0.60, 'external', 'Stage 0'),
('RC-BFS-006', 'BFS-002', 'Security Bar Compared to Consumer Apps', 'Knowledge', 'Security expectations are being modeled on a typical consumer app rather than a financial product.', 0.65, 'external', 'Stage 0'),
('RC-BFS-007', 'BFS-002', 'Cost of a Trust Failure Not Understood', 'Knowledge', 'The real cost of a trust or security failure in FinTech has not been understood.', 0.65, 'external', 'Stage 0'),
('RC-BFS-008', 'BFS-002', 'Regulatory and User Scrutiny Underestimated', 'Knowledge', 'The level of scrutiny financial products face from regulators and users is being underestimated.', 0.62, 'external', 'Stage 0'),
('RC-BFS-009', 'BFS-002', 'No Security-by-Design Thinking', 'Strategic', 'Security has not been built into the idea as a foundational design principle from the start.', 0.63, 'external', 'Stage 0'),
('RC-BFS-010', 'BFS-003', 'KYC/AML Obligations Not Researched', 'Knowledge', 'Know-your-customer and anti-money-laundering obligations have not been researched.', 0.65, 'external', 'Stage 0'),
('RC-BFS-011', 'BFS-003', 'Data Localization Rules Not Understood', 'Knowledge', 'RBI data localization requirements are not understood.', 0.63, 'external', 'Stage 0'),
('RC-BFS-012', 'BFS-003', 'No Secure Data Handling Plan', 'Operational', 'There is no real plan for securely handling sensitive financial data.', 0.63, 'external', 'Stage 0'),
('RC-BFS-013', 'BFS-003', 'Assuming General Data Practices Suffice', 'Knowledge', 'It is assumed that general data handling practices are sufficient for financial data specifically.', 0.60, 'external', 'Stage 0'),
('RC-BFS-014', 'BFS-004', 'Regulatory Capital Missing From Model', 'Strategic', 'Regulatory capital requirements are absent from the financial model entirely.', 0.65, 'external', 'Stage 0'),
('RC-BFS-015', 'BFS-004', 'Compliance Overhead Not Estimated', 'Operational', 'The ongoing cost of maintaining compliance has not been estimated.', 0.63, 'external', 'Stage 0'),
('RC-BFS-016', 'BFS-004', 'Insurance or Bonding Requirements Ignored', 'Operational', 'Required insurance or bonding costs have not been accounted for.', 0.62, 'external', 'Stage 0'),
('RC-BFS-017', 'BFS-004', 'Audit and Reporting Costs Unknown', 'Knowledge', 'The ongoing cost of audits and regulatory reporting is not understood.', 0.60, 'external', 'Stage 0'),
('RC-BFS-018', 'BFS-004', 'Total Pre-Launch Compliance Cost Underestimated', 'Knowledge', 'The full, real cost of becoming compliant before launch is being underestimated.', 0.62, 'external', 'Stage 0'),
('RC-BFS-019', 'BFS-005', 'Application Requirements Known but Not Submitted', 'Operational', 'The founder knows what is required but has not actually submitted the application.', 0.65, 'external', 'Stage 0â†’1'),
('RC-BFS-020', 'BFS-005', 'No Dedicated Application Owner', 'Operational', 'Nobody is specifically responsible for driving the filing forward.', 0.62, 'external', 'Stage 0â†’1'),
('RC-BFS-021', 'BFS-005', 'Application Treated as a Someday Task', 'Behavioural', 'Submitting the application keeps getting deferred as something to handle later.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BFS-022', 'BFS-005', 'Missing Documentation Delaying Submission', 'Operational', 'Required documentation is incomplete, delaying the actual filing.', 0.62, 'external', 'Stage 0â†’1'),
('RC-BFS-023', 'BFS-006', 'No Real Transaction Testing', 'Operational', 'No testing has been conducted using actual, real transactions.', 0.65, 'external', 'Stage 0â†’1'),
('RC-BFS-024', 'BFS-006', 'Testing Uses Dummy Money Only', 'Operational', 'All testing so far has used fake or simulated money, not real transactions.', 0.65, 'external', 'Stage 0â†’1'),
('RC-BFS-025', 'BFS-006', 'No Real Small-Value Test Plan', 'Strategic', 'There is no plan to test with real, small-value transactions before scaling.', 0.62, 'external', 'Stage 0â†’1'),
('RC-BFS-026', 'BFS-006', 'Assuming Dummy Results Hold With Real Money', 'Knowledge', 'The founder assumes results from dummy-money testing will hold once real money is involved.', 0.62, 'external', 'Stage 0â†’1'),
('RC-BFS-027', 'BFS-006', 'Regulatory Risk Fear Preventing Real Testing', 'Behavioural', 'Fear of regulatory consequences is preventing any real-money testing from happening.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BFS-028', 'BFS-007', 'No Third-Party Security Audit', 'Operational', 'No external party has ever audited the product''s security.', 0.68, 'external', 'Stage 0â†’1'),
('RC-BFS-029', 'BFS-007', 'No Penetration Testing Conducted', 'Operational', 'No penetration test has ever been run against the product.', 0.65, 'external', 'Stage 0â†’1'),
('RC-BFS-030', 'BFS-007', 'Assuming Internal Review Is Sufficient', 'Knowledge', 'It is assumed that internal review alone is enough, without external verification.', 0.62, 'external', 'Stage 0â†’1'),
('RC-BFS-031', 'BFS-007', 'No Security Audit Budget', 'Strategic', 'No budget has been allocated for a real, professional security audit.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BFS-032', 'BFS-008', 'Test Users Using Play Money', 'Operational', 'Testers are using simulated or play money rather than real funds.', 0.65, 'external', 'Stage 0â†’1'),
('RC-BFS-033', 'BFS-008', 'Testers Not Financially Representative', 'Knowledge', 'Testers do not match the real financial situation of the actual target customer.', 0.63, 'external', 'Stage 0â†’1'),
('RC-BFS-034', 'BFS-008', 'No Real Financial Stress in Testing', 'Operational', 'Testing conditions do not include any genuine financial stress or urgency.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BFS-035', 'BFS-008', 'Feedback Collected Under Artificial Conditions', 'Behavioural', 'Feedback is gathered in low-stakes, artificial conditions that may not reflect real use.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BFS-036', 'BFS-008', 'No Plan to Test Real Financial Decisions', 'Strategic', 'There is no plan to test with users actually making real financial decisions.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BFS-037', 'BFS-009', 'Sandbox Programs Unknown', 'Knowledge', 'The founder is unaware that regulatory sandbox programs exist for this category.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BFS-038', 'BFS-009', 'Sandbox Eligibility Not Researched', 'Operational', 'No research has been done on whether this idea qualifies for a sandbox program.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BFS-039', 'BFS-009', 'Assuming Full Licensing Is the Only Path', 'Knowledge', 'It is assumed full licensing is required before any legal testing can happen.', 0.58, 'external', 'Stage 0â†’1'),
('RC-BFS-040', 'BFS-009', 'No Sandbox Application Submitted', 'Operational', 'No application has actually been submitted to any sandbox program.', 0.58, 'external', 'Stage 0â†’1'),
('RC-BFS-041', 'BFS-010', 'No Fraud Detection System', 'Operational', 'No automated system exists to detect fraudulent transactions.', 0.68, 'external', 'Stage 1â†’10+'),
('RC-BFS-042', 'BFS-010', 'Fraud Losses Not Tracked Separately', 'Operational', 'Fraud losses are not measured separately from other business losses.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-BFS-043', 'BFS-010', 'No Fraud Rate Benchmark', 'Knowledge', 'There is no benchmark for what an acceptable fraud rate looks like in this category.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BFS-044', 'BFS-010', 'Manual Review Cannot Keep Pace', 'Operational', 'Manual fraud review cannot keep up with current transaction volume.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-BFS-045', 'BFS-010', 'No Fraud Investigation Process', 'Operational', 'There is no defined process for investigating a suspected fraud case.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BFS-046', 'BFS-011', 'Reporting Handled Reactively', 'Operational', 'Regulatory reporting is scrambled together at each deadline rather than managed proactively.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-BFS-047', 'BFS-011', 'No Dedicated Reporting Owner', 'Operational', 'Nobody is specifically responsible for regulatory reporting.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BFS-048', 'BFS-011', 'No Audit Trail in Core Systems', 'Operational', 'Core systems do not automatically produce the audit trail regulators expect.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-BFS-049', 'BFS-011', 'Reporting Requires Heavy Manual Compilation', 'Operational', 'Each reporting cycle requires significant manual data gathering and compilation.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BFS-050', 'BFS-012', 'No Formal Grievance Process', 'Operational', 'There is no formal, documented grievance redressal process.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-BFS-051', 'BFS-012', 'Mandated Timelines Not Tracked', 'Operational', 'Regulator-mandated complaint resolution timelines are not being tracked.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-BFS-052', 'BFS-012', 'No Grievance Officer Appointed', 'Operational', 'No grievance officer has been formally appointed as regulations typically require.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-BFS-053', 'BFS-012', 'Complaints Handled Informally', 'Operational', 'Customer complaints are handled case by case without a consistent process.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BFS-054', 'BFS-012', 'No Proof of Timeline Compliance', 'Operational', 'No record exists that could prove complaint resolution timelines were actually met.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BFS-055', 'BFS-013', 'Assuming New Products Fall Under Existing License', 'Knowledge', 'It is assumed a new product line is covered by the existing license without confirming this.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-BFS-056', 'BFS-013', 'No Licensing Research Before Product Planning', 'Operational', 'New product lines are planned before checking what licensing they would require.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-BFS-057', 'BFS-013', 'No Licensing Timeline in Product Roadmap', 'Strategic', 'The product roadmap does not build in time for obtaining new licenses.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BFS-058', 'BFS-013', 'Roadmap Ignores Regulatory Approval Gates', 'Strategic', 'The product roadmap does not treat regulatory approval as a real gating milestone.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BFS-059', 'BFS-014', 'Capital Adequacy Position Not Tracked', 'Operational', 'The current capital adequacy position is not being actively monitored.', 0.68, 'external', 'Stage 1â†’10+'),
('RC-BFS-060', 'BFS-014', 'No Early Warning for Regulatory Limits', 'Operational', 'There is no alert or early warning as the business approaches a regulatory limit.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-BFS-061', 'BFS-014', 'Liquidity Stress Not Modeled', 'Strategic', 'Liquidity risk under stress conditions has never been modeled.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-BFS-062', 'BFS-014', 'Growth Targets Not Checked Against Capital Limits', 'Strategic', 'Growth targets are set without checking them against capital adequacy constraints.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-BFS-063', 'BFS-014', 'No Capital Raise Plan Before Hitting Limits', 'Strategic', 'There is no plan for raising additional capital before regulatory limits are reached.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BFS-064', 'BFS-015', 'Total Dependence on One Partner', 'Strategic', 'The entire business depends on a single partner bank or NBFC relationship.', 0.68, 'external', 'Stage 1â†’10+'),
('RC-BFS-065', 'BFS-015', 'No Backup Partner Established', 'Strategic', 'No alternative partner bank or NBFC relationship has been established.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-BFS-066', 'BFS-015', 'Partnership Exit Terms Not Understood', 'Knowledge', 'The terms under which the partnership could end are not well understood.', 0.62, 'external', 'Stage 1â†’10+')
  ) AS v(root_cause_code, problem_code, root_cause_name, root_cause_category, explanation, confidence_weight, layer, primary_stage_group)
  JOIN new_problems p ON p.problem_code = v.problem_code
  RETURNING root_cause_id, root_cause_code
),
new_questions AS (
  INSERT INTO questions (question_code, category, question_text, problem_id, root_cause_id, question_type, difficulty_level, priority, is_distress_tagged, industry_relevance, embedding, primary_stage_group, embedding_model, embedding_version, embedding_dimension)
  SELECT v.question_code, 'Idea & Validation', v.question_text, p.problem_id, rc.root_cause_id, 'open_text', v.difficulty_level, v.priority, false, '["fintech"]'::jsonb, array_fill(0, ARRAY[1536])::vector, v.stage_group, NULL, NULL, NULL
  FROM (VALUES
('S0-BFS-001', 'BFS-001', 'RC-BFS-001', 'Do you know which regulator -- RBI, IRDAI, SEBI -- your idea would actually fall under?', 2, 'CORE', 'Stage 0'),
('S0-BFS-002', 'BFS-001', 'RC-BFS-002', 'Have you researched what license or registration this specific idea would legally require?', 2, 'CORE', 'Stage 0'),
('S0-BFS-003', 'BFS-001', 'RC-BFS-003', 'Are you assuming a lighter, easier registration will work without actually confirming that?', 2, 'CORE', 'Stage 0'),
('S0-BFS-004', 'BFS-001', 'RC-BFS-004', 'Do you know how long it realistically takes to get the license or registration you''d need?', 2, 'CORE', 'Stage 0'),
('S0-BFS-005', 'BFS-001', 'RC-BFS-005', 'Once licensed, do you know what ongoing compliance obligations you''d need to keep up with?', 3, 'CORE', 'Stage 0'),
('S0-BFS-006', 'BFS-002', 'RC-BFS-007', 'Do you understand that a single security or trust failure could be fatal here, in a way it wouldn''t be for a typical app?', 3, 'CORE', 'Stage 0'),
('S0-BFS-007', 'BFS-002', 'RC-BFS-006', 'Are you thinking about security the way a typical app would, or the way a financial product needs to?', 2, 'CORE', 'Stage 0'),
('S0-BFS-008', 'BFS-002', 'RC-BFS-008', 'Have you thought about how much scrutiny a financial product actually gets from users and regulators, compared to other apps?', 2, 'CORE', 'Stage 0'),
('S0-BFS-009', 'BFS-003', 'RC-BFS-010', 'Have you thought about what KYC or data rules apply to what you''re planning to collect?', 2, 'CORE', 'Stage 0'),
('S0-BFS-010', 'BFS-003', 'RC-BFS-011', 'Do you know what RBI''s data localization rules would require of you?', 3, 'CORE', 'Stage 0'),
('S0-BFS-011', 'BFS-003', 'RC-BFS-012', 'Do you have any real plan for how you''d securely handle sensitive financial data?', 2, 'CORE', 'Stage 0'),
('S0-BFS-012', 'BFS-004', 'RC-BFS-014', 'Does your cost model include compliance, licensing, or capital requirements at all?', 2, 'CORE', 'Stage 0'),
('S0-BFS-013', 'BFS-004', 'RC-BFS-015', 'Have you estimated what it actually costs to stay compliant on an ongoing basis?', 2, 'CORE', 'Stage 0'),
('S0-BFS-014', 'BFS-004', 'RC-BFS-016', 'Do you know if this business would need insurance or a bond to legally operate?', 2, 'SUPPLEMENTARY', 'Stage 0'),
('S0-BFS-015', 'BFS-004', 'RC-BFS-018', 'Have you added up the total real cost of becoming compliant before you can even launch?', 3, 'CORE', 'Stage 0'),
('S01-BFS-001', 'BFS-005', 'RC-BFS-019', 'Have you actually submitted your license application, or is it still sitting in draft?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BFS-002', 'BFS-005', 'RC-BFS-020', 'Is there someone specifically responsible for pushing your application forward?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BFS-003', 'BFS-005', 'RC-BFS-021', 'Is submitting your application something you''re actively doing, or something you keep planning to start?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BFS-004', 'BFS-005', 'RC-BFS-022', 'What documentation is still missing that''s delaying your submission?', 2, 'SUPPLEMENTARY', 'Stage 0â†’1'),
('S01-BFS-005', 'BFS-006', 'RC-BFS-023', 'Has this ever processed a real transaction with real money, even a small one?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BFS-006', 'BFS-006', 'RC-BFS-024', 'Has all your testing so far used fake or dummy money only?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BFS-007', 'BFS-006', 'RC-BFS-025', 'Do you have a plan to test with small, real-value transactions before scaling up?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BFS-008', 'BFS-006', 'RC-BFS-026', 'Are you assuming your dummy-data results will hold once real money is involved?', 3, 'CORE', 'Stage 0â†’1'),
('S01-BFS-009', 'BFS-006', 'RC-BFS-027', 'Is fear of regulatory risk the reason you haven''t tested with real money yet?', 3, 'CORE', 'Stage 0â†’1'),
('S01-BFS-010', 'BFS-007', 'RC-BFS-029', 'Has anyone actually tried to break into your system, or is security still theoretical?', 3, 'CORE', 'Stage 0â†’1'),
('S01-BFS-011', 'BFS-007', 'RC-BFS-028', 'Has a third party ever audited your security, or has it only been reviewed internally?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BFS-012', 'BFS-007', 'RC-BFS-030', 'Are you assuming your internal review is enough without external verification?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BFS-013', 'BFS-007', 'RC-BFS-031', 'Have you set aside a real budget for a proper security audit?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BFS-014', 'BFS-008', 'RC-BFS-032', 'Are your test users using real money in a real financial situation, or play money in a demo?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BFS-015', 'BFS-008', 'RC-BFS-033', 'Do your testers actually match the financial situation of your real target customer?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BFS-016', 'BFS-008', 'RC-BFS-034', 'Is there any real financial stress or urgency present when people test this, or is it low-stakes?', 3, 'CORE', 'Stage 0â†’1'),
('S01-BFS-017', 'BFS-008', 'RC-BFS-035', 'Could the feedback you''re getting be different if testers had something real financially at stake?', 3, 'CORE', 'Stage 0â†’1'),
('S01-BFS-018', 'BFS-008', 'RC-BFS-036', 'Do you have a plan to test this with people making genuinely real financial decisions?', 2, 'SUPPLEMENTARY', 'Stage 0â†’1'),
('S01-BFS-019', 'BFS-009', 'RC-BFS-037', 'Have you looked into RBI''s regulatory sandbox as a way to test this compliantly before full licensing?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BFS-020', 'BFS-009', 'RC-BFS-038', 'Have you checked whether your specific category is even eligible for a sandbox program?', 2, 'CORE', 'Stage 0â†’1'),
('S10-BFS-001', 'BFS-010', 'RC-BFS-042', 'Do you know what percentage of your transactions are fraudulent, or would you have to go find out?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-002', 'BFS-010', 'RC-BFS-041', 'Do you have an automated system catching fraud, or does it depend on someone noticing?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-003', 'BFS-010', 'RC-BFS-043', 'Do you know what a normal fraud rate looks like for your type of business?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-004', 'BFS-010', 'RC-BFS-044', 'Can your manual review process still keep up with your transaction volume?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-005', 'BFS-010', 'RC-BFS-045', 'When you suspect fraud, is there a clear process for investigating it?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-006', 'BFS-011', 'RC-BFS-046', 'Is regulatory reporting something you do calmly on schedule, or a scramble every deadline?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-007', 'BFS-011', 'RC-BFS-047', 'Is there someone specifically responsible for regulatory reporting?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-008', 'BFS-011', 'RC-BFS-048', 'Do your systems automatically create the audit trail regulators would ask for?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-009', 'BFS-011', 'RC-BFS-049', 'How much manual work goes into pulling together each regulatory report?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-010', 'BFS-012', 'RC-BFS-051', 'Do you meet the mandated timeline for resolving customer complaints, and can you prove it?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-011', 'BFS-012', 'RC-BFS-050', 'Do you have a formal, written grievance process, or are complaints handled however they come in?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-012', 'BFS-012', 'RC-BFS-052', 'Have you appointed a grievance officer, as regulations typically require?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-013', 'BFS-012', 'RC-BFS-054', 'If a regulator asked you to prove you resolved complaints on time, could you show them records?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-014', 'BFS-012', 'RC-BFS-053', 'Are customer complaints handled the same way every time, or does it depend on who picks it up?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-015', 'BFS-013', 'RC-BFS-055', 'If you added a new financial product, do you know whether that needs a completely separate license?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-016', 'BFS-013', 'RC-BFS-056', 'Do you check licensing requirements before planning a new product line, or after?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-017', 'BFS-013', 'RC-BFS-057', 'Does your product roadmap build in time for getting new licenses approved?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-018', 'BFS-013', 'RC-BFS-058', 'Does your roadmap treat regulatory approval as a real gate, or assume it will work out?', 3, 'SUPPLEMENTARY', 'Stage 1â†’10+'),
('S10-BFS-019', 'BFS-014', 'RC-BFS-059', 'Do you know your current capital adequacy position, and how close you are to the limit?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-020', 'BFS-014', 'RC-BFS-060', 'Would you get any warning before you hit a regulatory capital limit, or only find out when you cross it?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-021', 'BFS-014', 'RC-BFS-061', 'Have you modeled what happens to your liquidity under stress conditions?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-022', 'BFS-014', 'RC-BFS-062', 'Are your growth targets checked against your capital limits, or set independently?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-023', 'BFS-014', 'RC-BFS-063', 'Do you have a plan to raise capital before you hit your regulatory limit, not after?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-024', 'BFS-015', 'RC-BFS-064', 'If your partner bank or NBFC ended the relationship tomorrow, what happens to your business?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-BFS-025', 'BFS-015', 'RC-BFS-065', 'Have you established a backup partner bank or NBFC relationship?', 2, 'CORE', 'Stage 1â†’10+')
  ) AS v(question_code, problem_code, root_cause_code, question_text, difficulty_level, priority, stage_group)
  JOIN new_problems p ON p.problem_code = v.problem_code
  JOIN new_root_causes rc ON rc.root_cause_code = v.root_cause_code
  RETURNING question_id, question_code
),
new_tags AS (
  INSERT INTO question_tag_mapping (question_id, tag_id)
  SELECT q.question_id, v.tag_id
  FROM (VALUES
('S0-BFS-001', 4), ('S0-BFS-002', 4), ('S0-BFS-003', 4), ('S0-BFS-004', 4), ('S0-BFS-005', 4),
('S0-BFS-006', 33), ('S0-BFS-007', 33), ('S0-BFS-008', 33),
('S0-BFS-009', 36), ('S0-BFS-010', 36), ('S0-BFS-011', 36),
('S0-BFS-012', 84), ('S0-BFS-013', 84), ('S0-BFS-014', 84), ('S0-BFS-015', 84),
('S01-BFS-001', 4), ('S01-BFS-002', 4), ('S01-BFS-003', 4), ('S01-BFS-004', 4),
('S01-BFS-005', 33), ('S01-BFS-006', 33), ('S01-BFS-007', 33), ('S01-BFS-008', 33), ('S01-BFS-009', 33),
('S01-BFS-010', 36), ('S01-BFS-011', 36), ('S01-BFS-012', 36), ('S01-BFS-013', 36),
('S01-BFS-014', 2), ('S01-BFS-015', 2), ('S01-BFS-016', 2), ('S01-BFS-017', 2), ('S01-BFS-018', 2),
('S01-BFS-019', 12), ('S01-BFS-020', 12),
('S10-BFS-001', 36), ('S10-BFS-002', 36), ('S10-BFS-003', 36), ('S10-BFS-004', 36), ('S10-BFS-005', 36),
('S10-BFS-006', 4), ('S10-BFS-007', 4), ('S10-BFS-008', 4), ('S10-BFS-009', 4),
('S10-BFS-010', 87), ('S10-BFS-011', 87), ('S10-BFS-012', 87), ('S10-BFS-013', 87), ('S10-BFS-014', 87),
('S10-BFS-015', 4), ('S10-BFS-016', 4), ('S10-BFS-017', 4), ('S10-BFS-018', 4),
('S10-BFS-019', 84), ('S10-BFS-020', 84), ('S10-BFS-021', 84), ('S10-BFS-022', 84), ('S10-BFS-023', 84),
('S10-BFS-024', 23), ('S10-BFS-025', 23)
  ) AS v(question_code, tag_id)
  JOIN new_questions q ON q.question_code = v.question_code
  RETURNING mapping_id
),
new_interventions AS (
  INSERT INTO interventions (intervention_code, problem_id, root_cause_ids, secondary_root_cause_ids, capability_domain, section, recommended_frameworks, framework_codes, immediate_next_steps, stage_relevance, industry_relevance, design_principles)
  SELECT v.intervention_code, p.problem_id, v.root_cause_ids, '[]'::jsonb, v.capability_domain, v.section, v.recommended_frameworks, NULL, v.immediate_next_steps, v.stage_relevance, '["fintech"]'::jsonb, v.design_principles
  FROM (VALUES
('INT-BFS-001', 'BFS-001', '["RC-BFS-001", "RC-BFS-002"]'::jsonb, 'Regulatory Compliance', 'Ideation â€” FinTech Regulatory Foundations', '[{"name": "Regulatory Category Identification", "brief": "Determining exactly which regulator and license category applies before building."}]'::jsonb, '["Identify which regulator -- RBI, IRDAI, or SEBI -- governs your specific idea.", "Research the exact license category this falls under.", "Write down the specific requirements for that category."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-002', 'BFS-001', '["RC-BFS-003", "RC-BFS-005"]'::jsonb, 'Regulatory Compliance', 'Ideation â€” FinTech Regulatory Foundations', '[{"name": "Compliance Consultation", "brief": "Getting expert compliance advice before committing further to the idea."}]'::jsonb, '["Find a compliance consultant or lawyer with FinTech experience.", "Confirm whether a lighter registration genuinely applies to you.", "Get a clear list of ongoing obligations, not just the initial license."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-003', 'BFS-001', '["RC-BFS-004"]'::jsonb, 'Regulatory Compliance', 'Ideation â€” FinTech Regulatory Foundations', '[{"name": "Licensing Timeline Planning", "brief": "Building a realistic licensing timeline into the overall business plan."}]'::jsonb, '["Research the real timeline for your specific license category.", "Build this timeline into your overall launch plan.", "Identify what, if anything, you can legally do while awaiting approval."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-004', 'BFS-002', '["RC-BFS-006", "RC-BFS-009"]'::jsonb, 'Security & Trust', 'Ideation â€” FinTech Regulatory Foundations', '[{"name": "Financial-Grade Security Design", "brief": "Designing security to financial industry standards from day one, not consumer-app standards."}]'::jsonb, '["Research what security standard applies to your specific product type.", "Build security requirements into your design from the start.", "Identify the gap between your current plan and that standard."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-005', 'BFS-002', '["RC-BFS-007", "RC-BFS-008"]'::jsonb, 'Security & Trust', 'Ideation â€” FinTech Regulatory Foundations', '[{"name": "Trust Failure Case Study Research", "brief": "Researching what real trust or security failures have cost comparable FinTech companies."}]'::jsonb, '["Find 2-3 real examples of FinTech trust or security failures.", "Research the actual business impact of each.", "Use these as a benchmark for how seriously to treat this risk."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-006', 'BFS-003', '["RC-BFS-010", "RC-BFS-013"]'::jsonb, 'Data Compliance', 'Ideation â€” FinTech Regulatory Foundations', '[{"name": "KYC/AML Obligation Mapping", "brief": "Mapping every KYC and AML obligation before any user data collection begins."}]'::jsonb, '["List every piece of user data your idea would need to collect.", "Research KYC and AML obligations tied to that data.", "Confirm general data practices are not being relied on incorrectly."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-007', 'BFS-003', '["RC-BFS-011", "RC-BFS-012"]'::jsonb, 'Data Compliance', 'Ideation â€” FinTech Regulatory Foundations', '[{"name": "Data Localization Compliance Check", "brief": "Getting clarity on RBI data localization requirements before choosing infrastructure."}]'::jsonb, '["Research RBI data localization requirements for your data type.", "Confirm your planned infrastructure meets those requirements.", "Build a secure data handling plan before collecting any real data."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-008', 'BFS-004', '["RC-BFS-014", "RC-BFS-015"]'::jsonb, 'Financial Planning', 'Ideation â€” FinTech Regulatory Foundations', '[{"name": "Compliance Cost Modeling", "brief": "Building regulatory capital and compliance overhead directly into the financial model."}]'::jsonb, '["Research the regulatory capital requirement for your license category.", "Estimate ongoing compliance overhead costs.", "Add both directly into your financial model."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-009', 'BFS-004', '["RC-BFS-016", "RC-BFS-017"]'::jsonb, 'Financial Planning', 'Ideation â€” FinTech Regulatory Foundations', '[{"name": "Insurance and Audit Cost Research", "brief": "Getting real quotes for required insurance, bonding, and audit costs."}]'::jsonb, '["Confirm whether your business requires insurance or a bond.", "Get real quotes for any required coverage.", "Research typical ongoing audit and reporting costs for your category."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-010', 'BFS-004', '["RC-BFS-018"]'::jsonb, 'Financial Planning', 'Ideation â€” FinTech Regulatory Foundations', '[{"name": "Total Pre-Launch Cost Calculation", "brief": "Calculating the complete real cost of becoming compliant before launch."}]'::jsonb, '["Add up every compliance, licensing, and capital cost identified so far.", "Compare this total against your current funding plan.", "Revise your launch timeline if there is a real gap."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-011', 'BFS-005', '["RC-BFS-019", "RC-BFS-021"]'::jsonb, 'Regulatory Compliance', 'Validation â€” FinTech Real-World Readiness', '[{"name": "Application Submission Action", "brief": "Actually submitting the license application rather than continuing to prepare it."}]'::jsonb, '["Identify exactly what''s needed to submit today.", "Submit the application this month.", "Set a follow-up date to check on status."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-012', 'BFS-005', '["RC-BFS-020"]'::jsonb, 'Regulatory Compliance', 'Validation â€” FinTech Real-World Readiness', '[{"name": "Application Ownership Assignment", "brief": "Assigning a specific, accountable owner to drive the application to completion."}]'::jsonb, '["Assign one person to own the application process.", "Set a weekly check-in on application status.", "Track this as a core milestone, not a side task."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-013', 'BFS-006', '["RC-BFS-023", "RC-BFS-025"]'::jsonb, 'Product Validation', 'Validation â€” FinTech Real-World Readiness', '[{"name": "Real-Money Pilot Transaction", "brief": "Running one real transaction with real, small-value money before scaling testing."}]'::jsonb, '["Identify one small, real-value transaction to test.", "Run it through your actual system.", "Document exactly what happened, good or bad."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-014', 'BFS-006', '["RC-BFS-027"]'::jsonb, 'Product Validation', 'Validation â€” FinTech Real-World Readiness', '[{"name": "Structured Real-Money Pilot Plan", "brief": "Building a structured plan for real-money testing that manages regulatory risk deliberately."}]'::jsonb, '["Consult with a compliance expert on safe real-money testing limits.", "Design a structured pilot within those limits.", "Run the pilot and document compliance at each step."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-015', 'BFS-007', '["RC-BFS-028", "RC-BFS-029"]'::jsonb, 'Security & Trust', 'Validation â€” FinTech Real-World Readiness', '[{"name": "Third-Party Security Audit", "brief": "Getting a real, external security audit or penetration test conducted."}]'::jsonb, '["Identify a qualified third-party security auditor.", "Schedule a security audit or penetration test.", "Address any critical findings before proceeding further."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-016', 'BFS-007', '["RC-BFS-030", "RC-BFS-031"]'::jsonb, 'Security & Trust', 'Validation â€” FinTech Real-World Readiness', '[{"name": "Ongoing Security Review Budgeting", "brief": "Budgeting and scheduling a recurring third-party security review, not a one-time check."}]'::jsonb, '["Set aside a specific budget for security audits.", "Schedule a recurring annual review.", "Do not rely solely on internal review going forward."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-017', 'BFS-008', '["RC-BFS-032", "RC-BFS-033"]'::jsonb, 'Customer Validation', 'Validation â€” FinTech Real-World Readiness', '[{"name": "Representative Tester Recruitment", "brief": "Recruiting test users who genuinely represent the real target financial situation."}]'::jsonb, '["Define your real target customer''s financial profile.", "Recruit testers matching that profile.", "Replace or supplement testers who do not match it."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-018', 'BFS-008', '["RC-BFS-034", "RC-BFS-035", "RC-BFS-036"]'::jsonb, 'Customer Validation', 'Validation â€” FinTech Real-World Readiness', '[{"name": "Real-Stakes Testing Scenario Design", "brief": "Designing a testing scenario with genuine financial stakes rather than artificial, low-stakes conditions."}]'::jsonb, '["Design a test scenario involving a genuine financial decision.", "Run this with real testers facing real stakes.", "Compare feedback against your previous low-stakes testing."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-019', 'BFS-009', '["RC-BFS-039", "RC-BFS-040"]'::jsonb, 'Regulatory Compliance', 'Validation â€” FinTech Real-World Readiness', '[{"name": "Regulatory Sandbox Application", "brief": "Applying to a regulatory sandbox program to enable compliant testing before full licensing."}]'::jsonb, '["Identify the relevant sandbox program for your category.", "Prepare and submit a sandbox application.", "Use sandbox approval to test compliantly at smaller scale."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-020', 'BFS-009', '["RC-BFS-037", "RC-BFS-038"]'::jsonb, 'Regulatory Compliance', 'Validation â€” FinTech Real-World Readiness', '[{"name": "Sandbox Eligibility Research", "brief": "Researching sandbox eligibility before assuming full licensing is the only available path."}]'::jsonb, '["Research which regulatory sandbox programs exist for your category.", "Confirm your specific eligibility for one.", "Compare sandbox timeline against full licensing timeline."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-021', 'BFS-005', '["RC-BFS-022"]'::jsonb, 'Regulatory Compliance', 'Validation â€” FinTech Real-World Readiness', '[{"name": "Documentation Checklist Completion", "brief": "Compiling a complete documentation checklist to unblock the application."}]'::jsonb, '["List every document required for your application.", "Identify exactly what''s still missing.", "Set a deadline to complete each missing item."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-022', 'BFS-006', '["RC-BFS-024", "RC-BFS-026"]'::jsonb, 'Product Validation', 'Validation â€” FinTech Real-World Readiness', '[{"name": "Dummy vs Real Results Comparison", "brief": "Comparing real-money test results directly against prior dummy-data assumptions."}]'::jsonb, '["Run the same scenario in both dummy and real-money mode.", "Compare the two results side by side.", "Flag any meaningful difference for further investigation."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-023', 'BFS-010', '["RC-BFS-041", "RC-BFS-044"]'::jsonb, 'Risk Management', 'Growth â€” FinTech Fraud & Risk at Scale', '[{"name": "Automated Fraud Detection", "brief": "Implementing rule-based or model-based fraud detection that scales beyond manual review."}]'::jsonb, '["Identify your 3 most common fraud patterns.", "Implement automated rules to flag those patterns.", "Route flagged transactions to manual review, not all transactions."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-024', 'BFS-010', '["RC-BFS-042", "RC-BFS-043", "RC-BFS-045"]'::jsonb, 'Risk Management', 'Growth â€” FinTech Fraud & Risk at Scale', '[{"name": "Fraud Loss Tracking and Benchmarking", "brief": "Tracking fraud losses as a distinct metric and benchmarking against category norms."}]'::jsonb, '["Start tracking fraud losses separately from other losses.", "Research the typical fraud rate for your category.", "Define a clear investigation process for suspected fraud."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-025', 'BFS-011', '["RC-BFS-046", "RC-BFS-047"]'::jsonb, 'Regulatory Compliance', 'Growth â€” Regulatory Reporting at Scale', '[{"name": "Reporting Calendar and Ownership", "brief": "Assigning a dedicated reporting owner working from a proactive compliance calendar."}]'::jsonb, '["Assign one person to own regulatory reporting.", "Build a calendar of every reporting deadline for the year.", "Start preparing each report well before its deadline."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-026', 'BFS-011', '["RC-BFS-048", "RC-BFS-049"]'::jsonb, 'Regulatory Compliance', 'Growth â€” Regulatory Reporting at Scale', '[{"name": "Automated Audit Trail", "brief": "Building audit trails and reporting data directly into core systems to reduce manual compilation."}]'::jsonb, '["Identify what data each regulatory report requires.", "Build automated capture of that data into your systems.", "Reduce manual compilation work with each reporting cycle."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-027', 'BFS-012', '["RC-BFS-050", "RC-BFS-052"]'::jsonb, 'Customer Operations', 'Growth â€” Grievance & Complaint Handling', '[{"name": "Formal Grievance Redressal Framework", "brief": "Establishing a documented grievance process with an appointed grievance officer."}]'::jsonb, '["Appoint a formal grievance officer.", "Document your complete grievance redressal process.", "Publish the process where customers can find it."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-028', 'BFS-012', '["RC-BFS-051", "RC-BFS-053", "RC-BFS-054"]'::jsonb, 'Customer Operations', 'Growth â€” Grievance & Complaint Handling', '[{"name": "Complaint Timeline Tracking", "brief": "Tracking every complaint against its mandated resolution timeline with an auditable record."}]'::jsonb, '["Set up a system logging every complaint with a timestamp.", "Track each against the mandated resolution timeline.", "Ensure the record could be shown to a regulator on request."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-029', 'BFS-013', '["RC-BFS-055", "RC-BFS-056"]'::jsonb, 'Regulatory Compliance', 'Growth â€” Multi-Product Licensing', '[{"name": "Pre-Product Licensing Check", "brief": "Confirming licensing requirements before committing to a new product line."}]'::jsonb, '["Before planning any new product, confirm its licensing category.", "Verify whether your existing license actually covers it.", "Do this check before allocating any build resources."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-030', 'BFS-013', '["RC-BFS-057", "RC-BFS-058"]'::jsonb, 'Regulatory Compliance', 'Growth â€” Multi-Product Licensing', '[{"name": "Regulatory Gates in Product Roadmap", "brief": "Building regulatory approval timelines into the product roadmap as real gating milestones."}]'::jsonb, '["Add regulatory approval as an explicit milestone on your roadmap.", "Build realistic approval timelines into launch planning.", "Do not set a launch date before regulatory timeline is known."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-031', 'BFS-014', '["RC-BFS-059", "RC-BFS-060"]'::jsonb, 'Financial Risk', 'Growth â€” Capital Adequacy & Liquidity', '[{"name": "Capital Adequacy Monitoring Dashboard", "brief": "Real-time monitoring of capital adequacy position with alerts before regulatory limits."}]'::jsonb, '["Build a dashboard showing current capital adequacy position.", "Set an alert threshold well before the regulatory limit.", "Review this position at every leadership meeting."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-032', 'BFS-014', '["RC-BFS-061", "RC-BFS-062", "RC-BFS-063"]'::jsonb, 'Financial Risk', 'Growth â€” Capital Adequacy & Liquidity', '[{"name": "Liquidity Stress Testing and Capital Planning", "brief": "Modeling liquidity under stress and planning capital raises ahead of constraints."}]'::jsonb, '["Model your liquidity position under a stress scenario.", "Check your growth targets against capital constraints.", "Plan your next capital raise before you approach the limit."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-033', 'BFS-015', '["RC-BFS-064", "RC-BFS-065"]'::jsonb, 'Partnership Risk', 'Growth â€” Partner Bank Dependency', '[{"name": "Backup Partner Relationship", "brief": "Establishing a second partner bank or NBFC relationship before it becomes urgent."}]'::jsonb, '["Identify 2-3 alternative partner banks or NBFCs.", "Begin conversations with at least one before you need them.", "Understand what switching would actually require operationally."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BFS-034', 'BFS-015', '["RC-BFS-066"]'::jsonb, 'Partnership Risk', 'Growth â€” Partner Bank Dependency', '[{"name": "Partnership Exit Terms Review", "brief": "Fully understanding the terms under which the partner relationship could end."}]'::jsonb, '["Review your partnership agreement''s termination clauses.", "Identify how much notice you would actually get.", "Build a contingency plan matched to that notice period."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb)
  ) AS v(intervention_code, problem_code, root_cause_ids, capability_domain, section, recommended_frameworks, immediate_next_steps, stage_relevance, design_principles)
  JOIN new_problems p ON p.problem_code = v.problem_code
  RETURNING intervention_id, intervention_code
)
SELECT
  (SELECT COUNT(*) FROM new_problems) as problems_inserted,
  (SELECT COUNT(*) FROM new_root_causes) as root_causes_inserted,
  (SELECT COUNT(*) FROM new_questions) as questions_inserted,
  (SELECT COUNT(*) FROM new_tags) as tags_inserted,
  (SELECT COUNT(*) FROM new_interventions) as interventions_inserted;"""),

        ('Beauty & Personal Care', 'beauty_personal_care', 'BPC', r"""WITH new_problems AS (
  INSERT INTO problems (problem_code, problem_name, category, subcategory, layer, description, severity_min, severity_max, symptoms, pillar_id, industry_relevance, embedding, embedding_model, embedding_version, embedding_dimension)
  SELECT v.problem_code, v.problem_name, v.category, v.subcategory, v.layer, v.description, v.severity_min, v.severity_max, v.symptoms, v.pillar_id, '["beauty_personal_care"]'::jsonb, array_fill(0, ARRAY[1536])::vector, NULL, NULL, NULL
  FROM (VALUES
('BPC-001', 'Idea Not Differentiated From Existing Brands', 'Idea & Validation', 'Beauty Market Validation', 'external', 'There are already hundreds of beauty brands doing something similar, and the founder has not figured out what is actually different about theirs.', 3, 7, '["No clear point of difference has been identified", "Idea copies an existing successful brand without adding anything new", "No research has been done on what else already exists in this space", "Assuming better quality alone is enough differentiation", "No one else has been asked whether this idea stands out"]'::jsonb, 2),
('BPC-002', 'Basic Regulatory Awareness Missing', 'Idea & Validation', 'Beauty Market Validation', 'external', 'The founder does not know that beauty and personal care products need some form of approval before they can be legally sold.', 4, 8, '["Founder does not know regulatory approval is required at all", "Assuming a natural or herbal claim avoids regulation entirely", "No basic research has been done into what is legally required to sell", "Confusing manufacturing with legal approval to sell"]'::jsonb, 2),
('BPC-003', 'Chasing a Trend Without Knowing Why', 'Idea & Validation', 'Beauty Market Validation', 'external', 'The idea is based on something currently popular, such as an ingredient or product type, without understanding whether it will last or why someone would pick this over what already exists.', 3, 7, '["Idea is based purely on a currently trending ingredient or product type", "No thought given to whether the trend will still be relevant later", "No understanding of why a customer would choose this over the trend itself elsewhere", "Idea copies a trend without a personal or business reason behind it"]'::jsonb, 2),
('BPC-004', 'Unclear Who This Is Actually For', 'Idea & Validation', 'Beauty Market Validation', 'external', 'Beauty products can be for very different people and needs, such as skin type, age, or specific concern, and the founder has not picked a clear one yet.', 3, 7, '["No specific customer type has been chosen", "Idea is described as being for everyone", "No thought given to different skin types, ages, or specific concerns", "Assuming one product formulation works for all customers", "No real person has been imagined as the first customer"]'::jsonb, 2),
('BPC-005', 'Regulatory Approval Not Actually Obtained', 'Idea & Validation', 'Beauty Market Validation', 'external', 'The founder now knows approval is needed but has not actually obtained it, such as CDSCO or BIS registration and ingredient safety documentation.', 4, 8, '["Requirements are known but the application has not been filed", "No ingredient safety documentation has been prepared", "No timeline for approval has been built into the launch plan", "Assuming approval will be quick and simple"]'::jsonb, 2),
('BPC-006', 'Formulation Stability Not Tested', 'Idea & Validation', 'Beauty Market Validation', 'external', 'Shelf life, packaging compatibility, and product stability under real conditions such as heat, humidity, and shipping have not been tested.', 4, 8, '["No shelf-life testing has been done", "Packaging has never been tested with the actual formulation", "No testing has been done under heat or humidity conditions", "No testing exists for how the product performs after shipping", "Assuming lab results will hold in real storage conditions"]'::jsonb, 2),
('BPC-007', 'Real Customer Testing Skipped', 'Idea & Validation', 'Beauty Market Validation', 'external', 'The product has only been tried by friends and family, not genuine target customers with no personal connection to the founder.', 4, 8, '["Only friends and family have tried the product", "No outside, unbiased feedback has been collected", "Feedback is skewed by relationship bias", "No plan exists to test with strangers before launch"]'::jsonb, 2),
('BPC-008', 'Sampling Economics Not Planned', 'Idea & Validation', 'Beauty Market Validation', 'external', 'Beauty customers commonly expect to try before buying, and this changes the cost-of-acquisition math in a way that has not been built into the plan.', 3, 7, '["No sample or trial-size strategy exists", "Cost of samples is not built into customer acquisition math", "Assuming customers will buy full-size without trying first", "No plan exists for how samples convert to full purchases"]'::jsonb, 2),
('BPC-009', 'No Real Marketing or Content Plan', 'Idea & Validation', 'Beauty Market Validation', 'external', 'The founder is relying on hope that the product will go viral rather than any actual content or influencer strategy.', 4, 8, '["No content strategy exists", "No influencer or outreach plan exists", "Relying on hope that the product goes viral", "No budget has been allocated to marketing or content", "No understanding of which channel actual target customers use"]'::jsonb, 2),
('BPC-010', 'Batch Consistency Not Controlled at Scale', 'Idea & Validation', 'Beauty Market Validation', 'external', 'What worked in small hand-mixed batches breaks down when scaling to larger production runs, and batch-to-batch variation creeps in.', 4, 8, '["No standardized batch process exists", "Batch testing is not done consistently", "Different suppliers are used without checking consistency", "No quality checkpoint exists before batches ship", "Recipe or process knowledge lives only with one person"]'::jsonb, 2),
('BPC-011', 'Retailer and Distributor Margin Pressure', 'Idea & Validation', 'Beauty Market Validation', 'external', 'Moving into physical retail or larger distributors means giving up margin the founder did not originally plan for, squeezing profitability.', 4, 8, '["No margin modeling was done before entering retail", "Retailer terms were not negotiated from a position of strength", "Distributor cuts were not accounted for at signing", "No understanding exists of true landed cost after all channel fees"]'::jsonb, 2),
('BPC-012', 'Counterfeit and Copycat Risk', 'Idea & Validation', 'Beauty Market Validation', 'external', 'Popular beauty products get copied or counterfeited quickly, and there is no plan for protecting the brand or formulation.', 4, 8, '["No trademark or formulation protection is in place", "No monitoring exists for counterfeit products in the market", "No plan exists for responding if a copycat appears", "Assuming brand loyalty alone will prevent copying"]'::jsonb, 2),
('BPC-013', 'Influencer and Reputation Dependency', 'Idea & Validation', 'Beauty Market Validation', 'external', 'Growth has become tied to a small number of influencers or a single viral moment, creating fragile, unpredictable demand.', 4, 8, '["Majority of sales are tied to one or two influencers", "No diversified marketing channels exist beyond influencer partnerships", "No plan exists for what happens if a key influencer relationship ends", "Brand reputation is tied too closely to one person''s public image"]'::jsonb, 2),
('BPC-014', 'Return and Reaction Handling at Scale', 'Idea & Validation', 'Beauty Market Validation', 'external', 'As the customer base grows, so does the number of allergic reactions, complaints, and returns, with no real system to handle this at volume.', 5, 9, '["No formal system exists for logging allergic reactions or complaints", "No escalation process exists for serious reactions", "Return process is not built for current volume", "No tracking exists of complaint patterns across batches", "No legal or medical protocol exists for serious reaction reports"]'::jsonb, 2),
('BPC-015', 'International Expansion Regulatory Reset', 'Idea & Validation', 'Beauty Market Validation', 'external', 'Every new country has its own cosmetic regulations, and the founder is treating international expansion like a copy-paste of the domestic playbook.', 4, 8, '["Assuming domestic regulations apply internationally", "No research has been done on the target country''s cosmetic regulations", "No local registration or approval process has been started", "Product labeling has not been adapted for target country requirements"]'::jsonb, 2)
  ) AS v(problem_code, problem_name, category, subcategory, layer, description, severity_min, severity_max, symptoms, pillar_id)
  RETURNING problem_id, problem_code
),
new_root_causes AS (
  INSERT INTO root_causes (root_cause_code, problem_id, root_cause_name, root_cause_category, explanation, confidence_weight, layer, primary_stage_group, industry_relevance, embedding, embedding_model, embedding_version, embedding_dimension)
  SELECT v.root_cause_code, p.problem_id, v.root_cause_name, v.root_cause_category, v.explanation, v.confidence_weight, v.layer, v.primary_stage_group, '["beauty_personal_care"]'::jsonb, array_fill(0, ARRAY[1536])::vector, NULL, NULL, NULL
  FROM (VALUES
('RC-BPC-001', 'BPC-001', 'No Clear Point of Difference', 'Knowledge', 'The founder has not identified what actually makes this idea different from what already exists.', 0.65, 'external', 'Stage 0'),
('RC-BPC-002', 'BPC-001', 'Idea Copies an Existing Brand', 'Behavioural', 'The idea closely mirrors an existing successful brand without adding anything new.', 0.62, 'external', 'Stage 0'),
('RC-BPC-003', 'BPC-001', 'No Research on Existing Competitors', 'Operational', 'No research has been done on other brands already doing something similar.', 0.63, 'external', 'Stage 0'),
('RC-BPC-004', 'BPC-001', 'Assuming Better Quality Is Enough', 'Knowledge', 'The founder assumes simply being better quality is sufficient to differentiate.', 0.60, 'external', 'Stage 0'),
('RC-BPC-005', 'BPC-001', 'No Outside Opinion Sought', 'Behavioural', 'Nobody outside the founder has been asked whether the idea genuinely stands out.', 0.58, 'external', 'Stage 0'),
('RC-BPC-006', 'BPC-002', 'Regulatory Requirement Unknown', 'Knowledge', 'The founder is not aware that any regulatory approval is required at all.', 0.68, 'external', 'Stage 0'),
('RC-BPC-007', 'BPC-002', 'Assuming Natural Claims Avoid Regulation', 'Knowledge', 'It is assumed that labeling something natural or herbal removes the need for regulatory approval.', 0.63, 'external', 'Stage 0'),
('RC-BPC-008', 'BPC-002', 'No Basic Legal Research Done', 'Operational', 'No basic research has been done into what is legally required to sell this kind of product.', 0.62, 'external', 'Stage 0'),
('RC-BPC-009', 'BPC-002', 'Confusing Manufacturing With Legal Approval', 'Knowledge', 'The founder confuses being able to physically make the product with being legally allowed to sell it.', 0.60, 'external', 'Stage 0'),
('RC-BPC-010', 'BPC-003', 'Idea Based Purely on a Current Trend', 'Knowledge', 'The idea rests entirely on a currently popular ingredient or product type.', 0.63, 'external', 'Stage 0'),
('RC-BPC-011', 'BPC-003', 'No Thought on Trend Longevity', 'Strategic', 'No consideration has been given to whether this trend will still matter later.', 0.60, 'external', 'Stage 0'),
('RC-BPC-012', 'BPC-003', 'No Reason to Choose This Over the Trend Itself', 'Knowledge', 'There is no clear reason a customer would pick this product over simply buying the trending item elsewhere.', 0.62, 'external', 'Stage 0'),
('RC-BPC-013', 'BPC-003', 'No Personal or Business Reason Behind the Trend Choice', 'Behavioural', 'The trend was picked simply because it is popular, without a deeper reason connecting it to the founder or the business.', 0.58, 'external', 'Stage 0'),
('RC-BPC-014', 'BPC-004', 'No Specific Customer Type Chosen', 'Strategic', 'No specific type of customer has been chosen to build this product for.', 0.65, 'external', 'Stage 0'),
('RC-BPC-015', 'BPC-004', 'Idea Described as For Everyone', 'Behavioural', 'The idea is described broadly as being for everyone rather than a specific group.', 0.63, 'external', 'Stage 0'),
('RC-BPC-016', 'BPC-004', 'No Consideration of Skin Type, Age, or Concern', 'Knowledge', 'No thought has been given to how different skin types, ages, or specific concerns might need different versions.', 0.62, 'external', 'Stage 0'),
('RC-BPC-017', 'BPC-004', 'Assuming One Formulation Fits All', 'Knowledge', 'It is assumed that a single product formulation will work for every kind of customer.', 0.60, 'external', 'Stage 0'),
('RC-BPC-018', 'BPC-004', 'No Real First Customer Imagined', 'Behavioural', 'No specific, real person has been pictured as the actual first customer.', 0.58, 'external', 'Stage 0'),
('RC-BPC-019', 'BPC-005', 'Requirements Known but Not Filed', 'Operational', 'The founder knows the requirements but has not actually submitted the application.', 0.65, 'external', 'Stage 0â†’1'),
('RC-BPC-020', 'BPC-005', 'No Ingredient Safety Documentation', 'Operational', 'Required documentation on ingredient safety has not been prepared.', 0.63, 'external', 'Stage 0â†’1'),
('RC-BPC-021', 'BPC-005', 'No Approval Timeline in Launch Plan', 'Strategic', 'The launch plan does not account for how long approval actually takes.', 0.62, 'external', 'Stage 0â†’1'),
('RC-BPC-022', 'BPC-005', 'Assuming Approval Will Be Quick', 'Knowledge', 'The founder assumes the approval process will be fast and simple without confirming this.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BPC-023', 'BPC-006', 'No Shelf-Life Testing', 'Operational', 'No testing has been done to determine how long the product remains stable.', 0.65, 'external', 'Stage 0â†’1'),
('RC-BPC-024', 'BPC-006', 'Packaging Not Tested With Formulation', 'Operational', 'The packaging has never actually been tested together with the real product formulation.', 0.63, 'external', 'Stage 0â†’1'),
('RC-BPC-025', 'BPC-006', 'No Heat or Humidity Testing', 'Operational', 'The product has not been tested under real heat or humidity conditions.', 0.63, 'external', 'Stage 0â†’1'),
('RC-BPC-026', 'BPC-006', 'No Post-Shipping Performance Testing', 'Operational', 'There is no data on how the product performs after being shipped.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BPC-027', 'BPC-006', 'Assuming Lab Results Hold in Real Storage', 'Knowledge', 'It is assumed that lab testing results will hold true under real-world storage conditions.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BPC-028', 'BPC-007', 'Only Friends and Family Have Tried It', 'Operational', 'Testing has been limited to friends and family rather than genuine target customers.', 0.65, 'external', 'Stage 0â†’1'),
('RC-BPC-029', 'BPC-007', 'No Unbiased Outside Feedback', 'Operational', 'No feedback has been collected from anyone without a personal connection to the founder.', 0.63, 'external', 'Stage 0â†’1'),
('RC-BPC-030', 'BPC-007', 'Feedback Skewed by Relationship Bias', 'Behavioural', 'Feedback may be overly positive because testers do not want to disappoint the founder.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BPC-031', 'BPC-007', 'No Plan to Test With Strangers', 'Strategic', 'There is no plan to test the product with people who have no personal connection to the founder.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BPC-032', 'BPC-008', 'No Sample Strategy', 'Strategic', 'There is no defined strategy for offering samples or trial sizes.', 0.63, 'external', 'Stage 0â†’1'),
('RC-BPC-033', 'BPC-008', 'Sample Costs Not in Acquisition Math', 'Operational', 'The cost of giving out samples has not been factored into customer acquisition cost calculations.', 0.63, 'external', 'Stage 0â†’1'),
('RC-BPC-034', 'BPC-008', 'Assuming Full-Size Purchase Without Trial', 'Knowledge', 'It is assumed customers will buy full-size products without trying a sample first.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BPC-035', 'BPC-008', 'No Sample-to-Purchase Conversion Plan', 'Strategic', 'There is no plan for how sample recipients are expected to convert into full purchasers.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BPC-036', 'BPC-009', 'No Content Strategy', 'Strategic', 'There is no defined content strategy for reaching potential customers.', 0.63, 'external', 'Stage 0â†’1'),
('RC-BPC-037', 'BPC-009', 'No Influencer or Outreach Plan', 'Strategic', 'There is no plan for influencer partnerships or other outreach.', 0.62, 'external', 'Stage 0â†’1'),
('RC-BPC-038', 'BPC-009', 'Relying on Hope of Going Viral', 'Behavioural', 'The founder is relying on the hope of organic virality rather than a deliberate plan.', 0.63, 'external', 'Stage 0â†’1'),
('RC-BPC-039', 'BPC-009', 'No Marketing Budget Allocated', 'Operational', 'No budget has been set aside for marketing or content creation.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BPC-040', 'BPC-009', 'Target Customer Channel Unknown', 'Knowledge', 'It is not known which specific channel the real target customer actually spends time on.', 0.60, 'external', 'Stage 0â†’1'),
('RC-BPC-041', 'BPC-010', 'No Standardized Batch Process', 'Operational', 'There is no documented, repeatable process for producing a consistent batch.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-BPC-042', 'BPC-010', 'Batch Testing Inconsistent', 'Operational', 'Quality testing of batches happens irregularly rather than every time.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-BPC-043', 'BPC-010', 'Supplier Changes Not Checked for Consistency', 'Operational', 'Different suppliers are used without verifying whether that changes the final product.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BPC-044', 'BPC-010', 'No Pre-Ship Quality Checkpoint', 'Operational', 'There is no quality checkpoint before a batch ships to customers.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-BPC-045', 'BPC-010', 'Process Knowledge Lives With One Person', 'Operational', 'Exact process knowledge exists only in one person''s head, not documented anywhere.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BPC-046', 'BPC-011', 'No Margin Modeling Before Retail', 'Strategic', 'Retail margin impact was not modeled before entering retail channels.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-BPC-047', 'BPC-011', 'Retailer Terms Not Negotiated', 'Operational', 'Retailer terms were accepted as offered rather than negotiated.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BPC-048', 'BPC-011', 'Distributor Cuts Not Accounted For', 'Operational', 'Distributor fees were not factored in before signing agreements.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BPC-049', 'BPC-011', 'True Landed Cost Unknown', 'Knowledge', 'The real cost after every channel fee is included is not actually known.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-BPC-050', 'BPC-012', 'No Legal Protection on Formulation or Brand', 'Strategic', 'No trademark or formulation protection has been put in place.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-BPC-051', 'BPC-012', 'No Counterfeit Monitoring', 'Operational', 'There is no ongoing monitoring for counterfeit versions in the market.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-BPC-052', 'BPC-012', 'No Copycat Response Plan', 'Strategic', 'There is no plan for what to do if a copycat product appears.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-BPC-053', 'BPC-012', 'Assuming Brand Loyalty Prevents Copying', 'Knowledge', 'It is assumed that brand loyalty alone will stop customers from switching to a copycat.', 0.58, 'external', 'Stage 1â†’10+'),
('RC-BPC-054', 'BPC-013', 'Sales Concentrated in One or Two Influencers', 'Strategic', 'A majority of sales depend on just one or two influencer relationships.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-BPC-055', 'BPC-013', 'No Diversified Marketing Channels', 'Strategic', 'Marketing relies almost entirely on influencer partnerships, with no other channels developed.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-BPC-056', 'BPC-013', 'No Plan if Key Influencer Relationship Ends', 'Strategic', 'There is no contingency plan for if a major influencer relationship ends.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BPC-057', 'BPC-013', 'Brand Tied Too Closely to One Person', 'Strategic', 'The brand''s reputation is tied too closely to a single person''s public image.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-BPC-058', 'BPC-014', 'No Formal Complaint Logging System', 'Operational', 'There is no formal system for logging allergic reactions or complaints.', 0.68, 'external', 'Stage 1â†’10+'),
('RC-BPC-059', 'BPC-014', 'No Escalation Process for Serious Reactions', 'Operational', 'There is no defined process for escalating a serious reaction report.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-BPC-060', 'BPC-014', 'Return Process Not Built for Volume', 'Operational', 'The current return process was not designed to handle present order volume.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BPC-061', 'BPC-014', 'No Complaint Pattern Tracking', 'Operational', 'There is no tracking of whether complaints cluster around specific batches.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-BPC-062', 'BPC-014', 'No Legal or Medical Protocol for Reactions', 'Strategic', 'There is no defined legal or medical protocol for handling a serious reaction report.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-BPC-063', 'BPC-015', 'Assuming Domestic Regulations Apply Internationally', 'Knowledge', 'It is assumed the same regulations that apply domestically will apply in a new country.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-BPC-064', 'BPC-015', 'Target Country Regulations Not Researched', 'Operational', 'No research has been done into the specific cosmetic regulations of the target country.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-BPC-065', 'BPC-015', 'No Local Registration Started', 'Operational', 'No local registration or approval process has actually been started for the new country.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-BPC-066', 'BPC-015', 'Labeling Not Adapted for Target Country', 'Operational', 'Product labeling has not been adapted to meet the target country''s specific requirements.', 0.60, 'external', 'Stage 1â†’10+')
  ) AS v(root_cause_code, problem_code, root_cause_name, root_cause_category, explanation, confidence_weight, layer, primary_stage_group)
  JOIN new_problems p ON p.problem_code = v.problem_code
  RETURNING root_cause_id, root_cause_code
),
new_questions AS (
  INSERT INTO questions (question_code, category, question_text, problem_id, root_cause_id, question_type, difficulty_level, priority, is_distress_tagged, industry_relevance, embedding, primary_stage_group, embedding_model, embedding_version, embedding_dimension)
  SELECT v.question_code, 'Idea & Validation', v.question_text, p.problem_id, rc.root_cause_id, 'open_text', v.difficulty_level, v.priority, false, '["beauty_personal_care"]'::jsonb, array_fill(0, ARRAY[1536])::vector, v.stage_group, NULL, NULL, NULL
  FROM (VALUES
('S0-BPC-001', 'BPC-001', 'RC-BPC-001', 'If someone asked what makes your product different from what''s already sold in a store, what would you say?', 1, 'CORE', 'Stage 0'),
('S0-BPC-002', 'BPC-001', 'RC-BPC-002', 'Is your idea mostly inspired by copying an existing brand, or does it add something genuinely new?', 1, 'CORE', 'Stage 0'),
('S0-BPC-003', 'BPC-001', 'RC-BPC-003', 'Have you looked at what else already exists that''s similar to your idea?', 1, 'CORE', 'Stage 0'),
('S0-BPC-004', 'BPC-001', 'RC-BPC-004', 'If your only answer is "better quality," do you think that''s enough to make someone switch?', 2, 'SUPPLEMENTARY', 'Stage 0'),
('S0-BPC-005', 'BPC-002', 'RC-BPC-006', 'Do you know that beauty and personal care products need some kind of government approval before you can sell them?', 1, 'CORE', 'Stage 0'),
('S0-BPC-006', 'BPC-002', 'RC-BPC-007', 'Are you assuming that calling something "natural" or "herbal" means you don''t need any approval?', 2, 'CORE', 'Stage 0'),
('S0-BPC-007', 'BPC-002', 'RC-BPC-008', 'Have you looked into what''s legally required to sell this, even at a basic level?', 1, 'CORE', 'Stage 0'),
('S0-BPC-008', 'BPC-003', 'RC-BPC-010', 'Is this idea based on something trending right now -- and have you thought about whether that trend will still matter in a year?', 2, 'CORE', 'Stage 0'),
('S0-BPC-009', 'BPC-003', 'RC-BPC-011', 'If this trend faded tomorrow, would your idea still make sense?', 2, 'CORE', 'Stage 0'),
('S0-BPC-010', 'BPC-003', 'RC-BPC-012', 'Why would someone choose your version of this trend over just buying the trending product directly?', 2, 'CORE', 'Stage 0'),
('S0-BPC-011', 'BPC-003', 'RC-BPC-013', 'Is there a personal reason you''re drawn to this idea, or did you pick it because it''s popular right now?', 1, 'SUPPLEMENTARY', 'Stage 0'),
('S0-BPC-012', 'BPC-004', 'RC-BPC-014', 'Can you describe exactly who this product is for, or is it "for everyone" right now?', 1, 'CORE', 'Stage 0'),
('S0-BPC-013', 'BPC-004', 'RC-BPC-016', 'Have you thought about how different skin types or ages might need different versions of this?', 2, 'CORE', 'Stage 0'),
('S0-BPC-014', 'BPC-004', 'RC-BPC-018', 'If you had to picture one real person buying this first, who would that be?', 1, 'CORE', 'Stage 0'),
('S0-BPC-015', 'BPC-004', 'RC-BPC-017', 'Are you assuming one version of this product works for every kind of customer?', 1, 'CORE', 'Stage 0'),
('S01-BPC-001', 'BPC-005', 'RC-BPC-019', 'Have you actually applied for the approval you now know you need, or is that still pending?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BPC-002', 'BPC-005', 'RC-BPC-020', 'Do you have the ingredient safety documentation ready, or is that still missing?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BPC-003', 'BPC-005', 'RC-BPC-021', 'Have you built approval timing into your launch plan, or are you assuming it''ll be quick?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BPC-004', 'BPC-005', 'RC-BPC-022', 'What''s actually stopping you from submitting your application this month?', 2, 'SUPPLEMENTARY', 'Stage 0â†’1'),
('S01-BPC-005', 'BPC-006', 'RC-BPC-023', 'Has your product been tested to see how long it stays stable before it degrades?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BPC-006', 'BPC-006', 'RC-BPC-024', 'Has your packaging actually been tested with your real formulation, not just assumed to work?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BPC-007', 'BPC-006', 'RC-BPC-025', 'Has this been tested under real heat or humidity, or only in ideal lab conditions?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BPC-008', 'BPC-006', 'RC-BPC-026', 'Do you know how your product holds up after being shipped, not just sitting on a shelf?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BPC-009', 'BPC-006', 'RC-BPC-027', 'Are you assuming your lab testing results will hold once it''s in real storage conditions?', 3, 'CORE', 'Stage 0â†’1'),
('S01-BPC-010', 'BPC-007', 'RC-BPC-028', 'Has anyone outside your friends and family actually tried this and given honest feedback?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BPC-011', 'BPC-007', 'RC-BPC-030', 'Could the positive feedback you''ve gotten be because people don''t want to disappoint you?', 3, 'CORE', 'Stage 0â†’1'),
('S01-BPC-012', 'BPC-007', 'RC-BPC-029', 'Have you gotten any feedback from someone with zero personal connection to you?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BPC-013', 'BPC-007', 'RC-BPC-031', 'Do you have a plan to test this with complete strangers before you launch?', 2, 'SUPPLEMENTARY', 'Stage 0â†’1'),
('S01-BPC-014', 'BPC-008', 'RC-BPC-032', 'Have you planned for giving out samples, and does your cost model account for that?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BPC-015', 'BPC-008', 'RC-BPC-033', 'Have you built the cost of samples into how you calculate customer acquisition cost?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BPC-016', 'BPC-008', 'RC-BPC-034', 'Are you assuming customers will buy full-size without trying it first?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BPC-017', 'BPC-008', 'RC-BPC-035', 'Do you know what percentage of sample-takers you''d need to convert to make this work?', 3, 'CORE', 'Stage 0â†’1'),
('S01-BPC-018', 'BPC-009', 'RC-BPC-038', 'Do you have any real plan for how people will discover this, or are you hoping it goes viral?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BPC-019', 'BPC-009', 'RC-BPC-036', 'Do you have any actual content or influencer outreach plan, or is that still undefined?', 2, 'CORE', 'Stage 0â†’1'),
('S01-BPC-020', 'BPC-009', 'RC-BPC-040', 'Do you know which specific channel your real target customers actually spend time on?', 2, 'CORE', 'Stage 0â†’1'),
('S10-BPC-001', 'BPC-010', 'RC-BPC-041', 'Does every batch actually match the one before it, or does quality vary depending on who made it?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-002', 'BPC-010', 'RC-BPC-042', 'Is batch testing something you do every time, or only sometimes?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-003', 'BPC-010', 'RC-BPC-043', 'If you switched suppliers, would you actually know if that changed your product?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-004', 'BPC-010', 'RC-BPC-044', 'Is there a quality check before a batch ships, or does it just go out?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-005', 'BPC-010', 'RC-BPC-045', 'If the person who knows your exact process left, could anyone else replicate it?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-006', 'BPC-011', 'RC-BPC-046', 'Did you model your margins before agreeing to retailer terms, or after?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-007', 'BPC-011', 'RC-BPC-047', 'Were your retailer terms negotiated, or did you accept whatever was offered?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-008', 'BPC-011', 'RC-BPC-048', 'Did you account for distributor cuts before signing, or did that surprise you later?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-009', 'BPC-011', 'RC-BPC-049', 'Do you actually know your true landed cost after every channel fee is included?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-010', 'BPC-012', 'RC-BPC-050', 'Do you have any legal protection on your formulation or brand name?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-011', 'BPC-012', 'RC-BPC-051', 'Do you monitor the market for counterfeit versions of your product?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-012', 'BPC-012', 'RC-BPC-052', 'If a copycat appeared tomorrow, would you have any real plan to respond?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-013', 'BPC-012', 'RC-BPC-053', 'Are you assuming brand loyalty alone will stop people from copying you?', 2, 'SUPPLEMENTARY', 'Stage 1â†’10+'),
('S10-BPC-014', 'BPC-013', 'RC-BPC-054', 'If your top influencer disappeared tomorrow, would your sales survive?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-015', 'BPC-013', 'RC-BPC-055', 'How many different marketing channels do you actually rely on, beyond influencers?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-016', 'BPC-013', 'RC-BPC-056', 'Do you have a plan for what happens if a key influencer relationship ends badly?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-017', 'BPC-013', 'RC-BPC-057', 'Is your brand''s reputation tied too closely to one person''s public image?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-018', 'BPC-014', 'RC-BPC-058', 'Do you have a real system for handling allergic reactions and complaints at your current volume?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-019', 'BPC-014', 'RC-BPC-059', 'Is there a clear escalation process for a serious reaction report?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-020', 'BPC-014', 'RC-BPC-060', 'Can your return process actually handle your current order volume?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-021', 'BPC-014', 'RC-BPC-061', 'Do you track whether complaints are clustering around a specific batch?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-022', 'BPC-014', 'RC-BPC-062', 'If a serious reaction were reported, do you know the right legal or medical steps to take?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-023', 'BPC-015', 'RC-BPC-063', 'Are you assuming the same regulations that apply here will apply in a new country?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-024', 'BPC-015', 'RC-BPC-064', 'Have you actually researched your target country''s cosmetic regulations?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-BPC-025', 'BPC-015', 'RC-BPC-065', 'Have you started any local registration process for the country you''re expanding into?', 2, 'CORE', 'Stage 1â†’10+')
  ) AS v(question_code, problem_code, root_cause_code, question_text, difficulty_level, priority, stage_group)
  JOIN new_problems p ON p.problem_code = v.problem_code
  JOIN new_root_causes rc ON rc.root_cause_code = v.root_cause_code
  RETURNING question_id, question_code
),
new_tags AS (
  INSERT INTO question_tag_mapping (question_id, tag_id)
  SELECT q.question_id, v.tag_id
  FROM (VALUES
('S0-BPC-001', 4), ('S0-BPC-002', 4), ('S0-BPC-003', 4), ('S0-BPC-004', 4), ('S0-BPC-005', 4), ('S0-BPC-006', 4), ('S0-BPC-007', 4),
('S0-BPC-008', 2), ('S0-BPC-009', 2), ('S0-BPC-010', 2), ('S0-BPC-011', 2),
('S0-BPC-012', 3), ('S0-BPC-013', 3), ('S0-BPC-014', 3), ('S0-BPC-015', 3),
('S01-BPC-001', 4), ('S01-BPC-002', 4), ('S01-BPC-003', 4), ('S01-BPC-004', 4),
('S01-BPC-005', 33), ('S01-BPC-006', 33), ('S01-BPC-007', 33), ('S01-BPC-008', 33), ('S01-BPC-009', 33),
('S01-BPC-010', 2), ('S01-BPC-011', 2), ('S01-BPC-012', 2), ('S01-BPC-013', 2),
('S01-BPC-014', 84), ('S01-BPC-015', 84), ('S01-BPC-016', 84), ('S01-BPC-017', 84),
('S01-BPC-018', 12), ('S01-BPC-019', 12), ('S01-BPC-020', 12),
('S10-BPC-001', 33), ('S10-BPC-002', 33), ('S10-BPC-003', 33), ('S10-BPC-004', 33), ('S10-BPC-005', 33),
('S10-BPC-006', 84), ('S10-BPC-007', 84), ('S10-BPC-008', 84), ('S10-BPC-009', 84),
('S10-BPC-010', 4), ('S10-BPC-011', 4), ('S10-BPC-012', 4), ('S10-BPC-013', 4),
('S10-BPC-014', 12), ('S10-BPC-015', 12), ('S10-BPC-016', 12), ('S10-BPC-017', 12),
('S10-BPC-018', 36), ('S10-BPC-019', 36), ('S10-BPC-020', 36), ('S10-BPC-021', 36), ('S10-BPC-022', 36),
('S10-BPC-023', 4), ('S10-BPC-024', 4), ('S10-BPC-025', 4)
  ) AS v(question_code, tag_id)
  JOIN new_questions q ON q.question_code = v.question_code
  RETURNING mapping_id
),
new_interventions AS (
  INSERT INTO interventions (intervention_code, problem_id, root_cause_ids, secondary_root_cause_ids, capability_domain, section, recommended_frameworks, framework_codes, immediate_next_steps, stage_relevance, industry_relevance, design_principles)
  SELECT v.intervention_code, p.problem_id, v.root_cause_ids, '[]'::jsonb, v.capability_domain, v.section, v.recommended_frameworks, NULL, v.immediate_next_steps, v.stage_relevance, '["beauty_personal_care"]'::jsonb, v.design_principles
  FROM (VALUES
('INT-BPC-001', 'BPC-001', '["RC-BPC-001", "RC-BPC-004"]'::jsonb, 'Market Validation', 'Ideation â€” Beauty Market Fundamentals', '[{"name": "Differentiation Statement", "brief": "Writing a single, clear sentence describing what makes the product different."}]'::jsonb, '["Write one sentence describing what makes your product different.", "If you cannot write it clearly, treat that as your real starting point.", "Test this sentence on someone unfamiliar with your idea."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-002', 'BPC-001', '["RC-BPC-003"]'::jsonb, 'Market Validation', 'Ideation â€” Beauty Market Fundamentals', '[{"name": "Competitor Comparison List", "brief": "Listing existing brands doing something similar and comparing honestly."}]'::jsonb, '["List 3 existing brands doing something similar.", "Compare your idea against each one honestly.", "Identify what, if anything, is genuinely different."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-003', 'BPC-001', '["RC-BPC-005"]'::jsonb, 'Market Validation', 'Ideation â€” Beauty Market Fundamentals', '[{"name": "Outside Perspective Check", "brief": "Asking people outside the founder''s own circle whether the idea stands out."}]'::jsonb, '["Describe your idea to 5 people outside your close circle.", "Ask them directly what stands out, if anything.", "Note honestly if nobody mentions something unique."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-004', 'BPC-002', '["RC-BPC-006", "RC-BPC-008"]'::jsonb, 'Regulatory Compliance', 'Ideation â€” Beauty Market Fundamentals', '[{"name": "Basic Regulatory Awareness Check", "brief": "Confirming at a basic level that regulatory approval is required, before diving into specifics."}]'::jsonb, '["Search for what approval beauty products need in India.", "Confirm this applies to your specific type of product.", "Note this as a real requirement, not optional research."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-005', 'BPC-002', '["RC-BPC-007", "RC-BPC-009"]'::jsonb, 'Regulatory Compliance', 'Ideation â€” Beauty Market Fundamentals', '[{"name": "Talk to Someone Who Has Launched", "brief": "Speaking directly with someone who has actually launched a beauty product about the approval process."}]'::jsonb, '["Find one person who has launched a beauty or personal care product.", "Ask them specifically what approval they needed.", "Ask whether natural or herbal claims changed anything for them."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-006', 'BPC-003', '["RC-BPC-010", "RC-BPC-011"]'::jsonb, 'Market Validation', 'Ideation â€” Beauty Market Fundamentals', '[{"name": "Trend Longevity Check", "brief": "Deliberately asking whether the idea would still make sense if the current trend disappeared."}]'::jsonb, '["Ask yourself if this idea would still make sense without the current trend.", "Write down what happens to your business if the trend disappears in 6 months.", "Decide if that risk feels acceptable to you."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-007', 'BPC-003', '["RC-BPC-012", "RC-BPC-013"]'::jsonb, 'Market Validation', 'Ideation â€” Beauty Market Fundamentals', '[{"name": "Personal Reason Reflection", "brief": "Writing down the founder''s own reason for choosing this idea, beyond its current popularity."}]'::jsonb, '["Write down your personal reason for choosing this idea, if any.", "If the only reason is popularity, sit with that honestly.", "Consider whether a less trendy but more personal idea might serve you better."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-008', 'BPC-004', '["RC-BPC-014", "RC-BPC-015"]'::jsonb, 'Customer Definition', 'Ideation â€” Beauty Market Fundamentals', '[{"name": "First Customer Selection", "brief": "Picking one specific type of customer to build for first, instead of everyone."}]'::jsonb, '["Pick one specific type of customer to build for first.", "Write down why you chose that group specifically.", "Set aside every other customer type for now."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-009', 'BPC-004', '["RC-BPC-016", "RC-BPC-017"]'::jsonb, 'Customer Definition', 'Ideation â€” Beauty Market Fundamentals', '[{"name": "Real Customer Profile", "brief": "Describing one specific, real first customer in detail."}]'::jsonb, '["Describe your first real customer in detail -- age, skin type, concern.", "Check whether your current idea actually fits that specific person.", "Adjust the idea if it does not fit them well."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-010', 'BPC-004', '["RC-BPC-018"]'::jsonb, 'Customer Definition', 'Ideation â€” Beauty Market Fundamentals', '[{"name": "Imagined First Sale", "brief": "Picturing the actual first sale happening to a specific, real person."}]'::jsonb, '["Picture the moment your first sale actually happens.", "Name the specific person it happens to.", "Use that picture to check if your idea is specific enough."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-011', 'BPC-005', '["RC-BPC-019", "RC-BPC-022"]'::jsonb, 'Regulatory Compliance', 'Validation â€” Beauty Real-World Readiness', '[{"name": "Regulatory Application Submission", "brief": "Actually submitting the regulatory application rather than continuing to prepare it."}]'::jsonb, '["Identify exactly what''s needed to submit today.", "Submit the application this month.", "Set a follow-up date to check on status."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-012', 'BPC-005', '["RC-BPC-020", "RC-BPC-021"]'::jsonb, 'Regulatory Compliance', 'Validation â€” Beauty Real-World Readiness', '[{"name": "Ingredient Documentation Compilation", "brief": "Compiling required ingredient safety documentation and building approval time into the launch plan."}]'::jsonb, '["Compile your ingredient safety documentation now.", "Confirm the real approval timeline for your category.", "Adjust your launch date to reflect that real timeline."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-013', 'BPC-006', '["RC-BPC-023", "RC-BPC-027"]'::jsonb, 'Product Validation', 'Validation â€” Beauty Real-World Readiness', '[{"name": "Shelf-Life and Stability Testing", "brief": "Getting real shelf-life and stability testing done before scaling production."}]'::jsonb, '["Send your formulation for real shelf-life testing.", "Do not rely on assumptions from similar products.", "Wait for real results before committing to larger production runs."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-014', 'BPC-006', '["RC-BPC-024", "RC-BPC-025", "RC-BPC-026"]'::jsonb, 'Product Validation', 'Validation â€” Beauty Real-World Readiness', '[{"name": "Real-Condition Packaging Test", "brief": "Testing packaging together with the real formulation under heat, humidity, and shipping conditions."}]'::jsonb, '["Test your actual packaging with your actual formulation.", "Expose a test batch to real heat and humidity.", "Ship a test batch to yourself and check its condition on arrival."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-015', 'BPC-007', '["RC-BPC-028", "RC-BPC-029"]'::jsonb, 'Customer Validation', 'Validation â€” Beauty Real-World Readiness', '[{"name": "Outside Feedback Collection", "brief": "Getting honest feedback from people with no personal connection to the founder."}]'::jsonb, '["Find 10 people with no personal connection to you.", "Get them to actually try the product.", "Collect their honest feedback directly."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-016', 'BPC-007', '["RC-BPC-030", "RC-BPC-031"]'::jsonb, 'Customer Validation', 'Validation â€” Beauty Real-World Readiness', '[{"name": "Blind Feedback Test", "brief": "Running a test where the person giving feedback does not know the founder personally."}]'::jsonb, '["Find a tester who does not know you personally.", "Have someone else run the feedback session if possible.", "Compare this feedback against feedback from friends and family."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-017', 'BPC-008', '["RC-BPC-032", "RC-BPC-033"]'::jsonb, 'Financial Planning', 'Validation â€” Beauty Real-World Readiness', '[{"name": "Sample Cost Integration", "brief": "Building the real cost of samples directly into customer acquisition cost calculations."}]'::jsonb, '["Calculate the real cost of producing and shipping one sample.", "Add this cost into your customer acquisition math.", "Recalculate your unit economics with samples included."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-018', 'BPC-008', '["RC-BPC-034", "RC-BPC-035"]'::jsonb, 'Financial Planning', 'Validation â€” Beauty Real-World Readiness', '[{"name": "Sample Conversion Rate Calculation", "brief": "Calculating the real sample-to-purchase conversion rate needed to make the model work."}]'::jsonb, '["Run a small sample batch and track who converts to a full purchase.", "Calculate your real conversion rate from that test.", "Check whether that rate makes your business model viable."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-019', 'BPC-009', '["RC-BPC-036", "RC-BPC-038"]'::jsonb, 'Marketing Strategy', 'Validation â€” Beauty Real-World Readiness', '[{"name": "Deliberate Content Plan", "brief": "Building one real, deliberate content or influencer outreach plan instead of hoping for organic virality."}]'::jsonb, '["Choose one specific content or outreach approach to try.", "Build a simple, concrete plan for executing it.", "Commit to running it consistently before judging results."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-020', 'BPC-009', '["RC-BPC-040"]'::jsonb, 'Marketing Strategy', 'Validation â€” Beauty Real-World Readiness', '[{"name": "Target Channel Identification", "brief": "Identifying the specific channel where the real target customer actually spends time."}]'::jsonb, '["Ask your actual target customers where they spend time online.", "Identify one specific channel based on that answer.", "Focus your outreach there before spreading across many channels."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-021', 'BPC-005', '["RC-BPC-019"]'::jsonb, 'Regulatory Compliance', 'Validation â€” Beauty Real-World Readiness', '[{"name": "Application Deadline Setting", "brief": "Setting a specific, firm deadline for submitting the regulatory application."}]'::jsonb, '["Set a specific date to submit your application.", "Tell someone else this deadline to create accountability.", "Treat this date as non-negotiable."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-022', 'BPC-009', '["RC-BPC-039"]'::jsonb, 'Marketing Strategy', 'Validation â€” Beauty Real-World Readiness', '[{"name": "Marketing Budget Allocation", "brief": "Allocating a real marketing budget instead of relying on organic virality alone."}]'::jsonb, '["Set aside a specific budget for marketing, even if small.", "Spend it deliberately on one tested channel.", "Track results instead of hoping for organic reach."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-023', 'BPC-010', '["RC-BPC-041", "RC-BPC-044"]'::jsonb, 'Quality Management', 'Growth â€” Beauty Production Quality at Scale', '[{"name": "Standardized Batch Process", "brief": "Documenting a repeatable process with a quality checkpoint before shipping."}]'::jsonb, '["Document your exact batch process step by step.", "Define one clear quality checkpoint before shipping.", "Train anyone involved in production against that standard."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-024', 'BPC-010', '["RC-BPC-042", "RC-BPC-043", "RC-BPC-045"]'::jsonb, 'Quality Management', 'Growth â€” Beauty Production Quality at Scale', '[{"name": "Process Documentation and Consistency Testing", "brief": "Documenting exact process knowledge and testing consistency across suppliers and batches."}]'::jsonb, '["Write down your exact process so it does not live with one person only.", "Test consistency whenever a supplier changes.", "Run batch testing on every single batch, not just occasionally."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-025', 'BPC-011', '["RC-BPC-046", "RC-BPC-047"]'::jsonb, 'Financial Planning', 'Growth â€” Retail & Distribution Economics', '[{"name": "Retail Margin Modeling", "brief": "Modeling real margins before signing any retailer agreement."}]'::jsonb, '["Model your margin under the exact terms being offered.", "Identify your walk-away point before negotiating.", "Negotiate from that model, not from eagerness to get into the channel."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-026', 'BPC-011', '["RC-BPC-048", "RC-BPC-049"]'::jsonb, 'Financial Planning', 'Growth â€” Retail & Distribution Economics', '[{"name": "True Landed Cost Calculation", "brief": "Calculating the complete true cost after every channel fee is included."}]'::jsonb, '["List every fee involved in a retail or distributor transaction.", "Calculate your true landed cost including all of them.", "Compare this against your actual selling price."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-027', 'BPC-012', '["RC-BPC-050"]'::jsonb, 'Brand Protection', 'Growth â€” Counterfeit & IP Risk', '[{"name": "Formulation and Brand Legal Protection", "brief": "Registering trademark or formulation protection for real legal standing."}]'::jsonb, '["Identify what can realistically be trademarked or protected.", "File for that protection.", "Keep documentation proving your original development."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-028', 'BPC-012', '["RC-BPC-051", "RC-BPC-052", "RC-BPC-053"]'::jsonb, 'Brand Protection', 'Growth â€” Counterfeit & IP Risk', '[{"name": "Counterfeit Monitoring and Response Plan", "brief": "Setting up ongoing market monitoring and a real plan for responding if a copycat appears."}]'::jsonb, '["Set up a regular check for counterfeit listings online.", "Draft a response plan for if a copycat appears.", "Do not rely on brand loyalty alone as your only defense."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-029', 'BPC-013', '["RC-BPC-054", "RC-BPC-055"]'::jsonb, 'Marketing Strategy', 'Growth â€” Influencer Dependency Risk', '[{"name": "Marketing Channel Diversification", "brief": "Actively building marketing channels beyond dependency on a small number of influencers."}]'::jsonb, '["Identify your current percentage of sales from top influencers.", "Test one new marketing channel this quarter.", "Set a target to reduce influencer concentration over time."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-030', 'BPC-013', '["RC-BPC-056", "RC-BPC-057"]'::jsonb, 'Marketing Strategy', 'Growth â€” Influencer Dependency Risk', '[{"name": "Influencer Relationship Contingency Plan", "brief": "Building a contingency plan for if a key influencer relationship ends."}]'::jsonb, '["Identify what happens to sales if your top influencer left today.", "Build a contingency plan for that scenario.", "Reduce how tightly the brand''s image depends on one person."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-031', 'BPC-014', '["RC-BPC-058", "RC-BPC-060"]'::jsonb, 'Customer Operations', 'Growth â€” Reaction & Complaint Handling at Scale', '[{"name": "Scaled Complaint and Return System", "brief": "Building a formal system for logging complaints and handling returns at current volume."}]'::jsonb, '["Set up a formal system for logging every complaint or reaction.", "Review whether your return process can handle current volume.", "Fix any bottleneck found in that review."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-032', 'BPC-014', '["RC-BPC-059", "RC-BPC-061", "RC-BPC-062"]'::jsonb, 'Customer Operations', 'Growth â€” Reaction & Complaint Handling at Scale', '[{"name": "Reaction Escalation Protocol", "brief": "Defining a clear escalation protocol with legal and medical steps for serious reaction reports."}]'::jsonb, '["Define what counts as a serious reaction requiring escalation.", "Write the exact legal and medical steps to take.", "Track whether complaints cluster around specific batches."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-033', 'BPC-015', '["RC-BPC-063", "RC-BPC-064"]'::jsonb, 'Regulatory Compliance', 'Growth â€” International Expansion Readiness', '[{"name": "Target Country Regulatory Research", "brief": "Researching the specific cosmetic regulations of the target country before assuming they match domestic rules."}]'::jsonb, '["Research cosmetic regulations specific to your target country.", "Do not assume domestic approval transfers automatically.", "Identify exactly what differs from your current regulatory position."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-BPC-034', 'BPC-015', '["RC-BPC-065", "RC-BPC-066"]'::jsonb, 'Regulatory Compliance', 'Growth â€” International Expansion Readiness', '[{"name": "Early Local Registration and Labeling", "brief": "Starting local registration and adapting labeling well before committing to a launch date."}]'::jsonb, '["Start the local registration process now, not right before launch.", "Adapt your product labeling to target country requirements.", "Build registration timelines into your expansion launch date."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb)
  ) AS v(intervention_code, problem_code, root_cause_ids, capability_domain, section, recommended_frameworks, immediate_next_steps, stage_relevance, design_principles)
  JOIN new_problems p ON p.problem_code = v.problem_code
  RETURNING intervention_id, intervention_code
)
SELECT
  (SELECT COUNT(*) FROM new_problems) as problems_inserted,
  (SELECT COUNT(*) FROM new_root_causes) as root_causes_inserted,
  (SELECT COUNT(*) FROM new_questions) as questions_inserted,
  (SELECT COUNT(*) FROM new_tags) as tags_inserted,
  (SELECT COUNT(*) FROM new_interventions) as interventions_inserted;"""),

        ('Construction & Real Estate / PropTech', 'proptech', 'PRP', r"""WITH new_problems AS (
  INSERT INTO problems (problem_code, problem_name, category, subcategory, layer, description, severity_min, severity_max, symptoms, pillar_id, industry_relevance, embedding, embedding_model, embedding_version, embedding_dimension)
  SELECT v.problem_code, v.problem_name, v.category, v.subcategory, v.layer, v.description, v.severity_min, v.severity_max, v.symptoms, v.pillar_id, '["proptech"]'::jsonb, array_fill(0, ARRAY[1536])::vector, NULL, NULL, NULL
  FROM (VALUES
('PRP-001', 'Idea Not Differentiated From Existing Players', 'Idea & Validation', 'PropTech Market Validation', 'external', 'There are already many real estate and proptech platforms and construction businesses, and the founder has not identified what is genuinely different about theirs.', 3, 7, '["No clear point of difference has been identified", "Idea copies an existing real estate platform without adding anything new", "No research has been done on what else already exists in this space", "Assuming a nicer interface or app is enough differentiation", "No one else has been asked whether this idea stands out"]'::jsonb, 2),
('PRP-002', 'Unclear Which Part of Real Estate This Serves', 'Idea & Validation', 'PropTech Market Validation', 'external', 'This space is broad, covering developers, buyers, renters, contractors, and architects, and the founder has not picked a clear customer type.', 3, 7, '["No specific customer type has been chosen", "Idea is described as being for the real estate industry broadly", "No thought given to how different these customer types'' needs actually are", "Assuming one product serves everyone in the property chain"]'::jsonb, 2),
('PRP-003', 'Underestimating How Long Real Estate Deals Take', 'Idea & Validation', 'PropTech Market Validation', 'external', 'Property and construction transactions naturally take months or years, and the founder is assuming a fast, typical software timeline.', 3, 7, '["Founder is comparing this to how fast a typical app or software deal closes", "No research done on actual average timelines for property or construction deals", "Assuming urgency or excitement will speed up a naturally slow process", "No plan exists for how the business survives during naturally long deal cycles"]'::jsonb, 2),
('PRP-004', 'No Understanding of Who Makes the Buying Decision', 'Idea & Validation', 'PropTech Market Validation', 'external', 'Real estate decisions often involve multiple people, such as a buyer, spouse, broker, and bank, and this has not been thought through.', 3, 7, '["Assuming the person using the app is the only decision-maker", "No thought given to the role of a spouse, family member, or co-owner", "No thought given to the role of a broker, agent, or intermediary", "No thought given to the role of a bank or lender in the decision", "Assuming a purely digital decision process with no offline influence"]'::jsonb, 2),
('PRP-005', 'Listing or Property Data Accuracy Not Verified', 'Idea & Validation', 'PropTech Market Validation', 'external', 'Property details, pricing, or availability shown on the platform have not been checked against reality, and stale or wrong data breaks trust fast in this space.', 4, 8, '["No process exists for verifying listing accuracy", "Data is pulled from an unreliable source", "No process exists for updating stale listings", "Assuming listers will keep information accurate on their own"]'::jsonb, 2),
('PRP-006', 'Legal and Paperwork Complexity Underestimated', 'Idea & Validation', 'PropTech Market Validation', 'external', 'Real estate involves title checks, registration, contracts, and local paperwork that the founder has not actually navigated yet.', 4, 8, '["No understanding exists of local registration requirements", "No lawyer or legal consultant is involved yet", "Assuming standard contract templates are sufficient", "No process exists for handling title or ownership verification", "Underestimating the time and cost of legal compliance"]'::jsonb, 2),
('PRP-007', 'Broker or Agent Relationship Not Established', 'Idea & Validation', 'PropTech Market Validation', 'external', 'Much of real estate still flows through brokers and agents, and the founder has not built any real relationship with them or tested working with or around them.', 3, 7, '["No real relationship has been built with brokers or agents", "Assuming the platform can bypass brokers entirely", "No understanding of how brokers are compensated in this market", "No plan exists for how brokers would actually use or adopt the platform"]'::jsonb, 2),
('PRP-008', 'No Real Transaction Completed', 'Idea & Validation', 'PropTech Market Validation', 'external', 'The product has generated interest or leads, but no actual deal, such as a sale, rental, or signed contract, has gone all the way through.', 4, 8, '["Interest and leads have been generated but no deal has closed", "No process exists for guiding a lead through to actual completion", "Assuming interest automatically converts to a completed deal", "No manual effort has been applied to push even one deal through"]'::jsonb, 2),
('PRP-009', 'Trust Signals Not Built', 'Idea & Validation', 'PropTech Market Validation', 'external', 'Buyers and renters need to trust a platform with large sums of money, and no verification badges, reviews, or credibility markers exist yet.', 3, 7, '["No verification badges or credibility markers exist", "No reviews or testimonials have been collected yet", "No transparency exists into who is behind the platform or listings", "Assuming trust will build automatically over time", "No plan exists for how to earn trust before asking for large financial commitments"]'::jsonb, 2),
('PRP-010', 'Multi-City Regulatory Reset', 'Idea & Validation', 'PropTech Market Validation', 'external', 'Every city or state has different property laws, registration processes, and stamp duty rules, and expansion is being treated like a copy-paste of one city''s playbook.', 4, 8, '["No city-by-city regulatory checklist exists", "Assuming one city''s registration process transfers to another", "No local legal partner exists in new markets", "Stamp duty and registration cost differences have not been researched"]'::jsonb, 2),
('PRP-011', 'Construction Quality and Delay Risk at Scale', 'Idea & Validation', 'PropTech Market Validation', 'external', 'Managing multiple construction projects or listings simultaneously means quality and timeline issues that were manageable at small scale now compound.', 4, 8, '["No standardized quality control exists across multiple projects", "No centralized timeline tracking exists across projects", "Different contractors are held to different standards", "No early warning system exists for delays", "No process exists for handling recurring contractor issues"]'::jsonb, 2),
('PRP-012', 'Escrow and Payment Trust at Volume', 'Idea & Validation', 'PropTech Market Validation', 'external', 'As transaction values and volume grow, handling large sums of money such as deposits and escrow safely and compliantly becomes a much bigger operational and legal challenge.', 5, 9, '["No compliant escrow system is in place", "Large sums are handled without a proper legal structure", "No third-party escrow partner has been engaged", "No audit trail exists for fund movements"]'::jsonb, 2),
('PRP-013', 'Fraud and Fake Listing Risk', 'Idea & Validation', 'PropTech Market Validation', 'external', 'At scale, bad actors post fake listings or attempt fraud, and there is no real system to detect or prevent this.', 4, 8, '["No fraud detection process exists", "No verification step exists before listings go live", "No process exists for reporting or removing fraudulent listings", "No monitoring exists for repeat fraudulent actors"]'::jsonb, 2),
('PRP-014', 'Inventory or Supply Concentration Risk', 'Idea & Validation', 'PropTech Market Validation', 'external', 'Too much of the business depends on a small number of developers, projects, or property owners.', 4, 8, '["Majority of listings or projects are tied to a small number of developers", "No plan exists to diversify supply sources", "No backup relationship exists if a top supplier leaves", "No tracking exists of supply concentration over time", "Growth targets are not checked against supply diversity"]'::jsonb, 2),
('PRP-015', 'Long-Term Liability and Dispute Exposure', 'Idea & Validation', 'PropTech Market Validation', 'external', 'Real estate disputes, such as defects, boundary issues, or payment disputes, can surface years after a transaction, and no plan exists for this long-tail legal exposure.', 4, 9, '["No document retention system exists for past transactions", "No legal protocol exists for handling a dispute that surfaces late", "No insurance or liability coverage exists for long-tail claims", "Assuming closed transactions carry no ongoing risk"]'::jsonb, 2)
  ) AS v(problem_code, problem_name, category, subcategory, layer, description, severity_min, severity_max, symptoms, pillar_id)
  RETURNING problem_id, problem_code
),
new_root_causes AS (
  INSERT INTO root_causes (root_cause_code, problem_id, root_cause_name, root_cause_category, explanation, confidence_weight, layer, primary_stage_group, industry_relevance, embedding, embedding_model, embedding_version, embedding_dimension)
  SELECT v.root_cause_code, p.problem_id, v.root_cause_name, v.root_cause_category, v.explanation, v.confidence_weight, v.layer, v.primary_stage_group, '["proptech"]'::jsonb, array_fill(0, ARRAY[1536])::vector, NULL, NULL, NULL
  FROM (VALUES
('RC-PRP-001', 'PRP-001', 'No Clear Point of Difference', 'Knowledge', 'The founder has not identified what actually makes this idea different from what already exists.', 0.65, 'external', 'Stage 0'),
('RC-PRP-002', 'PRP-001', 'Idea Copies an Existing Platform', 'Behavioural', 'The idea closely mirrors an existing real estate platform without adding anything new.', 0.62, 'external', 'Stage 0'),
('RC-PRP-003', 'PRP-001', 'No Research on Existing Competitors', 'Operational', 'No research has been done on other platforms already doing something similar.', 0.63, 'external', 'Stage 0'),
('RC-PRP-004', 'PRP-001', 'Assuming a Nicer Interface Is Enough', 'Knowledge', 'The founder assumes a nicer app or interface alone is sufficient to differentiate.', 0.60, 'external', 'Stage 0'),
('RC-PRP-005', 'PRP-001', 'No Outside Opinion Sought', 'Behavioural', 'Nobody outside the founder has been asked whether the idea genuinely stands out.', 0.58, 'external', 'Stage 0'),
('RC-PRP-006', 'PRP-002', 'No Specific Customer Type Chosen', 'Strategic', 'No specific type of customer, such as developer, buyer, renter, or contractor, has been chosen.', 0.65, 'external', 'Stage 0'),
('RC-PRP-007', 'PRP-002', 'Idea Described as For the Industry Broadly', 'Behavioural', 'The idea is described broadly as being for the real estate industry rather than one specific group.', 0.63, 'external', 'Stage 0'),
('RC-PRP-008', 'PRP-002', 'No Consideration of How Different Needs Are', 'Knowledge', 'No thought has been given to how different a developer''s needs are from a renter''s or contractor''s.', 0.62, 'external', 'Stage 0'),
('RC-PRP-009', 'PRP-002', 'Assuming One Product Serves the Whole Chain', 'Knowledge', 'It is assumed that a single product can serve everyone involved in the property chain.', 0.60, 'external', 'Stage 0'),
('RC-PRP-010', 'PRP-003', 'Comparing to Software Deal Speed', 'Knowledge', 'The founder is comparing this to how quickly a typical app or software deal closes.', 0.63, 'external', 'Stage 0'),
('RC-PRP-011', 'PRP-003', 'No Research on Real Timelines', 'Operational', 'No research has been done on actual average timelines for property or construction deals.', 0.62, 'external', 'Stage 0'),
('RC-PRP-012', 'PRP-003', 'Assuming Excitement Speeds Up the Process', 'Knowledge', 'It is assumed that urgency or excitement will speed up a naturally slow property process.', 0.58, 'external', 'Stage 0'),
('RC-PRP-013', 'PRP-003', 'No Plan for Surviving Long Deal Cycles', 'Strategic', 'There is no plan for how the business survives during naturally long deal cycles.', 0.62, 'external', 'Stage 0'),
('RC-PRP-014', 'PRP-004', 'Assuming the App User Is the Only Decision-Maker', 'Knowledge', 'It is assumed the person using the product is the sole decision-maker in the transaction.', 0.63, 'external', 'Stage 0'),
('RC-PRP-015', 'PRP-004', 'No Thought on Family or Co-Owner Role', 'Knowledge', 'No thought has been given to the role a spouse, family member, or co-owner might play.', 0.60, 'external', 'Stage 0'),
('RC-PRP-016', 'PRP-004', 'No Thought on Broker or Agent Role', 'Knowledge', 'No thought has been given to the role a broker or agent might play in the decision.', 0.60, 'external', 'Stage 0'),
('RC-PRP-017', 'PRP-004', 'No Thought on Bank or Lender Role', 'Knowledge', 'No thought has been given to the role a bank or lender might play in the transaction.', 0.60, 'external', 'Stage 0'),
('RC-PRP-018', 'PRP-004', 'Assuming a Purely Digital Decision Process', 'Knowledge', 'It is assumed the decision happens entirely online with no offline influence.', 0.58, 'external', 'Stage 0'),
('RC-PRP-019', 'PRP-005', 'No Listing Verification Process', 'Operational', 'There is no process in place to verify that listing information is accurate.', 0.65, 'external', 'Stage 0â†’1'),
('RC-PRP-020', 'PRP-005', 'Data From an Unreliable Source', 'Operational', 'Listing data is pulled from a source that has not been checked for reliability.', 0.63, 'external', 'Stage 0â†’1'),
('RC-PRP-021', 'PRP-005', 'No Process for Updating Stale Listings', 'Operational', 'There is no process for catching and refreshing listings that have become outdated.', 0.62, 'external', 'Stage 0â†’1'),
('RC-PRP-022', 'PRP-005', 'Assuming Listers Self-Maintain Accuracy', 'Knowledge', 'It is assumed that the people posting listings will keep their information accurate without any prompting.', 0.60, 'external', 'Stage 0â†’1'),
('RC-PRP-023', 'PRP-006', 'Local Registration Requirements Not Understood', 'Knowledge', 'The founder does not understand what local registration requirements actually apply.', 0.65, 'external', 'Stage 0â†’1'),
('RC-PRP-024', 'PRP-006', 'No Lawyer or Legal Consultant Involved', 'Operational', 'No lawyer or legal consultant has been engaged to review the process.', 0.65, 'external', 'Stage 0â†’1'),
('RC-PRP-025', 'PRP-006', 'Assuming Standard Templates Suffice', 'Knowledge', 'It is assumed a standard contract template is sufficient for this specific kind of transaction.', 0.60, 'external', 'Stage 0â†’1'),
('RC-PRP-026', 'PRP-006', 'No Title or Ownership Verification Process', 'Operational', 'There is no process for verifying title or ownership before a deal proceeds.', 0.63, 'external', 'Stage 0â†’1'),
('RC-PRP-027', 'PRP-006', 'Legal Compliance Time and Cost Underestimated', 'Knowledge', 'The real time and cost of legal compliance in this space has been underestimated.', 0.62, 'external', 'Stage 0â†’1'),
('RC-PRP-028', 'PRP-007', 'No Real Broker Relationship Built', 'Operational', 'No genuine working relationship has been built with brokers or agents.', 0.63, 'external', 'Stage 0â†’1'),
('RC-PRP-029', 'PRP-007', 'Assuming Brokers Can Be Bypassed', 'Knowledge', 'It is assumed the platform can bypass brokers entirely in this market.', 0.60, 'external', 'Stage 0â†’1'),
('RC-PRP-030', 'PRP-007', 'Broker Compensation Model Not Understood', 'Knowledge', 'It is not understood how brokers are actually compensated in this market.', 0.60, 'external', 'Stage 0â†’1'),
('RC-PRP-031', 'PRP-007', 'No Broker Adoption Plan', 'Strategic', 'There is no real plan for how a broker would actually use or adopt the platform.', 0.60, 'external', 'Stage 0â†’1'),
('RC-PRP-032', 'PRP-008', 'Leads Generated but No Deal Closed', 'Operational', 'Interest and leads exist, but no actual deal has been completed.', 0.65, 'external', 'Stage 0â†’1'),
('RC-PRP-033', 'PRP-008', 'No Lead-to-Completion Process', 'Operational', 'There is no defined process for guiding a lead all the way through to completion.', 0.62, 'external', 'Stage 0â†’1'),
('RC-PRP-034', 'PRP-008', 'Assuming Interest Converts Automatically', 'Knowledge', 'It is assumed that generated interest will automatically turn into a completed deal.', 0.60, 'external', 'Stage 0â†’1'),
('RC-PRP-035', 'PRP-008', 'No Manual Push for a Completed Deal', 'Operational', 'No deliberate, manual effort has been applied to push even one deal through to completion.', 0.60, 'external', 'Stage 0â†’1'),
('RC-PRP-036', 'PRP-009', 'No Verification Badges or Credibility Markers', 'Operational', 'No verification badges or credibility markers exist on the platform.', 0.62, 'external', 'Stage 0â†’1'),
('RC-PRP-037', 'PRP-009', 'No Reviews or Testimonials Collected', 'Operational', 'No reviews or testimonials from real users have been collected yet.', 0.62, 'external', 'Stage 0â†’1'),
('RC-PRP-038', 'PRP-009', 'No Transparency on Who Is Behind It', 'Operational', 'It is not clear to a visitor who is actually behind the platform or its listings.', 0.60, 'external', 'Stage 0â†’1'),
('RC-PRP-039', 'PRP-009', 'Assuming Trust Builds Automatically', 'Knowledge', 'It is assumed that trust will build on its own over time without deliberate effort.', 0.58, 'external', 'Stage 0â†’1'),
('RC-PRP-040', 'PRP-009', 'No Plan to Earn Trust Before Big Commitments', 'Strategic', 'There is no plan for earning trust before asking users for large financial commitments.', 0.60, 'external', 'Stage 0â†’1'),
('RC-PRP-041', 'PRP-010', 'No City-by-City Regulatory Checklist', 'Strategic', 'There is no checklist covering regulatory differences across cities or states.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-PRP-042', 'PRP-010', 'Assuming Registration Process Transfers', 'Knowledge', 'It is assumed the current city''s registration process will work the same way elsewhere.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-PRP-043', 'PRP-010', 'No Local Legal Partner in New Markets', 'Operational', 'No local legal partner has been engaged in newly entered markets.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-PRP-044', 'PRP-010', 'Stamp Duty Differences Not Researched', 'Knowledge', 'Differences in stamp duty and registration costs between markets have not been researched.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-PRP-045', 'PRP-011', 'No Standardized Quality Control Across Projects', 'Operational', 'There is no consistent quality control process applied across multiple projects.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-PRP-046', 'PRP-011', 'No Centralized Timeline Tracking', 'Operational', 'There is no single place tracking timelines across all active projects.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-PRP-047', 'PRP-011', 'Contractors Held to Different Standards', 'Operational', 'Different contractors are evaluated against inconsistent quality standards.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-PRP-048', 'PRP-011', 'No Early Warning System for Delays', 'Operational', 'There is no system that flags a project heading toward delay before it actually happens.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-PRP-049', 'PRP-011', 'No Process for Recurring Contractor Issues', 'Operational', 'There is no defined process for addressing a contractor issue that keeps recurring.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-PRP-050', 'PRP-012', 'No Compliant Escrow System', 'Strategic', 'There is no properly compliant system in place for holding escrow funds.', 0.68, 'external', 'Stage 1â†’10+'),
('RC-PRP-051', 'PRP-012', 'Large Sums Handled Without Legal Structure', 'Operational', 'Large sums of money are being handled without a proper legal structure behind them.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-PRP-052', 'PRP-012', 'No Third-Party Escrow Partner', 'Operational', 'No real third-party escrow partner has been engaged.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-PRP-053', 'PRP-012', 'No Audit Trail for Fund Movements', 'Operational', 'There is no clear audit trail showing where funds moved and when.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-PRP-054', 'PRP-013', 'No Fraud Detection Process', 'Operational', 'There is no process in place to detect fraudulent activity on the platform.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-PRP-055', 'PRP-013', 'No Pre-Listing Verification Step', 'Operational', 'There is no verification step before a new listing actually goes live.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-PRP-056', 'PRP-013', 'No Fast Removal Process for Fraud', 'Operational', 'There is no fast, defined process for removing a reported fraudulent listing.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-PRP-057', 'PRP-013', 'No Repeat Offender Monitoring', 'Operational', 'There is no tracking of actors who post fraudulent listings more than once.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-PRP-058', 'PRP-014', 'Listings Concentrated in Few Developers', 'Strategic', 'A majority of listings or projects depend on a small number of developers or owners.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-PRP-059', 'PRP-014', 'No Supply Diversification Plan', 'Strategic', 'There is no active plan to diversify beyond the current top supply sources.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-PRP-060', 'PRP-014', 'No Backup Supplier Relationship', 'Strategic', 'There is no backup relationship ready if a top supplier were to leave.', 0.62, 'external', 'Stage 1â†’10+'),
('RC-PRP-061', 'PRP-014', 'Supply Concentration Not Tracked', 'Operational', 'Supply concentration is not tracked over time, so it is only noticed once it becomes a problem.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-PRP-062', 'PRP-014', 'Growth Targets Not Checked Against Supply Diversity', 'Strategic', 'Growth targets are set without checking them against how concentrated current supply actually is.', 0.60, 'external', 'Stage 1â†’10+'),
('RC-PRP-063', 'PRP-015', 'No Document Retention System', 'Operational', 'There is no system retaining documentation from past transactions for future reference.', 0.65, 'external', 'Stage 1â†’10+'),
('RC-PRP-064', 'PRP-015', 'No Protocol for Late-Surfacing Disputes', 'Strategic', 'There is no defined legal protocol for handling a dispute that surfaces well after closing.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-PRP-065', 'PRP-015', 'No Long-Tail Liability Coverage', 'Operational', 'There is no insurance or liability coverage for claims that could arise years later.', 0.63, 'external', 'Stage 1â†’10+'),
('RC-PRP-066', 'PRP-015', 'Assuming Closed Deals Carry No Ongoing Risk', 'Knowledge', 'It is assumed that once a transaction closes, it carries no further risk to the business.', 0.60, 'external', 'Stage 1â†’10+')
  ) AS v(root_cause_code, problem_code, root_cause_name, root_cause_category, explanation, confidence_weight, layer, primary_stage_group)
  JOIN new_problems p ON p.problem_code = v.problem_code
  RETURNING root_cause_id, root_cause_code
),
new_questions AS (
  INSERT INTO questions (question_code, category, question_text, problem_id, root_cause_id, question_type, difficulty_level, priority, is_distress_tagged, industry_relevance, embedding, primary_stage_group, embedding_model, embedding_version, embedding_dimension)
  SELECT v.question_code, 'Idea & Validation', v.question_text, p.problem_id, rc.root_cause_id, 'open_text', v.difficulty_level, v.priority, false, '["proptech"]'::jsonb, array_fill(0, ARRAY[1536])::vector, v.stage_group, NULL, NULL, NULL
  FROM (VALUES
('S0-PRP-001', 'PRP-001', 'RC-PRP-001', 'If someone asked what makes your idea different from other real estate or construction platforms out there, what would you say?', 1, 'CORE', 'Stage 0'),
('S0-PRP-002', 'PRP-001', 'RC-PRP-002', 'Is your idea mostly inspired by copying an existing platform, or does it add something genuinely new?', 1, 'CORE', 'Stage 0'),
('S0-PRP-003', 'PRP-001', 'RC-PRP-003', 'Have you looked at what else already exists that''s similar to your idea?', 1, 'CORE', 'Stage 0'),
('S0-PRP-004', 'PRP-001', 'RC-PRP-004', 'If your only answer is "a better app," do you think that''s enough to make someone switch?', 2, 'SUPPLEMENTARY', 'Stage 0'),
('S0-PRP-005', 'PRP-002', 'RC-PRP-006', 'Can you describe exactly who this is for -- buyers, renters, developers, contractors -- or is it "for the real estate industry" right now?', 1, 'CORE', 'Stage 0'),
('S0-PRP-006', 'PRP-002', 'RC-PRP-008', 'Have you thought about how different a developer''s needs are from a renter''s needs?', 2, 'CORE', 'Stage 0'),
('S0-PRP-007', 'PRP-002', 'RC-PRP-009', 'Are you assuming one product can serve everyone involved in a property transaction?', 1, 'CORE', 'Stage 0'),
('S0-PRP-008', 'PRP-002', 'RC-PRP-007', 'If you had to pick just one type of customer to start with, who would it be?', 1, 'SUPPLEMENTARY', 'Stage 0'),
('S0-PRP-009', 'PRP-003', 'RC-PRP-011', 'Do you know how long a typical property deal or construction project actually takes, from start to finish?', 1, 'CORE', 'Stage 0'),
('S0-PRP-010', 'PRP-003', 'RC-PRP-010', 'Are you assuming this will move at the speed of a typical app, rather than a property deal?', 2, 'CORE', 'Stage 0'),
('S0-PRP-011', 'PRP-003', 'RC-PRP-013', 'Have you thought about how your business survives during the naturally long time these deals take?', 2, 'CORE', 'Stage 0'),
('S0-PRP-012', 'PRP-003', 'RC-PRP-012', 'Have you actually asked someone who recently bought, sold, or built property how long it took them?', 1, 'CORE', 'Stage 0'),
('S0-PRP-013', 'PRP-004', 'RC-PRP-014', 'When someone buys or rents property, is it usually just their decision, or are other people involved?', 1, 'CORE', 'Stage 0'),
('S0-PRP-014', 'PRP-004', 'RC-PRP-016', 'Have you thought about the role a broker or agent might play in your idea?', 1, 'CORE', 'Stage 0'),
('S0-PRP-015', 'PRP-004', 'RC-PRP-017', 'Does a bank or lender typically need to be involved in the kind of transaction your idea touches?', 2, 'CORE', 'Stage 0'),
('S01-PRP-001', 'PRP-005', 'RC-PRP-019', 'Have you actually verified that the property information on your platform matches reality?', 2, 'CORE', 'Stage 0â†’1'),
('S01-PRP-002', 'PRP-005', 'RC-PRP-020', 'Where does your listing data actually come from, and how reliable is that source?', 2, 'CORE', 'Stage 0â†’1'),
('S01-PRP-003', 'PRP-005', 'RC-PRP-021', 'Do you have any process for catching and updating listings that have gone stale?', 2, 'CORE', 'Stage 0â†’1'),
('S01-PRP-004', 'PRP-005', 'RC-PRP-022', 'Are you assuming the people listing properties will keep their own information accurate?', 2, 'SUPPLEMENTARY', 'Stage 0â†’1'),
('S01-PRP-005', 'PRP-006', 'RC-PRP-023', 'Do you understand what legal paperwork is actually involved in the kind of transaction you''re facilitating?', 2, 'CORE', 'Stage 0â†’1'),
('S01-PRP-006', 'PRP-006', 'RC-PRP-024', 'Has a lawyer or legal consultant actually reviewed your process yet?', 2, 'CORE', 'Stage 0â†’1'),
('S01-PRP-007', 'PRP-006', 'RC-PRP-025', 'Are you assuming a standard contract template is enough for this kind of transaction?', 2, 'CORE', 'Stage 0â†’1'),
('S01-PRP-008', 'PRP-006', 'RC-PRP-026', 'Do you have any process for verifying title or ownership before a deal proceeds?', 3, 'CORE', 'Stage 0â†’1'),
('S01-PRP-009', 'PRP-006', 'RC-PRP-027', 'Have you underestimated how much time and cost real legal compliance actually takes here?', 2, 'CORE', 'Stage 0â†’1'),
('S01-PRP-010', 'PRP-007', 'RC-PRP-028', 'Have you built any real relationship with brokers or agents, or are you trying to work entirely around them?', 2, 'CORE', 'Stage 0â†’1'),
('S01-PRP-011', 'PRP-007', 'RC-PRP-029', 'Are you assuming your platform can bypass brokers entirely in this market?', 2, 'CORE', 'Stage 0â†’1'),
('S01-PRP-012', 'PRP-007', 'RC-PRP-030', 'Do you actually understand how brokers get paid in this market?', 2, 'CORE', 'Stage 0â†’1'),
('S01-PRP-013', 'PRP-007', 'RC-PRP-031', 'Do you have a real plan for how a broker would actually use your platform?', 2, 'CORE', 'Stage 0â†’1'),
('S01-PRP-014', 'PRP-008', 'RC-PRP-032', 'Has an actual deal gone all the way through your platform, from interest to completion?', 2, 'CORE', 'Stage 0â†’1'),
('S01-PRP-015', 'PRP-008', 'RC-PRP-033', 'Do you have a real process for guiding a lead all the way to a completed deal?', 2, 'CORE', 'Stage 0â†’1'),
('S01-PRP-016', 'PRP-008', 'RC-PRP-034', 'Are you assuming interest or inquiries will automatically turn into completed deals?', 3, 'CORE', 'Stage 0â†’1'),
('S01-PRP-017', 'PRP-008', 'RC-PRP-035', 'Have you personally pushed even one deal through manually, start to finish?', 2, 'SUPPLEMENTARY', 'Stage 0â†’1'),
('S01-PRP-018', 'PRP-009', 'RC-PRP-036', 'Would a stranger trust your platform enough to put real money into a transaction through it?', 3, 'CORE', 'Stage 0â†’1'),
('S01-PRP-019', 'PRP-009', 'RC-PRP-037', 'Do you have any reviews or testimonials from real users yet?', 2, 'CORE', 'Stage 0â†’1'),
('S01-PRP-020', 'PRP-009', 'RC-PRP-038', 'Is it clear to a visitor who is actually behind your platform or listings?', 2, 'CORE', 'Stage 0â†’1'),
('S10-PRP-001', 'PRP-010', 'RC-PRP-041', 'Have you actually researched what changes legally when you expand to a new city or state?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-002', 'PRP-010', 'RC-PRP-042', 'Are you assuming your current city''s registration process will work the same way elsewhere?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-003', 'PRP-010', 'RC-PRP-043', 'Do you have a local legal partner in each new market you''ve entered?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-004', 'PRP-010', 'RC-PRP-044', 'Have you checked how stamp duty and registration costs differ in your new market?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-005', 'PRP-011', 'RC-PRP-045', 'As you''ve added more projects or listings, has quality gotten harder to keep consistent?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-006', 'PRP-011', 'RC-PRP-046', 'Do you have one central place to track timelines across all your active projects?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-007', 'PRP-011', 'RC-PRP-047', 'Are all your contractors held to the same quality standard, or does it vary?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-008', 'PRP-011', 'RC-PRP-048', 'Would you know a project was heading toward delay early, or only once it was already late?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-009', 'PRP-011', 'RC-PRP-049', 'When a contractor issue keeps recurring, is there a process for addressing it?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-010', 'PRP-012', 'RC-PRP-050', 'Do you have a real, compliant system for holding large deposits or escrow funds safely?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-011', 'PRP-012', 'RC-PRP-051', 'Are you handling large sums of money without a proper legal structure behind it?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-012', 'PRP-012', 'RC-PRP-052', 'Have you engaged a real third-party escrow partner, or is this handled informally?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-013', 'PRP-012', 'RC-PRP-053', 'If asked, could you produce a clear audit trail for where funds moved and when?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-014', 'PRP-013', 'RC-PRP-054', 'Do you have any way to detect a fake or fraudulent listing before it goes live?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-015', 'PRP-013', 'RC-PRP-055', 'Is there a verification step before a new listing actually goes live?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-016', 'PRP-013', 'RC-PRP-056', 'If a fraudulent listing were reported, do you have a real process for removing it quickly?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-017', 'PRP-013', 'RC-PRP-057', 'Do you track repeat offenders who post fraudulent listings more than once?', 2, 'SUPPLEMENTARY', 'Stage 1â†’10+'),
('S10-PRP-018', 'PRP-014', 'RC-PRP-058', 'What percentage of your business depends on just your top few developers or property owners?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-019', 'PRP-014', 'RC-PRP-059', 'Do you have any active plan to diversify beyond your current top suppliers?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-020', 'PRP-014', 'RC-PRP-060', 'If your biggest supplier left tomorrow, do you have a backup relationship ready?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-021', 'PRP-014', 'RC-PRP-061', 'Do you track your supply concentration over time, or only notice it when it becomes a problem?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-022', 'PRP-014', 'RC-PRP-062', 'Are your growth targets realistic given how concentrated your current supply actually is?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-023', 'PRP-015', 'RC-PRP-063', 'If a dispute surfaced two years after a transaction closed, would you have any records to defend yourself?', 3, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-024', 'PRP-015', 'RC-PRP-064', 'Do you have a real legal protocol for handling a dispute that surfaces well after closing?', 2, 'CORE', 'Stage 1â†’10+'),
('S10-PRP-025', 'PRP-015', 'RC-PRP-065', 'Do you carry any insurance or coverage for liability claims that could arise years later?', 2, 'CORE', 'Stage 1â†’10+')
  ) AS v(question_code, problem_code, root_cause_code, question_text, difficulty_level, priority, stage_group)
  JOIN new_problems p ON p.problem_code = v.problem_code
  JOIN new_root_causes rc ON rc.root_cause_code = v.root_cause_code
  RETURNING question_id, question_code
),
new_tags AS (
  INSERT INTO question_tag_mapping (question_id, tag_id)
  SELECT q.question_id, v.tag_id
  FROM (VALUES
('S0-PRP-001', 4), ('S0-PRP-002', 4), ('S0-PRP-003', 4), ('S0-PRP-004', 4),
('S0-PRP-005', 3), ('S0-PRP-006', 3), ('S0-PRP-007', 3), ('S0-PRP-008', 3),
('S0-PRP-009', 4), ('S0-PRP-010', 4), ('S0-PRP-011', 4), ('S0-PRP-012', 4),
('S0-PRP-013', 2), ('S0-PRP-014', 2), ('S0-PRP-015', 2),
('S01-PRP-001', 33), ('S01-PRP-002', 33), ('S01-PRP-003', 33), ('S01-PRP-004', 33),
('S01-PRP-005', 4), ('S01-PRP-006', 4), ('S01-PRP-007', 4), ('S01-PRP-008', 4), ('S01-PRP-009', 4),
('S01-PRP-010', 12), ('S01-PRP-011', 12), ('S01-PRP-012', 12), ('S01-PRP-013', 12),
('S01-PRP-014', 2), ('S01-PRP-015', 2), ('S01-PRP-016', 2), ('S01-PRP-017', 2),
('S01-PRP-018', 8), ('S01-PRP-019', 8), ('S01-PRP-020', 8),
('S10-PRP-001', 4), ('S10-PRP-002', 4), ('S10-PRP-003', 4), ('S10-PRP-004', 4),
('S10-PRP-005', 33), ('S10-PRP-006', 33), ('S10-PRP-007', 33), ('S10-PRP-008', 33), ('S10-PRP-009', 33),
('S10-PRP-010', 84), ('S10-PRP-011', 84), ('S10-PRP-012', 84), ('S10-PRP-013', 84),
('S10-PRP-014', 36), ('S10-PRP-015', 36), ('S10-PRP-016', 36), ('S10-PRP-017', 36),
('S10-PRP-018', 12), ('S10-PRP-019', 12), ('S10-PRP-020', 12), ('S10-PRP-021', 12), ('S10-PRP-022', 12),
('S10-PRP-023', 4), ('S10-PRP-024', 4), ('S10-PRP-025', 4)
  ) AS v(question_code, tag_id)
  JOIN new_questions q ON q.question_code = v.question_code
  RETURNING mapping_id
),
new_interventions AS (
  INSERT INTO interventions (intervention_code, problem_id, root_cause_ids, secondary_root_cause_ids, capability_domain, section, recommended_frameworks, framework_codes, immediate_next_steps, stage_relevance, industry_relevance, design_principles)
  SELECT v.intervention_code, p.problem_id, v.root_cause_ids, '[]'::jsonb, v.capability_domain, v.section, v.recommended_frameworks, NULL, v.immediate_next_steps, v.stage_relevance, '["proptech"]'::jsonb, v.design_principles
  FROM (VALUES
('INT-PRP-001', 'PRP-001', '["RC-PRP-001", "RC-PRP-004"]'::jsonb, 'Market Validation', 'Ideation â€” PropTech Market Fundamentals', '[{"name": "Differentiation Statement", "brief": "Writing a single, clear sentence describing what makes the product different."}]'::jsonb, '["Write one sentence describing what makes your product different.", "If you cannot write it clearly, treat that as your real starting point.", "Test this sentence on someone unfamiliar with your idea."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-002', 'PRP-001', '["RC-PRP-003"]'::jsonb, 'Market Validation', 'Ideation â€” PropTech Market Fundamentals', '[{"name": "Competitor Comparison List", "brief": "Listing existing platforms doing something similar and comparing honestly."}]'::jsonb, '["List 3 existing platforms doing something similar.", "Compare your idea against each one honestly.", "Identify what, if anything, is genuinely different."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-003', 'PRP-001', '["RC-PRP-005"]'::jsonb, 'Market Validation', 'Ideation â€” PropTech Market Fundamentals', '[{"name": "Outside Perspective Check", "brief": "Asking people outside the founder''s own circle whether the idea stands out."}]'::jsonb, '["Describe your idea to 5 people outside your close circle.", "Ask them directly what stands out, if anything.", "Note honestly if nobody mentions something unique."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-004', 'PRP-002', '["RC-PRP-006", "RC-PRP-007"]'::jsonb, 'Customer Definition', 'Ideation â€” PropTech Market Fundamentals', '[{"name": "First Customer Selection", "brief": "Picking one specific type of customer to build for first, instead of the whole industry."}]'::jsonb, '["Pick one specific type of customer to build for first.", "Write down why you chose that group specifically.", "Set aside every other customer type for now."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-005', 'PRP-002', '["RC-PRP-008", "RC-PRP-009"]'::jsonb, 'Customer Definition', 'Ideation â€” PropTech Market Fundamentals', '[{"name": "Customer Need Comparison", "brief": "Comparing how different needs actually are across different roles in the property chain."}]'::jsonb, '["List the needs of two different customer types in this space.", "Compare them side by side honestly.", "Note where one product genuinely cannot serve both well."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-006', 'PRP-003', '["RC-PRP-011", "RC-PRP-012"]'::jsonb, 'Market Validation', 'Ideation â€” PropTech Market Fundamentals', '[{"name": "Real Timeline Research", "brief": "Talking to someone who has actually completed a property or construction transaction about how long it took."}]'::jsonb, '["Talk to someone who recently bought, sold, or built property.", "Ask them specifically how long the process took.", "Compare that against your current assumption."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-007', 'PRP-003', '["RC-PRP-010"]'::jsonb, 'Market Validation', 'Ideation â€” PropTech Market Fundamentals', '[{"name": "Sector Timeline Research", "brief": "Researching actual average timelines for your specific type of transaction."}]'::jsonb, '["Research typical timelines for your specific transaction type.", "Write down that real number.", "Compare it against what your current plan assumes."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-008', 'PRP-003', '["RC-PRP-013"]'::jsonb, 'Financial Planning', 'Ideation â€” PropTech Market Fundamentals', '[{"name": "Long Cycle Survival Plan", "brief": "Writing down what the business does to survive during a typical deal-length gap with no revenue."}]'::jsonb, '["Write down the real length of a typical deal cycle.", "Write down what your business does during that gap with no revenue.", "Decide if that gap feels survivable as currently planned."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-009', 'PRP-004', '["RC-PRP-014", "RC-PRP-015"]'::jsonb, 'Customer Definition', 'Ideation â€” PropTech Market Fundamentals', '[{"name": "Decision-Maker Mapping", "brief": "Listing every person who might be involved in the decision the customer makes."}]'::jsonb, '["List every person who might be involved in this decision.", "Include family, co-owners, and anyone else relevant.", "Note who among them actually has final say."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-010', 'PRP-004', '["RC-PRP-016", "RC-PRP-017", "RC-PRP-018"]'::jsonb, 'Customer Definition', 'Ideation â€” PropTech Market Fundamentals', '[{"name": "Offline Influence Mapping", "brief": "Mapping where a broker, bank, or other offline party would enter the process."}]'::jsonb, '["Map out where a broker or agent would enter your process.", "Map out where a bank or lender would enter your process.", "Note anywhere your idea assumes a purely digital decision that is not realistic."]'::jsonb, '[1]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-011', 'PRP-005', '["RC-PRP-019", "RC-PRP-020"]'::jsonb, 'Data Quality', 'Validation â€” PropTech Real-World Readiness', '[{"name": "Listing Verification Process", "brief": "Building a real process to verify listing accuracy before scaling."}]'::jsonb, '["Pick a sample of current listings and verify them against reality.", "Identify how many were inaccurate.", "Build a verification step into how new listings get added."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-012', 'PRP-005', '["RC-PRP-021", "RC-PRP-022"]'::jsonb, 'Data Quality', 'Validation â€” PropTech Real-World Readiness', '[{"name": "Stale Listing Refresh Process", "brief": "Setting up a regular process to catch and refresh outdated listings."}]'::jsonb, '["Set a regular schedule for checking listing freshness.", "Flag and refresh anything found to be stale.", "Do not assume listers will self-maintain accuracy without prompting."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-013', 'PRP-006', '["RC-PRP-023", "RC-PRP-024"]'::jsonb, 'Legal Compliance', 'Validation â€” PropTech Real-World Readiness', '[{"name": "Legal Process Review", "brief": "Getting a lawyer or legal consultant to review the actual transaction process."}]'::jsonb, '["Find a lawyer with real estate experience.", "Have them review your actual process end to end.", "Fix any gap they identify before proceeding further."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-014', 'PRP-006', '["RC-PRP-025", "RC-PRP-027"]'::jsonb, 'Legal Compliance', 'Validation â€” PropTech Real-World Readiness', '[{"name": "Full Legal Step Mapping", "brief": "Mapping every legal and paperwork step involved in a real transaction, including real time and cost."}]'::jsonb, '["List every legal step a real transaction requires.", "Get a real time and cost estimate for each step.", "Compare this against your current assumptions."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-015', 'PRP-007', '["RC-PRP-028", "RC-PRP-029"]'::jsonb, 'Partnership Strategy', 'Validation â€” PropTech Real-World Readiness', '[{"name": "Broker Relationship Building", "brief": "Having real conversations with brokers about working together, rather than assuming they can be bypassed."}]'::jsonb, '["Have direct conversations with 3-5 real brokers.", "Ask them how they currently work and what they need.", "Reconsider any assumption that they can simply be bypassed."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-016', 'PRP-007', '["RC-PRP-030", "RC-PRP-031"]'::jsonb, 'Partnership Strategy', 'Validation â€” PropTech Real-World Readiness', '[{"name": "Broker Compensation and Adoption Design", "brief": "Understanding real broker compensation and designing a genuine path for broker adoption."}]'::jsonb, '["Research exactly how brokers are compensated in this market.", "Design your platform to work with that model, not against it.", "Build a concrete plan for how a broker would actually adopt this."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-017', 'PRP-008', '["RC-PRP-032", "RC-PRP-035"]'::jsonb, 'Sales Execution', 'Validation â€” PropTech Real-World Readiness', '[{"name": "Manual Deal Completion Push", "brief": "Manually pushing one real deal all the way to completion, even if it requires significant personal effort."}]'::jsonb, '["Pick your strongest current lead.", "Personally push that deal through to completion, manually if needed.", "Document every obstacle encountered along the way."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-018', 'PRP-008', '["RC-PRP-033", "RC-PRP-034"]'::jsonb, 'Sales Execution', 'Validation â€” PropTech Real-World Readiness', '[{"name": "Lead-to-Completion Process Design", "brief": "Building a defined process for guiding a lead through every stage to a completed deal."}]'::jsonb, '["Map every stage between initial interest and a completed deal.", "Define what needs to happen at each stage.", "Stop assuming interest converts automatically without this process."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-019', 'PRP-009', '["RC-PRP-036", "RC-PRP-039"]'::jsonb, 'Trust Building', 'Validation â€” PropTech Real-World Readiness', '[{"name": "Basic Trust Signal Implementation", "brief": "Adding basic verification and credibility markers before asking for bigger financial commitments."}]'::jsonb, '["Add basic verification badges to listings or profiles.", "Do not assume trust will build without deliberate signals.", "Test whether these signals actually change user behavior."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-020', 'PRP-009', '["RC-PRP-038", "RC-PRP-040"]'::jsonb, 'Trust Building', 'Validation â€” PropTech Real-World Readiness', '[{"name": "Platform Transparency", "brief": "Being clearly transparent about who is behind the platform and its listings before asking for trust."}]'::jsonb, '["Add clear information about who is behind the platform.", "Make this visible before asking for any financial commitment.", "Build a deliberate plan for earning trust in stages."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-021', 'PRP-006', '["RC-PRP-026"]'::jsonb, 'Legal Compliance', 'Validation â€” PropTech Real-World Readiness', '[{"name": "Title and Ownership Verification", "brief": "Building a real process for verifying title or ownership before a listing or deal proceeds."}]'::jsonb, '["Define what ownership verification looks like for your transaction type.", "Build a verification step before a listing goes live.", "Do not skip this step for the sake of speed."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-022', 'PRP-009', '["RC-PRP-037"]'::jsonb, 'Trust Building', 'Validation â€” PropTech Real-World Readiness', '[{"name": "Early Testimonial Collection", "brief": "Actively collecting real testimonials from the platform''s first completed transactions."}]'::jsonb, '["Identify your first completed transactions, however few.", "Ask those users directly for a testimonial.", "Display these prominently to build early credibility."]'::jsonb, '[2, 3, 4]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-023', 'PRP-010', '["RC-PRP-041", "RC-PRP-042"]'::jsonb, 'Regulatory Compliance', 'Growth â€” Multi-City Regulatory Readiness', '[{"name": "City-by-City Regulatory Checklist", "brief": "Building a reusable checklist covering regulatory differences before entering any new city or state."}]'::jsonb, '["Research regulatory requirements for your next target city.", "Build a reusable checklist template from that research.", "Confirm what differs from your current market before assuming it transfers."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-024', 'PRP-010', '["RC-PRP-043", "RC-PRP-044"]'::jsonb, 'Regulatory Compliance', 'Growth â€” Multi-City Regulatory Readiness', '[{"name": "Local Legal Partner Engagement", "brief": "Engaging a local legal partner and understanding stamp duty differences before entering a new market."}]'::jsonb, '["Identify and engage a local legal partner in your new market.", "Confirm stamp duty and registration cost differences.", "Build these costs into your market-entry plan."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-025', 'PRP-011', '["RC-PRP-045", "RC-PRP-047"]'::jsonb, 'Quality Management', 'Growth â€” Construction Quality at Scale', '[{"name": "Standardized Quality Control", "brief": "Applying one consistent quality standard across all active projects and contractors."}]'::jsonb, '["Define one clear quality standard for all projects.", "Apply that standard consistently across every contractor.", "Audit a sample of current projects against that standard."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-026', 'PRP-011', '["RC-PRP-046", "RC-PRP-048", "RC-PRP-049"]'::jsonb, 'Quality Management', 'Growth â€” Construction Quality at Scale', '[{"name": "Centralized Timeline and Issue Tracking", "brief": "Building a central system to track timelines and flag delays and recurring contractor issues early."}]'::jsonb, '["Set up one central place to track all project timelines.", "Define early warning signs for delay risk.", "Build a process for addressing recurring contractor issues."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-027', 'PRP-012', '["RC-PRP-050", "RC-PRP-051"]'::jsonb, 'Financial Compliance', 'Growth â€” Escrow & Payment Trust', '[{"name": "Compliant Escrow System Setup", "brief": "Setting up a properly compliant escrow system with real legal structure behind it."}]'::jsonb, '["Consult a legal expert on compliant escrow requirements.", "Set up a proper legal structure for holding large sums.", "Do not continue handling large sums informally."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-028', 'PRP-012', '["RC-PRP-052", "RC-PRP-053"]'::jsonb, 'Financial Compliance', 'Growth â€” Escrow & Payment Trust', '[{"name": "Third-Party Escrow Partnership and Audit Trail", "brief": "Engaging a real third-party escrow partner and building a clear audit trail for fund movements."}]'::jsonb, '["Identify and engage a real third-party escrow partner.", "Build a system that logs every fund movement clearly.", "Test that you could produce this audit trail on request."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-029', 'PRP-013', '["RC-PRP-054", "RC-PRP-055"]'::jsonb, 'Risk Management', 'Growth â€” Fraud & Fake Listing Prevention', '[{"name": "Fraud Detection and Pre-Listing Verification", "brief": "Building a basic fraud detection process with a verification step before listings go live."}]'::jsonb, '["Identify common patterns in fraudulent listings.", "Build a verification step before any listing goes live.", "Test this process against a known fraudulent example."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-030', 'PRP-013', '["RC-PRP-056", "RC-PRP-057"]'::jsonb, 'Risk Management', 'Growth â€” Fraud & Fake Listing Prevention', '[{"name": "Fast Fraud Response and Repeat Offender Tracking", "brief": "Building a fast removal process for reported fraud and tracking repeat offenders."}]'::jsonb, '["Build a fast, defined process for removing reported fraud.", "Set a target response time for removal.", "Track repeat offenders and block them proactively."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-031', 'PRP-014', '["RC-PRP-058", "RC-PRP-059"]'::jsonb, 'Supply Strategy', 'Growth â€” Supply Concentration Risk', '[{"name": "Active Supply Diversification", "brief": "Actively diversifying supply sources beyond dependence on a small number of top developers."}]'::jsonb, '["Calculate your current concentration among top suppliers.", "Identify 2-3 new supply sources to pursue.", "Set a target to reduce concentration over time."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-032', 'PRP-014', '["RC-PRP-060", "RC-PRP-061", "RC-PRP-062"]'::jsonb, 'Supply Strategy', 'Growth â€” Supply Concentration Risk', '[{"name": "Backup Supplier and Concentration Tracking", "brief": "Building a backup supplier relationship and ongoing tracking of supply concentration against growth targets."}]'::jsonb, '["Identify a backup relationship for your top supplier.", "Set up ongoing tracking of supply concentration.", "Check your growth targets against current supply diversity."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-033', 'PRP-015', '["RC-PRP-063", "RC-PRP-066"]'::jsonb, 'Legal Risk Management', 'Growth â€” Long-Term Liability Protection', '[{"name": "Document Retention System", "brief": "Building a system to retain transaction documentation for long-term dispute protection."}]'::jsonb, '["Set up a system to retain documents from every closed transaction.", "Define a retention period based on legal advice.", "Stop assuming closed deals carry zero ongoing risk."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb),
('INT-PRP-034', 'PRP-015', '["RC-PRP-064", "RC-PRP-065"]'::jsonb, 'Legal Risk Management', 'Growth â€” Long-Term Liability Protection', '[{"name": "Late-Dispute Protocol and Liability Coverage", "brief": "Defining a legal protocol for late-surfacing disputes and obtaining liability coverage for long-tail claims."}]'::jsonb, '["Consult a lawyer on handling disputes that surface after closing.", "Write a defined protocol for that scenario.", "Get liability insurance coverage for long-tail claims."]'::jsonb, '[5, 6, 7]'::jsonb, '["minimum_effective_dose", "evidence_based", "stage_contextualised"]'::jsonb)
  ) AS v(intervention_code, problem_code, root_cause_ids, capability_domain, section, recommended_frameworks, immediate_next_steps, stage_relevance, design_principles)
  JOIN new_problems p ON p.problem_code = v.problem_code
  RETURNING intervention_id, intervention_code
)
SELECT
  (SELECT COUNT(*) FROM new_problems) as problems_inserted,
  (SELECT COUNT(*) FROM new_root_causes) as root_causes_inserted,
  (SELECT COUNT(*) FROM new_questions) as questions_inserted,
  (SELECT COUNT(*) FROM new_tags) as tags_inserted,
  (SELECT COUNT(*) FROM new_interventions) as interventions_inserted;"""),

        ('Consumer Electronics', 'consumer_electronics', 'CEL', r"""WITH z AS (
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
  ('CEL-001', 'Idea Not Different From What Is Already Available', 'Big brands already sell something similar and often cheaper, and the founder has not identified what is genuinely different about their product.', 'Idea & Validation', 'Consumer Electronics Market Validation', 'external', 2, 3, 7, '["No clear point of difference from existing products", "Assuming a small feature change is enough to win customers", "No research done on what is already sold in this category", "No reason given for why someone would switch from a known brand", "Planning to compete on price without knowing own cost"]'::jsonb, '["consumer_electronics"]'::jsonb),
  ('CEL-002', 'No Idea What It Actually Costs to Make', 'The founder has a product idea but no sense of what it would cost to build even one real working unit.', 'Idea & Validation', 'Consumer Electronics Cost Reality', 'external', 2, 4, 8, '["No cost estimate exists for a single unit", "No idea what the key components cost", "Selling price picked before knowing the making cost", "Tooling and packaging costs not considered at all", "Assuming costs will drop later without checking"]'::jsonb, '["consumer_electronics"]'::jsonb),
  ('CEL-003', 'Treating Hardware Like an App', 'The founder assumes the product can be changed and improved quickly, without accounting for tooling, parts and long lead times that physical products need.', 'Idea & Validation', 'Consumer Electronics Build Reality', 'external', 2, 4, 8, '["Expecting to update the product quickly after launch", "No awareness of tooling or mould costs", "Assuming parts can be sourced instantly", "Timeline based on software-style iteration speed", "No plan for what happens if a design change is needed after production"]'::jsonb, '["consumer_electronics"]'::jsonb),
  ('CEL-004', 'Unclear Who Would Actually Buy This', 'The product is aimed at anyone who might want it, rather than one clear type of customer with a clear reason to buy.', 'Idea & Validation', 'Consumer Electronics Customer Clarity', 'external', 2, 3, 7, '["Target customer described as everyone", "No specific use case identified", "No clear reason why this customer would buy now", "Different customer types mixed into one idea", "No one outside friends and family has been asked"]'::jsonb, '["consumer_electronics"]'::jsonb),
  ('CEL-005', 'Prototype Cannot Actually Be Manufactured', 'The working sample relies on 3D printing, hand soldering or off-the-shelf boards that cannot be reproduced at real production volume.', 'Product Development', 'Consumer Electronics Manufacturability', 'external', 3, 5, 9, '["Prototype built by hand and never reviewed by a manufacturer", "Parts used in the prototype are not available in bulk", "No design for manufacturing review has been done", "Assuming the prototype only needs to be scaled up", "No production version of the design exists yet"]'::jsonb, '["consumer_electronics"]'::jsonb),
  ('CEL-006', 'Certification and Compliance Not Started', 'The founder knows electronics need BIS registration and safety or EMC testing, but nothing has actually been filed or tested.', 'Operations & Systems', 'Consumer Electronics Compliance', 'external', 3, 6, 9, '["No BIS application submitted", "No EMC or safety testing booked", "Certification timeline not built into the launch plan", "No budget set aside for testing and certification", "Assuming certification is a formality"]'::jsonb, '["consumer_electronics"]'::jsonb),
  ('CEL-007', 'Component Sourcing Not Locked', 'Key components have no confirmed supplier, no checked minimum order quantity and no understanding of lead times.', 'Operations & Systems', 'Consumer Electronics Supply Chain', 'external', 3, 5, 9, '["No supplier confirmed for key components", "Minimum order quantities never checked", "Lead times unknown for critical parts", "Only online listed prices used, no real quotes", "No backup supplier identified for any part"]'::jsonb, '["consumer_electronics"]'::jsonb),
  ('CEL-008', 'Unit Cost at Real Volume Not Verified', 'The cost estimate is based on buying a handful of pieces, and no real factory quote has been taken at production volume.', 'Financial Management', 'Consumer Electronics Unit Economics', 'external', 4, 5, 9, '["Cost based on small quantity purchases", "No factory quote at target order volume", "Assembly and labour costs not included", "Margin calculated on an unverified cost", "No idea how cost changes between 100 and 1000 units"]'::jsonb, '["consumer_electronics"]'::jsonb),
  ('CEL-009', 'No After Sales or Warranty Plan', 'The product is close to being sold but nothing exists for repairs, replacements or handling units that fail in a customer home.', 'Operations & Systems', 'Consumer Electronics Service Readiness', 'external', 3, 5, 9, '["No warranty terms defined", "No repair or replacement process exists", "No spare parts held for failures", "Expected failure rate unknown", "No cost set aside for returns and replacements"]'::jsonb, '["consumer_electronics"]'::jsonb),
  ('CEL-010', 'Quality and Defect Rate Rising at Scale', 'Defect rates climb as production volume rises, with no systematic quality control or defect tracking to catch problems early.', 'Operations & Systems', 'Consumer Electronics Quality Control', 'external', 3, 6, 9, '["Defect rate not measured", "No incoming inspection of parts", "Repeat faults never traced to a root cause", "Quality varies between production batches", "Customer complaints are the first sign of a defect"]'::jsonb, '["consumer_electronics"]'::jsonb),
  ('CEL-011', 'Service Network and Spare Parts Gaps', 'Units are in customer hands across many locations, but no real repair network or spare parts supply exists behind them.', 'Operations & Systems', 'Consumer Electronics After Sales', 'external', 3, 6, 9, '["No service coverage outside the home city", "No spare parts held in stock", "Every repair handled as a full replacement", "No turnaround time promised or measured", "Service handled personally by the founder or core team"]'::jsonb, '["consumer_electronics"]'::jsonb),
  ('CEL-012', 'Inventory and Obsolescence Risk', 'Cash is locked in stock that ages quickly, and a newer model or an end of life component can make that stock unsellable.', 'Financial Management', 'Consumer Electronics Inventory Risk', 'external', 4, 6, 9, '["Large cash amount sitting in unsold stock", "Stock age never reviewed", "No plan for end of life components", "Old model stock still held after a new launch", "Ordering based on optimism rather than sell through"]'::jsonb, '["consumer_electronics"]'::jsonb),
  ('CEL-013', 'Retail and Marketplace Margin Pressure', 'Selling through retail chains and marketplaces gives away margin, returns and listing costs that were never modelled.', 'Financial Management', 'Consumer Electronics Channel Economics', 'external', 4, 5, 9, '["Retail terms agreed without margin modelling", "Marketplace fees and returns not counted in unit economics", "Discounting to win shelf space", "Different prices across channels causing conflict", "Profit per unit unknown by channel"]'::jsonb, '["consumer_electronics"]'::jsonb),
  ('CEL-014', 'Single Factory or Region Dependency', 'One manufacturer or one sourcing region carries the entire production line, with no working alternative if it stops.', 'Operations & Systems', 'Consumer Electronics Supply Risk', 'external', 3, 6, 10, '["All production with one factory", "No second factory qualified", "All key parts sourced from one region", "No stock buffer for a supply interruption", "No written contract or capacity commitment"]'::jsonb, '["consumer_electronics"]'::jsonb),
  ('CEL-015', 'No Product Lifecycle or Next Model Plan', 'There is no clear plan for when the current model is replaced, so the range ages while competitors refresh theirs.', 'Strategy & Planning', 'Consumer Electronics Lifecycle Planning', 'external', 2, 5, 9, '["No end of life date for the current model", "No next model in development", "Competitor refresh cycles not tracked", "Engineering effort all on firefighting, none on the next product", "Price cuts used to keep an ageing model selling"]'::jsonb, '["consumer_electronics"]'::jsonb)
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
         t.primary_stage_group, '["consumer_electronics"]'::jsonb, z.v
  FROM (VALUES
  ('RC-CEL-001', 'No Clear Point of Difference', 'The founder cannot say what makes this product different from what is already on the shelf.', 'CEL-001', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-CEL-002', 'Never Checked What Already Exists', 'No time has been spent looking at products already selling in this category.', 'CEL-001', 'external', 'Knowledge', 0.62, 'Stage 0'),
  ('RC-CEL-003', 'Small Feature Treated as Enough', 'A minor feature change is being treated as a strong reason for customers to switch.', 'CEL-001', 'external', 'Strategic', 0.60, 'Stage 0'),
  ('RC-CEL-004', 'No Reason for Customer to Switch Brands', 'No thought given to why someone would leave a trusted brand for an unknown one.', 'CEL-001', 'external', 'Strategic', 0.63, 'Stage 0'),
  ('RC-CEL-005', 'Competing on Price Without Knowing Cost', 'The plan is to be cheaper than others without knowing what the product costs to make.', 'CEL-001', 'external', 'Knowledge', 0.61, 'Stage 0'),
  ('RC-CEL-006', 'No Cost Estimate for One Unit', 'No attempt has been made to price out a single working unit.', 'CEL-002', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-CEL-007', 'Component Prices Unknown', 'The cost of the main parts inside the product has never been checked.', 'CEL-002', 'external', 'Knowledge', 0.64, 'Stage 0'),
  ('RC-CEL-008', 'Selling Price Chosen Before Cost Is Known', 'A price point was decided based on what feels right, not on what it costs to make.', 'CEL-002', 'external', 'Behavioural', 0.62, 'Stage 0'),
  ('RC-CEL-009', 'Tooling and Packaging Costs Ignored', 'Only the parts are being counted, leaving out moulds, tooling, packaging and testing.', 'CEL-002', 'external', 'Knowledge', 0.60, 'Stage 0'),
  ('RC-CEL-010', 'Assuming Costs Will Drop Later', 'Believing costs will fall with volume without checking whether that is realistic here.', 'CEL-002', 'external', 'Strategic', 0.58, 'Stage 0'),
  ('RC-CEL-011', 'Expecting Quick Changes After Launch', 'The founder assumes the product can be improved quickly once it is out, like software.', 'CEL-003', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-CEL-012', 'No Awareness of Tooling Lead Times', 'No understanding that moulds and tooling take real time and money to create or change.', 'CEL-003', 'external', 'Knowledge', 0.63, 'Stage 0'),
  ('RC-CEL-013', 'Assuming Parts Are Always Available', 'Assuming components can be bought instantly whenever needed, in any quantity.', 'CEL-003', 'external', 'Operational', 0.61, 'Stage 0'),
  ('RC-CEL-014', 'Timeline Based on Software Speed', 'The build timeline was set using app-style speed, not physical product reality.', 'CEL-003', 'external', 'Strategic', 0.64, 'Stage 0'),
  ('RC-CEL-015', 'Target Customer Described as Everyone', 'The product is aimed at anyone, so no single customer is being served well.', 'CEL-004', 'external', 'Strategic', 0.67, 'Stage 0'),
  ('RC-CEL-016', 'No Specific Use Case Identified', 'There is no clear moment or situation where this product is the obvious choice.', 'CEL-004', 'external', 'Knowledge', 0.62, 'Stage 0'),
  ('RC-CEL-017', 'No Clear Reason to Buy Now', 'Nothing explains why the customer would buy this today rather than later or never.', 'CEL-004', 'external', 'Strategic', 0.60, 'Stage 0'),
  ('RC-CEL-018', 'Only Friends and Family Asked', 'Feedback so far has come only from people close to the founder.', 'CEL-004', 'external', 'Behavioural', 0.59, 'Stage 0'),
  ('RC-CEL-019', 'No Design for Manufacturing Review', 'The design has never been checked by anyone who would actually have to produce it.', 'CEL-005', 'external', 'Operational', 0.70, 'Stage 0â†’1'),
  ('RC-CEL-020', 'Prototype Parts Not Available in Bulk', 'The components used in the sample cannot be bought in production quantities.', 'CEL-005', 'external', 'Operational', 0.66, 'Stage 0â†’1'),
  ('RC-CEL-021', 'No Manufacturer Has Seen the Design', 'No factory or contract manufacturer has been approached with the actual design files.', 'CEL-005', 'external', 'Behavioural', 0.68, 'Stage 0â†’1'),
  ('RC-CEL-022', 'Assuming the Prototype Just Needs Scaling', 'The founder believes production is the same design made in larger numbers.', 'CEL-005', 'external', 'Knowledge', 0.65, 'Stage 0â†’1'),
  ('RC-CEL-023', 'No Production Version of the Design Exists', 'Only a hand-built version exists, with no manufacturable drawing or file set.', 'CEL-005', 'external', 'Operational', 0.64, 'Stage 0â†’1'),
  ('RC-CEL-024', 'Certification Application Never Filed', 'The requirement is understood but the application has not been submitted.', 'CEL-006', 'external', 'Behavioural', 0.72, 'Stage 0â†’1'),
  ('RC-CEL-025', 'No Testing Lab Engaged', 'No safety or EMC testing has been booked with an approved lab.', 'CEL-006', 'external', 'Operational', 0.68, 'Stage 0â†’1'),
  ('RC-CEL-026', 'Certification Timeline Not in the Plan', 'The launch plan assumes certification takes no meaningful time.', 'CEL-006', 'external', 'Strategic', 0.66, 'Stage 0â†’1'),
  ('RC-CEL-027', 'No Budget for Testing and Certification', 'Money has not been set aside for the real cost of compliance.', 'CEL-006', 'external', 'Knowledge', 0.63, 'Stage 0â†’1'),
  ('RC-CEL-028', 'Certification Treated as a Formality', 'The founder assumes approval is automatic rather than a real gate that can fail.', 'CEL-006', 'external', 'Psychological', 0.61, 'Stage 0â†’1'),
  ('RC-CEL-029', 'No Confirmed Supplier for Key Parts', 'Critical components have no named, agreed supplier behind them.', 'CEL-007', 'external', 'Operational', 0.71, 'Stage 0â†’1'),
  ('RC-CEL-030', 'Minimum Order Quantities Never Checked', 'No one has asked suppliers what the smallest order they will accept is.', 'CEL-007', 'external', 'Knowledge', 0.67, 'Stage 0â†’1'),
  ('RC-CEL-031', 'Component Lead Times Unknown', 'How long parts take to arrive has never been confirmed with a supplier.', 'CEL-007', 'external', 'Knowledge', 0.66, 'Stage 0â†’1'),
  ('RC-CEL-032', 'Only Online Prices Used, No Real Quotes', 'Planning is based on listed web prices rather than written supplier quotes.', 'CEL-007', 'external', 'Behavioural', 0.64, 'Stage 0â†’1'),
  ('RC-CEL-033', 'No Backup Supplier Identified', 'If one supplier fails, there is no second option for that part.', 'CEL-007', 'external', 'Operational', 0.62, 'Stage 0â†’1'),
  ('RC-CEL-034', 'Cost Based on Small Quantity Buying', 'Unit cost was worked out from buying a few pieces, not production volumes.', 'CEL-008', 'external', 'Knowledge', 0.70, 'Stage 0â†’1'),
  ('RC-CEL-035', 'No Factory Quote at Target Volume', 'No manufacturer has given a written price for the real first order size.', 'CEL-008', 'external', 'Operational', 0.68, 'Stage 0â†’1'),
  ('RC-CEL-036', 'Assembly and Labour Costs Left Out', 'Only parts are counted, ignoring what it costs to actually put the product together.', 'CEL-008', 'external', 'Knowledge', 0.65, 'Stage 0â†’1'),
  ('RC-CEL-037', 'Margin Calculated on an Unverified Cost', 'Profit expectations are built on a cost number nobody has confirmed.', 'CEL-008', 'external', 'Strategic', 0.64, 'Stage 0â†’1'),
  ('RC-CEL-038', 'No Warranty Terms Defined', 'There is no written statement of what the customer is promised if the product fails.', 'CEL-009', 'external', 'Operational', 0.69, 'Stage 0â†’1'),
  ('RC-CEL-039', 'No Repair or Replacement Process', 'Nothing is set up for getting a failed unit fixed or swapped.', 'CEL-009', 'external', 'Operational', 0.67, 'Stage 0â†’1'),
  ('RC-CEL-040', 'Expected Failure Rate Unknown', 'The founder has no estimate of how many units will fail in the first year.', 'CEL-009', 'external', 'Knowledge', 0.63, 'Stage 0â†’1'),
  ('RC-CEL-041', 'Defect Rate Never Measured', 'Nobody tracks what share of units fail, so quality problems are invisible until customers complain.', 'CEL-010', 'external', 'Operational', 0.72, 'Stage 1â†’10+'),
  ('RC-CEL-042', 'No Incoming Parts Inspection', 'Components go straight into production without being checked on arrival.', 'CEL-010', 'external', 'Operational', 0.68, 'Stage 1â†’10+'),
  ('RC-CEL-043', 'Repeat Faults Never Traced', 'The same fault keeps appearing because nobody investigates why it happens.', 'CEL-010', 'external', 'Operational', 0.70, 'Stage 1â†’10+'),
  ('RC-CEL-044', 'Quality Varies Between Batches', 'Each production run is treated separately, with no fixed standard to hold them to.', 'CEL-010', 'external', 'Operational', 0.66, 'Stage 1â†’10+'),
  ('RC-CEL-045', 'Customer Complaints Are the Only Signal', 'Quality problems are discovered by customers rather than caught in the factory.', 'CEL-010', 'external', 'Operational', 0.64, 'Stage 1â†’10+'),
  ('RC-CEL-046', 'No Service Coverage Outside Home City', 'Customers elsewhere have nowhere to take a faulty unit.', 'CEL-011', 'external', 'Operational', 0.71, 'Stage 1â†’10+'),
  ('RC-CEL-047', 'No Spare Parts Held', 'There is no stock of parts, so nothing can actually be repaired.', 'CEL-011', 'external', 'Operational', 0.68, 'Stage 1â†’10+'),
  ('RC-CEL-048', 'Every Repair Becomes a Replacement', 'Whole units are swapped because repair is not set up, which destroys margin.', 'CEL-011', 'external', 'Operational', 0.66, 'Stage 1â†’10+'),
  ('RC-CEL-049', 'No Turnaround Time Promised or Measured', 'Customers are not told how long a repair takes, and it is never tracked.', 'CEL-011', 'external', 'Operational', 0.62, 'Stage 1â†’10+'),
  ('RC-CEL-050', 'Service Still Handled by the Core Team', 'Repairs pull the founder and core team away from building the business.', 'CEL-011', 'external', 'Behavioural', 0.64, 'Stage 1â†’10+'),
  ('RC-CEL-051', 'Stock Age Never Reviewed', 'Nobody checks how long inventory has been sitting before it becomes hard to sell.', 'CEL-012', 'external', 'Operational', 0.70, 'Stage 1â†’10+'),
  ('RC-CEL-052', 'No Plan for End of Life Components', 'A supplier discontinuing a part would strand the existing design and stock.', 'CEL-012', 'external', 'Strategic', 0.68, 'Stage 1â†’10+'),
  ('RC-CEL-053', 'Ordering Based on Optimism', 'Purchase quantities are set on hoped for sales rather than actual sell through.', 'CEL-012', 'external', 'Behavioural', 0.67, 'Stage 1â†’10+'),
  ('RC-CEL-054', 'Old Model Stock Held After New Launch', 'Previous model inventory is not cleared before the replacement arrives.', 'CEL-012', 'external', 'Strategic', 0.63, 'Stage 1â†’10+'),
  ('RC-CEL-055', 'Cash Locked in Unsold Stock', 'Working capital is tied up in inventory instead of being available to the business.', 'CEL-012', 'external', 'Operational', 0.69, 'Stage 1â†’10+'),
  ('RC-CEL-056', 'Retail Terms Agreed Without Margin Modelling', 'Channel agreements were signed before working out what was left per unit.', 'CEL-013', 'external', 'Strategic', 0.71, 'Stage 1â†’10+'),
  ('RC-CEL-057', 'Marketplace Fees and Returns Not Counted', 'Platform commission, returns and shipping are missing from the unit economics.', 'CEL-013', 'external', 'Knowledge', 0.68, 'Stage 1â†’10+'),
  ('RC-CEL-058', 'Discounting to Win Shelf Space', 'Price is cut to get into retail, and the discount never comes back.', 'CEL-013', 'external', 'Behavioural', 0.64, 'Stage 1â†’10+'),
  ('RC-CEL-059', 'Profit Per Channel Unknown', 'There is no view of which channels actually make money and which lose it.', 'CEL-013', 'external', 'Operational', 0.66, 'Stage 1â†’10+'),
  ('RC-CEL-060', 'All Production With One Factory', 'The entire output depends on a single manufacturer continuing to perform.', 'CEL-014', 'external', 'Operational', 0.73, 'Stage 1â†’10+'),
  ('RC-CEL-061', 'No Second Factory Qualified', 'No alternative manufacturer has been trialled or approved.', 'CEL-014', 'external', 'Strategic', 0.69, 'Stage 1â†’10+'),
  ('RC-CEL-062', 'All Key Parts From One Region', 'A single region disruption would stop every critical component at once.', 'CEL-014', 'external', 'Operational', 0.67, 'Stage 1â†’10+'),
  ('RC-CEL-063', 'No Buffer Stock for Supply Interruption', 'Nothing is held back to keep selling if supply pauses.', 'CEL-014', 'external', 'Operational', 0.63, 'Stage 1â†’10+'),
  ('RC-CEL-064', 'No End of Life Date for Current Model', 'Nobody has decided when the current product stops being the main one.', 'CEL-015', 'external', 'Strategic', 0.68, 'Stage 1â†’10+'),
  ('RC-CEL-065', 'No Next Model in Development', 'All effort goes to the current product, with nothing being readied to replace it.', 'CEL-015', 'external', 'Strategic', 0.70, 'Stage 1â†’10+'),
  ('RC-CEL-066', 'Competitor Refresh Cycles Not Tracked', 'How often rivals launch new versions is not watched or planned against.', 'CEL-015', 'external', 'Knowledge', 0.64, 'Stage 1â†’10+')
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
         '["consumer_electronics"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-CEL-001', 'If someone can already buy something similar from a big brand, why would they buy yours instead?', 'open_text', 'Idea & Validation', 'CORE', 'CEL-001', 'RC-CEL-001', 1, 'Stage 0'),
  ('S0-CEL-002', 'Have you actually looked at what is already being sold that does something close to this?', 'open_text', 'Idea & Validation', 'CORE', 'CEL-001', 'RC-CEL-002', 1, 'Stage 0'),
  ('S0-CEL-003', 'Is the difference in your product one small feature, or something a customer would really notice?', 'open_text', 'Idea & Validation', 'CORE', 'CEL-001', 'RC-CEL-003', 1, 'Stage 0'),
  ('S0-CEL-004', 'What would make someone leave a brand they already trust and try yours?', 'open_text', 'Idea & Validation', 'CORE', 'CEL-001', 'RC-CEL-004', 2, 'Stage 0'),
  ('S0-CEL-005', 'Are you planning to be cheaper than others? If yes, do you know what yours costs to make?', 'open_text', 'Idea & Validation', 'CORE', 'CEL-001', 'RC-CEL-005', 2, 'Stage 0'),
  ('S0-CEL-006', 'Do you have any idea what it would cost to make just one real working unit?', 'open_text', 'Idea & Validation', 'CORE', 'CEL-002', 'RC-CEL-006', 1, 'Stage 0'),
  ('S0-CEL-007', 'Do you know roughly what the main parts inside your product cost?', 'open_text', 'Idea & Validation', 'CORE', 'CEL-002', 'RC-CEL-007', 1, 'Stage 0'),
  ('S0-CEL-008', 'How did you decide your selling price? Was it based on cost, or on what felt right?', 'open_text', 'Idea & Validation', 'CORE', 'CEL-002', 'RC-CEL-008', 2, 'Stage 0'),
  ('S0-CEL-009', 'Apart from the parts, have you counted packaging, moulds, testing and shipping in your cost?', 'open_text', 'Idea & Validation', 'CORE', 'CEL-002', 'RC-CEL-009', 2, 'Stage 0'),
  ('S0-CEL-010', 'Are you expecting to change and improve this quickly after launch, like an app?', 'open_text', 'Idea & Validation', 'CORE', 'CEL-003', 'RC-CEL-011', 1, 'Stage 0'),
  ('S0-CEL-011', 'Do you know how long it takes and what it costs to make or change a mould or tool?', 'open_text', 'Idea & Validation', 'CORE', 'CEL-003', 'RC-CEL-012', 2, 'Stage 0'),
  ('S0-CEL-012', 'How long do you think it will take from idea to a finished product you can sell?', 'open_text', 'Idea & Validation', 'CORE', 'CEL-003', 'RC-CEL-014', 1, 'Stage 0'),
  ('S0-CEL-013', 'Can you name one specific type of person this is for, or is it for anyone right now?', 'open_text', 'Idea & Validation', 'CORE', 'CEL-004', 'RC-CEL-015', 1, 'Stage 0'),
  ('S0-CEL-014', 'Describe one moment in someone daily life where they would reach for your product.', 'open_text', 'Idea & Validation', 'CORE', 'CEL-004', 'RC-CEL-016', 2, 'Stage 0'),
  ('S0-CEL-015', 'Has anyone outside your friends and family told you they would buy this?', 'open_text', 'Idea & Validation', 'CORE', 'CEL-004', 'RC-CEL-018', 1, 'Stage 0'),
  ('S01-CEL-001', 'Could a factory actually make your current design, or does it only work because you built it by hand?', 'open_text', 'Product Development', 'CORE', 'CEL-005', 'RC-CEL-019', 2, 'Stage 0â†’1'),
  ('S01-CEL-002', 'Are the parts in your prototype ones you can buy in large quantities, or only in ones and twos?', 'open_text', 'Product Development', 'CORE', 'CEL-005', 'RC-CEL-020', 2, 'Stage 0â†’1'),
  ('S01-CEL-003', 'Has a manufacturer actually looked at your design and told you what needs to change?', 'open_text', 'Product Development', 'CORE', 'CEL-005', 'RC-CEL-021', 2, 'Stage 0â†’1'),
  ('S01-CEL-004', 'Do you think production is just your prototype made in bigger numbers, or a different design job?', 'open_text', 'Product Development', 'CORE', 'CEL-005', 'RC-CEL-022', 3, 'Stage 0â†’1'),
  ('S01-CEL-005', 'Do you have proper production drawings or files, or only the hand built sample?', 'open_text', 'Product Development', 'CORE', 'CEL-005', 'RC-CEL-023', 2, 'Stage 0â†’1'),
  ('S01-CEL-006', 'Have you applied for BIS registration, or is it still on the to do list?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-006', 'RC-CEL-024', 2, 'Stage 0â†’1'),
  ('S01-CEL-007', 'Have you booked safety or EMC testing with an approved lab yet?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-006', 'RC-CEL-025', 2, 'Stage 0â†’1'),
  ('S01-CEL-008', 'How many months has your launch plan set aside for certification?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-006', 'RC-CEL-026', 2, 'Stage 0â†’1'),
  ('S01-CEL-009', 'How much money have you kept aside for testing and certification costs?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-006', 'RC-CEL-027', 2, 'Stage 0â†’1'),
  ('S01-CEL-010', 'What is your plan if your product fails its first certification test?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-006', 'RC-CEL-028', 3, 'Stage 0â†’1'),
  ('S01-CEL-011', 'Do you have a confirmed supplier for your key parts, or just prices you found online?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-007', 'RC-CEL-029', 2, 'Stage 0â†’1'),
  ('S01-CEL-012', 'What is the smallest quantity you would have to order for your main components?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-007', 'RC-CEL-030', 2, 'Stage 0â†’1'),
  ('S01-CEL-013', 'How long would it take for your key parts to arrive after you place an order?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-007', 'RC-CEL-031', 2, 'Stage 0â†’1'),
  ('S01-CEL-014', 'Do you have written quotes from suppliers, or only listed web prices?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-007', 'RC-CEL-032', 2, 'Stage 0â†’1'),
  ('S01-CEL-015', 'If your main supplier could not deliver, who would you go to instead?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-007', 'RC-CEL-033', 3, 'Stage 0â†’1'),
  ('S01-CEL-016', 'Is your cost per unit based on buying a few pieces, or on a real production order?', 'open_text', 'Financial Management', 'CORE', 'CEL-008', 'RC-CEL-034', 2, 'Stage 0â†’1'),
  ('S01-CEL-017', 'Have you got a written factory quote at 500 or 1000 units?', 'open_text', 'Financial Management', 'CORE', 'CEL-008', 'RC-CEL-035', 2, 'Stage 0â†’1'),
  ('S01-CEL-018', 'Does your cost include what it takes to assemble the product, not just the parts?', 'open_text', 'Financial Management', 'CORE', 'CEL-008', 'RC-CEL-036', 2, 'Stage 0â†’1'),
  ('S01-CEL-019', 'If a customer unit stops working in month two, what happens right now?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-009', 'RC-CEL-038', 2, 'Stage 0â†’1'),
  ('S01-CEL-020', 'Out of every 100 units you sell, how many do you expect to come back as faulty?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-009', 'RC-CEL-040', 3, 'Stage 0â†’1'),
  ('S10-CEL-001', 'Do you know what percentage of your units come back faulty, or would you have to go and find out?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-010', 'RC-CEL-041', 2, 'Stage 1â†’10+'),
  ('S10-CEL-002', 'Are parts checked when they arrive, or do they go straight into production?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-010', 'RC-CEL-042', 2, 'Stage 1â†’10+'),
  ('S10-CEL-003', 'When the same fault appears again and again, does anyone find out why?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-010', 'RC-CEL-043', 3, 'Stage 1â†’10+'),
  ('S10-CEL-004', 'Does every production batch come out the same, or does quality depend on the run?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-010', 'RC-CEL-044', 3, 'Stage 1â†’10+'),
  ('S10-CEL-005', 'How do you usually find out about a quality problem, from your factory or from customers?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-010', 'RC-CEL-045', 2, 'Stage 1â†’10+'),
  ('S10-CEL-006', 'If a customer in a city you do not cover needs a repair, what actually happens?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-011', 'RC-CEL-046', 2, 'Stage 1â†’10+'),
  ('S10-CEL-007', 'Do you hold spare parts, or does a repair mean replacing the whole unit?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-011', 'RC-CEL-047', 2, 'Stage 1â†’10+'),
  ('S10-CEL-008', 'What does it cost you every time you replace a unit instead of repairing it?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-011', 'RC-CEL-048', 3, 'Stage 1â†’10+'),
  ('S10-CEL-009', 'How long do you tell a customer a repair will take, and do you measure whether you hit it?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-011', 'RC-CEL-049', 2, 'Stage 1â†’10+'),
  ('S10-CEL-010', 'Who handles service requests today, and how much of your own time does it take?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-011', 'RC-CEL-050', 2, 'Stage 1â†’10+'),
  ('S10-CEL-011', 'How much cash is sitting in stock right now, and how long has it been there?', 'open_text', 'Financial Management', 'CORE', 'CEL-012', 'RC-CEL-055', 2, 'Stage 1â†’10+'),
  ('S10-CEL-012', 'Do you review how old your stock is, or only how much of it there is?', 'open_text', 'Financial Management', 'CORE', 'CEL-012', 'RC-CEL-051', 2, 'Stage 1â†’10+'),
  ('S10-CEL-013', 'What happens to your product if a key component goes end of life?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-012', 'RC-CEL-052', 3, 'Stage 1â†’10+'),
  ('S10-CEL-014', 'Are your order quantities based on actual sales so far, or on what you hope to sell?', 'open_text', 'Financial Management', 'CORE', 'CEL-012', 'RC-CEL-053', 2, 'Stage 1â†’10+'),
  ('S10-CEL-015', 'When you launched your newest model, was the old stock already cleared?', 'open_text', 'Financial Management', 'CORE', 'CEL-012', 'RC-CEL-054', 2, 'Stage 1â†’10+'),
  ('S10-CEL-016', 'Did you work out your margin before agreeing retailer and marketplace terms, or after?', 'open_text', 'Financial Management', 'CORE', 'CEL-013', 'RC-CEL-056', 2, 'Stage 1â†’10+'),
  ('S10-CEL-017', 'Does your cost per unit include platform commission, returns and shipping?', 'open_text', 'Financial Management', 'CORE', 'CEL-013', 'RC-CEL-057', 2, 'Stage 1â†’10+'),
  ('S10-CEL-018', 'Have you cut your price to get shelf space, and did that price ever go back up?', 'open_text', 'Financial Management', 'CORE', 'CEL-013', 'RC-CEL-058', 3, 'Stage 1â†’10+'),
  ('S10-CEL-019', 'Which of your sales channels makes the most profit per unit, and which makes the least?', 'open_text', 'Financial Management', 'CORE', 'CEL-013', 'RC-CEL-059', 3, 'Stage 1â†’10+'),
  ('S10-CEL-020', 'If your factory stopped tomorrow, how long before you could produce anywhere else?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-014', 'RC-CEL-060', 3, 'Stage 1â†’10+'),
  ('S10-CEL-021', 'Have you ever trial produced with a second factory, or only talked about it?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-014', 'RC-CEL-061', 2, 'Stage 1â†’10+'),
  ('S10-CEL-022', 'Do all your key parts come from the same region, or are they spread out?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-014', 'RC-CEL-062', 2, 'Stage 1â†’10+'),
  ('S10-CEL-023', 'How many weeks could you keep selling if supply stopped today?', 'open_text', 'Operations & Systems', 'CORE', 'CEL-014', 'RC-CEL-063', 3, 'Stage 1â†’10+'),
  ('S10-CEL-024', 'Do you know when your current model gets replaced, or is that decision still open?', 'open_text', 'Strategy & Planning', 'CORE', 'CEL-015', 'RC-CEL-064', 2, 'Stage 1â†’10+'),
  ('S10-CEL-025', 'Is anyone working on the next product, or is all effort on the current one?', 'open_text', 'Strategy & Planning', 'CORE', 'CEL-015', 'RC-CEL-065', 2, 'Stage 1â†’10+')
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
  ('S0-CEL-001', 'problem-clarity'),
  ('S0-CEL-002', 'problem-clarity'),
  ('S0-CEL-003', 'problem-clarity'),
  ('S0-CEL-004', 'problem-clarity'),
  ('S0-CEL-005', 'problem-clarity'),
  ('S0-CEL-006', 'customer-discovery'),
  ('S0-CEL-007', 'customer-discovery'),
  ('S0-CEL-008', 'customer-discovery'),
  ('S0-CEL-009', 'customer-discovery'),
  ('S0-CEL-010', 'problem-clarity'),
  ('S0-CEL-011', 'problem-clarity'),
  ('S0-CEL-012', 'problem-clarity'),
  ('S0-CEL-013', 'icp'),
  ('S0-CEL-014', 'icp'),
  ('S0-CEL-015', 'icp'),
  ('S01-CEL-001', 'technical-quality'),
  ('S01-CEL-002', 'technical-quality'),
  ('S01-CEL-003', 'technical-quality'),
  ('S01-CEL-004', 'technical-quality'),
  ('S01-CEL-005', 'technical-quality'),
  ('S01-CEL-006', 'problem-clarity'),
  ('S01-CEL-007', 'problem-clarity'),
  ('S01-CEL-008', 'problem-clarity'),
  ('S01-CEL-009', 'problem-clarity'),
  ('S01-CEL-010', 'problem-clarity'),
  ('S01-CEL-011', 'problem-clarity'),
  ('S01-CEL-012', 'problem-clarity'),
  ('S01-CEL-013', 'problem-clarity'),
  ('S01-CEL-014', 'problem-clarity'),
  ('S01-CEL-015', 'problem-clarity'),
  ('S01-CEL-016', 'willingness-to-pay'),
  ('S01-CEL-017', 'willingness-to-pay'),
  ('S01-CEL-018', 'willingness-to-pay'),
  ('S01-CEL-019', 'technical-quality'),
  ('S01-CEL-020', 'technical-quality'),
  ('S10-CEL-001', 'technical-quality'),
  ('S10-CEL-002', 'technical-quality'),
  ('S10-CEL-003', 'technical-quality'),
  ('S10-CEL-004', 'technical-quality'),
  ('S10-CEL-005', 'technical-quality'),
  ('S10-CEL-006', 'technical-quality'),
  ('S10-CEL-007', 'technical-quality'),
  ('S10-CEL-008', 'technical-quality'),
  ('S10-CEL-009', 'technical-quality'),
  ('S10-CEL-010', 'technical-quality'),
  ('S10-CEL-011', 'willingness-to-pay'),
  ('S10-CEL-012', 'willingness-to-pay'),
  ('S10-CEL-013', 'willingness-to-pay'),
  ('S10-CEL-014', 'willingness-to-pay'),
  ('S10-CEL-015', 'willingness-to-pay'),
  ('S10-CEL-016', 'willingness-to-pay'),
  ('S10-CEL-017', 'willingness-to-pay'),
  ('S10-CEL-018', 'willingness-to-pay'),
  ('S10-CEL-019', 'willingness-to-pay'),
  ('S10-CEL-020', 'problem-clarity'),
  ('S10-CEL-021', 'problem-clarity'),
  ('S10-CEL-022', 'problem-clarity'),
  ('S10-CEL-023', 'problem-clarity'),
  ('S10-CEL-024', 'problem-clarity'),
  ('S10-CEL-025', 'problem-clarity')
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
         '["consumer_electronics"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-CEL-001', 'Ideation â€” Consumer Electronics Market Fundamentals', 'CEL-001', '["RC-CEL-002"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Visit a shop or online store and list 5 products that already do something close to yours.", "Note the price and the main selling point of each.", "Write down where your idea sits among them."]'::jsonb, '[{"name": "Competitor Shelf Scan", "brief": "Listing products already sold in the same category to see the real market."}]'::jsonb),
  ('INT-CEL-002', 'Ideation â€” Consumer Electronics Market Fundamentals', 'CEL-001', '["RC-CEL-001", "RC-CEL-003"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Write one sentence saying what makes your product different.", "Read it out to someone who does not know your idea.", "If they shrug, the difference is not strong enough yet."]'::jsonb, '[{"name": "Differentiation Statement", "brief": "A single clear sentence describing what makes the product different."}]'::jsonb),
  ('INT-CEL-003', 'Ideation â€” Consumer Electronics Market Fundamentals', 'CEL-001', '["RC-CEL-004", "RC-CEL-005"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Pick one brand your customer already trusts.", "Write down one honest reason someone would switch from it to you.", "If the only reason is price, check your cost first."]'::jsonb, '[{"name": "Switching Reason Test", "brief": "Testing whether there is a real reason for a customer to leave a trusted brand."}]'::jsonb),
  ('INT-CEL-004', 'Ideation â€” Consumer Electronics Cost Fundamentals', 'CEL-002', '["RC-CEL-006", "RC-CEL-007"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["List the main parts your product needs.", "Find the price of each part online or from a supplier.", "Add them up to get a rough cost for one unit."]'::jsonb, '[{"name": "Bill of Materials (Basic)", "brief": "A simple list of parts and their costs to get a first unit cost."}]'::jsonb),
  ('INT-CEL-005', 'Ideation â€” Consumer Electronics Cost Fundamentals', 'CEL-002', '["RC-CEL-009"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Add packaging, testing, shipping and tooling to your parts cost.", "Keep these as separate lines so you can see each one.", "Compare the total against the price you had in mind."]'::jsonb, '[{"name": "Full Cost Picture", "brief": "Counting all costs, not just parts, before setting a price."}]'::jsonb),
  ('INT-CEL-006', 'Ideation â€” Consumer Electronics Cost Fundamentals', 'CEL-002', '["RC-CEL-008", "RC-CEL-010"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Write down the price you were planning to charge and why.", "Check it against your real cost per unit.", "If there is no margin left, change the product or the price now, not later."]'::jsonb, '[{"name": "Cost Before Price", "brief": "Setting price only after the real cost of making one unit is known."}]'::jsonb),
  ('INT-CEL-007', 'Ideation â€” Consumer Electronics Build Reality', 'CEL-003', '["RC-CEL-011", "RC-CEL-014"]'::jsonb, '[1]'::jsonb, 'Execution Planning', '["Write your expected timeline from idea to first sellable unit.", "Show it to someone who has built a physical product before.", "Adjust it based on what they tell you."]'::jsonb, '[{"name": "Hardware Timeline Check", "brief": "Testing a build timeline against someone with real hardware experience."}]'::jsonb),
  ('INT-CEL-008', 'Ideation â€” Consumer Electronics Build Reality', 'CEL-003', '["RC-CEL-012", "RC-CEL-013"]'::jsonb, '[1]'::jsonb, 'Execution Planning', '["Ask one manufacturer what a mould or tool for your product would cost and how long it takes.", "Ask what happens if the design changes after tooling is made.", "Write both answers into your plan."]'::jsonb, '[{"name": "Tooling Reality Check", "brief": "Getting real tooling cost and lead time from a manufacturer early."}]'::jsonb),
  ('INT-CEL-009', 'Ideation â€” Consumer Electronics Customer Clarity', 'CEL-004', '["RC-CEL-015", "RC-CEL-016"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Pick one specific type of person to build for first.", "Describe one moment in their day when they would use your product.", "Write both down in two lines."]'::jsonb, '[{"name": "One Customer, One Moment", "brief": "Narrowing to a single customer type and a single clear use moment."}]'::jsonb),
  ('INT-CEL-010', 'Ideation â€” Consumer Electronics Customer Clarity', 'CEL-004', '["RC-CEL-017", "RC-CEL-018"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Talk to 5 people who are not friends or family.", "Ask what they use today instead of your product.", "Ask what would make them buy something new now rather than later."]'::jsonb, '[{"name": "Outside Feedback Round", "brief": "Getting first honest reactions from people with no personal connection to the founder."}]'::jsonb),
  ('INT-CEL-011', 'Validation to Traction â€” Consumer Electronics Manufacturability', 'CEL-005', '["RC-CEL-019", "RC-CEL-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Development', '["Send your design to one contract manufacturer for review.", "Ask them to list every change needed to make it producible.", "Work through that list before building another prototype."]'::jsonb, '[{"name": "Design for Manufacturing Review", "brief": "Getting a real manufacturer to mark up the design before production planning."}]'::jsonb),
  ('INT-CEL-012', 'Validation to Traction â€” Consumer Electronics Manufacturability', 'CEL-005', '["RC-CEL-020", "RC-CEL-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Development', '["List every part in your prototype.", "Mark the ones you cannot buy in production quantities.", "Find a production equivalent for each one before locking the design."]'::jsonb, '[{"name": "Production Parts Swap List", "brief": "Replacing prototype only components with parts available at volume."}]'::jsonb),
  ('INT-CEL-013', 'Validation to Traction â€” Consumer Electronics Compliance', 'CEL-006', '["RC-CEL-024"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Identify the exact certification your product category needs.", "Submit the application this month rather than researching further.", "Record the submission date and expected decision date."]'::jsonb, '[{"name": "File, Do Not Research", "brief": "Moving from understanding a compliance requirement to actually submitting it."}]'::jsonb),
  ('INT-CEL-014', 'Validation to Traction â€” Consumer Electronics Compliance', 'CEL-006', '["RC-CEL-025", "RC-CEL-026"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Book testing with an approved lab and get a date in writing.", "Add that date and the retest window to your launch plan.", "Move your launch date if the two do not fit."]'::jsonb, '[{"name": "Certification in the Timeline", "brief": "Putting real testing dates into the launch plan instead of assuming they fit."}]'::jsonb),
  ('INT-CEL-015', 'Validation to Traction â€” Consumer Electronics Compliance', 'CEL-006', '["RC-CEL-027", "RC-CEL-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Compliance', '["Ask the lab what a full test plus one retest costs.", "Set that amount aside as a separate line in your budget.", "Assume at least one retest will be needed."]'::jsonb, '[{"name": "Compliance Budget Line", "brief": "Treating certification cost and a likely retest as a planned expense."}]'::jsonb),
  ('INT-CEL-016', 'Validation to Traction â€” Consumer Electronics Supply Chain', 'CEL-007', '["RC-CEL-029", "RC-CEL-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Supply Chain', '["Pick your five most critical components.", "Get a written quote from a real supplier for each one.", "Keep the quotes on file with dates and validity periods."]'::jsonb, '[{"name": "Written Quotes Only", "brief": "Replacing web listed prices with real supplier quotes for critical parts."}]'::jsonb),
  ('INT-CEL-017', 'Validation to Traction â€” Consumer Electronics Supply Chain', 'CEL-007', '["RC-CEL-030", "RC-CEL-031"]'::jsonb, '[2, 3, 4]'::jsonb, 'Supply Chain', '["Ask each supplier for minimum order quantity and lead time.", "Put both numbers next to each part in one sheet.", "Check whether your cash and timeline can actually meet them."]'::jsonb, '[{"name": "MOQ and Lead Time Sheet", "brief": "A single view of order minimums and delivery times for every key part."}]'::jsonb),
  ('INT-CEL-018', 'Validation to Traction â€” Consumer Electronics Supply Chain', 'CEL-007', '["RC-CEL-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Supply Chain', '["Find a second source for every single source component.", "Get at least an indicative price from them.", "Note which parts still have no backup and treat those as your real risk."]'::jsonb, '[{"name": "Second Source Mapping", "brief": "Identifying a backup supplier for each critical component before volume production."}]'::jsonb),
  ('INT-CEL-019', 'Validation to Traction â€” Consumer Electronics Unit Economics', 'CEL-008', '["RC-CEL-034", "RC-CEL-035"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Ask a factory for a written price at your realistic first order size.", "Compare it against the cost you have been planning with.", "Update every number that depended on the old cost."]'::jsonb, '[{"name": "Volume Quote Reset", "brief": "Rebuilding unit economics on a real factory quote at production volume."}]'::jsonb),
  ('INT-CEL-020', 'Validation to Traction â€” Consumer Electronics Unit Economics', 'CEL-008', '["RC-CEL-036", "RC-CEL-037"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Add assembly, testing, packaging and freight to your parts cost.", "Recalculate your margin on that full number.", "If the margin disappears, fix it before you order stock."]'::jsonb, '[{"name": "Landed Cost Margin Check", "brief": "Checking margin against the full cost of a finished, delivered unit."}]'::jsonb),
  ('INT-CEL-021', 'Validation to Traction â€” Consumer Electronics Service Readiness', 'CEL-009', '["RC-CEL-038", "RC-CEL-039"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Write your warranty in plain language on one page.", "Decide whether a failed unit gets repaired or replaced.", "Write down who does it and how the customer sends it back."]'::jsonb, '[{"name": "One Page Warranty", "brief": "A simple written promise and process for handling failed units."}]'::jsonb),
  ('INT-CEL-022', 'Validation to Traction â€” Consumer Electronics Service Readiness', 'CEL-009', '["RC-CEL-040"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Estimate how many units out of 100 will fail in the first year.", "Multiply that by your unit cost to get a replacement reserve.", "Hold that money back before counting your profit."]'::jsonb, '[{"name": "Failure Rate Reserve", "brief": "Setting aside money for expected returns and replacements before booking profit."}]'::jsonb),
  ('INT-CEL-023', 'Growth to Maturity â€” Consumer Electronics Quality Control', 'CEL-010', '["RC-CEL-041", "RC-CEL-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Start recording defects by batch and by fault type.", "Review the numbers once a month, not only when complaints spike.", "Set a defect rate you will not accept and act when it is crossed."]'::jsonb, '[{"name": "Defect Rate Tracking", "brief": "Measuring failures by batch and fault type so quality problems surface early."}]'::jsonb),
  ('INT-CEL-024', 'Growth to Maturity â€” Consumer Electronics Quality Control', 'CEL-010', '["RC-CEL-042", "RC-CEL-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Add a simple incoming check for critical components.", "Write one quality checklist every batch must pass before shipping.", "Keep the checklist the same across runs and factories."]'::jsonb, '[{"name": "Incoming and Outgoing Checks", "brief": "A fixed inspection standard applied to every batch, not per run."}]'::jsonb),
  ('INT-CEL-025', 'Growth to Maturity â€” Consumer Electronics Quality Control', 'CEL-010', '["RC-CEL-043"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Pick your most common repeat fault.", "Trace it back to the part, process or supplier causing it.", "Fix that cause before adding more production volume."]'::jsonb, '[{"name": "Repeat Fault Root Cause", "brief": "Tracing recurring defects to their source instead of replacing units."}]'::jsonb),
  ('INT-CEL-026', 'Growth to Maturity â€” Consumer Electronics After Sales', 'CEL-011', '["RC-CEL-046", "RC-CEL-049"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["List the cities where you now have customers but no service option.", "Set up one repair partner or collection point per priority city.", "Publish a turnaround time and start measuring against it."]'::jsonb, '[{"name": "Minimum Service Coverage", "brief": "A basic repair route and promised turnaround wherever customers exist."}]'::jsonb),
  ('INT-CEL-027', 'Growth to Maturity â€” Consumer Electronics After Sales', 'CEL-011', '["RC-CEL-047", "RC-CEL-048"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Identify the parts that fail most often.", "Hold spare stock of those parts so repairs are possible.", "Compare repair cost against full replacement cost for each fault."]'::jsonb, '[{"name": "Repair Before Replace", "brief": "Holding spares for common failures to stop margin leaking through replacements."}]'::jsonb),
  ('INT-CEL-028', 'Growth to Maturity â€” Consumer Electronics After Sales', 'CEL-011', '["RC-CEL-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write down the steps you personally follow to handle a service request.", "Hand that process to one named person.", "Review it weekly instead of doing it yourself."]'::jsonb, '[{"name": "Service Handover", "brief": "Moving after sales off the founder by documenting and assigning the process."}]'::jsonb),
  ('INT-CEL-029', 'Growth to Maturity â€” Consumer Electronics Inventory Risk', 'CEL-012', '["RC-CEL-051", "RC-CEL-055"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["List your stock by age in weeks and the cash sitting in each bucket.", "Set an age limit after which stock gets discounted or cleared.", "Review this once a month."]'::jsonb, '[{"name": "Stock Ageing Review", "brief": "Tracking inventory by age and cash locked up, with a clearance trigger."}]'::jsonb),
  ('INT-CEL-030', 'Growth to Maturity â€” Consumer Electronics Inventory Risk', 'CEL-012', '["RC-CEL-052", "RC-CEL-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Supply Chain', '["Ask suppliers which of your parts are nearing end of life.", "Set order quantities from actual sell through, not forecasts.", "Plan a redesign or last time buy for any part being discontinued."]'::jsonb, '[{"name": "End of Life Watch", "brief": "Spotting components being discontinued before they strand the design."}]'::jsonb),
  ('INT-CEL-031', 'Growth to Maturity â€” Consumer Electronics Channel Economics', 'CEL-013', '["RC-CEL-056", "RC-CEL-057"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Build one sheet showing profit per unit for each channel.", "Include commission, returns, shipping and listing costs.", "Renegotiate or exit any channel that loses money."]'::jsonb, '[{"name": "Profit by Channel", "brief": "Seeing true margin per channel after all fees and returns."}]'::jsonb),
  ('INT-CEL-032', 'Growth to Maturity â€” Consumer Electronics Channel Economics', 'CEL-013', '["RC-CEL-058", "RC-CEL-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["List every discount currently running and why it started.", "Decide which ones end and on what date.", "Agree a price floor no channel is allowed to go below."]'::jsonb, '[{"name": "Discount Cleanup", "brief": "Ending legacy discounts and setting one price floor across channels."}]'::jsonb),
  ('INT-CEL-033', 'Growth to Maturity â€” Consumer Electronics Supply Risk', 'CEL-014', '["RC-CEL-060", "RC-CEL-061", "RC-CEL-062"]'::jsonb, '[5, 6, 7]'::jsonb, 'Supply Chain', '["Identify a second factory and run one small trial order with them.", "Split at least one key part across two sourcing regions.", "Write down how long a full switch would take."]'::jsonb, '[{"name": "Second Source Qualification", "brief": "Proving an alternative factory works before you are forced to use it."}]'::jsonb),
  ('INT-CEL-034', 'Growth to Maturity â€” Consumer Electronics Lifecycle Planning', 'CEL-015', '["RC-CEL-064", "RC-CEL-065", "RC-CEL-066"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Set an end of life date for your current model.", "Name who is working on the next one and what stage it is at.", "Track how often your main competitors launch new versions."]'::jsonb, '[{"name": "Next Model Roadmap", "brief": "A dated plan for retiring the current product and readying its replacement."}]'::jsonb)
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
  (SELECT COUNT(*) FROM new_interventions) AS interventions_inserted;-- expect 34"""),

        ('Education & EdTech', 'edtech', 'EDU', r"""WITH z AS (
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
  ('EDU-001', 'Unclear Who Pays and Who Learns', 'In education the learner and the payer are often different people, and the founder has not separated the two.', 'Idea & Validation', 'EdTech Buyer Clarity', 'external', 2, 4, 8, '["Learner and payer treated as the same person", "No idea who actually makes the buying decision", "Pricing aimed at the wrong person", "Never spoken to a real parent, employer or buyer", "Marketing message written for the learner only"]'::jsonb, '["edtech"]'::jsonb),
  ('EDU-002', 'Assuming People Will Pay for Learning', 'Free learning content is everywhere online, and the founder has not thought about why anyone would pay for theirs.', 'Idea & Validation', 'EdTech Willingness to Pay', 'external', 2, 4, 8, '["No thought given to the free alternatives online", "No clear reason why this is worth paying for", "Price picked without checking what people pay today", "Assuming quality alone justifies a price", "No evidence anyone has paid for something similar"]'::jsonb, '["edtech"]'::jsonb),
  ('EDU-003', 'No Idea If Learners Will Finish', 'The whole idea assumes learners complete the course, with no thought given to people dropping off partway.', 'Idea & Validation', 'EdTech Completion Reality', 'external', 3, 4, 8, '["Assuming most learners will complete", "No plan for keeping learners going", "Drop off treated as the learners fault", "No idea what a normal completion rate looks like", "Success defined as signups rather than learning"]'::jsonb, '["edtech"]'::jsonb),
  ('EDU-004', 'Content Plan Not Thought Through', 'There is no clarity on who creates the teaching content, how long it takes to make, or how it stays current.', 'Idea & Validation', 'EdTech Content Basics', 'external', 3, 4, 8, '["No one identified to create the content", "Time needed to make content underestimated", "No plan for keeping content updated", "Subject expertise assumed rather than confirmed", "No way to check whether a learner improved"]'::jsonb, '["edtech"]'::jsonb),
  ('EDU-005', 'Learners Sign Up but Do Not Complete', 'Real enrolments are happening but completion rates are low, and nobody is treating that as a product problem.', 'Product Development', 'EdTech Completion and Engagement', 'external', 3, 6, 9, '["Completion never measured lesson by lesson", "No support when a learner gets stuck", "Lessons longer than the time learners actually have", "No follow up when a learner goes quiet", "Refund requests linked to not finishing"]'::jsonb, '["edtech"]'::jsonb),
  ('EDU-006', 'Free Users Do Not Convert to Paid', 'A free tier or free demo class brings people in, but very few of them ever pay.', 'Sales & Revenue', 'EdTech Free to Paid Conversion', 'external', 4, 5, 9, '["Conversion rate from free to paid not measured", "Free version gives away the main value", "No clear moment where the learner is asked to pay", "Free users never contacted after signup", "Demo class not connected to an offer"]'::jsonb, '["edtech"]'::jsonb),
  ('EDU-007', 'Everything Depends on One Teacher', 'The founder or one star teacher delivers all the classes, so nothing can grow beyond their available hours.', 'Operations & Systems', 'EdTech Delivery Dependency', 'external', 3, 6, 9, '["All classes taught by one person", "No recorded version of the course", "Growth limited by one persons calendar", "No second teacher trained", "Learners choose the teacher, not the programme"]'::jsonb, '["edtech"]'::jsonb),
  ('EDU-008', 'Content Production Cannot Keep Up', 'Making and updating lessons takes far longer than expected, so the content pipeline is always behind.', 'Operations & Systems', 'EdTech Content Pipeline', 'external', 3, 5, 9, '["Content always behind schedule", "No measured time per lesson", "No content calendar", "Updates postponed indefinitely", "Quality dropping to meet deadlines"]'::jsonb, '["edtech"]'::jsonb),
  ('EDU-009', 'No Proof That Learners Get Results', 'There is no evidence learners actually improve, so nothing credible can be shown to a buyer.', 'Sales & Revenue', 'EdTech Outcome Evidence', 'external', 4, 5, 9, '["No before and after measurement", "Testimonials used in place of results", "Learner outcomes never tracked", "Buyers ask for proof and nothing exists", "Success claimed on attendance rather than learning"]'::jsonb, '["edtech"]'::jsonb),
  ('EDU-010', 'Teaching Quality Drops as Faculty Grows', 'More teachers are delivering now, and the learner experience varies a lot depending on who they are assigned.', 'Operations & Systems', 'EdTech Teaching Quality', 'external', 3, 6, 9, '["No written teaching standard", "Teachers never observed after hiring", "Learner feedback not linked to individual teachers", "New faculty onboarding is informal", "Experience varies sharply between batches"]'::jsonb, '["edtech"]'::jsonb),
  ('EDU-011', 'Batch and Scheduling Operations Straining', 'Managing many batches, timings and teacher allocations has outgrown the spreadsheet and messaging approach.', 'Operations & Systems', 'EdTech Scheduling at Scale', 'external', 3, 5, 9, '["Scheduling handled in spreadsheets and chat", "Clashes and double bookings happening", "Founder time consumed by scheduling", "No single view of batches and teachers", "Learner rescheduling requests handled manually"]'::jsonb, '["edtech"]'::jsonb),
  ('EDU-012', 'Regulatory and Accreditation Complexity', 'Expanding into certifications, degrees, government schemes or new states brings approval requirements the business is not set up for.', 'Operations & Systems', 'EdTech Compliance', 'external', 3, 6, 10, '["Approval requirements not mapped before launch", "Claims made about certification that cannot be backed", "No compliance owner", "Different rules per state not researched", "Partnerships used to sidestep approvals"]'::jsonb, '["edtech"]'::jsonb),
  ('EDU-013', 'Counselling and Sales Pressure Damaging Trust', 'Aggressive selling or over promising by counsellors is winning enrolments but creating refunds, complaints and reputation damage.', 'Sales & Revenue', 'EdTech Sales Integrity', 'external', 4, 6, 9, '["Refunds and complaints rising with enrolments", "Counsellors promising outcomes that are not guaranteed", "Incentives reward enrolment only", "Negative reviews mentioning sales pressure", "No check on what is said during counselling"]'::jsonb, '["edtech"]'::jsonb),
  ('EDU-014', 'Content Library Ageing and Bloated', 'Years of content have built up, much of it outdated or duplicated, and nobody owns what stays and what goes.', 'Product Development', 'EdTech Content Lifecycle', 'external', 3, 5, 9, '["Large share of content over two years old", "Duplicate lessons covering the same topic", "No owner for the content library", "Outdated material still being sold", "No retirement process for content"]'::jsonb, '["edtech"]'::jsonb),
  ('EDU-015', 'Institutional and B2B Deals Behave Differently', 'Selling to schools, colleges or companies involves long cycles, tender processes and payment terms the consumer playbook does not handle.', 'Sales & Revenue', 'EdTech Institutional Sales', 'external', 4, 5, 9, '["Consumer sales approach used for institutions", "Long payment cycles straining cash", "Tender and procurement steps not understood", "No dedicated institutional process", "Deals stall without anyone knowing why"]'::jsonb, '["edtech"]'::jsonb)
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
         t.primary_stage_group, '["edtech"]'::jsonb, z.v
  FROM (VALUES
  ('RC-EDU-001', 'Learner and Payer Treated as One', 'The person who studies and the person who pays are assumed to be the same.', 'EDU-001', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-EDU-002', 'Buying Decision Maker Unknown', 'Nobody has worked out who actually decides to spend the money.', 'EDU-001', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-EDU-003', 'Pricing Aimed at the Wrong Person', 'The price is built around what the learner can afford, not the actual payer.', 'EDU-001', 'external', 'Strategic', 0.63, 'Stage 0'),
  ('RC-EDU-004', 'Never Spoken to a Real Buyer', 'No parent, employer or institutional buyer has ever been asked directly.', 'EDU-001', 'external', 'Behavioural', 0.65, 'Stage 0'),
  ('RC-EDU-005', 'Message Written for the Learner Only', 'The pitch speaks to the student while the payer hears nothing that matters to them.', 'EDU-001', 'external', 'Strategic', 0.61, 'Stage 0'),
  ('RC-EDU-006', 'Free Alternatives Not Considered', 'No thought given to the free content already teaching the same thing.', 'EDU-002', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-EDU-007', 'No Clear Reason to Pay', 'Nothing explains what the learner gets here that free content does not give.', 'EDU-002', 'external', 'Strategic', 0.68, 'Stage 0'),
  ('RC-EDU-008', 'Price Picked Without Checking the Market', 'The amount was chosen without looking at what people already pay.', 'EDU-002', 'external', 'Knowledge', 0.62, 'Stage 0'),
  ('RC-EDU-009', 'Assuming Quality Alone Justifies Price', 'Belief that better teaching automatically means people will pay.', 'EDU-002', 'external', 'Psychological', 0.61, 'Stage 0'),
  ('RC-EDU-010', 'No Evidence of Past Paid Demand', 'Nobody has shown they paid for anything similar before.', 'EDU-002', 'external', 'Knowledge', 0.64, 'Stage 0'),
  ('RC-EDU-011', 'Assuming Most Learners Will Complete', 'The plan quietly depends on people finishing what they start.', 'EDU-003', 'external', 'Psychological', 0.69, 'Stage 0'),
  ('RC-EDU-012', 'No Plan to Keep Learners Going', 'Nothing has been designed to help someone continue past the first week.', 'EDU-003', 'external', 'Strategic', 0.66, 'Stage 0'),
  ('RC-EDU-013', 'Drop Off Blamed on the Learner', 'Quitting is seen as a learner failure rather than a design problem.', 'EDU-003', 'external', 'Psychological', 0.63, 'Stage 0'),
  ('RC-EDU-014', 'Normal Completion Rates Unknown', 'No idea what completion looks like for similar courses.', 'EDU-003', 'external', 'Knowledge', 0.62, 'Stage 0'),
  ('RC-EDU-015', 'Success Measured by Signups', 'Signups are counted as the win instead of learning or completion.', 'EDU-003', 'external', 'Strategic', 0.64, 'Stage 0'),
  ('RC-EDU-016', 'No One Identified to Create Content', 'It is unclear who will actually make the teaching material.', 'EDU-004', 'external', 'Operational', 0.67, 'Stage 0'),
  ('RC-EDU-017', 'Content Creation Time Underestimated', 'How long it takes to build even one lesson has never been tested.', 'EDU-004', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-EDU-018', 'No Way to Check If Learning Happened', 'Nothing exists to show whether a learner actually improved.', 'EDU-004', 'external', 'Operational', 0.63, 'Stage 0'),
  ('RC-EDU-019', 'Completion Never Measured by Lesson', 'Nobody knows at which lesson learners actually stop.', 'EDU-005', 'external', 'Operational', 0.71, 'Stage 0â†’1'),
  ('RC-EDU-020', 'No Support When a Learner Gets Stuck', 'A learner who hits a hard point has nowhere to turn.', 'EDU-005', 'external', 'Operational', 0.68, 'Stage 0â†’1'),
  ('RC-EDU-021', 'Lessons Too Long for Real Learner Time', 'Content length ignores how much time learners really have.', 'EDU-005', 'external', 'Strategic', 0.65, 'Stage 0â†’1'),
  ('RC-EDU-022', 'No Follow Up When a Learner Goes Quiet', 'Silence from a learner triggers no action at all.', 'EDU-005', 'external', 'Behavioural', 0.66, 'Stage 0â†’1'),
  ('RC-EDU-023', 'Refunds Linked to Not Finishing', 'People ask for money back because they never got through the course.', 'EDU-005', 'external', 'Operational', 0.62, 'Stage 0â†’1'),
  ('RC-EDU-024', 'Free to Paid Conversion Not Measured', 'The share of free users who pay is never calculated.', 'EDU-006', 'external', 'Operational', 0.70, 'Stage 0â†’1'),
  ('RC-EDU-025', 'Free Version Gives Away the Main Value', 'The free tier satisfies the need, so paying adds little.', 'EDU-006', 'external', 'Strategic', 0.69, 'Stage 0â†’1'),
  ('RC-EDU-026', 'No Clear Moment to Ask for Payment', 'There is no defined point where the learner is invited to pay.', 'EDU-006', 'external', 'Strategic', 0.66, 'Stage 0â†’1'),
  ('RC-EDU-027', 'Free Users Never Contacted', 'Nobody reaches out to free users after signup.', 'EDU-006', 'external', 'Behavioural', 0.64, 'Stage 0â†’1'),
  ('RC-EDU-028', 'Demo Class Not Connected to an Offer', 'The demo ends without a clear next step or offer.', 'EDU-006', 'external', 'Operational', 0.63, 'Stage 0â†’1'),
  ('RC-EDU-029', 'All Classes Taught by One Person', 'Delivery sits entirely with one individual.', 'EDU-007', 'external', 'Operational', 0.73, 'Stage 0â†’1'),
  ('RC-EDU-030', 'No Recorded Version of the Course', 'Everything is live, so nothing can run without that person.', 'EDU-007', 'external', 'Operational', 0.69, 'Stage 0â†’1'),
  ('RC-EDU-031', 'Growth Limited by One Calendar', 'How much the business can sell is capped by one persons hours.', 'EDU-007', 'external', 'Strategic', 0.68, 'Stage 0â†’1'),
  ('RC-EDU-032', 'No Second Teacher Trained', 'Nobody else has been prepared to deliver the same programme.', 'EDU-007', 'external', 'Operational', 0.66, 'Stage 0â†’1'),
  ('RC-EDU-033', 'Learners Attached to the Teacher Not the Programme', 'Demand follows the individual rather than the course.', 'EDU-007', 'external', 'Strategic', 0.64, 'Stage 0â†’1'),
  ('RC-EDU-034', 'Time Per Lesson Never Measured', 'How long a lesson really takes to produce has never been recorded.', 'EDU-008', 'external', 'Knowledge', 0.68, 'Stage 0â†’1'),
  ('RC-EDU-035', 'No Content Calendar', 'Production happens reactively with no schedule.', 'EDU-008', 'external', 'Operational', 0.66, 'Stage 0â†’1'),
  ('RC-EDU-036', 'Updates Postponed Indefinitely', 'Refreshing old content keeps slipping behind new content.', 'EDU-008', 'external', 'Behavioural', 0.63, 'Stage 0â†’1'),
  ('RC-EDU-037', 'Quality Dropping to Meet Deadlines', 'Lessons are rushed out to stay on schedule.', 'EDU-008', 'external', 'Operational', 0.62, 'Stage 0â†’1'),
  ('RC-EDU-038', 'No Before and After Measurement', 'Nothing captures where a learner started and where they ended.', 'EDU-009', 'external', 'Operational', 0.71, 'Stage 0â†’1'),
  ('RC-EDU-039', 'Testimonials Used in Place of Results', 'Positive quotes stand in for actual evidence of learning.', 'EDU-009', 'external', 'Behavioural', 0.66, 'Stage 0â†’1'),
  ('RC-EDU-040', 'Learner Outcomes Never Tracked', 'What happened to past learners is unknown.', 'EDU-009', 'external', 'Operational', 0.68, 'Stage 0â†’1'),
  ('RC-EDU-041', 'No Written Teaching Standard', 'There is no agreed definition of what good teaching looks like here.', 'EDU-010', 'external', 'Operational', 0.72, 'Stage 1â†’10+'),
  ('RC-EDU-042', 'Teachers Never Observed After Hiring', 'Nobody watches a class once the teacher is onboarded.', 'EDU-010', 'external', 'Operational', 0.69, 'Stage 1â†’10+'),
  ('RC-EDU-043', 'Feedback Not Linked to Individual Teachers', 'Learner ratings are collected but never traced to who taught.', 'EDU-010', 'external', 'Operational', 0.67, 'Stage 1â†’10+'),
  ('RC-EDU-044', 'Faculty Onboarding Is Informal', 'New teachers learn by watching rather than from a defined process.', 'EDU-010', 'external', 'Operational', 0.65, 'Stage 1â†’10+'),
  ('RC-EDU-045', 'Experience Varies Sharply Between Batches', 'Two learners on the same programme get very different experiences.', 'EDU-010', 'external', 'Operational', 0.64, 'Stage 1â†’10+'),
  ('RC-EDU-046', 'Scheduling Handled in Spreadsheets and Chat', 'Batch and teacher allocation runs on tools that cannot hold the volume.', 'EDU-011', 'external', 'Operational', 0.70, 'Stage 1â†’10+'),
  ('RC-EDU-047', 'Clashes and Double Bookings Happening', 'Errors in allocation are reaching learners and teachers.', 'EDU-011', 'external', 'Operational', 0.67, 'Stage 1â†’10+'),
  ('RC-EDU-048', 'Founder Time Consumed by Scheduling', 'Senior time goes into timetable work instead of the business.', 'EDU-011', 'external', 'Behavioural', 0.66, 'Stage 1â†’10+'),
  ('RC-EDU-049', 'No Single View of Batches and Teachers', 'Information is spread across files and chats with no one source.', 'EDU-011', 'external', 'Operational', 0.65, 'Stage 1â†’10+'),
  ('RC-EDU-050', 'Approval Requirements Not Mapped', 'New offerings launch before anyone checks what approval they need.', 'EDU-012', 'external', 'Knowledge', 0.73, 'Stage 1â†’10+'),
  ('RC-EDU-051', 'Certification Claims Cannot Be Backed', 'What is promised about certificates is stronger than what is actually held.', 'EDU-012', 'external', 'Strategic', 0.70, 'Stage 1â†’10+'),
  ('RC-EDU-052', 'No Compliance Owner', 'Nobody is responsible for keeping approvals current.', 'EDU-012', 'external', 'Operational', 0.67, 'Stage 1â†’10+'),
  ('RC-EDU-053', 'State Level Differences Not Researched', 'Rules that vary by state are assumed to be the same everywhere.', 'EDU-012', 'external', 'Knowledge', 0.65, 'Stage 1â†’10+'),
  ('RC-EDU-054', 'Partnerships Used to Sidestep Approvals', 'Tie ups are used as a workaround rather than a proper route.', 'EDU-012', 'external', 'Strategic', 0.63, 'Stage 1â†’10+'),
  ('RC-EDU-055', 'Refunds and Complaints Rising With Enrolments', 'Growth in signups is matched by growth in dissatisfaction.', 'EDU-013', 'external', 'Operational', 0.71, 'Stage 1â†’10+'),
  ('RC-EDU-056', 'Counsellors Promising Unguaranteed Outcomes', 'Job or score promises are made that the programme cannot ensure.', 'EDU-013', 'external', 'Behavioural', 0.72, 'Stage 1â†’10+'),
  ('RC-EDU-057', 'Incentives Reward Enrolment Only', 'Counsellor pay depends on signing people up, not on them succeeding.', 'EDU-013', 'external', 'Strategic', 0.69, 'Stage 1â†’10+'),
  ('RC-EDU-058', 'No Check on What Is Said in Counselling', 'Nobody reviews or records what is actually promised to a prospect.', 'EDU-013', 'external', 'Operational', 0.66, 'Stage 1â†’10+'),
  ('RC-EDU-059', 'Reviews Mentioning Sales Pressure', 'Public feedback is starting to describe the selling, not the teaching.', 'EDU-013', 'external', 'Operational', 0.64, 'Stage 1â†’10+'),
  ('RC-EDU-060', 'Large Share of Content Over Two Years Old', 'Much of the library has not been reviewed since it was made.', 'EDU-014', 'external', 'Operational', 0.68, 'Stage 1â†’10+'),
  ('RC-EDU-061', 'Duplicate Lessons on the Same Topic', 'The same subject is covered several times in different places.', 'EDU-014', 'external', 'Operational', 0.65, 'Stage 1â†’10+'),
  ('RC-EDU-062', 'No Owner for the Content Library', 'Nobody is responsible for what the library contains overall.', 'EDU-014', 'external', 'Operational', 0.67, 'Stage 1â†’10+'),
  ('RC-EDU-063', 'No Retirement Process for Content', 'Nothing is ever formally removed from the catalogue.', 'EDU-014', 'external', 'Operational', 0.63, 'Stage 1â†’10+'),
  ('RC-EDU-064', 'Consumer Approach Used for Institutions', 'Institutional buyers are sold to as if they were individual learners.', 'EDU-015', 'external', 'Strategic', 0.70, 'Stage 1â†’10+'),
  ('RC-EDU-065', 'Procurement and Tender Steps Not Understood', 'How institutions actually buy has never been learned.', 'EDU-015', 'external', 'Knowledge', 0.68, 'Stage 1â†’10+'),
  ('RC-EDU-066', 'Long Payment Cycles Straining Cash', 'Institutional payment terms are much slower than the business is built for.', 'EDU-015', 'external', 'Operational', 0.66, 'Stage 1â†’10+')
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
         '["edtech"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-EDU-001', 'Who will actually pay for this, the learner or someone else like a parent or employer?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-001', 'RC-EDU-001', 1, 'Stage 0'),
  ('S0-EDU-002', 'Who makes the final decision to spend the money?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-001', 'RC-EDU-002', 1, 'Stage 0'),
  ('S0-EDU-003', 'Is your price built around what the learner can afford or what the payer can afford?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-001', 'RC-EDU-003', 2, 'Stage 0'),
  ('S0-EDU-004', 'Have you spoken to a real parent, employer or buyer about this yet?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-001', 'RC-EDU-004', 1, 'Stage 0'),
  ('S0-EDU-005', 'If a parent is paying, what would convince them, not the student?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-001', 'RC-EDU-005', 2, 'Stage 0'),
  ('S0-EDU-006', 'Plenty of free videos already teach this. Why would someone pay you instead?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-002', 'RC-EDU-006', 1, 'Stage 0'),
  ('S0-EDU-007', 'What does a learner get from you that they cannot get free online?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-002', 'RC-EDU-007', 2, 'Stage 0'),
  ('S0-EDU-008', 'How did you decide your price? Did you check what people pay today?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-002', 'RC-EDU-008', 2, 'Stage 0'),
  ('S0-EDU-009', 'Do you believe better teaching alone is enough for people to pay?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-002', 'RC-EDU-009', 2, 'Stage 0'),
  ('S0-EDU-010', 'Do you know anyone who has already paid money for something like this?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-002', 'RC-EDU-010', 1, 'Stage 0'),
  ('S0-EDU-011', 'Out of 10 people who start your course, how many do you think will finish?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-003', 'RC-EDU-011', 1, 'Stage 0'),
  ('S0-EDU-012', 'What will you do to help someone keep going after the first week?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-003', 'RC-EDU-012', 2, 'Stage 0'),
  ('S0-EDU-013', 'If a learner quits halfway, is that their problem or yours?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-003', 'RC-EDU-013', 2, 'Stage 0'),
  ('S0-EDU-014', 'Who is going to create the actual teaching content, and how long will that take?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-004', 'RC-EDU-016', 1, 'Stage 0'),
  ('S0-EDU-015', 'How will you know a learner actually learned something?', 'open_text', 'Idea & Validation', 'CORE', 'EDU-004', 'RC-EDU-018', 1, 'Stage 0'),
  ('S01-EDU-001', 'Out of everyone who enrolled last month, how many actually finished?', 'open_text', 'Product Development', 'CORE', 'EDU-005', 'RC-EDU-019', 2, 'Stage 0â†’1'),
  ('S01-EDU-002', 'At which lesson do most learners stop?', 'open_text', 'Product Development', 'CORE', 'EDU-005', 'RC-EDU-019', 2, 'Stage 0â†’1'),
  ('S01-EDU-003', 'What happens when a learner gets stuck on something?', 'open_text', 'Product Development', 'CORE', 'EDU-005', 'RC-EDU-020', 2, 'Stage 0â†’1'),
  ('S01-EDU-004', 'How long is one lesson, and how much time does your learner really have?', 'open_text', 'Product Development', 'CORE', 'EDU-005', 'RC-EDU-021', 2, 'Stage 0â†’1'),
  ('S01-EDU-005', 'If a learner goes quiet for two weeks, does anyone notice or reach out?', 'open_text', 'Product Development', 'CORE', 'EDU-005', 'RC-EDU-022', 2, 'Stage 0â†’1'),
  ('S01-EDU-006', 'How many refund requests did you get last month, and why?', 'open_text', 'Product Development', 'CORE', 'EDU-005', 'RC-EDU-023', 2, 'Stage 0â†’1'),
  ('S01-EDU-007', 'What share of your free users end up paying?', 'open_text', 'Sales & Revenue', 'CORE', 'EDU-006', 'RC-EDU-024', 2, 'Stage 0â†’1'),
  ('S01-EDU-008', 'Does your free version already solve the problem, or does it leave a real reason to pay?', 'open_text', 'Sales & Revenue', 'CORE', 'EDU-006', 'RC-EDU-025', 3, 'Stage 0â†’1'),
  ('S01-EDU-009', 'At what exact point is a free user asked to pay?', 'open_text', 'Sales & Revenue', 'CORE', 'EDU-006', 'RC-EDU-026', 2, 'Stage 0â†’1'),
  ('S01-EDU-010', 'After someone signs up free, does anyone contact them?', 'open_text', 'Sales & Revenue', 'CORE', 'EDU-006', 'RC-EDU-027', 2, 'Stage 0â†’1'),
  ('S01-EDU-011', 'What happens at the end of a demo class?', 'open_text', 'Sales & Revenue', 'CORE', 'EDU-006', 'RC-EDU-028', 2, 'Stage 0â†’1'),
  ('S01-EDU-012', 'If you were unwell for two weeks, would classes still run?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-007', 'RC-EDU-029', 2, 'Stage 0â†’1'),
  ('S01-EDU-013', 'Is any part of your course recorded, or is everything live?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-007', 'RC-EDU-030', 2, 'Stage 0â†’1'),
  ('S01-EDU-014', 'How many more learners could you take on without adding hours to your week?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-007', 'RC-EDU-031', 3, 'Stage 0â†’1'),
  ('S01-EDU-015', 'Has anyone else been trained to teach your programme?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-007', 'RC-EDU-032', 2, 'Stage 0â†’1'),
  ('S01-EDU-016', 'Do learners come for your course, or specifically for you?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-007', 'RC-EDU-033', 3, 'Stage 0â†’1'),
  ('S01-EDU-017', 'How many hours does one lesson take to make, start to finish?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-008', 'RC-EDU-034', 2, 'Stage 0â†’1'),
  ('S01-EDU-018', 'Do you have a content calendar, or is content made when there is time?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-008', 'RC-EDU-035', 2, 'Stage 0â†’1'),
  ('S01-EDU-019', 'When did you last update an older lesson?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-008', 'RC-EDU-036', 2, 'Stage 0â†’1'),
  ('S01-EDU-020', 'Can you show a buyer any proof that your learners actually improved?', 'open_text', 'Sales & Revenue', 'CORE', 'EDU-009', 'RC-EDU-038', 2, 'Stage 0â†’1'),
  ('S10-EDU-001', 'Does a learner get the same quality whichever teacher they are assigned?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-010', 'RC-EDU-041', 2, 'Stage 1â†’10+'),
  ('S10-EDU-002', 'When did you last sit in on one of your teachers classes?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-010', 'RC-EDU-042', 2, 'Stage 1â†’10+'),
  ('S10-EDU-003', 'How do you know if one of your teachers is underperforming?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-010', 'RC-EDU-043', 2, 'Stage 1â†’10+'),
  ('S10-EDU-004', 'What does a new teacher go through before their first class?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-010', 'RC-EDU-044', 2, 'Stage 1â†’10+'),
  ('S10-EDU-005', 'Would two learners in different batches describe the same experience?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-010', 'RC-EDU-045', 3, 'Stage 1â†’10+'),
  ('S10-EDU-006', 'How much of your week goes into scheduling batches and teachers?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-011', 'RC-EDU-048', 2, 'Stage 1â†’10+'),
  ('S10-EDU-007', 'Where does your batch and teacher schedule actually live?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-011', 'RC-EDU-046', 2, 'Stage 1â†’10+'),
  ('S10-EDU-008', 'When did you last have a clash or double booking?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-011', 'RC-EDU-047', 2, 'Stage 1â†’10+'),
  ('S10-EDU-009', 'Can you see all batches and teacher availability in one place?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-011', 'RC-EDU-049', 2, 'Stage 1â†’10+'),
  ('S10-EDU-010', 'Do you know what approvals you need before offering this in a new state or as a certification?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-012', 'RC-EDU-050', 3, 'Stage 1â†’10+'),
  ('S10-EDU-011', 'Can you back up everything you claim about your certificates?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-012', 'RC-EDU-051', 3, 'Stage 1â†’10+'),
  ('S10-EDU-012', 'Who in your team is responsible for keeping approvals current?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-012', 'RC-EDU-052', 2, 'Stage 1â†’10+'),
  ('S10-EDU-013', 'Have you checked whether the rules differ in the states you operate in?', 'open_text', 'Operations & Systems', 'CORE', 'EDU-012', 'RC-EDU-053', 2, 'Stage 1â†’10+'),
  ('S10-EDU-014', 'What percentage of enrolments end in a refund or complaint, and why?', 'open_text', 'Sales & Revenue', 'CORE', 'EDU-013', 'RC-EDU-055', 2, 'Stage 1â†’10+'),
  ('S10-EDU-015', 'What exactly do your counsellors promise a prospect about outcomes?', 'open_text', 'Sales & Revenue', 'CORE', 'EDU-013', 'RC-EDU-056', 3, 'Stage 1â†’10+'),
  ('S10-EDU-016', 'Are your counsellors paid for enrolments only, or also for learners who succeed?', 'open_text', 'Sales & Revenue', 'CORE', 'EDU-013', 'RC-EDU-057', 3, 'Stage 1â†’10+'),
  ('S10-EDU-017', 'Does anyone review what is actually said during a counselling call?', 'open_text', 'Sales & Revenue', 'CORE', 'EDU-013', 'RC-EDU-058', 2, 'Stage 1â†’10+'),
  ('S10-EDU-018', 'What do your recent public reviews talk about most?', 'open_text', 'Sales & Revenue', 'CORE', 'EDU-013', 'RC-EDU-059', 2, 'Stage 1â†’10+'),
  ('S10-EDU-019', 'How much of your content library is more than two years old?', 'open_text', 'Product Development', 'CORE', 'EDU-014', 'RC-EDU-060', 2, 'Stage 1â†’10+'),
  ('S10-EDU-020', 'Do you have several lessons covering the same topic in different places?', 'open_text', 'Product Development', 'CORE', 'EDU-014', 'RC-EDU-061', 2, 'Stage 1â†’10+'),
  ('S10-EDU-021', 'Who owns the content library as a whole?', 'open_text', 'Product Development', 'CORE', 'EDU-014', 'RC-EDU-062', 2, 'Stage 1â†’10+'),
  ('S10-EDU-022', 'Has anything ever been removed from your catalogue?', 'open_text', 'Product Development', 'CORE', 'EDU-014', 'RC-EDU-063', 2, 'Stage 1â†’10+'),
  ('S10-EDU-023', 'Do you sell to schools and companies the same way you sell to individuals?', 'open_text', 'Sales & Revenue', 'CORE', 'EDU-015', 'RC-EDU-064', 2, 'Stage 1â†’10+'),
  ('S10-EDU-024', 'How long does an institutional deal take from first meeting to payment?', 'open_text', 'Sales & Revenue', 'CORE', 'EDU-015', 'RC-EDU-065', 3, 'Stage 1â†’10+'),
  ('S10-EDU-025', 'How do institutional payment terms affect your cash each month?', 'open_text', 'Financial Management', 'CORE', 'EDU-015', 'RC-EDU-066', 3, 'Stage 1â†’10+')
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
  ('S0-EDU-001', 'icp'),
  ('S0-EDU-002', 'icp'),
  ('S0-EDU-003', 'icp'),
  ('S0-EDU-004', 'icp'),
  ('S0-EDU-005', 'icp'),
  ('S0-EDU-006', 'willingness-to-pay'),
  ('S0-EDU-007', 'willingness-to-pay'),
  ('S0-EDU-008', 'willingness-to-pay'),
  ('S0-EDU-009', 'willingness-to-pay'),
  ('S0-EDU-010', 'willingness-to-pay'),
  ('S0-EDU-011', 'problem-clarity'),
  ('S0-EDU-012', 'problem-clarity'),
  ('S0-EDU-013', 'problem-clarity'),
  ('S0-EDU-014', 'problem-clarity'),
  ('S0-EDU-015', 'problem-clarity'),
  ('S01-EDU-001', 'technical-quality'),
  ('S01-EDU-002', 'technical-quality'),
  ('S01-EDU-003', 'technical-quality'),
  ('S01-EDU-004', 'technical-quality'),
  ('S01-EDU-005', 'technical-quality'),
  ('S01-EDU-006', 'technical-quality'),
  ('S01-EDU-007', 'willingness-to-pay'),
  ('S01-EDU-008', 'willingness-to-pay'),
  ('S01-EDU-009', 'willingness-to-pay'),
  ('S01-EDU-010', 'willingness-to-pay'),
  ('S01-EDU-011', 'willingness-to-pay'),
  ('S01-EDU-012', 'problem-clarity'),
  ('S01-EDU-013', 'problem-clarity'),
  ('S01-EDU-014', 'problem-clarity'),
  ('S01-EDU-015', 'problem-clarity'),
  ('S01-EDU-016', 'problem-clarity'),
  ('S01-EDU-017', 'problem-clarity'),
  ('S01-EDU-018', 'problem-clarity'),
  ('S01-EDU-019', 'problem-clarity'),
  ('S01-EDU-020', 'willingness-to-pay'),
  ('S10-EDU-001', 'technical-quality'),
  ('S10-EDU-002', 'technical-quality'),
  ('S10-EDU-003', 'technical-quality'),
  ('S10-EDU-004', 'technical-quality'),
  ('S10-EDU-005', 'technical-quality'),
  ('S10-EDU-006', 'technical-quality'),
  ('S10-EDU-007', 'technical-quality'),
  ('S10-EDU-008', 'technical-quality'),
  ('S10-EDU-009', 'technical-quality'),
  ('S10-EDU-010', 'problem-clarity'),
  ('S10-EDU-011', 'problem-clarity'),
  ('S10-EDU-012', 'problem-clarity'),
  ('S10-EDU-013', 'problem-clarity'),
  ('S10-EDU-014', 'willingness-to-pay'),
  ('S10-EDU-015', 'willingness-to-pay'),
  ('S10-EDU-016', 'willingness-to-pay'),
  ('S10-EDU-017', 'willingness-to-pay'),
  ('S10-EDU-018', 'willingness-to-pay'),
  ('S10-EDU-019', 'technical-quality'),
  ('S10-EDU-020', 'technical-quality'),
  ('S10-EDU-021', 'technical-quality'),
  ('S10-EDU-022', 'technical-quality'),
  ('S10-EDU-023', 'willingness-to-pay'),
  ('S10-EDU-024', 'willingness-to-pay'),
  ('S10-EDU-025', 'willingness-to-pay')
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
         '["edtech"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-EDU-001', 'Ideation â€” EdTech Buyer Clarity', 'EDU-001', '["RC-EDU-001", "RC-EDU-002"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Write two separate lines, one for who learns and one for who pays.", "Name the person who actually decides to spend the money.", "If they are different, write what each one cares about."]'::jsonb, '[{"name": "Learner and Payer Split", "brief": "Separating the person who studies from the person who pays before designing anything."}]'::jsonb),
  ('INT-EDU-002', 'Ideation â€” EdTech Buyer Clarity', 'EDU-001', '["RC-EDU-004", "RC-EDU-005"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Talk to 5 real parents, employers or buyers, not learners.", "Ask what would make them say yes to paying.", "Rewrite your pitch so it speaks to them."]'::jsonb, '[{"name": "Talk to the Payer", "brief": "Getting the buying view from the person who actually pays."}]'::jsonb),
  ('INT-EDU-003', 'Ideation â€” EdTech Buyer Clarity', 'EDU-001', '["RC-EDU-003"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Check what the payer already spends on similar learning.", "Set your price against that, not against learner pocket money.", "Write down why that price is fair to them."]'::jsonb, '[{"name": "Price to the Payer", "brief": "Setting price against the real payers spending, not the learners."}]'::jsonb),
  ('INT-EDU-004', 'Ideation â€” EdTech Willingness to Pay', 'EDU-002', '["RC-EDU-006", "RC-EDU-007"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Find the best free version of what you plan to teach.", "Watch it and list what is missing or frustrating.", "Write one line on what you give that it does not."]'::jsonb, '[{"name": "Free Alternative Audit", "brief": "Studying the free content already teaching the same thing."}]'::jsonb),
  ('INT-EDU-005', 'Ideation â€” EdTech Willingness to Pay', 'EDU-002', '["RC-EDU-008", "RC-EDU-010"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Find what people already pay for similar courses.", "Ask 5 people if they have ever paid for learning like this.", "Set your price only after both answers."]'::jsonb, '[{"name": "Existing Spend Check", "brief": "Grounding price in what people already pay for similar learning."}]'::jsonb),
  ('INT-EDU-006', 'Ideation â€” EdTech Willingness to Pay', 'EDU-002', '["RC-EDU-009"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Write down why someone would pay, beyond it being good.", "Test that sentence on someone outside your circle.", "If it does not land, the reason is not strong enough yet."]'::jsonb, '[{"name": "Reason to Pay Statement", "brief": "Naming a reason to pay that goes beyond teaching quality."}]'::jsonb),
  ('INT-EDU-007', 'Ideation â€” EdTech Completion Reality', 'EDU-003', '["RC-EDU-011", "RC-EDU-014"]'::jsonb, '[1]'::jsonb, 'Product Design', '["Find out what completion rates look like for courses like yours.", "Assume yours will be similar, not better.", "Plan your business on that number."]'::jsonb, '[{"name": "Realistic Completion Assumption", "brief": "Planning on normal completion rates instead of hopeful ones."}]'::jsonb),
  ('INT-EDU-008', 'Ideation â€” EdTech Completion Reality', 'EDU-003', '["RC-EDU-012", "RC-EDU-013", "RC-EDU-015"]'::jsonb, '[1]'::jsonb, 'Product Design', '["Design one thing that helps a learner get past week one.", "Decide to measure completion, not just signups.", "Treat drop off as something for you to fix."]'::jsonb, '[{"name": "Design for Week One", "brief": "Building one deliberate step to keep learners going early on."}]'::jsonb),
  ('INT-EDU-009', 'Ideation â€” EdTech Content Basics', 'EDU-004', '["RC-EDU-016", "RC-EDU-017"]'::jsonb, '[1]'::jsonb, 'Operations', '["Make one small piece of content yourself.", "Time exactly how long it took start to finish.", "Multiply that by your planned course size."]'::jsonb, '[{"name": "One Lesson Time Test", "brief": "Measuring the real time cost of content by making one piece first."}]'::jsonb),
  ('INT-EDU-010', 'Ideation â€” EdTech Content Basics', 'EDU-004', '["RC-EDU-018"]'::jsonb, '[1]'::jsonb, 'Product Design', '["Pick one simple way to check if a learner improved.", "It can be a short test before and after.", "Write it down before you build the course."]'::jsonb, '[{"name": "Before and After Check", "brief": "One simple measure of whether learning actually happened."}]'::jsonb),
  ('INT-EDU-011', 'Validation to Traction â€” EdTech Completion', 'EDU-005', '["RC-EDU-019", "RC-EDU-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["Count how many learners reach each lesson.", "Find the exact lesson where most stop.", "Fix that one lesson before touching anything else."]'::jsonb, '[{"name": "Lesson Level Drop Off", "brief": "Measuring completion lesson by lesson to find the real break point."}]'::jsonb),
  ('INT-EDU-012', 'Validation to Traction â€” EdTech Completion', 'EDU-005', '["RC-EDU-020", "RC-EDU-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["Set a rule for when a quiet learner gets a message.", "Have one real person send it, not an automated blast.", "Track how many come back after that message."]'::jsonb, '[{"name": "Quiet Learner Check In", "brief": "One human follow up when a learner stops showing up."}]'::jsonb),
  ('INT-EDU-013', 'Validation to Traction â€” EdTech Completion', 'EDU-005', '["RC-EDU-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["Ask 10 learners how much time they really have per session.", "Cut your lessons to fit that.", "Check whether completion improves over the next month."]'::jsonb, '[{"name": "Fit the Lesson to the Learner", "brief": "Sizing content to the time learners actually have."}]'::jsonb),
  ('INT-EDU-014', 'Validation to Traction â€” EdTech Conversion', 'EDU-006', '["RC-EDU-024", "RC-EDU-026"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Calculate what share of free users paid last month.", "Pick one clear moment where the paid offer appears.", "Measure the same number again after 30 days."]'::jsonb, '[{"name": "Free to Paid Baseline", "brief": "Measuring conversion and defining one clear moment to ask for payment."}]'::jsonb),
  ('INT-EDU-015', 'Validation to Traction â€” EdTech Conversion', 'EDU-006', '["RC-EDU-025"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["List what the free version gives away.", "Move the most valuable part behind the paid line.", "Keep enough free to prove it works."]'::jsonb, '[{"name": "Free Tier Boundary", "brief": "Deciding what stays free so paying still has a real reason."}]'::jsonb),
  ('INT-EDU-016', 'Validation to Traction â€” EdTech Conversion', 'EDU-006', '["RC-EDU-027", "RC-EDU-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Send one message to every free user within 48 hours.", "End every demo class with one clear next step.", "Track how many take it."]'::jsonb, '[{"name": "Follow the Free User", "brief": "Contacting free signups and closing every demo with a clear offer."}]'::jsonb),
  ('INT-EDU-017', 'Validation to Traction â€” EdTech Delivery Dependency', 'EDU-007', '["RC-EDU-029", "RC-EDU-030"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Record one full course end to end.", "Run one batch using the recording plus light support.", "Compare results against your live batch."]'::jsonb, '[{"name": "Record One Course", "brief": "Creating a version of the programme that runs without live delivery."}]'::jsonb),
  ('INT-EDU-018', 'Validation to Traction â€” EdTech Delivery Dependency', 'EDU-007', '["RC-EDU-031", "RC-EDU-032", "RC-EDU-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Write down how you teach, step by step.", "Train one other person to deliver from it.", "Let them run one small batch and review it."]'::jsonb, '[{"name": "Train a Second Teacher", "brief": "Documenting the teaching method so someone else can deliver it."}]'::jsonb),
  ('INT-EDU-019', 'Validation to Traction â€” EdTech Content Pipeline', 'EDU-008', '["RC-EDU-034", "RC-EDU-035"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Time one lesson from script to published.", "Use that number to build a realistic content calendar.", "Plan only what the calendar can actually hold."]'::jsonb, '[{"name": "Real Content Calendar", "brief": "Building a schedule from measured production time, not hope."}]'::jsonb),
  ('INT-EDU-020', 'Validation to Traction â€” EdTech Content Pipeline', 'EDU-008', '["RC-EDU-036", "RC-EDU-037"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Set one fixed slot each month for updating old lessons.", "Protect it even when new content is late.", "Keep a list of what needs refreshing."]'::jsonb, '[{"name": "Update Slot", "brief": "A protected monthly slot so old content does not rot."}]'::jsonb),
  ('INT-EDU-021', 'Validation to Traction â€” EdTech Outcome Evidence', 'EDU-009', '["RC-EDU-038", "RC-EDU-040"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["Give a short test before the course and the same one after.", "Record both scores for every learner.", "Report the average improvement honestly."]'::jsonb, '[{"name": "Before and After Test", "brief": "Simple paired testing that produces real evidence of learning."}]'::jsonb),
  ('INT-EDU-022', 'Validation to Traction â€” EdTech Outcome Evidence', 'EDU-009', '["RC-EDU-039"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Pick 5 past learners and find out what actually changed for them.", "Write one honest result line per learner.", "Use those alongside testimonials, not instead of evidence."]'::jsonb, '[{"name": "Real Outcome Stories", "brief": "Following up past learners for concrete results rather than praise."}]'::jsonb),
  ('INT-EDU-023', 'Growth to Maturity â€” EdTech Teaching Quality', 'EDU-010', '["RC-EDU-041", "RC-EDU-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write one page describing what a good class looks like here.", "Share it with every teacher.", "Use it as the basis for every review."]'::jsonb, '[{"name": "One Page Teaching Standard", "brief": "A written definition of good teaching every faculty member works to."}]'::jsonb),
  ('INT-EDU-024', 'Growth to Maturity â€” EdTech Teaching Quality', 'EDU-010', '["RC-EDU-042", "RC-EDU-043"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Sit in on one class per teacher each quarter.", "Link learner feedback to the teacher who taught it.", "Review both together every month."]'::jsonb, '[{"name": "Observe and Attribute", "brief": "Classroom observation plus feedback tied to individual teachers."}]'::jsonb),
  ('INT-EDU-025', 'Growth to Maturity â€” EdTech Teaching Quality', 'EDU-010', '["RC-EDU-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write the steps a new teacher goes through before teaching.", "Include one observed practice class.", "Use it for every new hire."]'::jsonb, '[{"name": "Faculty Onboarding Path", "brief": "A defined route from hire to first class for every new teacher."}]'::jsonb),
  ('INT-EDU-026', 'Growth to Maturity â€” EdTech Scheduling at Scale', 'EDU-011', '["RC-EDU-046", "RC-EDU-049"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Move batches, teachers and timings into one system.", "Make it the only place the schedule lives.", "Give the team access so it does not route through you."]'::jsonb, '[{"name": "One Scheduling System", "brief": "A single source of truth for batches, teachers and timings."}]'::jsonb),
  ('INT-EDU-027', 'Growth to Maturity â€” EdTech Scheduling at Scale', 'EDU-011', '["RC-EDU-047", "RC-EDU-048"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Hand scheduling to one named person.", "Track clashes and reschedules each week.", "Review the number, not the individual bookings."]'::jsonb, '[{"name": "Scheduling Handover", "brief": "Moving timetable work off the founder and measuring errors instead."}]'::jsonb),
  ('INT-EDU-028', 'Growth to Maturity â€” EdTech Compliance', 'EDU-012', '["RC-EDU-050", "RC-EDU-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["List every approval needed for each offering and state.", "Check it before any new launch, not after.", "Keep the list updated as you expand."]'::jsonb, '[{"name": "Approval Map Before Launch", "brief": "Mapping required approvals per offering and per state ahead of launch."}]'::jsonb),
  ('INT-EDU-029', 'Growth to Maturity â€” EdTech Compliance', 'EDU-012', '["RC-EDU-051", "RC-EDU-052", "RC-EDU-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Check every certificate claim against what you actually hold.", "Remove or correct anything you cannot back.", "Name one person responsible for keeping approvals current."]'::jsonb, '[{"name": "Claim and Approval Audit", "brief": "Matching public certification claims to what is genuinely held."}]'::jsonb),
  ('INT-EDU-030', 'Growth to Maturity â€” EdTech Sales Integrity', 'EDU-013', '["RC-EDU-055", "RC-EDU-058", "RC-EDU-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Track refunds and complaints by counsellor.", "Listen to or review a sample of counselling calls each month.", "Act on the pattern, not one bad call."]'::jsonb, '[{"name": "Counselling Quality Check", "brief": "Reviewing what is actually promised and tracking the fallout by counsellor."}]'::jsonb),
  ('INT-EDU-031', 'Growth to Maturity â€” EdTech Sales Integrity', 'EDU-013', '["RC-EDU-056", "RC-EDU-057"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Write down what may and may not be promised.", "Tie part of counsellor pay to learners who stay and complete.", "Remove incentives that reward enrolment alone."]'::jsonb, '[{"name": "Promise Rules and Aligned Incentives", "brief": "Limiting outcome promises and paying for learner success, not just signups."}]'::jsonb),
  ('INT-EDU-032', 'Growth to Maturity â€” EdTech Content Lifecycle', 'EDU-014', '["RC-EDU-060", "RC-EDU-061"]'::jsonb, '[5, 6, 7]'::jsonb, 'Product Design', '["List every lesson with its last update date.", "Mark duplicates and anything over two years old.", "Fix or retire the worst offenders first."]'::jsonb, '[{"name": "Content Library Audit", "brief": "A full inventory of the library by age and duplication."}]'::jsonb),
  ('INT-EDU-033', 'Growth to Maturity â€” EdTech Content Lifecycle', 'EDU-014', '["RC-EDU-062", "RC-EDU-063"]'::jsonb, '[5, 6, 7]'::jsonb, 'Product Design', '["Name one owner for the content library.", "Write a rule for when a lesson gets retired.", "Review the catalogue against it every quarter."]'::jsonb, '[{"name": "Library Owner and Retirement Rule", "brief": "One accountable owner and a standing rule for removing old content."}]'::jsonb),
  ('INT-EDU-034', 'Growth to Maturity â€” EdTech Institutional Sales', 'EDU-015', '["RC-EDU-064", "RC-EDU-065", "RC-EDU-066"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Write a separate process for institutional deals, with stages and timelines.", "Learn how your target institutions actually procure.", "Set payment terms your cash flow can survive, and plan for the gap."]'::jsonb, '[{"name": "Institutional Sales Process", "brief": "A distinct process, timeline and payment plan for institutional buyers."}]'::jsonb)
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
  (SELECT COUNT(*) FROM new_interventions) AS interventions_inserted;-- expect 34"""),

        ('Energy, CleanTech & Renewables', 'cleantech_energy', 'ENR', r"""WITH z AS (
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
  ('ENR-001', 'No Idea How Much Money This Really Needs', 'Energy projects need far more upfront money than most other businesses, and the founder has not grasped the scale of it.', 'Idea & Validation', 'CleanTech Capital Reality', 'external', 4, 5, 9, '["No cost estimate for one installation or unit", "Comparing this to a small services business", "No idea how long before first revenue", "Assuming a subsidy will cover the gap", "Equipment and installation costs not separated"]'::jsonb, '["cleantech_energy"]'::jsonb),
  ('ENR-002', 'Government Rules and Approvals Not Understood', 'This sector runs on permissions, tariffs and government schemes, and the founder does not yet know any of that applies.', 'Idea & Validation', 'CleanTech Regulatory Basics', 'external', 3, 5, 9, '["No idea which authority gives permission", "Assuming no approval is needed to start", "Scheme or subsidy assumed without checking it is open", "Tariff and metering rules unknown", "State level differences not considered"]'::jsonb, '["cleantech_energy"]'::jsonb),
  ('ENR-003', 'Customer Pays Later While You Pay Now', 'Energy savings pay back over years while costs land upfront, and the founder has not thought about who carries that gap.', 'Idea & Validation', 'CleanTech Payback Gap', 'external', 4, 5, 9, '["Equipment cost falls on the founder upfront", "Customer benefit spread over years", "No plan for financing the gap", "Assuming customers will pay full cost in advance", "Payback period never calculated"]'::jsonb, '["cleantech_energy"]'::jsonb),
  ('ENR-004', 'Unclear Who Actually Buys This', 'Homes, businesses, factories and government buy energy very differently, and no single customer type has been chosen.', 'Idea & Validation', 'CleanTech Customer Clarity', 'external', 2, 4, 8, '["Target customer described as everyone", "No single segment chosen to start with", "Same pitch used for homes and factories", "Buying process differences not understood", "No conversation yet with a real buyer"]'::jsonb, '["cleantech_energy"]'::jsonb),
  ('ENR-005', 'Projects Cost More and Take Longer Than Quoted', 'Early installations overrun on both time and money, and the difference is absorbed as a loss.', 'Operations & Systems', 'CleanTech Project Delivery', 'external', 3, 6, 9, '["Final project cost higher than the quote", "No site survey before quoting", "Approval delays not built into the timeline", "Scope changes accepted without repricing", "Quoted versus actual never compared"]'::jsonb, '["cleantech_energy"]'::jsonb),
  ('ENR-006', 'Subsidy and Government Payments Arrive Late', 'Money counted on from schemes or government buyers arrives months late, straining cash badly.', 'Financial Management', 'CleanTech Receivables Risk', 'external', 4, 6, 9, '["Cash plan assumes subsidy arrives on time", "Government payments months overdue", "No buffer for delayed receivables", "Paying suppliers before being paid", "Follow up on claims handled ad hoc"]'::jsonb, '["cleantech_energy"]'::jsonb),
  ('ENR-007', 'No Service and Maintenance Plan', 'Equipment is installed and then forgotten, so failures have no process behind them and servicing earns nothing.', 'Operations & Systems', 'CleanTech After Installation', 'external', 3, 5, 9, '["No maintenance contract offered", "No process when installed equipment fails", "No revenue after the installation", "Customers calling the founder directly for repairs", "No record of what was installed where"]'::jsonb, '["cleantech_energy"]'::jsonb),
  ('ENR-008', 'Customer Financing Not Arranged', 'Buyers want the product but cannot pay upfront, and no lender, EMI or lease route has been set up.', 'Sales & Revenue', 'CleanTech Customer Financing', 'external', 4, 5, 9, '["Deals lost because customer cannot pay upfront", "No lender or financing partner in place", "No EMI or lease option offered", "Founder funding customer purchases personally", "Payment terms decided deal by deal"]'::jsonb, '["cleantech_energy"]'::jsonb),
  ('ENR-009', 'One Site Does Not Make the Next One Easier', 'Every installation is treated as a one off, so nothing learned carries forward into faster or cheaper delivery.', 'Operations & Systems', 'CleanTech Repeatability', 'external', 3, 5, 9, '["No standard installation checklist", "Each site planned from scratch", "Lessons from past sites not recorded", "Second installation no faster than the first", "Different teams doing the same job differently"]'::jsonb, '["cleantech_energy"]'::jsonb),
  ('ENR-010', 'Working Capital Cannot Keep Up With the Order Book', 'Orders are growing but every project ties up cash upfront, so growth itself is squeezing the business.', 'Financial Management', 'CleanTech Working Capital', 'external', 4, 7, 10, '["Cash tied up per project never measured", "Orders accepted without checking funding capacity", "No working capital facility arranged", "Payment milestones loaded towards the end", "Growth increasing cash strain rather than easing it"]'::jsonb, '["cleantech_energy"]'::jsonb),
  ('ENR-011', 'Installed Base Outgrowing Service Capacity', 'Hundreds of sites are now live and servicing them is overwhelming the team.', 'Operations & Systems', 'CleanTech Service at Scale', 'external', 3, 6, 9, '["Live site count far ahead of service team size", "Service requests queuing up", "No regional service coverage", "Maintenance visits missed or delayed", "Complaints rising with installed base"]'::jsonb, '["cleantech_energy"]'::jsonb),
  ('ENR-012', 'Performance Guarantees and Warranty Exposure', 'Promises about generation, savings or uptime were made across many sites with no system to track whether they are being met.', 'Operations & Systems', 'CleanTech Performance Risk', 'external', 3, 6, 10, '["Output or savings guarantees given in contracts", "Actual performance not monitored per site", "No early warning when a site underperforms", "Warranty claims handled case by case", "Financial exposure from guarantees unknown"]'::jsonb, '["cleantech_energy"]'::jsonb),
  ('ENR-013', 'Policy and Tariff Changes Can Wipe Out the Model', 'Business economics depend on rules such as net metering, tariffs and subsidies that governments can change with little notice.', 'Strategy & Planning', 'CleanTech Policy Risk', 'external', 2, 7, 10, '["Model depends on current tariff or metering rules", "No scenario planned for a policy change", "Subsidy dependence never reduced", "Policy news not tracked systematically", "No pricing flexibility if rules shift"]'::jsonb, '["cleantech_energy"]'::jsonb),
  ('ENR-014', 'Multi State Expansion Resets Everything', 'Each new state brings different approvals, discoms, tariffs and local partners, and expansion is being treated as a copy paste.', 'Operations & Systems', 'CleanTech State Expansion', 'external', 3, 6, 9, '["Same playbook applied to every state", "Discom and approval differences discovered late", "No local partner in new states", "Timelines in new states far longer than planned", "Costs in new states higher than modelled"]'::jsonb, '["cleantech_energy"]'::jsonb),
  ('ENR-015', 'Project Concentration in Few Large Clients', 'A large share of revenue depends on a small number of big customers or government contracts.', 'Sales & Revenue', 'CleanTech Client Concentration', 'external', 4, 6, 10, '["Most revenue from two or three clients", "Losing one client would threaten the business", "Terms dictated by the large buyer", "No pipeline of smaller customers", "Payment delays from one client affect everything"]'::jsonb, '["cleantech_energy"]'::jsonb)
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
         t.primary_stage_group, '["cleantech_energy"]'::jsonb, z.v
  FROM (VALUES
  ('RC-ENR-001', 'No Cost Estimate for One Installation', 'Nobody has priced out what a single complete installation would cost.', 'ENR-001', 'external', 'Knowledge', 0.70, 'Stage 0'),
  ('RC-ENR-002', 'Compared to a Small Services Business', 'Capital needs are judged against a business that needs almost none.', 'ENR-001', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-ENR-003', 'Time to First Revenue Unknown', 'How many months pass before any money comes in has never been worked out.', 'ENR-001', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-ENR-004', 'Assuming a Subsidy Will Cover the Gap', 'The plan quietly depends on government money arriving.', 'ENR-001', 'external', 'Psychological', 0.64, 'Stage 0'),
  ('RC-ENR-005', 'Equipment and Installation Costs Not Separated', 'Hardware, labour and site work are treated as one vague number.', 'ENR-001', 'external', 'Knowledge', 0.62, 'Stage 0'),
  ('RC-ENR-006', 'Permitting Authority Unknown', 'It is unclear which government body actually grants permission.', 'ENR-002', 'external', 'Knowledge', 0.71, 'Stage 0'),
  ('RC-ENR-007', 'Assuming No Approval Is Needed', 'The founder believes they can simply start without any clearance.', 'ENR-002', 'external', 'Knowledge', 0.67, 'Stage 0'),
  ('RC-ENR-008', 'Scheme Assumed Without Checking', 'A subsidy or scheme is counted on without confirming it is still open.', 'ENR-002', 'external', 'Behavioural', 0.66, 'Stage 0'),
  ('RC-ENR-009', 'Tariff and Metering Rules Unknown', 'How energy is priced, billed or fed back to the grid has not been studied.', 'ENR-002', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-ENR-010', 'State Level Differences Not Considered', 'Rules that change from state to state are assumed to be uniform.', 'ENR-002', 'external', 'Knowledge', 0.63, 'Stage 0'),
  ('RC-ENR-011', 'Equipment Cost Falls Upfront on the Founder', 'The business pays for hardware long before the customer pays back.', 'ENR-003', 'external', 'Operational', 0.72, 'Stage 0'),
  ('RC-ENR-012', 'No Plan for Financing the Gap', 'Nothing has been arranged to bridge the period between spend and return.', 'ENR-003', 'external', 'Strategic', 0.69, 'Stage 0'),
  ('RC-ENR-013', 'Assuming Customers Will Pay Fully in Advance', 'The model expects buyers to fund the whole cost upfront.', 'ENR-003', 'external', 'Psychological', 0.65, 'Stage 0'),
  ('RC-ENR-014', 'Payback Period Never Calculated', 'How long the customer takes to recover their money is unknown.', 'ENR-003', 'external', 'Knowledge', 0.67, 'Stage 0'),
  ('RC-ENR-015', 'Target Customer Described as Everyone', 'Homes, businesses and government are all treated as one market.', 'ENR-004', 'external', 'Strategic', 0.68, 'Stage 0'),
  ('RC-ENR-016', 'No Single Segment Chosen', 'Effort will be spread because no starting customer type is picked.', 'ENR-004', 'external', 'Strategic', 0.65, 'Stage 0'),
  ('RC-ENR-017', 'Same Pitch Used for Very Different Buyers', 'One message is aimed at buyers with completely different reasons to buy.', 'ENR-004', 'external', 'Strategic', 0.62, 'Stage 0'),
  ('RC-ENR-018', 'No Conversation With a Real Buyer', 'Nobody who would actually purchase has been spoken to yet.', 'ENR-004', 'external', 'Behavioural', 0.64, 'Stage 0'),
  ('RC-ENR-019', 'No Site Survey Before Quoting', 'Prices are given without anyone visiting and assessing the site.', 'ENR-005', 'external', 'Operational', 0.72, 'Stage 0â†’1'),
  ('RC-ENR-020', 'Costs Quoted From a Supplier List', 'Pricing uses list prices rather than what projects actually cost to deliver.', 'ENR-005', 'external', 'Knowledge', 0.68, 'Stage 0â†’1'),
  ('RC-ENR-021', 'Approval Delays Not in the Timeline', 'Schedules assume permissions arrive instantly.', 'ENR-005', 'external', 'Strategic', 0.67, 'Stage 0â†’1'),
  ('RC-ENR-022', 'Scope Changes Accepted Without Repricing', 'Extra work is absorbed rather than charged for.', 'ENR-005', 'external', 'Behavioural', 0.66, 'Stage 0â†’1'),
  ('RC-ENR-023', 'Quoted Versus Actual Never Compared', 'Nobody checks afterwards how close the quote was to reality.', 'ENR-005', 'external', 'Operational', 0.65, 'Stage 0â†’1'),
  ('RC-ENR-024', 'Cash Plan Assumes Subsidy Arrives on Time', 'The forecast treats government money as if it were predictable.', 'ENR-006', 'external', 'Strategic', 0.71, 'Stage 0â†’1'),
  ('RC-ENR-025', 'No Buffer for Delayed Receivables', 'Nothing is held back to survive a late payment.', 'ENR-006', 'external', 'Operational', 0.69, 'Stage 0â†’1'),
  ('RC-ENR-026', 'Paying Suppliers Before Being Paid', 'Money goes out well before it comes in, with no terms to soften it.', 'ENR-006', 'external', 'Operational', 0.67, 'Stage 0â†’1'),
  ('RC-ENR-027', 'Claim Follow Up Handled Ad Hoc', 'Chasing subsidy claims happens only when someone remembers.', 'ENR-006', 'external', 'Behavioural', 0.63, 'Stage 0â†’1'),
  ('RC-ENR-028', 'Payment Delay Length Not Tracked', 'How late payments actually run has never been measured.', 'ENR-006', 'external', 'Knowledge', 0.64, 'Stage 0â†’1'),
  ('RC-ENR-029', 'No Maintenance Contract Offered', 'Customers are never sold an ongoing service arrangement.', 'ENR-007', 'external', 'Strategic', 0.70, 'Stage 0â†’1'),
  ('RC-ENR-030', 'No Process When Equipment Fails', 'A breakdown is handled differently every time.', 'ENR-007', 'external', 'Operational', 0.68, 'Stage 0â†’1'),
  ('RC-ENR-031', 'No Revenue After Installation', 'The business earns nothing once the equipment is handed over.', 'ENR-007', 'external', 'Strategic', 0.67, 'Stage 0â†’1'),
  ('RC-ENR-032', 'Customers Call the Founder for Repairs', 'Service requests land personally on the founder.', 'ENR-007', 'external', 'Behavioural', 0.64, 'Stage 0â†’1'),
  ('RC-ENR-033', 'No Record of What Was Installed Where', 'There is no list of sites, equipment and dates to service from.', 'ENR-007', 'external', 'Operational', 0.65, 'Stage 0â†’1'),
  ('RC-ENR-034', 'No Lender or Financing Partner', 'Nobody has been tied up to fund customer purchases.', 'ENR-008', 'external', 'Strategic', 0.71, 'Stage 0â†’1'),
  ('RC-ENR-035', 'No EMI or Lease Option Offered', 'The only way to buy is paying the whole amount at once.', 'ENR-008', 'external', 'Strategic', 0.68, 'Stage 0â†’1'),
  ('RC-ENR-036', 'Founder Funding Customer Purchases', 'The business absorbs customer financing out of its own pocket.', 'ENR-008', 'external', 'Operational', 0.67, 'Stage 0â†’1'),
  ('RC-ENR-037', 'Payment Terms Decided Deal by Deal', 'Every customer negotiates their own terms with no standard.', 'ENR-008', 'external', 'Operational', 0.63, 'Stage 0â†’1'),
  ('RC-ENR-038', 'No Standard Installation Checklist', 'There is no fixed sequence of steps for doing a site.', 'ENR-009', 'external', 'Operational', 0.70, 'Stage 0â†’1'),
  ('RC-ENR-039', 'Each Site Planned From Scratch', 'Every project starts as if it were the first one.', 'ENR-009', 'external', 'Operational', 0.68, 'Stage 0â†’1'),
  ('RC-ENR-040', 'Lessons From Past Sites Not Recorded', 'What went wrong last time is never written down.', 'ENR-009', 'external', 'Behavioural', 0.66, 'Stage 0â†’1'),
  ('RC-ENR-041', 'Cash Tied Up Per Project Never Measured', 'Nobody knows how much money one project locks up or for how long.', 'ENR-010', 'external', 'Knowledge', 0.73, 'Stage 1â†’10+'),
  ('RC-ENR-042', 'Orders Accepted Without Funding Check', 'New work is taken on without asking whether it can be funded.', 'ENR-010', 'external', 'Behavioural', 0.71, 'Stage 1â†’10+'),
  ('RC-ENR-043', 'No Working Capital Facility', 'No credit line exists to bridge project spending.', 'ENR-010', 'external', 'Strategic', 0.69, 'Stage 1â†’10+'),
  ('RC-ENR-044', 'Payment Milestones Loaded to the End', 'Most of the money arrives only after the work is finished.', 'ENR-010', 'external', 'Strategic', 0.67, 'Stage 1â†’10+'),
  ('RC-ENR-045', 'Growth Increasing Cash Strain', 'Each new order makes the cash position worse rather than better.', 'ENR-010', 'external', 'Operational', 0.68, 'Stage 1â†’10+'),
  ('RC-ENR-046', 'Service Team Far Behind Site Count', 'Live sites have grown much faster than the people servicing them.', 'ENR-011', 'external', 'Operational', 0.72, 'Stage 1â†’10+'),
  ('RC-ENR-047', 'Service Requests Queuing Up', 'Requests wait because capacity cannot absorb them.', 'ENR-011', 'external', 'Operational', 0.69, 'Stage 1â†’10+'),
  ('RC-ENR-048', 'No Regional Service Coverage', 'Distant sites have nobody nearby who can attend.', 'ENR-011', 'external', 'Operational', 0.67, 'Stage 1â†’10+'),
  ('RC-ENR-049', 'Maintenance Visits Missed', 'Scheduled servicing slips because urgent breakdowns take priority.', 'ENR-011', 'external', 'Operational', 0.65, 'Stage 1â†’10+'),
  ('RC-ENR-050', 'Complaints Rising With Installed Base', 'Dissatisfaction grows in step with the number of live sites.', 'ENR-011', 'external', 'Operational', 0.64, 'Stage 1â†’10+'),
  ('RC-ENR-051', 'Guarantees Given in Contracts', 'Output or savings promises are written into customer agreements.', 'ENR-012', 'external', 'Strategic', 0.71, 'Stage 1â†’10+'),
  ('RC-ENR-052', 'Actual Performance Not Monitored', 'What each site really produces is not measured against what was promised.', 'ENR-012', 'external', 'Operational', 0.73, 'Stage 1â†’10+'),
  ('RC-ENR-053', 'No Early Warning for Underperformance', 'A failing site is discovered only when the customer complains.', 'ENR-012', 'external', 'Operational', 0.70, 'Stage 1â†’10+'),
  ('RC-ENR-054', 'Warranty Claims Handled Case by Case', 'Every claim is negotiated separately with no policy.', 'ENR-012', 'external', 'Operational', 0.65, 'Stage 1â†’10+'),
  ('RC-ENR-055', 'Guarantee Exposure Not Quantified', 'Nobody has added up what the promises could cost if called in.', 'ENR-012', 'external', 'Knowledge', 0.68, 'Stage 1â†’10+'),
  ('RC-ENR-056', 'Model Depends on Current Tariff Rules', 'The economics only work under todays metering and tariff regime.', 'ENR-013', 'external', 'Strategic', 0.74, 'Stage 1â†’10+'),
  ('RC-ENR-057', 'No Scenario for a Policy Change', 'Nothing has been planned for rules shifting against the business.', 'ENR-013', 'external', 'Strategic', 0.71, 'Stage 1â†’10+'),
  ('RC-ENR-058', 'Subsidy Dependence Never Reduced', 'Reliance on government support has not decreased as the business grew.', 'ENR-013', 'external', 'Strategic', 0.69, 'Stage 1â†’10+'),
  ('RC-ENR-059', 'Policy News Not Tracked Systematically', 'Regulatory changes are learned about by accident.', 'ENR-013', 'external', 'Behavioural', 0.65, 'Stage 1â†’10+'),
  ('RC-ENR-060', 'No Pricing Flexibility if Rules Shift', 'Prices and contracts cannot absorb a change in the rules.', 'ENR-013', 'external', 'Operational', 0.66, 'Stage 1â†’10+'),
  ('RC-ENR-061', 'Same Playbook Applied to Every State', 'Expansion assumes what worked in one state works everywhere.', 'ENR-014', 'external', 'Strategic', 0.72, 'Stage 1â†’10+'),
  ('RC-ENR-062', 'Discom and Approval Differences Found Late', 'Local requirements surface only after committing to a project.', 'ENR-014', 'external', 'Knowledge', 0.70, 'Stage 1â†’10+'),
  ('RC-ENR-063', 'No Local Partner in New States', 'There is nobody on the ground who knows the local system.', 'ENR-014', 'external', 'Operational', 0.67, 'Stage 1â†’10+'),
  ('RC-ENR-064', 'Most Revenue From Two or Three Clients', 'A handful of buyers carry nearly all the income.', 'ENR-015', 'external', 'Strategic', 0.74, 'Stage 1â†’10+'),
  ('RC-ENR-065', 'Terms Dictated by the Large Buyer', 'Pricing and payment conditions are set by the client, not the business.', 'ENR-015', 'external', 'Strategic', 0.69, 'Stage 1â†’10+'),
  ('RC-ENR-066', 'No Pipeline of Smaller Customers', 'Nothing is being built that could replace a lost large client.', 'ENR-015', 'external', 'Strategic', 0.68, 'Stage 1â†’10+')
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
         '["cleantech_energy"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-ENR-001', 'Do you know roughly what one full installation or unit would cost to put in?', 'open_text', 'Idea & Validation', 'CORE', 'ENR-001', 'RC-ENR-001', 1, 'Stage 0'),
  ('S0-ENR-002', 'How long before your first payment actually comes in?', 'open_text', 'Idea & Validation', 'CORE', 'ENR-001', 'RC-ENR-003', 1, 'Stage 0'),
  ('S0-ENR-003', 'Are you counting on a subsidy or scheme to make the numbers work?', 'open_text', 'Idea & Validation', 'CORE', 'ENR-001', 'RC-ENR-004', 2, 'Stage 0'),
  ('S0-ENR-004', 'Have you separated equipment cost from installation and site work?', 'open_text', 'Idea & Validation', 'CORE', 'ENR-001', 'RC-ENR-005', 2, 'Stage 0'),
  ('S0-ENR-005', 'How much money would you need before you earn your first rupee?', 'open_text', 'Idea & Validation', 'CORE', 'ENR-001', 'RC-ENR-002', 2, 'Stage 0'),
  ('S0-ENR-006', 'Do you know which government body actually gives permission for this?', 'open_text', 'Idea & Validation', 'CORE', 'ENR-002', 'RC-ENR-006', 1, 'Stage 0'),
  ('S0-ENR-007', 'Do you think you can start this without any approval?', 'open_text', 'Idea & Validation', 'CORE', 'ENR-002', 'RC-ENR-007', 1, 'Stage 0'),
  ('S0-ENR-008', 'If you are relying on a scheme, have you checked it is still open?', 'open_text', 'Idea & Validation', 'CORE', 'ENR-002', 'RC-ENR-008', 2, 'Stage 0'),
  ('S0-ENR-009', 'Do you know how the energy gets priced, billed or sent back to the grid?', 'open_text', 'Idea & Validation', 'CORE', 'ENR-002', 'RC-ENR-009', 2, 'Stage 0'),
  ('S0-ENR-010', 'Have you checked whether the rules differ in other states?', 'open_text', 'Idea & Validation', 'CORE', 'ENR-002', 'RC-ENR-010', 2, 'Stage 0'),
  ('S0-ENR-011', 'If the customer saves money over 5 years, who pays for the equipment today?', 'open_text', 'Idea & Validation', 'CORE', 'ENR-003', 'RC-ENR-011', 1, 'Stage 0'),
  ('S0-ENR-012', 'How will you cover the gap between paying for equipment and getting paid back?', 'open_text', 'Idea & Validation', 'CORE', 'ENR-003', 'RC-ENR-012', 2, 'Stage 0'),
  ('S0-ENR-013', 'How long would it take a customer to get their money back?', 'open_text', 'Idea & Validation', 'CORE', 'ENR-003', 'RC-ENR-014', 2, 'Stage 0'),
  ('S0-ENR-014', 'Is this for homes, businesses, factories or government? Pick one.', 'open_text', 'Idea & Validation', 'CORE', 'ENR-004', 'RC-ENR-015', 1, 'Stage 0'),
  ('S0-ENR-015', 'Have you spoken to even one real buyer of this type yet?', 'open_text', 'Idea & Validation', 'CORE', 'ENR-004', 'RC-ENR-018', 1, 'Stage 0'),
  ('S01-ENR-001', 'On your last project, was the final cost the same as what you quoted?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-005', 'RC-ENR-023', 2, 'Stage 0â†’1'),
  ('S01-ENR-002', 'Do you do a site visit before giving a price?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-005', 'RC-ENR-019', 2, 'Stage 0â†’1'),
  ('S01-ENR-003', 'Is your pricing based on supplier lists or on what past projects really cost?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-005', 'RC-ENR-020', 2, 'Stage 0â†’1'),
  ('S01-ENR-004', 'Does your project timeline include waiting time for approvals?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-005', 'RC-ENR-021', 2, 'Stage 0â†’1'),
  ('S01-ENR-005', 'When a customer asks for extra work mid project, do you charge for it?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-005', 'RC-ENR-022', 2, 'Stage 0â†’1'),
  ('S01-ENR-006', 'How many months late was your last government or subsidy payment?', 'open_text', 'Financial Management', 'CORE', 'ENR-006', 'RC-ENR-028', 2, 'Stage 0â†’1'),
  ('S01-ENR-007', 'Does your cash plan assume subsidy money arrives on time?', 'open_text', 'Financial Management', 'CORE', 'ENR-006', 'RC-ENR-024', 2, 'Stage 0â†’1'),
  ('S01-ENR-008', 'If a payment came 6 months late, could the business survive it?', 'open_text', 'Financial Management', 'CORE', 'ENR-006', 'RC-ENR-025', 3, 'Stage 0â†’1'),
  ('S01-ENR-009', 'Do you pay your suppliers before your customer pays you?', 'open_text', 'Financial Management', 'CORE', 'ENR-006', 'RC-ENR-026', 2, 'Stage 0â†’1'),
  ('S01-ENR-010', 'Who chases your pending subsidy claims, and how often?', 'open_text', 'Financial Management', 'CORE', 'ENR-006', 'RC-ENR-027', 2, 'Stage 0â†’1'),
  ('S01-ENR-011', 'If the equipment you installed last year stops working, who fixes it and who pays?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-007', 'RC-ENR-030', 2, 'Stage 0â†’1'),
  ('S01-ENR-012', 'Do you earn anything after the installation is done?', 'open_text', 'Sales & Revenue', 'CORE', 'ENR-007', 'RC-ENR-031', 2, 'Stage 0â†’1'),
  ('S01-ENR-013', 'Do you offer customers any maintenance contract?', 'open_text', 'Sales & Revenue', 'CORE', 'ENR-007', 'RC-ENR-029', 2, 'Stage 0â†’1'),
  ('S01-ENR-014', 'When something breaks, who does the customer call?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-007', 'RC-ENR-032', 2, 'Stage 0â†’1'),
  ('S01-ENR-015', 'Do you have a list of every site, what was installed and when?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-007', 'RC-ENR-033', 2, 'Stage 0â†’1'),
  ('S01-ENR-016', 'When a customer says yes but cannot pay upfront, what do you offer them?', 'open_text', 'Sales & Revenue', 'CORE', 'ENR-008', 'RC-ENR-034', 2, 'Stage 0â†’1'),
  ('S01-ENR-017', 'Is there any EMI or lease option a customer can take?', 'open_text', 'Sales & Revenue', 'CORE', 'ENR-008', 'RC-ENR-035', 2, 'Stage 0â†’1'),
  ('S01-ENR-018', 'Have you ever funded a customer purchase out of your own money?', 'open_text', 'Financial Management', 'CORE', 'ENR-008', 'RC-ENR-036', 3, 'Stage 0â†’1'),
  ('S01-ENR-019', 'Is your second installation faster and cheaper than your first?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-009', 'RC-ENR-038', 2, 'Stage 0â†’1'),
  ('S01-ENR-020', 'When a site goes wrong, does anyone write down what happened?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-009', 'RC-ENR-040', 2, 'Stage 0â†’1'),
  ('S10-ENR-001', 'How much cash does one project tie up, and for how long?', 'open_text', 'Financial Management', 'CORE', 'ENR-010', 'RC-ENR-041', 2, 'Stage 1â†’10+'),
  ('S10-ENR-002', 'Do you check whether you can fund a project before accepting the order?', 'open_text', 'Financial Management', 'CORE', 'ENR-010', 'RC-ENR-042', 2, 'Stage 1â†’10+'),
  ('S10-ENR-003', 'Do you have a working capital line, or do you fund projects from revenue?', 'open_text', 'Financial Management', 'CORE', 'ENR-010', 'RC-ENR-043', 3, 'Stage 1â†’10+'),
  ('S10-ENR-004', 'When during a project do you actually get paid, start or end?', 'open_text', 'Financial Management', 'CORE', 'ENR-010', 'RC-ENR-044', 2, 'Stage 1â†’10+'),
  ('S10-ENR-005', 'Does taking on more orders make your cash position better or worse?', 'open_text', 'Financial Management', 'CORE', 'ENR-010', 'RC-ENR-045', 3, 'Stage 1â†’10+'),
  ('S10-ENR-006', 'How many sites are live now, and how many people service them?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-011', 'RC-ENR-046', 2, 'Stage 1â†’10+'),
  ('S10-ENR-007', 'How long does a customer wait for a service visit?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-011', 'RC-ENR-047', 2, 'Stage 1â†’10+'),
  ('S10-ENR-008', 'If a site is in a city you have no team in, who attends it?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-011', 'RC-ENR-048', 2, 'Stage 1â†’10+'),
  ('S10-ENR-009', 'Are scheduled maintenance visits actually happening on time?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-011', 'RC-ENR-049', 2, 'Stage 1â†’10+'),
  ('S10-ENR-010', 'Have complaints gone up as your number of sites has grown?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-011', 'RC-ENR-050', 2, 'Stage 1â†’10+'),
  ('S10-ENR-011', 'Did you promise customers a certain output or saving in writing?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-012', 'RC-ENR-051', 2, 'Stage 1â†’10+'),
  ('S10-ENR-012', 'Do you know if each site is actually delivering what you promised?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-012', 'RC-ENR-052', 3, 'Stage 1â†’10+'),
  ('S10-ENR-013', 'How do you find out a site is underperforming, from data or from the customer?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-012', 'RC-ENR-053', 2, 'Stage 1â†’10+'),
  ('S10-ENR-014', 'If every guarantee you gave was claimed, what would it cost you?', 'open_text', 'Financial Management', 'CORE', 'ENR-012', 'RC-ENR-055', 3, 'Stage 1â†’10+'),
  ('S10-ENR-015', 'Do you have a standard way of handling warranty claims?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-012', 'RC-ENR-054', 2, 'Stage 1â†’10+'),
  ('S10-ENR-016', 'If net metering or tariff rules changed next year, what happens to your model?', 'open_text', 'Strategy & Planning', 'CORE', 'ENR-013', 'RC-ENR-056', 3, 'Stage 1â†’10+'),
  ('S10-ENR-017', 'Have you planned for what you would do if the rules changed against you?', 'open_text', 'Strategy & Planning', 'CORE', 'ENR-013', 'RC-ENR-057', 3, 'Stage 1â†’10+'),
  ('S10-ENR-018', 'Has your dependence on subsidies gone down as you have grown?', 'open_text', 'Strategy & Planning', 'CORE', 'ENR-013', 'RC-ENR-058', 3, 'Stage 1â†’10+'),
  ('S10-ENR-019', 'How do you keep track of policy and regulation changes?', 'open_text', 'Strategy & Planning', 'CORE', 'ENR-013', 'RC-ENR-059', 2, 'Stage 1â†’10+'),
  ('S10-ENR-020', 'Could your pricing absorb a change in tariff rules?', 'open_text', 'Financial Management', 'CORE', 'ENR-013', 'RC-ENR-060', 3, 'Stage 1â†’10+'),
  ('S10-ENR-021', 'What changes when you enter a new state?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-014', 'RC-ENR-061', 2, 'Stage 1â†’10+'),
  ('S10-ENR-022', 'When did you last discover a local requirement after committing to a project?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-014', 'RC-ENR-062', 2, 'Stage 1â†’10+'),
  ('S10-ENR-023', 'Do you have someone on the ground in each state you operate in?', 'open_text', 'Operations & Systems', 'CORE', 'ENR-014', 'RC-ENR-063', 2, 'Stage 1â†’10+'),
  ('S10-ENR-024', 'What share of revenue comes from your top two customers?', 'open_text', 'Sales & Revenue', 'CORE', 'ENR-015', 'RC-ENR-064', 2, 'Stage 1â†’10+'),
  ('S10-ENR-025', 'If your biggest client left, how long could the business continue?', 'open_text', 'Sales & Revenue', 'CORE', 'ENR-015', 'RC-ENR-066', 3, 'Stage 1â†’10+')
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
  ('S0-ENR-001', 'willingness-to-pay'),
  ('S0-ENR-002', 'willingness-to-pay'),
  ('S0-ENR-003', 'willingness-to-pay'),
  ('S0-ENR-004', 'willingness-to-pay'),
  ('S0-ENR-005', 'willingness-to-pay'),
  ('S0-ENR-006', 'problem-clarity'),
  ('S0-ENR-007', 'problem-clarity'),
  ('S0-ENR-008', 'problem-clarity'),
  ('S0-ENR-009', 'problem-clarity'),
  ('S0-ENR-010', 'problem-clarity'),
  ('S0-ENR-011', 'willingness-to-pay'),
  ('S0-ENR-012', 'willingness-to-pay'),
  ('S0-ENR-013', 'willingness-to-pay'),
  ('S0-ENR-014', 'icp'),
  ('S0-ENR-015', 'icp'),
  ('S01-ENR-001', 'technical-quality'),
  ('S01-ENR-002', 'technical-quality'),
  ('S01-ENR-003', 'technical-quality'),
  ('S01-ENR-004', 'technical-quality'),
  ('S01-ENR-005', 'technical-quality'),
  ('S01-ENR-006', 'willingness-to-pay'),
  ('S01-ENR-007', 'willingness-to-pay'),
  ('S01-ENR-008', 'willingness-to-pay'),
  ('S01-ENR-009', 'willingness-to-pay'),
  ('S01-ENR-010', 'willingness-to-pay'),
  ('S01-ENR-011', 'technical-quality'),
  ('S01-ENR-012', 'technical-quality'),
  ('S01-ENR-013', 'technical-quality'),
  ('S01-ENR-014', 'technical-quality'),
  ('S01-ENR-015', 'technical-quality'),
  ('S01-ENR-016', 'willingness-to-pay'),
  ('S01-ENR-017', 'willingness-to-pay'),
  ('S01-ENR-018', 'willingness-to-pay'),
  ('S01-ENR-019', 'technical-quality'),
  ('S01-ENR-020', 'technical-quality'),
  ('S10-ENR-001', 'willingness-to-pay'),
  ('S10-ENR-002', 'willingness-to-pay'),
  ('S10-ENR-003', 'willingness-to-pay'),
  ('S10-ENR-004', 'willingness-to-pay'),
  ('S10-ENR-005', 'willingness-to-pay'),
  ('S10-ENR-006', 'technical-quality'),
  ('S10-ENR-007', 'technical-quality'),
  ('S10-ENR-008', 'technical-quality'),
  ('S10-ENR-009', 'technical-quality'),
  ('S10-ENR-010', 'technical-quality'),
  ('S10-ENR-011', 'technical-quality'),
  ('S10-ENR-012', 'technical-quality'),
  ('S10-ENR-013', 'technical-quality'),
  ('S10-ENR-014', 'technical-quality'),
  ('S10-ENR-015', 'technical-quality'),
  ('S10-ENR-016', 'problem-clarity'),
  ('S10-ENR-017', 'problem-clarity'),
  ('S10-ENR-018', 'problem-clarity'),
  ('S10-ENR-019', 'problem-clarity'),
  ('S10-ENR-020', 'problem-clarity'),
  ('S10-ENR-021', 'problem-clarity'),
  ('S10-ENR-022', 'problem-clarity'),
  ('S10-ENR-023', 'problem-clarity'),
  ('S10-ENR-024', 'willingness-to-pay'),
  ('S10-ENR-025', 'willingness-to-pay')
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
         '["cleantech_energy"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-ENR-001', 'Ideation â€” CleanTech Capital Reality', 'ENR-001', '["RC-ENR-001", "RC-ENR-005"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Price out one complete installation, start to finish.", "Keep equipment, labour and site work as separate lines.", "Compare the total against the money you actually have."]'::jsonb, '[{"name": "One Installation Cost Sheet", "brief": "A real, itemised cost for a single complete installation."}]'::jsonb),
  ('INT-ENR-002', 'Ideation â€” CleanTech Capital Reality', 'ENR-001', '["RC-ENR-002", "RC-ENR-003"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Work out how many months pass before your first payment.", "Add up what you must spend during that time.", "That number is what you really need to start."]'::jsonb, '[{"name": "Months to First Rupee", "brief": "Counting the spending months before any revenue arrives."}]'::jsonb),
  ('INT-ENR-003', 'Ideation â€” CleanTech Capital Reality', 'ENR-001', '["RC-ENR-004"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Write down every subsidy your plan depends on.", "Check today whether each one is open and who qualifies.", "Redo your numbers assuming none of them arrive."]'::jsonb, '[{"name": "Plan Without the Subsidy", "brief": "Testing whether the idea works if government money never comes."}]'::jsonb),
  ('INT-ENR-004', 'Ideation â€” CleanTech Regulatory Basics', 'ENR-002', '["RC-ENR-006", "RC-ENR-007"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Find out which authority gives permission for what you want to do.", "Call or visit them and ask what is required.", "Write down the steps and rough timeline."]'::jsonb, '[{"name": "Find the Permitting Authority", "brief": "Identifying the body that actually approves this work and what it asks for."}]'::jsonb),
  ('INT-ENR-005', 'Ideation â€” CleanTech Regulatory Basics', 'ENR-002', '["RC-ENR-008", "RC-ENR-010"]'::jsonb, '[1]'::jsonb, 'Compliance', '["List every scheme or incentive you plan to use.", "Confirm each is currently open in your state.", "Note where the rules differ if you plan to expand."]'::jsonb, '[{"name": "Scheme Status Check", "brief": "Confirming incentives are live and state specific before relying on them."}]'::jsonb),
  ('INT-ENR-006', 'Ideation â€” CleanTech Regulatory Basics', 'ENR-002', '["RC-ENR-009"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Learn how energy is billed and metered for your customer type.", "Find out what happens with any surplus sent back.", "Write it in two lines you can explain to a buyer."]'::jsonb, '[{"name": "Tariff and Metering Basics", "brief": "Understanding how the energy is actually priced and billed."}]'::jsonb),
  ('INT-ENR-007', 'Ideation â€” CleanTech Payback Gap', 'ENR-003', '["RC-ENR-011", "RC-ENR-014"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Work out how long the customer takes to recover their money.", "Work out how long you wait to recover yours.", "Write both numbers side by side."]'::jsonb, '[{"name": "Two Sided Payback", "brief": "Seeing the payback period for the customer and for the business together."}]'::jsonb),
  ('INT-ENR-008', 'Ideation â€” CleanTech Payback Gap', 'ENR-003', '["RC-ENR-012", "RC-ENR-013"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Decide who funds the equipment at the start.", "Look at one option, such as customer advance, lender or lease.", "Write down what happens if that option is not available."]'::jsonb, '[{"name": "Who Funds the Gap", "brief": "Naming a real source of money for the period before payback."}]'::jsonb),
  ('INT-ENR-009', 'Ideation â€” CleanTech Customer Clarity', 'ENR-004', '["RC-ENR-015", "RC-ENR-016"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Pick one customer type to start with, homes or business or industry.", "Write one line on why that one first.", "Set the others aside for now."]'::jsonb, '[{"name": "One Segment First", "brief": "Choosing a single starting customer type instead of serving all."}]'::jsonb),
  ('INT-ENR-010', 'Ideation â€” CleanTech Customer Clarity', 'ENR-004', '["RC-ENR-017", "RC-ENR-018"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Talk to 5 buyers of your chosen type.", "Ask what would make them say yes, and what stops them.", "Rewrite your pitch for them alone."]'::jsonb, '[{"name": "Talk to Your One Segment", "brief": "Learning what your chosen buyer actually needs before building."}]'::jsonb),
  ('INT-ENR-011', 'Validation to Traction â€” CleanTech Project Delivery', 'ENR-005', '["RC-ENR-019", "RC-ENR-020"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Visit every site before giving a price.", "Build the quote from what the last project actually cost.", "Add a line for the things that always go wrong."]'::jsonb, '[{"name": "Survey Before Quote", "brief": "Pricing from a real site visit and real past costs, not a supplier list."}]'::jsonb),
  ('INT-ENR-012', 'Validation to Traction â€” CleanTech Project Delivery', 'ENR-005', '["RC-ENR-021", "RC-ENR-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Record quoted cost and time against actual for every project.", "Include approval waiting time in the schedule.", "Use the gap to correct your next quote."]'::jsonb, '[{"name": "Quoted Versus Actual Log", "brief": "Tracking the difference between promise and delivery on every project."}]'::jsonb),
  ('INT-ENR-013', 'Validation to Traction â€” CleanTech Project Delivery', 'ENR-005', '["RC-ENR-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Write one line in every contract about extra work being charged.", "Price any change before doing it.", "Get it in writing, even a message."]'::jsonb, '[{"name": "Charge for Scope Change", "brief": "A simple rule that extra work gets repriced before it is done."}]'::jsonb),
  ('INT-ENR-014', 'Validation to Traction â€” CleanTech Receivables Risk', 'ENR-006', '["RC-ENR-024", "RC-ENR-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Record how many days late each payment actually was.", "Rebuild your cash plan using those real delays.", "Never plan on the official timeline again."]'::jsonb, '[{"name": "Plan on Real Payment Delays", "brief": "Building cash forecasts from actual payment behaviour, not promised terms."}]'::jsonb),
  ('INT-ENR-015', 'Validation to Traction â€” CleanTech Receivables Risk', 'ENR-006', '["RC-ENR-025", "RC-ENR-026"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Work out how many months of costs you must cover while waiting.", "Hold that much back or arrange a credit line.", "Negotiate longer terms with suppliers where you can."]'::jsonb, '[{"name": "Receivables Buffer", "brief": "Holding enough cash or credit to survive the waiting period."}]'::jsonb),
  ('INT-ENR-016', 'Validation to Traction â€” CleanTech Receivables Risk', 'ENR-006', '["RC-ENR-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Give one person responsibility for chasing claims.", "Set a fixed day each week to follow up.", "Keep a list of every pending claim and its age."]'::jsonb, '[{"name": "Claim Follow Up Routine", "brief": "One owner and a weekly rhythm for chasing pending payments."}]'::jsonb),
  ('INT-ENR-017', 'Validation to Traction â€” CleanTech After Installation', 'ENR-007', '["RC-ENR-029", "RC-ENR-031"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Design one simple annual maintenance contract.", "Price it and offer it with every new installation.", "Go back and offer it to past customers too."]'::jsonb, '[{"name": "Annual Maintenance Contract", "brief": "Turning post installation service into a real revenue line."}]'::jsonb),
  ('INT-ENR-018', 'Validation to Traction â€” CleanTech After Installation', 'ENR-007', '["RC-ENR-030", "RC-ENR-032", "RC-ENR-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Build one list of every site, equipment and installation date.", "Write the steps for handling a breakdown.", "Give customers one service number, not your personal one."]'::jsonb, '[{"name": "Service Register and Process", "brief": "A site record plus a defined route for handling failures."}]'::jsonb),
  ('INT-ENR-019', 'Validation to Traction â€” CleanTech Customer Financing', 'ENR-008', '["RC-ENR-034", "RC-ENR-035"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Approach two lenders or financing partners this month.", "Set up one EMI or lease option customers can take.", "Put it on your quote as a standard choice."]'::jsonb, '[{"name": "Arrange Customer Financing", "brief": "Giving buyers a real way to pay over time instead of only upfront."}]'::jsonb),
  ('INT-ENR-020', 'Validation to Traction â€” CleanTech Customer Financing', 'ENR-008', '["RC-ENR-036", "RC-ENR-037"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Stop funding customer purchases from your own cash.", "Write one standard set of payment terms.", "Use it for every deal unless there is a strong reason not to."]'::jsonb, '[{"name": "Standard Payment Terms", "brief": "One consistent payment structure instead of per deal improvisation."}]'::jsonb),
  ('INT-ENR-021', 'Validation to Traction â€” CleanTech Repeatability', 'ENR-009', '["RC-ENR-038", "RC-ENR-039"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Write a step by step checklist for a standard installation.", "Use it on the next three sites without exception.", "Update it each time something new comes up."]'::jsonb, '[{"name": "Standard Installation Checklist", "brief": "A fixed sequence so every site runs the same way."}]'::jsonb),
  ('INT-ENR-022', 'Validation to Traction â€” CleanTech Repeatability', 'ENR-009', '["RC-ENR-040"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["After every site, write three lines on what went wrong.", "Keep them in one place the team can read.", "Review them before starting the next project."]'::jsonb, '[{"name": "Site Lessons Log", "brief": "Capturing what went wrong so the next site avoids it."}]'::jsonb),
  ('INT-ENR-023', 'Growth to Maturity â€” CleanTech Working Capital', 'ENR-010', '["RC-ENR-041", "RC-ENR-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Work out the cash locked up by one typical project and for how many months.", "Multiply by the number of projects you want running at once.", "Set a limit on concurrent projects your cash can carry."]'::jsonb, '[{"name": "Cash Per Project Limit", "brief": "Capping concurrent projects to what the cash position can actually fund."}]'::jsonb),
  ('INT-ENR-024', 'Growth to Maturity â€” CleanTech Working Capital', 'ENR-010', '["RC-ENR-042", "RC-ENR-043"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Arrange a working capital line before you need it.", "Check funding capacity before accepting any new order.", "Make that check part of the sales process."]'::jsonb, '[{"name": "Fund Before You Sign", "brief": "A credit line plus a funding check before every order is accepted."}]'::jsonb),
  ('INT-ENR-025', 'Growth to Maturity â€” CleanTech Working Capital', 'ENR-010', '["RC-ENR-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Restructure payment milestones so more money arrives early.", "Ask for a larger advance on new contracts.", "Compare cash strain before and after the change."]'::jsonb, '[{"name": "Front Load Payment Milestones", "brief": "Shifting contract payments earlier to reduce cash tied up."}]'::jsonb),
  ('INT-ENR-026', 'Growth to Maturity â€” CleanTech Service at Scale', 'ENR-011', '["RC-ENR-046", "RC-ENR-047", "RC-ENR-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Work out how many sites one service person can cover.", "Hire or partner to close the gap before complaints grow.", "Track waiting time for service visits every week."]'::jsonb, '[{"name": "Service Capacity Plan", "brief": "Sizing the service team against the real number of live sites."}]'::jsonb),
  ('INT-ENR-027', 'Growth to Maturity â€” CleanTech Service at Scale', 'ENR-011', '["RC-ENR-048", "RC-ENR-049"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Identify regions where you have sites but no service presence.", "Appoint one local partner or technician per priority region.", "Protect scheduled maintenance from being pushed aside by breakdowns."]'::jsonb, '[{"name": "Regional Service Coverage", "brief": "A service presence wherever live sites exist, with protected maintenance."}]'::jsonb),
  ('INT-ENR-028', 'Growth to Maturity â€” CleanTech Performance Risk', 'ENR-012', '["RC-ENR-051", "RC-ENR-052", "RC-ENR-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["List every guarantee you have given, by site.", "Monitor actual output against each one.", "Set an alert when a site falls below its promise."]'::jsonb, '[{"name": "Guarantee Versus Actual Monitoring", "brief": "Tracking real site performance against every promise made."}]'::jsonb),
  ('INT-ENR-029', 'Growth to Maturity â€” CleanTech Performance Risk', 'ENR-012', '["RC-ENR-054", "RC-ENR-055"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Add up what all your guarantees would cost if claimed.", "Write one standard warranty claim process.", "Set money aside against that exposure."]'::jsonb, '[{"name": "Warranty Exposure and Policy", "brief": "Quantifying guarantee risk and handling claims by one standard rule."}]'::jsonb),
  ('INT-ENR-030', 'Growth to Maturity â€” CleanTech Policy Risk', 'ENR-013', '["RC-ENR-056", "RC-ENR-057", "RC-ENR-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Write what happens to your margins if tariff or metering rules change.", "Decide now what you would do in that case.", "Build some pricing flexibility into new contracts."]'::jsonb, '[{"name": "Policy Change Scenario", "brief": "A written plan for the day the rules move against the business."}]'::jsonb),
  ('INT-ENR-031', 'Growth to Maturity â€” CleanTech Policy Risk', 'ENR-013', '["RC-ENR-058", "RC-ENR-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Measure what share of your margin comes from subsidies.", "Set a target to reduce that share each year.", "Give one person the job of tracking policy changes."]'::jsonb, '[{"name": "Reduce Subsidy Dependence", "brief": "Lowering reliance on government support and watching policy deliberately."}]'::jsonb),
  ('INT-ENR-032', 'Growth to Maturity â€” CleanTech State Expansion', 'ENR-014', '["RC-ENR-061", "RC-ENR-062"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Build a checklist covering approvals, discom rules and tariffs per state.", "Complete it before committing to any project in a new state.", "Update it after every state you enter."]'::jsonb, '[{"name": "State Entry Checklist", "brief": "Mapping local approvals, discom and tariff rules before entering a state."}]'::jsonb),
  ('INT-ENR-033', 'Growth to Maturity â€” CleanTech State Expansion', 'ENR-014', '["RC-ENR-063"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Find one local partner or hire in each new state.", "Use them to validate timelines and costs before you commit.", "Do not enter a state without one."]'::jsonb, '[{"name": "Local Partner First", "brief": "Having someone on the ground before committing to a new state."}]'::jsonb),
  ('INT-ENR-034', 'Growth to Maturity â€” CleanTech Client Concentration', 'ENR-015', '["RC-ENR-064", "RC-ENR-065", "RC-ENR-066"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Calculate the revenue share of your top two clients.", "Set a target share and build a pipeline of smaller customers to reach it.", "Review the number every quarter."]'::jsonb, '[{"name": "Reduce Client Concentration", "brief": "Measuring dependence on top clients and deliberately building beyond them."}]'::jsonb)
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
  (SELECT COUNT(*) FROM new_interventions) AS interventions_inserted;-- expect 34"""),
        ('Entertainment & Media', 'media_entertainment', 'MED', r"""-- ============================================================================
-- Ally :: Industry seed -- ENTERTAINMENT & MEDIA (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            35 interventions.  Industry tag: media_entertainment
--
-- Note     : 35 interventions, not the usual 34 -- this industry has one extra
--            so that every problem has at least one intervention of its own.
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (MED-001, RC-MED-014, S0-MED-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (monetisation, platform risk, rights, talent)
--            starts at Stage 0->1.
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
  ('MED-001', 'No Clear Idea Who Pays for the Content', 'The founder wants to make content but has not worked out whether the money comes from viewers, advertisers, brands or a platform.', 'Idea & Validation', 'Media Revenue Basics', 'external', 4, 4, 8, '["No revenue source identified", "Assuming views turn into money automatically", "No idea what advertisers actually pay for", "Platform payout rates never checked", "No plan if sponsors never arrive"]'::jsonb, '["media_entertainment"]'::jsonb),
  ('MED-002', 'Making Content Confused With Building a Business', 'There is a plan to create content but no plan for how any of it becomes something that earns.', 'Idea & Validation', 'Media Business Model', 'external', 2, 4, 8, '["Plan describes what will be made, not how it earns", "Success defined as making content", "No thought about rights or ownership", "Assuming an audience automatically becomes a business", "No idea what a good month would look like financially"]'::jsonb, '["media_entertainment"]'::jsonb),
  ('MED-003', 'Audience Is Everyone So It Is Nobody', 'No specific type of viewer, listener or reader has been chosen, so the content has no one it clearly belongs to.', 'Idea & Validation', 'Media Audience Clarity', 'external', 2, 4, 8, '["Audience described as everyone", "No single platform or format chosen", "Content topic changes with every idea", "No idea what this audience already watches or reads", "Nobody outside friends has given feedback"]'::jsonb, '["media_entertainment"]'::jsonb),
  ('MED-004', 'No Idea How Much Content This Actually Takes', 'The time, effort and cost of producing content regularly has never been tested even once.', 'Idea & Validation', 'Media Production Reality', 'external', 3, 4, 8, '["No complete piece of content made yet", "Time per piece never measured", "Publishing frequency chosen without testing", "No plan for who does editing or production", "Cost of production never estimated"]'::jsonb, '["media_entertainment"]'::jsonb),
  ('MED-005', 'Audience Is Growing but Income Is Not', 'Views and followers keep rising while almost no money comes in from any of it.', 'Sales & Revenue', 'Media Monetisation Gap', 'external', 4, 6, 9, '["Audience growth not matched by revenue", "No way for a follower to pay directly", "Income only arrives when a brand appears", "Audience never asked for anything", "No owned list or channel"]'::jsonb, '["media_entertainment"]'::jsonb),
  ('MED-006', 'Everything Depends on One Creator', 'The founder is the face, the voice and the editor, so nothing exists without them showing up.', 'Operations & Systems', 'Media Creator Dependency', 'external', 3, 6, 9, '["All content made by one person", "No other face or voice on the channel", "Publishing stops when the founder is unavailable", "No editing or production help", "Audience follows the person, not the brand"]'::jsonb, '["media_entertainment"]'::jsonb),
  ('MED-007', 'Platform Algorithm Controls the Whole Business', 'All reach comes from one platform feed, so a change to it can stop the business overnight.', 'Strategy & Planning', 'Media Platform Risk', 'external', 2, 7, 10, '["Nearly all reach from one platform", "No second platform built", "No owned audience list", "Views swing wildly with algorithm changes", "No plan if the account is restricted"]'::jsonb, '["media_entertainment"]'::jsonb),
  ('MED-008', 'Brand Deals Are One Off and Underpriced', 'Sponsorships happen occasionally, are negotiated from scratch each time and usually end up too cheap.', 'Sales & Revenue', 'Media Sponsorship Pricing', 'external', 4, 5, 9, '["No rate card", "Price negotiated from zero every time", "No repeat deals with the same brand", "Deliverables unclear in each deal", "No idea what similar creators charge"]'::jsonb, '["media_entertainment"]'::jsonb),
  ('MED-009', 'Production Cannot Keep to Schedule', 'Publishing is irregular because the content pipeline runs on last minute effort with nothing ready in advance.', 'Operations & Systems', 'Media Production Pipeline', 'external', 3, 5, 9, '["Content made just before publishing", "No buffer of ready content", "Publishing gaps whenever something goes wrong", "No content calendar", "Quality dropping under time pressure"]'::jsonb, '["media_entertainment"]'::jsonb),
  ('MED-010', 'Content Team Scaled but Quality Slipped', 'More people are producing now and the work no longer holds one consistent standard or voice.', 'Operations & Systems', 'Media Quality at Scale', 'external', 3, 6, 9, '["No written style or quality standard", "Nothing reviewed before publishing", "New contributors onboarded informally", "Output prioritised over consistency", "Audience noticing the difference"]'::jsonb, '["media_entertainment"]'::jsonb),
  ('MED-011', 'Revenue Tied to Attention Not Assets', 'The business earns only from current views rather than from anything it owns and can sell again.', 'Sales & Revenue', 'Media Asset Building', 'external', 4, 6, 9, '["Income stops when posting stops", "Nothing owned that earns repeatedly", "No licensing or catalogue revenue", "No format or IP that could be sold", "Back catalogue earns almost nothing"]'::jsonb, '["media_entertainment"]'::jsonb),
  ('MED-012', 'IP, Rights and Licensing Not Managed', 'Music, clips, footage and contributor rights were handled loosely, creating real takedown and legal exposure.', 'Operations & Systems', 'Media Rights Management', 'external', 3, 6, 10, '["No written rights for music or footage used", "Contributor releases not collected", "Takedowns or claims already received", "No record of what is licensed and until when", "Rights handled differently by each team member"]'::jsonb, '["media_entertainment"]'::jsonb),
  ('MED-013', 'Talent Retention and Contracts', 'Creators, hosts or editors who became central have no contracts or clear terms and could leave with the audience.', 'Team & Leadership', 'Media Talent Risk', 'external', 5, 6, 10, '["Key talent working without contracts", "No clarity on who owns the channel or audience", "No notice period or handover terms", "Talent approached by competitors", "Audience attached to one individual"]'::jsonb, '["media_entertainment"]'::jsonb),
  ('MED-014', 'Platform and Advertiser Policy Risk at Scale', 'Bigger reach brings more scrutiny, so one policy breach, demonetisation or brand safety flag can hit a large share of income.', 'Strategy & Planning', 'Media Policy Compliance', 'external', 2, 6, 10, '["Platform policies never fully read", "Content that could breach brand safety rules", "Demonetisation already experienced", "No review of risky content before publishing", "Large income share exposed to one policy decision"]'::jsonb, '["media_entertainment"]'::jsonb),
  ('MED-015', 'No Data on What Actually Works', 'Content decisions are still made on instinct even though years of performance data now exist.', 'Strategy & Planning', 'Media Data Decisions', 'external', 2, 5, 9, '["Decisions made on instinct", "Performance data never analysed", "No idea which formats perform best", "Repeating content that consistently underperforms", "No review of what worked each quarter"]'::jsonb, '["media_entertainment"]'::jsonb)
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
         t.primary_stage_group, '["media_entertainment"]'::jsonb, z.v
  FROM (VALUES
  ('RC-MED-001', 'No Revenue Source Identified', 'Nobody has decided where the money would actually come from.', 'MED-001', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-MED-002', 'Assuming Views Turn Into Money', 'Attention is treated as if it automatically becomes income.', 'MED-001', 'external', 'Psychological', 0.68, 'Stage 0'),
  ('RC-MED-003', 'No Idea What Advertisers Pay For', 'What a brand actually buys and at what price has never been checked.', 'MED-001', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-MED-004', 'Platform Payout Rates Never Checked', 'What a platform really pays per view is unknown.', 'MED-001', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-MED-005', 'No Plan If Sponsors Never Arrive', 'There is no income route that works without brand deals.', 'MED-001', 'external', 'Strategic', 0.63, 'Stage 0'),
  ('RC-MED-006', 'Plan Describes Making, Not Earning', 'The plan covers what will be produced but not how it pays.', 'MED-002', 'external', 'Strategic', 0.69, 'Stage 0'),
  ('RC-MED-007', 'Success Defined as Making Content', 'Publishing is treated as the goal rather than a means to one.', 'MED-002', 'external', 'Psychological', 0.66, 'Stage 0'),
  ('RC-MED-008', 'Rights and Ownership Not Considered', 'Who owns the content and what can be licensed has not been thought about.', 'MED-002', 'external', 'Knowledge', 0.62, 'Stage 0'),
  ('RC-MED-009', 'Assuming Audience Becomes a Business', 'Believing that once people watch, the business follows by itself.', 'MED-002', 'external', 'Psychological', 0.67, 'Stage 0'),
  ('RC-MED-010', 'No Financial Picture of a Good Month', 'There is no sense of what earning well would even look like.', 'MED-002', 'external', 'Knowledge', 0.61, 'Stage 0'),
  ('RC-MED-011', 'Audience Described as Everyone', 'No specific viewer or reader has been chosen to serve.', 'MED-003', 'external', 'Strategic', 0.68, 'Stage 0'),
  ('RC-MED-012', 'No Single Platform or Format Chosen', 'Effort will be spread across formats with no starting point.', 'MED-003', 'external', 'Strategic', 0.65, 'Stage 0'),
  ('RC-MED-013', 'Topic Changes With Every Idea', 'The subject keeps shifting so no audience can form around it.', 'MED-003', 'external', 'Behavioural', 0.64, 'Stage 0'),
  ('RC-MED-014', 'What the Audience Already Consumes Is Unknown', 'Nobody has looked at what this audience watches or reads today.', 'MED-003', 'external', 'Knowledge', 0.63, 'Stage 0'),
  ('RC-MED-015', 'No Feedback From Outside the Circle', 'Only friends and family have reacted to the idea.', 'MED-003', 'external', 'Behavioural', 0.61, 'Stage 0'),
  ('RC-MED-016', 'No Complete Piece of Content Made', 'Not one full piece has been produced end to end.', 'MED-004', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-MED-017', 'Time Per Piece Never Measured', 'How long one piece takes to make has never been recorded.', 'MED-004', 'external', 'Knowledge', 0.67, 'Stage 0'),
  ('RC-MED-018', 'Publishing Frequency Chosen Without Testing', 'A schedule was promised before knowing what is sustainable.', 'MED-004', 'external', 'Strategic', 0.65, 'Stage 0'),
  ('RC-MED-019', 'No Direct Way for the Audience to Pay', 'There is nothing a follower can buy or support even if they want to.', 'MED-005', 'external', 'Strategic', 0.72, 'Stage 0â†’1'),
  ('RC-MED-020', 'Income Only Arrives With a Brand', 'The business earns nothing unless a sponsor turns up.', 'MED-005', 'external', 'Strategic', 0.70, 'Stage 0â†’1'),
  ('RC-MED-021', 'Audience Never Asked for Anything', 'The audience has never been invited to buy, join or support.', 'MED-005', 'external', 'Behavioural', 0.67, 'Stage 0â†’1'),
  ('RC-MED-022', 'No Owned List or Channel', 'There is no email list or direct channel the creator controls.', 'MED-005', 'external', 'Operational', 0.68, 'Stage 0â†’1'),
  ('RC-MED-023', 'Audience Size Treated as the Goal', 'Growth is chased while revenue is left for later.', 'MED-005', 'external', 'Psychological', 0.65, 'Stage 0â†’1'),
  ('RC-MED-024', 'All Content Made by One Person', 'Every step from idea to publish sits with the founder.', 'MED-006', 'external', 'Operational', 0.73, 'Stage 0â†’1'),
  ('RC-MED-025', 'No Second Face or Voice', 'Nobody else appears, so the channel has one point of failure.', 'MED-006', 'external', 'Strategic', 0.68, 'Stage 0â†’1'),
  ('RC-MED-026', 'Publishing Stops When the Founder Stops', 'Any illness or travel breaks the schedule completely.', 'MED-006', 'external', 'Operational', 0.70, 'Stage 0â†’1'),
  ('RC-MED-027', 'No Editing or Production Help', 'Post production is entirely on the founder.', 'MED-006', 'external', 'Operational', 0.67, 'Stage 0â†’1'),
  ('RC-MED-028', 'Audience Follows the Person Not the Brand', 'Attachment is to the individual rather than to anything transferable.', 'MED-006', 'external', 'Strategic', 0.66, 'Stage 0â†’1'),
  ('RC-MED-029', 'Nearly All Reach From One Platform', 'One feed decides whether the content is seen at all.', 'MED-007', 'external', 'Strategic', 0.74, 'Stage 0â†’1'),
  ('RC-MED-030', 'No Second Platform Built', 'Nothing else has been grown that could carry the audience.', 'MED-007', 'external', 'Strategic', 0.70, 'Stage 0â†’1'),
  ('RC-MED-031', 'No Owned Audience List', 'There is no way to reach followers if the platform disappears.', 'MED-007', 'external', 'Operational', 0.71, 'Stage 0â†’1'),
  ('RC-MED-032', 'Views Swing With Algorithm Changes', 'Reach moves sharply for reasons outside anyone control.', 'MED-007', 'external', 'Operational', 0.66, 'Stage 0â†’1'),
  ('RC-MED-033', 'No Plan If the Account Is Restricted', 'A suspension or strike has no prepared response.', 'MED-007', 'external', 'Strategic', 0.68, 'Stage 0â†’1'),
  ('RC-MED-034', 'No Rate Card', 'There is no standard price list for sponsorships.', 'MED-008', 'external', 'Operational', 0.71, 'Stage 0â†’1'),
  ('RC-MED-035', 'Price Negotiated From Zero Each Time', 'Every deal starts with guessing what to ask for.', 'MED-008', 'external', 'Behavioural', 0.69, 'Stage 0â†’1'),
  ('RC-MED-036', 'No Repeat Deals With the Same Brand', 'Sponsorships end after one campaign with no renewal path.', 'MED-008', 'external', 'Strategic', 0.66, 'Stage 0â†’1'),
  ('RC-MED-037', 'Deliverables Unclear in Each Deal', 'What the brand receives is agreed loosely and varies.', 'MED-008', 'external', 'Operational', 0.64, 'Stage 0â†’1'),
  ('RC-MED-038', 'Market Rates Unknown', 'What similar creators charge has never been researched.', 'MED-008', 'external', 'Knowledge', 0.67, 'Stage 0â†’1'),
  ('RC-MED-039', 'Content Made Just Before Publishing', 'Nothing is produced ahead of the deadline.', 'MED-009', 'external', 'Behavioural', 0.70, 'Stage 0â†’1'),
  ('RC-MED-040', 'No Buffer of Ready Content', 'There is no stock of finished pieces to fall back on.', 'MED-009', 'external', 'Operational', 0.68, 'Stage 0â†’1'),
  ('RC-MED-041', 'No Written Style or Quality Standard', 'There is no agreed definition of what good looks like here.', 'MED-010', 'external', 'Operational', 0.72, 'Stage 1â†’10+'),
  ('RC-MED-042', 'Nothing Reviewed Before Publishing', 'Work goes out without anyone checking it against a standard.', 'MED-010', 'external', 'Operational', 0.70, 'Stage 1â†’10+'),
  ('RC-MED-043', 'Contributors Onboarded Informally', 'New people learn the style by guessing rather than being taught.', 'MED-010', 'external', 'Operational', 0.66, 'Stage 1â†’10+'),
  ('RC-MED-044', 'Output Prioritised Over Consistency', 'Hitting the schedule matters more than holding the bar.', 'MED-010', 'external', 'Behavioural', 0.67, 'Stage 1â†’10+'),
  ('RC-MED-045', 'Audience Noticing the Difference', 'Viewers are commenting that the work has changed.', 'MED-010', 'external', 'Operational', 0.64, 'Stage 1â†’10+'),
  ('RC-MED-046', 'Income Stops When Posting Stops', 'Revenue depends entirely on continuing to publish.', 'MED-011', 'external', 'Strategic', 0.73, 'Stage 1â†’10+'),
  ('RC-MED-047', 'Nothing Owned That Earns Repeatedly', 'No product, format or catalogue generates income on its own.', 'MED-011', 'external', 'Strategic', 0.71, 'Stage 1â†’10+'),
  ('RC-MED-048', 'No Licensing or Catalogue Revenue', 'Existing content is never licensed or resold anywhere.', 'MED-011', 'external', 'Strategic', 0.67, 'Stage 1â†’10+'),
  ('RC-MED-049', 'No Format or IP That Could Be Sold', 'Nothing has been built that another party would buy.', 'MED-011', 'external', 'Strategic', 0.66, 'Stage 1â†’10+'),
  ('RC-MED-050', 'Back Catalogue Earns Almost Nothing', 'Older content sits unused instead of continuing to work.', 'MED-011', 'external', 'Operational', 0.65, 'Stage 1â†’10+'),
  ('RC-MED-051', 'No Written Rights for Music or Footage', 'Material is used without documented permission.', 'MED-012', 'external', 'Knowledge', 0.74, 'Stage 1â†’10+'),
  ('RC-MED-052', 'Contributor Releases Not Collected', 'People who appear on camera have signed nothing.', 'MED-012', 'external', 'Operational', 0.70, 'Stage 1â†’10+'),
  ('RC-MED-053', 'Takedowns or Claims Already Received', 'The exposure has already started showing up as claims.', 'MED-012', 'external', 'Operational', 0.68, 'Stage 1â†’10+'),
  ('RC-MED-054', 'No Record of What Is Licensed', 'Nobody can say what rights are held and until when.', 'MED-012', 'external', 'Operational', 0.69, 'Stage 1â†’10+'),
  ('RC-MED-055', 'Rights Handled Differently by Each Person', 'Every team member follows their own approach to clearance.', 'MED-012', 'external', 'Operational', 0.65, 'Stage 1â†’10+'),
  ('RC-MED-056', 'Key Talent Working Without Contracts', 'Central people have no written agreement of any kind.', 'MED-013', 'external', 'Operational', 0.75, 'Stage 1â†’10+'),
  ('RC-MED-057', 'Unclear Who Owns the Channel and Audience', 'Ownership of the account and following was never agreed.', 'MED-013', 'external', 'Strategic', 0.72, 'Stage 1â†’10+'),
  ('RC-MED-058', 'No Notice Period or Handover Terms', 'Someone could leave immediately with no transition.', 'MED-013', 'external', 'Operational', 0.68, 'Stage 1â†’10+'),
  ('RC-MED-059', 'Talent Approached by Competitors', 'Key people are being actively recruited elsewhere.', 'MED-013', 'external', 'Strategic', 0.66, 'Stage 1â†’10+'),
  ('RC-MED-060', 'Audience Attached to One Individual', 'The following belongs to a person rather than the brand.', 'MED-013', 'external', 'Strategic', 0.69, 'Stage 1â†’10+'),
  ('RC-MED-061', 'Platform Policies Never Fully Read', 'Nobody has actually read the rules the business depends on.', 'MED-014', 'external', 'Knowledge', 0.71, 'Stage 1â†’10+'),
  ('RC-MED-062', 'No Review of Risky Content Before Publishing', 'Sensitive material goes out without a compliance check.', 'MED-014', 'external', 'Operational', 0.69, 'Stage 1â†’10+'),
  ('RC-MED-063', 'Large Income Share Exposed to One Policy', 'A single demonetisation decision would hit most of the revenue.', 'MED-014', 'external', 'Strategic', 0.72, 'Stage 1â†’10+'),
  ('RC-MED-064', 'Decisions Made on Instinct', 'What to make next is chosen by feel rather than evidence.', 'MED-015', 'external', 'Behavioural', 0.70, 'Stage 1â†’10+'),
  ('RC-MED-065', 'Performance Data Never Analysed', 'Years of data sit unused in the platform dashboard.', 'MED-015', 'external', 'Operational', 0.68, 'Stage 1â†’10+'),
  ('RC-MED-066', 'Underperforming Content Repeated', 'The same formats keep being made despite weak results.', 'MED-015', 'external', 'Behavioural', 0.66, 'Stage 1â†’10+')
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
         '["media_entertainment"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-MED-001', 'Where would the money actually come from, viewers, advertisers, brands or a platform?', 'open_text', 'Idea & Validation', 'CORE', 'MED-001', 'RC-MED-001', 1, 'Stage 0'),
  ('S0-MED-002', 'Do you think a lot of views automatically means a lot of money?', 'open_text', 'Idea & Validation', 'CORE', 'MED-001', 'RC-MED-002', 1, 'Stage 0'),
  ('S0-MED-003', 'Do you know what a brand actually pays for, and roughly how much?', 'open_text', 'Idea & Validation', 'CORE', 'MED-001', 'RC-MED-003', 2, 'Stage 0'),
  ('S0-MED-004', 'Do you know what a platform pays for views of your kind of content?', 'open_text', 'Idea & Validation', 'CORE', 'MED-001', 'RC-MED-004', 2, 'Stage 0'),
  ('S0-MED-005', 'If no sponsor ever came, would you earn anything at all?', 'open_text', 'Idea & Validation', 'CORE', 'MED-001', 'RC-MED-005', 2, 'Stage 0'),
  ('S0-MED-006', 'Does your plan say how this earns, or only what you will make?', 'open_text', 'Idea & Validation', 'CORE', 'MED-002', 'RC-MED-006', 1, 'Stage 0'),
  ('S0-MED-007', 'If you published every week for a year and earned nothing, would you call that success?', 'open_text', 'Idea & Validation', 'CORE', 'MED-002', 'RC-MED-007', 2, 'Stage 0'),
  ('S0-MED-008', 'Have you thought about who owns the content you create?', 'open_text', 'Idea & Validation', 'CORE', 'MED-002', 'RC-MED-008', 2, 'Stage 0'),
  ('S0-MED-009', 'Do you believe that once people watch, the money follows on its own?', 'open_text', 'Idea & Validation', 'CORE', 'MED-002', 'RC-MED-009', 2, 'Stage 0'),
  ('S0-MED-010', 'What would a good earning month look like for you, in numbers?', 'open_text', 'Idea & Validation', 'CORE', 'MED-002', 'RC-MED-010', 2, 'Stage 0'),
  ('S0-MED-011', 'Who exactly is this for, one specific type of person or anyone?', 'open_text', 'Idea & Validation', 'CORE', 'MED-003', 'RC-MED-011', 1, 'Stage 0'),
  ('S0-MED-012', 'Which one platform or format will you start with, and why that one?', 'open_text', 'Idea & Validation', 'CORE', 'MED-003', 'RC-MED-012', 2, 'Stage 0'),
  ('S0-MED-013', 'Do you know what your audience already watches or reads today?', 'open_text', 'Idea & Validation', 'CORE', 'MED-003', 'RC-MED-014', 2, 'Stage 0'),
  ('S0-MED-014', 'Have you made even one full piece of content and timed how long it took?', 'open_text', 'Idea & Validation', 'CORE', 'MED-004', 'RC-MED-016', 1, 'Stage 0'),
  ('S0-MED-015', 'How often would you need to publish, and can you keep that up?', 'open_text', 'Idea & Validation', 'CORE', 'MED-004', 'RC-MED-018', 1, 'Stage 0'),
  ('S01-MED-001', 'Your audience has grown. Has your income grown with it?', 'open_text', 'Sales & Revenue', 'CORE', 'MED-005', 'RC-MED-023', 2, 'Stage 0â†’1'),
  ('S01-MED-002', 'Is there any way for a follower to give you money directly today?', 'open_text', 'Sales & Revenue', 'CORE', 'MED-005', 'RC-MED-019', 2, 'Stage 0â†’1'),
  ('S01-MED-003', 'If no brand sponsored you this year, what would you earn?', 'open_text', 'Sales & Revenue', 'CORE', 'MED-005', 'RC-MED-020', 2, 'Stage 0â†’1'),
  ('S01-MED-004', 'Have you ever actually asked your audience to buy or support something?', 'open_text', 'Sales & Revenue', 'CORE', 'MED-005', 'RC-MED-021', 2, 'Stage 0â†’1'),
  ('S01-MED-005', 'Do you have an email list or group you own, outside the platform?', 'open_text', 'Sales & Revenue', 'CORE', 'MED-005', 'RC-MED-022', 2, 'Stage 0â†’1'),
  ('S01-MED-006', 'If you stopped appearing for a month, what would happen?', 'open_text', 'Operations & Systems', 'CORE', 'MED-006', 'RC-MED-026', 2, 'Stage 0â†’1'),
  ('S01-MED-007', 'Does anyone else edit, script or publish, or is it all you?', 'open_text', 'Operations & Systems', 'CORE', 'MED-006', 'RC-MED-024', 2, 'Stage 0â†’1'),
  ('S01-MED-008', 'Has anyone else ever appeared on your channel?', 'open_text', 'Operations & Systems', 'CORE', 'MED-006', 'RC-MED-025', 2, 'Stage 0â†’1'),
  ('S01-MED-009', 'How many hours a week go into editing and post production?', 'open_text', 'Operations & Systems', 'CORE', 'MED-006', 'RC-MED-027', 2, 'Stage 0â†’1'),
  ('S01-MED-010', 'Do people follow you, or would they follow the brand without you?', 'open_text', 'Strategy & Planning', 'CORE', 'MED-006', 'RC-MED-028', 3, 'Stage 0â†’1'),
  ('S01-MED-011', 'What share of your reach comes from one platform feed?', 'open_text', 'Strategy & Planning', 'CORE', 'MED-007', 'RC-MED-029', 2, 'Stage 0â†’1'),
  ('S01-MED-012', 'Have you built anything on a second platform yet?', 'open_text', 'Strategy & Planning', 'CORE', 'MED-007', 'RC-MED-030', 2, 'Stage 0â†’1'),
  ('S01-MED-013', 'If your account was restricted tomorrow, how would you reach your audience?', 'open_text', 'Strategy & Planning', 'CORE', 'MED-007', 'RC-MED-031', 3, 'Stage 0â†’1'),
  ('S01-MED-014', 'How much do your views swing month to month, and do you know why?', 'open_text', 'Strategy & Planning', 'CORE', 'MED-007', 'RC-MED-032', 2, 'Stage 0â†’1'),
  ('S01-MED-015', 'Do you have any plan for a strike or suspension?', 'open_text', 'Strategy & Planning', 'CORE', 'MED-007', 'RC-MED-033', 3, 'Stage 0â†’1'),
  ('S01-MED-016', 'How do you decide what to charge a brand?', 'open_text', 'Sales & Revenue', 'CORE', 'MED-008', 'RC-MED-034', 2, 'Stage 0â†’1'),
  ('S01-MED-017', 'Do you know what creators of your size usually charge?', 'open_text', 'Sales & Revenue', 'CORE', 'MED-008', 'RC-MED-038', 2, 'Stage 0â†’1'),
  ('S01-MED-018', 'Has any brand worked with you more than once?', 'open_text', 'Sales & Revenue', 'CORE', 'MED-008', 'RC-MED-036', 2, 'Stage 0â†’1'),
  ('S01-MED-019', 'Do you have content ready in advance, or is it made just before publishing?', 'open_text', 'Operations & Systems', 'CORE', 'MED-009', 'RC-MED-039', 2, 'Stage 0â†’1'),
  ('S01-MED-020', 'How many finished pieces are sitting ready right now?', 'open_text', 'Operations & Systems', 'CORE', 'MED-009', 'RC-MED-040', 2, 'Stage 0â†’1'),
  ('S10-MED-001', 'Is there a written standard for what good work looks like here?', 'open_text', 'Operations & Systems', 'CORE', 'MED-010', 'RC-MED-041', 2, 'Stage 1â†’10+'),
  ('S10-MED-002', 'Does anything get reviewed before it goes out?', 'open_text', 'Operations & Systems', 'CORE', 'MED-010', 'RC-MED-042', 2, 'Stage 1â†’10+'),
  ('S10-MED-003', 'What does a new contributor get shown before their first piece?', 'open_text', 'Operations & Systems', 'CORE', 'MED-010', 'RC-MED-043', 2, 'Stage 1â†’10+'),
  ('S10-MED-004', 'When the schedule is tight, what gets sacrificed?', 'open_text', 'Operations & Systems', 'CORE', 'MED-010', 'RC-MED-044', 2, 'Stage 1â†’10+'),
  ('S10-MED-005', 'Has your audience commented that the work has changed?', 'open_text', 'Operations & Systems', 'CORE', 'MED-010', 'RC-MED-045', 2, 'Stage 1â†’10+'),
  ('S10-MED-006', 'If you stopped posting for six months, what would you still earn?', 'open_text', 'Sales & Revenue', 'CORE', 'MED-011', 'RC-MED-046', 3, 'Stage 1â†’10+'),
  ('S10-MED-007', 'Do you own anything that could still earn in three years without new posting?', 'open_text', 'Sales & Revenue', 'CORE', 'MED-011', 'RC-MED-047', 3, 'Stage 1â†’10+'),
  ('S10-MED-008', 'Has any of your content ever been licensed to someone else?', 'open_text', 'Sales & Revenue', 'CORE', 'MED-011', 'RC-MED-048', 2, 'Stage 1â†’10+'),
  ('S10-MED-009', 'Is there a format or idea here that another company would buy?', 'open_text', 'Strategy & Planning', 'CORE', 'MED-011', 'RC-MED-049', 3, 'Stage 1â†’10+'),
  ('S10-MED-010', 'How much does your older content earn compared to new content?', 'open_text', 'Sales & Revenue', 'CORE', 'MED-011', 'RC-MED-050', 2, 'Stage 1â†’10+'),
  ('S10-MED-011', 'Do you have written rights for all the music, clips and footage you use?', 'open_text', 'Operations & Systems', 'CORE', 'MED-012', 'RC-MED-051', 2, 'Stage 1â†’10+'),
  ('S10-MED-012', 'Have the people who appear in your content signed anything?', 'open_text', 'Operations & Systems', 'CORE', 'MED-012', 'RC-MED-052', 2, 'Stage 1â†’10+'),
  ('S10-MED-013', 'Have you received any takedowns or copyright claims?', 'open_text', 'Operations & Systems', 'CORE', 'MED-012', 'RC-MED-053', 2, 'Stage 1â†’10+'),
  ('S10-MED-014', 'Can you say what you have licensed and until when?', 'open_text', 'Operations & Systems', 'CORE', 'MED-012', 'RC-MED-054', 3, 'Stage 1â†’10+'),
  ('S10-MED-015', 'Does everyone on your team clear rights the same way?', 'open_text', 'Operations & Systems', 'CORE', 'MED-012', 'RC-MED-055', 2, 'Stage 1â†’10+'),
  ('S10-MED-016', 'Are your key people on written contracts?', 'open_text', 'Team & Leadership', 'CORE', 'MED-013', 'RC-MED-056', 2, 'Stage 1â†’10+'),
  ('S10-MED-017', 'Is it clear in writing who owns the channel and the audience?', 'open_text', 'Team & Leadership', 'CORE', 'MED-013', 'RC-MED-057', 3, 'Stage 1â†’10+'),
  ('S10-MED-018', 'If your main host left tomorrow, what could they take with them?', 'open_text', 'Team & Leadership', 'CORE', 'MED-013', 'RC-MED-060', 3, 'Stage 1â†’10+'),
  ('S10-MED-019', 'Is there any notice period or handover agreed with key talent?', 'open_text', 'Team & Leadership', 'CORE', 'MED-013', 'RC-MED-058', 2, 'Stage 1â†’10+'),
  ('S10-MED-020', 'Has anyone on your team been approached by a competitor?', 'open_text', 'Team & Leadership', 'CORE', 'MED-013', 'RC-MED-059', 2, 'Stage 1â†’10+'),
  ('S10-MED-021', 'Has anyone actually read the platform policies you depend on?', 'open_text', 'Strategy & Planning', 'CORE', 'MED-014', 'RC-MED-061', 2, 'Stage 1â†’10+'),
  ('S10-MED-022', 'Does risky or sensitive content get checked before publishing?', 'open_text', 'Strategy & Planning', 'CORE', 'MED-014', 'RC-MED-062', 2, 'Stage 1â†’10+'),
  ('S10-MED-023', 'What share of your income would a demonetisation decision affect?', 'open_text', 'Strategy & Planning', 'CORE', 'MED-014', 'RC-MED-063', 3, 'Stage 1â†’10+'),
  ('S10-MED-024', 'When you decide what to make next, do you look at data or go by feel?', 'open_text', 'Strategy & Planning', 'CORE', 'MED-015', 'RC-MED-064', 2, 'Stage 1â†’10+'),
  ('S10-MED-025', 'Which of your formats performs best, and how do you know?', 'open_text', 'Strategy & Planning', 'CORE', 'MED-015', 'RC-MED-065', 2, 'Stage 1â†’10+')
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
  ('S0-MED-001', 'willingness-to-pay'),
  ('S0-MED-002', 'willingness-to-pay'),
  ('S0-MED-003', 'willingness-to-pay'),
  ('S0-MED-004', 'willingness-to-pay'),
  ('S0-MED-005', 'willingness-to-pay'),
  ('S0-MED-006', 'willingness-to-pay'),
  ('S0-MED-007', 'willingness-to-pay'),
  ('S0-MED-008', 'willingness-to-pay'),
  ('S0-MED-009', 'willingness-to-pay'),
  ('S0-MED-010', 'willingness-to-pay'),
  ('S0-MED-011', 'icp'),
  ('S0-MED-012', 'icp'),
  ('S0-MED-013', 'icp'),
  ('S0-MED-014', 'problem-clarity'),
  ('S0-MED-015', 'problem-clarity'),
  ('S01-MED-001', 'willingness-to-pay'),
  ('S01-MED-002', 'willingness-to-pay'),
  ('S01-MED-003', 'willingness-to-pay'),
  ('S01-MED-004', 'willingness-to-pay'),
  ('S01-MED-005', 'willingness-to-pay'),
  ('S01-MED-006', 'technical-quality'),
  ('S01-MED-007', 'technical-quality'),
  ('S01-MED-008', 'technical-quality'),
  ('S01-MED-009', 'technical-quality'),
  ('S01-MED-010', 'technical-quality'),
  ('S01-MED-011', 'channel-strategy'),
  ('S01-MED-012', 'channel-strategy'),
  ('S01-MED-013', 'channel-strategy'),
  ('S01-MED-014', 'channel-strategy'),
  ('S01-MED-015', 'channel-strategy'),
  ('S01-MED-016', 'willingness-to-pay'),
  ('S01-MED-017', 'willingness-to-pay'),
  ('S01-MED-018', 'willingness-to-pay'),
  ('S01-MED-019', 'technical-quality'),
  ('S01-MED-020', 'technical-quality'),
  ('S10-MED-001', 'technical-quality'),
  ('S10-MED-002', 'technical-quality'),
  ('S10-MED-003', 'technical-quality'),
  ('S10-MED-004', 'technical-quality'),
  ('S10-MED-005', 'technical-quality'),
  ('S10-MED-006', 'willingness-to-pay'),
  ('S10-MED-007', 'willingness-to-pay'),
  ('S10-MED-008', 'willingness-to-pay'),
  ('S10-MED-009', 'willingness-to-pay'),
  ('S10-MED-010', 'willingness-to-pay'),
  ('S10-MED-011', 'technical-quality'),
  ('S10-MED-012', 'technical-quality'),
  ('S10-MED-013', 'technical-quality'),
  ('S10-MED-014', 'technical-quality'),
  ('S10-MED-015', 'technical-quality'),
  ('S10-MED-016', 'problem-clarity'),
  ('S10-MED-017', 'problem-clarity'),
  ('S10-MED-018', 'problem-clarity'),
  ('S10-MED-019', 'problem-clarity'),
  ('S10-MED-020', 'problem-clarity'),
  ('S10-MED-021', 'problem-clarity'),
  ('S10-MED-022', 'problem-clarity'),
  ('S10-MED-023', 'problem-clarity'),
  ('S10-MED-024', 'problem-clarity'),
  ('S10-MED-025', 'problem-clarity')
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
         '["media_entertainment"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-MED-001', 'Ideation â€” Media Revenue Basics', 'MED-001', '["RC-MED-001", "RC-MED-005"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Write down your one main source of money.", "Write a second one as backup.", "If neither works without sponsors, keep looking."]'::jsonb, '[{"name": "Name Your Money Source", "brief": "Deciding where income comes from before producing anything."}]'::jsonb),
  ('INT-MED-002', 'Ideation â€” Media Revenue Basics', 'MED-001', '["RC-MED-002", "RC-MED-004"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Look up what your chosen platform pays per thousand views.", "Work out how many views you would need to earn a basic income.", "Decide whether that number is realistic."]'::jsonb, '[{"name": "Views to Income Check", "brief": "Turning platform payout rates into a real view target."}]'::jsonb),
  ('INT-MED-003', 'Ideation â€” Media Revenue Basics', 'MED-001', '["RC-MED-003"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Find one creator in your space who has brand deals.", "Look at what the brand got in return.", "Write down what you would be selling a brand."]'::jsonb, '[{"name": "What Brands Actually Buy", "brief": "Understanding the real product being sold to a sponsor."}]'::jsonb),
  ('INT-MED-004', 'Ideation â€” Media Business Model', 'MED-002', '["RC-MED-006", "RC-MED-010"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Write one page on how this earns, not what you will make.", "Put a number on what a good month looks like.", "Check whether your plan can reach it."]'::jsonb, '[{"name": "How It Earns, On One Page", "brief": "A short written model of income, not a content plan."}]'::jsonb),
  ('INT-MED-005', 'Ideation â€” Media Business Model', 'MED-002', '["RC-MED-007", "RC-MED-009"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Write what success looks like in 12 months, in money not posts.", "Ask whether publishing alone would get you there.", "Adjust the plan if it would not."]'::jsonb, '[{"name": "Success in Money Not Posts", "brief": "Defining the goal as an outcome rather than output."}]'::jsonb),
  ('INT-MED-006', 'Ideation â€” Media Business Model', 'MED-002', '["RC-MED-008"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Write down who owns the content you create.", "Check what happens if you use music, clips or images from elsewhere.", "Decide what you can license or reuse later."]'::jsonb, '[{"name": "Ownership and Rights Basics", "brief": "Knowing what you own and what you are borrowing."}]'::jsonb),
  ('INT-MED-007', 'Ideation â€” Media Audience Clarity', 'MED-003', '["RC-MED-011", "RC-MED-012"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Describe one specific person this content is for, in two lines.", "Pick one platform and one format to start with.", "Ignore the rest for the first three months."]'::jsonb, '[{"name": "One Person, One Platform", "brief": "Choosing a single audience and format to start with."}]'::jsonb),
  ('INT-MED-008', 'Ideation â€” Media Audience Clarity', 'MED-003', '["RC-MED-013", "RC-MED-014", "RC-MED-015"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["List 5 creators your audience already follows.", "Note what they cover and what is missing.", "Show your idea to 10 people outside your circle."]'::jsonb, '[{"name": "Study the Audience First", "brief": "Learning what the audience already consumes before creating."}]'::jsonb),
  ('INT-MED-009', 'Ideation â€” Media Production Reality', 'MED-004', '["RC-MED-016", "RC-MED-017"]'::jsonb, '[1]'::jsonb, 'Operations', '["Make one complete piece of content end to end.", "Time every stage honestly, including editing.", "Use that number to plan everything else."]'::jsonb, '[{"name": "One Piece, Timed", "brief": "Measuring the real effort of production by making one full piece."}]'::jsonb),
  ('INT-MED-010', 'Ideation â€” Media Production Reality', 'MED-004', '["RC-MED-018"]'::jsonb, '[1]'::jsonb, 'Operations', '["Work out how many hours a week you truly have.", "Divide by the time one piece takes.", "Set your publishing schedule from that, not from ambition."]'::jsonb, '[{"name": "Sustainable Publishing Rhythm", "brief": "Setting frequency from real available hours, not hope."}]'::jsonb),
  ('INT-MED-011', 'Validation to Traction â€” Media Monetisation', 'MED-005', '["RC-MED-019", "RC-MED-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Add one thing your audience can pay for this month.", "Tell them about it clearly, more than once.", "Count how many actually buy."]'::jsonb, '[{"name": "One Direct Offer", "brief": "Giving the audience a real way to pay and actually asking them."}]'::jsonb),
  ('INT-MED-012', 'Validation to Traction â€” Media Monetisation', 'MED-005', '["RC-MED-020", "RC-MED-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Work out what you would earn this year with zero sponsorships.", "Set a target for non sponsor income.", "Track it separately every month."]'::jsonb, '[{"name": "Income Without Sponsors", "brief": "Building a revenue line that does not depend on brand deals."}]'::jsonb),
  ('INT-MED-013', 'Validation to Traction â€” Media Monetisation', 'MED-005', '["RC-MED-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Start collecting emails or contacts you own.", "Give people a clear reason to join.", "Message that list once a month."]'::jsonb, '[{"name": "Build an Owned List", "brief": "Creating a direct channel to the audience outside any platform."}]'::jsonb),
  ('INT-MED-014', 'Validation to Traction â€” Media Creator Dependency', 'MED-006', '["RC-MED-024", "RC-MED-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Pick the production step that takes the most time.", "Hand that one step to someone else.", "Keep doing only the part only you can do."]'::jsonb, '[{"name": "Hand Off One Step", "brief": "Removing the heaviest production task from the founder first."}]'::jsonb),
  ('INT-MED-015', 'Validation to Traction â€” Media Creator Dependency', 'MED-006', '["RC-MED-025", "RC-MED-026", "RC-MED-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Bring one other person onto the content, even occasionally.", "Record a batch that can publish without you.", "See whether the audience stays."]'::jsonb, '[{"name": "More Than One Face", "brief": "Testing whether the channel can survive without the founder present."}]'::jsonb),
  ('INT-MED-016', 'Validation to Traction â€” Media Platform Risk', 'MED-007', '["RC-MED-029", "RC-MED-030"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Work out what share of reach comes from one platform.", "Pick one second platform and post there consistently for 90 days.", "Compare reach at the end."]'::jsonb, '[{"name": "Second Platform in 90 Days", "brief": "Deliberately building reach somewhere other than the main feed."}]'::jsonb),
  ('INT-MED-017', 'Validation to Traction â€” Media Platform Risk', 'MED-007', '["RC-MED-031", "RC-MED-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["Write what you would do if your main account was suspended tomorrow.", "Make sure the owned list can reach people without it.", "Keep backups of your content."]'::jsonb, '[{"name": "Account Loss Plan", "brief": "A prepared response for losing access to the main platform."}]'::jsonb),
  ('INT-MED-018', 'Validation to Traction â€” Media Platform Risk', 'MED-007', '["RC-MED-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Record monthly reach for the last year.", "Note what changed in the months it dropped.", "Stop judging your work by a single bad month."]'::jsonb, '[{"name": "Reach Trend Not Panic", "brief": "Reading platform swings as a trend instead of reacting to each dip."}]'::jsonb),
  ('INT-MED-019', 'Validation to Traction â€” Media Sponsorship Pricing', 'MED-008', '["RC-MED-034", "RC-MED-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Find what creators of your size charge.", "Write a one page rate card with clear deliverables.", "Send that instead of negotiating from zero."]'::jsonb, '[{"name": "Rate Card", "brief": "A written price list so every deal starts from a number you set."}]'::jsonb),
  ('INT-MED-020', 'Validation to Traction â€” Media Sponsorship Pricing', 'MED-008', '["RC-MED-035", "RC-MED-037"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Write exactly what a brand gets for each package.", "Put it in writing before work starts.", "Keep the same structure for every deal."]'::jsonb, '[{"name": "Clear Deliverables", "brief": "Defining what the sponsor receives so nothing is negotiated mid campaign."}]'::jsonb),
  ('INT-MED-021', 'Validation to Traction â€” Media Sponsorship Pricing', 'MED-008', '["RC-MED-036"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["After every campaign, send the brand simple results.", "Offer a follow up package while it is fresh.", "Aim for renewals, not new logos each time."]'::jsonb, '[{"name": "Turn Deals Into Renewals", "brief": "Reporting results and asking for the next campaign."}]'::jsonb),
  ('INT-MED-022', 'Validation to Traction â€” Media Production Pipeline', 'MED-009', '["RC-MED-039", "RC-MED-040"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Record or write a batch of pieces in one sitting.", "Build up to four finished pieces sitting ready.", "Publish from the buffer, not from todays work."]'::jsonb, '[{"name": "Build a Content Buffer", "brief": "Batching production so publishing never depends on this weeks effort."}]'::jsonb),
  ('INT-MED-023', 'Growth to Maturity â€” Media Quality at Scale', 'MED-010', '["RC-MED-041", "RC-MED-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write one page describing your style and quality bar.", "Share it with everyone producing content.", "Point to it whenever work misses the mark."]'::jsonb, '[{"name": "One Page Style Standard", "brief": "A written definition of the bar every contributor works to."}]'::jsonb),
  ('INT-MED-024', 'Growth to Maturity â€” Media Quality at Scale', 'MED-010', '["RC-MED-042", "RC-MED-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Add one review step before anything publishes.", "Give the reviewer authority to hold a piece back.", "Accept a missed slot over a weak piece."]'::jsonb, '[{"name": "Review Before Publish", "brief": "One checkpoint with real authority to stop weak work going out."}]'::jsonb),
  ('INT-MED-025', 'Growth to Maturity â€” Media Quality at Scale', 'MED-010', '["RC-MED-043"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write the steps a new contributor goes through before producing.", "Include examples of good and bad work.", "Use it for everyone who joins."]'::jsonb, '[{"name": "Contributor Onboarding", "brief": "A defined route so new people learn the standard rather than guess it."}]'::jsonb),
  ('INT-MED-026', 'Growth to Maturity â€” Media Asset Building', 'MED-011', '["RC-MED-046", "RC-MED-047"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Work out what you would earn if you stopped posting for six months.", "Build one thing that earns without new content.", "Track its income separately."]'::jsonb, '[{"name": "Build One Earning Asset", "brief": "Creating income that does not depend on continuing to publish."}]'::jsonb),
  ('INT-MED-027', 'Growth to Maturity â€” Media Asset Building', 'MED-011', '["RC-MED-048", "RC-MED-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["List your best performing older content.", "Find one way to license, repackage or resell it.", "Measure what the back catalogue earns each month."]'::jsonb, '[{"name": "Make the Back Catalogue Work", "brief": "Turning existing content into ongoing income."}]'::jsonb),
  ('INT-MED-028', 'Growth to Maturity â€” Media Asset Building', 'MED-011', '["RC-MED-049"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Identify the format or idea that is genuinely yours.", "Write down what a buyer would actually be getting.", "Protect it properly before showing it around."]'::jsonb, '[{"name": "Define What You Own", "brief": "Naming the format or IP that has value beyond the audience."}]'::jsonb),
  ('INT-MED-029', 'Growth to Maturity â€” Media Rights Management', 'MED-012', '["RC-MED-051", "RC-MED-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["List every piece of music, footage and image you use.", "Record what rights you hold and until when.", "Replace anything you cannot document."]'::jsonb, '[{"name": "Rights Register", "brief": "A single record of what is licensed, from whom and for how long."}]'::jsonb),
  ('INT-MED-030', 'Growth to Maturity â€” Media Rights Management', 'MED-012', '["RC-MED-052", "RC-MED-055"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Create one simple release form for anyone appearing on camera.", "Collect it every time, without exception.", "Give one person responsibility for clearance."]'::jsonb, '[{"name": "Releases and One Owner", "brief": "A standard release form and a single person accountable for rights."}]'::jsonb),
  ('INT-MED-031', 'Growth to Maturity â€” Media Rights Management', 'MED-012', '["RC-MED-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["List every claim or takedown you have received.", "Find what caused each one.", "Fix that cause across your whole library."]'::jsonb, '[{"name": "Claim Root Cause Sweep", "brief": "Tracing takedowns to their source and fixing the whole catalogue."}]'::jsonb),
  ('INT-MED-032', 'Growth to Maturity â€” Media Talent Risk', 'MED-013', '["RC-MED-056", "RC-MED-057", "RC-MED-058"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Put written contracts in place with every key person.", "State clearly who owns the channel and the audience.", "Agree a notice period and handover terms."]'::jsonb, '[{"name": "Contracts With Key Talent", "brief": "Written terms covering ownership, notice and handover."}]'::jsonb),
  ('INT-MED-033', 'Growth to Maturity â€” Media Talent Risk', 'MED-013', '["RC-MED-059", "RC-MED-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Ask what would keep each key person here for two more years.", "Build the brand so it is bigger than any one face.", "Bring more than one person in front of the audience."]'::jsonb, '[{"name": "Beyond One Face", "brief": "Reducing the risk that the audience belongs to one individual."}]'::jsonb),
  ('INT-MED-034', 'Growth to Maturity â€” Media Policy Compliance', 'MED-014', '["RC-MED-061", "RC-MED-062", "RC-MED-063"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Read the platform policies properly and note anything you currently breach.", "Add a check before publishing anything sensitive.", "Reduce how much of your income sits behind one policy decision."]'::jsonb, '[{"name": "Policy Compliance Check", "brief": "Closing platform policy gaps before they cost income."}]'::jsonb),
  ('INT-MED-035', 'Growth to Maturity â€” Media Data Decisions', 'MED-015', '["RC-MED-064", "RC-MED-065", "RC-MED-066"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Pull a year of performance data for every piece you published.", "Mark which formats consistently work and which do not.", "Let that decide next quarter content slate, not instinct."]'::jsonb, '[{"name": "Let the Data Pick the Slate", "brief": "Using a year of real performance data to choose what gets made next."}]'::jsonb)
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
  (SELECT COUNT(*) FROM new_interventions) AS interventions_inserted;-- expect 35

-- ============================================================================
-- After running, the single result row above must read:  15 | 66 | 60 | 60 | 35
-- If any number differs, something did not link -- roll back and check.
-- ============================================================================"""),
        ('Fashion & Apparel', 'fashion_apparel', 'FSH', r"""-- ============================================================================
-- Ally :: Industry seed -- FASHION & APPAREL (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: fashion_apparel
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (FSH-001, RC-FSH-014, S0-FSH-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Trading depth (returns, inventory mix, vendor and channel work)
--            starts at Stage 0->1.
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
  ('FSH-001', 'No Idea Where the Clothes Will Be Made', 'Designs exist but no tailor, unit or manufacturer has been found or spoken to.', 'Idea & Validation', 'Fashion Manufacturing Basics', 'external', 3, 4, 8, '["No manufacturer or tailor identified", "Minimum order quantity unknown", "Fabric sourcing not considered", "Cost per piece never confirmed", "No sample ever stitched"]'::jsonb, '["fashion_apparel"]'::jsonb),
  ('FSH-002', 'Sizes and Fit Not Thought Through', 'Clothes have to fit real bodies, and no decision has been made about sizes, fit or what happens when they are wrong.', 'Idea & Validation', 'Fashion Fit and Sizing', 'external', 3, 4, 8, '["No size range decided", "Fit never tested on real people", "No plan for returns due to fit", "Size chart not created", "Assuming standard sizes will work"]'::jsonb, '["fashion_apparel"]'::jsonb),
  ('FSH-003', 'Too Many Designs, No Focus', 'The plan includes many styles, colours and categories before a single one has sold.', 'Idea & Validation', 'Fashion Range Discipline', 'external', 2, 4, 8, '["Large number of designs planned before any sale", "Multiple categories at launch", "Every colour and size combination planned", "Cash spread thin across styles", "No single hero product"]'::jsonb, '["fashion_apparel"]'::jsonb),
  ('FSH-004', 'No Clear Reason Someone Would Buy This Brand', 'There are thousands of clothing brands and nothing has been defined that makes this one different.', 'Idea & Validation', 'Fashion Brand Differentiation', 'external', 2, 4, 8, '["No point of difference from existing brands", "Brand described only as good quality", "No clear customer this is made for", "Competing on price without knowing cost", "Design inspired by others without a distinct view"]'::jsonb, '["fashion_apparel"]'::jsonb),
  ('FSH-005', 'Returns and Exchanges Eating the Margin', 'Fit related returns are high and each one costs shipping, repacking and often a lost sale.', 'Operations & Systems', 'Fashion Returns', 'external', 3, 6, 9, '["Return rate not measured", "Return reasons never collected", "Size chart does not match the actual garment", "Photos not showing real fit", "Cost of a return never calculated"]'::jsonb, '["fashion_apparel"]'::jsonb),
  ('FSH-006', 'Dead Stock in the Wrong Sizes and Colours', 'Some sizes and colours sell out quickly while others sit unsold, locking up cash.', 'Financial Management', 'Fashion Inventory Mix', 'external', 4, 6, 9, '["Equal quantities bought across sizes", "Best selling sizes out of stock", "Slow colours repeatedly reordered", "Cash locked in unsold variants", "Size ratio never analysed"]'::jsonb, '["fashion_apparel"]'::jsonb),
  ('FSH-007', 'Quality Varies Between Production Lots', 'The same style comes out differently depending on the batch or the unit that made it.', 'Operations & Systems', 'Fashion Quality Control', 'external', 3, 6, 9, '["Same style differs between batches", "No quality check before accepting a lot", "No written specification given to the unit", "Fabric substituted without notice", "Customer complaints about stitching or shrinkage"]'::jsonb, '["fashion_apparel"]'::jsonb),
  ('FSH-008', 'Customers Buy Once and Do Not Come Back', 'First orders happen but almost nobody returns for a second purchase.', 'Sales & Revenue', 'Fashion Repeat Purchase', 'external', 4, 5, 9, '["Repeat purchase rate never measured", "No contact after delivery", "No reason given to buy again", "New styles not shown to past buyers", "Growth depends entirely on new customers"]'::jsonb, '["fashion_apparel"]'::jsonb),
  ('FSH-009', 'Discounting to Clear Leftover Stock', 'Every season ends with a sale to clear what did not sell, and the discount eats the year profit.', 'Financial Management', 'Fashion Markdown Pressure', 'external', 4, 6, 9, '["Season always ends with a clearance sale", "Large share of stock sold at discount", "Production quantity set on optimism", "Margin after markdown never calculated", "Customers waiting for the sale"]'::jsonb, '["fashion_apparel"]'::jsonb),
  ('FSH-010', 'Too Many SKUs to Manage', 'Styles, sizes and colours have multiplied into thousands of combinations nobody can forecast or control.', 'Operations & Systems', 'Fashion SKU Control', 'external', 3, 6, 9, '["SKU count grown without review", "No rule for retiring a style", "Forecasting done per style not per variant", "Long tail eating warehouse space", "Most revenue from a small share of SKUs"]'::jsonb, '["fashion_apparel"]'::jsonb),
  ('FSH-011', 'Vendor Base Unmanaged at Scale', 'Several units are producing now with different quality, prices and lead times, and no way to compare them.', 'Operations & Systems', 'Fashion Vendor Management', 'external', 3, 6, 9, '["No comparison of vendors on price or quality", "Lead times vary widely between units", "No vendor scorecard", "Volume allocated by habit not performance", "Quality differs depending on who made it"]'::jsonb, '["fashion_apparel"]'::jsonb),
  ('FSH-012', 'Channel Conflict Across Store, Marketplace and Retail', 'The same product sells at different prices in different places and the channels are competing with each other.', 'Sales & Revenue', 'Fashion Channel Conflict', 'external', 4, 5, 9, '["Same product priced differently by channel", "Marketplace discounting undercutting own store", "Retail partners complaining about online price", "No price floor across channels", "Profit per channel unknown"]'::jsonb, '["fashion_apparel"]'::jsonb),
  ('FSH-013', 'Working Capital Locked in Inventory', 'Growth requires stock bought months ahead, so the business stays cash poor even when sales are strong.', 'Financial Management', 'Fashion Working Capital', 'external', 4, 7, 10, '["Months of stock held at all times", "Cash always tight despite good sales", "Stock bought long before it sells", "No limit on inventory months", "Growth increasing cash strain"]'::jsonb, '["fashion_apparel"]'::jsonb),
  ('FSH-014', 'Compliance, Labour and Sustainability Scrutiny', 'Larger buyers, marketplaces and customers now ask about factory conditions, labelling and material claims.', 'Operations & Systems', 'Fashion Compliance', 'external', 3, 6, 10, '["No factory compliance documentation", "Labelling requirements not fully met", "Material or sustainability claims unverified", "Buyers asking questions that cannot be answered", "No audit of manufacturing partners"]'::jsonb, '["fashion_apparel"]'::jsonb),
  ('FSH-015', 'Design Calendar Drives the Business Instead of Data', 'New collections launch on a fixed seasonal rhythm regardless of what actually sold last time.', 'Strategy & Planning', 'Fashion Range Planning', 'external', 2, 5, 9, '["Collections launched on calendar not data", "Past sell through not reviewed before designing", "Same collection size every season", "Best sellers not repeated", "Designer preference overriding sales evidence"]'::jsonb, '["fashion_apparel"]'::jsonb)
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
         t.primary_stage_group, '["fashion_apparel"]'::jsonb, z.v
  FROM (VALUES
  ('RC-FSH-001', 'No Manufacturer or Tailor Identified', 'Nobody has been found who could actually make the garments.', 'FSH-001', 'external', 'Operational', 0.70, 'Stage 0'),
  ('RC-FSH-002', 'Minimum Order Quantity Unknown', 'How many pieces a unit will insist on has never been asked.', 'FSH-001', 'external', 'Knowledge', 0.67, 'Stage 0'),
  ('RC-FSH-003', 'Fabric Sourcing Not Considered', 'Where the material comes from and what it costs is unknown.', 'FSH-001', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-FSH-004', 'Cost Per Piece Never Confirmed', 'What one finished garment costs to make has not been priced.', 'FSH-001', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-FSH-005', 'No Sample Ever Stitched', 'The design exists only on paper or screen.', 'FSH-001', 'external', 'Behavioural', 0.65, 'Stage 0'),
  ('RC-FSH-006', 'No Size Range Decided', 'Which sizes will be offered has not been settled.', 'FSH-002', 'external', 'Operational', 0.66, 'Stage 0'),
  ('RC-FSH-007', 'Fit Never Tested on Real People', 'No real body has worn the garment to check the fit.', 'FSH-002', 'external', 'Behavioural', 0.68, 'Stage 0'),
  ('RC-FSH-008', 'No Plan for Fit Returns', 'Nothing has been decided for when a garment does not fit.', 'FSH-002', 'external', 'Operational', 0.65, 'Stage 0'),
  ('RC-FSH-009', 'Size Chart Not Created', 'There is no measurement guide for a buyer to choose from.', 'FSH-002', 'external', 'Operational', 0.62, 'Stage 0'),
  ('RC-FSH-010', 'Assuming Standard Sizes Will Work', 'Believing generic sizing will fit the target customer.', 'FSH-002', 'external', 'Knowledge', 0.63, 'Stage 0'),
  ('RC-FSH-011', 'Too Many Designs Before Any Sale', 'A wide range is planned before one piece has been sold.', 'FSH-003', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-FSH-012', 'Multiple Categories at Launch', 'Several product types are planned at the same time.', 'FSH-003', 'external', 'Strategic', 0.66, 'Stage 0'),
  ('RC-FSH-013', 'Every Colour and Size Combination Planned', 'Stock is being spread thin across variants.', 'FSH-003', 'external', 'Operational', 0.65, 'Stage 0'),
  ('RC-FSH-014', 'No Single Hero Product', 'Nothing has been chosen as the one piece to lead with.', 'FSH-003', 'external', 'Strategic', 0.64, 'Stage 0'),
  ('RC-FSH-015', 'No Point of Difference From Existing Brands', 'Nothing sets this brand apart from what already sells.', 'FSH-004', 'external', 'Strategic', 0.70, 'Stage 0'),
  ('RC-FSH-016', 'Brand Described Only as Good Quality', 'Quality is offered as the differentiator, which everyone claims.', 'FSH-004', 'external', 'Strategic', 0.66, 'Stage 0'),
  ('RC-FSH-017', 'No Clear Customer This Is Made For', 'No specific person has been chosen to design for.', 'FSH-004', 'external', 'Strategic', 0.67, 'Stage 0'),
  ('RC-FSH-018', 'Design Copied Without a Distinct View', 'Styles are borrowed from others with no original point of view.', 'FSH-004', 'external', 'Behavioural', 0.63, 'Stage 0'),
  ('RC-FSH-019', 'Return Rate Not Measured', 'Nobody tracks what share of orders comes back.', 'FSH-005', 'external', 'Operational', 0.72, 'Stage 0â†’1'),
  ('RC-FSH-020', 'Return Reasons Never Collected', 'Customers are not asked why they returned, so the cause is never fixed.', 'FSH-005', 'external', 'Operational', 0.70, 'Stage 0â†’1'),
  ('RC-FSH-021', 'Size Chart Does Not Match the Garment', 'Published measurements differ from the actual stitched piece.', 'FSH-005', 'external', 'Operational', 0.69, 'Stage 0â†’1'),
  ('RC-FSH-022', 'Photos Not Showing Real Fit', 'Product images do not show how the garment actually sits.', 'FSH-005', 'external', 'Operational', 0.65, 'Stage 0â†’1'),
  ('RC-FSH-023', 'Cost of a Return Never Calculated', 'What one return really costs has never been worked out.', 'FSH-005', 'external', 'Knowledge', 0.67, 'Stage 0â†’1'),
  ('RC-FSH-024', 'Equal Quantities Bought Across Sizes', 'Every size is ordered in the same number regardless of demand.', 'FSH-006', 'external', 'Behavioural', 0.71, 'Stage 0â†’1'),
  ('RC-FSH-025', 'Best Selling Sizes Out of Stock', 'The sizes people actually want run out first and stay out.', 'FSH-006', 'external', 'Operational', 0.69, 'Stage 0â†’1'),
  ('RC-FSH-026', 'Slow Colours Repeatedly Reordered', 'Colours that do not sell keep being produced again.', 'FSH-006', 'external', 'Behavioural', 0.66, 'Stage 0â†’1'),
  ('RC-FSH-027', 'Cash Locked in Unsold Variants', 'Money sits in combinations nobody is buying.', 'FSH-006', 'external', 'Operational', 0.68, 'Stage 0â†’1'),
  ('RC-FSH-028', 'Size Ratio Never Analysed', 'Nobody has looked at which sizes actually sold.', 'FSH-006', 'external', 'Knowledge', 0.67, 'Stage 0â†’1'),
  ('RC-FSH-029', 'No Quality Check Before Accepting a Lot', 'Garments are accepted from the unit without inspection.', 'FSH-007', 'external', 'Operational', 0.72, 'Stage 0â†’1'),
  ('RC-FSH-030', 'No Written Specification Given to the Unit', 'The maker works from a verbal brief rather than a written spec.', 'FSH-007', 'external', 'Operational', 0.70, 'Stage 0â†’1'),
  ('RC-FSH-031', 'Fabric Substituted Without Notice', 'The unit changes material without telling anyone.', 'FSH-007', 'external', 'Operational', 0.67, 'Stage 0â†’1'),
  ('RC-FSH-032', 'Complaints About Stitching or Shrinkage', 'Customers are reporting quality failures after washing or wearing.', 'FSH-007', 'external', 'Operational', 0.65, 'Stage 0â†’1'),
  ('RC-FSH-033', 'Repeat Purchase Rate Never Measured', 'How many customers buy twice is not tracked.', 'FSH-008', 'external', 'Operational', 0.70, 'Stage 0â†’1'),
  ('RC-FSH-034', 'No Contact After Delivery', 'The relationship ends once the parcel arrives.', 'FSH-008', 'external', 'Behavioural', 0.68, 'Stage 0â†’1'),
  ('RC-FSH-035', 'No Reason Given to Buy Again', 'Nothing invites the customer back for a second purchase.', 'FSH-008', 'external', 'Strategic', 0.66, 'Stage 0â†’1'),
  ('RC-FSH-036', 'New Styles Not Shown to Past Buyers', 'Existing customers never hear about new arrivals.', 'FSH-008', 'external', 'Operational', 0.65, 'Stage 0â†’1'),
  ('RC-FSH-037', 'Growth Depends Entirely on New Customers', 'Every month starts from zero with no returning base.', 'FSH-008', 'external', 'Strategic', 0.67, 'Stage 0â†’1'),
  ('RC-FSH-038', 'Production Quantity Set on Optimism', 'Quantities are chosen on hope rather than past sales.', 'FSH-009', 'external', 'Behavioural', 0.71, 'Stage 0â†’1'),
  ('RC-FSH-039', 'Margin After Markdown Never Calculated', 'Nobody works out what is left once discounted stock is counted.', 'FSH-009', 'external', 'Knowledge', 0.69, 'Stage 0â†’1'),
  ('RC-FSH-040', 'Customers Waiting for the Sale', 'Buyers have learned to hold out for the seasonal discount.', 'FSH-009', 'external', 'Behavioural', 0.67, 'Stage 0â†’1'),
  ('RC-FSH-041', 'SKU Count Grown Without Review', 'Styles and variants keep being added while nothing is removed.', 'FSH-010', 'external', 'Behavioural', 0.71, 'Stage 1â†’10+'),
  ('RC-FSH-042', 'No Rule for Retiring a Style', 'There is no moment at which a style is formally dropped.', 'FSH-010', 'external', 'Operational', 0.68, 'Stage 1â†’10+'),
  ('RC-FSH-043', 'Forecasting Done Per Style Not Per Variant', 'Planning ignores that demand differs by size and colour.', 'FSH-010', 'external', 'Operational', 0.67, 'Stage 1â†’10+'),
  ('RC-FSH-044', 'Long Tail Eating Warehouse Space', 'Slow variants take up room and handling effort.', 'FSH-010', 'external', 'Operational', 0.66, 'Stage 1â†’10+'),
  ('RC-FSH-045', 'Most Revenue From Few SKUs', 'A small share of the catalogue carries nearly all sales.', 'FSH-010', 'external', 'Operational', 0.69, 'Stage 1â†’10+'),
  ('RC-FSH-046', 'No Comparison of Vendors', 'Units are never measured against each other on price or quality.', 'FSH-011', 'external', 'Operational', 0.71, 'Stage 1â†’10+'),
  ('RC-FSH-047', 'Lead Times Vary Widely', 'Delivery times differ so much that planning becomes guesswork.', 'FSH-011', 'external', 'Operational', 0.68, 'Stage 1â†’10+'),
  ('RC-FSH-048', 'No Vendor Scorecard', 'Nothing records how each unit actually performs.', 'FSH-011', 'external', 'Operational', 0.69, 'Stage 1â†’10+'),
  ('RC-FSH-049', 'Volume Allocated by Habit', 'Work goes to the same units regardless of how they perform.', 'FSH-011', 'external', 'Behavioural', 0.66, 'Stage 1â†’10+'),
  ('RC-FSH-050', 'Quality Differs by Who Made It', 'The same style varies depending on which unit produced it.', 'FSH-011', 'external', 'Operational', 0.67, 'Stage 1â†’10+'),
  ('RC-FSH-051', 'Same Product Priced Differently by Channel', 'Prices are inconsistent across store, marketplace and retail.', 'FSH-012', 'external', 'Strategic', 0.72, 'Stage 1â†’10+'),
  ('RC-FSH-052', 'Marketplace Discounting Undercutting Own Store', 'Platform discounts pull customers away from the direct channel.', 'FSH-012', 'external', 'Strategic', 0.69, 'Stage 1â†’10+'),
  ('RC-FSH-053', 'Retail Partners Complaining About Online Price', 'Stockists find they cannot compete with the brand own pricing.', 'FSH-012', 'external', 'Operational', 0.66, 'Stage 1â†’10+'),
  ('RC-FSH-054', 'No Price Floor Across Channels', 'No minimum price has been set that every channel must respect.', 'FSH-012', 'external', 'Strategic', 0.70, 'Stage 1â†’10+'),
  ('RC-FSH-055', 'Profit Per Channel Unknown', 'It is not known which channel actually makes money.', 'FSH-012', 'external', 'Knowledge', 0.68, 'Stage 1â†’10+'),
  ('RC-FSH-056', 'Months of Stock Held at All Times', 'A large amount of inventory sits waiting to sell.', 'FSH-013', 'external', 'Operational', 0.73, 'Stage 1â†’10+'),
  ('RC-FSH-057', 'Stock Bought Long Before It Sells', 'Money leaves months before revenue arrives.', 'FSH-013', 'external', 'Operational', 0.71, 'Stage 1â†’10+'),
  ('RC-FSH-058', 'No Limit on Inventory Months', 'Nothing caps how much stock the business will carry.', 'FSH-013', 'external', 'Strategic', 0.69, 'Stage 1â†’10+'),
  ('RC-FSH-059', 'Growth Increasing Cash Strain', 'Each growth step makes the cash position tighter.', 'FSH-013', 'external', 'Operational', 0.70, 'Stage 1â†’10+'),
  ('RC-FSH-060', 'No Factory Compliance Documentation', 'Nothing exists to show how or where garments are made.', 'FSH-014', 'external', 'Operational', 0.72, 'Stage 1â†’10+'),
  ('RC-FSH-061', 'Labelling Requirements Not Fully Met', 'Legal labelling and care information is incomplete.', 'FSH-014', 'external', 'Knowledge', 0.68, 'Stage 1â†’10+'),
  ('RC-FSH-062', 'Material or Sustainability Claims Unverified', 'Claims are made about fabric or ethics that cannot be proven.', 'FSH-014', 'external', 'Strategic', 0.70, 'Stage 1â†’10+'),
  ('RC-FSH-063', 'No Audit of Manufacturing Partners', 'Nobody has checked conditions at the units producing the goods.', 'FSH-014', 'external', 'Operational', 0.67, 'Stage 1â†’10+'),
  ('RC-FSH-064', 'Collections Launched on Calendar Not Data', 'Timing is set by season rather than by evidence.', 'FSH-015', 'external', 'Behavioural', 0.70, 'Stage 1â†’10+'),
  ('RC-FSH-065', 'Past Sell Through Not Reviewed', 'What actually sold last season is not studied before designing.', 'FSH-015', 'external', 'Operational', 0.69, 'Stage 1â†’10+'),
  ('RC-FSH-066', 'Best Sellers Not Repeated', 'Proven styles are dropped in favour of new ones each season.', 'FSH-015', 'external', 'Strategic', 0.67, 'Stage 1â†’10+')
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
         '["fashion_apparel"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-FSH-001', 'Who will actually stitch these clothes, and have you spoken to them?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-001', 'RC-FSH-001', 1, 'Stage 0'),
  ('S0-FSH-002', 'Do you know the smallest quantity a manufacturer will make for you?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-001', 'RC-FSH-002', 2, 'Stage 0'),
  ('S0-FSH-003', 'Where would the fabric come from, and what does it cost?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-001', 'RC-FSH-003', 2, 'Stage 0'),
  ('S0-FSH-004', 'Do you know what one finished piece would cost you to make?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-001', 'RC-FSH-004', 1, 'Stage 0'),
  ('S0-FSH-005', 'Has even one sample been stitched, or is it all still on paper?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-001', 'RC-FSH-005', 1, 'Stage 0'),
  ('S0-FSH-006', 'How many sizes will you make, and how did you decide?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-002', 'RC-FSH-006', 1, 'Stage 0'),
  ('S0-FSH-007', 'Has anyone actually worn your design and told you how it fits?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-002', 'RC-FSH-007', 1, 'Stage 0'),
  ('S0-FSH-008', 'What happens when a customer says it does not fit?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-002', 'RC-FSH-008', 1, 'Stage 0'),
  ('S0-FSH-009', 'Do you have a size chart a buyer can measure against?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-002', 'RC-FSH-009', 2, 'Stage 0'),
  ('S0-FSH-010', 'Are you assuming standard sizes will fit your customers?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-002', 'RC-FSH-010', 2, 'Stage 0'),
  ('S0-FSH-011', 'How many designs are you planning to launch with?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-003', 'RC-FSH-011', 1, 'Stage 0'),
  ('S0-FSH-012', 'Are you starting with one product type or several?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-003', 'RC-FSH-012', 2, 'Stage 0'),
  ('S0-FSH-013', 'Which single piece would you want to be known for?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-003', 'RC-FSH-014', 2, 'Stage 0'),
  ('S0-FSH-014', 'If someone can buy a similar piece elsewhere, why buy yours?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-004', 'RC-FSH-015', 1, 'Stage 0'),
  ('S0-FSH-015', 'Who exactly are you designing for, one specific person or anyone?', 'open_text', 'Idea & Validation', 'CORE', 'FSH-004', 'RC-FSH-017', 1, 'Stage 0'),
  ('S01-FSH-001', 'Out of every 100 orders, how many come back?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-005', 'RC-FSH-019', 2, 'Stage 0â†’1'),
  ('S01-FSH-002', 'Do you ask customers why they returned something?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-005', 'RC-FSH-020', 2, 'Stage 0â†’1'),
  ('S01-FSH-003', 'Have you measured a stitched garment against your own size chart?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-005', 'RC-FSH-021', 2, 'Stage 0â†’1'),
  ('S01-FSH-004', 'Do your photos show how the garment actually sits on a person?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-005', 'RC-FSH-022', 2, 'Stage 0â†’1'),
  ('S01-FSH-005', 'What does one return actually cost you in shipping and repacking?', 'open_text', 'Financial Management', 'CORE', 'FSH-005', 'RC-FSH-023', 3, 'Stage 0â†’1'),
  ('S01-FSH-006', 'Which sizes sell out first, and which are left over every time?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-006', 'RC-FSH-028', 2, 'Stage 0â†’1'),
  ('S01-FSH-007', 'Do you order the same quantity in every size?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-006', 'RC-FSH-024', 2, 'Stage 0â†’1'),
  ('S01-FSH-008', 'How often is your best selling size out of stock?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-006', 'RC-FSH-025', 2, 'Stage 0â†’1'),
  ('S01-FSH-009', 'Are you still reordering colours that never sold well?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-006', 'RC-FSH-026', 2, 'Stage 0â†’1'),
  ('S01-FSH-010', 'How much money is sitting in stock that is not selling?', 'open_text', 'Financial Management', 'CORE', 'FSH-006', 'RC-FSH-027', 2, 'Stage 0â†’1'),
  ('S01-FSH-011', 'Does the same style come out the same in every batch?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-007', 'RC-FSH-029', 2, 'Stage 0â†’1'),
  ('S01-FSH-012', 'Does your manufacturer get a written specification or a verbal brief?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-007', 'RC-FSH-030', 2, 'Stage 0â†’1'),
  ('S01-FSH-013', 'Has a unit ever changed the fabric without telling you?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-007', 'RC-FSH-031', 2, 'Stage 0â†’1'),
  ('S01-FSH-014', 'What do customers complain about most after wearing or washing?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-007', 'RC-FSH-032', 2, 'Stage 0â†’1'),
  ('S01-FSH-015', 'Out of your last 100 orders, how many were repeat customers?', 'open_text', 'Sales & Revenue', 'CORE', 'FSH-008', 'RC-FSH-033', 2, 'Stage 0â†’1'),
  ('S01-FSH-016', 'Does a customer hear anything from you after the parcel arrives?', 'open_text', 'Sales & Revenue', 'CORE', 'FSH-008', 'RC-FSH-034', 2, 'Stage 0â†’1'),
  ('S01-FSH-017', 'What reason does a customer have to buy from you again?', 'open_text', 'Sales & Revenue', 'CORE', 'FSH-008', 'RC-FSH-035', 2, 'Stage 0â†’1'),
  ('S01-FSH-018', 'Do your past buyers get told when new styles arrive?', 'open_text', 'Sales & Revenue', 'CORE', 'FSH-008', 'RC-FSH-036', 2, 'Stage 0â†’1'),
  ('S01-FSH-019', 'How much of your stock ends up sold at a discount?', 'open_text', 'Financial Management', 'CORE', 'FSH-009', 'RC-FSH-038', 2, 'Stage 0â†’1'),
  ('S01-FSH-020', 'After your end of season sale, what profit is actually left?', 'open_text', 'Financial Management', 'CORE', 'FSH-009', 'RC-FSH-039', 3, 'Stage 0â†’1'),
  ('S10-FSH-001', 'How many live SKUs do you have today, and how many did you have two years ago?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-010', 'RC-FSH-041', 2, 'Stage 1â†’10+'),
  ('S10-FSH-002', 'How many of your SKUs make up most of your sales?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-010', 'RC-FSH-045', 2, 'Stage 1â†’10+'),
  ('S10-FSH-003', 'Do you have any rule for dropping a style?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-010', 'RC-FSH-042', 2, 'Stage 1â†’10+'),
  ('S10-FSH-004', 'Do you forecast by style, or by each size and colour separately?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-010', 'RC-FSH-043', 3, 'Stage 1â†’10+'),
  ('S10-FSH-005', 'How much warehouse space is taken up by slow moving variants?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-010', 'RC-FSH-044', 2, 'Stage 1â†’10+'),
  ('S10-FSH-006', 'How do your units compare on price, quality and delivery time?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-011', 'RC-FSH-046', 2, 'Stage 1â†’10+'),
  ('S10-FSH-007', 'How much do lead times vary between your manufacturers?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-011', 'RC-FSH-047', 2, 'Stage 1â†’10+'),
  ('S10-FSH-008', 'Do you score your vendors on anything, or judge by feel?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-011', 'RC-FSH-048', 2, 'Stage 1â†’10+'),
  ('S10-FSH-009', 'How do you decide which unit gets which order?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-011', 'RC-FSH-049', 2, 'Stage 1â†’10+'),
  ('S10-FSH-010', 'Can a customer tell which unit made their garment from the quality?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-011', 'RC-FSH-050', 3, 'Stage 1â†’10+'),
  ('S10-FSH-011', 'Does the same product sell at different prices in different places?', 'open_text', 'Sales & Revenue', 'CORE', 'FSH-012', 'RC-FSH-051', 2, 'Stage 1â†’10+'),
  ('S10-FSH-012', 'Is the marketplace discounting below your own store price?', 'open_text', 'Sales & Revenue', 'CORE', 'FSH-012', 'RC-FSH-052', 2, 'Stage 1â†’10+'),
  ('S10-FSH-013', 'Have retail partners complained about your online pricing?', 'open_text', 'Sales & Revenue', 'CORE', 'FSH-012', 'RC-FSH-053', 2, 'Stage 1â†’10+'),
  ('S10-FSH-014', 'Is there a minimum price every channel has to respect?', 'open_text', 'Sales & Revenue', 'CORE', 'FSH-012', 'RC-FSH-054', 2, 'Stage 1â†’10+'),
  ('S10-FSH-015', 'Which channel actually makes you the most profit per piece?', 'open_text', 'Financial Management', 'CORE', 'FSH-012', 'RC-FSH-055', 3, 'Stage 1â†’10+'),
  ('S10-FSH-016', 'How many months of stock are you holding right now?', 'open_text', 'Financial Management', 'CORE', 'FSH-013', 'RC-FSH-056', 2, 'Stage 1â†’10+'),
  ('S10-FSH-017', 'How long before a sale does your money go out for that stock?', 'open_text', 'Financial Management', 'CORE', 'FSH-013', 'RC-FSH-057', 3, 'Stage 1â†’10+'),
  ('S10-FSH-018', 'Is there any limit on how much inventory you will carry?', 'open_text', 'Financial Management', 'CORE', 'FSH-013', 'RC-FSH-058', 2, 'Stage 1â†’10+'),
  ('S10-FSH-019', 'Does growing sales make your cash position better or worse?', 'open_text', 'Financial Management', 'CORE', 'FSH-013', 'RC-FSH-059', 3, 'Stage 1â†’10+'),
  ('S10-FSH-020', 'If a buyer asked about your factory labour conditions, could you answer?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-014', 'RC-FSH-060', 3, 'Stage 1â†’10+'),
  ('S10-FSH-021', 'Are your labels fully compliant with what is legally required?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-014', 'RC-FSH-061', 2, 'Stage 1â†’10+'),
  ('S10-FSH-022', 'Can you prove the fabric or sustainability claims you make?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-014', 'RC-FSH-062', 3, 'Stage 1â†’10+'),
  ('S10-FSH-023', 'Has anyone visited or audited the units making your clothes?', 'open_text', 'Operations & Systems', 'CORE', 'FSH-014', 'RC-FSH-063', 2, 'Stage 1â†’10+'),
  ('S10-FSH-024', 'Do you launch collections because the season says so, or because data says so?', 'open_text', 'Strategy & Planning', 'CORE', 'FSH-015', 'RC-FSH-064', 2, 'Stage 1â†’10+'),
  ('S10-FSH-025', 'Before designing a new collection, do you review what actually sold?', 'open_text', 'Strategy & Planning', 'CORE', 'FSH-015', 'RC-FSH-065', 2, 'Stage 1â†’10+')
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
  ('S0-FSH-001', 'technical-quality'),
  ('S0-FSH-002', 'technical-quality'),
  ('S0-FSH-003', 'technical-quality'),
  ('S0-FSH-004', 'technical-quality'),
  ('S0-FSH-005', 'technical-quality'),
  ('S0-FSH-006', 'technical-quality'),
  ('S0-FSH-007', 'technical-quality'),
  ('S0-FSH-008', 'technical-quality'),
  ('S0-FSH-009', 'technical-quality'),
  ('S0-FSH-010', 'technical-quality'),
  ('S0-FSH-011', 'problem-clarity'),
  ('S0-FSH-012', 'problem-clarity'),
  ('S0-FSH-013', 'problem-clarity'),
  ('S0-FSH-014', 'icp'),
  ('S0-FSH-015', 'icp'),
  ('S01-FSH-001', 'technical-quality'),
  ('S01-FSH-002', 'technical-quality'),
  ('S01-FSH-003', 'technical-quality'),
  ('S01-FSH-004', 'technical-quality'),
  ('S01-FSH-005', 'technical-quality'),
  ('S01-FSH-006', 'willingness-to-pay'),
  ('S01-FSH-007', 'willingness-to-pay'),
  ('S01-FSH-008', 'willingness-to-pay'),
  ('S01-FSH-009', 'willingness-to-pay'),
  ('S01-FSH-010', 'willingness-to-pay'),
  ('S01-FSH-011', 'technical-quality'),
  ('S01-FSH-012', 'technical-quality'),
  ('S01-FSH-013', 'technical-quality'),
  ('S01-FSH-014', 'technical-quality'),
  ('S01-FSH-015', 'customer-discovery'),
  ('S01-FSH-016', 'customer-discovery'),
  ('S01-FSH-017', 'customer-discovery'),
  ('S01-FSH-018', 'customer-discovery'),
  ('S01-FSH-019', 'willingness-to-pay'),
  ('S01-FSH-020', 'willingness-to-pay'),
  ('S10-FSH-001', 'technical-quality'),
  ('S10-FSH-002', 'technical-quality'),
  ('S10-FSH-003', 'technical-quality'),
  ('S10-FSH-004', 'technical-quality'),
  ('S10-FSH-005', 'technical-quality'),
  ('S10-FSH-006', 'technical-quality'),
  ('S10-FSH-007', 'technical-quality'),
  ('S10-FSH-008', 'technical-quality'),
  ('S10-FSH-009', 'technical-quality'),
  ('S10-FSH-010', 'technical-quality'),
  ('S10-FSH-011', 'willingness-to-pay'),
  ('S10-FSH-012', 'willingness-to-pay'),
  ('S10-FSH-013', 'willingness-to-pay'),
  ('S10-FSH-014', 'willingness-to-pay'),
  ('S10-FSH-015', 'willingness-to-pay'),
  ('S10-FSH-016', 'willingness-to-pay'),
  ('S10-FSH-017', 'willingness-to-pay'),
  ('S10-FSH-018', 'willingness-to-pay'),
  ('S10-FSH-019', 'willingness-to-pay'),
  ('S10-FSH-020', 'technical-quality'),
  ('S10-FSH-021', 'technical-quality'),
  ('S10-FSH-022', 'technical-quality'),
  ('S10-FSH-023', 'technical-quality'),
  ('S10-FSH-024', 'problem-clarity'),
  ('S10-FSH-025', 'problem-clarity')
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
         '["fashion_apparel"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-FSH-001', 'Ideation â€” Fashion Manufacturing Basics', 'FSH-001', '["RC-FSH-001", "RC-FSH-002"]'::jsonb, '[1]'::jsonb, 'Supply Chain', '["Visit or call one real manufacturing unit or tailor.", "Ask their minimum order quantity and price per piece.", "Write both numbers down before planning further."]'::jsonb, '[{"name": "One Real Manufacturer", "brief": "Getting a real price and minimum order from an actual unit."}]'::jsonb),
  ('INT-FSH-002', 'Ideation â€” Fashion Manufacturing Basics', 'FSH-001', '["RC-FSH-003", "RC-FSH-004"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Find one fabric supplier and get a price per metre.", "Add stitching, trims and finishing to get a cost per piece.", "Compare that with the price you had in mind."]'::jsonb, '[{"name": "Cost Per Piece", "brief": "Building a real garment cost from fabric, stitching and finishing."}]'::jsonb),
  ('INT-FSH-003', 'Ideation â€” Fashion Manufacturing Basics', 'FSH-001', '["RC-FSH-005"]'::jsonb, '[1]'::jsonb, 'Product Design', '["Get one sample stitched before anything else.", "Wear it, wash it and look at it honestly.", "Change the design based on what you see."]'::jsonb, '[{"name": "Sample First", "brief": "Turning a drawing into one real garment before committing."}]'::jsonb),
  ('INT-FSH-004', 'Ideation â€” Fashion Fit and Sizing', 'FSH-002', '["RC-FSH-006", "RC-FSH-009"]'::jsonb, '[1]'::jsonb, 'Product Design', '["Decide how many sizes you will offer at launch.", "Create a simple measurement chart for each.", "Keep the range small to start with."]'::jsonb, '[{"name": "Size Range and Chart", "brief": "A decided size range with real measurements buyers can check."}]'::jsonb),
  ('INT-FSH-005', 'Ideation â€” Fashion Fit and Sizing', 'FSH-002', '["RC-FSH-007", "RC-FSH-010"]'::jsonb, '[1]'::jsonb, 'Product Design', '["Have 5 real people of different builds wear the sample.", "Note where it pinches, gaps or hangs wrong.", "Fix the pattern before making anything in bulk."]'::jsonb, '[{"name": "Fit Test on Real Bodies", "brief": "Checking fit on actual people before production."}]'::jsonb),
  ('INT-FSH-006', 'Ideation â€” Fashion Fit and Sizing', 'FSH-002', '["RC-FSH-008"]'::jsonb, '[1]'::jsonb, 'Operations', '["Write your return and exchange rule in one line.", "Decide who pays the return shipping.", "Put it where the customer can see it before buying."]'::jsonb, '[{"name": "Simple Fit Return Rule", "brief": "One clear policy for when a garment does not fit."}]'::jsonb),
  ('INT-FSH-007', 'Ideation â€” Fashion Range Discipline', 'FSH-003', '["RC-FSH-011", "RC-FSH-012"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Cut your launch to a handful of styles.", "Pick one product category to start with.", "Add more only after something sells."]'::jsonb, '[{"name": "Small First Range", "brief": "Launching with few styles in one category instead of a full collection."}]'::jsonb),
  ('INT-FSH-008', 'Ideation â€” Fashion Range Discipline', 'FSH-003', '["RC-FSH-013", "RC-FSH-014"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Choose one piece to be your hero product.", "Limit colours and sizes on everything else.", "Put your money behind the hero first."]'::jsonb, '[{"name": "Pick a Hero Product", "brief": "Concentrating stock and attention on one leading piece."}]'::jsonb),
  ('INT-FSH-009', 'Ideation â€” Fashion Brand Differentiation', 'FSH-004', '["RC-FSH-015", "RC-FSH-016"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Look at 5 brands your customer already buys.", "Write one line on what you do that they do not.", "If it is only quality, keep looking."]'::jsonb, '[{"name": "One Line of Difference", "brief": "Naming a real difference beyond claiming better quality."}]'::jsonb),
  ('INT-FSH-010', 'Ideation â€” Fashion Brand Differentiation', 'FSH-004', '["RC-FSH-017", "RC-FSH-018"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Describe the one person you are designing for, in two lines.", "Note what they wear today and what frustrates them.", "Let that shape the design, not other brands."]'::jsonb, '[{"name": "Design for One Person", "brief": "Anchoring the brand in a specific customer rather than a trend."}]'::jsonb),
  ('INT-FSH-011', 'Validation to Traction â€” Fashion Returns', 'FSH-005', '["RC-FSH-019", "RC-FSH-020"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Record returns as a percentage of orders each week.", "Ask every returning customer one question about why.", "Group the reasons after 20 returns."]'::jsonb, '[{"name": "Return Rate and Reasons", "brief": "Measuring returns weekly and capturing why they happen."}]'::jsonb),
  ('INT-FSH-012', 'Validation to Traction â€” Fashion Returns', 'FSH-005', '["RC-FSH-021", "RC-FSH-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["Measure a real stitched garment and correct your size chart.", "Photograph the piece on a real person with their measurements listed.", "Update every listing with the corrected information."]'::jsonb, '[{"name": "Honest Sizing and Photos", "brief": "Matching published sizes and images to the real garment."}]'::jsonb),
  ('INT-FSH-013', 'Validation to Traction â€” Fashion Returns', 'FSH-005', '["RC-FSH-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Work out the full cost of one return.", "Multiply it by your monthly return count.", "Compare that number against your monthly profit."]'::jsonb, '[{"name": "Cost of a Return", "brief": "Putting a real rupee figure on every returned order."}]'::jsonb),
  ('INT-FSH-014', 'Validation to Traction â€” Fashion Inventory Mix', 'FSH-006', '["RC-FSH-024", "RC-FSH-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Look at what actually sold, size by size.", "Order your next lot in that ratio, not equally.", "Review the ratio after every production run."]'::jsonb, '[{"name": "Buy by Real Size Ratio", "brief": "Ordering quantities from actual sales, not equal splits."}]'::jsonb),
  ('INT-FSH-015', 'Validation to Traction â€” Fashion Inventory Mix', 'FSH-006', '["RC-FSH-025", "RC-FSH-026", "RC-FSH-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["List every size and colour with units sold and units left.", "Stop reordering anything in the slow list.", "Clear that stock and put the cash into what sells."]'::jsonb, '[{"name": "Fast and Dead Variant Split", "brief": "Separating what sells from what sits, by size and colour."}]'::jsonb),
  ('INT-FSH-016', 'Validation to Traction â€” Fashion Quality Control', 'FSH-007', '["RC-FSH-029", "RC-FSH-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Check a sample from every lot before accepting it.", "Use a short checklist covering stitching, measurement and finish.", "Reject the lot if it fails, do not accept and hope."]'::jsonb, '[{"name": "Check Before You Accept", "brief": "A fixed inspection on every lot before it enters stock."}]'::jsonb),
  ('INT-FSH-017', 'Validation to Traction â€” Fashion Quality Control', 'FSH-007', '["RC-FSH-030", "RC-FSH-031"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Give the unit a written specification for every style.", "Include fabric, measurements, trims and finishing.", "Make any substitution require your approval in writing."]'::jsonb, '[{"name": "Written Spec Per Style", "brief": "A documented brief so every batch is made to the same standard."}]'::jsonb),
  ('INT-FSH-018', 'Validation to Traction â€” Fashion Repeat Purchase', 'FSH-008', '["RC-FSH-033", "RC-FSH-037"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Count how many of your last 100 orders were repeat buyers.", "Write that as a percentage.", "Set a target to improve it this quarter."]'::jsonb, '[{"name": "Repeat Rate Baseline", "brief": "Measuring repeat buying before trying to improve it."}]'::jsonb),
  ('INT-FSH-019', 'Validation to Traction â€” Fashion Repeat Purchase', 'FSH-008', '["RC-FSH-034", "RC-FSH-035"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Send one message a week after delivery.", "Ask how the fit was and give one reason to come back.", "Track how many return within a month."]'::jsonb, '[{"name": "Post Delivery Follow Up", "brief": "One planned message that reopens the customer relationship."}]'::jsonb),
  ('INT-FSH-020', 'Validation to Traction â€” Fashion Repeat Purchase', 'FSH-008', '["RC-FSH-036"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Build a list of everyone who has bought from you.", "Tell them first whenever new styles arrive.", "Measure what share of new launch sales come from that list."]'::jsonb, '[{"name": "Tell Past Buyers First", "brief": "Using existing customers as the first audience for every launch."}]'::jsonb),
  ('INT-FSH-021', 'Validation to Traction â€” Fashion Markdown Pressure', 'FSH-009', '["RC-FSH-038", "RC-FSH-039"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Set production quantity from last season actual sales.", "Calculate your margin after expected markdowns, not before.", "Produce less than you think you will sell."]'::jsonb, '[{"name": "Plan Quantity for Real Demand", "brief": "Sizing production so the season does not end in clearance."}]'::jsonb),
  ('INT-FSH-022', 'Validation to Traction â€” Fashion Markdown Pressure', 'FSH-009', '["RC-FSH-040"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["List how often you have discounted in the last year.", "Space sales further apart and cap the depth.", "Watch whether full price selling recovers."]'::jsonb, '[{"name": "Break the Discount Habit", "brief": "Reducing sale frequency so customers stop waiting for one."}]'::jsonb),
  ('INT-FSH-023', 'Growth to Maturity â€” Fashion SKU Control', 'FSH-010', '["RC-FSH-041", "RC-FSH-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["List every SKU with revenue for the last six months.", "Mark the bottom 20 percent by sales.", "Stop producing them and clear what is left."]'::jsonb, '[{"name": "Bottom Twenty Percent Cut", "brief": "Removing the weakest SKUs to free cash, space and attention."}]'::jsonb),
  ('INT-FSH-024', 'Growth to Maturity â€” Fashion SKU Control', 'FSH-010', '["RC-FSH-042", "RC-FSH-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write one rule for when a style gets retired.", "Review the full catalogue against it every season.", "Keep the range small enough to forecast properly."]'::jsonb, '[{"name": "Style Retirement Rule", "brief": "A standing rule so the range does not keep expanding."}]'::jsonb),
  ('INT-FSH-025', 'Growth to Maturity â€” Fashion SKU Control', 'FSH-010', '["RC-FSH-043"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Forecast demand for each size and colour, not just the style.", "Use last season actual sales per variant.", "Order to that, not to an even split."]'::jsonb, '[{"name": "Forecast by Variant", "brief": "Planning at size and colour level instead of style level."}]'::jsonb),
  ('INT-FSH-026', 'Growth to Maturity â€” Fashion Vendor Management', 'FSH-011', '["RC-FSH-046", "RC-FSH-048"]'::jsonb, '[5, 6, 7]'::jsonb, 'Supply Chain', '["Score every unit on price, quality and on time delivery.", "Update the scores after every order.", "Review them together each quarter."]'::jsonb, '[{"name": "Vendor Scorecard", "brief": "Measuring every unit on the same three things."}]'::jsonb),
  ('INT-FSH-027', 'Growth to Maturity â€” Fashion Vendor Management', 'FSH-011', '["RC-FSH-047", "RC-FSH-049", "RC-FSH-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Supply Chain', '["Shift volume towards the units that score best.", "Give weaker units a clear standard to meet or lose work.", "Record real lead times and plan from those."]'::jsonb, '[{"name": "Allocate by Performance", "brief": "Giving work to the units that actually perform, not by habit."}]'::jsonb),
  ('INT-FSH-028', 'Growth to Maturity â€” Fashion Channel Conflict', 'FSH-012', '["RC-FSH-051", "RC-FSH-054"]'::jsonb, '[5, 6, 7]'::jsonb, 'Sales', '["Set one minimum price every channel must respect.", "Write it into marketplace and retail agreements.", "Check compliance monthly."]'::jsonb, '[{"name": "One Price Floor", "brief": "A minimum price that holds across every channel."}]'::jsonb),
  ('INT-FSH-029', 'Growth to Maturity â€” Fashion Channel Conflict', 'FSH-012', '["RC-FSH-052", "RC-FSH-053", "RC-FSH-055"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Work out profit per piece for each channel after all fees and returns.", "Decide which channels you actually want to grow.", "Give retail partners terms they can compete with."]'::jsonb, '[{"name": "Profit by Channel", "brief": "Seeing true margin per channel before deciding where to push."}]'::jsonb),
  ('INT-FSH-030', 'Growth to Maturity â€” Fashion Working Capital', 'FSH-013', '["RC-FSH-056", "RC-FSH-058"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Measure how many months of stock you are holding.", "Set a ceiling your cash can comfortably carry.", "Do not order beyond it, even for a good price."]'::jsonb, '[{"name": "Inventory Months Ceiling", "brief": "Capping stock at what the cash position can actually fund."}]'::jsonb),
  ('INT-FSH-031', 'Growth to Maturity â€” Fashion Working Capital', 'FSH-013', '["RC-FSH-057", "RC-FSH-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Work out the gap between paying for stock and selling it.", "Negotiate longer terms with units or shorter production runs.", "Track whether growth is improving or worsening cash."]'::jsonb, '[{"name": "Close the Cash Gap", "brief": "Shortening the time between paying for stock and selling it."}]'::jsonb),
  ('INT-FSH-032', 'Growth to Maturity â€” Fashion Compliance', 'FSH-014', '["RC-FSH-060", "RC-FSH-063"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Collect basic documentation from every unit you use.", "Visit or audit the main ones at least once a year.", "Keep the records ready before a buyer asks."]'::jsonb, '[{"name": "Factory Documentation", "brief": "Having proof of where and how garments are made."}]'::jsonb),
  ('INT-FSH-033', 'Growth to Maturity â€” Fashion Compliance', 'FSH-014', '["RC-FSH-061", "RC-FSH-062"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Check your labels against what is legally required.", "Remove any fabric or sustainability claim you cannot prove.", "Get written confirmation from suppliers for claims you keep."]'::jsonb, '[{"name": "Labels and Claims Audit", "brief": "Making every label and claim legally correct and provable."}]'::jsonb),
  ('INT-FSH-034', 'Growth to Maturity â€” Fashion Range Planning', 'FSH-015', '["RC-FSH-064", "RC-FSH-065", "RC-FSH-066"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Review last season sell through before designing anything new.", "Repeat your best sellers instead of replacing them.", "Size the next collection from evidence, not the calendar."]'::jsonb, '[{"name": "Design From Sell Through", "brief": "Letting real sales shape the next collection size and mix."}]'::jsonb)
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
        ('Food & Beverage / FoodTech', 'foodtech', 'FNB', r"""-- ============================================================================
-- Ally :: Industry seed -- FOOD & BEVERAGE / FOODTECH (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 66 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: foodtech
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (FNB-001, RC-FNB-014, S0-FNB-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (wastage, consistency, aggregators, cold chain,
--            food safety at scale) starts at Stage 0->1.
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
  ('FNB-001', 'Food Licence and Safety Rules Not Known', 'Selling food legally needs a licence and basic hygiene compliance, and the founder does not yet know this applies.', 'Idea & Validation', 'FoodTech Licensing Basics', 'external', 3, 5, 9, '["No idea a food licence is needed", "Hygiene requirements unknown", "Assuming home cooking can be sold freely", "Labelling rules not considered", "No plan for who handles compliance"]'::jsonb, '["foodtech"]'::jsonb),
  ('FNB-002', 'No Idea Where It Will Be Cooked or Made', 'A recipe exists but no kitchen, unit or facility has been identified that can legally produce it.', 'Idea & Validation', 'FoodTech Production Basics', 'external', 3, 4, 8, '["No kitchen or production unit identified", "Cost of using a commercial kitchen unknown", "Assuming the home kitchen is enough", "Equipment needed never listed", "No idea of capacity per day"]'::jsonb, '["foodtech"]'::jsonb),
  ('FNB-003', 'Shelf Life and Storage Not Considered', 'Food spoils, and how long it lasts, how it is stored and how it travels has not been thought about.', 'Idea & Validation', 'FoodTech Shelf Life', 'external', 3, 5, 9, '["Shelf life never tested", "Storage conditions not decided", "No thought about transport and spoilage", "Packaging not chosen for food safety", "No plan for unsold or expired stock"]'::jsonb, '["foodtech"]'::jsonb),
  ('FNB-004', 'Recipe Works Small but Not at Scale', 'It tastes good made at home in small quantity, but nobody has checked whether it stays the same made in bulk.', 'Idea & Validation', 'FoodTech Recipe Scaling', 'external', 3, 4, 8, '["Only made in small home quantities", "Taste consistency at scale never tested", "Ingredient cost at volume unknown", "Recipe not written down in measurable terms", "Assuming a bigger batch behaves the same"]'::jsonb, '["foodtech"]'::jsonb),
  ('FNB-005', 'Wastage Eating the Margin', 'Unsold, expired and spoiled stock is destroying profit and nobody is measuring how much.', 'Operations & Systems', 'FoodTech Wastage', 'external', 3, 6, 9, '["Wastage percentage not measured", "Production quantity set on guesswork", "Expired stock discovered rather than planned for", "No use for near expiry stock", "Cost of waste never added to unit cost"]'::jsonb, '["foodtech"]'::jsonb),
  ('FNB-006', 'Taste and Quality Not Consistent', 'The same dish or product varies from batch to batch and from person to person making it.', 'Operations & Systems', 'FoodTech Consistency', 'external', 3, 6, 9, '["Taste varies between batches", "Different staff produce different results", "No standard recipe card in the kitchen", "Ingredients substituted without adjustment", "Customer complaints about inconsistency"]'::jsonb, '["foodtech"]'::jsonb),
  ('FNB-007', 'Delivery Partners Control the Business', 'Most orders come through delivery apps that take a large commission and own the customer relationship.', 'Sales & Revenue', 'FoodTech Aggregator Dependence', 'external', 4, 6, 9, '["Most orders from delivery platforms", "Commission eating most of the margin", "No direct ordering channel", "Customer details held by the platform", "Discounts demanded by the platform"]'::jsonb, '["foodtech"]'::jsonb),
  ('FNB-008', 'Cold Chain and Delivery Failures', 'Products arrive late, warm or damaged, and each failure costs a refund and a customer.', 'Operations & Systems', 'FoodTech Cold Chain', 'external', 3, 6, 9, '["Products arriving warm or spoiled", "No temperature control in transit", "Delivery time not tracked", "Complaints about condition on arrival", "No process when a delivery fails"]'::jsonb, '["foodtech"]'::jsonb),
  ('FNB-009', 'Ingredient Prices Move and Pricing Does Not', 'Raw material costs change constantly while the selling price stays fixed, quietly destroying margin.', 'Financial Management', 'FoodTech Input Cost Volatility', 'external', 4, 6, 9, '["Ingredient prices changing frequently", "Selling price unchanged for months", "Recipe cost not recalculated", "No supplier price agreements", "Margin per item unknown today"]'::jsonb, '["foodtech"]'::jsonb),
  ('FNB-010', 'Second Location or Kitchen Does Not Match the First', 'A new outlet or kitchen has opened and the food, service and standards are not the same as the original.', 'Operations & Systems', 'FoodTech Multi Site Consistency', 'external', 3, 6, 9, '["New location quality below the original", "Founder still needed at the first site", "Nothing written down to hand over", "Different suppliers used per site", "Customers noticing the difference"]'::jsonb, '["foodtech"]'::jsonb),
  ('FNB-011', 'Food Safety Risk Grows With Volume', 'More sites, staff and volume mean one hygiene failure could cause illness, closure or serious reputation damage.', 'Operations & Systems', 'FoodTech Safety at Scale', 'external', 3, 7, 10, '["No regular hygiene audits", "Staff food safety training informal", "No temperature or batch records kept", "No recall process if something goes wrong", "Licence renewals tracked ad hoc"]'::jsonb, '["foodtech"]'::jsonb),
  ('FNB-012', 'Kitchen Staff Attrition and Training', 'Cooks and kitchen staff leave often, taking skill with them, and each replacement lowers quality for weeks.', 'Team & Leadership', 'FoodTech Staffing', 'external', 5, 6, 9, '["High kitchen staff turnover", "Training done by watching others", "Quality dips after every departure", "No documented station procedures", "Skill concentrated in one or two people"]'::jsonb, '["foodtech"]'::jsonb),
  ('FNB-013', 'Supply Chain Fragility and Seasonality', 'Key ingredients depend on few suppliers and seasonal availability, and disruption stops production.', 'Operations & Systems', 'FoodTech Supply Risk', 'external', 3, 6, 10, '["Single supplier for key ingredients", "Seasonal shortages disrupt the menu", "No buffer stock for critical items", "Price and availability swing sharply", "No alternate supplier qualified"]'::jsonb, '["foodtech"]'::jsonb),
  ('FNB-014', 'Menu or Range Too Large to Run Well', 'The menu or product range has grown so wide that prep, stock and quality all suffer.', 'Operations & Systems', 'FoodTech Menu Control', 'external', 3, 5, 9, '["Menu grown without removing items", "Most revenue from a few items", "Prep time and stock spread thin", "Slow items still requiring dedicated ingredients", "No review of item level profitability"]'::jsonb, '["foodtech"]'::jsonb),
  ('FNB-015', 'Brand Reputation Rests on Reviews', 'Public ratings now drive most new customers, and a run of bad reviews can hit revenue within days.', 'Sales & Revenue', 'FoodTech Reputation Risk', 'external', 4, 6, 9, '["Most new customers come from ratings", "No process for responding to reviews", "Negative reviews not traced to a cause", "Rating drops noticed late", "No system for collecting positive feedback"]'::jsonb, '["foodtech"]'::jsonb)
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
         t.primary_stage_group, '["foodtech"]'::jsonb, z.v
  FROM (VALUES
  ('RC-FNB-001', 'Unaware a Food Licence Is Required', 'The founder does not know that selling food legally needs registration.', 'FNB-001', 'external', 'Knowledge', 0.72, 'Stage 0'),
  ('RC-FNB-002', 'Hygiene Requirements Unknown', 'What the law expects of a food handling space has never been checked.', 'FNB-001', 'external', 'Knowledge', 0.68, 'Stage 0'),
  ('RC-FNB-003', 'Assuming Home Cooking Can Be Sold Freely', 'Believing food made at home can be sold without any approval.', 'FNB-001', 'external', 'Knowledge', 0.67, 'Stage 0'),
  ('RC-FNB-004', 'Labelling Rules Not Considered', 'What must legally appear on the packet has not been looked at.', 'FNB-001', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-FNB-005', 'No Owner for Compliance', 'Nobody has been made responsible for licences and renewals.', 'FNB-001', 'external', 'Operational', 0.62, 'Stage 0'),
  ('RC-FNB-006', 'No Kitchen or Unit Identified', 'There is no approved place where the food could actually be made.', 'FNB-002', 'external', 'Operational', 0.70, 'Stage 0'),
  ('RC-FNB-007', 'Cost of a Commercial Kitchen Unknown', 'What renting or using a licensed kitchen costs has not been asked.', 'FNB-002', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-FNB-008', 'Assuming the Home Kitchen Is Enough', 'The plan relies on a domestic kitchen that may not qualify.', 'FNB-002', 'external', 'Knowledge', 0.67, 'Stage 0'),
  ('RC-FNB-009', 'Equipment Needed Never Listed', 'What machines or tools are required has not been worked out.', 'FNB-002', 'external', 'Operational', 0.63, 'Stage 0'),
  ('RC-FNB-010', 'Daily Capacity Unknown', 'How many units could be produced in a day has never been estimated.', 'FNB-002', 'external', 'Knowledge', 0.64, 'Stage 0'),
  ('RC-FNB-011', 'Shelf Life Never Tested', 'How long the product stays good has not been measured.', 'FNB-003', 'external', 'Operational', 0.71, 'Stage 0'),
  ('RC-FNB-012', 'Storage Conditions Not Decided', 'Whether it needs cold, dry or ambient storage is unsettled.', 'FNB-003', 'external', 'Operational', 0.67, 'Stage 0'),
  ('RC-FNB-013', 'Transport and Spoilage Not Thought About', 'How the product survives the journey has not been considered.', 'FNB-003', 'external', 'Operational', 0.68, 'Stage 0'),
  ('RC-FNB-014', 'Packaging Not Chosen for Food Safety', 'No packaging has been selected that protects and preserves.', 'FNB-003', 'external', 'Operational', 0.65, 'Stage 0'),
  ('RC-FNB-015', 'No Plan for Expired or Unsold Stock', 'What happens to food that does not sell in time is undecided.', 'FNB-003', 'external', 'Strategic', 0.63, 'Stage 0'),
  ('RC-FNB-016', 'Only Made in Small Home Quantities', 'The recipe has never left the domestic batch size.', 'FNB-004', 'external', 'Behavioural', 0.69, 'Stage 0'),
  ('RC-FNB-017', 'Taste Consistency at Scale Never Tested', 'Nobody has checked whether a large batch tastes the same.', 'FNB-004', 'external', 'Operational', 0.68, 'Stage 0'),
  ('RC-FNB-018', 'Recipe Not Written in Measurable Terms', 'Quantities are by feel, so nobody else could reproduce it.', 'FNB-004', 'external', 'Operational', 0.66, 'Stage 0'),
  ('RC-FNB-019', 'Wastage Percentage Not Measured', 'Nobody tracks how much food is thrown away each week.', 'FNB-005', 'external', 'Operational', 0.72, 'Stage 0â†’1'),
  ('RC-FNB-020', 'Production Quantity Set on Guesswork', 'How much to make is decided by feel rather than by demand data.', 'FNB-005', 'external', 'Behavioural', 0.70, 'Stage 0â†’1'),
  ('RC-FNB-021', 'Expiry Discovered Rather Than Planned', 'Stock nearing expiry is noticed too late to do anything with it.', 'FNB-005', 'external', 'Operational', 0.67, 'Stage 0â†’1'),
  ('RC-FNB-022', 'No Use for Near Expiry Stock', 'There is no discount, staff meal or donation route for ageing stock.', 'FNB-005', 'external', 'Strategic', 0.65, 'Stage 0â†’1'),
  ('RC-FNB-023', 'Cost of Waste Not in Unit Cost', 'Thrown away food is never added into the price of what does sell.', 'FNB-005', 'external', 'Knowledge', 0.68, 'Stage 0â†’1'),
  ('RC-FNB-024', 'No Standard Recipe Card in the Kitchen', 'Staff cook from memory rather than a fixed written recipe.', 'FNB-006', 'external', 'Operational', 0.72, 'Stage 0â†’1'),
  ('RC-FNB-025', 'Different Staff Produce Different Results', 'Output depends on who is on shift that day.', 'FNB-006', 'external', 'Operational', 0.70, 'Stage 0â†’1'),
  ('RC-FNB-026', 'Ingredients Substituted Without Adjustment', 'Replacements are used without changing quantities or method.', 'FNB-006', 'external', 'Operational', 0.67, 'Stage 0â†’1'),
  ('RC-FNB-027', 'No Taste Check Before Dispatch', 'Nothing is tasted or checked before it goes to a customer.', 'FNB-006', 'external', 'Operational', 0.66, 'Stage 0â†’1'),
  ('RC-FNB-028', 'Complaints About Inconsistency', 'Customers are reporting that it is not the same as last time.', 'FNB-006', 'external', 'Operational', 0.64, 'Stage 0â†’1'),
  ('RC-FNB-029', 'Most Orders From Delivery Platforms', 'Nearly all demand arrives through one or two apps.', 'FNB-007', 'external', 'Strategic', 0.73, 'Stage 0â†’1'),
  ('RC-FNB-030', 'Commission Eating Most of the Margin', 'Platform fees take a large share of every order.', 'FNB-007', 'external', 'Operational', 0.71, 'Stage 0â†’1'),
  ('RC-FNB-031', 'No Direct Ordering Channel', 'There is no way for a customer to order without the app.', 'FNB-007', 'external', 'Strategic', 0.69, 'Stage 0â†’1'),
  ('RC-FNB-032', 'Customer Details Held by the Platform', 'The brand cannot contact its own buyers.', 'FNB-007', 'external', 'Operational', 0.68, 'Stage 0â†’1'),
  ('RC-FNB-033', 'Discounts Demanded by the Platform', 'Participation in offers is effectively compulsory to stay visible.', 'FNB-007', 'external', 'Strategic', 0.65, 'Stage 0â†’1'),
  ('RC-FNB-034', 'No Temperature Control in Transit', 'Food travels without any way to keep it at the right temperature.', 'FNB-008', 'external', 'Operational', 0.71, 'Stage 0â†’1'),
  ('RC-FNB-035', 'Delivery Time Not Tracked', 'How long orders actually take to reach customers is unknown.', 'FNB-008', 'external', 'Operational', 0.68, 'Stage 0â†’1'),
  ('RC-FNB-036', 'Complaints About Condition on Arrival', 'Customers report food arriving warm, leaking or damaged.', 'FNB-008', 'external', 'Operational', 0.67, 'Stage 0â†’1'),
  ('RC-FNB-037', 'No Process When a Delivery Fails', 'Each failed delivery is handled differently and ad hoc.', 'FNB-008', 'external', 'Operational', 0.65, 'Stage 0â†’1'),
  ('RC-FNB-038', 'Recipe Cost Not Recalculated', 'What a dish costs to make has not been updated as prices moved.', 'FNB-009', 'external', 'Knowledge', 0.72, 'Stage 0â†’1'),
  ('RC-FNB-039', 'Selling Price Unchanged for Months', 'Prices stay fixed while input costs keep rising.', 'FNB-009', 'external', 'Behavioural', 0.70, 'Stage 0â†’1'),
  ('RC-FNB-040', 'No Supplier Price Agreements', 'Nothing has been negotiated to hold prices steady.', 'FNB-009', 'external', 'Strategic', 0.66, 'Stage 0â†’1'),
  ('RC-FNB-041', 'Nothing Written Down to Hand Over', 'The original site runs on knowledge that exists only in peoples heads.', 'FNB-010', 'external', 'Operational', 0.73, 'Stage 1â†’10+'),
  ('RC-FNB-042', 'Founder Still Needed at the First Site', 'The original outlet cannot run without the founder present.', 'FNB-010', 'external', 'Operational', 0.70, 'Stage 1â†’10+'),
  ('RC-FNB-043', 'Different Suppliers Used Per Site', 'Each location buys its own ingredients, so output differs.', 'FNB-010', 'external', 'Operational', 0.67, 'Stage 1â†’10+'),
  ('RC-FNB-044', 'New Location Opened Before the First Was Systemised', 'Expansion happened before the original was repeatable.', 'FNB-010', 'external', 'Strategic', 0.71, 'Stage 1â†’10+'),
  ('RC-FNB-045', 'Customers Noticing the Difference', 'Reviews and feedback show the sites are not the same.', 'FNB-010', 'external', 'Operational', 0.65, 'Stage 1â†’10+'),
  ('RC-FNB-046', 'No Regular Hygiene Audits', 'Nobody inspects the kitchens on a fixed schedule.', 'FNB-011', 'external', 'Operational', 0.74, 'Stage 1â†’10+'),
  ('RC-FNB-047', 'Staff Food Safety Training Informal', 'New staff learn hygiene by watching rather than being trained.', 'FNB-011', 'external', 'Operational', 0.71, 'Stage 1â†’10+'),
  ('RC-FNB-048', 'No Temperature or Batch Records', 'Nothing is logged that could trace a problem back to its source.', 'FNB-011', 'external', 'Operational', 0.72, 'Stage 1â†’10+'),
  ('RC-FNB-049', 'No Recall Process', 'There is no plan for pulling a bad batch back from customers.', 'FNB-011', 'external', 'Strategic', 0.70, 'Stage 1â†’10+'),
  ('RC-FNB-050', 'Licence Renewals Tracked Ad Hoc', 'Renewal dates are remembered rather than managed.', 'FNB-011', 'external', 'Operational', 0.66, 'Stage 1â†’10+'),
  ('RC-FNB-051', 'High Kitchen Staff Turnover', 'Cooks and helpers leave frequently.', 'FNB-012', 'external', 'Operational', 0.71, 'Stage 1â†’10+'),
  ('RC-FNB-052', 'Training Done by Watching Others', 'New staff copy whoever is nearby rather than a standard.', 'FNB-012', 'external', 'Operational', 0.69, 'Stage 1â†’10+'),
  ('RC-FNB-053', 'No Documented Station Procedures', 'Each station has no written method to work from.', 'FNB-012', 'external', 'Operational', 0.68, 'Stage 1â†’10+'),
  ('RC-FNB-054', 'Skill Concentrated in One or Two People', 'Key capability sits with very few individuals.', 'FNB-012', 'external', 'Operational', 0.70, 'Stage 1â†’10+'),
  ('RC-FNB-055', 'Quality Dips After Every Departure', 'Output falls noticeably whenever someone leaves.', 'FNB-012', 'external', 'Operational', 0.65, 'Stage 1â†’10+'),
  ('RC-FNB-056', 'Single Supplier for Key Ingredients', 'Critical inputs come from only one source.', 'FNB-013', 'external', 'Operational', 0.73, 'Stage 1â†’10+'),
  ('RC-FNB-057', 'Seasonal Shortages Disrupt the Menu', 'Items become unavailable at predictable times of year.', 'FNB-013', 'external', 'Operational', 0.68, 'Stage 1â†’10+'),
  ('RC-FNB-058', 'No Buffer Stock for Critical Items', 'Nothing is held back against a supply interruption.', 'FNB-013', 'external', 'Operational', 0.67, 'Stage 1â†’10+'),
  ('RC-FNB-059', 'No Alternate Supplier Qualified', 'No second source has been tested and approved.', 'FNB-013', 'external', 'Strategic', 0.70, 'Stage 1â†’10+'),
  ('RC-FNB-060', 'Menu Grown Without Removing Items', 'New dishes keep being added and nothing is taken off.', 'FNB-014', 'external', 'Behavioural', 0.70, 'Stage 1â†’10+'),
  ('RC-FNB-061', 'Most Revenue From a Few Items', 'A small part of the menu carries nearly all sales.', 'FNB-014', 'external', 'Operational', 0.69, 'Stage 1â†’10+'),
  ('RC-FNB-062', 'Slow Items Requiring Dedicated Ingredients', 'Rarely ordered dishes force stock that mostly goes to waste.', 'FNB-014', 'external', 'Operational', 0.68, 'Stage 1â†’10+'),
  ('RC-FNB-063', 'No Item Level Profitability Review', 'Nobody knows which dishes make money and which lose it.', 'FNB-014', 'external', 'Knowledge', 0.71, 'Stage 1â†’10+'),
  ('RC-FNB-064', 'Most New Customers Come From Ratings', 'Demand depends heavily on public review scores.', 'FNB-015', 'external', 'Strategic', 0.71, 'Stage 1â†’10+'),
  ('RC-FNB-065', 'No Process for Responding to Reviews', 'Negative feedback goes unanswered and unexamined.', 'FNB-015', 'external', 'Operational', 0.68, 'Stage 1â†’10+'),
  ('RC-FNB-066', 'Negative Reviews Not Traced to a Cause', 'Complaints are read but never linked back to a kitchen or process issue.', 'FNB-015', 'external', 'Operational', 0.69, 'Stage 1â†’10+')
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
         '["foodtech"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-FNB-001', 'Do you know that selling food needs a government licence?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-001', 'RC-FNB-001', 1, 'Stage 0'),
  ('S0-FNB-002', 'Do you know what hygiene rules apply to the place where food is made?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-001', 'RC-FNB-002', 2, 'Stage 0'),
  ('S0-FNB-003', 'Are you planning to cook at home and sell it?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-001', 'RC-FNB-003', 1, 'Stage 0'),
  ('S0-FNB-004', 'Do you know what has to be printed on the packet by law?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-001', 'RC-FNB-004', 2, 'Stage 0'),
  ('S0-FNB-005', 'Where would the food actually be cooked or made, and is that place allowed to?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-002', 'RC-FNB-006', 1, 'Stage 0'),
  ('S0-FNB-006', 'Have you asked what a commercial kitchen would cost you?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-002', 'RC-FNB-007', 2, 'Stage 0'),
  ('S0-FNB-007', 'What equipment would you need that you do not have today?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-002', 'RC-FNB-009', 2, 'Stage 0'),
  ('S0-FNB-008', 'How many units could you make in a single day?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-002', 'RC-FNB-010', 2, 'Stage 0'),
  ('S0-FNB-009', 'How long does your product stay good after it is made?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-003', 'RC-FNB-011', 1, 'Stage 0'),
  ('S0-FNB-010', 'Does it need to be kept cold, or can it sit at room temperature?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-003', 'RC-FNB-012', 1, 'Stage 0'),
  ('S0-FNB-011', 'How would it reach a customer without spoiling?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-003', 'RC-FNB-013', 2, 'Stage 0'),
  ('S0-FNB-012', 'What packaging would keep it safe and fresh?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-003', 'RC-FNB-014', 2, 'Stage 0'),
  ('S0-FNB-013', 'What happens to food that does not sell before it expires?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-003', 'RC-FNB-015', 2, 'Stage 0'),
  ('S0-FNB-014', 'Has anyone made it in a big batch, or only small home portions?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-004', 'RC-FNB-016', 1, 'Stage 0'),
  ('S0-FNB-015', 'Is your recipe written down in exact measurements, or made by feel?', 'open_text', 'Idea & Validation', 'CORE', 'FNB-004', 'RC-FNB-018', 1, 'Stage 0'),
  ('S01-FNB-001', 'What percentage of what you make ends up thrown away?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-005', 'RC-FNB-019', 2, 'Stage 0â†’1'),
  ('S01-FNB-002', 'How do you decide how much to make each day?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-005', 'RC-FNB-020', 2, 'Stage 0â†’1'),
  ('S01-FNB-003', 'Do you know in advance which stock is close to expiry?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-005', 'RC-FNB-021', 2, 'Stage 0â†’1'),
  ('S01-FNB-004', 'What do you do with food that is about to expire?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-005', 'RC-FNB-022', 2, 'Stage 0â†’1'),
  ('S01-FNB-005', 'Is the cost of wasted food included in your pricing?', 'open_text', 'Financial Management', 'CORE', 'FNB-005', 'RC-FNB-023', 3, 'Stage 0â†’1'),
  ('S01-FNB-006', 'Is there a written recipe card in the kitchen, or is it from memory?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-006', 'RC-FNB-024', 2, 'Stage 0â†’1'),
  ('S01-FNB-007', 'Does the food taste the same whoever is on shift?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-006', 'RC-FNB-025', 2, 'Stage 0â†’1'),
  ('S01-FNB-008', 'When an ingredient is unavailable, what happens?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-006', 'RC-FNB-026', 2, 'Stage 0â†’1'),
  ('S01-FNB-009', 'Does anyone taste or check an order before it is dispatched?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-006', 'RC-FNB-027', 2, 'Stage 0â†’1'),
  ('S01-FNB-010', 'Do customers ever say it was different from last time?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-006', 'RC-FNB-028', 2, 'Stage 0â†’1'),
  ('S01-FNB-011', 'What share of your orders comes through delivery apps?', 'open_text', 'Sales & Revenue', 'CORE', 'FNB-007', 'RC-FNB-029', 2, 'Stage 0â†’1'),
  ('S01-FNB-012', 'After platform commission, how much is left on one order?', 'open_text', 'Financial Management', 'CORE', 'FNB-007', 'RC-FNB-030', 2, 'Stage 0â†’1'),
  ('S01-FNB-013', 'Can a customer order from you directly without the app?', 'open_text', 'Sales & Revenue', 'CORE', 'FNB-007', 'RC-FNB-031', 2, 'Stage 0â†’1'),
  ('S01-FNB-014', 'Do you have the contact details of your own customers?', 'open_text', 'Sales & Revenue', 'CORE', 'FNB-007', 'RC-FNB-032', 2, 'Stage 0â†’1'),
  ('S01-FNB-015', 'Do you join platform discount schemes by choice or because you have to?', 'open_text', 'Sales & Revenue', 'CORE', 'FNB-007', 'RC-FNB-033', 3, 'Stage 0â†’1'),
  ('S01-FNB-016', 'Does your food stay at the right temperature until it reaches the customer?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-008', 'RC-FNB-034', 2, 'Stage 0â†’1'),
  ('S01-FNB-017', 'Do you know how long your orders actually take to arrive?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-008', 'RC-FNB-035', 2, 'Stage 0â†’1'),
  ('S01-FNB-018', 'What do customers complain about most when food arrives?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-008', 'RC-FNB-036', 2, 'Stage 0â†’1'),
  ('S01-FNB-019', 'When did you last recalculate what a dish costs you to make?', 'open_text', 'Financial Management', 'CORE', 'FNB-009', 'RC-FNB-038', 2, 'Stage 0â†’1'),
  ('S01-FNB-020', 'When did you last change your prices, and why then?', 'open_text', 'Financial Management', 'CORE', 'FNB-009', 'RC-FNB-039', 2, 'Stage 0â†’1'),
  ('S10-FNB-001', 'Does your newest location match the quality of your first one?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-010', 'RC-FNB-045', 2, 'Stage 1â†’10+'),
  ('S10-FNB-002', 'Is there anything written down that a new site could run from?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-010', 'RC-FNB-041', 2, 'Stage 1â†’10+'),
  ('S10-FNB-003', 'Can your original site run properly without you there?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-010', 'RC-FNB-042', 3, 'Stage 1â†’10+'),
  ('S10-FNB-004', 'Do all your sites buy from the same suppliers?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-010', 'RC-FNB-043', 2, 'Stage 1â†’10+'),
  ('S10-FNB-005', 'Was the first site fully systemised before you opened the second?', 'open_text', 'Strategy & Planning', 'CORE', 'FNB-010', 'RC-FNB-044', 3, 'Stage 1â†’10+'),
  ('S10-FNB-006', 'How often is each kitchen actually inspected for hygiene?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-011', 'RC-FNB-046', 2, 'Stage 1â†’10+'),
  ('S10-FNB-007', 'What food safety training does a new kitchen hire receive?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-011', 'RC-FNB-047', 2, 'Stage 1â†’10+'),
  ('S10-FNB-008', 'Do you keep temperature or batch records anywhere?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-011', 'RC-FNB-048', 3, 'Stage 1â†’10+'),
  ('S10-FNB-009', 'If a bad batch reached customers, what would you do?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-011', 'RC-FNB-049', 3, 'Stage 1â†’10+'),
  ('S10-FNB-010', 'Who tracks your licence renewal dates?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-011', 'RC-FNB-050', 2, 'Stage 1â†’10+'),
  ('S10-FNB-011', 'How many kitchen staff have left in the last year?', 'open_text', 'Team & Leadership', 'CORE', 'FNB-012', 'RC-FNB-051', 2, 'Stage 1â†’10+'),
  ('S10-FNB-012', 'How does a new cook learn your way of making things?', 'open_text', 'Team & Leadership', 'CORE', 'FNB-012', 'RC-FNB-052', 2, 'Stage 1â†’10+'),
  ('S10-FNB-013', 'Does each station have a written procedure?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-012', 'RC-FNB-053', 2, 'Stage 1â†’10+'),
  ('S10-FNB-014', 'If your head cook left tomorrow, what would break?', 'open_text', 'Team & Leadership', 'CORE', 'FNB-012', 'RC-FNB-054', 3, 'Stage 1â†’10+'),
  ('S10-FNB-015', 'Does quality drop for a while after someone leaves?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-012', 'RC-FNB-055', 2, 'Stage 1â†’10+'),
  ('S10-FNB-016', 'Is there any key ingredient you can only get from one supplier?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-013', 'RC-FNB-056', 2, 'Stage 1â†’10+'),
  ('S10-FNB-017', 'Which items become hard to get at certain times of year?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-013', 'RC-FNB-057', 2, 'Stage 1â†’10+'),
  ('S10-FNB-018', 'How many days could you keep operating if a supplier stopped?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-013', 'RC-FNB-058', 3, 'Stage 1â†’10+'),
  ('S10-FNB-019', 'Have you ever tested a second supplier for your main ingredients?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-013', 'RC-FNB-059', 2, 'Stage 1â†’10+'),
  ('S10-FNB-020', 'How many items are on your menu now, and how many two years ago?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-014', 'RC-FNB-060', 2, 'Stage 1â†’10+'),
  ('S10-FNB-021', 'How many of your items make up most of your sales?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-014', 'RC-FNB-061', 2, 'Stage 1â†’10+'),
  ('S10-FNB-022', 'Which items need special ingredients but rarely get ordered?', 'open_text', 'Operations & Systems', 'CORE', 'FNB-014', 'RC-FNB-062', 2, 'Stage 1â†’10+'),
  ('S10-FNB-023', 'Do you know which dishes actually make money and which lose it?', 'open_text', 'Financial Management', 'CORE', 'FNB-014', 'RC-FNB-063', 3, 'Stage 1â†’10+'),
  ('S10-FNB-024', 'What share of your new customers come from ratings and reviews?', 'open_text', 'Sales & Revenue', 'CORE', 'FNB-015', 'RC-FNB-064', 2, 'Stage 1â†’10+'),
  ('S10-FNB-025', 'When a bad review comes in, what happens next?', 'open_text', 'Sales & Revenue', 'CORE', 'FNB-015', 'RC-FNB-065', 2, 'Stage 1â†’10+')
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
  ('S0-FNB-001', 'technical-quality'),
  ('S0-FNB-002', 'technical-quality'),
  ('S0-FNB-003', 'technical-quality'),
  ('S0-FNB-004', 'technical-quality'),
  ('S0-FNB-005', 'technical-quality'),
  ('S0-FNB-006', 'technical-quality'),
  ('S0-FNB-007', 'technical-quality'),
  ('S0-FNB-008', 'technical-quality'),
  ('S0-FNB-009', 'technical-quality'),
  ('S0-FNB-010', 'technical-quality'),
  ('S0-FNB-011', 'technical-quality'),
  ('S0-FNB-012', 'technical-quality'),
  ('S0-FNB-013', 'technical-quality'),
  ('S0-FNB-014', 'technical-quality'),
  ('S0-FNB-015', 'technical-quality'),
  ('S01-FNB-001', 'willingness-to-pay'),
  ('S01-FNB-002', 'willingness-to-pay'),
  ('S01-FNB-003', 'willingness-to-pay'),
  ('S01-FNB-004', 'willingness-to-pay'),
  ('S01-FNB-005', 'willingness-to-pay'),
  ('S01-FNB-006', 'technical-quality'),
  ('S01-FNB-007', 'technical-quality'),
  ('S01-FNB-008', 'technical-quality'),
  ('S01-FNB-009', 'technical-quality'),
  ('S01-FNB-010', 'technical-quality'),
  ('S01-FNB-011', 'channel-strategy'),
  ('S01-FNB-012', 'channel-strategy'),
  ('S01-FNB-013', 'channel-strategy'),
  ('S01-FNB-014', 'channel-strategy'),
  ('S01-FNB-015', 'channel-strategy'),
  ('S01-FNB-016', 'technical-quality'),
  ('S01-FNB-017', 'technical-quality'),
  ('S01-FNB-018', 'technical-quality'),
  ('S01-FNB-019', 'willingness-to-pay'),
  ('S01-FNB-020', 'willingness-to-pay'),
  ('S10-FNB-001', 'technical-quality'),
  ('S10-FNB-002', 'technical-quality'),
  ('S10-FNB-003', 'technical-quality'),
  ('S10-FNB-004', 'technical-quality'),
  ('S10-FNB-005', 'technical-quality'),
  ('S10-FNB-006', 'technical-quality'),
  ('S10-FNB-007', 'technical-quality'),
  ('S10-FNB-008', 'technical-quality'),
  ('S10-FNB-009', 'technical-quality'),
  ('S10-FNB-010', 'technical-quality'),
  ('S10-FNB-011', 'technical-quality'),
  ('S10-FNB-012', 'technical-quality'),
  ('S10-FNB-013', 'technical-quality'),
  ('S10-FNB-014', 'technical-quality'),
  ('S10-FNB-015', 'technical-quality'),
  ('S10-FNB-016', 'technical-quality'),
  ('S10-FNB-017', 'technical-quality'),
  ('S10-FNB-018', 'technical-quality'),
  ('S10-FNB-019', 'technical-quality'),
  ('S10-FNB-020', 'technical-quality'),
  ('S10-FNB-021', 'technical-quality'),
  ('S10-FNB-022', 'technical-quality'),
  ('S10-FNB-023', 'technical-quality'),
  ('S10-FNB-024', 'channel-strategy'),
  ('S10-FNB-025', 'channel-strategy')
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
         '["foodtech"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-FNB-001', 'Ideation â€” FoodTech Licensing Basics', 'FNB-001', '["RC-FNB-001", "RC-FNB-003"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Find out which food licence applies to what you want to sell.", "Check whether your intended kitchen qualifies for it.", "Write down the cost and the time it takes to get."]'::jsonb, '[{"name": "Find Your Food Licence", "brief": "Identifying the licence needed before cooking anything for sale."}]'::jsonb),
  ('INT-FNB-002', 'Ideation â€” FoodTech Licensing Basics', 'FNB-001', '["RC-FNB-002", "RC-FNB-005"]'::jsonb, '[1]'::jsonb, 'Compliance', '["Read the basic hygiene requirements for a food business.", "Note which ones your setup would fail today.", "Name one person responsible for compliance."]'::jsonb, '[{"name": "Hygiene Gap Check", "brief": "Comparing your setup against the basic hygiene rules."}]'::jsonb),
  ('INT-FNB-003', 'Ideation â€” FoodTech Licensing Basics', 'FNB-001', '["RC-FNB-004"]'::jsonb, '[1]'::jsonb, 'Compliance', '["List everything that must legally appear on a food label.", "Draft a sample label for your product.", "Get it checked before printing anything."]'::jsonb, '[{"name": "Legal Label Draft", "brief": "Building a label that meets legal requirements from the start."}]'::jsonb),
  ('INT-FNB-004', 'Ideation â€” FoodTech Production Basics', 'FNB-002', '["RC-FNB-006", "RC-FNB-008"]'::jsonb, '[1]'::jsonb, 'Operations', '["Visit one licensed commercial kitchen or unit.", "Ask what they require from you and what they charge.", "Compare that against using your own space legally."]'::jsonb, '[{"name": "One Real Kitchen Visit", "brief": "Seeing a licensed production space and its real terms."}]'::jsonb),
  ('INT-FNB-005', 'Ideation â€” FoodTech Production Basics', 'FNB-002', '["RC-FNB-007", "RC-FNB-009", "RC-FNB-010"]'::jsonb, '[1]'::jsonb, 'Operations', '["List every piece of equipment you would need.", "Work out how many units you could make in one day.", "Price the kitchen and equipment together."]'::jsonb, '[{"name": "Equipment and Capacity List", "brief": "Knowing what you need and how much you could make daily."}]'::jsonb),
  ('INT-FNB-006', 'Ideation â€” FoodTech Shelf Life', 'FNB-003', '["RC-FNB-011", "RC-FNB-012"]'::jsonb, '[1]'::jsonb, 'Product Design', '["Make a batch and keep samples in different conditions.", "Check them daily and record when quality drops.", "Use that number as your real shelf life."]'::jsonb, '[{"name": "Shelf Life Test", "brief": "Measuring how many days the product actually stays good."}]'::jsonb),
  ('INT-FNB-007', 'Ideation â€” FoodTech Shelf Life', 'FNB-003', '["RC-FNB-013", "RC-FNB-014"]'::jsonb, '[1]'::jsonb, 'Operations', '["Send one sample by the delivery method you plan to use.", "Open it on arrival and check condition.", "Choose packaging based on what survives the journey."]'::jsonb, '[{"name": "Travel Test", "brief": "Checking whether the product survives real delivery conditions."}]'::jsonb),
  ('INT-FNB-008', 'Ideation â€” FoodTech Shelf Life', 'FNB-003', '["RC-FNB-015"]'::jsonb, '[1]'::jsonb, 'Operations', '["Decide now what happens to stock nearing expiry.", "Set a rule, such as discount, donate or discard.", "Include that cost in your pricing."]'::jsonb, '[{"name": "Expiry Rule", "brief": "A decision made in advance for food that does not sell in time."}]'::jsonb),
  ('INT-FNB-009', 'Ideation â€” FoodTech Recipe Scaling', 'FNB-004', '["RC-FNB-016", "RC-FNB-017"]'::jsonb, '[1]'::jsonb, 'Product Design', '["Make one batch ten times your normal size.", "Taste it against the small batch honestly.", "Adjust the recipe until both match."]'::jsonb, '[{"name": "Ten Times Batch Test", "brief": "Checking whether the recipe holds up at a larger quantity."}]'::jsonb),
  ('INT-FNB-010', 'Ideation â€” FoodTech Recipe Scaling', 'FNB-004', '["RC-FNB-018"]'::jsonb, '[1]'::jsonb, 'Operations', '["Write the recipe in exact weights and times.", "Have someone else make it using only that sheet.", "Fix anything that was unclear to them."]'::jsonb, '[{"name": "Written Recipe Standard", "brief": "Documenting the recipe so anyone can reproduce it exactly."}]'::jsonb),
  ('INT-FNB-011', 'Validation to Traction â€” FoodTech Wastage', 'FNB-005', '["RC-FNB-019", "RC-FNB-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Weigh and record what gets thrown away each day.", "Convert it into a weekly rupee figure.", "Add that cost into your price per item."]'::jsonb, '[{"name": "Measure the Bin", "brief": "Turning daily wastage into a real number that enters pricing."}]'::jsonb),
  ('INT-FNB-012', 'Validation to Traction â€” FoodTech Wastage', 'FNB-005', '["RC-FNB-020", "RC-FNB-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Use last four weeks of sales to set daily production.", "Track what is nearing expiry every morning.", "Adjust tomorrow quantity from today leftovers."]'::jsonb, '[{"name": "Produce to Demand", "brief": "Setting daily quantities from real sales instead of guesswork."}]'::jsonb),
  ('INT-FNB-013', 'Validation to Traction â€” FoodTech Wastage', 'FNB-005', '["RC-FNB-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Decide one route for near expiry stock, such as discount or staff meals.", "Make it a standing rule, not a daily decision.", "Track how much is recovered that way."]'::jsonb, '[{"name": "Near Expiry Route", "brief": "One standing plan for stock that will not sell in time."}]'::jsonb),
  ('INT-FNB-014', 'Validation to Traction â€” FoodTech Consistency', 'FNB-006', '["RC-FNB-024", "RC-FNB-025"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Put a written recipe card at every station.", "Include exact weights, times and temperatures.", "Train every person on shift against it."]'::jsonb, '[{"name": "Recipe Card at Every Station", "brief": "A fixed written standard so output does not depend on who cooks."}]'::jsonb),
  ('INT-FNB-015', 'Validation to Traction â€” FoodTech Consistency', 'FNB-006', '["RC-FNB-026", "RC-FNB-027", "RC-FNB-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Write approved substitutes for every key ingredient.", "Add one taste or visual check before dispatch.", "Log complaints about consistency and review weekly."]'::jsonb, '[{"name": "Substitutes and Final Check", "brief": "Controlling substitutions and checking every order before it leaves."}]'::jsonb),
  ('INT-FNB-016', 'Validation to Traction â€” FoodTech Aggregator Dependence', 'FNB-007', '["RC-FNB-029", "RC-FNB-030"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Work out profit per order on the platform versus direct.", "Calculate what share of revenue the platform takes.", "Decide how much platform volume you actually want."]'::jsonb, '[{"name": "Platform Versus Direct Margin", "brief": "Comparing what each channel really leaves you per order."}]'::jsonb),
  ('INT-FNB-017', 'Validation to Traction â€” FoodTech Aggregator Dependence', 'FNB-007', '["RC-FNB-031", "RC-FNB-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Set up one simple direct ordering route, even WhatsApp.", "Collect customer contact details with consent on every direct order.", "Give customers a reason to order directly next time."]'::jsonb, '[{"name": "Build a Direct Channel", "brief": "Creating one ordering route the business owns outright."}]'::jsonb),
  ('INT-FNB-018', 'Validation to Traction â€” FoodTech Aggregator Dependence', 'FNB-007', '["RC-FNB-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Strategy', '["List every platform discount you are currently in.", "Work out what each one costs you per order.", "Exit the ones that lose money and measure the effect."]'::jsonb, '[{"name": "Audit Platform Discounts", "brief": "Checking which mandatory offers actually cost more than they bring."}]'::jsonb),
  ('INT-FNB-019', 'Validation to Traction â€” FoodTech Cold Chain', 'FNB-008', '["RC-FNB-034", "RC-FNB-036"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Test how warm a typical order gets on arrival.", "Add insulation, ice packs or shorter delivery radius.", "Retest after the change."]'::jsonb, '[{"name": "Temperature on Arrival Test", "brief": "Measuring real condition at the customer door and fixing it."}]'::jsonb),
  ('INT-FNB-020', 'Validation to Traction â€” FoodTech Cold Chain', 'FNB-008', '["RC-FNB-035", "RC-FNB-037"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Record delivery time for every order for two weeks.", "Set a maximum time you will accept.", "Write one process for handling a failed delivery."]'::jsonb, '[{"name": "Delivery Time and Failure Process", "brief": "Measuring delivery performance and a fixed route for failures."}]'::jsonb),
  ('INT-FNB-021', 'Validation to Traction â€” FoodTech Input Costs', 'FNB-009', '["RC-FNB-038", "RC-FNB-039"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Recalculate the cost of your top five items at todays prices.", "Compare against your selling price.", "Change price or portion where the margin has gone."]'::jsonb, '[{"name": "Recost Your Top Items", "brief": "Rebuilding dish costs at current ingredient prices."}]'::jsonb),
  ('INT-FNB-022', 'Validation to Traction â€” FoodTech Input Costs', 'FNB-009', '["RC-FNB-040"]'::jsonb, '[2, 3, 4]'::jsonb, 'Supply Chain', '["Approach your main suppliers for a fixed price period.", "Get at least one alternative quote for each key ingredient.", "Review ingredient prices monthly, not yearly."]'::jsonb, '[{"name": "Lock Supplier Prices", "brief": "Negotiating stability on the ingredients that move most."}]'::jsonb),
  ('INT-FNB-023', 'Growth to Maturity â€” FoodTech Multi Site', 'FNB-010', '["RC-FNB-041", "RC-FNB-044"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write down how the original site actually runs, step by step.", "Use that document to set up every new location.", "Do not open another site until it exists."]'::jsonb, '[{"name": "Systemise Before You Expand", "brief": "Documenting the first site so the next one can copy it."}]'::jsonb),
  ('INT-FNB-024', 'Growth to Maturity â€” FoodTech Multi Site', 'FNB-010', '["RC-FNB-042", "RC-FNB-043", "RC-FNB-045"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Centralise buying so all sites use the same suppliers.", "Spend a full week away from the first site and see what breaks.", "Fix whatever broke before expanding further."]'::jsonb, '[{"name": "Same Inputs, No Founder", "brief": "Common suppliers and a site that runs without the founder present."}]'::jsonb),
  ('INT-FNB-025', 'Growth to Maturity â€” FoodTech Safety at Scale', 'FNB-011', '["RC-FNB-046", "RC-FNB-047"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Set a fixed hygiene audit schedule for every kitchen.", "Give every new hire proper food safety training before they start.", "Keep a signed record of both."]'::jsonb, '[{"name": "Audit and Train on Schedule", "brief": "Regular hygiene checks and real training rather than informal habits."}]'::jsonb),
  ('INT-FNB-026', 'Growth to Maturity â€” FoodTech Safety at Scale', 'FNB-011', '["RC-FNB-048", "RC-FNB-049"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Start keeping temperature and batch records daily.", "Write a one page recall plan for a bad batch.", "Test that you could trace one dish back to its batch."]'::jsonb, '[{"name": "Records and Recall Plan", "brief": "Traceability and a written plan before something goes wrong."}]'::jsonb),
  ('INT-FNB-027', 'Growth to Maturity â€” FoodTech Safety at Scale', 'FNB-011', '["RC-FNB-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["List every licence with its renewal date.", "Set reminders 60 days before each one.", "Give one person responsibility for all of them."]'::jsonb, '[{"name": "Licence Calendar", "brief": "One owner and a dated list so nothing lapses."}]'::jsonb),
  ('INT-FNB-028', 'Growth to Maturity â€” FoodTech Staffing', 'FNB-012', '["RC-FNB-052", "RC-FNB-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Write a one page procedure for each kitchen station.", "Use it to train instead of learning by watching.", "Have new staff sign off once they can run it alone."]'::jsonb, '[{"name": "Station Procedures", "brief": "Written methods per station so training does not depend on observation."}]'::jsonb),
  ('INT-FNB-029', 'Growth to Maturity â€” FoodTech Staffing', 'FNB-012', '["RC-FNB-051", "RC-FNB-054", "RC-FNB-055"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Find out why people are leaving, by asking them.", "Cross train so no single person holds a critical skill.", "Fix the biggest reason before hiring more."]'::jsonb, '[{"name": "Retention and Cross Training", "brief": "Understanding departures and spreading critical skills wider."}]'::jsonb),
  ('INT-FNB-030', 'Growth to Maturity â€” FoodTech Supply Risk', 'FNB-013', '["RC-FNB-056", "RC-FNB-059"]'::jsonb, '[5, 6, 7]'::jsonb, 'Supply Chain', '["List every ingredient with only one supplier.", "Test a second source for each of the top three.", "Place one small trial order with each."]'::jsonb, '[{"name": "Second Source the Critical Few", "brief": "Qualifying a backup supplier for ingredients that could stop production."}]'::jsonb),
  ('INT-FNB-031', 'Growth to Maturity â€” FoodTech Supply Risk', 'FNB-013', '["RC-FNB-057", "RC-FNB-058"]'::jsonb, '[5, 6, 7]'::jsonb, 'Supply Chain', '["Map which items go short in which months.", "Hold buffer stock or plan a seasonal substitute.", "Tell customers in advance rather than removing items suddenly."]'::jsonb, '[{"name": "Seasonality Plan", "brief": "Planning around predictable shortages instead of reacting to them."}]'::jsonb),
  ('INT-FNB-032', 'Growth to Maturity â€” FoodTech Menu Control', 'FNB-014', '["RC-FNB-060", "RC-FNB-061"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["List every item with revenue for the last three months.", "Mark the bottom 20 percent.", "Remove them and watch what happens to prep time and waste."]'::jsonb, '[{"name": "Cut the Bottom of the Menu", "brief": "Removing the weakest items to simplify prep, stock and quality."}]'::jsonb),
  ('INT-FNB-033', 'Growth to Maturity â€” FoodTech Menu Control', 'FNB-014', '["RC-FNB-062", "RC-FNB-063"]'::jsonb, '[5, 6, 7]'::jsonb, 'Financial Clarity', '["Work out cost and profit for every item on the menu.", "Flag items that need dedicated ingredients but rarely sell.", "Keep, reprice or remove each one deliberately."]'::jsonb, '[{"name": "Item Level Profitability", "brief": "Knowing what each dish actually earns before deciding it stays."}]'::jsonb),
  ('INT-FNB-034', 'Growth to Maturity â€” FoodTech Reputation Risk', 'FNB-015', '["RC-FNB-064", "RC-FNB-065", "RC-FNB-066"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Give one person responsibility for reading and replying to reviews.", "Trace each negative review back to a kitchen or delivery cause.", "Ask happy customers to leave feedback so the score reflects reality."]'::jsonb, '[{"name": "Review Loop", "brief": "Answering reviews, tracing their cause and actively gathering good ones."}]'::jsonb)
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
        ('Gaming', 'gaming', 'GAM', r"""-- ============================================================================
-- Ally :: Industry seed -- GAMING (complete, all 3 stages)
-- ============================================================================
-- Contents : 15 problems, 67 root causes, 60 questions, 60 tag links,
--            34 interventions.  Industry tag: gaming
--
-- Note     : 67 root causes, not the usual 66 -- Stage 0->1 carries one extra.
--            Every root cause is linked to a problem and used by a question or
--            an intervention; nothing is orphaned.
--
-- Portable : NOTHING is linked by ID.  Every row is linked by its code
--            (GAM-001, RC-GAM-014, S0-GAM-006 ...), so this runs correctly
--            whatever the current ID sequence on the target database is.
--
-- Safety   : single transaction -- if anything fails, nothing is saved.
--            Re-running will fail on duplicate codes rather than duplicate data.
--
-- Note     : embeddings are inserted as zero-vector placeholders.  These rows
--            need a real embedding pass before semantic search will find them.
--
-- Note     : Stage 0 questions are deliberately simple and foundational.
--            Operating depth (retention, monetisation, stability, live ops,
--            platform and regulation risk) starts at Stage 0->1.
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
  ('GAM-001', 'No Idea How the Game Will Make Money', 'There is a game idea but no decision on whether money comes from a purchase price, ads, in game buying or something else.', 'Idea & Validation', 'Gaming Revenue Basics', 'external', 4, 4, 8, '["No revenue model chosen", "Assuming downloads turn into money", "No idea what players actually pay for", "Store commission not considered", "No plan if nobody spends"]'::jsonb, '["gaming"]'::jsonb),
  ('GAM-002', 'Scope Far Bigger Than the Team Can Build', 'The planned game is far larger than the people, time and money available to build it.', 'Idea & Validation', 'Gaming Scope Reality', 'external', 2, 5, 9, '["Feature list far beyond team capacity", "No estimate of build time", "Comparing the idea to large studio titles", "No smallest playable version defined", "Budget for art, sound and testing not counted"]'::jsonb, '["gaming"]'::jsonb),
  ('GAM-003', 'No Clear Player This Is Made For', 'No specific type of player has been chosen, so the game is being designed for everyone and nobody.', 'Idea & Validation', 'Gaming Player Clarity', 'external', 2, 4, 8, '["Target player described as everyone", "No idea what similar games this player already plays", "Platform not chosen", "Genre keeps changing", "No conversation with a real player yet"]'::jsonb, '["gaming"]'::jsonb),
  ('GAM-004', 'Nobody Outside the Team Has Played It', 'The game has never been put in front of a real player, so there is no evidence anyone finds it fun.', 'Idea & Validation', 'Gaming Playtest Basics', 'external', 3, 5, 9, '["No playable prototype yet", "Only the team has played it", "Fun assumed rather than tested", "No feedback from strangers", "Polish being added before fun is proven"]'::jsonb, '["gaming"]'::jsonb),
  ('GAM-005', 'Players Install and Leave Within Days', 'Downloads happen but almost nobody is still playing after the first week.', 'Sales & Revenue', 'Gaming Retention', 'external', 4, 6, 9, '["Day one and day seven retention not measured", "Most players never finish the tutorial", "No idea where players drop off", "Nothing bringing players back", "Growth measured only in installs"]'::jsonb, '["gaming"]'::jsonb),
  ('GAM-006', 'Almost Nobody Spends Money', 'The game has players but the share who pay anything is tiny, so revenue stays near zero.', 'Sales & Revenue', 'Gaming Monetisation', 'external', 4, 6, 9, '["Paying player share not measured", "Nothing compelling to buy", "Prices set by guesswork", "Purchase moment badly placed", "Revenue per player never calculated"]'::jsonb, '["gaming"]'::jsonb),
  ('GAM-007', 'Launch Was the Whole Marketing Plan', 'The game was released and then left to find players on its own, with no ongoing way to reach new ones.', 'Marketing & Growth', 'Gaming Launch and Growth', 'external', 4, 5, 9, '["No plan beyond the launch day", "No community built before release", "Store page treated as an afterthought", "Acquisition cost unknown", "Growth stalled after the first week"]'::jsonb, '["gaming"]'::jsonb),
  ('GAM-008', 'Bugs and Crashes Driving Players Away', 'Technical problems on real devices are losing players and ratings faster than new ones arrive.', 'Operations & Systems', 'Gaming Stability', 'external', 3, 6, 9, '["Crashes on common devices", "No crash reporting set up", "Bugs reported through reviews rather than tools", "No testing across device types", "Updates breaking things that worked"]'::jsonb, '["gaming"]'::jsonb),
  ('GAM-009', 'No Way to Know What Players Actually Do', 'There is no analytics in the game, so every decision about what to change is guesswork.', 'Operations & Systems', 'Gaming Analytics', 'external', 2, 5, 9, '["No analytics in the build", "Drop off points unknown", "Decisions based on opinion", "No way to test a change", "Player feedback only from reviews"]'::jsonb, '["gaming"]'::jsonb),
  ('GAM-010', 'Whole Business Rests on One Title', 'Almost all revenue comes from a single game, and its decline would take the studio with it.', 'Sales & Revenue', 'Gaming Title Concentration', 'external', 4, 7, 10, '["Nearly all revenue from one game", "Revenue from that title flattening or falling", "No second title in production", "No plan if the game declines", "Team fully committed to one product"]'::jsonb, '["gaming"]'::jsonb),
  ('GAM-011', 'Live Operations Now Never Stop', 'The game needs constant events, content and updates, and the team is permanently in delivery mode.', 'Operations & Systems', 'Gaming Live Ops', 'external', 3, 6, 9, '["Team permanently shipping events", "No content pipeline planned ahead", "Burnout from continuous releases", "Quality slipping under update pressure", "No buffer of ready content"]'::jsonb, '["gaming"]'::jsonb),
  ('GAM-012', 'Platform and Store Rules Control the Business', 'The store owns distribution, payment and discovery, and one policy or ranking change can cut revenue sharply.', 'Strategy & Planning', 'Gaming Platform Risk', 'external', 2, 7, 10, '["Nearly all revenue through one store", "Store policy changes affecting income", "Ranking drops with no explanation", "No direct player relationship", "Payment rules set entirely by the platform"]'::jsonb, '["gaming"]'::jsonb),
  ('GAM-013', 'Community and Moderation Getting Harder', 'The player community has grown large enough that toxicity, cheating and complaints need real management.', 'Operations & Systems', 'Gaming Community Management', 'external', 3, 5, 9, '["Toxic behaviour in game or channels", "Cheating affecting fair play", "No moderation policy or team", "Community managed by the founder personally", "Complaints handled inconsistently"]'::jsonb, '["gaming"]'::jsonb),
  ('GAM-014', 'Regulation Around Paid Mechanics Tightening', 'Rules on in game purchases, loot boxes, age ratings and real money gaming are changing and compliance is unclear.', 'Operations & Systems', 'Gaming Regulation', 'external', 3, 6, 10, '["Paid mechanics not checked against regulation", "Age rating requirements unclear", "Rules differ by country and not tracked", "Real money mechanics without legal review", "No plan if a mechanic becomes restricted"]'::jsonb, '["gaming"]'::jsonb),
  ('GAM-015', 'Talent Retention in a Poaching Market', 'Experienced developers and artists are being recruited away, and each departure delays the roadmap badly.', 'Team & Leadership', 'Gaming Talent Retention', 'external', 5, 6, 9, '["Key developers approached by competitors", "Knowledge concentrated in few people", "No documentation of systems", "Roadmap slips after each departure", "Compensation not compared to market"]'::jsonb, '["gaming"]'::jsonb)
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
         t.primary_stage_group, '["gaming"]'::jsonb, z.v
  FROM (VALUES
  ('RC-GAM-001', 'No Revenue Model Chosen', 'Nobody has decided how the game would actually earn money.', 'GAM-001', 'external', 'Strategic', 0.71, 'Stage 0'),
  ('RC-GAM-002', 'Assuming Downloads Turn Into Money', 'Installs are treated as if they automatically become income.', 'GAM-001', 'external', 'Psychological', 0.68, 'Stage 0'),
  ('RC-GAM-003', 'No Idea What Players Pay For', 'What players in this genre actually spend on has not been studied.', 'GAM-001', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-GAM-004', 'Store Commission Not Considered', 'The platform cut taken from every sale has not been factored in.', 'GAM-001', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-GAM-005', 'No Plan If Nobody Spends', 'There is no fallback if players download but never pay.', 'GAM-001', 'external', 'Strategic', 0.63, 'Stage 0'),
  ('RC-GAM-006', 'Feature List Beyond Team Capacity', 'The planned features need far more people than exist.', 'GAM-002', 'external', 'Strategic', 0.72, 'Stage 0'),
  ('RC-GAM-007', 'No Estimate of Build Time', 'How many months this would take has never been worked out.', 'GAM-002', 'external', 'Knowledge', 0.69, 'Stage 0'),
  ('RC-GAM-008', 'Comparing the Idea to Large Studio Titles', 'The benchmark is a game built by hundreds of people.', 'GAM-002', 'external', 'Psychological', 0.67, 'Stage 0'),
  ('RC-GAM-009', 'No Smallest Playable Version Defined', 'Nothing has been cut down to a version that could ship first.', 'GAM-002', 'external', 'Strategic', 0.68, 'Stage 0'),
  ('RC-GAM-010', 'Art, Sound and Testing Not Budgeted', 'Only coding is being counted, not the rest of production.', 'GAM-002', 'external', 'Knowledge', 0.65, 'Stage 0'),
  ('RC-GAM-011', 'Target Player Described as Everyone', 'No specific player type has been chosen to design for.', 'GAM-003', 'external', 'Strategic', 0.68, 'Stage 0'),
  ('RC-GAM-012', 'Similar Games Not Studied', 'What this player already plays has not been looked at.', 'GAM-003', 'external', 'Knowledge', 0.66, 'Stage 0'),
  ('RC-GAM-013', 'Platform Not Chosen', 'Whether this is mobile, PC or console is still undecided.', 'GAM-003', 'external', 'Strategic', 0.65, 'Stage 0'),
  ('RC-GAM-014', 'Genre Keeps Changing', 'The type of game shifts with each new idea.', 'GAM-003', 'external', 'Behavioural', 0.63, 'Stage 0'),
  ('RC-GAM-015', 'No Conversation With a Real Player', 'Nobody who would actually play this has been spoken to.', 'GAM-003', 'external', 'Behavioural', 0.64, 'Stage 0'),
  ('RC-GAM-016', 'No Playable Prototype Yet', 'Nothing exists that a person could actually pick up and play.', 'GAM-004', 'external', 'Behavioural', 0.72, 'Stage 0'),
  ('RC-GAM-017', 'Only the Team Has Played It', 'The only feedback comes from people who built it.', 'GAM-004', 'external', 'Behavioural', 0.70, 'Stage 0'),
  ('RC-GAM-018', 'Polish Before Fun Is Proven', 'Art and detail are being added before the core is tested.', 'GAM-004', 'external', 'Behavioural', 0.67, 'Stage 0'),
  ('RC-GAM-019', 'Retention Not Measured', 'Nobody tracks how many players come back after day one or day seven.', 'GAM-005', 'external', 'Operational', 0.73, 'Stage 0â†’1'),
  ('RC-GAM-020', 'Most Players Never Finish the Tutorial', 'The opening minutes lose people before the game begins.', 'GAM-005', 'external', 'Operational', 0.71, 'Stage 0â†’1'),
  ('RC-GAM-021', 'Drop Off Points Unknown', 'Where players quit has never been identified.', 'GAM-005', 'external', 'Knowledge', 0.69, 'Stage 0â†’1'),
  ('RC-GAM-022', 'Nothing Brings Players Back', 'There is no reason or reminder to return the next day.', 'GAM-005', 'external', 'Strategic', 0.68, 'Stage 0â†’1'),
  ('RC-GAM-023', 'Growth Measured Only in Installs', 'Success is judged by downloads rather than by players who stay.', 'GAM-005', 'external', 'Behavioural', 0.66, 'Stage 0â†’1'),
  ('RC-GAM-024', 'Paying Player Share Not Measured', 'What percentage of players spend anything is unknown.', 'GAM-006', 'external', 'Operational', 0.72, 'Stage 0â†’1'),
  ('RC-GAM-025', 'Nothing Compelling to Buy', 'What is on sale does not matter enough to players.', 'GAM-006', 'external', 'Strategic', 0.70, 'Stage 0â†’1'),
  ('RC-GAM-026', 'Prices Set by Guesswork', 'Price points were chosen without testing or comparison.', 'GAM-006', 'external', 'Behavioural', 0.67, 'Stage 0â†’1'),
  ('RC-GAM-027', 'Purchase Moment Badly Placed', 'The buying offer appears before the player cares about it.', 'GAM-006', 'external', 'Operational', 0.68, 'Stage 0â†’1'),
  ('RC-GAM-028', 'Revenue Per Player Never Calculated', 'Average earnings per player has not been worked out.', 'GAM-006', 'external', 'Knowledge', 0.66, 'Stage 0â†’1'),
  ('RC-GAM-029', 'No Plan Beyond Launch Day', 'Marketing stopped the day the game went live.', 'GAM-007', 'external', 'Strategic', 0.72, 'Stage 0â†’1'),
  ('RC-GAM-030', 'No Community Built Before Release', 'Nobody was waiting for the game when it launched.', 'GAM-007', 'external', 'Strategic', 0.70, 'Stage 0â†’1'),
  ('RC-GAM-031', 'Store Page Treated as an Afterthought', 'The listing, screenshots and description were rushed.', 'GAM-007', 'external', 'Operational', 0.67, 'Stage 0â†’1'),
  ('RC-GAM-032', 'Acquisition Cost Unknown', 'What it costs to get one new player has never been measured.', 'GAM-007', 'external', 'Knowledge', 0.68, 'Stage 0â†’1'),
  ('RC-GAM-033', 'Growth Stalled After the First Week', 'Nothing sustains installs once launch attention fades.', 'GAM-007', 'external', 'Operational', 0.65, 'Stage 0â†’1'),
  ('RC-GAM-034', 'Crashes on Common Devices', 'The game fails on hardware many players actually use.', 'GAM-008', 'external', 'Operational', 0.72, 'Stage 0â†’1'),
  ('RC-GAM-035', 'No Crash Reporting Set Up', 'Failures are invisible because nothing reports them.', 'GAM-008', 'external', 'Operational', 0.70, 'Stage 0â†’1'),
  ('RC-GAM-036', 'Bugs Found Through Reviews', 'Problems are learned about from angry players, not tools.', 'GAM-008', 'external', 'Operational', 0.67, 'Stage 0â†’1'),
  ('RC-GAM-037', 'No Testing Across Device Types', 'The build is only tested on the team own devices.', 'GAM-008', 'external', 'Operational', 0.69, 'Stage 0â†’1'),
  ('RC-GAM-038', 'Updates Breaking Working Features', 'New releases introduce failures in parts that were fine.', 'GAM-008', 'external', 'Operational', 0.65, 'Stage 0â†’1'),
  ('RC-GAM-039', 'No Analytics in the Build', 'The game sends back no information about how it is played.', 'GAM-009', 'external', 'Operational', 0.73, 'Stage 0â†’1'),
  ('RC-GAM-040', 'Decisions Based on Opinion', 'Changes are made on what the team feels rather than evidence.', 'GAM-009', 'external', 'Behavioural', 0.70, 'Stage 0â†’1'),
  ('RC-GAM-041', 'No Way to Test a Change', 'There is no method to compare a change against the old version.', 'GAM-009', 'external', 'Operational', 0.67, 'Stage 0â†’1'),
  ('RC-GAM-042', 'Nearly All Revenue From One Game', 'A single title carries the entire business.', 'GAM-010', 'external', 'Strategic', 0.74, 'Stage 1â†’10+'),
  ('RC-GAM-043', 'Revenue From That Title Flattening', 'The one earning game has stopped growing or is declining.', 'GAM-010', 'external', 'Operational', 0.70, 'Stage 1â†’10+'),
  ('RC-GAM-044', 'No Second Title in Production', 'Nothing is being built that could replace the first.', 'GAM-010', 'external', 'Strategic', 0.72, 'Stage 1â†’10+'),
  ('RC-GAM-045', 'No Plan If the Game Declines', 'Nothing has been decided for the day revenue drops.', 'GAM-010', 'external', 'Strategic', 0.69, 'Stage 1â†’10+'),
  ('RC-GAM-046', 'Team Fully Committed to One Product', 'Every person is tied to the single title.', 'GAM-010', 'external', 'Operational', 0.66, 'Stage 1â†’10+'),
  ('RC-GAM-047', 'Team Permanently Shipping Events', 'There is no gap between one release and the next.', 'GAM-011', 'external', 'Operational', 0.72, 'Stage 1â†’10+'),
  ('RC-GAM-048', 'No Content Pipeline Planned Ahead', 'Content is created just before it is needed.', 'GAM-011', 'external', 'Operational', 0.70, 'Stage 1â†’10+'),
  ('RC-GAM-049', 'Burnout From Continuous Releases', 'Sustained delivery pressure is exhausting the team.', 'GAM-011', 'external', 'Operational', 0.68, 'Stage 1â†’10+'),
  ('RC-GAM-050', 'Quality Slipping Under Update Pressure', 'Speed is being bought at the cost of polish and stability.', 'GAM-011', 'external', 'Operational', 0.67, 'Stage 1â†’10+'),
  ('RC-GAM-051', 'No Buffer of Ready Content', 'Nothing is finished and waiting in reserve.', 'GAM-011', 'external', 'Operational', 0.65, 'Stage 1â†’10+'),
  ('RC-GAM-052', 'Nearly All Revenue Through One Store', 'One platform handles distribution and payment for everything.', 'GAM-012', 'external', 'Strategic', 0.74, 'Stage 1â†’10+'),
  ('RC-GAM-053', 'Store Policy Changes Affecting Income', 'Platform rule changes directly move revenue.', 'GAM-012', 'external', 'Strategic', 0.71, 'Stage 1â†’10+'),
  ('RC-GAM-054', 'Ranking Drops With No Explanation', 'Discovery can fall without warning or reason given.', 'GAM-012', 'external', 'Operational', 0.67, 'Stage 1â†’10+'),
  ('RC-GAM-055', 'No Direct Player Relationship', 'The studio cannot reach its own players outside the store.', 'GAM-012', 'external', 'Operational', 0.70, 'Stage 1â†’10+'),
  ('RC-GAM-056', 'Payment Rules Set by the Platform', 'Pricing and payment terms are dictated entirely by the store.', 'GAM-012', 'external', 'Strategic', 0.66, 'Stage 1â†’10+'),
  ('RC-GAM-057', 'Toxic Behaviour in Game or Channels', 'Player conduct is driving others away.', 'GAM-013', 'external', 'Operational', 0.70, 'Stage 1â†’10+'),
  ('RC-GAM-058', 'Cheating Affecting Fair Play', 'Exploits or cheats are damaging the experience for honest players.', 'GAM-013', 'external', 'Operational', 0.69, 'Stage 1â†’10+'),
  ('RC-GAM-059', 'No Moderation Policy or Team', 'Nothing defines what is allowed or who enforces it.', 'GAM-013', 'external', 'Operational', 0.71, 'Stage 1â†’10+'),
  ('RC-GAM-060', 'Community Managed by the Founder', 'Player relations sit personally with the founder.', 'GAM-013', 'external', 'Operational', 0.66, 'Stage 1â†’10+'),
  ('RC-GAM-061', 'Paid Mechanics Not Checked Against Regulation', 'In game purchase design has never had a legal review.', 'GAM-014', 'external', 'Knowledge', 0.73, 'Stage 1â†’10+'),
  ('RC-GAM-062', 'Age Rating Requirements Unclear', 'What rating applies and what it demands is not understood.', 'GAM-014', 'external', 'Knowledge', 0.69, 'Stage 1â†’10+'),
  ('RC-GAM-063', 'Rules Differ by Country and Not Tracked', 'Regulation varies across markets and nobody follows the changes.', 'GAM-014', 'external', 'Knowledge', 0.70, 'Stage 1â†’10+'),
  ('RC-GAM-064', 'No Plan If a Mechanic Becomes Restricted', 'Nothing is prepared for a paid feature being banned or limited.', 'GAM-014', 'external', 'Strategic', 0.68, 'Stage 1â†’10+'),
  ('RC-GAM-065', 'Knowledge Concentrated in Few People', 'Critical systems are understood by only one or two developers.', 'GAM-015', 'external', 'Operational', 0.73, 'Stage 1â†’10+'),
  ('RC-GAM-066', 'No Documentation of Systems', 'How the game works internally exists mostly in memory.', 'GAM-015', 'external', 'Operational', 0.71, 'Stage 1â†’10+'),
  ('RC-GAM-067', 'Compensation Not Compared to Market', 'Nobody has checked pay against what competitors offer.', 'GAM-015', 'external', 'Knowledge', 0.67, 'Stage 1â†’10+')
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
         '["gaming"]'::jsonb, false, z.v
  FROM (VALUES
  ('S0-GAM-001', 'How would this game actually make money, a price, ads or in game buying?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-001', 'RC-GAM-001', 1, 'Stage 0'),
  ('S0-GAM-002', 'Do you think lots of downloads automatically means lots of money?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-001', 'RC-GAM-002', 1, 'Stage 0'),
  ('S0-GAM-003', 'Do you know what players of this kind of game usually spend on?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-001', 'RC-GAM-003', 2, 'Stage 0'),
  ('S0-GAM-004', 'Do you know how much the app store keeps from every sale?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-001', 'RC-GAM-004', 2, 'Stage 0'),
  ('S0-GAM-005', 'If players downloaded it but nobody paid, what would you do?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-001', 'RC-GAM-005', 2, 'Stage 0'),
  ('S0-GAM-006', 'How many people are building this, and how long do you think it will take?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-002', 'RC-GAM-007', 1, 'Stage 0'),
  ('S0-GAM-007', 'Is the game you are describing built by teams much bigger than yours?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-002', 'RC-GAM-008', 2, 'Stage 0'),
  ('S0-GAM-008', 'What is the smallest version of this you could actually finish?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-002', 'RC-GAM-009', 1, 'Stage 0'),
  ('S0-GAM-009', 'Have you counted art, sound and testing, or only the coding?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-002', 'RC-GAM-010', 2, 'Stage 0'),
  ('S0-GAM-010', 'Who exactly is this for, one specific type of player or anyone?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-003', 'RC-GAM-011', 1, 'Stage 0'),
  ('S0-GAM-011', 'What games does that player already spend their time on?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-003', 'RC-GAM-012', 2, 'Stage 0'),
  ('S0-GAM-012', 'Which platform will you launch on, and why that one?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-003', 'RC-GAM-013', 2, 'Stage 0'),
  ('S0-GAM-013', 'Has the type of game changed since you started thinking about it?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-003', 'RC-GAM-014', 2, 'Stage 0'),
  ('S0-GAM-014', 'Is there anything playable yet, even a rough version?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-004', 'RC-GAM-016', 1, 'Stage 0'),
  ('S0-GAM-015', 'Has anyone outside your team played it and told you honestly what they thought?', 'open_text', 'Idea & Validation', 'CORE', 'GAM-004', 'RC-GAM-017', 1, 'Stage 0'),
  ('S01-GAM-001', 'Out of 100 people who install, how many are still playing a week later?', 'open_text', 'Sales & Revenue', 'CORE', 'GAM-005', 'RC-GAM-019', 2, 'Stage 0â†’1'),
  ('S01-GAM-002', 'How many players actually finish your tutorial?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-005', 'RC-GAM-020', 2, 'Stage 0â†’1'),
  ('S01-GAM-003', 'Do you know at which point most players stop playing?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-005', 'RC-GAM-021', 2, 'Stage 0â†’1'),
  ('S01-GAM-004', 'What brings a player back the next day?', 'open_text', 'Sales & Revenue', 'CORE', 'GAM-005', 'RC-GAM-022', 2, 'Stage 0â†’1'),
  ('S01-GAM-005', 'Are you judging success by downloads or by players who stay?', 'open_text', 'Strategy & Planning', 'CORE', 'GAM-005', 'RC-GAM-023', 2, 'Stage 0â†’1'),
  ('S01-GAM-006', 'What share of your players have ever spent money?', 'open_text', 'Sales & Revenue', 'CORE', 'GAM-006', 'RC-GAM-024', 2, 'Stage 0â†’1'),
  ('S01-GAM-007', 'What exactly can a player buy, and why would they want it?', 'open_text', 'Sales & Revenue', 'CORE', 'GAM-006', 'RC-GAM-025', 2, 'Stage 0â†’1'),
  ('S01-GAM-008', 'How did you decide your prices?', 'open_text', 'Sales & Revenue', 'CORE', 'GAM-006', 'RC-GAM-026', 2, 'Stage 0â†’1'),
  ('S01-GAM-009', 'At what point in the game do you first ask for money?', 'open_text', 'Sales & Revenue', 'CORE', 'GAM-006', 'RC-GAM-027', 2, 'Stage 0â†’1'),
  ('S01-GAM-010', 'How much does an average player earn you?', 'open_text', 'Financial Management', 'CORE', 'GAM-006', 'RC-GAM-028', 3, 'Stage 0â†’1'),
  ('S01-GAM-011', 'What was your plan for getting players after launch day?', 'open_text', 'Marketing & Growth', 'CORE', 'GAM-007', 'RC-GAM-029', 2, 'Stage 0â†’1'),
  ('S01-GAM-012', 'Was anyone waiting for this game before it launched?', 'open_text', 'Marketing & Growth', 'CORE', 'GAM-007', 'RC-GAM-030', 2, 'Stage 0â†’1'),
  ('S01-GAM-013', 'How much time went into your store page and screenshots?', 'open_text', 'Marketing & Growth', 'CORE', 'GAM-007', 'RC-GAM-031', 2, 'Stage 0â†’1'),
  ('S01-GAM-014', 'What does it cost you to get one new player?', 'open_text', 'Marketing & Growth', 'CORE', 'GAM-007', 'RC-GAM-032', 3, 'Stage 0â†’1'),
  ('S01-GAM-015', 'What happened to your installs after the first week?', 'open_text', 'Marketing & Growth', 'CORE', 'GAM-007', 'RC-GAM-033', 2, 'Stage 0â†’1'),
  ('S01-GAM-016', 'Does your game crash on any common devices?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-008', 'RC-GAM-034', 2, 'Stage 0â†’1'),
  ('S01-GAM-017', 'Do you get told when the game crashes, or do you find out from reviews?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-008', 'RC-GAM-035', 2, 'Stage 0â†’1'),
  ('S01-GAM-018', 'How many different devices do you test on before releasing?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-008', 'RC-GAM-037', 2, 'Stage 0â†’1'),
  ('S01-GAM-019', 'Has an update ever broken something that was working before?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-008', 'RC-GAM-038', 2, 'Stage 0â†’1'),
  ('S01-GAM-020', 'Does your game send back any data about how people play it?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-009', 'RC-GAM-039', 2, 'Stage 0â†’1'),
  ('S10-GAM-001', 'What share of your revenue comes from one game?', 'open_text', 'Sales & Revenue', 'CORE', 'GAM-010', 'RC-GAM-042', 2, 'Stage 1â†’10+'),
  ('S10-GAM-002', 'Is revenue from that game still growing, flat or falling?', 'open_text', 'Sales & Revenue', 'CORE', 'GAM-010', 'RC-GAM-043', 2, 'Stage 1â†’10+'),
  ('S10-GAM-003', 'Is anything else in production that could earn?', 'open_text', 'Strategy & Planning', 'CORE', 'GAM-010', 'RC-GAM-044', 2, 'Stage 1â†’10+'),
  ('S10-GAM-004', 'If that game halved in revenue next year, what would you do?', 'open_text', 'Strategy & Planning', 'CORE', 'GAM-010', 'RC-GAM-045', 3, 'Stage 1â†’10+'),
  ('S10-GAM-005', 'Could you free anyone from the main title to start something new?', 'open_text', 'Team & Leadership', 'CORE', 'GAM-010', 'RC-GAM-046', 3, 'Stage 1â†’10+'),
  ('S10-GAM-006', 'Is there ever a gap between one release and the next?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-011', 'RC-GAM-047', 2, 'Stage 1â†’10+'),
  ('S10-GAM-007', 'How far ahead is your content planned?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-011', 'RC-GAM-048', 2, 'Stage 1â†’10+'),
  ('S10-GAM-008', 'How is the team holding up under the release schedule?', 'open_text', 'Team & Leadership', 'CORE', 'GAM-011', 'RC-GAM-049', 2, 'Stage 1â†’10+'),
  ('S10-GAM-009', 'Has quality slipped because of update pressure?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-011', 'RC-GAM-050', 2, 'Stage 1â†’10+'),
  ('S10-GAM-010', 'How much finished content is sitting ready right now?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-011', 'RC-GAM-051', 2, 'Stage 1â†’10+'),
  ('S10-GAM-011', 'What share of revenue goes through one store?', 'open_text', 'Strategy & Planning', 'CORE', 'GAM-012', 'RC-GAM-052', 2, 'Stage 1â†’10+'),
  ('S10-GAM-012', 'Has a store policy change ever hit your income?', 'open_text', 'Strategy & Planning', 'CORE', 'GAM-012', 'RC-GAM-053', 2, 'Stage 1â†’10+'),
  ('S10-GAM-013', 'If your ranking dropped tomorrow, how would you reach players?', 'open_text', 'Strategy & Planning', 'CORE', 'GAM-012', 'RC-GAM-055', 3, 'Stage 1â†’10+'),
  ('S10-GAM-014', 'Do you have any way to contact your players directly?', 'open_text', 'Strategy & Planning', 'CORE', 'GAM-012', 'RC-GAM-056', 2, 'Stage 1â†’10+'),
  ('S10-GAM-015', 'Is toxic behaviour driving players away from your game?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-013', 'RC-GAM-057', 2, 'Stage 1â†’10+'),
  ('S10-GAM-016', 'Is cheating affecting fair play for honest players?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-013', 'RC-GAM-058', 2, 'Stage 1â†’10+'),
  ('S10-GAM-017', 'Do you have written rules for what is allowed, and someone enforcing them?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-013', 'RC-GAM-059', 2, 'Stage 1â†’10+'),
  ('S10-GAM-018', 'Who handles your community day to day?', 'open_text', 'Team & Leadership', 'CORE', 'GAM-013', 'RC-GAM-060', 2, 'Stage 1â†’10+'),
  ('S10-GAM-019', 'Has anyone checked your paid mechanics against current regulation?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-014', 'RC-GAM-061', 3, 'Stage 1â†’10+'),
  ('S10-GAM-020', 'Do you know what age rating applies and what it requires?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-014', 'RC-GAM-062', 2, 'Stage 1â†’10+'),
  ('S10-GAM-021', 'Do the rules differ in the countries you sell in, and who tracks that?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-014', 'RC-GAM-063', 3, 'Stage 1â†’10+'),
  ('S10-GAM-022', 'If one of your paid features was restricted, what would happen?', 'open_text', 'Strategy & Planning', 'CORE', 'GAM-014', 'RC-GAM-064', 3, 'Stage 1â†’10+'),
  ('S10-GAM-023', 'If your lead developer left tomorrow, what would break?', 'open_text', 'Team & Leadership', 'CORE', 'GAM-015', 'RC-GAM-065', 3, 'Stage 1â†’10+'),
  ('S10-GAM-024', 'Is how your game works written down anywhere?', 'open_text', 'Operations & Systems', 'CORE', 'GAM-015', 'RC-GAM-066', 2, 'Stage 1â†’10+'),
  ('S10-GAM-025', 'Do you know what competitors pay people in the same roles?', 'open_text', 'Team & Leadership', 'CORE', 'GAM-015', 'RC-GAM-067', 2, 'Stage 1â†’10+')
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
  ('S0-GAM-001', 'willingness-to-pay'),
  ('S0-GAM-002', 'willingness-to-pay'),
  ('S0-GAM-003', 'willingness-to-pay'),
  ('S0-GAM-004', 'willingness-to-pay'),
  ('S0-GAM-005', 'willingness-to-pay'),
  ('S0-GAM-006', 'technical-quality'),
  ('S0-GAM-007', 'technical-quality'),
  ('S0-GAM-008', 'technical-quality'),
  ('S0-GAM-009', 'technical-quality'),
  ('S0-GAM-010', 'icp'),
  ('S0-GAM-011', 'icp'),
  ('S0-GAM-012', 'icp'),
  ('S0-GAM-013', 'icp'),
  ('S0-GAM-014', 'technical-quality'),
  ('S0-GAM-015', 'technical-quality'),
  ('S01-GAM-001', 'icp'),
  ('S01-GAM-002', 'icp'),
  ('S01-GAM-003', 'icp'),
  ('S01-GAM-004', 'icp'),
  ('S01-GAM-005', 'icp'),
  ('S01-GAM-006', 'willingness-to-pay'),
  ('S01-GAM-007', 'willingness-to-pay'),
  ('S01-GAM-008', 'willingness-to-pay'),
  ('S01-GAM-009', 'willingness-to-pay'),
  ('S01-GAM-010', 'willingness-to-pay'),
  ('S01-GAM-011', 'channel-strategy'),
  ('S01-GAM-012', 'channel-strategy'),
  ('S01-GAM-013', 'channel-strategy'),
  ('S01-GAM-014', 'channel-strategy'),
  ('S01-GAM-015', 'channel-strategy'),
  ('S01-GAM-016', 'technical-quality'),
  ('S01-GAM-017', 'technical-quality'),
  ('S01-GAM-018', 'technical-quality'),
  ('S01-GAM-019', 'technical-quality'),
  ('S01-GAM-020', 'technical-quality'),
  ('S10-GAM-001', 'willingness-to-pay'),
  ('S10-GAM-002', 'willingness-to-pay'),
  ('S10-GAM-003', 'willingness-to-pay'),
  ('S10-GAM-004', 'willingness-to-pay'),
  ('S10-GAM-005', 'willingness-to-pay'),
  ('S10-GAM-006', 'technical-quality'),
  ('S10-GAM-007', 'technical-quality'),
  ('S10-GAM-008', 'technical-quality'),
  ('S10-GAM-009', 'technical-quality'),
  ('S10-GAM-010', 'technical-quality'),
  ('S10-GAM-011', 'channel-strategy'),
  ('S10-GAM-012', 'channel-strategy'),
  ('S10-GAM-013', 'channel-strategy'),
  ('S10-GAM-014', 'channel-strategy'),
  ('S10-GAM-015', 'technical-quality'),
  ('S10-GAM-016', 'technical-quality'),
  ('S10-GAM-017', 'technical-quality'),
  ('S10-GAM-018', 'technical-quality'),
  ('S10-GAM-019', 'technical-quality'),
  ('S10-GAM-020', 'technical-quality'),
  ('S10-GAM-021', 'technical-quality'),
  ('S10-GAM-022', 'technical-quality'),
  ('S10-GAM-023', 'technical-quality'),
  ('S10-GAM-024', 'technical-quality'),
  ('S10-GAM-025', 'technical-quality')
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
         '["gaming"]'::jsonb, '[]'::jsonb
  FROM (VALUES
  ('INT-GAM-001', 'Ideation â€” Gaming Revenue Basics', 'GAM-001', '["RC-GAM-001", "RC-GAM-005"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Decide one way this game earns money.", "Write what a player would be paying for.", "Check the idea still works if very few players pay."]'::jsonb, '[{"name": "Pick One Money Model", "brief": "Choosing how the game earns before building it."}]'::jsonb),
  ('INT-GAM-002', 'Ideation â€” Gaming Revenue Basics', 'GAM-001', '["RC-GAM-002", "RC-GAM-004"]'::jsonb, '[1]'::jsonb, 'Financial Clarity', '["Find out what the store keeps from each sale.", "Work out how many paying players you would need to cover costs.", "Decide whether that number is realistic."]'::jsonb, '[{"name": "Players Needed to Break Even", "brief": "Turning store cuts and costs into a real player target."}]'::jsonb),
  ('INT-GAM-003', 'Ideation â€” Gaming Revenue Basics', 'GAM-001', '["RC-GAM-003"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["Look at 5 games your player already pays for.", "Note exactly what they are buying in each.", "Write what you would offer instead."]'::jsonb, '[{"name": "What Players Actually Buy", "brief": "Studying real spending in your genre before designing yours."}]'::jsonb),
  ('INT-GAM-004', 'Ideation â€” Gaming Scope Reality', 'GAM-002', '["RC-GAM-006", "RC-GAM-009"]'::jsonb, '[1]'::jsonb, 'Product Design', '["Cut the feature list to what makes the game fun.", "Define the smallest version you could finish and ship.", "Park everything else for later."]'::jsonb, '[{"name": "Smallest Shippable Game", "brief": "Reducing the plan to a version the team can actually finish."}]'::jsonb),
  ('INT-GAM-005', 'Ideation â€” Gaming Scope Reality', 'GAM-002', '["RC-GAM-007", "RC-GAM-010"]'::jsonb, '[1]'::jsonb, 'Operations', '["Estimate build time for each part, including art and sound.", "Add testing and fixing time on top.", "Compare the total against how long you can fund."]'::jsonb, '[{"name": "Honest Build Estimate", "brief": "Counting all production work, not just coding."}]'::jsonb),
  ('INT-GAM-006', 'Ideation â€” Gaming Scope Reality', 'GAM-002', '["RC-GAM-008"]'::jsonb, '[1]'::jsonb, 'Strategy', '["Find out how many people built the game you are comparing to.", "Compare that with your team size.", "Redefine what good looks like at your scale."]'::jsonb, '[{"name": "Compare Like With Like", "brief": "Benchmarking against games built by teams your size."}]'::jsonb),
  ('INT-GAM-007', 'Ideation â€” Gaming Player Clarity', 'GAM-003', '["RC-GAM-011", "RC-GAM-013"]'::jsonb, '[1]'::jsonb, 'Customer Clarity', '["Describe one specific player in two lines.", "Pick one platform to launch on.", "Design for that player and platform only."]'::jsonb, '[{"name": "One Player, One Platform", "brief": "Choosing a single player type and platform to start with."}]'::jsonb),
  ('INT-GAM-008', 'Ideation â€” Gaming Player Clarity', 'GAM-003', '["RC-GAM-012", "RC-GAM-014", "RC-GAM-015"]'::jsonb, '[1]'::jsonb, 'Market Validation', '["List the games your chosen player already plays.", "Talk to 10 of them about what they like and what annoys them.", "Lock your genre and stop changing it."]'::jsonb, '[{"name": "Study and Talk to Players", "brief": "Learning from real players before locking the design."}]'::jsonb),
  ('INT-GAM-009', 'Ideation â€” Gaming Playtest Basics', 'GAM-004', '["RC-GAM-016", "RC-GAM-017"]'::jsonb, '[1]'::jsonb, 'Product Design', '["Build a rough playable version, however ugly.", "Put it in front of 10 people who are not your friends.", "Watch them play without explaining anything."]'::jsonb, '[{"name": "Rough Prototype, Real Players", "brief": "Testing fun with strangers before anything is polished."}]'::jsonb),
  ('INT-GAM-010', 'Ideation â€” Gaming Playtest Basics', 'GAM-004', '["RC-GAM-018"]'::jsonb, '[1]'::jsonb, 'Product Design', '["Stop adding art and detail for now.", "Prove the core loop is fun with placeholder graphics.", "Only polish once people want to keep playing."]'::jsonb, '[{"name": "Fun Before Polish", "brief": "Proving the core is enjoyable before investing in looks."}]'::jsonb),
  ('INT-GAM-011', 'Validation to Traction â€” Gaming Retention', 'GAM-005', '["RC-GAM-019", "RC-GAM-023"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Measure how many players return on day one and day seven.", "Report that number every week instead of installs.", "Set a target to improve it before spending on ads."]'::jsonb, '[{"name": "Retention as the Real Number", "brief": "Judging the game by players who stay, not by downloads."}]'::jsonb),
  ('INT-GAM-012', 'Validation to Traction â€” Gaming Retention', 'GAM-005', '["RC-GAM-020", "RC-GAM-021"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["Find the exact point where most players quit.", "Watch 5 new players go through the opening minutes.", "Fix the biggest drop off before anything else."]'::jsonb, '[{"name": "Fix the First Ten Minutes", "brief": "Finding and repairing the point where new players leave."}]'::jsonb),
  ('INT-GAM-013', 'Validation to Traction â€” Gaming Retention', 'GAM-005', '["RC-GAM-022"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["Give players one clear reason to come back tomorrow.", "Make progress visible so returning feels worth it.", "Measure whether day two returns improve."]'::jsonb, '[{"name": "A Reason to Return", "brief": "Building one honest hook that brings players back."}]'::jsonb),
  ('INT-GAM-014', 'Validation to Traction â€” Gaming Monetisation', 'GAM-006', '["RC-GAM-024", "RC-GAM-028"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Measure what share of players spend anything.", "Work out average revenue per player.", "Track both every month."]'::jsonb, '[{"name": "Paying Share and Revenue Per Player", "brief": "The two numbers that show whether the game earns."}]'::jsonb),
  ('INT-GAM-015', 'Validation to Traction â€” Gaming Monetisation', 'GAM-006', '["RC-GAM-025", "RC-GAM-027"]'::jsonb, '[2, 3, 4]'::jsonb, 'Product Design', '["Ask players what they would happily pay for.", "Move the purchase offer to after they care about the game.", "Test one new thing to buy and measure the change."]'::jsonb, '[{"name": "Sell Something Players Want", "brief": "Offering the right thing at the right moment in the game."}]'::jsonb),
  ('INT-GAM-016', 'Validation to Traction â€” Gaming Monetisation', 'GAM-006', '["RC-GAM-026"]'::jsonb, '[2, 3, 4]'::jsonb, 'Sales', '["Look at what comparable games charge.", "Test two price points with different player groups.", "Keep the one that earns more per player."]'::jsonb, '[{"name": "Test Your Prices", "brief": "Choosing price points from evidence rather than guesswork."}]'::jsonb),
  ('INT-GAM-017', 'Validation to Traction â€” Gaming Launch and Growth', 'GAM-007', '["RC-GAM-029", "RC-GAM-033"]'::jsonb, '[2, 3, 4]'::jsonb, 'Marketing', '["Write a plan for getting players every month, not just at launch.", "Pick two channels and post consistently.", "Measure installs from each."]'::jsonb, '[{"name": "Growth After Launch Day", "brief": "A repeatable way to reach new players every month."}]'::jsonb),
  ('INT-GAM-018', 'Validation to Traction â€” Gaming Launch and Growth', 'GAM-007', '["RC-GAM-030", "RC-GAM-031"]'::jsonb, '[2, 3, 4]'::jsonb, 'Marketing', '["Build a community before your next release.", "Rewrite your store page with better screenshots and a clear first line.", "Compare install rate before and after."]'::jsonb, '[{"name": "Community and Store Page", "brief": "Having an audience ready and a listing that converts."}]'::jsonb),
  ('INT-GAM-019', 'Validation to Traction â€” Gaming Launch and Growth', 'GAM-007', '["RC-GAM-032"]'::jsonb, '[2, 3, 4]'::jsonb, 'Financial Clarity', '["Work out what you spend to get one new player.", "Compare it against what that player earns you.", "Stop any channel where the first number is bigger."]'::jsonb, '[{"name": "Cost Per Player Versus Value", "brief": "Checking that acquiring a player earns more than it costs."}]'::jsonb),
  ('INT-GAM-020', 'Validation to Traction â€” Gaming Stability', 'GAM-008', '["RC-GAM-034", "RC-GAM-035", "RC-GAM-036"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Add crash reporting to the build this week.", "Fix the crashes affecting the most players first.", "Stop learning about bugs from reviews."]'::jsonb, '[{"name": "Crash Reporting First", "brief": "Seeing failures in data instead of in angry reviews."}]'::jsonb),
  ('INT-GAM-021', 'Validation to Traction â€” Gaming Stability', 'GAM-008', '["RC-GAM-037", "RC-GAM-038"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Test every release on a spread of real devices.", "Keep a short checklist of features to retest each time.", "Do not ship an update that fails the checklist."]'::jsonb, '[{"name": "Device and Regression Checklist", "brief": "Testing across real hardware so updates do not break things."}]'::jsonb),
  ('INT-GAM-022', 'Validation to Traction â€” Gaming Analytics', 'GAM-009', '["RC-GAM-039", "RC-GAM-040", "RC-GAM-041"]'::jsonb, '[2, 3, 4]'::jsonb, 'Operations', '["Add basic analytics covering start, progress and drop off.", "Look at the data before deciding what to change next.", "Test one change at a time and compare the result."]'::jsonb, '[{"name": "See What Players Do", "brief": "Basic analytics so decisions rest on behaviour, not opinion."}]'::jsonb),
  ('INT-GAM-023', 'Growth to Maturity â€” Gaming Title Concentration', 'GAM-010', '["RC-GAM-042", "RC-GAM-043"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Chart revenue from your main title month by month.", "Decide whether it is still growing or past its peak.", "Set a target share of revenue that should come from elsewhere."]'::jsonb, '[{"name": "Read the Curve on Your Main Title", "brief": "Knowing where the one earning game sits in its life."}]'::jsonb),
  ('INT-GAM-024', 'Growth to Maturity â€” Gaming Title Concentration', 'GAM-010', '["RC-GAM-044", "RC-GAM-045", "RC-GAM-046"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Free a small team to prototype a second title.", "Fund it from the first game while it is still strong.", "Write what you would do if revenue halved."]'::jsonb, '[{"name": "Start the Second Title Early", "brief": "Building the next game while the current one still pays."}]'::jsonb),
  ('INT-GAM-025', 'Growth to Maturity â€” Gaming Live Ops', 'GAM-011', '["RC-GAM-047", "RC-GAM-049"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Map the release schedule for the next three months.", "Build real gaps into it.", "Protect those gaps even when something slips."]'::jsonb, '[{"name": "Gaps in the Schedule", "brief": "Planned breaks so continuous delivery does not exhaust the team."}]'::jsonb),
  ('INT-GAM-026', 'Growth to Maturity â€” Gaming Live Ops', 'GAM-011', '["RC-GAM-048", "RC-GAM-051"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Work at least two content drops ahead.", "Keep a buffer of finished content in reserve.", "Ship from the buffer, not from this week work."]'::jsonb, '[{"name": "Content Buffer", "brief": "Working ahead so releases never depend on this week."}]'::jsonb),
  ('INT-GAM-027', 'Growth to Maturity â€” Gaming Live Ops', 'GAM-011', '["RC-GAM-050"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Set a quality bar every release must meet.", "Give someone authority to delay a release that misses it.", "Accept a later date over a broken update."]'::jsonb, '[{"name": "Quality Gate on Releases", "brief": "One standard that a release must clear before shipping."}]'::jsonb),
  ('INT-GAM-028', 'Growth to Maturity â€” Gaming Platform Risk', 'GAM-012', '["RC-GAM-052", "RC-GAM-053"]'::jsonb, '[5, 6, 7]'::jsonb, 'Strategy', '["Work out what share of revenue sits with one store.", "Test a second platform or storefront.", "Track revenue by platform every month."]'::jsonb, '[{"name": "Second Platform", "brief": "Reducing how much of the business one store controls."}]'::jsonb),
  ('INT-GAM-029', 'Growth to Maturity â€” Gaming Platform Risk', 'GAM-012', '["RC-GAM-054", "RC-GAM-055", "RC-GAM-056"]'::jsonb, '[5, 6, 7]'::jsonb, 'Marketing', '["Build a direct channel to players, such as a newsletter or community.", "Collect contacts with consent wherever you can.", "Use it the next time ranking drops."]'::jsonb, '[{"name": "Own the Player Relationship", "brief": "A direct line to players that does not depend on the store."}]'::jsonb),
  ('INT-GAM-030', 'Growth to Maturity â€” Gaming Community Management', 'GAM-013', '["RC-GAM-057", "RC-GAM-059", "RC-GAM-060"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Write clear rules for what is allowed in your community.", "Give one person responsibility for enforcing them.", "Apply the same consequence every time."]'::jsonb, '[{"name": "Moderation Policy and Owner", "brief": "Written rules and one accountable person, not founder improvisation."}]'::jsonb),
  ('INT-GAM-031', 'Growth to Maturity â€” Gaming Community Management', 'GAM-013', '["RC-GAM-058"]'::jsonb, '[5, 6, 7]'::jsonb, 'Operations', '["Measure how widespread cheating actually is.", "Fix the exploits affecting the most players first.", "Tell the community what you did."]'::jsonb, '[{"name": "Tackle Cheating Openly", "brief": "Measuring exploits, fixing the worst and telling players."}]'::jsonb),
  ('INT-GAM-032', 'Growth to Maturity â€” Gaming Regulation', 'GAM-014', '["RC-GAM-061", "RC-GAM-062"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["Get your paid mechanics reviewed against current rules.", "Confirm what age rating applies and what it demands.", "Fix anything that would not survive scrutiny."]'::jsonb, '[{"name": "Review Paid Mechanics", "brief": "Checking purchase design and age rating against real regulation."}]'::jsonb),
  ('INT-GAM-033', 'Growth to Maturity â€” Gaming Regulation', 'GAM-014', '["RC-GAM-063", "RC-GAM-064"]'::jsonb, '[5, 6, 7]'::jsonb, 'Compliance', '["List the countries you earn from and their rules on paid mechanics.", "Give one person the job of tracking changes.", "Write what you would do if a mechanic was restricted."]'::jsonb, '[{"name": "Country Rules and a Fallback", "brief": "Tracking regulation by market and planning for a restriction."}]'::jsonb),
  ('INT-GAM-034', 'Growth to Maturity â€” Gaming Talent Retention', 'GAM-015', '["RC-GAM-065", "RC-GAM-066", "RC-GAM-067"]'::jsonb, '[5, 6, 7]'::jsonb, 'Team', '["Document the systems only one person understands.", "Cross train so no single departure stops the roadmap.", "Compare your pay against the market and close obvious gaps."]'::jsonb, '[{"name": "Spread Knowledge, Check Pay", "brief": "Documentation and cross training so one exit does not derail the roadmap."}]'::jsonb)
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
  (SELECT COUNT(*) FROM new_interventions) AS interventions_inserted;-- expect 34

-- ============================================================================
-- After running, the single result row above must read:  15 | 67 | 60 | 60 | 34
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

    expected_overrides = {
        "media_entertainment": {
            "interventions_inserted": 35,
        },
        "gaming": {
            "root_causes_inserted": 67,
        },
    }

    for label, industry_code, prefix, sql in seeds:
        result = dict(bind.exec_driver_sql(sql).mappings().one())

        expected = {
            **default_expected,
            **expected_overrides.get(industry_code, {}),
        }

        actual = {
            "problems_inserted": result.get("problems_inserted"),
            "root_causes_inserted": result.get("root_causes_inserted"),
            "questions_inserted": result.get("questions_inserted"),
            "tags_inserted": result.get(
                "tags_inserted", result.get("tag_links_inserted")
            ),
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
                        question_id,
                        industry_code,
                        stage_group,
                        applicability_type
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
    # Deliberately non-destructive. Once live diagnosis sessions can reference
    # these rows, automatic deletion would risk orphaning production history.
    raise RuntimeError(
        "Migration 91c4f0a2bd73 is intentionally irreversible. "
        "Roll back application code without downgrading this seed migration."
    )
