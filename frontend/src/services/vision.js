/**
 * services/vision.js — the founder's long-term vision, kept in front of them.
 *
 * Backed by the real /vision endpoints (see backend/app/vision) -- previously
 * this lived in localStorage, keyed by founder id, and never survived a
 * cache-clear or showed up on another device. The server is now the single
 * source of truth and enforces the same rules the UI does (a non-empty
 * statement to save a territory) so they can't be bypassed by calling the
 * API directly.
 *
 * Nothing here is pre-filled with sample numbers. The reference mockup this
 * was built from ships demo copy ("Build a ₹100Cr company...") baked into
 * every card -- shipping that as this founder's actual vision would be the
 * exact bug this codebase's other services go out of their way to avoid
 * (see e.g. NextSteps.jsx's note on the deleted ACTIONS list). Every
 * territory starts genuinely empty until the founder writes their own.
 */

import { get, put } from './api';

/** The six vision territories, in the order they're shown. */
export const TERRITORIES = [
  { key: 'life', label: 'My Life', placeholder: 'What does your day-to-day actually look like?' },
  { key: 'business', label: 'My Business', placeholder: 'What has the business become?' },
  { key: 'impact', label: 'My Impact', placeholder: 'Who is better off because this exists?' },
  { key: 'financial', label: 'My Financial Future', placeholder: 'What does financial freedom mean to you?' },
  { key: 'ideal_day', label: 'My Ideal Day', placeholder: 'Walk through it, hour by hour.' },
  { key: 'legacy', label: 'My Legacy', placeholder: 'What outlasts you?' },
];

function toTerritory(t) {
  return { statement: t.statement, tag1: t.tag1, tag2: t.tag2 };
}

function toSummary(s) {
  return { target: s.target, current: s.current, unit: s.unit };
}

/** { territories: {key: {statement,tag1,tag2}}, summary: {target,current,unit} } */
export async function loadVision() {
  const res = await get('/vision');
  return {
    territories: Object.fromEntries(
      TERRITORIES.map(({ key }) => [key, toTerritory(res.territories?.[key] ?? { statement: '', tag1: '', tag2: '' })])
    ),
    summary: toSummary(res.summary ?? { target: '', current: '', unit: '' }),
  };
}

export async function saveTerritory(key, { statement, tag1 = '', tag2 = '' }) {
  const t = await put(`/vision/territories/${key}`, { statement, tag1, tag2 });
  return toTerritory(t);
}

/** Partial: only the passed fields change; an omitted field keeps its
 *  previous value server-side (see VisionService.upsert_summary). */
export async function saveSummary(fields) {
  const s = await put('/vision/summary', fields);
  return toSummary(s);
}

/** Numeric gap between target and current, when both parse as plain numbers
 *  (same free-text unit assumed for both -- this is a founder's own two
 *  fields, not two different currencies). Returns null when either is blank
 *  or not a number, rather than guessing. */
export function computeGap(target, current) {
  const t = parseFloat(String(target).replace(/[^\d.-]/g, ''));
  const c = parseFloat(String(current).replace(/[^\d.-]/g, ''));
  if (Number.isNaN(t) || Number.isNaN(c)) return null;
  return t - c;
}
