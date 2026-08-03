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
  customer: 'customer_segment',
  industry: 'industry',
  challenges: 'current_challenges',
};

const FOUNDER = {
  why: 'founder_motivation',
  working: 'support_preferences',
  experience: 'experience_level',
  feeling: 'emotional_state',
  reflection: 'adaptive_reflection',
};

const GOALS = {
  goal90: 'goal_90_day',
  vision: 'vision_1_year',
};

/** Fields the API models as lists even when onboarding collects a single choice. */
const LIST_FIELDS = new Set(['support_preferences', 'emotional_state', 'current_challenges']);

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
