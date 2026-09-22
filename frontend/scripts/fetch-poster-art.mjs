/**
 * Fill src/data/covers.json with poster art for the series and films.
 *
 * WHY THIS IS NOT fetch-covers.mjs. That one asks Open Library, which is a book
 * catalogue and has no idea what Mad Men is. This asks Apple, which carries TV
 * shows and films -- the same free, keyless endpoint the podcast artwork
 * already comes from, so there is no account to create and no key to rotate.
 * TMDB would also work and wants an API key, which is the only reason it is not
 * used here.
 *
 * SERIES TAKE TWO REQUESTS, AND THAT IS NOT AN OVERSIGHT. `entity=tvSeason` on
 * the search endpoint returns resultCount 0 for everything, with or without
 * `media=tvShow` -- verified against the live API, not assumed. What does work
 * is `media=tvShow`, which answers with EPISODES: the right show, but artwork
 * that is a still from one episode rather than the show's poster, and an
 * artistName Apple sometimes runs together ("MadMen"). So the search is used
 * only to learn the show's artistId, and the poster comes from a second call to
 * the /lookup endpoint, where `entity=tvSeason` does work and hands back proper
 * season art. Films need only the one search.
 *
 * NOTHING ON THE RENDERING SIDE CHANGES. covers.json is a flat id -> URL map and
 * TitleTile (pages/KnowledgePage.jsx) already reads it for every title tile --
 * the series and films have been able to show a poster since the books shipped,
 * they simply had no entries. This script writes the entries.
 *
 * RUN IT WHERE THERE IS NETWORK:
 *
 *     node scripts/fetch-poster-art.mjs           # series (the default)
 *     node scripts/fetch-poster-art.mjs movies    # the films
 *     node scripts/fetch-poster-art.mjs --refresh # re-look-up everything
 *
 * Incremental like its siblings: only ids with no answer are asked about,
 * nothing it cannot find is written, and a tile with no poster renders exactly
 * as it does today. A partial run is shippable.
 *
 * EXPECT THE INDIAN TITLES TO BE THE HARD ONES. Apple's catalogue is thin on
 * shows that live on SonyLIV, JioCinema and Prime India, so Panchayat and Scam
 * 1992 may well come back empty where Mad Men does not. That is what
 * public/covers/ is for -- see its README.
 */

import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(HERE, '../src/data/covers.json');
const LOCAL_DIR = resolve(HERE, '../public/covers');

const SEARCH = 'https://itunes.apple.com/search';
const LOOKUP = 'https://itunes.apple.com/lookup';

/* Storefronts, in order. India first: a show that exists in both catalogues is
   more likely to carry the artwork an Indian founder recognises there, and the
   Indian titles exist in no other storefront at all. */
const STOREFRONTS = ['in', 'us'];

/* Apple throttles this endpoint at roughly 20 calls a minute and answers an
   over-limit request with resultCount 0 rather than an error, which is
   indistinguishable from "we do not have that". A second per call keeps a
   13-title run inside the budget and is still under a minute of waiting. */
const GAP_MS = 1000;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* "Scam 1992: The Harshad Mehta Story" -> "Scam 1992".
   Apple lists several of these under the short name, and the subtitle is what
   stops an otherwise exact match from matching. */
export const mainTitle = (title) => String(title || '').split(/[:—–]/)[0].trim();

/* Case and spacing only. Punctuation is KEPT on purpose: it is what tells a
   subtitle apart from a different show -- see `plausible`. */
const loose = (s) => String(s || '').toLowerCase().replace(/\s+/g, ' ').trim();

/* Everything but the letters and digits. Used for EXACT comparison only, never
   as a prefix, because Apple's own data is inconsistent about spaces: the show
   that lookup calls "Mad Men" comes back from search as "MadMen". Squashing is
   safe for equality and dangerous for prefixes -- it eats the very punctuation
   `CONTINUES` relies on -- so the two are kept apart. */
const squash = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9]/g, '');

/* Where one title is allowed to continue past the other: a subtitle, a season
   suffix, a parenthetical. A SPACE IS NOT IN THIS SET, and that is the whole
   point of it. */
