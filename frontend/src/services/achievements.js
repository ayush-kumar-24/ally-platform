/**
 * services/achievements.js — Your Achievements.
 *
 * Frontend-only, same reasoning as services/vision.js: no backend model for
 * this yet, so entries are kept in localStorage, keyed per founder, and
 * nothing here is pre-filled with the reference mockup's sample wins
 * ("Crossed ₹1Cr ARR", "Zero-attrition year"...) -- those belong to one
 * fictional founder, not whoever is signed in.
 *
 * The one thing that IS real: the unlock gate. Ally can't discover
 * achievements from conversations that don't exist, so the page stays
 * locked until the founder has actually talked to Ally a meaningful
 * amount -- computed from listConversations()'s real message_count per
 * conversation, not a made-up number.
 */

import { listConversations } from './chat';

const KEY_PREFIX = 'ally.achievements.';

/** Total messages across all of a founder's conversations with Ally is the
 *  honest stand-in for "how much Ally has to work with" until a real
 *  achievement-detection feature exists on the backend. */
export const UNLOCK_MESSAGE_THRESHOLD = 15;

function keyFor(founderId) {
  return `${KEY_PREFIX}${founderId || 'anon'}`;
}

/** { messageCount, conversationCount, unlocked }, or a zeroed/locked shape
 *  if the conversation list can't be fetched -- never assume unlocked on a
 *  failure, that would open a gate nobody actually earned. */
export async function getEngagement() {
  try {
    const res = await listConversations();
    const conversations = res?.conversations ?? [];
    const messageCount = conversations.reduce((sum, c) => sum + (c.message_count || 0), 0);
    return {
      messageCount,
      conversationCount: conversations.length,
      unlocked: messageCount >= UNLOCK_MESSAGE_THRESHOLD,
    };
  } catch {
    return { messageCount: 0, conversationCount: 0, unlocked: false };
  }
}

export function loadAchievements(founderId) {
  try {
    const raw = localStorage.getItem(keyFor(founderId));
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveAchievements(founderId, list) {
  localStorage.setItem(keyFor(founderId), JSON.stringify(list));
}
