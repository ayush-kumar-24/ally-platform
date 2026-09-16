/**
 * Fill src/data/covers.json with show artwork for every podcast episode.
 *
 * WHY A SECOND SCRIPT AND NOT A FLAG ON fetch-covers.mjs. Open Library is a
 * library catalogue -- it has book covers and nothing else. Podcast artwork
 * comes from Apple's public iTunes Search API, which is a different endpoint,
 * a different matching problem and a different failure mode. One script that
 * did both would be two scripts sharing a file.
 *
 * They share the OUTPUT, though: covers.json is a flat id -> URL map and the
 * card does not care who filled it, so running either script fills in its own
 * ids and leaves the other's alone.
 *
 * WHY THE SHOW'S ARTWORK AND NOT THE EPISODE'S. These entries are individual
 * episodes, and most podcasts publish no per-episode image at all -- the feed
 * falls back to the show's. Looking the show up once and giving every episode
 * of it the same picture is what the podcast apps themselves do, and it is ten
 * lookups instead of thirty.
 *
 * WHY iTUNES. It is free, needs no API key and no account, and Apple publishes
 * the artwork URLs precisely so third parties can display them -- which is what
 * makes hot-linking them the ordinary posture. We host nothing. (TMDB would be
 * the equivalent for the films and series, but it wants a key, which is why
 * those still have no images.)
 *
 * RUN IT WHERE THERE IS NETWORK:
 *
 *     node scripts/fetch-podcast-art.mjs            # fill in the gaps
 *     node scripts/fetch-podcast-art.mjs --refresh  # re-look-up everything
 *
 * Incremental by default, like its sibling: it only asks about ids it has no
 * answer for, nothing it cannot find is written, and a card with no artwork
 * renders exactly as it does today. A partial run is shippable.
 */

import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(HERE, '../src/data/covers.json');
const LOCAL_DIR = resolve(HERE, '../public/covers');

const SEARCH = 'https://itunes.apple.com/search';

// Apple asks for no more than ~20 calls/minute on this endpoint. Ten lookups
// at this spacing is a few seconds, so there is nothing to optimise.
const GAP_MS = 400;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* `by` is written for a READER: "The SaaS Podcast #492 · Julius Korfgen,
   Uplane", "Startup Project #127 · Sviat Dulianinov, Bright Machines". The
   show is everything before the middle dot, with the episode number dropped. */
export function showFrom(by) {
  const head = (by || '').split('·')[0];
  return head.replace(/#\s*\d+\s*$/, '').trim();
}

/* THE SHOWS WE ACTUALLY LIST, spelled out rather than searched for blind.
   There are ten of them, so an explicit table is both shorter and safer than a
   cascade of loosening queries: "Founders" and "Startup Project" are ordinary
   words that match dozens of feeds, and a confidently wrong picture is worse
   than none -- nobody reports a missing image, everybody notices Paul Graham's
   episode wearing some other show's cover.

   `must` is every pattern that has to appear in "<show name> <publisher>" for
   a result to be accepted. Anything that matches none of them is skipped and
   reported, so a show that gets renamed shows up as a gap rather than as the
   wrong art. */
export const SHOWS = {
  'YC Startup Podcast': {
    term: 'Y Combinator Startup Podcast',
    must: [/y ?combinator/i, /startup/i],
  },
  'YC Root Access': {
    term: 'Root Access Y Combinator',
    must: [/root access/i],
  },
  'A Product Market Fit Show': {
    term: 'A Product Market Fit Show',
    must: [/product market fit/i],
  },
  'The SaaS Podcast': {
    term: 'The SaaS Podcast Omer Khan',
    must: [/saas podcast/i],
  },
  'a16z Podcast': {
    term: 'a16z Podcast',
    must: [/a16z|andreessen/i],
  },
  'Startup Project': {
    term: 'Startup Project Nataraj Sindam',
    must: [/startup project/i],
  },
  'The Founder Mindset': {
    term: 'The Founder Mindset',
    must: [/founder mindset/i],
  },
  'Startups For the Rest of Us': {
    term: 'Startups For the Rest of Us',
    must: [/rest of us/i],
  },
  /* One entry credits the host rather than the show ("David Senra · Sam
     Altman"), because that is how a founder would recognise it. Both spellings
     point at the same feed. */
  Founders: {
    term: 'Founders David Senra',
    must: [/founders/i, /senra/i],
  },
  'David Senra': {
    term: 'Founders David Senra',
    must: [/founders/i, /senra/i],
  },
};

async function artworkFor({ term, must }) {
  const params = new URLSearchParams({ term, entity: 'podcast', limit: '10' });
  const res = await fetch(`${SEARCH}?${params}`);
  if (!res.ok) throw new Error(`search ${res.status}`);
  /* Apple serves this as text/javascript, so res.json() refuses it on some
     Node versions. Parsing the text ourselves sidesteps the content type. */
  const { results = [] } = JSON.parse(await res.text());

  const hit = results.find((r) => {
    const hay = `${r.collectionName || ''} ${r.artistName || ''}`;
    return must.every((re) => re.test(hay)) && (r.artworkUrl600 || r.artworkUrl100);
  });
  return hit ? hit.artworkUrl600 || hit.artworkUrl100 : null;
}

/* An image dropped into public/covers/<id>.<ext> wins over any lookup -- the
   same escape hatch the book covers have, for a show Apple does not carry. */
const LOCAL_EXTS = ['jpg', 'jpeg', 'png', 'webp'];
function localCover(id) {
  for (const ext of LOCAL_EXTS) {
    if (existsSync(resolve(LOCAL_DIR, `${id}.${ext}`))) return `/covers/${id}.${ext}`;
  }
  return null;
}

// Importable for the unit test without firing thirty requests at Apple.
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const refresh = process.argv.includes('--refresh');
  const existing = refresh ? {} : JSON.parse(readFileSync(OUT, 'utf8'));

  const { PODCASTS } = await import('../src/data/watch.js');

  // One lookup per SHOW, reused by every episode of it.
  const byShow = new Map();
  let found = 0, missed = 0, skipped = 0;

  for (const item of PODCASTS) {
    const local = localCover(item.id);
    if (local) {
      if (existing[item.id] !== local) { existing[item.id] = local; found += 1; }
      else { skipped += 1; }
      writeFileSync(OUT, `${JSON.stringify(existing, null, 2)}\n`);
      continue;
    }
    if (existing[item.id]) { skipped += 1; continue; }

    const show = showFrom(item.by);
    const spec = SHOWS[show];
    if (!spec) {
      missed += 1;
      console.warn(`  unknown show: ${show || '(none)'} -- ${item.title}`);
      continue;
    }

    if (!byShow.has(show)) {
      try {
        byShow.set(show, await artworkFor(spec));
        if (!byShow.get(show)) console.warn(`  no artwork: ${show}`);
      } catch (err) {
        byShow.set(show, null);
        console.warn(`  failed:     ${show} -- ${err.message}`);
      }
      await sleep(GAP_MS);
    }

    const url = byShow.get(show);
    if (url) { existing[item.id] = url; found += 1; } else { missed += 1; }
    // Written as we go, so a run killed halfway keeps what it already found.
    writeFileSync(OUT, `${JSON.stringify(existing, null, 2)}\n`);
  }

  console.log(`\n${PODCASTS.length} episodes: ${found} with artwork, ${missed} without, ${skipped} already had one.`);
  console.log(`${byShow.size} shows looked up. Written to ${OUT}`);
}
