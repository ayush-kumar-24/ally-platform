# Hand-added covers and artwork

For anything the catalogues do not have. Several of our books are Indian
editions nobody has scanned. This folder is the escape hatch for all of it —
books, podcasts, series and films alike — and it is the last resort, after
both catalogues a script knows about have been asked.

## Adding one

1. Find the book's `id` in `src/data/read.js` — e.g. `doglapan`. For a podcast
   episode, series or film it is the `id` in `src/data/watch.js`.
2. Save the cover here as `<id>.jpg` (`.jpeg`, `.png` and `.webp` also work):
   `public/covers/doglapan.jpg`
3. Re-run the lookup:
   - a book → `node scripts/fetch-covers.mjs`
   - a podcast episode → `node scripts/fetch-podcast-art.mjs`
   - a series → `node scripts/fetch-poster-art.mjs`
   - a film → `node scripts/fetch-poster-art.mjs movies`

   **Set `TMDB_API_KEY` before the series run, or most of them will come back
   empty.** Apple only lists what Apple SELLS, so a streaming exclusive is
   simply absent: Panchayat, Scam 1992 and TVF Pitchers are not there, and
   neither are WeCrashed or The Playlist, which are Apple's and Netflix's own
   originals. TMDB has all of them. The key is free
   (https://www.themoviedb.org/settings/api) and goes in the terminal, never in
   this repo:

   ```powershell
   $env:TMDB_API_KEY = "..."    # PowerShell, this terminal only
   ```
   ```bash
   export TMDB_API_KEY=...      # bash / zsh
   ```

   With no key the script asks Apple only, and says so at the end rather than
   pretending the title does not exist. Either way it prints exactly which ids
   came back empty, ready to paste.

For a podcast whose whole feed is missing, put one image in `shows/` instead
of one per episode — see the README in there.

Every script checks this folder **before** its catalogue, so a file dropped in
here wins over anything the lookup returns — and it is picked up on an
ordinary run, without `--refresh`. It then writes `/covers/<id>.jpg` into
`src/data/covers.json` for you.

Commit both the image and the updated `covers.json`, or the cover exists only
on your laptop.

## Before you save one

Keep it small — book and series posters render at 84×126 and podcast artwork
at 56×56, so anything past ~400px wide is wasted bytes in the bundle. A poster
is cropped to fit rather than squashed, so its exact aspect ratio does not
matter much; portrait is the closest to what the tile expects. Prefer the publisher's or retailer's product image over a
Google Images result: those are frequently the wrong edition, a different
book's jacket, or a watermarked stock photo. For a podcast, the show's own
artwork from its site or its Apple/Spotify page.

Cover art is copyrighted. Displaying a thumbnail to identify a book you are
recommending is ordinary practice, but that is a judgement for the team to
make deliberately rather than by accident — which is why the catalogue route,
where the host publishes covers for third parties to display, is the default
and this folder is the exception.
