/**
 * The visual vocabulary for the Founder DNA and Business DNA cards.
 *
 * Two kinds of colour live here and they mean different things, which is the
 * whole reason this file exists rather than one shared palette:
 *
 *  - Business DNA colour is a JUDGEMENT. It comes from the pillar's band, which
 *    the engine actually computed, so red genuinely means "this is the weak
 *    one".
 *  - Founder DNA colour is an IDENTITY. There is no score and no band behind a
 *    founder dimension -- the engine stores the founder's answers as text and
 *    nothing else (see backend payload.FounderDNA.phase2_dimensions). Colour
 *    there distinguishes one dimension from the next and says nothing about how
 *    well the founder is doing, because there is nothing to say it from.
 *
 * That distinction is why Founder DNA cards carry no progress bar. A bar is a
 * measurement; drawing one from a value that does not exist would invent a
 * grade for a founder's own psychology, which is the one thing this page must
 * never do.
 */

/** Band label (backend score_bands) -> the tone class the CSS colours from. */
const BAND_TONE = {
  'critical gap': 'fd-cat-red',
  'developing': 'fd-cat-orange',
  'watch': 'fd-cat-orange',
  'strong': 'fd-cat-green',
  'healthy': 'fd-cat-green',
};

/**
 * How full the bar sits for a band.
 *
 * Three steps, not a percentage. The band IS the resolution the engine
 * publishes -- the underlying score is deliberately not exposed
 * (PillarFinding.score, "engine-internal: NOT exposed in the report") -- so a
 * bar drawn at, say, 47% would be claiming a precision the page was not given.
 * Even thirds read as "one of three levels", which is exactly what is known.
 */
const BAND_FILL = {
  'fd-cat-red': 33,
  'fd-cat-orange': 66,
  'fd-cat-green': 100,
};

export function bandTone(band) {
  if (!band) return 'fd-cat-orange';
  return BAND_TONE[String(band).trim().toLowerCase()] || 'fd-cat-orange';
}

export function bandFill(band) {
  return BAND_FILL[bandTone(band)] ?? 66;
}

/* ---- icons ------------------------------------------------------------
   Drawn inline rather than imported from utils/icons so a dimension can get a
   glyph that actually depicts it. Each is a bare <path>/<circle> set; the card
   supplies the <svg> wrapper and stroke styling. */

