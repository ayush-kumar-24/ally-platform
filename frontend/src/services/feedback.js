/**
 * services/feedback.js — what the founder thinks of what we gave them.
 *
 * Three moments ask: right after a diagnosis completes, once they've read the
 * report, and whenever they feel like it from the dashboard. Each rating is
 * stored against the thing it's about, so a low score can be traced back to the
 * diagnosis or report that earned it.
 */

import { get, post } from './api';

export const FEEDBACK = {
  DIAGNOSIS: 'diagnosis_rating',
  REPORT: 'report_rating',
  GENERAL: 'general',
};

/**
 * Submit a 1-5 rating with optional words.
 * Re-answering the same prompt updates the earlier answer server-side.
 */
export function submitFeedback({ type, rating, comment, sessionId, reportId }) {
  return post('/feedback', {
    feedback_type: type,
    rating,
    ...(comment?.trim() ? { comment: comment.trim() } : {}),
    ...(sessionId != null ? { session_id: sessionId } : {}),
    ...(reportId != null ? { report_id: reportId } : {}),
  });
}

/**
 * Everything this founder has already told us. Never throws: a prompt failing
 * to load its own history should just mean we ask, not that the page breaks.
 */
export async function listFeedback() {
  try {
    const data = await get('/feedback');
    return data?.items ?? [];
  } catch {
    return [];
  }
}

/**
 * Has this exact prompt already been answered?
 *
 * Used to decide whether to interrupt someone. Asking a founder to rate the
 * same report every time they open it is how a feedback prompt becomes
 * something people learn to dismiss without reading.
 */
export function alreadyAnswered(items, type, { sessionId, reportId } = {}) {
  return (items ?? []).some((f) => {
    if (f.feedback_type !== type) return false;
    if (sessionId != null) return f.session_id === sessionId;
    if (reportId != null) return f.report_id === reportId;
    return true;
  });
}
