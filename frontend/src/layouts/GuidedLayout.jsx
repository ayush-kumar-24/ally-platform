import { Navigate, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useEffect } from 'react';
import { getAccessToken } from '../services/api';
import { getProfile } from '../services/profile';

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

  /**
   * A founder who already finished onboarding used to be forced through this
   * entire 14-step sequence again on every login -- nothing anywhere checked
   * whether they'd already done it. `profile_completed` only becomes true once
   * every required field (including the problem statement from the last guided
   * step) is filled, so by the time it flips, a founder who is still legitimately
   * on a guided page hasn't finished it yet -- this can only fire for someone
   * returning to /guided/* after already completing it.
   */
  useEffect(() => {
    if (!getAccessToken()) return;
    let cancelled = false;
    getProfile()
      .then((p) => {
        if (!cancelled && p?.profile_completed) navigate('/app', { replace: true });
      })
      .catch(() => { /* not signed in, or offline -- let onboarding proceed as normal */ });
    return () => { cancelled = true; };
    // Runs once per mount of the guided shell, not on every step -- re-checking on
    // every pathname change would refetch the profile on each of the 10 clicks
    // through a normal first-time onboarding for no benefit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  /* The shell below was height:100vh + overflow:hidden, which pinned the guided
     flow to the viewport and left no page scroll at all. Any screen taller than
     the window -- the summary, with thirteen answers plus Ally's read -- had to
     grow its own inner scrollbar, so content below the fold was reachable only
     by scrolling inside a box. minHeight lets the page itself scroll. */

  /* Onboarding writes to the founder's row from the very first answer, so it
     needs a session before it starts -- not at the end. Without one, the dev
     auth fallback resolves every request to a placeholder founder that has no
     database row, so each write comes back 404: the founder answers thirteen
     questions, none of it saves, and the only symptom is being bounced to login
     at the /app boundary once RequireAuth finally checks. The login step is of
     course exempt. */
  if (location.pathname !== '/guided/login' && !getAccessToken()) {
    return <Navigate to="/guided/login" replace state={{ from: location.pathname }} />;
  }

  return (
    <div style={{ position: 'relative', minHeight: '100vh', display: 'flex', flexDirection: 'column', overflowX: 'hidden' }}>
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

      <nav className="guided-nav">
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
