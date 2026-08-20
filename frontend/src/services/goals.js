/**
 * services/goals.js — longer-horizon founder/business/life goals.
 *
 * Backed by the real /goals endpoints (see backend/app/founder_goals) --
 * previously this lived in localStorage; moved server-side so a goal
 * survives a cache-clear and shows up on another device/login. Nothing is
 * pre-filled with the reference mockup's sample goals ("₹5Cr annual
 * revenue", "Retention at 80%"...) -- those are one fictional founder's
 * numbers, not whoever is signed in. Unlike Achievements, there's no
 * engagement gate: setting a goal doesn't require Ally to have learned
 * anything first, so this is usable immediately.
 *
 * Deliberately a different backend concept from Plan Your Day's nested
 * Goal (under /planning/plans/:id/goals) -- that one is a near-term action
 * item under a paid plan; this is a free-standing, free, longer-horizon
 * outcome. See backend/app/founder_goals/models.py for the full reasoning.
 */

import { del, get, patch, post } from './api';

function toGoal(g) {
  return { id: g.goal_id, title: g.title, subtitle: g.subtitle };
}

export async function listGoals() {
  const res = await get('/goals');
  return (res.goals ?? []).map(toGoal);
}

export async function createGoal({ title, subtitle = '' }) {
  const g = await post('/goals', { title, subtitle });
  return toGoal(g);
}

export async function updateGoal(id, { title, subtitle }) {
  const g = await patch(`/goals/${id}`, { title, subtitle });
  return toGoal(g);
}

export function deleteGoal(id) {
  return del(`/goals/${id}`);
}
