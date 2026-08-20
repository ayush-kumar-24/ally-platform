/**
 * services/achievements.js — Your Achievements.
 *
 * Backed by the real /achievements endpoints (see backend/app/achievements)
 * -- previously entries lived in localStorage and the engagement gate was
 * recomputed client-side from listConversations(); both now come from the
 * server, which is the single source of truth for the unlock threshold and
 * enforces the gate on creation too (a UI gate alone can be bypassed by
 * calling the API directly). Nothing here is pre-filled with the reference
 * mockup's sample wins ("Crossed ₹1Cr ARR", "Zero-attrition year"...) --
 * those belong to one fictional founder, not whoever is signed in.
 */

import { del, get, patch, post } from './api';

function toAchievement(a) {
  return {
    id: a.achievement_id,
    title: a.title,
    description: a.description,
    category: a.category,
    date: a.occurred_on,
  };
}

/** { messageCount, threshold, unlocked }, or a locked shape if the request
 *  fails -- never assume unlocked on a failure, that would open a gate
 *  nobody actually earned. */
export async function getEngagement() {
  try {
    const res = await get('/achievements/engagement');
    return { messageCount: res.message_count, threshold: res.threshold, unlocked: res.unlocked };
  } catch {
    return { messageCount: 0, threshold: 15, unlocked: false };
  }
}

export async function listAchievements() {
  const res = await get('/achievements');
  return (res.achievements ?? []).map(toAchievement);
}

export async function createAchievement({ title, description = '', category = '', date = '' }) {
  const a = await post('/achievements', { title, description, category, occurred_on: date });
  return toAchievement(a);
}

export async function updateAchievement(id, { title, description, category, date }) {
  const a = await patch(`/achievements/${id}`, {
    title, description, category,
    ...(date !== undefined ? { occurred_on: date } : {}),
  });
  return toAchievement(a);
}

export function deleteAchievement(id) {
  return del(`/achievements/${id}`);
}
