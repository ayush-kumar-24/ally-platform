/**
 * services/diagnosis.js — the guided diagnosis session.
 *
 * The session lives on the server, which is what makes resume work: a founder who
 * closes the tab mid-diagnosis gets the same question back, because the frontend
 * never held the progress in the first place.
 */

import { get, post } from './api';

/** Begin a new diagnosis. Returns the first question. */
export function startDiagnosis() {
  return post('/diagnosis/start', {});
}

/**
 * The in-progress session, or null when there isn't one.
 * 404 is a legitimate answer here, not a failure.
 */
export async function getCurrentSession() {
  try {
    return await get('/diagnosis/current');
  } catch (err) {
    if (err.status === 404) return null;
    throw err;
  }
}

/**
 * Submit an answer; the response carries the next question (or completion).
 *
 * The API takes `answer_text` and infers the session from the caller's identity —
 * there is no session_id on this endpoint, which is what stops one founder
 * answering into another's session.
 */
export function submitAnswer({ questionId, answer }) {
  // Live-reproduced: this call runs an LLM answer classification AND an
  // incremental confidence recompute in series, routinely taking 12-15s and
  // observed at 23.7s once -- over api.js's default 20s timeout. When that
  // happens the client gives up and shows a false failure while the server
  // goes on to save the answer successfully seconds later; the founder's
  // next "retry" then correctly 409s because the session already moved on.
  // 45s gives real headroom without hiding a genuinely hung request forever.
  return post('/diagnosis/answer', {
    question_id: questionId,
    answer_text: answer,
  }, { timeout: 45_000 });
}

/**
 * Resume if a session exists, otherwise start a fresh one.
 * Callers shouldn't have to care which happened.
 */
/**
 * Flatten the API envelope.
 *
 * The two endpoints disagree on the field name: /current returns `question`,
 * /answer returns `next_question` plus an `is_complete` flag. Normalising here
 * means the page never has to know which call it came from.
 */
export function normalise(payload, resumed) {
  const q = payload?.question ?? payload?.next_question ?? null;
  return {
    sessionId: payload?.session?.session_id ?? payload?.session_id ?? null,
    status: payload?.session?.status ?? null,
    answered: payload?.session?.questions_answered_count ?? 0,
    complete: payload?.is_complete === true,
    question: q && {
      id: q.question_id,
      text: q.question_text ?? q.text ?? '',
      category: q.category ?? null,
      code: q.question_code ?? null,
    },
    resumed,
  };
}

export async function resumeOrStart() {
  const current = await getCurrentSession();
  if (current) return normalise(current, true);
  return normalise(await startDiagnosis(), false);
}
