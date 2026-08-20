/**
 * services/frameworks.js — the founder's personal thinking toolkit.
 *
 * FRAMEWORKS itself is static reference content (what the framework is, when
 * to reach for it, how to apply it) -- a built-in library, same idea as
 * HelpSupport's FAQ list, not a claim that it was derived from this founder's
 * data. What must NOT be static is "last used" and the personal note: the
 * reference mockup shows a real date and a specific reflection per framework
 * ("Used on the pricing pivot...") as if Ally had been watching the founder
 * apply it. Nothing does that. So those two fields are real, local, and
 * start empty/"Not used yet" -- exactly the mockup's own honest fallback for
 * Ikigai -- until the founder actually opens the framework or writes a note.
 */

const USED_KEY_PREFIX = 'ally.frameworks.used.';
const NOTE_KEY_PREFIX = 'ally.frameworks.note.';

function usedKey(founderId) {
  return `${USED_KEY_PREFIX}${founderId || 'anon'}`;
}

function noteKey(founderId) {
  return `${NOTE_KEY_PREFIX}${founderId || 'anon'}`;
}

function readMap(key) {
  try {
    const raw = localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

/** { [frameworkId]: isoTimestamp } for every framework this founder has actually opened. */
export function loadLastUsed(founderId) {
  return readMap(usedKey(founderId));
}

/** Records "opened this framework right now" -- called when the founder actually
 *  navigates into a framework's detail page, not on every render. */
export function recordUsed(founderId, frameworkId, whenIso) {
  const map = readMap(usedKey(founderId));
  map[frameworkId] = whenIso;
  localStorage.setItem(usedKey(founderId), JSON.stringify(map));
  return map;
}

/** { [frameworkId]: noteText } -- the founder's own reflection, never AI-written. */
export function loadNotes(founderId) {
  return readMap(noteKey(founderId));
}

export function saveNote(founderId, frameworkId, text) {
  const map = readMap(noteKey(founderId));
  if (text.trim()) map[frameworkId] = text.trim();
  else delete map[frameworkId];
  localStorage.setItem(noteKey(founderId), JSON.stringify(map));
  return map;
}

/** "12 Aug 2026" — matches the mockup's date style. */
export function formatUsedDate(iso) {
  if (!iso) return 'Not used yet';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'Not used yet';
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}
