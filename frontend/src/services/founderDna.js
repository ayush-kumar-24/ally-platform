/**
 * services/founderDna.js — the Founder DNA phase.
 *
 * The identity half of the journey, asked BEFORE the business diagnosis:
 * fourteen dimensions (the GoXL Founder DNA doc's thirteen plus Emotional
 * Intelligence), 14-16 questions, ending on a deliberately larger closing
 * question. The backend gates /diagnosis/start until this completes.
 *
 * Progress lives on the founder row server-side, not here, which is what
 * makes closing the tab safe — same reason services/diagnosis.js keeps its
 * session on the server.
 */

import { get, post } from './api';

/** Begin (or resume) the phase. Idempotent — safe to call on a reload. */
export function startFounderDna() {
  return post('/founder-dna/start', {});
}

/**
 * Where the founder currently is. Unlike /diagnosis/current this never 404s:
 * the phase is founder-scoped rather than session-scoped, so "not started"
 * and "finished" are both legitimate states of the same resource.
 */
export function getCurrentFounderDna() {
  return get('/founder-dna/current');
}

/**
 * Submit an answer; the response carries the next question or completion.
 *
 * 45s timeout, matching submitAnswer in services/diagnosis.js and for the
 * same measured reason: this call can run an LLM dimension-resolution
 * judgement before it returns, which puts it well past api.js's 20s default.
 * A client-side give-up there would show a false failure for an answer the
 * server goes on to save.
 */
export function submitFounderDnaAnswer({ questionId, answer }) {
  return post('/founder-dna/answer', {
    founder_dna_question_id: questionId,
    answer_text: answer,
  }, { timeout: 45_000 });
}

/**
 * Flatten the API envelope.
 *
 * Deliberately carries `format` and `options` through. The sibling
 * normaliser in services/diagnosis.js drops question_type at exactly this
 * boundary, which is why every diagnosis question renders as a textarea
 * regardless of its type — a forced-choice question sent down that path
 * would show its options as prose the founder has to retype. This one keeps
 * them so FounderDnaChat can render the right control.
 */
export function normalise(payload) {
  const q = payload?.question ?? payload?.next_question ?? null;
  const p = payload?.progress ?? {};
  return {
    answered: p.questions_answered ?? 0,
    resolved: p.dimensions_resolved ?? [],
    remaining: p.dimensions_remaining ?? [],
    complete: p.is_complete === true,
    // POST /answer only. `false` means the input wasn't an answer to the
    // question -- nothing was stored, `question` is the SAME question, and
    // `reprompt` is what Ally says back. Defaults to true so /start and
    // /current, which never send it, aren't read as rejections.
    accepted: payload?.accepted !== false,
    reprompt: payload?.reprompt ?? null,
    question: q && {
      id: q.founder_dna_question_id,
      text: q.question_text ?? '',
      dimension: q.dimension_code ?? null,
      format: q.format ?? 'narrative',
      options: q.options ?? null,
      isClosing: q.is_closing === true,
    },
    // Only GET /current sends this — POST /answer has no reason to resend
    // what the client just watched happen. Absent there, not empty.
    history: (payload?.history ?? []).map(h => ({
      questionText: h.question_text,
      dimension: h.dimension_code,
      answerText: h.answer_text,
      answeredAt: h.answered_at,
    })),
  };
}

/**
 * Human labels for dimension_code. Kept here rather than derived by
 * title-casing the code, because several would read wrong: "Emotional
 * Intelligence" not "Emotional intelligence", "Purpose & Mission" not
 * "Purpose mission", "Strengths & Blind Spots" not "Strengths blind spots".
 * Mirrors _DNA_LABELS in backend/app/api/v1/reports/print_html.py — change
 * both together.
 */
export const DIMENSION_LABELS = {
  archetype: 'Archetype',
  core_motivation: 'Core Motivation',
  origin: 'Your Origin',
  purpose_mission: 'Purpose & Mission',
  vision: 'Vision',
  core_values: 'Core Values',
  mindset_excellence: 'Mindset & Excellence',
  strengths_blind_spots: 'Strengths & Blind Spots',
  energy_patterns: 'Energy Patterns',
  stress_response: 'Stress Response',
  decision_style: 'Decision Style',
  communication_preference: 'Communication Preference',
  focus_attention: 'Focus & Attention',
  emotional_intelligence: 'Emotional Intelligence',
};

export const TOTAL_DIMENSIONS = Object.keys(DIMENSION_LABELS).length;

export function dimensionLabel(code) {
  return DIMENSION_LABELS[code] ?? code;
}

/** Resume if in progress, otherwise start. Callers shouldn't care which. */
export async function resumeOrStartFounderDna() {
  const current = normalise(await getCurrentFounderDna());
  if (current.question || current.complete) return current;
  return normalise(await startFounderDna());
}
