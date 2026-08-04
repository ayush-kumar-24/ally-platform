/**
 * data/onboardingQuestions.js — the GoXL AI Founder DNA onboarding question set.
 *
 * Transcribed from the "GoXL AI Founder DNA Onboarding" spec. Questions, prompts
 * and option lists are reproduced verbatim; only the storage plumbing (`key`,
 * `field`, option `value`s) is ours.
 *
 * Onboarding runs entirely in the browser — no LLM, no API key, no agent. The
 * backend's only job is to persist the answers. Everything a founder is asked
 * lives in this file, so changing the flow never means touching a component.
 */

/* ---------------------------------------------------------------------------
 * Q1 — Where are you in your entrepreneurial journey?
 *
 * Asked as two steps rather than one flat list. The founder first picks the
 * broad group, then (where it's ambiguous) the exact stage inside it. Stage 0
 * contains only Ideation, so that second step is skipped entirely.
 *
 * `group` mirrors questions.primary_stage_group in the database and decides
 * which slice of the diagnosis question bank the founder later sees; `stage`
 * resolves to founder_stages.stage_id via the name. Both are kept: the group is
 * what the diagnosis engine gates on, the stage is the precise self-assessment.
 * ------------------------------------------------------------------------- */
export const STAGE_GROUPS = [
  {
    key: 'stage_0',
    group: 'Stage 0',
    label: 'Just exploring ideas',
    hint: 'Still shaping what to build',
    stages: [
      { name: 'Ideation', order: 1, blurb: 'Exploring ideas, nothing built yet' },
    ],
  },
  {
    key: 'stage_0_1',
    group: 'Stage 0→1',
    label: 'Building from 0 → 1',
    hint: 'Turning the idea into something real people use',
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
    stages: [
      { name: 'Growth / Scaling', order: 5, blurb: 'Pushing hard on what already works' },
      { name: 'Expansion', order: 6, blurb: 'New markets, products or geographies' },
      { name: 'Maturity', order: 7, blurb: 'An established business to steward' },
      { name: 'Exit', order: 8, blurb: 'Preparing to hand it on or sell' },
    ],
  },
];

/** Flat lookup: stage name -> its group + order. */
export const STAGE_BY_NAME = Object.fromEntries(
  STAGE_GROUPS.flatMap((g) =>
    g.stages.map((s) => [s.name, { ...s, group: g.group, groupKey: g.key }]),
  ),
);

/* ---------------------------------------------------------------------------
 * The adaptive stage question.
 *
 * The spec defines five of these against its five stages; we ask against the
 * eight the database actually stores, so several stages share a question. The
 * wording is the spec's, unchanged.
 * ------------------------------------------------------------------------- */
export const ADAPTIVE_BY_STAGE = {
  Ideation: "What's stopping you from getting started?",
  Validation: "What's the biggest blocker to launching?",
  'Prototype / MVP': "What's the biggest blocker to launching?",
  'Early Traction': "What's the biggest obstacle to your next phase of growth?",
  'Growth / Scaling': 'Which part of your business needs the most attention right now?',
  Expansion: 'What legacy or long-term impact do you want to create over the next decade?',
  Maturity: 'What legacy or long-term impact do you want to create over the next decade?',
  Exit: 'What legacy or long-term impact do you want to create over the next decade?',
};

export const ADAPTIVE_FALLBACK = 'What matters most to you right now?';

/** The spec's three sections, used for the live Founder DNA panel. */
export const SECTIONS = [
  { key: 'journey', label: 'Your Journey' },
  { key: 'business', label: 'Your Business' },
  { key: 'style', label: 'Your Working Style' },
];

/* ---------------------------------------------------------------------------
 * The questions.
 *
 * type:
 *   'stage'    two-step group -> stage picker (Q1 only)
 *   'short'    one-line free text
 *   'long'     multi-line free text
 *   'chips'    multi-select chips, plus free text when "Other" is picked
 *   'dropdown' searchable single-select
 *   'multi'    multi-select, optionally capped by `max`
 *   'single'   single-select
 * ------------------------------------------------------------------------- */
