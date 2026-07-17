import { useEffect, useRef, useState } from 'react';

const EASE = 'cubic-bezier(.22,1,.3,1)';

export default function AuthTransition({ onNavigate, onComplete }) {
  const [phase, setPhase] = useState('playing'); // playing -> settling -> flying -> done
  const [logoStyle, setLogoStyle] = useState(null);
  const firedEndRef = useRef(false);
  const navigatedRef = useRef(false);

  const endVideo = () => {
    if (firedEndRef.current) return;
    firedEndRef.current = true;
    setPhase('settling');
  };

  useEffect(() => {
    const fallback = setTimeout(endVideo, 6000);
    return () => clearTimeout(fallback);
  }, []);

  useEffect(() => {
    if (phase !== 'settling') return;
    if (navigatedRef.current) return;
    navigatedRef.current = true;
    onNavigate();

    const raf = requestAnimationFrame(() => {
      const target = document.querySelector('.j-avatar');
      if (!target) {
        onComplete();
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
        <video
          src="/ally-animation-video.mp4"
          autoPlay
          muted
          playsInline
          onEnded={endVideo}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      )}

      {phase !== 'playing' && (
        <img
          src="/ally-logo.png"
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
