# Hand-added covers and artwork

For the few titles Open Library has no scan of. Several of ours are Indian
editions nobody has catalogued. The same folder is the escape hatch for a
podcast Apple does not carry.

## Adding one

1. Find the book's `id` in `src/data/read.js` — e.g. `doglapan`. For a podcast
   episode it is the `id` in `src/data/watch.js`.
2. Save the cover here as `<id>.jpg` (`.jpeg`, `.png` and `.webp` also work):
   `public/covers/doglapan.jpg`
3. Re-run the lookup — `node scripts/fetch-covers.mjs` for a book,
   `node scripts/fetch-podcast-art.mjs` for a podcast episode.

Both scripts check this folder **before** the catalogue, so a file dropped in
here wins over anything Open Library returns — and it is picked up on an
ordinary run, without `--refresh`. It then writes `/covers/<id>.jpg` into
`src/data/covers.json` for you.

Commit both the image and the updated `covers.json`, or the cover exists only
on your laptop.

## Before you save one

Keep it small — book covers render at 84×126 and podcast artwork at 56×56, so
anything past ~400px wide is wasted bytes in the bundle. Prefer the publisher's or retailer's product image over a
Google Images result: those are frequently the wrong edition, a different
book's jacket, or a watermarked stock photo. For a podcast, the show's own
artwork from its site or its Apple/Spotify page.

Cover art is copyrighted. Displaying a thumbnail to identify a book you are
recommending is ordinary practice, but that is a judgement for the team to
make deliberately rather than by accident — which is why the catalogue route,
where the host publishes covers for third parties to display, is the default
and this folder is the exception.
