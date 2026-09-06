/**
 * The help bot's API.
 *
 * Answers come from `support_bot_answers` -- 277 published answers, each checked
 * against the running product -- rather than from a list bundled into the app.
 * That is the whole point: the team can correct an answer in the database and
 * every founder sees the correction, with no deploy.
 *
 * EVERY CALL HERE IS OPTIONAL. The widget falls back to its built-in list if any
 * of this fails, so these return null rather than throwing on a bad response.
 * A help widget that shows an error is worse than one that quietly answers from
 * a shorter list.
 */

import { get, post } from './api';

/**
 * Ask a question about the product.
 *
 * Resolves to `{ answer, answered, escalate, links, sources, reason }`, or null
 * if the call failed. `answer` is always safe to render as-is -- the backend
 * has an honest reply for content-missing, model-down and nothing-matched, and
 * never returns an empty one.
 */
export async function askSupport(question) {
  const res = await post('/support/ask', { question });
  return res?.answer ? res : null;
}

/**
 * The published answers, grouped, for the Help page's own list.
 *
 * Returns [] rather than null on failure so a caller can render an empty
 * section without a null check.
 */
export async function getSupportFaq(limit) {
  try {
    // Axios config, not a bare params object -- `get(url, config)`.
    const res = await get('/support/faq', limit ? { params: { limit } } : undefined);
    return Array.isArray(res) ? res : [];
  } catch {
    return [];
  }
}

/**
 * Whether the content table is loaded, and how many topics are in it.
 *
 * The widget calls this once on mount so it can decide up front between the
 * live bot and its built-in list, rather than discovering the gap on a
 * founder's first question. Returns null if it cannot tell.
 */
export async function getSupportStatus() {
  try {
    const res = await get('/support/status');
    return typeof res?.available === 'boolean' ? res : null;
  } catch {
    return null;
  }
}
