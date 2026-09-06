import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getMyPlan } from '../services/plans';

/**
 * Sends a founder with no plan to the plans page.
 *
 * Nothing is free once we launch, so a founder who has not chosen a plan can
 * sign in and then do precisely nothing. Without this they would meet that as a
 * series of locked pages and 402s, one feature at a time, and have to work out
 * for themselves that the answer is "pick a plan". This says it once, at the
 * door.
 *
 * The condition is an EMPTY FEATURE SET, not `tier === 'free'`. That is the
 * thing that actually matters — a founder who can do nothing needs a plan,
 * whatever the tier happens to be called — and it keeps working if the tiers are
 * renamed, which they already have been once.
 *
 * While we are still testing, Free carries almost the whole product, so this
 * gate is inert for everyone: the feature set is not empty, and nobody is
 * redirected. It starts working the day PUBLIC_LAUNCH is switched on, from the
 * same one setting.
 *
 * FAILS OPEN. If the plan lookup errors we let the founder through: being
 * unable to read a plan is our problem, and locking someone out of a product
 * they have paid for is far worse than briefly showing a page they cannot use.
 */
export default function PlanRequiredGate() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    // Billing is where we are sending them, and the plans page has to stay
    // reachable to a founder with no plan or the redirect is a loop.
    if (pathname.startsWith('/app/billing')) return undefined;

    let cancelled = false;
    getMyPlan()
      .then((plan) => {
        if (cancelled) return;
        const features = Array.isArray(plan?.features) ? plan.features : null;
        // `null` means we could not tell — treat that as "let them through",
        // the same as an error. Only a genuine empty list is a founder with
        // nothing.
        if (features && features.length === 0) {
          navigate('/app/billing', { replace: true, state: { needsPlan: true } });
        }
      })
      .catch(() => { /* fail open — see the note above */ })
      .finally(() => { if (!cancelled) setChecked(true); });

    return () => { cancelled = true; };
  }, [pathname, navigate]);

  // Renders nothing either way. The redirect is the whole behaviour, and
  // blocking the app behind a spinner while this resolves would make every page
  // load feel slower for the paying majority who are never redirected.
  void checked;
  return null;
}
