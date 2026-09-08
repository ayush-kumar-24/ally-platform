/**
 * RequireProfile — the diagnosis is closed until onboarding is finished.
 *
 * WHY THIS EXISTS. The API already refuses: /diagnosis/start,
 * /founder-dna/start and /current-problem/start all carry
 * `require_profile_complete` and answer 409 for a founder who skipped
 * onboarding. But nothing in the app stopped that founder from opening those
 * pages, so the block arrived as an error on a page they had already committed
 * to, rather than as a door that was never open. This sends them to the
 * onboarding they skipped instead.
 *
 * IT IS NOT THE SECURITY BOUNDARY, and does not pretend to be. Same division
 * as PlanGate: the server decides, this explains. Someone who edits the bundle
 * reaches a 409.
 *
 * FAILS OPEN, DELIBERATELY. If /profile/validate cannot be reached we render
 * the page. The server will still refuse a founder who has not finished, so
 * the cost of being wrong here is one clear error message; the cost of failing
 * closed is locking a founder who HAS finished out of their own diagnosis
 * because one request timed out.
 *
 * NO SPINNER while checking -- a blank frame, the same choice RouteFallback
 * makes. The check is one small request and a spinner that flashes for 200ms
 * is noise, not information.
 */

import { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { checkProfileComplete } from '../services/onboarding';
import { useApp } from '../context/AppContext';

export default function RequireProfile({ children }) {
  const [state, setState] = useState('checking');   // checking | ok | incomplete
  const { showToast } = useApp();
  const location = useLocation();

  useEffect(() => {
    let cancelled = false;
    checkProfileComplete()
      .then((result) => {
        if (cancelled) return;
        setState(result?.valid === false ? 'incomplete' : 'ok');
      })
      .catch(() => { if (!cancelled) setState('ok'); });
    return () => { cancelled = true; };
  }, []);

  /* Said out loud. Landing in onboarding after clicking "Adaptive diagnosis"
     looks like the app lost the click unless something explains it. */
  useEffect(() => {
    if (state === 'incomplete') {
      showToast('Finish setting up your profile first — Ally uses it to choose your questions.', 6000);
    }
  }, [state, showToast]);

  if (state === 'checking') return null;

  if (state === 'incomplete') {
    /* `from` so onboarding can send them back where they were headed once it
       is done, rather than dropping them on the dashboard. */
    return <Navigate to="/guided/profile" replace state={{ from: location.pathname }} />;
  }

  return children;
}
