/**
 * data/onboardingQuestions.js — the Ally onboarding question set.
 *
 * Rewritten 2026-09-11 against `Founder DNA Onboarding — Build Spec v2.4`:
 * 11 questions across 4 sections on BOTH paths, Industry before Audience, and
 * Sections 2/3 split by subject rather than by when the question was written.
 *
 * Onboarding runs entirely in the browser — no LLM, no API key, no agent. The
 * backend's only job is to persist the answers. Everything a founder is asked
 * lives in this file, so changing the flow never means touching a component.
 *
 * Two paths, decided by the Section 1 stage question and nothing else:
 *   PATH_1  Stage 0 (Ideation) only
 *   PATH_2  Stage 0→1 or Stage 1→10+ -- everyone beyond Stage 0
 *
 * This is ONE flow with conditional questions, not two separate flows. Path
 * narrowing happens at THREE levels, and all three are declared here rather
 * than branched for in a component:
 *
 *   question  `paths` on a question   -- the whole question is skipped
 *   part      `paths` on a group part -- one control inside a question is
 *                                        skipped (see the `group` type)
 *   option    `paths` on an option    -- a single chip/checkbox is hidden
 *
 * The option level is the one that is easy to forget and the one a founder
 * actually notices. Filtering whole questions already spares a Stage 0 founder
 * the revenue question and the Business Reality checks -- but it left them
 * being offered "Business depends heavily on me" as an invisible gap and
 * "Cash flow", "Hiring" and "Scaling" as their biggest challenge, none of
 * which can be true of someone who has not started yet. An option that cannot
 * apply is not a harmless extra: picking it writes a signal the diagnosis
 * later reads as real, and leaving it unpicked is indistinguishable from
 * having considered and rejected it.
 *
 * The rule used below: an option is Path 2 only when it PRESUPPOSES AN
 * OPERATING BUSINESS -- revenue to manage, a team to lead, systems already
 * running, work already being executed. Forward-looking worries an ideation
 * founder genuinely has (getting customers, fundraising) stay on both paths.
 */

export const PATH_1 = 'path1'; // Stage 0 / Ideation
export const PATH_2 = 'path2'; // Stage 0->1 or Stage 1->10+
const BOTH = [PATH_1, PATH_2];

/* ---------------------------------------------------------------------------
 * Stage picker (part of Section 1's Q3). Unchanged: founder_stages already
 * contains exactly this 3-group / 8-stage structure (confirmed against the
 * live table), so nothing here invents a parallel enum. `group` mirrors
 * founder_stages.onboarding_label / questions.primary_stage_group; `stage`
 * resolves to stage_id via the name.
 *
 * These boundaries must stay in step with _STAGE_ORDER_TO_GROUP in
 * backend/app/api/v1/diagnosis/engine.py -- the founder picks the group here
 * and the backend re-derives it there to choose a question bank. Change both
 * together.
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

/**
 * The 4 onboarding sections. `label` names the section in the side panel;
 * `chapter` is the eyebrow shown above the progress bar, which shifts at each
 * section boundary so the flow reads as one continuous conversation rather
 * than four stapled-together blocks (spec v2.4 §2).
 */
export const SECTIONS = [
  { key: 'personal',      label: 'Personal Detail',             chapter: 'Getting to know you' },
  { key: 'where_you_are', label: 'Understanding Where You Are', chapter: 'Understanding where you are' },
  { key: 'what_you_know', label: 'What Do You Know',            chapter: 'What do you know' },
  { key: 'final',         label: "Where You're Headed",         chapter: "Where you're headed" },
];

