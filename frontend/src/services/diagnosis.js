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
  //
  // Still 45s, and the FINAL answer no longer needs anywhere near it. That
  // request used to also run the whole reasoning pipeline inline -- profiled at
  // 203s, so it could never have fit in this timeout under any value worth
  // setting. Reasoning is now a background task (api/v1/diagnosis/router.py),
  // so every answer including the last returns in classification time. Kept at
  // 45s because the 12-15s figure above is about the per-answer LLM work, which
  // has not changed; do not read the reduced tail latency as headroom to lower
  // it. The wait for the report itself is owned by the Thinking screen, which
  // polls for the report rather than holding a request open.
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
    // Only /current sends this (POST /answer has no reason to resend
    // everything already known) -- absent there, not just empty.
    history: (payload?.history ?? []).map(h => ({
      questionText: h.question_text,
      category: h.category,
      answerText: h.answer_text,
      answeredAt: h.answered_at,
    })),
    resumed,
  };
}

export async function resumeOrStart() {
  const current = await getCurrentSession();
  if (current) return normalise(current, true);
  return normalise(await startDiagnosis(), false);
}
