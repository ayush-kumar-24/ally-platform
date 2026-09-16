/**
 * "Good Morning" / "Good Afternoon" / "Good Evening" for right now.
 *
 * There were three of these: the dashboard computed it, Ally Chat computed it
 * with a different afternoon cutoff, and the platform header just hardcoded
 * "Good morning" -- so at 7pm the page greeted you good morning at the top and
 * good evening immediately below it.
 */
export function greetingNow(date = new Date()) {
  const h = date.getHours();
  if (h < 12) return 'Good Morning';
  if (h < 18) return 'Good Afternoon';
  return 'Good Evening';
}

/**
 * Which part of the day it is, for anything that should read differently at
 * 7am and at midnight. Shares the noon/6pm boundaries with greetingNow above
 * so a page cannot say "Good evening" beside a quote picked as afternoon;
 * night splits off at 10pm, which greetingNow has no reason to care about but
 * a quote does.
 */
export function timeSlot(date = new Date()) {
  const h = date.getHours();
  if (h < 5) return 'night';
  if (h < 12) return 'morning';
  if (h < 18) return 'afternoon';
  if (h < 22) return 'evening';
  return 'night';
}

/** Day of the year, 0-based. Used to rotate a daily pick without storing one. */
export function dayIndex(date = new Date()) {
  const start = new Date(date.getFullYear(), 0, 0);
  return Math.floor((date - start) / 86400000);
}

export function acEsc(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}

export function formatDate(d) {
  if (!d) return '';
  const date = new Date(d);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export function formatTime(d) {
  if (!d) return '';
  const date = new Date(d);
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

export function formatRelativeTime(d) {
  if (!d) return '';
  const diff = Date.now() - new Date(d).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return formatDate(d);
}

/**
 * "hie" -> "Hie". "explain me this doc" -> "Explain me this doc".
 *
 * Titles a founder typed are stored EXACTLY as typed -- no forced casing at
 * the API layer, so nobody's own capitalisation is ever silently overwritten
 * and the value they edit in a rename box is the value they saved. This is a
 * display concern only.
 *
 * It matters most in lists. A column of left-aligned rows all starting
 * lowercase ("hie", "heo", "hello there") reads as broken rather than
 * informal, and in Ally Chat's history those titles are taken from the
 * founder's first message, which is exactly the text least likely to have
 * been capitalised.
 *
 * Only the first character, deliberately: title-casing every word would
 * mangle names, acronyms and the founder's own emphasis ("explain MY DNA" is
 * not "Explain My Dna"). Non-letters are left alone -- a title starting with
 * a digit or an emoji is returned unchanged rather than mysteriously
 * reformatted.
 *
 * Was a private copy in PlanYourDay.jsx; Ally Chat's history, the Compass
 * card and the chat header all needed the same thing, which is what made it
 * shared rather than a fourth copy.
 */
export function displayTitle(title) {
  if (!title) return title;
  return title.charAt(0).toUpperCase() + title.slice(1);
}

export function clamp(v, min, max) {
  return Math.min(Math.max(v, min), max);
}

export function randomBetween(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

export function classNames(...args) {
  return args.filter(Boolean).join(' ');
}

export function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}
