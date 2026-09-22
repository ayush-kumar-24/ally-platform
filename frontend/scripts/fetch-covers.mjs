/**
 * Fill src/data/covers.json with a cover image for every book and film.
 *
 * WHY A SCRIPT AND NOT A FIELD IN read.js / watch.js. There are 128 books and
 * the films besides, and a cover is not editorial judgement -- it is a lookup
 * whose answer can change when a source re-scans an edition. Keeping it in a
 * generated file means the curated lists stay hand-written and reviewable, and
 * refreshing every cover is one command that touches one file.
 *
 * WHY OPEN LIBRARY. It publishes covers for third parties to display, which is
 * what makes hot-linking them the ordinary posture rather than copying 128
 * pieces of copyrighted cover art onto our own bucket. The URLs written here
 * point at their CDN; we host nothing.
 *
 * RUN IT WHERE THERE IS NETWORK:
 *
 *     node scripts/fetch-covers.mjs            # fill in the gaps
 *     node scripts/fetch-covers.mjs --refresh  # re-look-up the books
 *
 * It is incremental by default, so a run that is interrupted or rate-limited
 * can simply be run again -- it only asks about ids it has no answer for.
 * Nothing it cannot find is written, and the card falls back to the text-only
 * tile it shows today, so a partial run is a perfectly shippable state.
 */

import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(HERE, '../src/data/covers.json');

const SEARCH = 'https://openlibrary.org/search.json';
const COVER = (id) => `https://covers.openlibrary.org/b/id/${id}-M.jpg`;
const LOCAL_DIR = resolve(HERE, '../public/covers');

// Open Library asks for a contactable agent on automated reads.
const HEADERS = { 'User-Agent': 'GoXL-Ally/1.0 (info@goxl.in)' };

// Polite spacing. Their guidance is to stay well under 100/minute; this is ~4.
const GAP_MS = 250;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const norm = (s) => (s || '')
  .toLowerCase()
  .replace(/[^a-z0-9 ]+/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

/* `by` is written for a READER, not for a search index: "A.P.J. Abdul Kalam
   with Arun Tiwari", "Clayton Christensen and others", "Brad Feld & Jason
   Mendelson", "Saurabh Mukherjea, Rakshit Ranjan & Pranab Uniyal". Passed
   whole to Open Library's author filter, every one of those matches nothing --
   which is why the first run missed Wings of Fire and Competing Against Luck,
   books the catalogue certainly holds. Only the first name is used. */
const firstAuthor = (by) =>
  (by || '').split(/\s+(?:with|and others|and|&)\s+|,/i)[0].trim();

/* Open Library indexes "Mindset", not "Mindset: The New Psychology of
   Success". Dropping the subtitle is the single biggest recovery in the
   cascade below. */
const mainTitle = (title) => title.split(/[:—–]/)[0].trim();

/* A LOOSER SEARCH CAN RETURN THE WRONG BOOK, and a wrong cover is worse than
   none -- nobody reports a missing picture, everybody notices Principles
   showing someone else's jacket. So every candidate is checked before it is
   accepted: the titles must actually correspond, and where we know an author,
   one of their name-parts must appear in the record's authors. */
function plausible(doc, { title, author }) {
  const want = norm(mainTitle(title));
  const got = norm(doc.title);
  if (!got || !want) return false;
  const titleOk = got === want || got.startsWith(want) || want.startsWith(got);
  if (!titleOk) return false;

  if (!author) return true;
  const names = norm((doc.author_name || []).join(' '));
  // Parts of 4+ characters only: "A.P.J." and "de" match everything.
  const parts = norm(author).split(' ').filter((w) => w.length >= 4);
  return parts.length === 0 || parts.some((w) => names.includes(w));
}

async function query(params) {
  const res = await fetch(`${SEARCH}?${new URLSearchParams(params)}`, { headers: HEADERS });
  if (!res.ok) throw new Error(`search ${res.status}`);
  const { docs = [] } = await res.json();
  return docs;
}

async function coverFor({ title, by }) {
  const author = firstAuthor(by);
  const fields = 'cover_i,title,author_name';

  /* Narrowest first, so the confident answer wins and the loose fallbacks are
     only reached for the records that need them. limit=20, not 3: a book with
     hundreds of editions can easily have twenty unscanned ones at the front,
     which is the other half of why the first run missed so many. */
  const attempts = [
    { title, author, limit: '20', fields },
    { title: mainTitle(title), author, limit: '20', fields },
    { title: mainTitle(title), limit: '20', fields },
    { q: `${mainTitle(title)} ${author}`.trim(), limit: '20', fields },
  ];

  for (const params of attempts) {
    if (params.author === '') delete params.author;
    const docs = await query(params);
    const hit = docs.find((d) => d.cover_i && plausible(d, { title, author }));
    if (hit) return COVER(hit.cover_i);
    await sleep(GAP_MS);
  }
  return null;
}

/* A cover dropped into public/covers/<id>.<ext> wins over any lookup.

   That is the escape hatch for the handful the catalogue genuinely does not
   have -- several of these are Indian editions nobody has scanned. Drop the
   file in, re-run, and it is picked up; no edit to this script or to the data. */
const LOCAL_EXTS = ['jpg', 'jpeg', 'png', 'webp'];
function localCover(id) {
  for (const ext of LOCAL_EXTS) {
    if (existsSync(resolve(LOCAL_DIR, `${id}.${ext}`))) return `/covers/${id}.${ext}`;
  }
  return null;
}

const refresh = process.argv.includes('--refresh');
const existing = JSON.parse(readFileSync(OUT, 'utf8'));

/* BOOKS ONLY, deliberately.

   Open Library is a library catalogue: it has book covers and nothing else.
   The films, series and podcasts under "Things to watch" need a different
   source, so pointing this script at them would write 60-odd wrong answers
   rather than none. Podcast artwork has its own script now
   (fetch-podcast-art.mjs, which reads Apple's free search API); the films and
   series still have none, because TMDB wants an API key.

   The rendering side is source-agnostic -- covers.json is a flat id -> URL
   map and the tile does not care who filled it -- so film posters can be
   added to the same file by a second script without touching the component. */
const { BOOKS } = await import('../src/data/read.js');

const items = BOOKS;

/* --refresh forgets what THIS run is about to look up, and nothing else.
   Starting from an empty object instead would drop every cover the other
   scripts filled in: covers.json is one shared map, and each script only ever
   writes its own keys back into it. */
if (refresh) for (const item of items) delete existing[item.id];
let found = 0, missed = 0, skipped = 0;

for (const item of items) {
  // Checked before the skip: a cover dropped in by hand should replace a
  // lookup result on the next run without anyone having to pass --refresh.
  const local = localCover(item.id);
  if (local) {
    if (existing[item.id] !== local) { existing[item.id] = local; found += 1; }
    else { skipped += 1; }
    writeFileSync(OUT, `${JSON.stringify(existing, null, 2)}\n`);
    continue;
  }
  if (existing[item.id]) { skipped += 1; continue; }
  try {
    const url = await coverFor(item);
    if (url) { existing[item.id] = url; found += 1; }
    else { missed += 1; console.warn(`  no cover: ${item.title}`); }
  } catch (err) {
    missed += 1;
    console.warn(`  failed:   ${item.title} -- ${err.message}`);
  }
  await sleep(GAP_MS);
  // Written as we go, so a run killed halfway keeps what it already found.
  writeFileSync(OUT, `${JSON.stringify(existing, null, 2)}\n`);
}

console.log(`\n${items.length} titles: ${found} found, ${missed} without a cover, ${skipped} already had one.`);
console.log(`Written to ${OUT}`);
