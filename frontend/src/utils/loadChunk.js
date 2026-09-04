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
 * The document itself is always fresh (index.html is served no-store), so a
 * reload fixes it every time. `loadChunk` does that automatically: one quiet
 * retry for a blip, then a single reload to pick up the new build. The
 * sessionStorage stamp makes sure a genuinely broken chunk cannot put the tab
 * into a reload loop -- after one attempt the error is allowed through to the
 * caller, which shows its own message.
 */

const RELOAD_KEY = 'goxlally:chunk-reload-at';
// Long enough that a second failure means the build really is broken, short
// enough that a reload is available again next time the founder deploys into a
// long-lived tab.
const RELOAD_COOLDOWN_MS = 30_000;

function reloadedRecently() {
  try {
    const at = Number(window.sessionStorage.getItem(RELOAD_KEY) || 0);
    return at > 0 && Date.now() - at < RELOAD_COOLDOWN_MS;
  } catch {
    // Private mode / storage disabled: never reload rather than risk a loop.
    return true;
  }
}

function markReloaded() {
  try {
    window.sessionStorage.setItem(RELOAD_KEY, String(Date.now()));
  } catch {
    /* nothing we can do; the check above already returned true */
  }
}

/** A network/404 failure fetching a chunk, as opposed to the module itself throwing. */
function isChunkLoadError(error) {
  const message = String(error?.message || error || '');
  return (
    /dynamically imported module/i.test(message) ||
    /Importing a module script failed/i.test(message) ||
    /error loading dynamically imported module/i.test(message) ||
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
          markReloaded();
          window.location.reload();
          // Hold the promise open: the page is going away, and resolving or
          // rejecting here would only flash an error during the unload.
          return new Promise(() => {});
        }
        throw retryError;
      });
  });
}

export { isChunkLoadError };
