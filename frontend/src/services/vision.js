/**
 * services/vision.js — the founder's long-term vision, kept in front of them.
 *
 * Frontend-only for now: no backend model exists for this yet, so it lives in
 * localStorage rather than pretending to be synced across devices. Keyed by
 * founder id (falling back to a shared key only when no id is known yet) so
 * two founders signing into the same browser don't see each other's vision.
 *
 * Nothing here is pre-filled with sample numbers. The reference mockup this
 * was built from ships demo copy ("Build a ₹100Cr company...") baked into
 * every card -- shipping that as this founder's actual vision would be the
 * exact bug this codebase's other services go out of their way to avoid
 * (see e.g. NextSteps.jsx's note on the deleted ACTIONS list). Every
 * territory starts genuinely empty until the founder writes their own.
 */

const KEY_PREFIX = 'ally.vision.';

/** The six vision territories, in the order they're shown. */
export const TERRITORIES = [
  { key: 'life', label: 'My Life', placeholder: 'What does your day-to-day actually look like?' },
  { key: 'business', label: 'My Business', placeholder: 'What has the business become?' },
  { key: 'impact', label: 'My Impact', placeholder: 'Who is better off because this exists?' },
  { key: 'financial', label: 'My Financial Future', placeholder: 'What does financial freedom mean to you?' },
  { key: 'ideal_day', label: 'My Ideal Day', placeholder: 'Walk through it, hour by hour.' },
  { key: 'legacy', label: 'My Legacy', placeholder: 'What outlasts you?' },
];

function keyFor(founderId) {
  return `${KEY_PREFIX}${founderId || 'anon'}`;
}

const EMPTY_TERRITORY = { statement: '', tag1: '', tag2: '' };

function emptyVision() {
  return {
    territories: Object.fromEntries(TERRITORIES.map(t => [t.key, { ...EMPTY_TERRITORY }])),
    summary: { target: '', current: '', unit: '' },
  };
}

/** Load the founder's saved vision, or an empty shape if they haven't written one yet. */
export function loadVision(founderId) {
  try {
    const raw = localStorage.getItem(keyFor(founderId));
    if (!raw) return emptyVision();
    const parsed = JSON.parse(raw);
    // Merge over the empty shape so an older save (fewer territories, e.g.)
    // never crashes the page on a field that doesn't exist yet.
    const base = emptyVision();
    return {
      territories: { ...base.territories, ...(parsed.territories || {}) },
      summary: { ...base.summary, ...(parsed.summary || {}) },
    };
  } catch {
    return emptyVision();
  }
}

export function saveVision(founderId, vision) {
  localStorage.setItem(keyFor(founderId), JSON.stringify(vision));
}

/** Numeric gap between target and current, when both parse as plain numbers
 *  (same free-text unit assumed for both -- this is a founder's own two
 *  fields, not two different currencies). Returns null when either is blank
 *  or not a number, rather than guessing. */
export function computeGap(target, current) {
  const t = parseFloat(String(target).replace(/[^\d.-]/g, ''));
  const c = parseFloat(String(current).replace(/[^\d.-]/g, ''));
  if (Number.isNaN(t) || Number.isNaN(c)) return null;
  return t - c;
}
