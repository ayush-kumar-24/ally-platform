/**
 * services/swr.js — show what we knew, then correct it.
 *
 * Two things, both in-memory and both scoped to this tab's session:
 *
 *  - DEDUPE. Two components mounting at once ask for one request, not two.
 *    useCallAccess already did this by hand for one endpoint ("eleven entry
 *    points ask this question, and eleven identical requests on every
 *    dashboard load is not a courtesy"); this is the same idea, reusable.
 *
 *  - STALE-WHILE-REVALIDATE. A repeat visit renders the value from last time
 *    immediately and refetches in the background, so navigating back to a page
 *    is instant instead of showing placeholders again.
 *
 * `maxAge` is deliberately short, and this is deliberately NOT persisted to
 * localStorage. A cached value is a claim about the founder, and the moment it
 * is old enough to be wrong -- they finished a diagnosis, a report landed --
 * showing it is worse than showing a placeholder for one round trip. Inside
 * the window it is a value that was true seconds ago and is corrected as soon
 * as the server answers; outside it, callers get the placeholder path back.
 */

const store = new Map();
const inflight = new Map();

/** Long enough to cover moving between pages, short enough that a founder who
 *  just changed something is not shown the state before they changed it. */
export const DEFAULT_MAX_AGE_MS = 30_000;

/**
 * Fetch `key`, calling `onValue` with a fresh-enough cached value first (if
 * there is one) and again with the server's answer when it lands.
 *
 * Never rejects -- a failure resolves to null, the same contract the dashboard
 * services already use, so one dead source dims one card.
 */
export function swrGet(key, fetcher, onValue, { maxAge = DEFAULT_MAX_AGE_MS } = {}) {
  const hit = store.get(key);
  if (hit && Date.now() - hit.at < maxAge) onValue?.(hit.value);

  let flight = inflight.get(key);
  if (!flight) {
    flight = fetcher()
      .catch(() => null)
      .then((value) => {
        store.set(key, { at: Date.now(), value });
        inflight.delete(key);
        return value;
      });
    inflight.set(key, flight);
  }

  return flight.then((value) => {
    onValue?.(value);
    return value;
  });
}

/** Drop cached values. Call after a write that changes what they said. */
export function invalidate(prefix) {
  if (!prefix) {
    store.clear();
    inflight.clear();
    return;
  }
  for (const key of [...store.keys()]) if (key.startsWith(prefix)) store.delete(key);
  for (const key of [...inflight.keys()]) if (key.startsWith(prefix)) inflight.delete(key);
}
