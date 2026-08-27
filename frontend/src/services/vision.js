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

import { del, get, post, put } from './api';

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
  // imageUrl is null, never '', when nothing is attached -- the card branches
  // on it, and an empty string is truthy enough to render a broken <img>.
  return { statement: t.statement, tag1: t.tag1, tag2: t.tag2, imageUrl: t.image_url ?? null };
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

/** PNG/JPEG/WEBP under 5MB, matching what the endpoint accepts. Checked here
 *  too so an obviously wrong file is refused instantly instead of after a
 *  5MB round-trip. */
export const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

export function imageProblem(file) {
  if (!file) return 'No file selected.';
  if (!IMAGE_TYPES.includes((file.type || '').toLowerCase())) return 'Use a PNG, JPEG or WEBP image.';
  if (file.size > MAX_IMAGE_BYTES) return 'That image is too large — please pick one under 5MB.';
  return null;
}

/** Attach a picture to one territory. Returns the whole territory, not just
 *  the URL: the server sends back the stored row, so the caller replaces its
 *  copy wholesale rather than merging a URL into possibly-stale text. */
export async function uploadTerritoryImage(key, file) {
  const form = new FormData();
  form.append('file', file);
  const t = await post(`/vision/territories/${key}/image`, form, {
    headers: { 'Content-Type': undefined },
  });
  return toTerritory(t);
}

export async function removeTerritoryImage(key) {
  const t = await del(`/vision/territories/${key}/image`);
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
