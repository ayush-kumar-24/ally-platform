/**
 * services/goals.js — longer-horizon founder/business/life goals.
 *
 * Frontend-only, same reasoning as vision.js and achievements.js: no
 * backend model for this yet, so goals live in localStorage, keyed per
 * founder. Nothing is pre-filled with the reference mockup's sample goals
 * ("₹5Cr annual revenue", "Retention at 80%"...) -- those are one fictional
 * founder's numbers, not whoever is signed in. Unlike Achievements, there's
 * no engagement gate: setting a goal doesn't require Ally to have learned
 * anything first, so this is usable immediately.
 */

const KEY_PREFIX = 'ally.goals.';

function keyFor(founderId) {
  return `${KEY_PREFIX}${founderId || 'anon'}`;
}

export function loadGoals(founderId) {
  try {
    const raw = localStorage.getItem(keyFor(founderId));
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveGoals(founderId, list) {
  localStorage.setItem(keyFor(founderId), JSON.stringify(list));
}
