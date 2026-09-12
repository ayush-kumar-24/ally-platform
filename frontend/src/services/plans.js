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

export const TIERS = { FREE: 'free', BASIC: 'basic', STARTER: 'starter', PRO: 'pro' };

/**
 * Tier id -> the name a founder is shown. These are NOT the same words, and the
 * two that differ are the ones that caused a founder who had paid to be told,
 * by our own sidebar, that they were still on "Basic":
 *
 *   basic   -> "Starter"   (Rs 199)
 *   starter -> "Plus"      (Rs 499)
 *
 * app/plans/catalog.py says so directly -- the tier ids are internal, kept
 * stable because renaming one means migrating every founders.plan_type row,
 * while Plan.name "changes with marketing". Anything that builds a label out of
 * the tier id therefore prints last season's name at best. PlatformLayout did
 * exactly that and mapped `starter` to "Ally Starter", so the Rs 499 plan and
 * the Rs 199 plan both rendered as "Ally Starter" -- two different plans, one
 * label, and no way for support to tell them apart from a screenshot.
 *
 * This map exists so a label is right immediately, offline, and before any
 * request resolves. The server's own plan_name still wins where it is
 * available (see planLabel) -- that is the copy marketing actually edits.
 */
export const PLAN_NAMES = { free: 'Free', basic: 'Starter', starter: 'Plus', pro: 'Pro' };

/**
 * The founder-facing plan label, e.g. "Ally Starter".
 *
 * `serverName` is Entitlements.plan_name from GET /plans/me -- the catalog's
 * own word for the plan, and the only one guaranteed current. Falls back to the
 * table above, then to a bare "Ally" rather than inventing a plan name out of
 * an internal id.
 */
export function planLabel(tier, serverName) {
  const name = serverName || PLAN_NAMES[String(tier || '').toLowerCase()];
  return name ? `Ally ${name}` : 'Ally';
}

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
  GOALS: 'goals',
  VISION: 'vision',
  RECOMMENDATIONS: 'recommendations',
  KNOWLEDGE_CHAT: 'knowledge_chat',
  EMAIL_NOTIFICATIONS: 'email_notifications',
  PRIORITY_CALL: 'priority_call',
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
  // Before the generic 429 below, which it would otherwise be swallowed by.
  // "Daily limit reached" is the wrong sentence here: this founder still has
  // tokens, just not enough for the turn they tried, and the backend's message
  // is the only thing that explains a refusal happening while the counter
  // beside it still reads above zero.
  if (error.code === 'TurnExceedsRemainingTokensError') {
    return { kind: 'wait', title: 'Not enough tokens left for that',
             message: error.detail || "That message needs more tokens than you have left today." };
  }
  if (error.status === 429) {
    return { kind: 'wait', title: 'Daily limit reached',
             message: error.detail || 'Your allowance resets tomorrow.' };
  }
  return null;
}

/** Prefix the streaming path uses for the same refusal -- see
 *  TOKEN_BUDGET_ERROR_CODE in app/ai_chat/streaming/schemas.py. START has
 *  already been sent by the time the cost is known, so /chat/stream cannot
 *  answer 429 and puts the code in the error event instead. */
const STREAM_TOKEN_BUDGET = 'token_budget_exceeded';

/**
 * The same notice as explainLimit(), for a refusal that arrived as a streamed
 * error event rather than an HTTP status.
 *
 * @param {string} content the ERROR chunk's text
 * @returns {{kind:string,title:string,message:string}|null}
 */
export function explainStreamLimit(content) {
  const text = String(content || '');
  if (!text.startsWith(`${STREAM_TOKEN_BUDGET}:`)) return null;
  return {
    kind: 'wait',
    title: 'Not enough tokens left for that',
    message: text.slice(STREAM_TOKEN_BUDGET.length + 1).trim()
      || "That message needs more tokens than you have left today.",
  };
}
