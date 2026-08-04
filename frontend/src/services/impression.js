/**
 * services/impression.js — the read Ally formed of the founder after onboarding.
 *
 * The server generates this once from the founder's real answers and stores it,
 * so every screen in the post-onboarding funnel shows the same read rather than
 * each inventing its own from a local template.
 */

import { get } from './api';

/**
 * Returns { available, impression } where impression is
 * { bullets, read, instinct, source, generated_at }.
 *
 * Never throws: these screens are a hand-off, not a destination, and a founder
 * should not hit an error card on the way to their diagnosis. A null impression
 * means callers fall back to what they can derive locally.
 */
export async function getFirstImpression() {
  try {
    const data = await get('/impression');
    return {
      available: Boolean(data?.available),
      impression: data?.impression || null,
    };
  } catch {
    return { available: false, impression: null };
  }
}
