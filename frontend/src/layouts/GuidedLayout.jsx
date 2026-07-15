import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useEffect } from 'react';

const STEP_LABELS = {
  '/guided/login': { stage: 'Sign In', step: '1 / 14', pct: 7 },
  '/guided/welcome': { stage: 'Welcome', step: '2 / 14', pct: 14 },
  '/guided/expectation': { stage: 'How It Works', step: '3 / 14', pct: 21 },
  '/guided/ally-intro': { stage: 'Meet Ally', step: '3 / 14', pct: 21 },
  '/guided/profile': { stage: 'Building your profile', step: '3 / 14', pct: 21 },
  '/guided/tour': { stage: 'First impression', step: '4 / 14', pct: 29 },
  '/guided/summary': { stage: 'Founder summary', step: '5 / 14', pct: 36 },
  '/guided/validate': { stage: 'A quick check', step: '6 / 14', pct: 43 },
  '/guided/problem': { stage: 'The perceived problem', step: '7 / 14', pct: 50 },
  '/guided/reveal': { stage: 'Adaptive diagnosis', step: '8 / 14', pct: 57 },
  '/guided/root-cause': { stage: 'Root-cause detection', step: '9 / 14', pct: 64 },
  '/guided/conclusion': { stage: 'A conclusion', step: '10 / 14', pct: 71 },
  '/guided/report': { stage: 'Founder Report', step: '11 / 14', pct: 79 },
  '/guided/recommend': { stage: 'Recommendation', step: '12 / 14', pct: 86 },
  '/guided/discovery': { stage: 'Discovery call', step: '13 / 14', pct: 93 },
  '/guided/success': { stage: 'All set', step: '14 / 14', pct: 100 },
};

export default function GuidedLayout() {
  const { exitGuided, setIsGuided } = useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const meta = STEP_LABELS[location.pathname] || { stage: 'Getting Started', step: '1 / 14', pct: 7 };

  useEffect(() => {
    setIsGuided(true);
    return () => setIsGuided(false);
  }, [setIsGuided]);

  useEffect(() => {
    const isAuth = location.pathname === '/guided/login' || location.pathname === '/guided/welcome';
    if (isAuth) {
      document.body.classList.add('auth-active');
    } else {
      document.body.classList.remove('auth-active');
    }
    return () => document.body.classList.remove('auth-active');
  }, [location.pathname]);

  const handleBack = () => navigate(-1);
  const handleExit = () => { exitGuided(); navigate('/'); };

  return (
    <div style={{ position: 'relative', height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div id="guidedBg" style={{ display: 'block' }}>
        <div className="gb-orb o1" />
        <div className="gb-orb o2" />
        <div className="gb-orb o3" />
        <div className="gb-ray" />
        <div className="gb-particles">
          {[...Array(12)].map((_, i) => (
            <i key={i} style={{
              left: `${(i * 8.5) % 100}%`,
              animationDuration: `${6 + (i * 1.3) % 8}s`,
              animationDelay: `${(i * 0.7) % 5}s`,
              width: i % 3 === 0 ? '4px' : '3px',
              height: i % 3 === 0 ? '4px' : '3px',
            }} />
          ))}
        </div>
      </div>

      <nav 
        className="guided-nav" 
        style={location.pathname === '/guided/report' ? {
          position: 'relative',
          pointerEvents: 'auto',
          width: '100%',
        } : {}}
      >
        <a className="gn-logo" href="/" onClick={e => { e.preventDefault(); handleExit(); }}>
          <span className="gn-logo-text">Go<span className="x">XL</span></span>
          <span className="al">· Ally</span>
        </a>

        <div className="gn-center">
          <button className="gn-back" onClick={handleBack} title="Go back">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
          </button>
          <span className="gn-stage">{meta.stage}</span>
          <div className="gn-sep" />
          <span className="gn-step">{meta.step}</span>
          <div className="gn-track">
            <div className="gn-fill" style={{ width: `${meta.pct}%` }} />
          </div>
        </div>

        <button className="gn-exit" onClick={handleExit}>Exit</button>
      </nav>

      <div className="view-wrap" style={{ position: 'relative', zIndex: 1, flex: 1, minHeight: 0 }}>
        <Outlet />
      </div>
    </div>
  );
}
