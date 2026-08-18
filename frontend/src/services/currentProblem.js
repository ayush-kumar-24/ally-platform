/**
 * services/currentProblem.js — the Current Problem phase.
 *
 * The third section of the Stage-Adaptive Diagnosis Framework, sitting
 * between Founder DNA and the business diagnosis. Four questions: the
 * founder states the problem in their own words, then three stage-specific
 * probes. The backend gates /diagnosis/start until this completes.
 *
 * Unlike Founder DNA this phase has a FIXED length, so progress is an honest
 * "2 of 4" rather than a dimensions-understood count.
 *
 * Progress lives on the founder row server-side, same as founderDna.js —
 * which is what makes closing the tab safe.
 */

import { get, post } from './api';

/** Begin (or resume) the phase. Idempotent — safe to call on a reload. */
export function startCurrentProblem() {
  return post('/current-problem/start', {});
}

/** Where the founder currently is. Never 404s — founder-scoped, not session-scoped. */
export function getCurrentProblem() {
  return get('/current-problem/current');
}

/**
 * Submit an answer; the response carries the next question or completion.
 *
 * Default timeout here, unlike submitFounderDnaAnswer's 45s: that phase can
 * run an LLM dimension-resolution call before responding, this one makes no
 * LLM call at all — it is a write and a fixed-order lookup.
 */
export function submitCurrentProblemAnswer({ questionId, answer }) {
  return post('/current-problem/answer', {
    current_problem_question_id: questionId,
    answer_text: answer,
  });
}

/** Flatten the API envelope. */
export function normalise(payload) {
  const q = payload?.question ?? payload?.next_question ?? null;
  const p = payload?.progress ?? {};
  return {
    answered: p.questions_answered ?? 0,
    total: p.questions_total ?? 0,
    complete: p.is_complete === true,
    question: q && {
      id: q.current_problem_question_id,
      text: q.question_text ?? '',
      arcPosition: q.arc_position ?? 0,
      // The opening question — the founder's own words, which the report
      // quotes verbatim. The UI frames it differently for that reason.
      isSymptom: q.is_symptom === true,
    },
    // Only GET /current sends this — POST /answer has no reason to resend
    // what the client just watched happen. Absent there, not empty.
    history: (payload?.history ?? []).map(h => ({
      questionText: h.question_text,
      answerText: h.answer_text,
      isSymptom: h.is_symptom === true,
      answeredAt: h.answered_at,
    })),
  };
}

/** Resume if in progress, otherwise start. Callers shouldn't care which. */
export async function resumeOrStartCurrentProblem() {
  const current = normalise(await getCurrentProblem());
  if (current.question || current.complete) return current;
  return normalise(await startCurrentProblem());
}