export const QUESTIONS = [
  /* --- Section 1: Your Journey --------------------------------------------- */
  {
    key: 'stage',
    section: 'journey',
    label: 'Entrepreneurial Stage',
    type: 'stage',
    q: 'Where are you in your entrepreneurial journey?',
  },
  {
    key: 'building',
    section: 'journey',
    label: "What You're Building",
    type: 'short',
    q: 'What are you building?',
    prompt: 'Tell us about your startup, company, or idea in one or two sentences.',
    placeholder: 'Your startup, company or idea…',
  },
  {
    key: 'problem',
    section: 'journey',
    label: 'Problem Statement',
    type: 'long',
    q: 'What problem are you trying to solve?',
    prompt: "Describe the problem as if you're explaining it to a friend.",
    placeholder: 'The problem you keep coming back to…',
  },
  {
    key: 'why',
    section: 'journey',
    label: 'Founder Story',
    type: 'long',
    q: 'Why is solving this problem important to you?',
    prompt: 'What made you dedicate your time and energy to solving this problem?',
    placeholder: 'The real reason…',
  },
  {
    key: 'audience',
    section: 'journey',
    label: 'Who You Serve',
    type: 'chips',
    q: 'Who are you building this for?',
    prompt: 'Pick everyone that fits — you can add your own.',
    options: [
      'Consumers', 'Businesses', 'Students', 'Doctors', 'Creators',
      'Developers', 'Manufacturers', 'Retailers', 'Enterprises', 'Other',
    ],
    otherPlaceholder: 'Who else are you building for?',
  },

  /* --- Section 2: Your Business -------------------------------------------- */
  {
    key: 'industry',
    section: 'business',
    label: 'Industry',
    type: 'dropdown',
    q: 'Which industry best describes your business?',
    prompt: 'Start typing to search.',
    options: [
      'AI', 'SaaS', 'FinTech', 'Manufacturing', 'Healthcare', 'Education',
      'D2C', 'Services', 'Logistics', 'Real Estate', 'Agriculture', 'Other',
    ],
    placeholder: 'Search industries…',
  },
  {
    key: 'challenges',
    section: 'business',
    label: 'Biggest Challenges',
    type: 'multi',
    max: 3,
    q: "What's your biggest challenge right now?",
    prompt: 'Choose up to 3.',
    options: [
      'Finding the right idea', 'Building the product', 'Getting customers',
      'Sales', 'Marketing', 'Hiring', 'Fundraising', 'Cash flow', 'Team',
      'Leadership', 'Scaling', 'Operations', 'Decision making', 'Productivity',
      'Other',
    ],
  },
  {
    key: 'goal90',
    section: 'business',
    label: '90-Day Breakthrough',
    type: 'long',
    q: 'If GoXL AI could help you achieve one breakthrough in the next 90 days, what would it be?',
    examples: [
      'Launch MVP', 'Reach ₹10L MRR', 'Hire leadership',
      'Raise funding', 'Improve profitability', 'Acquire first 100 customers',
    ],
    placeholder: 'Your one breakthrough…',
  },
  {
    key: 'vision',
    section: 'business',
    label: 'One-Year Vision',
    type: 'long',
    q: 'What does success look like one year from today?',
    prompt: 'Describe your ideal future.',
    placeholder: 'A year from today…',
  },

  /* --- Section 3: Your Working Style --------------------------------------- */
  {
    key: 'support',
    section: 'style',
    label: 'How Ally Helps',
    type: 'multi',
    q: 'How would you like GoXL AI to support you?',
    prompt: 'Pick as many as you like.',
    options: [
      'Strategic thinking', 'Daily planning', 'Accountability', 'Brainstorming',
      'Decision support', 'Research', 'Sales', 'Marketing', 'Finance',
      'Hiring', 'Product', 'Leadership', 'Investor readiness',
    ],
  },
  {
    key: 'experience',
    section: 'style',
    label: 'Experience Level',
    type: 'single',
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
    key: 'feeling',
    section: 'style',
    label: 'Today’s Mindset',
    type: 'single',
    q: 'How are you feeling today?',
    // values match the founders_emotional_state_check constraint
    options: [
      { label: 'Excited', value: 'excited' },
      { label: 'Inspired', value: 'inspired' },
      { label: 'Confident', value: 'confident' },
      { label: 'Curious', value: 'curious' },
      { label: 'Overwhelmed', value: 'overwhelmed' },
      { label: 'Stuck', value: 'stuck' },
      { label: 'Determined', value: 'determined' },
      { label: 'Hopeful', value: 'hopeful' },
    ],
  },
  {
    key: 'reflection',
    section: 'style',
    label: 'Stage Reflection',
    type: 'long',
    adaptive: true,
    q: '',
    placeholder: 'Say what’s really on your mind…',
  },
];

export const QUESTION_COUNT = QUESTIONS.length;
