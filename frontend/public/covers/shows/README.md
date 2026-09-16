# Hand-added podcast artwork, per show

For a show Apple's catalogue does not carry. Right now that is **YC Root
Access** — it is not on Apple as its own feed, so `fetch-podcast-art.mjs`
finds nothing for it and its episodes render as plain cards.

## Adding one

1. Take the show name as it is written in `by` in `src/data/watch.js` — the
   part before the `·`, e.g. `YC Root Access`.
2. Lower-case it and replace anything that is not a letter or digit with a
   hyphen: `yc-root-access`.
3. Save the artwork here as `<that>.jpg` (`.jpeg`, `.png`, `.webp` also work):
   `public/covers/shows/yc-root-access.jpg`
4. Re-run the lookup: `node scripts/fetch-podcast-art.mjs`

Every episode of that show picks it up, including ones added later. It wins
over anything Apple returns, and it is picked up on an ordinary run without
`--refresh`. An image for a single episode goes in the parent folder under
that episode's `id` instead, and wins over this one.

## Before you save one

Square, and small — these render at 56×56, so anything past ~400px is wasted
bytes in the bundle. Take it from the show's own site or its YouTube channel
art, not a Google Images result.

Do not substitute a different show's artwork because the publisher is the
same. Root Access is not the Y Combinator Startup Podcast, and a card wearing
the wrong show's cover is worse than a card with no cover: nobody reports a
missing image, everybody notices the wrong one.
