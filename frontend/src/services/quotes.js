import { get } from './api';

/**
 * The founder's two lines for today, one per surface.
 *
 * Chosen for them at midnight IST from their stage and what they are dealing
 * with, and fixed until the next one -- so this is a read, not a computation,
 * and a refresh does not reshuffle the card.
 *
 * RESOLVES TO AN EMPTY MAP RATHER THAN REJECTING. A quote card is decoration
 * on a page full of the founder's actual work; a failed request here must not
 * bubble up as an error state or an empty panel, and the card has its own
 * bundled list to fall back to.
 */
export async function getTodayQuotes() {
  try {
    const data = await get('/quotes/today');
    const out = {};
    for (const q of data?.quotes ?? []) {
      if (q?.surface && q?.text) out[q.surface] = q.text;
    }
    return out;
  } catch {
    return {};
  }
}