/* ---------------------------------------------------------------------------
 * Question types:
 *   'stage'      two-step group -> stage picker
 *   'short'      one-line free text
 *   'long'       multi-line free text
 *   'url'        a single URL, validated + normalised server-side
 *   'chips'      multi-select chips, plus free text when the "other" option
 *                is picked (see otherValue/otherPlaceholder)
 *   'dropdown'   searchable single-select
 *   'multi'      multi-select checkboxes, capped when `max` is set, plus
 *                free text when the "other" option is picked (same as chips)
 *   'single'     single-select cards
 *   'yesno'      a fixed set of Yes/No checks answered together as one screen
 *                (`items`), submitted as a single object
 *   'group'      ONE question made of several controls, asked back to back and
 *                committed together (`parts`). This is what keeps the flow at
 *                the spec's 11 questions while the chat surface still asks for
 *                one thing at a time: Q3 is stage + experience + revenue, Q4 is
 *                a name + a one-line description, Q9 is Business Reality +
 *                Invisible Gaps. Each part carries its own `key`, `field`,
 *                `type` and `paths`; a part whose path does not match is
 *                skipped without the question itself disappearing.
 *
 * `paths`: which path(s) this question / part / option is shown on. Resolved by
 * effectiveQuestions(), activeParts() and activeOptions() below -- the only
 * three places path-branching happens.
 *
 * OPTIONS may be plain strings (shown on both paths) or
 * `{ value, paths }` objects. optionValue() normalises the two, so a question
 * that needs no filtering stays a plain list of strings.
 * ------------------------------------------------------------------------- */

/** The stored value of an option, whether it is a bare string or {value,paths}. */
export function optionValue(option) {
  return typeof option === 'string' ? option : option.value;
}

/** The options of `question` visible on `path` (all of them when path is null). */
export function activeOptions(question, path) {
  const options = question?.options || [];
  if (!path) return options;
  return options.filter((o) => typeof o === 'string' || !o.paths || o.paths.includes(path));
}

/** The parts of a `group` question asked on `path` (all of them when null). */
export function activeParts(question, path) {
  const parts = question?.parts || [];
  if (!path) return parts;
  return parts.filter((p) => !p.paths || p.paths.includes(path));
}

