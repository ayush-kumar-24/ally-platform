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
 * The founder's real dashboard: journey state, stage, latest diagnosis, live
 * counts, upcoming call, recent conversations and reports.
 *
 * This endpoint has existed and gone unused, which is why the page showed
 * invented conversations, an invented booking and invented report scores
 * alongside the founder's real name.
 */
export function getOverview() {
  return get('/dashboard/overview');
}

/**
 * Everything the dashboard needs, in one call.
 *
 * Each source resolves to null on failure rather than rejecting, so one missing
 * piece dims one card instead of blanking the page. The caller can tell "no data
 * yet" (`available: false`) from "could not load" (`null`).
 */
/** The founder's real plan, credits and daily token usage. */
export function getMyPlan() {
  return get('/plans/me');
}

export async function loadDashboard() {
  const [profile, health, progress, summary, overview, plan] = await Promise.all([
    getProfile().catch(() => null),
    getBusinessHealth().catch(() => null),
    getProfileProgress().catch(() => null),
    getIntelligenceSummary().catch(() => null),
    getOverview().catch(() => null),
    getMyPlan().catch(() => null),
  ]);
  return { profile, health, progress, summary, overview, plan };
}

/** "14 JUL" / "Today" / "3d ago" — dates as a person reads them. */
export function relativeDay(iso) {
  if (!iso) return '';
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return '';
  const days = Math.floor((Date.now() - then.getTime()) / 86_400_000);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 30) return `${days}d ago`;
  return then.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

/** Percentage of required profile fields that are filled. */
export function completionPercent(progress) {
  const fields = progress?.fields ?? [];
  const required = fields.filter(f => f.required);
  if (required.length === 0) return null;
  const filled = required.filter(f => f.filled).length;
  return Math.round((filled / required.length) * 100);
}
