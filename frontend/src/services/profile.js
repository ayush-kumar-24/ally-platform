/**
 * services/profile.js — the founder profile collected during onboarding.
 *
 * The guided flow gathers answers under its own short keys ('stage', 'building',
 * 'goal90'…). The API expects the canonical column names. The mapping lives here
 * so the onboarding screens stay presentation-only and there is exactly one place
 * to look when a field stops saving.
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
  problem: 'problem_statement',
  audience: 'customer_segment',
  audienceOther: 'customer_segment_other',
  industry: 'industry',
  challenges: 'current_challenges',
};

const FOUNDER = {
  why: 'founder_motivation',
  support: 'support_preferences',
  experience: 'experience_level',
  feeling: 'emotional_state',
  reflection: 'adaptive_reflection',
};

const GOALS = {
  goal90: 'goal_90_day',
  vision: 'vision_1_year',
};

/** Fields the API models as lists even when onboarding collects a single choice. */
const LIST_FIELDS = new Set([
  'support_preferences', 'emotional_state', 'current_challenges', 'customer_segment',
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
 */
export function toGuidedAnswers(profile) {
  if (!profile) return {};
  const feelings = profile.emotional_state || [];
  return {
    stage: profile.stage_name || '',
    building: profile.building_summary || '',
    problem: profile.problem_statement || '',
    audience: profile.customer_segment || [],
    audienceOther: profile.customer_segment_other || '',
    industry: profile.industry || '',
    challenges: profile.current_challenges || [],
    goal90: profile.goal_90_day || '',
    vision: profile.vision_1_year || '',
    why: profile.founder_motivation || '',
    support: profile.support_preferences || [],
    experience: profile.experience_level || '',
    feeling: Array.isArray(feelings) ? (feelings[0] || '') : (feelings || ''),
    reflection: profile.adaptive_reflection || '',
  };
}

/** Which section endpoint owns each canonical field. */
const OWNER = {
  business: new Set(Object.values(BUSINESS)),
  founder: new Set(Object.values(FOUNDER)),
  goals: new Set(Object.values(GOALS)),
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
 * lose the other two sections because one field was rejected. The caller gets a
 * report of what saved so it can decide what to say.
 */
export async function saveOnboardingProfile(answers) {
  const jobs = [
    ['business', updateBusinessSection, section(answers, BUSINESS)],
    ['founder', updateFounderSection, section(answers, FOUNDER)],
    ['goals', updateGoals, section(answers, GOALS)],
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
