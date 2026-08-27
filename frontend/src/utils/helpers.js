/**
 * "Good morning" / "Good afternoon" / "Good evening" for right now.
 *
 * There were three of these: the dashboard computed it, Ally Chat computed it
 * with a different afternoon cutoff, and the platform header just hardcoded
 * "Good morning" -- so at 7pm the page greeted you good morning at the top and
 * good evening immediately below it.
 */
export function greetingNow(date = new Date()) {
  const h = date.getHours();
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
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