export const QUESTIONS = [
  /* === Section 1 — Personal Detail ===================================== */

  // Q1
  {
    key: 'name',
    section: 'personal',
    field: 'full_name',
    label: 'Name',
    type: 'short',
    paths: BOTH,
    q: 'What would you like Ally to call you?',
    prompt: "Pre-filled from your name — change it if you'd like something else.",
    placeholder: 'Your name…',
  },

  // Q2 -- optional, and asked before the stage question so the flow still
  // opens on a person rather than a taxonomy (spec v2.4 §2).
  {
    key: 'socialHandle',
    section: 'personal',
    field: 'linkedin_url',
    label: 'Social Profile',
    type: 'url',
    paths: BOTH,
    optional: true,
    q: 'Share your LinkedIn or Instagram profile.',
    prompt: "Helps Ally reference your public work — skip if you'd rather not.",
    placeholder: 'instagram.com/you or linkedin.com/in/you',
  },

  /* Q3 -- stage, experience and (beyond Stage 0) monthly revenue, as one
     question. Stage leads because it is the only answer the rest of this flow
     branches on: until it is given, nothing path-specific can be asked
     honestly. `GoXL_Stage_Adaptive_Diagnosis_Framework_2.docx` s9 asks for the
     stage "captured in the first 1-2 onboarding questions, since every
     downstream question bank and root-cause filter branches off it" -- Founder
     DNA and Current Problem select their bank by stage group, the
     recommendation engine filters interventions by stage_id, the report picks
     its tone by stage, and the confidence model reads stage-adjusted priors.

     Because every question at or before this one is shown on both paths, the
     founder's index never shifts when the list narrows -- see answer() in
     ProfileBuild.jsx, which relies on exactly that. */
  {
    key: 'stageExperience',
    section: 'personal',
    label: 'Stage & Experience',
    type: 'group',
    paths: BOTH,
    q: 'Where are you on your entrepreneurial journey?',
    parts: [
      {
        key: 'stage',
        field: 'stage',
        label: 'Entrepreneurial Stage',
        type: 'stage',
        paths: BOTH,
        q: 'Where are you on your entrepreneurial journey?',
      },
      {
        key: 'experience',
        field: 'experience_level',
        label: 'Experience Level',
        type: 'single',
        paths: BOTH,
        q: 'And how experienced are you as an entrepreneur?',
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
        key: 'teamSize',
        field: 'team_size',
        label: 'Team Size',
        type: 'single',
        // Asked on BOTH paths. A Stage 0 founder has a team or does not, and
        // the answer changes which questions the diagnosis may ask them --
        // delegation, hiring and decision-rights questions presuppose people
        // to delegate to. Without it, team size is UNKNOWN and those questions
        // stay eligible for everyone, which is what founders reported.
        paths: BOTH,
        q: "And who's building this with you right now?",
        // Phrasing counts people doing the work, not payroll: a two-co-founder
        // pre-hire company is "2-5", not "just me". The VALUES mirror the
        // founders.team_size CHECK constraint exactly -- see TeamSize in
        // backend/app/schemas/founder.py. Do not invent a seventh band.
        options: [
          { label: 'Just me', value: 'solo' },
          { label: '2-5 people', value: '2_5' },
          { label: '6-10 people', value: '6_10' },
          { label: '11-25 people', value: '11_25' },
          { label: '26-50 people', value: '26_50' },
          { label: '50+ people', value: '50_plus' },
        ],
      },
      {
        key: 'businessModel',
        field: 'business_model',
        label: 'Business Model',
        type: 'single',
        // BOTH paths: an idea-stage founder usually knows who they intend to
        // sell to even before they sell to anyone.
        paths: BOTH,
        q: 'And who do you sell to?',
        // Mirrors BusinessModel in backend/app/schemas/founder.py.
        options: [
          { label: 'Businesses (B2B)', value: 'B2B' },
          { label: 'Consumers (B2C)', value: 'B2C' },
          { label: 'Businesses who serve consumers (B2B2C)', value: 'B2B2C' },
          { label: 'A marketplace connecting both', value: 'marketplace' },
          { label: 'Direct to consumer (D2C)', value: 'D2C' },
          { label: 'Something else', value: 'other' },
        ],
      },
      {
        key: 'revenue',
        field: 'current_revenue',
        label: 'Monthly Revenue',
        type: 'single',
        // Stage 0 founders are pre-revenue by definition -- never asked, and
        // the column stays NULL rather than being written a 6th "none" band.
        paths: [PATH_2],
        q: 'And what is your monthly revenue right now?',
        // The existing coded bands on founders.current_revenue, kept rather
        // than the spec's proposed new boundaries -- explicit product call
        // (2026-09-11): this question writes into an already-live column with
        // a CHECK constraint and existing founder rows behind it. See
        // MonthlyRevenue in backend/app/schemas/sections.py.
        options: [
          { label: 'Pre-revenue (₹0)', value: 'pre_revenue' },
          { label: 'Under ₹1 lakh/month', value: 'under_1L' },
          { label: '₹1 lakh – ₹5 lakh/month', value: '1L_5L' },
          { label: '₹5 lakh – ₹25 lakh/month', value: '5L_25L' },
          { label: '₹25 lakh – ₹1 crore/month', value: '25L_1Cr' },
          { label: '₹1 crore+/month', value: 'above_1Cr' },
        ],
      },
    ],
  },

  /* === Section 2 — Understanding Where You Are ========================== */

  /* Q4 -- the name and the one-line description, as one question. The two
     name parts are mutually exclusive by path and write the same column:
     Path 2 has a product or company to name, Path 1 has an idea to label. */
  {
    key: 'building',
    section: 'where_you_are',
    label: "What You're Building",
    type: 'group',
    paths: BOTH,
    q: "Tell us what you're building — and what do you call it?",
    parts: [
      {
        key: 'buildingName',
        field: 'building_summary',
        label: "What You're Building",
        type: 'short',
        paths: [PATH_2],
        q: 'First — what do you call it?',
        prompt: 'The product or company name.',
        placeholder: 'Your product or company…',
      },
      {
        key: 'buildingName',
        field: 'building_summary',
        label: 'Idea Name',
        type: 'short',
        paths: [PATH_1],
        q: 'What would you call this idea?',
        prompt: "There's no product yet — just give it a name.",
        placeholder: 'Name your idea…',
      },
      {
        key: 'buildingDescription',
        field: 'product_description',
        label: 'What It Is',
        type: 'short',
        paths: BOTH,
        q: 'And what is it, in one line?',
        prompt: 'What it actually does.',
        placeholder: 'A one-line description…',
      },
    ],
  },

  // Q5
  {
    key: 'problem',
    section: 'where_you_are',
    field: 'problem_statement',
    label: 'Problem Statement',
    type: 'long',
    paths: BOTH,
    q: 'What problem are you trying to solve?',
    prompt: "Describe it as if you're explaining it to a friend.",
    placeholder: 'The problem you keep coming back to…',
  },

  // Q6 -- Industry before Audience. This ordering came in with v2.3 and is the
  // one v2.3 change v2.4 explicitly did NOT revert.
  {
    key: 'industry',
    section: 'where_you_are',
    field: 'industry',
    label: 'Industry',
    type: 'dropdown',
    paths: BOTH,
    q: 'Which industry best describes your business?',
    prompt: 'Start typing to search.',
    /* The thirty industries the product actually has data for.
     *
     * Every VALUE below is an `industries.industry_name` from the seed
     * migrations (backend/alembic/versions/*seed*industry*), which is the
     * taxonomy the diagnosis content is built on: each of these thirty has its
     * own problems, root causes, question bank and interventions seeded against
     * its industry_code. The old twelve ('AI', 'SaaS', 'D2C', 'Real Estate'...)
     * were written before that content existed and match none of them, so an
     * answer here named an industry the rest of the system had never heard of.
     *
     * Values must keep matching that table character for character. Anything
     * that later resolves founders.industry to founders.industry_mapped_id --
     * which is what the diagnosis engine, the reasoning service and the Ally
     * context builder all read to pick an industry's dataset -- does it by
     * name, so a wording change here without one there silently unmaps every
     * founder who picked it. (Nothing writes industry_mapped_id today; see the
     * note in backend/app/api/v1/profile/routes.py.)
     *
     * LABELS are the fuller, more searchable wording where the stored name is
     * an abbreviation or a shorthand: this control filters on the label as the
     * founder types, so a founder searching "Banking" finds BFSI / FinTech and
     * one searching "Information Technology" finds Technology & SaaS. Where the
     * two agree the option stays a plain string. labelFor() in
     * utils/profileDisplay.js reads these back, so the panel, the summary and
     * the transcript all show the founder's wording rather than the stored one.
     *
     * Stage-agnostic: an industry is just as true of an idea as of a running
     * company, so this is on both paths. A–Z by label.
     */
    options: [
      'Agriculture & AgriTech',
      'Automotive & Mobility',
      { label: 'Banking, Financial Services & Insurance (BFSI) / FinTech', value: 'BFSI / FinTech' },
      'Beauty & Personal Care',
      'Construction & Real Estate / PropTech',
      'Consumer Electronics',
      { label: 'E-commerce & D2C', value: 'E-Commerce & D2C' },
      'Education & EdTech',
      'Energy, CleanTech & Renewables',
      'Entertainment & Media',
      'Fashion & Apparel',
      'Food & Beverage / FoodTech',
      'Gaming',
      'Healthcare & HealthTech / MedTech',
      'Hospitality, Travel & Tourism',
      'Human Resources & HRTech',
      { label: 'Import/Export & Trade', value: 'Import / Export & Trade' },
      { label: 'Industrial & Manufacturing (heavy/light)', value: 'Industrial & Manufacturing' },
      { label: 'Information Technology & Software (SaaS)', value: 'Technology & SaaS' },
      'Legal & LegalTech',
      'Logistics & Supply Chain',
      'Marketing, Advertising & AdTech',
      'Non-Profit, Social Impact & NGO',
      'Pharmaceuticals & Biotech',
      { label: 'Professional Services & Consulting', value: 'Services & Consulting' },
      { label: 'Retail (offline & online)', value: 'Retail' },
      'Sports, Fitness & Wellness',
      'Telecommunications',
      'Textiles',
      'Transportation & Delivery',
      'Other',
    ],
    otherValue: 'Other',
    placeholder: 'Search industries…',
  },

  // Q7
  {
    key: 'audience',
    section: 'where_you_are',
    field: 'customer_segment',
    otherField: 'customer_segment_other',
    label: 'Who You Serve',
    type: 'chips',
    paths: BOTH,
    q: 'Who are you building this for?',
    prompt: 'Select all that apply.',
    options: [
      'Consumers', 'Business', 'Student', 'Doctors', 'Creator', 'Developer',
      'Manufacturers', 'Retailers', 'Enterprises', 'Others',
    ],
    otherValue: 'Others',
    otherPlaceholder: 'Who else are you building for?',
  },

  /* === Section 3 — What Do You Know ===================================== */

  // Q8 -- shown on both paths. Having no business yet is not a reason to skip
  // this set: every statement is about the founder, not the company.
  {
    key: 'founderReality',
    section: 'what_you_know',
    field: 'founder_reality_signals',
    label: 'Founder Reality',
    type: 'yesno',
    paths: BOTH,
    q: 'A few honest yes/no questions about where you’re really at.',
    prompt: 'No wrong answers — this just helps Ally calibrate.',
    items: [
      { key: 'clear_next_priorities', text: 'I clearly know my next 3 priorities', sub: 'Clarity vs random daily work' },
      { key: 'decisive', text: 'I take decisions with confidence', sub: 'Decisive vs overthinking' },
      { key: 'effort_aligned_to_growth', text: 'My effort is aligned to what I want to build', sub: 'Impact work vs busy work' },
      { key: 'executes_consistently', text: 'I execute consistently', sub: 'Systems vs mood-driven action' },
      { key: 'mentally_clear', text: 'I feel mentally clear & in control', sub: 'Focus vs overwhelm' },
    ],
  },

  /* Q9 -- Business Reality (Path 2 only; there is no business to assess
     structure on at Stage 0) plus Invisible Gaps (both paths), as one
     question. On Path 1 this question is just the Invisible Gaps checkboxes. */
  {
    key: 'reality',
    section: 'what_you_know',
    label: 'Business Reality & Gaps',
    type: 'group',
    paths: BOTH,
    // Only shown when the group actually has more than one part -- on Path 1
    // this question is Invisible Gaps alone, and "the business itself" would
    // be addressing a business that does not exist.
    q: 'And a few about the business itself.',
    parts: [
      {
        key: 'businessReality',
        field: 'business_reality_signals',
        label: 'Business Reality',
        type: 'yesno',
        paths: [PATH_2],
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
        field: 'invisible_gaps',
        label: 'Invisible Gaps',
        type: 'multi',
        paths: BOTH,
        q: 'What resonates?',
        prompt: 'Pick anything that feels familiar.',
        options: [
          "Working hard but results don't match",
          "Doing many things but unsure what's right",
          // Both of these describe a business that already runs: one that
          // leans on the founder, and a strategy already diverging from
          // execution. Neither can be true before there is anything to run.
          { value: 'Business depends heavily on me', paths: [PATH_2] },
          { value: 'Strategy ≠ execution reality', paths: [PATH_2] },
          'Feeling stuck despite effort',
          'No clear roadmap',
          'Mental clutter / overwhelm',
        ],
      },
    ],
  },

  /* === Section 4 — Where You're Headed ================================== */

  // Q10 -- capped at 3. `max` is enforced in the control; the backend bounds
  // it too, so a hand-rolled request cannot write more.
  {
    key: 'biggestChallenge',
    section: 'final',
    field: 'current_challenges',
    otherField: 'current_challenges_other',
    label: 'Biggest Challenge',
    type: 'multi',
    max: 3,
    paths: BOTH,
    q: "What's the biggest challenge you're facing today?",
    prompt: 'Pick up to three.',
    // Team and Leadership are separate challenges -- being short-handed is not
    // the same problem as not knowing how to lead. Everything Path 2-only
    // below needs an operating business to be true of; "Getting customers" and
    // "Fundraising" stay on both paths because an ideation founder genuinely
    // worries about them before anything exists.
    options: [
      'Finding the right idea',
      'Building the product',
      'Getting customers',
      { value: 'Sales', paths: [PATH_2] },
      { value: 'Marketing', paths: [PATH_2] },
      { value: 'Hiring', paths: [PATH_2] },
      'Fundraising',
      { value: 'Cash flow', paths: [PATH_2] },
      { value: 'Team', paths: [PATH_2] },
      { value: 'Leadership', paths: [PATH_2] },
      { value: 'Scaling', paths: [PATH_2] },
      { value: 'Operations', paths: [PATH_2] },
      'Decision making',
      'Productivity',
      'Other',
    ],
    otherValue: 'Other',
    otherPlaceholder: 'What else is the biggest challenge?',
  },

  // Q11 -- mutually exclusive by path, so this is one question either way.
  {
    key: 'oneYearSuccess',
    section: 'final',
    field: 'vision_1_year',
    label: 'One-Year Vision',
    type: 'long',
    paths: [PATH_2],
    q: 'What does success look like one year from today?',
    prompt: 'Describe it as vividly (or as simply) as you like.',
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
    prompt: 'Describe it as vividly (or as simply) as you like.',
    placeholder: 'One thing, 90 days…',
  },
];

