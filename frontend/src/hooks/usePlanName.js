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

/** Drop the cached plan so the next mount refetches -- call after an upgrade. */
export function refreshPlanName() {
  cached = undefined;
  inflight = null;
}

export function usePlanName() {
  const [plan, setPlan] = useState(() => (cached === undefined ? null : cached));

  useEffect(() => {
    if (cached !== undefined) return undefined;

    let cancelled = false;
    inflight = inflight ?? getMyPlan().then((p) => p ?? null).catch(() => null);
    inflight.then((p) => {
      cached = p;
      inflight = null;
      if (!cancelled) setPlan(p);
    });

    return () => { cancelled = true; };
  }, []);

  return plan?.plan_name || null;
}
