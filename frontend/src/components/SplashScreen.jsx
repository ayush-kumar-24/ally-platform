import { useCallback, useEffect, useRef, useState } from 'react';
import { prefersReducedMotion } from '../services/motion';

const EASE = 'cubic-bezier(.22,1,.3,1)';

/**
 * SplashScreen – plays the Ally logo animation once on the very first visit.
 * Fades out and calls `onDone` when finished.
 * Uses sessionStorage so it only plays once per browser session.
 *
 * Uses ally-animation-video-hd.mp4 — the original animation re-rendered at
 * 1696×960 (2× lanczos upscale + sharpen, CRF 16) so it stays crisp when
 * stretched fullscreen. The 848×480 source is kept at ally-animation-video.mp4.
 */
export default function SplashScreen({ onDone }) {
  const [phase, setPhase] = useState('playing'); // playing → fading → done
  const [ready, setReady] = useState(false); // video has a frame to show
  const firedRef = useRef(false);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  const finish = useCallback(() => {
    if (firedRef.current) return;
    firedRef.current = true;
    setPhase('fading');
  }, []);

  // Fallback: if video never fires onEnded (e.g. load error), bail after 7 s
  useEffect(() => {
    const t = setTimeout(finish, 7000);
    return () => clearTimeout(t);
  }, [finish]);

  /* Seven seconds of fullscreen motion with no way to pause, stop or hide it
     fails WCAG 2.2.2. ProductTour and LandingPage both already check this
     query; this one blocked the whole app and did not. Skipped outright under
     reduced motion, and there is now a visible Skip control either way. */
  useEffect(() => {
    if (prefersReducedMotion()) finish();
  }, [finish]);

  // When fade-out transition ends, call onDone
  const handleTransitionEnd = (e) => {
    if (phase === 'fading' && e.propertyName === 'opacity') {
      setPhase('done');
      onDone();
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
        // Matches the video's own backdrop (sampled rgb(13,27,21)) so the
        // frame edges blend invisibly while loading and during the fade.
        background: '#0d1b15',
        opacity: phase === 'fading' ? 0 : 1,
        transition: phase === 'fading' ? `opacity 0.8s ${EASE}` : 'none',
        pointerEvents: phase === 'fading' ? 'none' : 'auto',
      }}
      onTransitionEnd={handleTransitionEnd}
      role="status"
      aria-label="Ally is starting"
    >
      <button
        type="button"
        onClick={finish}
        style={{
          position: 'absolute',
          top: 20,
          right: 20,
          zIndex: 1,
          padding: '8px 16px',
          borderRadius: 999,
          border: '1px solid rgba(255,255,255,.22)',
          background: 'rgba(0,0,0,.35)',
          color: '#eaf3ee',
          fontSize: 13,
          fontWeight: 600,
          backdropFilter: 'blur(6px)',
        }}
      >
        Skip intro
      </button>
      <video
        src="/ally-animation-video-hd.mp4"
        autoPlay
        muted
        playsInline
        preload="auto"
        onCanPlay={() => setReady(true)}
        onEnded={finish}
        onError={finish}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          // Ease the first frame in instead of popping — reads as intentional
          opacity: ready ? 1 : 0,
          transform: ready ? 'scale(1)' : 'scale(1.03)',
          transition: `opacity 0.6s ${EASE}, transform 1.2s ${EASE}`,
        }}
      />
      {/* Soft vignette keeps focus on the mark and hides upscale softness at
          the extreme edges on very wide displays. */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'radial-gradient(115% 90% at 50% 46%, transparent 55%, rgba(6,20,13,.42) 100%)',
        }}
      />
    </div>
  );
}
