/**
 * utils/profileDisplay.js — turning stored founder answers into readable text.
 *
 * Onboarding stores what the database needs: enum values ('one_company',
 * 'determined') and jsonb arrays (challenges, audience, support). Every screen
 * that reads those answers back to the founder needs their own words instead,
 * and none of them should be doing `.toLowerCase()` on an array.
 *
 * The label maps are derived from the question definitions themselves, so an
 * option's wording lives in exactly one place: data/onboardingQuestions.js.
 */

/* ASKABLE, not QUESTIONS: a `group` question holds its options on its PARTS,
   not on itself -- Q3's experience and revenue cards and Q9's invisible gaps
   all live one level down. Walking only the top level silently lost them,
   which showed up as a founder's experience reading back as the raw enum
   ('one_company'). This file used to keep its own copy of that flatten; it is
   shared now, because the same omission has since been made twice more (see
   the note on ASKABLE itself). */
import { ASKABLE } from '../data/onboardingQuestions';

/** { questionKey: { storedValue: shownLabel } }, built from the question set. */
const LABELS = Object.fromEntries(
  ASKABLE
    .filter((q) => Array.isArray(q.options))
    .map((q) => [
      q.key,
      Object.fromEntries(
        // An option is a bare string, a {value,label} card, or a
        // {value,paths} entry that is path-filtered but shown verbatim --
        // the last of those has no separate label to fall back to.
        q.options.map((o) => (typeof o === 'string' ? [o, o] : [o.value, o.label ?? o.value])),
      ),
    ]),
);

/** One stored value as the founder saw it. Unknown values pass through. */
export function labelFor(key, value) {
  if (value === null || value === undefined) return '';
  return LABELS[key]?.[value] ?? String(value);
}

const clean = (value) =>
  (Array.isArray(value) ? value : [value]).filter(
    (v) => v !== null && v !== undefined && v !== '',
  );

/**
 * Prose form: "Hiring, Cash flow and Scaling".
 * Safe for any answer shape — string, array, enum, missing.
 */
export function readable(key, value) {
  const items = clean(value).map((v) => labelFor(key, v));
  if (items.length === 0) return '';
  if (items.length === 1) return items[0];
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}

/** Compact form: "Hiring, Cash flow, Scaling" — for panels and chips. */
export function listed(key, value) {
  return clean(value).map((v) => labelFor(key, v)).join(', ');
}

/** The first entry only — for sentences that want one thing, not all of them. */
export function primary(key, value) {
  const items = clean(value).map((v) => labelFor(key, v));
  return items[0] || '';
}

/**
 * Lowercased for mid-sentence use, without mangling names that carry their own
 * capitalisation ("Prototype / MVP" must not become "prototype / mvp").
 */
export function midSentence(text) {
  const s = String(text ?? '').trim();
  if (!s) return '';
  /* Decided per word, not for the whole string.
     The old test was /[A-Z]{2,}/ over the entire value, which needed two
     ADJACENT capitals -- so it protected MVP and AI but not D2C, B2B or SaaS,
     whose capitals are separated by a digit or lowercase. "D2C" duly rendered as
     "the lens of d2c". Testing the whole string also over-protected: any
     two-capital phrase survived, so "Growth / Scaling" would have kept its caps
     mid-sentence once the test was loosened.
     A word is left alone when it carries 2+ capitals of its own (D2C, SaaS, MVP,
     AI, B2B); ordinary words like "Growth" have one and are lowered. */
  return s
    .split(/(\s+)/)
    .map((word) => ((word.match(/[A-Z]/g) || []).length >= 2 ? word : word.toLowerCase()))
    .join('');
}
