/**
 * data/onboardingQuestions.js — the Ally onboarding question set.
 *
 * Rewritten 2026-08-17 for the 4-section, path-branching onboarding redesign.
 * Onboarding runs entirely in the browser — no LLM, no API key, no agent. The
 * backend's only job is to persist the answers. Everything a founder is asked
 * lives in this file, so changing the flow never means touching a component.
 *
 * Two paths, decided by the Section 1 stage question and nothing else:
 *   PATH_1  Stage 0 (Ideation) only
 *   PATH_2  Stage 0→1 or Stage 1→10+ -- everyone beyond Stage 0
 *
 * This is ONE flow with conditional questions (each question declares which
 * path(s) it belongs to via `paths`), not two separate onboarding flows —
 * see effectiveQuestions() below, the single place that decision is made.
 */

export const PATH_1 = 'path1'; // Stage 0 / Ideation
export const PATH_2 = 'path2'; // Stage 0->1 or Stage 1->10+
const BOTH = [PATH_1, PATH_2];

/* ---------------------------------------------------------------------------
 * Stage picker (Section 1, Q2). Unchanged from the prior onboarding build --
 * founder_stages already contains exactly this 3-group / 8-stage structure
 * (confirmed against the live table before writing this), so nothing here
 * invents a parallel enum. `group` mirrors founder_stages.onboarding_label /
 * questions.primary_stage_group; `stage` resolves to stage_id via the name.
 * ------------------------------------------------------------------------- */
export const STAGE_GROUPS = [
  {
    key: 'stage_0',
    group: 'Stage 0',
    label: 'Just exploring ideas',
    hint: 'Still shaping what to build',
    path: PATH_1,
    stages: [
      { name: 'Ideation', order: 1, blurb: 'Exploring ideas, nothing built yet' },
    ],
  },
  {
    key: 'stage_0_1',
    group: 'Stage 0→1',
    label: 'Building from 0 → 1',
    hint: 'Turning the idea into something real people use',
    path: PATH_2,
    stages: [
      { name: 'Validation', order: 2, blurb: 'Testing whether people actually want this' },
      { name: 'Prototype / MVP', order: 3, blurb: 'Building the first working version' },
      { name: 'Early Traction', order: 4, blurb: 'First customers and early revenue' },
    ],
  },
  {
    key: 'stage_1_10',
    group: 'Stage 1→10+',
    label: 'Growing an established business',
    hint: 'Scaling something that already works',
    path: PATH_2,
    stages: [
      { name: 'Growth / Scaling', order: 5, blurb: 'Pushing hard on what already works' },
      { name: 'Expansion', order: 6, blurb: 'New markets, products or geographies' },
      { name: 'Maturity', order: 7, blurb: 'An established business to steward' },
      { name: 'Exit', order: 8, blurb: 'Preparing to hand it on or sell' },
    ],
  },
];

/** Flat lookup: stage name -> its group + order + path. */
export const STAGE_BY_NAME = Object.fromEntries(
  STAGE_GROUPS.flatMap((g) =>
    g.stages.map((s) => [s.name, { ...s, group: g.group, groupKey: g.key, path: g.path }]),
  ),
);

/** The 4 onboarding sections, used for the live side panel and step labels. */
export const SECTIONS = [
  { key: 'personal', label: 'Personal Details' },
  { key: 'where_you_are', label: 'Understanding Where You Are' },
  { key: 'what_you_know', label: 'What Do You Know?' },
  { key: 'final', label: 'Final Questions' },
];

/* ---------------------------------------------------------------------------
 * Question types:
 *   'stage'      two-step group -> stage picker (Section 1 Q2 only)
 *   'short'      one-line free text
 *   'long'       multi-line free text
 *   'url'        a single URL, validated + normalised server-side
 *   'chips'      multi-select chips, plus free text when the "other" option
 *                is picked (see otherValue/otherPlaceholder)
 *   'dropdown'   searchable single-select
 *   'multi'      multi-select checkboxes, uncapped unless `max` is set, plus
 *                free text when the "other" option is picked (same as chips)
 *   'single'     single-select cards
 *   'yesno'      a fixed set of Yes/No checks answered together as one screen
 *                (`items`), submitted as a single object, not one answer per
 *                item -- see the reality-check schema on the backend.
 *
 * `paths`: which path(s) this question is shown on. Filtered by
 * effectiveQuestions() once the founder's path is known from the stage
 * answer -- everything below this point is the single source of truth for
 * both paths; nothing here is a separate flow.
 * ------------------------------------------------------------------------- */
