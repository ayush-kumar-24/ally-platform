/**
 * hooks/usePlanName.js — the founder-facing name of the plan they are on.
 *
 * The plan tier a founder is on (`user.plan`) is an internal id: `basic`,
 * `starter`. The name they are sold and shown is a different word for two of
 * the four tiers -- basic is "Starter", starter is "Plus" -- and only the
 * server's catalog knows which is current. GET /plans/me returns it as
 * `plan_name`.
 *
 * Fetched once per session and shared, the same way useCallAccess handles the
 * call quote: the badge renders in the app shell, on every single screen, and
 * a request per mount would be a request per navigation.
 *
 * Never blocks a render. Until it resolves (or if it fails) callers fall back
 * to the local PLAN_NAMES table, which is correct today -- so the badge is
 * never wrong and never blank, it just gets a second opinion from the server.
 */

import { useEffect, useState } from 'react';
import { getMyPlan } from '../services/plans';

let cached;             // undefined = never fetched; null = fetched and failed
let inflight = null;

/* Every mounted usePlanName, so an invalidation can reach them.
 *
 * The cache lives at module scope and the badge that reads it renders in the
 * app shell, which stays mounted for the whole session. Clearing `cached`
 * alone therefore changed nothing on screen: the effect below only runs on
 * mount, and the shell does not remount on navigation or on an upgrade. */
const subscribers = new Set();

function fetchPlan() {
  inflight = inflight ?? getMyPlan().then((p) => p ?? null).catch(() => null);
  return inflight.then((p) => {
    cached = p;
    inflight = null;
    subscribers.forEach((set) => set(p));
    return p;
  });
}

/**
 * Drop the cached plan and refetch, telling every mounted caller the answer.
 *
 * Call this whenever the founder behind the cache may have changed: on sign-out
 * (the cache is module state, so without it the next founder to sign in IN THE
 * SAME TAB inherits the previous one's plan badge -- an SPA never reloads the
 * page between the two), and on a completed upgrade (otherwise a founder who
 * has just paid keeps seeing the plan they left behind).
 */
export function refreshPlanName() {
  cached = undefined;
  inflight = null;
  if (subscribers.size > 0) fetchPlan();
}

function useServerPlan() {
  const [plan, setPlan] = useState(() => (cached === undefined ? null : cached));

  useEffect(() => {
    subscribers.add(setPlan);
    // A mount arriving after someone else's fetch resolved has the answer
    // already; one arriving during it is covered by the subscriber above.
    if (cached !== undefined) setPlan(cached);
    else fetchPlan();
    return () => { subscribers.delete(setPlan); };
  }, []);

  return plan;
}

export function usePlanName() {
  return useServerPlan()?.plan_name || null;
}

/**
 * The tier the SERVER says the founder is on, or null until it answers.
 *
 * `user.plan` on the AppContext profile answers the same question, but it is
 * hydrated at sign-in and not refreshed when a plan changes -- so the sidebar
 * button kept offering "Upgrade plan" to a founder who had just paid, on the
 * very page that took their money. This comes from the same GET /plans/me the
 * badge beside it already trusts, and the same refreshPlanName() updates both,
 * so the two can no longer disagree about which plan someone is on.
 */
export function usePlanTier() {
  return useServerPlan()?.tier || null;
}