/**
 * The question list a founder with `path` (PATH_1 | PATH_2) actually sees, in
 * order. This is the ONE place question-level path-branching happens -- every
 * question declares its own `paths`, so adding or removing one never means
 * editing branching logic elsewhere.
 *
 * `path` may be null before the stage question is answered -- in that case
 * every question is included (nothing downstream of "not yet known" can be
 * excluded), matching resolve_stage_groups' own "fail open" convention on the
 * backend. That is safe here because the stage question sits inside Q3 and
 * everything at or before it is shown on both paths, so nothing path-specific
 * is ever reachable while path is still null.
 */
export function effectiveQuestions(path) {
  if (!path) return QUESTIONS;
  return QUESTIONS.filter((q) => q.paths.includes(path));
}

/**
 * Every question a founder is actually ASKED, keyed by its own key -- a
 * group's parts lifted to the top level, each carrying the section of the
 * group it came from.
 *
 * QUESTIONS is not a lookup table. Its entries are the eleven questions in
 * flow order, and three of the things a founder answers -- stage, experience,
 * revenue -- are PARTS of Q3's group rather than entries in it, as are the
 * two reality checks inside Q9. So `QUESTIONS.find((x) => x.key === 'stage')`
 * is undefined, not the stage part, and anything that then reads a field off
 * it throws.
 *
 * That has now bitten three times. profileDisplay.js (a founder's experience
 * reading back as the raw enum 'one_company') and Summary.jsx's yesNoSummary
 * (Business Reality silently blank) each grew their own private copy of this
 * flatten after being caught. ProfileBuild's confirmField never got one, and
 * threw on `q.section` the instant a founder picked their stage -- taking the
 * whole onboarding screen down at question 3 of 11, for everyone.
 *
 * So it lives here once and those three read it, rather than each rediscovering
 * it the hard way. Anything looking a question up BY KEY wants this or
 * askableByKey(); QUESTIONS itself is for walking the flow in order, and
 * effectiveQuestions()/questionCount() for the founder's path through it.
 *
 * Parts carry no `section` of their own -- they inherit the group's, which is
 * what the DNA side panel already does when it lists them as rows.
 *
 * One caveat, because it is invisible until it bites: keys are NOT unique
 * across parts. Q4 declares 'buildingName' twice, once per path ("What You're
 * Building" on Path 2, "Idea Name" on Path 1), and a key can only resolve to
 * one of them -- the later, Path 1 entry. Both sit in the same group, so
 * anything path-independent (`section`, `type`) is the same either way and
 * safe to read here. Anything a founder SEES that differs by path -- `label`,
 * `q`, `placeholder` -- must come from activeParts(question, path) instead,
 * which is what the flow and the DNA panel already use.
 */
