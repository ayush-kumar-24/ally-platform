/**
 * services/reports.js — diagnosis reports and the DNA sections derived from them.
 *
 * Founder DNA and Business DNA are *outputs of a diagnosis*, not profile fields.
 * A founder who has not run one has no DNA — and the UI must say so rather than
 * showing a plausible-looking archetype, which is what it did before this was
 * wired. A fabricated profile that reads as real is worse than an empty state:
 * the founder acts on it.
 */

import { get } from './api';

/** All reports for the signed-in founder, newest first. */
export function listReports() {
  return get('/intelligence/reports');
}

/** The active report, or null when no diagnosis has been completed. */
export async function getLatestReport() {
  try {
    return await get('/intelligence/reports/latest');
  } catch (err) {
    // 404 here is a legitimate answer ("no report yet"), not a failure.
    if (err.status === 404) return null;
    throw err;
  }
}

export function getReport(reportId) {
  return get(`/reports/${reportId}`);
}

/** A named section of a report. Returns null when the section isn't present. */
async function section(reportId, name) {
  try {
    const slice = await get(`/reports/${reportId}/${name}`);
    return slice?.section ?? null;
  } catch (err) {
    if (err.status === 404) return null;
    throw err;
  }
}

export const getFounderDna = (reportId) => section(reportId, 'founder-dna');
export const getBusinessDna = (reportId) => section(reportId, 'business-dna');

export function getInsights(reportId) {
  return get(`/reports/${reportId}/insights`);
}

export function getRecommendations(reportId) {
  return get(`/reports/${reportId}/recommendations`);
}

/**
 * Load one DNA section, resolving the latest report first.
 *
 * Returns `{ status, report, section }` where status is:
 *   'ready'        — a report exists and the section is present
 *   'no-report'    — no diagnosis completed yet (offer to start one)
 *   'no-section'   — report exists but this section was not generated
 *   'error'        — something actually failed
 *
 * Four distinct states because each needs different copy. Collapsing them would
 * mean telling a founder "run a diagnosis" when they already have.
 */
export async function loadDna(which) {
  try {
    const report = await getLatestReport();
    if (!report) return { status: 'no-report', report: null, section: null };

    const id = report.report_id;
    const data = which === 'founder' ? await getFounderDna(id) : await getBusinessDna(id);
    if (!data) return { status: 'no-section', report, section: null };
    return { status: 'ready', report, section: data };
  } catch (error) {
    return { status: 'error', report: null, section: null, error };
  }
}

/** Keys inside a fact object that describe the report's machinery, not the founder. */
const INTERNAL_FACT_KEYS = new Set(['code', 'is_confident', 'tentative', 'narrator']);

function readable(value) {
  if (Array.isArray(value)) return value.map(readable).filter(Boolean).join(', ');
  if (value && typeof value === 'object') {
    // Nested objects (e.g. `archetype`) would otherwise render as "[object Object]".
    // Flatten to "Name · Motivation" style, dropping the internal bookkeeping.
    return Object.entries(value)
      .filter(([k, v]) => !INTERNAL_FACT_KEYS.has(k) && v !== null && v !== undefined && v !== '')
      .map(([, v]) => readable(v))
      .join(' · ');
  }
  return String(value);
}

/**
 * `facts` is an open object on SectionOut, so its shape varies by report.
 * Normalise it into label/value pairs the UI can render without knowing the keys.
 *
 * Underscore-prefixed keys are skipped: the generator uses them for its own
 * bookkeeping (`_narrator` records which narrator produced the section), and a
 * founder reading their DNA should not be shown "narrator: template".
 */
export function factList(facts) {
  if (!facts || typeof facts !== 'object') return [];
  return Object.entries(facts)
    .filter(([key, v]) => !key.startsWith('_') &&
                          v !== null && v !== undefined && v !== '' &&
                          !(Array.isArray(v) && v.length === 0))
    .map(([key, value]) => ({
      label: key.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()),
      value: readable(value),
    }))
    .filter(f => f.value !== '');
}
