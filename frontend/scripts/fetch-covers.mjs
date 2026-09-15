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
 *     node scripts/fetch-covers.mjs --refresh  # re-look-up everything
 *
 * It is incremental by default, so a run that is interrupted or rate-limited
 * can simply be run again -- it only asks about ids it has no answer for.
 * Nothing it cannot find is written, and the card falls back to the text-only
 * tile it shows today, so a partial run is a perfectly shippable state.
 */

import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(HERE, '../src/data/covers.json');

const SEARCH = 'https://openlibrary.org/search.json';
const COVER = (id) => `https://covers.openlibrary.org/b/id/${id}-M.jpg`;

// Open Library asks for a contactable agent on automated reads.
const HEADERS = { 'User-Agent': 'GoXL-Ally/1.0 (info@goxl.in)' };

// Polite spacing. Their guidance is to stay well under 100/minute; this is ~4.
const GAP_MS = 250;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function coverFor({ title, by }) {
  const params = new URLSearchParams({ title, limit: '3', fields: 'cover_i,title,author_name' });
  if (by) params.set('author', by);

  const res = await fetch(`${SEARCH}?${params}`, { headers: HEADERS });
  if (!res.ok) throw new Error(`search ${res.status}`);
  const { docs = [] } = await res.json();

  // First result that actually HAS a cover. A doc without cover_i is an
  // edition nobody scanned; taking it would write a dead URL.
  const hit = docs.find((d) => d.cover_i);
  return hit ? COVER(hit.cover_i) : null;
}

const refresh = process.argv.includes('--refresh');
const existing = refresh ? {} : JSON.parse(readFileSync(OUT, 'utf8'));

/* BOOKS ONLY, deliberately.

   Open Library is a library catalogue: it has book covers and nothing else.
   The films, series and podcasts under "Things to watch" need a different
   source (TMDB for the first two, which wants an API key), so pointing this
   script at them would write 60-odd wrong answers rather than none.

   The rendering side is source-agnostic -- covers.json is a flat id -> URL
   map and the tile does not care who filled it -- so film posters can be
   added to the same file by a second script without touching the component. */
const { BOOKS } = await import('../src/data/read.js');

const items = BOOKS;
let found = 0, missed = 0, skipped = 0;

for (const item of items) {
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
