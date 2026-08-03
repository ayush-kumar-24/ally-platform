/**
 * services/dashboard.js — the founder's home screen data.
 *
 * Three independent sources, fetched together but failing independently: a founder
 * with no diagnosis yet still has a profile and a name, and the page must render
 * for them. Treating any one failure as fatal would make a brand-new account look
 * like a broken app.
 */

import { get } from './api';

/** Diagnosis-derived health score, band, pillars and red flags. */
export function getBusinessHealth() {
  return get('/dashboard/business-health');
}

/** Profile completion — which fields are still missing. */
export function getProfileProgress() {
  return get('/profile/progress');
}

/** Session and report counts. */
export function getIntelligenceSummary() {
  return get('/intelligence/summary');
}

/** The signed-in founder's profile. */
export function getProfile() {
  return get('/profile');
}

/**
 * Everything the dashboard needs, in one call.
 *
 * Each source resolves to null on failure rather than rejecting, so one missing
 * piece dims one card instead of blanking the page. The caller can tell "no data
 * yet" (`available: false`) from "could not load" (`null`).
 */
export async function loadDashboard() {
  const [profile, health, progress, summary] = await Promise.all([
    getProfile().catch(() => null),
    getBusinessHealth().catch(() => null),
    getProfileProgress().catch(() => null),
    getIntelligenceSummary().catch(() => null),
  ]);
  return { profile, health, progress, summary };
}

/** Percentage of required profile fields that are filled. */
export function completionPercent(progress) {
  const fields = progress?.fields ?? [];
  const required = fields.filter(f => f.required);
  if (required.length === 0) return null;
  const filled = required.filter(f => f.filled).length;
  return Math.round((filled / required.length) * 100);
}
