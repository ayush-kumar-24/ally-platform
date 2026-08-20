/**
 * services/frameworks.js — the founder's personal thinking toolkit.
 *
 * FRAMEWORKS itself (data/frameworks.js) is static reference content (what
 * the framework is, when to reach for it, how to apply it) -- a built-in
 * library, same idea as HelpSupport's FAQ list, not a claim that it was
 * derived from this founder's data. What must NOT be static is "last used"
 * and the personal note: the reference mockup shows a real date and a
 * specific reflection per framework ("Used on the pricing pivot...") as if
 * Ally had been watching the founder apply it. Nothing does that.
 *
 * Backed by the real /frameworks/usage endpoints (see
 * backend/app/framework_usage) -- previously this lived in localStorage,
 * keyed by founder id, and never survived a cache-clear or showed up on
 * another device. Those two fields are real, server-persisted, and start
 * empty/"Not used yet" -- exactly the mockup's own honest fallback for
 * Ikigai -- until the founder actually opens the framework or writes a note.
 */

import { get, post, put } from './api';

/** { [frameworkId]: isoTimestamp } for every framework this founder has actually opened. */
export async function loadLastUsed() {
  const usage = await get('/frameworks/usage');
  return Object.fromEntries(Object.entries(usage).map(([id, u]) => [id, u.last_used_at]));
}

/** { [frameworkId]: noteText } -- the founder's own reflection, never AI-written. */
export async function loadNotes() {
  const usage = await get('/frameworks/usage');
  return Object.fromEntries(
    Object.entries(usage).filter(([, u]) => u.note).map(([id, u]) => [id, u.note])
  );
}

/** Records "opened this framework right now" -- called when the founder actually
 *  navigates into a framework's detail page, not on every render. Returns the
 *  ISO timestamp the server stamped it with. */
export async function recordUsed(frameworkId) {
  const u = await post(`/frameworks/${frameworkId}/use`);
  return u.last_used_at;
}

export async function saveNote(frameworkId, text) {
  const u = await put(`/frameworks/${frameworkId}/note`, { note: text });
  return u.note;
}

/** "12 Aug 2026" — matches the mockup's date style. */
export function formatUsedDate(iso) {
  if (!iso) return 'Not used yet';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'Not used yet';
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}
