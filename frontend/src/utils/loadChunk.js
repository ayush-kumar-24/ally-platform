/**
 * utils/loadChunk.js — make dynamic imports survive a redeploy.
 *
 * The app is code-split: every route, and the Supabase SDK behind the login
 * form, arrives as its own hashed chunk (`assets/Dashboard-a1b2c3.js`). Those
 * file names change on every deploy, and the old ones stop being served the
 * moment the new build goes live. A tab that loaded index.html before the
 * deploy is still holding the *old* names, so the next lazy import 404s and
 * React surfaces the raw
 *
 *     Failed to fetch dynamically imported module: .../supabaseClient-XXXX.js
 *
 * straight into the UI. The same thing happens on a dropped connection.
 *
 * The document itself is always revalidated (see vercel.json's Cache-Control
 * for everything outside /assets), so a reload fixes it every time.
 * `loadChunk` does that automatically: one quiet retry for a blip, then a
 * single reload to pick up the new build. The reload stamp makes sure a
 * genuinely broken chunk cannot put the tab into a reload loop -- after one
 * attempt the error is allowed through to the caller, which shows its own
 * message (ErrorBoundary, which recognises this case by isChunkLoadError and
 * says "a new version is ready" rather than "something went wrong").
 *
 * Onboarding is where this bites hardest: it is a ~20-minute single-tab
 * session, by far the longest-lived tab in the product, so it is the one most
 * likely to still be open when a deploy lands. /guided/login is exempt (it is
 * in the entry chunk, not a lazy one), which is exactly why the front door can
 * look healthy while founders mid-flow hit the error card.
 */

const RELOAD_KEY = 'goxlally:chunk-reload-at';
/* The same stamp as a query parameter, for browsers where storage is not
   available -- see the note on readReloadStamp below. */
const RELOAD_PARAM = 'chunk_reload';
// Long enough that a second failure means the build really is broken, short
// enough that a reload is available again next time the founder deploys into a
// long-lived tab.
const RELOAD_COOLDOWN_MS = 30_000;

/**
 * When this tab last reloaded itself to pick up a new build, or 0.
 *
 * The stamp is written to TWO places on purpose, and read back from either.
 *
 * sessionStorage alone was the original design, and it had a hole. When
 * storage is unavailable -- a locked-down browser, some private windows, an
 * embedded webview, a third-party-cookie-blocked context -- the read throws,
 * and the old code answered "yes, we already reloaded" so as not to risk a
 * reload loop. Staying out of a loop was right; the side effect was not. The
 * founders whose browsers refuse storage were the only ones who NEVER got the
 * automatic recovery: their very first stale-chunk failure went straight to
 * the error card, while everyone else was quietly reloaded and never knew.
 *
 * The query parameter closes that. It survives a reload (which is the only
 * thing sessionStorage was needed for here) without storing anything at all,
 * so every browser now gets exactly one reload and no browser gets two. It
 * does not linger in the address bar either: every in-app navigation is a
 * client-side route change that rewrites the URL without it.
 */
function readReloadStamp() {
  try {
    const stored = Number(window.sessionStorage.getItem(RELOAD_KEY) || 0);
    if (stored > 0) return stored;
  } catch {
    /* No storage. The parameter below is the whole point of this fallback. */
  }
  try {
    const fromUrl = Number(
      new URLSearchParams(window.location.search).get(RELOAD_PARAM) || 0,
    );
    return fromUrl > 0 ? fromUrl : 0;
  } catch {
    return 0;
  }
}

function reloadedRecently() {
  const at = readReloadStamp();
  // A negative age means the clock moved backwards between the two reads.
  // `< COOLDOWN` still catches it, which errs toward not reloading -- the safe
  // direction, since the cost is one error card and the alternative is a loop.
  return at > 0 && Date.now() - at < RELOAD_COOLDOWN_MS;
}

/**
 * Stamp this attempt and reload into the current build.
 *
 * `location.replace`, not `assign`: the pre-reload URL must not become a
 * back-button stop, and the founder should land on the page they were already
 * heading to.
 */
function reloadForNewBuild() {
  const now = String(Date.now());
  try {
    window.sessionStorage.setItem(RELOAD_KEY, now);
  } catch {
    /* The URL stamp below carries it instead. */
  }
  try {
    const url = new URL(window.location.href);
    url.searchParams.set(RELOAD_PARAM, now);
    window.location.replace(url.toString());
    return;
  } catch {
    /* URL construction failed (never seen, but this must not be what breaks
       the recovery). A plain reload still picks up the new build; it just
       cannot carry the stamp for a browser with no storage. */
  }
  window.location.reload();
}

/** A network/404 failure fetching a chunk, as opposed to the module itself throwing. */
function isChunkLoadError(error) {
  const message = String(error?.message || error || '');
  return (
    // Chrome/Edge: "Failed to fetch dynamically imported module: ..."
    /dynamically imported module/i.test(message) ||
    // Safari: "Importing a module script failed."
    /Importing a module script failed/i.test(message) ||
    // Firefox: "error loading dynamically imported module"
    /error loading dynamically imported module/i.test(message) ||
    // Vite's own preload helper, when the stylesheet beside a route chunk is
    // the thing that 404s: "Unable to preload CSS for /assets/Foo-XXXX.css".
    /Unable to preload CSS/i.test(message) ||
    /ChunkLoadError/i.test(error?.name || '')
  );
}

/**
 * Run a `() => import('...')` factory, retrying once and then reloading the
 * page if the chunk cannot be fetched.
 */
export function loadChunk(factory) {
  return factory().catch((error) => {
    if (!isChunkLoadError(error)) throw error;

    return new Promise((resolve) => setTimeout(resolve, 400))
      .then(factory)
      .catch((retryError) => {
        if (isChunkLoadError(retryError) && !reloadedRecently()) {
          reloadForNewBuild();
          // Hold the promise open: the page is going away, and resolving or
          // rejecting here would only flash an error during the unload.
          return new Promise(() => {});
        }
        throw retryError;
      });
  });
}

export { isChunkLoadError };
