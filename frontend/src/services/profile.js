/**
 * services/profile.js — the founder profile collected during onboarding.
 *
 * The guided flow gathers answers under its own short keys ('stage', 'building',
 * 'goal90'…). The API expects the canonical column names. The mapping lives here
 * so the onboarding screens stay presentation-only and there is exactly one place
 * to look when a field stops saving.
 *
 * Rewritten 2026-08-17 for the 4-section, path-branching onboarding redesign
 * (see data/onboardingQuestions.js). Retired: why/support/feeling/reflection
 * (founder_motivation/support_preferences/emotional_state/adaptive_reflection)
 * -- no longer asked, so no longer mapped here. Their founders columns are
 * untouched; this file just stops writing them.
 */

import { get, patch, put } from './api';

export function getProfile() {
  return get('/profile');
}

export function getProgress() {
  return get('/profile/progress');
}

export function updateProfile(changes) {
  return patch('/profile', changes);
}

export function updateFounderSection(changes) {
  return patch('/profile/founder', changes);
}

export function updateBusinessSection(changes) {
  return patch('/profile/business', changes);
}

export function updateGoals(changes) {
  return patch('/profile/goals', changes);
}

export function updateContext(changes) {
  return put('/profile/context', changes);
}

/** Guided-flow key -> API field, split by the section that owns it. */
const BUSINESS = {
  stage: 'stage',
  building: 'building_summary',
  ideaName: 'building_summary', // same column as `building` -- mutually
  // exclusive by path (Path 2 vs Path 1), see onboardingQuestions.js
  productDescription: 'product_description',
  problem: 'problem_statement',
  revenue: 'current_revenue',
  audience: 'customer_segment',
  audienceOther: 'customer_segment_other',
  industry: 'industry',
  founderReality: 'founder_reality_signals',
  businessReality: 'business_reality_signals',
  invisibleGaps: 'invisible_gaps',
  biggestChallenge: 'current_challenges',
  biggestChallengeOther: 'current_challenges_other',
};

const FOUNDER = {
  name: 'full_name',
  experience: 'experience_level',
};

const GOALS = {
  ninetyDayGoal: 'goal_90_day',
  oneYearSuccess: 'vision_1_year',
};

// The social handle question isn't owned by any section endpoint -- it goes
// through the existing generic PATCH /profile (FounderUpdate already carries
// linkedin_url and validates it as a real URL), same as the settings page.
const PROFILE = {
  socialHandle: 'linkedin_url',
};

/** Fields the API models as lists even when onboarding collects a single choice. */
const LIST_FIELDS = new Set([
  'current_challenges', 'customer_segment', 'invisible_gaps',
]);

function section(answers, map) {
  const out = {};
  for (const [key, field] of Object.entries(map)) {
    const value = answers?.[key];
    if (value === undefined || value === null || value === '') continue;
    out[field] = LIST_FIELDS.has(field) && !Array.isArray(value) ? [value] : value;
  }
  return out;
}

/**
 * Server profile -> the short keys the guided screens use.
 *
 * The inverse of the maps above. Without it those screens can only read answers
 * from React state, which is memory-only: after a reload every field reads
 * "Not answered" even though the answers are sitting in the database.
 *
 * Path-agnostic on purpose: this runs before the founder's path may even be
 * known (e.g. on first mount), so both `building` and `ideaName` are
 * populated from the same building_summary value -- whichever one the
 * founder's actual path shows is the one that renders.
 */
export function toGuidedAnswers(profile) {
  if (!profile) return {};
  return {
    name: profile.full_name || '',
    socialHandle: profile.linkedin_url || '',
    stage: profile.stage_name || '',
    experience: profile.experience_level || '',
    revenue: profile.current_revenue || '',
    building: profile.building_summary || '',
    ideaName: profile.building_summary || '',
    productDescription: profile.product_description || '',
    problem: profile.problem_statement || '',
    audience: profile.customer_segment || [],
    audienceOther: profile.customer_segment_other || '',
    industry: profile.industry || '',
    founderReality: profile.founder_reality_signals || null,
    businessReality: profile.business_reality_signals || null,
    invisibleGaps: profile.invisible_gaps || [],
    biggestChallenge: profile.current_challenges || [],
    biggestChallengeOther: profile.current_challenges_other || '',
    oneYearSuccess: profile.vision_1_year || '',
    ninetyDayGoal: profile.goal_90_day || '',
  };
}

/** Which section endpoint owns each canonical field. */
const OWNER = {
  business: new Set(Object.values(BUSINESS)),
  founder: new Set(Object.values(FOUNDER)),
  goals: new Set(Object.values(GOALS)),
  profile: new Set(Object.values(PROFILE)),
};

/**
 * Save an already-canonical patch (e.g. { building_summary, goal_90_day }),
 * routing each field to the section endpoint that owns it.
 *
 * Used by the summary screen, where a founder corrects what Ally read back.
 * Throws if any section fails, so the caller can tell them it didn't stick.
 */
export async function saveProfileEdits(changes) {
  const calls = [
    [OWNER.business, updateBusinessSection],
    [OWNER.founder, updateFounderSection],
    [OWNER.goals, updateGoals],
    [OWNER.profile, updateProfile],
  ]
    .map(([fields, call]) => {
      const payload = Object.fromEntries(
        Object.entries(changes).filter(([field]) => fields.has(field)),
      );
      return Object.keys(payload).length > 0 ? call(payload) : null;
    })
    .filter(Boolean);

  await Promise.all(calls);
}

/**
 * Persist everything the guided flow collected.
 *
 * Each section is sent independently and failures are collected rather than
 * thrown: a founder who has just spent ten minutes answering questions should not
 * lose the other sections because one field was rejected. The caller gets a
 * report of what saved so it can decide what to say.
 */
export async function saveOnboardingProfile(answers) {
  const jobs = [
    ['business', updateBusinessSection, section(answers, BUSINESS)],
    ['founder', updateFounderSection, section(answers, FOUNDER)],
    ['goals', updateGoals, section(answers, GOALS)],
    ['profile', updateProfile, section(answers, PROFILE)],
  ].filter(([, , payload]) => Object.keys(payload).length > 0);

  const results = await Promise.all(jobs.map(async ([name, call, payload]) => {
    try {
      await call(payload);
      return { name, ok: true };
    } catch (error) {
      return { name, ok: false, error };
    }
  }));

  return {
    saved: results.filter(r => r.ok).map(r => r.name),
    failed: results.filter(r => !r.ok).map(r => r.name),
    ok: results.every(r => r.ok),
  };
}
