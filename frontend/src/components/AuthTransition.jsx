import { useEffect, useRef } from 'react';

export default function AuthTransition({ onComplete }) {
  const firedRef = useRef(false);

  const complete = () => {
    if (firedRef.current) return;
    firedRef.current = true;
    onComplete();
  };

  useEffect(() => {
    const fallback = setTimeout(complete, 6000);
    return () => clearTimeout(fallback);
  }, []);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: '#0a0f0d',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        animation: 'rzFade .3s ease forwards'
      }}
    >
      <video
        src="/ally-animation-video.mp4"
        autoPlay
        muted
        playsInline
        onEnded={complete}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />
    </div>
  );
}