const CONTINUES = /^[\s]*[,:\-–—(\[|/]/;

/* A WRONG POSTER IS WORSE THAN NONE. Nobody reports a missing picture;
   everybody notices Panchayat wearing some other show's artwork.

   So a candidate is accepted when the name Apple has for it is OURS, or ours
   plus a subtitle -- "Silicon Valley, Season 1", "Super Pumped: The Battle For
   Uber", "Mad Men, The Complete Series". It is refused when the extra words
   simply run on: "Panchayat Raj Documentary" is not Panchayat and "The Dropout
   Kings" is not The Dropout, though a plain prefix test calls both a match.
   Short titles are where this matters and they are most of the Indian list. */
export function plausible(candidateName, wanted) {
  const got = loose(candidateName);
  const want = loose(mainTitle(wanted));
  if (!got || !want) return false;
  if (got === want) return true;
  // Two characters is not a match, it is a coincidence.
  if (want.length < 3) return false;
  if (got.startsWith(want)) return CONTINUES.test(got.slice(want.length));
  if (want.startsWith(got)) return CONTINUES.test(want.slice(got.length));
  return false;
}

/* `plausible`, plus the one loosening Apple's own data forces on us. */
export function matches(candidateName, wanted) {
  if (plausible(candidateName, wanted)) return true;
  const got = squash(candidateName);
  return Boolean(got) && got === squash(mainTitle(wanted));
}

/* For an episode Apple puts the show in artistName and "Show, The Complete
   Series" in collectionName; for a film the name is trackName or
   collectionName. Checking all three means one matcher serves both. */
export function nameCandidates(result) {
  return [result.artistName, result.collectionName, result.trackName].filter(Boolean);
}

/* 100x100 is the default Apple hands back on most rows. The URL is templated on
   its dimensions, so asking for a bigger one is a string replace rather than
   another request. */
const big = (url) => url.replace(/\/\d+x\d+bb\./, '/600x600bb.');

export function pickArtwork(results, wanted) {
  for (const r of results) {
    const art = r.artworkUrl600 || r.artworkUrl100;
    if (!art) continue;
    if (nameCandidates(r).some((n) => matches(n, wanted))) return big(art);
  }
  return null;
}

async function ask(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`apple ${res.status}`);
  // Apple serves this as text/javascript, which res.json() refuses on some
  // Node versions. Parsing the text ourselves sidesteps the content type.
  const { results = [] } = JSON.parse(await res.text());
  return results;
}

const search = (params) => ask(`${SEARCH}?${new URLSearchParams(params)}`);
const lookup = (params) => ask(`${LOOKUP}?${new URLSearchParams(params)}`);

/* The show's own poster, via the two-step described at the top of the file. */
async function seriesArtwork(title) {
  for (const country of STOREFRONTS) {
    const hits = await search({
      term: mainTitle(title), media: 'tvShow', country, limit: '25',
    });
    await sleep(GAP_MS);

    /* Only the id is taken from here. The episode's own artwork is a still
       frame, which is not what a tile wants. */
    const show = hits.find((r) => nameCandidates(r).some((n) => matches(n, title)));
    if (!show?.artistId) continue;

    const seasons = await lookup({ id: String(show.artistId), entity: 'tvSeason', country });
    await sleep(GAP_MS);

    /* The first row of a lookup is the show itself and carries no artwork; the
       collections after it are the seasons and the box set, any of which is the
       poster we want. The name is re-checked because an id can only have come
       from a match, but a lookup that returns the wrong thing should still be
       refused rather than trusted. */
    const art = seasons
      .filter((r) => r.wrapperType === 'collection' && (r.artworkUrl600 || r.artworkUrl100))
      .find((r) => nameCandidates(r).some((n) => matches(n, title)));
    if (art) return big(art.artworkUrl600 || art.artworkUrl100);
  }
  return null;
}

/* Films need no second call: `media=movie` answers with the film itself, and
   its artwork is the poster. */
async function movieArtwork(title) {
  for (const country of STOREFRONTS) {
    for (const term of [title, mainTitle(title)]) {
      const found = pickArtwork(await search({ term, media: 'movie', country, limit: '15' }), title);
      await sleep(GAP_MS);
      if (found) return found;
      // The full title and the short title are the same string for most of
      // these; no point asking twice.
      if (term === mainTitle(title)) break;
    }
  }
  return null;
}

/* A poster dropped into public/covers/<id>.<ext> wins over any lookup -- the
   same escape hatch the book covers have, and the one the Indian series will
   probably need. */
const LOCAL_EXTS = ['jpg', 'jpeg', 'png', 'webp'];
function localCover(id) {
  for (const ext of LOCAL_EXTS) {
    if (existsSync(resolve(LOCAL_DIR, `${id}.${ext}`))) return `/covers/${id}.${ext}`;
  }
  return null;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const refresh = process.argv.includes('--refresh');
  const wantMovies = process.argv.includes('movies');
  const existing = refresh ? {} : JSON.parse(readFileSync(OUT, 'utf8'));

  const { SERIES, MOVIES } = await import('../src/data/watch.js');
  const items = wantMovies ? MOVIES : SERIES;
  const artworkFor = wantMovies ? movieArtwork : seriesArtwork;

  let found = 0, missed = 0, skipped = 0;
  const gaps = [];

  for (const item of items) {
    // Checked before the skip, so a poster added by hand is picked up on an
    // ordinary run without anyone having to remember --refresh.
    const local = localCover(item.id);
    if (local) {
      if (existing[item.id] !== local) { existing[item.id] = local; found += 1; }
      else { skipped += 1; }
      writeFileSync(OUT, `${JSON.stringify(existing, null, 2)}\n`);
      continue;
    }
    if (existing[item.id]) { skipped += 1; continue; }

    try {
      const url = await artworkFor(item.title);
      if (url) { existing[item.id] = url; found += 1; console.log(`  found:     ${item.title}`); }
      else { missed += 1; gaps.push(item); console.warn(`  no poster: ${item.title}`); }
    } catch (err) {
      missed += 1;
      gaps.push(item);
      console.warn(`  failed:    ${item.title} -- ${err.message}`);
    }
    // Written as we go, so a run killed halfway keeps what it already found.
    writeFileSync(OUT, `${JSON.stringify(existing, null, 2)}\n`);
  }

  console.log(`\n${items.length} titles: ${found} with a poster, ${missed} without, ${skipped} already had one.`);
  if (gaps.length) {
    console.log('\nAdd these by hand -- save each as public/covers/<id>.jpg:');
    for (const g of gaps) console.log(`  ${g.id.padEnd(24)} ${g.title}`);
  }
  console.log(`\nWritten to ${OUT}`);
}
