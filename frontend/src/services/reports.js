/**
 * services/reports.js — diagnosis reports and the DNA sections derived from them.
 *
 * Founder DNA and Business DNA are *outputs of a diagnosis*, not profile fields.
 * A founder who has not run one has no DNA — and the UI must say so rather than
 * showing a plausible-looking archetype, which is what it did before this was
 * wired. A fabricated profile that reads as real is worse than an empty state:
 * the founder acts on it.
 */

import { del, get, post } from './api';

/**
 * The report as a rendered HTML document — the same one the PDF is built from.
 *
 * The page mounts this rather than re-implementing the layout in JSX, because a
 * second implementation is exactly how the PDF drifted from the screen before.
 * One builder on the server, one flag between the two outputs.
 */
export function getReportDocument(reportId) {
  return get(`/reports/${reportId}/document`, { responseType: 'text' });
}

/**
 * Download the PDF of this report.
 *
 * Rejects rather than resolving on failure: the export endpoint answers 503 when
 * the renderer is momentarily down, and that is a real "try again shortly", not
 * a file. Handing the founder a broken download would be worse than saying so.
 */
export async function downloadReportPdf(reportId) {
  let blob;
  try {
    blob = await post(`/reports/${reportId}/export`, null, { responseType: 'blob' });
  } catch (err) {
    // responseType 'blob' applies to error responses too, so the API's own
    // founder-facing sentence arrives as an unread Blob and normalizeError
    // falls back to axios's "Request failed with status code 503". Read it back
    // out: the endpoint writes a better message than any generic one we'd
    // substitute here, and it is the one the founder should see.
    if (err?.data instanceof Blob) {
      try {
        const parsed = JSON.parse(await err.data.text());
        if (typeof parsed?.message === 'string') err.message = parsed.message;
      } catch { /* not JSON — keep the normalized message */ }
    }
    throw err;
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `clarity-report-${reportId}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Next tick — revoking synchronously can cancel the download before the
  // browser has finished reading the blob.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

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

/** Keys inside a fact object that describe the report's machinery, not the founder.
 *
 * `red_flag_note` is a pillar's SCORING RULE, written for whoever tunes the
 * engine, and it rendered straight onto the Business DNA page: "A score below
 * 35% in this pillar triggers Section H (Psychological State Note)...". The
 * generator no longer puts it in founder-facing facts, but reports are stored
 * once and read many times, so every report generated before that fix still
 * carries it -- this filter is what keeps those readable. */
const INTERNAL_FACT_KEYS = new Set([
  'code', 'is_confident', 'tentative', 'narrator', 'red_flag_note',
]);

/** Top-level fact keys that drive rendering rather than telling the founder
 *  anything: `cta` is a flag the discovery-call section sets for itself, and
 *  surfaced as a fact it read "Cta: true". */
const INTERNAL_TOP_LEVEL_KEYS = new Set(['cta']);

function readable(value) {
  if (Array.isArray(value)) return value.map(readable).filter(Boolean).join(', ');
  if (value && typeof value === 'object') {
    // Nested objects (e.g. `archetype`) would otherwise render as "[object Object]".
    // Flatten to "Name · Motivation" style, dropping the internal bookkeeping.
    //
    // Booleans are dropped here rather than printed: this flattener throws the
    // KEY away and joins only the values, so a bare "false" carries no meaning
    // at all. Every business-DNA pillar carries `red_flag_triggered: false`,
    // which rendered as "Founder Readiness · <band description> · false" and
    // "Market Clarity · false" straight onto the report. Dropping them
    // structurally also means the next flag someone adds to a nested fact can't
    // leak the same way -- INTERNAL_FACT_KEYS only catches names known today.
    return Object.entries(value)
      .filter(([k, v]) => !INTERNAL_FACT_KEYS.has(k) && typeof v !== 'boolean'
                          && v !== null && v !== undefined && v !== '')
      .map(([, v]) => readable(v))
      .join(' · ');
  }
  // A top-level boolean keeps its label, so it stays -- but as words. `String(true)`
  // put a literal "true" under the heading "Provisional" on the founder's report.
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
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
    .filter(([key, v]) => !key.startsWith('_') && !INTERNAL_TOP_LEVEL_KEYS.has(key) &&
                          v !== null && v !== undefined && v !== '' &&
                          !(Array.isArray(v) && v.length === 0))
    .map(([key, value]) => ({
      label: key.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()),
      value: readable(value),
    }))
    .filter(f => f.value !== '');
}

/**
 * Business DNA pillars as structured rows, not the flattened strings factList()
 * produces.
 *
 * The generic flattener joins a pillar's fields into one line -- "Retention ·
 * Critical Gap · <description>" -- which is all a text card ever needed. A card
 * that colours itself by band, or fills a bar from it, has to read the band as
 * its own value, so it gets its own reader rather than parsing that string back
 * apart.
 *
 * Returns [] when the section carries no pillars, which is the honest answer
 * for a report that predates them or for a variant that omits Business DNA --
 * the caller falls back to the generic fact grid rather than showing an empty
 * scaffold.
 */
export function pillarList(facts) {
  const raw = facts?.pillars;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((p) => p && typeof p === 'object' && p.pillar_name)
    .map((p) => ({
      name: String(p.pillar_name),
      band: p.band ? String(p.band) : null,
      description: p.band_description ? String(p.band_description) : '',
      redFlag: Boolean(p.red_flag_triggered),
    }));
}

/**
 * A public link to this report. The shared view is a strict subset — headings
 * and prose only, no scores, facts or reasoning — so sharing one cannot leak
 * the engine's internals to whoever the founder sends it to.
 */
export function createShareLink(reportId) {
  return post(`/reports/${reportId}/share`, {});
}

/**
 * Every live share link for this report, so a founder can see what is out there.
 *
 * Carries access_count and last_accessed_at, which is the part that matters:
 * deciding whether to revoke a link is a different decision when it has been
 * opened eleven times than when it has never been opened at all.
 */
export function listShareLinks(reportId) {
  return get(`/reports/${reportId}/shares`);
}

/**
 * Revoke one share link, immediately and permanently.
 *
 * This existed on the API from the start and nothing in the app ever called it,
 * so a founder could publish a link to their own diagnosis -- readable by anyone
 * holding it, no sign-in -- and then had no way to take it back for thirty days
 * except emailing support.
 */
export function revokeShareLink(reportId, token) {
  return del(`/reports/${reportId}/share/${encodeURIComponent(token)}`);
}
