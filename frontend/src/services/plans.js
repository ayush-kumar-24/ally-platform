/**
 * services/plans.js — plan catalog and the signed-in founder's entitlements.
 *
 * The catalog comes from the backend rather than being duplicated here. If the
 * pricing page hard-coded its own copy of the tiers, it would eventually disagree
 * with the gate that actually enforces them — and the version the customer read is
 * the one they'd expect to be honoured.
 *
 * `can()` is for hiding controls the founder cannot use. That is a courtesy, not a
 * security boundary: every gated action is refused server-side regardless.
 */

import { get } from './api';

export const TIERS = { FREE: 'free', STARTER: 'starter', PRO: 'pro' };

/** Features the backend knows about — mirrors app/plans/catalog.py:Feature. */
export const FEATURES = {
  ALLY_CHAT: 'ally_chat',
  DIAGNOSIS: 'diagnosis',
  VOICE_DIAGNOSIS: 'voice_diagnosis',
  VOICE_CHAT: 'voice_chat',
  PLAN_YOUR_DAY: 'plan_your_day',
  KNOW_MY_ENERGY: 'know_my_energy',
  FOUNDER_DNA: 'founder_dna',
  BUSINESS_DNA: 'business_dna',
  REPORTS: 'reports',
  NEXT_STEPS: 'next_steps',
  CALL_BOOKING: 'call_booking',
};

/** Public pricing catalog. No auth required — the pricing page needs it logged out. */
export function getCatalog() {
  return get('/plans');
}

/** My plan, limits and current usage. */
export function getMyPlan() {
  return get('/plans/me');
}

/** What a 30-minute call costs me right now (free allowance or ₹300). */
export function getCallQuote() {
  return get('/plans/me/call-quote');
}

/** True when the founder's plan includes a feature. Presentation only. */
export function can(entitlements, feature) {
  return Boolean(entitlements?.features?.includes(feature));
}

/** Cheapest plan that includes a feature — for "Upgrade to X" copy. */
export function requiredPlanFor(catalog, feature) {
  const plan = (catalog?.plans ?? []).find(p => p.features?.includes(feature));
  return plan?.name ?? null;
}

/**
 * Turn a 402/403/429 from a gated call into something worth showing a person.
 * Each status means a different next step, which is why the backend keeps them
 * distinct rather than collapsing everything into one 403.
 *
 * DiagnosisAlreadyCompletedError is also a 429 (see plans/errors.py -- grouped
 * with the other "you've used your allotment" errors) but it must never say
 * "resets tomorrow": it never resets. `error.code`, the backend's own error
 * class name, is what tells the two apart -- checking status alone would show
 * a false promise that waiting helps.
 */
export function explainLimit(error) {
  if (!error) return null;
  if (error.code === 'DiagnosisAlreadyCompletedError') {
    return { kind: 'completed', title: 'Diagnosis already completed',
             message: error.detail || "You've used your one free diagnosis." };
  }
  if (error.status === 403) {
    return { kind: 'upgrade', title: 'Not on your plan',
             message: error.detail || 'Upgrade to unlock this feature.' };
  }
  if (error.status === 402) {
    return { kind: 'topup', title: 'Out of credits',
             message: error.detail || 'Top up or upgrade to keep going.' };
  }
  if (error.status === 429) {
    return { kind: 'wait', title: 'Daily limit reached',
             message: error.detail || 'Your allowance resets tomorrow.' };
  }
  return null;
}
