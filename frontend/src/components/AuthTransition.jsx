import { useEffect, useRef, useState } from 'react';

const EASE = 'cubic-bezier(.22,1,.3,1)';
const RISE = 'cubic-bezier(.2,.7,.2,1)';

/* How long the splash holds before the mark flies to the sidebar. The film
   this replaced ran up to six seconds; the founder has just signed in and is
   waiting to be let in, so this is the length of the animation itself and not
   a second longer. */
const SPLASH_MS = 2200;

/* The sign-in splash, drawn rather than filmed.
 *
 * This was a 957 KB H.264 film. Built from the mark, two words and three dots
 * it is a 101 KB image and some CSS: nothing to buffer, nothing to decode,
 * no codec that a given browser might not have, and it cannot arrive late on a
 * slow connection — which is the failure the video version had to guard
 * against with a timeout.
 *
 * Kept as one object at module scope so it is not rebuilt on every render.
 * The keyframes live in styles/animations.css, where the global reduced-motion
 * rule flattens them: the splash then simply appears, still and legible.
 */
const splash = {
  screen: {
    position: 'absolute',
    inset: 0,
    background:
      'radial-gradient(130% 90% at 50% 18%, #0c3a2b 0%, #071812 60%, #04100b 100%)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 26,
  },
  markWrap: {
    position: 'relative',
    width: 132,
    height: 132,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  glow: {
    position: 'absolute',
    inset: -18,
    borderRadius: '50%',
    background: 'radial-gradient(circle, rgba(52,224,166,.35), transparent 70%)',
    animation: 'gxGlow 2.4s ease-in-out infinite',
  },
  mark: {
    width: 112,
    height: 112,
    objectFit: 'contain',
    animation: `gxRise .7s ${RISE} both`,
  },
  words: { textAlign: 'center', animation: `gxRise .7s ${RISE} .12s both` },
  name: {
    fontFamily: 'var(--display-tight)',
    fontWeight: 800,
    fontSize: 30,
    letterSpacing: '-.02em',
    color: '#fff',
  },
  tagline: {
    fontFamily: 'var(--serif)',
    fontStyle: 'italic',
    fontSize: 17,
    color: '#7fe9c2',
    marginTop: 4,
  },
  dots: { display: 'flex', gap: 7, marginTop: 6 },
  dot: {
    width: 7,
    height: 7,
    borderRadius: '50%',
    background: '#34E0A6',
    animation: 'gxDot 1.2s ease infinite',
  },
};

export default function AuthTransition({ onNavigate, onComplete }) {
  const [phase, setPhase] = useState('playing'); // playing -> settling -> flying -> done
  const [logoStyle, setLogoStyle] = useState(null);
  const firedEndRef = useRef(false);
  const navigatedRef = useRef(false);
  /* Held in refs so the effect below can stay keyed on `phase` alone without
     capturing a stale copy of either callback — Login re-renders while this is
     on screen (submitting, validationError), so the closure this effect kept
     could easily be one from a previous render. */
  const onNavigateRef = useRef(onNavigate);
  const onCompleteRef = useRef(onComplete);
  onNavigateRef.current = onNavigate;
  onCompleteRef.current = onComplete;

  const endSplash = () => {
    if (firedEndRef.current) return;
    firedEndRef.current = true;
    setPhase('settling');
  };

  /* The splash has no `ended` event to wait for, so this timer is what moves
     the sequence on rather than the safety net it used to be. */
  useEffect(() => {
    const t = setTimeout(endSplash, SPLASH_MS);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (phase !== 'settling') return undefined;
    if (navigatedRef.current) return undefined;
    navigatedRef.current = true;
    onNavigateRef.current();

    const raf = requestAnimationFrame(() => {
      const target = document.querySelector('.j-avatar');
      if (!target) {
        onCompleteRef.current();
        return;
      }
      const rect = target.getBoundingClientRect();
      setLogoStyle({
        top: rect.top + rect.height / 2,
        left: rect.left + rect.width / 2,
        size: rect.width
      });
      setPhase('flying');
    });
    return () => cancelAnimationFrame(raf);
  }, [phase]);

  const vw = typeof window !== 'undefined' ? window.innerWidth : 0;
  const vh = typeof window !== 'undefined' ? window.innerHeight : 0;

  const logoTransform = phase === 'flying' && logoStyle
    ? {
        top: logoStyle.top,
        left: logoStyle.left,
        width: logoStyle.size,
        height: logoStyle.size,
        transform: 'translate(-50%, -50%) scale(1)',
        transition: `top .65s ${EASE}, left .65s ${EASE}, width .65s ${EASE}, height .65s ${EASE}`
      }
    : {
        top: vh / 2,
        left: vw / 2,
        width: 96,
        height: 96,
        transform: 'translate(-50%, -50%) scale(1)',
        transition: 'none'
      };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: '#0a0f0d',
        pointerEvents: phase === 'done' ? 'none' : 'auto',
        opacity: phase === 'flying' ? 0 : 1,
        transition: phase === 'flying' ? `opacity 1.1s ${EASE}` : 'none',
        animation: 'rzFade .3s ease forwards'
      }}
      onTransitionEnd={(e) => {
        if (phase === 'flying' && e.propertyName === 'opacity') {
          setPhase('done');
          onComplete();
        }
      }}
    >
      {phase === 'playing' && (
        <div style={splash.screen} role="status" aria-label="Signing you in">
          <div style={splash.markWrap}>
            <div style={splash.glow} />
            <img src="/ally-logo-mark-on-dark.png" alt="" style={splash.mark} />
          </div>
          <div style={splash.words}>
            <div style={splash.name}>GoXL Ally</div>
            <div style={splash.tagline}>The Founder&rsquo;s Compass</div>
          </div>
          <div style={splash.dots}>
            {[0, 0.2, 0.4].map((delay) => (
              <span key={delay} style={{ ...splash.dot, animationDelay: `${delay}s` }} />
            ))}
          </div>
        </div>
      )}

      {phase !== 'playing' && (
        /* The same mark the splash just showed, so the handoff into the
           sidebar avatar reads as one movement rather than a swap. */
        <img
          src="/ally-logo-mark-on-dark.png"
          alt=""
          style={{
            position: 'fixed',
            borderRadius: '50%',
            objectFit: 'contain',
            padding: '18%',
            background: 'rgba(16,185,129,.14)',
            border: '2px solid rgba(16,185,129,.4)',
            boxShadow: '0 0 40px rgba(16,185,129,.3)',
            ...logoTransform
          }}
        />
      )}
    </div>
  );
}
