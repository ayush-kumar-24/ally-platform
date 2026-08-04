/**
 * useFounderRead — the founder's stored answers, plus the read Ally formed.
 *
 * Every screen after onboarding (first impression, summary, the confirmation)
 * needs the same two things, and both live on the server. Reading them from
 * React state instead is how those screens ended up showing "Not answered" for
 * questions the founder had answered minutes earlier: context is memory, and a
 * reload empties it.
 *
 * Session state is still used for first paint, so the screens have something to
 * show before the round trip lands.
 */

import { useEffect, useState } from 'react';
import { useApp } from '../context/AppContext';
import { getProfile, toGuidedAnswers } from '../services/profile';
import { getFirstImpression } from '../services/impression';

/** Drop blanks so a server null never wipes something this session knows. */
function withoutBlanks(answers) {
  return Object.fromEntries(
    Object.entries(answers).filter(([, v]) => {
      if (Array.isArray(v)) return v.length > 0;
      return v !== null && v !== undefined && v !== '';
    }),
  );
}

export function useFounderRead() {
  const { user } = useApp();
  const [answers, setAnswers] = useState(() => user?.founderProfile || {});
  const [impression, setImpression] = useState(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getProfile().catch(() => null),   // signed out or offline: keep what we have
      getFirstImpression(),             // already never throws
    ]).then(([profile, { impression: read }]) => {
      if (cancelled) return;
      if (profile) {
        setAnswers((prev) => ({ ...prev, ...withoutBlanks(toGuidedAnswers(profile)) }));
      }
      if (read) setImpression(read);
      setLoaded(true);
    });
    return () => { cancelled = true; };
  }, []);

  return { answers, impression, loaded };
}
