import { useCallback, useEffect, useRef, useState } from 'react';
import AllySplash, { SPLASH_MS } from './AllySplash';
import { prefersReducedMotion } from '../services/motion';

const EASE = 'cubic-bezier(.22,1,.3,1)';

/**
 * SplashScreen – the Ally splash, once per browser session, on whichever page
 * the founder arrives at. Holds for SPLASH_MS, fades out, calls `onDone`.
 * App.jsx owns the once-per-session rule (sessionStorage) and mounts this only
 * when it applies.
 *
 * This used to play a seven-second film with a Skip button, and had to be kept
 * off the sign-in page because that was too much to put in front of a founder
 * who had just clicked "Log in". It is now the drawn splash from AllySplash --
 * the same one that plays after sign-in -- at two seconds and a bit, so it
 * plays on the sign-in page too. The film's other guards went with it: there
 * is no frame to wait for, so nothing can be "not ready", and nothing needs a
 * Skip control at this length (WCAG 2.2.2 starts at five seconds).
 *
 * Reduced motion skips it outright rather than showing a still: someone who
 * asked for less motion did not ask for a two-second pause either.
 */
export default function SplashScreen({ onDone }) {
  const [phase, setPhase] = useState('playing'); // playing → fading → done
  const firedRef = useRef(false);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  const finish = useCallback(() => {
    if (firedRef.current) return;
    firedRef.current = true;
    setPhase('fading');
  }, []);

  /* The splash has no `ended` event, so this timer is what moves it on. */
  useEffect(() => {
    const t = setTimeout(finish, SPLASH_MS);
    return () => clearTimeout(t);
  }, [finish]);

  useEffect(() => {
    if (prefersReducedMotion()) finish();
  }, [finish]);

  const handleTransitionEnd = (e) => {
    if (phase === 'fading' && e.propertyName === 'opacity') {
      setPhase('done');
      onDoneRef.current();
    }
  };

  // Safety net: hidden tabs don't run CSS transitions, so `transitionend`
  // may never fire. Force completion shortly after the fade should have ended.
  useEffect(() => {
    if (phase !== 'fading') return undefined;
    const t = setTimeout(() => {
      setPhase('done');
      onDoneRef.current();
    }, 1000);
    return () => clearTimeout(t);
  }, [phase]);

  if (phase === 'done') return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        // The splash's own base tone, so its edges blend during the fade.
        background: '#071812',
        opacity: phase === 'fading' ? 0 : 1,
        transition: phase === 'fading' ? `opacity 0.8s ${EASE}` : 'none',
        pointerEvents: phase === 'fading' ? 'none' : 'auto',
      }}
      onTransitionEnd={handleTransitionEnd}
    >
      <AllySplash label="Ally is starting" />
    </div>
  );
}
