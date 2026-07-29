import { useEffect, useRef, useState } from 'react';

const EASE = 'cubic-bezier(.22,1,.3,1)';

/**
 * SplashScreen – plays ally-animation-video.mp4 once on the very first visit.
 * Fades out and calls `onDone` when finished.
 * Uses sessionStorage so it only plays once per browser session.
 */
export default function SplashScreen({ onDone }) {
  const [phase, setPhase] = useState('playing'); // playing → fading → done
  const firedRef = useRef(false);

  const finish = () => {
    if (firedRef.current) return;
    firedRef.current = true;
    setPhase('fading');
  };

  // Fallback: if video never fires onEnded (e.g. load error), bail after 7 s
  useEffect(() => {
    const t = setTimeout(finish, 7000);
    return () => clearTimeout(t);
  }, []);

  // When fade-out transition ends, call onDone
  const handleTransitionEnd = (e) => {
    if (phase === 'fading' && e.propertyName === 'opacity') {
      setPhase('done');
      onDone();
    }
  };

  if (phase === 'done') return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: '#0a0f0d',
        opacity: phase === 'fading' ? 0 : 1,
        transition: phase === 'fading' ? `opacity 0.8s ${EASE}` : 'none',
        pointerEvents: phase === 'fading' ? 'none' : 'auto',
      }}
      onTransitionEnd={handleTransitionEnd}
    >
      <video
        src="/ally-animation-video.mp4"
        autoPlay
        muted
        playsInline
        onEnded={finish}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />
    </div>
  );
}