export const QUESTIONS = [
  /* === Section 1 — Personal Details (identical for both paths, except the
     conditional revenue question at the end) ============================ */
  {
    key: 'name',
    section: 'personal',
    field: 'full_name',
    label: 'Name',
    type: 'short',
    paths: BOTH,
    q: 'What would you like Ally to call you?',
    placeholder: 'Your name…',
  },
  /* Second, ahead of the optional social handle. Two reasons, and the first is
     not a preference:

     `GoXL_Stage_Adaptive_Diagnosis_Framework_2.docx` s9 asks for the stage
     "captured in the first 1-2 onboarding questions, since every downstream
     question bank and root-cause filter branches off it". It does: Founder DNA
     and Current Problem select their bank by stage group, the recommendation
     engine filters interventions by stage_id, the report picks its tone
     (Validator / Compass / Auditor) by stage, and the confidence model reads
     stage-adjusted root-cause priors. A founder with no stage gets the earliest
     bank, no tone at all, and no intervention filtering.

     And it is the only answer the rest of this flow branches on -- until it is
     given, effectiveQuestions() cannot narrow to a path, so asking anything
     path-specific before it is asking blind. It sits after `name` rather than
     first so the flow still opens on a person, not a taxonomy. */
  {
    key: 'stage',
    section: 'personal',
    field: 'stage',
    label: 'Entrepreneurial Stage',
    type: 'stage',
    paths: BOTH,
    q: 'Where are you in your entrepreneurial journey?',
  },
  {
    key: 'socialHandle',
    section: 'personal',
    field: 'linkedin_url',
    label: 'Social Handle',
    type: 'url',
    paths: BOTH,
    optional: true,
    q: "Where is your Instagram page or LinkedIn profile — whichever you'd like to share with Ally?",
    prompt: 'Optional — skip if you’d rather not share.',
    placeholder: 'instagram.com/you or linkedin.com/in/you',
  },
  {
    key: 'experience',
    section: 'personal',
    field: 'experience_level',
    label: 'Experience Level',
    type: 'single',
    paths: BOTH,
    q: 'How experienced are you as an entrepreneur?',
    // values match the founders_experience_level_check constraint
    options: [
      { label: 'First-time founder', value: 'first_time' },
      { label: 'Built one company', value: 'one_company' },
      { label: 'Serial entrepreneur', value: 'serial' },
      { label: 'Investor', value: 'investor' },
      { label: 'Mentor', value: 'mentor' },
      { label: 'Experienced executive', value: 'executive' },
    ],
  },
  {
    key: 'revenue',
    section: 'personal',
    field: 'current_revenue',
    label: 'Monthly Revenue',
    type: 'single',
    paths: [PATH_2], // Stage 0 founders are pre-revenue by definition -- skipped entirely
    q: 'What is your monthly revenue?',
    // values match the founders_current_revenue_check constraint, kept as the
    // existing coded bands rather than introducing a new set for this
    // question alone -- see backend/app/schemas/sections.py's MonthlyRevenue.
    options: [
      { label: 'Pre-revenue (₹0)', value: 'pre_revenue' },
      { label: 'Under ₹1 lakh/month', value: 'under_1L' },
      { label: '₹1 lakh – ₹5 lakh/month', value: '1L_5L' },
      { label: '₹5 lakh – ₹25 lakh/month', value: '5L_25L' },
      { label: '₹25 lakh – ₹1 crore/month', value: '25L_1Cr' },
      { label: '₹1 crore+/month', value: 'above_1Cr' },
    ],
  },

  /* === Section 2 — Understanding Where You Are (genuinely different
     questions per path, not just relabelled) ============================= */
  {
    key: 'building',
    section: 'where_you_are',
    field: 'building_summary',
    label: "What You're Building",
    type: 'short',
    paths: [PATH_2],
    q: 'What are you building?',
    prompt: 'The product or company name.',
    placeholder: 'Your product or company…',
  },
  {
    key: 'productDescription',
    section: 'where_you_are',
    field: 'product_description',
    label: 'What It Is',
    type: 'short',
    paths: [PATH_2],
    q: 'What is it?',
    prompt: 'One line — what it actually does.',
    placeholder: 'A one-line description…',
  },
  {
    key: 'problem',
    section: 'where_you_are',
    field: 'problem_statement',
    label: 'Problem Statement',
    type: 'long',
    paths: BOTH,
    q: 'What problem are you trying to solve?',
    placeholder: 'The problem you keep coming back to…',
  },
  {
    key: 'ideaName',
    section: 'where_you_are',
    field: 'building_summary', // same column as `building` above -- mutually
    // exclusive by path, both are a short name/label for "the thing"
    label: 'Idea Name',
    type: 'short',
    paths: [PATH_1],
    q: 'What would you call this idea?',
    prompt: "There's no product yet — just give it a name.",
    placeholder: 'Name your idea…',
  },

  /* === Section 3 — What Do You Know? ==================================== */
  {
    key: 'audience',
    section: 'what_you_know',
    field: 'customer_segment',
    otherField: 'customer_segment_other',
    label: 'Who You Serve',
    type: 'chips',
    paths: BOTH,
    q: 'Who is it for? Who are you building this for?',
    options: [
      'Consumers', 'Business', 'Student', 'Doctors', 'Creator', 'Developer',
      'Manufacturers', 'Retailers', 'Enterprises', 'Others',
    ],
    otherValue: 'Others',
    otherPlaceholder: 'Who else are you building for?',
  },
  {
    key: 'industry',
    section: 'what_you_know',
    field: 'industry',
    label: 'Industry',
    type: 'dropdown',
    paths: BOTH,
    q: 'Which industry best describes your business?',
    prompt: 'Start typing to search.',
    options: [
      'AI', 'SaaS', 'Fintech', 'Manufacturing', 'Healthcare', 'Education',
      'D2C Services', 'Logistics', 'Real Estate', 'Agriculture', 'Other',
    ],
    otherValue: 'Other',
    placeholder: 'Search industries…',
  },
  {
    key: 'founderReality',
    section: 'what_you_know',
    field: 'founder_reality_signals',
    label: 'Founder Reality',
    type: 'yesno',
    paths: BOTH,
    q: 'Founder Reality (Intuitive Check)',
    prompt: 'Tick what feels true — go with instinct.',
    items: [
      { key: 'clear_next_priorities', text: 'I clearly know my next 3 priorities', sub: 'Clarity vs random daily work' },
      { key: 'decisive', text: 'I take decisions with confidence', sub: 'Decisive vs overthinking' },
      { key: 'effort_aligned_to_growth', text: 'My effort is aligned to growth', sub: 'Impact work vs busy work' },
      { key: 'executes_consistently', text: 'I execute consistently', sub: 'Systems vs mood-driven action' },
      { key: 'mentally_clear', text: 'I feel mentally clear & in control', sub: 'Focus vs overwhelm' },
    ],
  },
  {
    key: 'businessReality',
    section: 'what_you_know',
    field: 'business_reality_signals',
    label: 'Business Reality',
    type: 'yesno',
    paths: [PATH_2], // no business yet to assess structure on for Path 1
    q: 'Business Reality (Structure Check)',
    prompt: 'Tick what feels true — go with instinct.',
    items: [
      { key: 'revenue_predictable', text: 'Revenue is predictable', sub: 'Consistency vs uncertainty' },
      { key: 'systems_defined', text: 'Systems/processes are defined', sub: 'Structure vs chaos' },
      { key: 'plans_become_execution', text: 'Plans turn into execution', sub: 'Action vs discussion' },
      { key: 'team_independent', text: 'Team operates without dependency', sub: 'Delegation vs founder bottleneck' },
      { key: 'financials_clear', text: 'Financials are clear — cost, margin, runway', sub: 'Visibility vs guesswork' },
    ],
  },
  {
    key: 'invisibleGaps',
    section: 'what_you_know',
    field: 'invisible_gaps',
    label: 'Invisible Gaps',
    type: 'multi',
    paths: BOTH,
    q: 'What resonates?',
    options: [
      "Working hard but results don't match",
      "Doing many things but unsure what's right",
      'Business depends heavily on me',
      'Feeling stuck despite effort',
      'No clear roadmap',
      'Strategy ≠ execution reality',
      'Mental clutter / overwhelm',
    ],
  },

  /* === Section 4 — Final Questions ====================================== */
  {
    key: 'biggestChallenge',
    section: 'final',
    field: 'current_challenges',
    otherField: 'current_challenges_other',
    label: 'Biggest Challenge',
    type: 'multi',
    paths: BOTH,
    q: "What's the biggest challenge you are facing today?",
    options: [
      'Finding the right idea', 'Building the product', 'Getting customers',
      'Sales', 'Marketing', 'Hiring', 'Fundraising', 'Cash flow',
      'Team leadership', 'Scaling', 'Operations', 'Decision-making',
      'Productivity', 'Other',
    ],
    otherValue: 'Other',
    otherPlaceholder: 'What else is the biggest challenge?',
  },
  {
    key: 'oneYearSuccess',
    section: 'final',
    field: 'vision_1_year',
    label: 'One-Year Vision',
    type: 'long',
    paths: [PATH_2],
    q: 'What does success look like one year from today?',
    placeholder: 'A year from today…',
  },
  {
    key: 'ninetyDayGoal',
    section: 'final',
    field: 'goal_90_day',
    label: '90-Day Goal',
    type: 'long',
    paths: [PATH_1],
    q: 'What one thing would you like to achieve in the next 90 days?',
    placeholder: 'One thing, 90 days…',
  },
];

/**
 * The question list a founder with `path` (PATH_1 | PATH_2) actually sees, in
 * order. This is the ONE place path-branching happens -- every question above
 * declares its own `paths`, so adding/removing a question never means editing
 * branching logic elsewhere.
 *
 * `path` may be null before the stage question is answered -- in that case
 * every question is included (nothing downstream of "not yet known" can be
 * excluded), matching resolve_stage_groups' own "fail open" convention on the
 * backend.
 */
export function effectiveQuestions(path) {
  if (!path) return QUESTIONS;
  return QUESTIONS.filter((q) => q.paths.includes(path));
}

export const QUESTION_COUNT = QUESTIONS.length;