export const ASKABLE = QUESTIONS.flatMap((q) => (q.type === 'group'
  ? q.parts.map((p) => ({ ...p, section: p.section ?? q.section }))
  : [q]));

const ASKABLE_BY_KEY = new Map(ASKABLE.map((q) => [q.key, q]));

/** The question or group part with this key, or undefined if there is none. */
export function askableByKey(key) {
  return ASKABLE_BY_KEY.get(key);
}

/**
 * Every guided key a question can write, including a group's parts. Used by
 * the resume path to decide whether a question has already been answered.
 */
export function questionKeys(question, path) {
  if (question.type !== 'group') return [question.key];
  return activeParts(question, path).map((p) => p.key);
}

/**
 * How many questions a founder is asked -- what the progress counter shows.
 *
 * NOT `effectiveQuestions(path).length` when the path is unknown. That list is
 * the SUPERSET (it carries both the one-year vision and the 90-day goal, which
 * are mutually exclusive), so a founder saw "Question 1 of 12" and then watched
 * the total drop to 11 the moment they picked their stage -- the denominator
 * moving under them while the numerator stood still.
 *
 * Both paths ask the same number, so there is an honest answer to give before
 * the stage question narrows anything. The max is a guard rather than a
 * calculation: if the two ever diverge, the bar under-promises and then fills,
 * which is the failure worth having -- it never counts backwards.
 */
export function questionCount(path) {
  if (path) return effectiveQuestions(path).length;
  return Math.max(
    effectiveQuestions(PATH_1).length,
    effectiveQuestions(PATH_2).length,
  );
}