const ICONS = {
  retention: <><path d="M3 12a9 9 0 1 0 3-6.7" /><polyline points="3 4 3 9 8 9" /></>,
  acquisition: <><circle cx="9" cy="8" r="3.2" /><path d="M3 20a6 6 0 0 1 12 0" /><path d="M18 8v6M21 11h-6" /></>,
  product: <><path d="M12 3 3 7.5v9L12 21l9-4.5v-9L12 3Z" /><path d="M3 7.5 12 12l9-4.5M12 12v9" /></>,
  sales: <><polyline points="3 17 9 11 13 15 21 7" /><polyline points="21 12 21 7 16 7" /></>,
  cash: <><rect x="2.5" y="6" width="19" height="12" rx="2" /><circle cx="12" cy="12" r="2.5" /></>,
  team: <><circle cx="9" cy="8" r="3" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0" /><path d="M17 6.2a3 3 0 0 1 0 5.6M18 20a6 6 0 0 0-3-5.2" /></>,
  strategy: <><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4" /><circle cx="12" cy="12" r="1" /></>,
  pricing: <><path d="M20.6 13.4 12 22l-9-9V4h9l8.6 8.6a1.4 1.4 0 0 1 0 2Z" /><circle cx="7.5" cy="7.5" r="1.4" /></>,
  founder: <><circle cx="12" cy="8" r="3.4" /><path d="M5 20a7 7 0 0 1 14 0" /></>,
  market: <><circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h17M12 3.5c2.4 2.6 2.4 14.4 0 17M12 3.5c-2.4 2.6-2.4 14.4 0 17" /></>,

  decision: <><path d="M12 3v6M12 15v6" /><circle cx="12" cy="12" r="3" /><path d="M5 8l3 2M19 8l-3 2" /></>,
  communication: <><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></>,
  stress: <><polyline points="2 12 6 12 9 5 15 19 18 12 22 12" /></>,
  blindspot: <><path d="M3 3l18 18" /><path d="M10.6 5.3A9.6 9.6 0 0 1 12 5c5 0 9 4.5 9 7a12 12 0 0 1-2.2 3.3M6.6 6.9C4.2 8.4 3 10.6 3 12c0 2.5 4 7 9 7a9.7 9.7 0 0 0 4-.9" /></>,
  values: <><path d="M12 20s-7-4.4-7-9.3A4 4 0 0 1 12 8a4 4 0 0 1 7 2.7C19 15.6 12 20 12 20Z" /></>,
  purpose: <><circle cx="12" cy="12" r="8.5" /><path d="m8.5 12 2.5 2.5 4.5-5" /></>,
  energy: <><polygon points="13 2 4 14 11 14 10 22 20 10 13 10 13 2" /></>,
  focus: <><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></>,
  mindset: <><path d="M9 20a4 4 0 0 1-1-7.9A4.5 4.5 0 0 1 12 4a4.5 4.5 0 0 1 4 8.1A4 4 0 0 1 15 20Z" /><path d="M12 4v16" /></>,
  motivation: <><path d="M5 21V9l7-6 7 6v12" /><path d="M10 21v-6h4v6" /></>,
  eq: <><path d="M12 20s-7-4.4-7-9.3A4 4 0 0 1 12 8a4 4 0 0 1 7 2.7C19 15.6 12 20 12 20Z" /><path d="M9.5 11h5" /></>,
  generic: <><circle cx="12" cy="12" r="8.5" /><path d="M12 8v4l3 2" /></>,
};

/* Matched on words rather than exact keys: the pillar names come from a
   database table an operator can rename, and the founder-dimension keys are an
   open set the backend adds to without touching this file. A miss falls back to
   the generic glyph, which is a duller card -- never a broken one. */
const MATCHERS = [
  [/retent|churn|loyal/, 'retention'],
  [/acquisit|growth|lead|funnel/, 'acquisition'],
  [/product|offering|solution/, 'product'],
  [/sales|pipeline|convers/, 'sales'],
  [/cash|financ|revenue|runway|money/, 'cash'],
  [/team|people|hiring|talent/, 'team'],
  [/strateg|position|vision|clarity/, 'strategy'],
  [/pricing|price|monetis|monetiz/, 'pricing'],
  [/founder.*readiness|readiness/, 'founder'],
  [/market/, 'market'],

  [/decision/, 'decision'],
  [/communicat/, 'communication'],
  [/stress|pressure|resilien/, 'stress'],
  [/blind|strength/, 'blindspot'],
  [/value/, 'values'],
  [/purpose|mission/, 'purpose'],
  [/energy/, 'energy'],
  [/focus|attention/, 'focus'],
  [/mindset|excellence|learning/, 'mindset'],
  [/motivat|drive/, 'motivation'],
  [/emotional|intellig|empath/, 'eq'],
];

export function iconFor(label) {
  const text = String(label || '').toLowerCase();
  const hit = MATCHERS.find(([re]) => re.test(text));
  return ICONS[hit ? hit[1] : 'generic'];
}

/* Founder DNA accent, assigned by position rather than meaning -- see the note
   at the top of this file. Kept to the product's own greens and warm neutrals
   so a wall of cards still reads as one page rather than a paint chart. */
const ACCENTS = ['fd-accent-1', 'fd-accent-2', 'fd-accent-3', 'fd-accent-4', 'fd-accent-5'];

export function accentFor(index) {
  return ACCENTS[index % ACCENTS.length];
}
