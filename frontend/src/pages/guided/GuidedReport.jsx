import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ReportView from '../../components/ReportView';

/* Guided report route (/guided/report). Same live report as /app/report via the
   shared ReportView — previously this screen rendered mock data with fabricated
   metrics ("-38%", "92% confidence", "+18-24%") and the cut sections (Supporting
   evidence, Roadmap, Expected impact). Those are gone; only the guided chrome
   (a keep-your-report bottom bar + the to-dashboard transition) stays. */
export default function GuidedReport() {
  const navigate = useNavigate();
  const [goingToDashboard, setGoingToDashboard] = useState(false);
  const goToDashboard = () => setGoingToDashboard(true);

  useEffect(() => {
    if (!goingToDashboard) return;
    const t = setTimeout(() => navigate('/app'), 1400);
    return () => clearTimeout(t);
  }, [goingToDashboard, navigate]);

  return (
    <div style={{ position: 'relative', height: '100%', display: 'flex', flexDirection: 'column', width: '100%' }}>
      <div className="fd-container" style={{ flex: 1, overflowY: 'auto', paddingBottom: '90px' }}>
        <ReportView onBook={goToDashboard} />
      </div>

      {/* Guided bottom bar */}
      <div
        style={{
          position: 'absolute', bottom: 0, left: 0, right: 0, height: '64px',
          background: '#06231a', borderTop: '1px solid rgba(255,255,255,0.08)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 24px', zIndex: 100,
        }}
      >
        <span style={{ color: '#a7c0b4', fontSize: '13px', fontWeight: 500, fontFamily: 'var(--body)' }}>
          This report is yours to keep.
        </span>
        <button
          className="btn btn-em"
          style={{
            background: '#10B981', color: '#06231a', fontWeight: 750, padding: '10px 18px',
            borderRadius: '8px', display: 'inline-flex', alignItems: 'center', gap: 8,
            fontFamily: 'var(--display)', fontSize: '13px', border: 'none', cursor: 'pointer',
          }}
          onClick={goToDashboard}
          type="button"
        >
          To user&rsquo;s dashboard
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" style={{ width: 14, height: 14 }}>
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </button>
      </div>

      {goingToDashboard && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 999, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 18,
            background: 'rgba(6, 20, 13, 0.92)', backdropFilter: 'blur(6px)',
          }}
        >
          <div
            style={{
              width: 44, height: 44, borderRadius: '50%',
              border: '3px solid rgba(52, 211, 153, 0.25)', borderTopColor: '#34d399',
              animation: 'gr-spin 0.8s linear infinite',
            }}
          />
          <span style={{ color: '#a7c0b4', fontSize: 13, fontWeight: 500, fontFamily: 'var(--body)' }}>
            Taking you to your dashboard…
          </span>
          <style>{`@keyframes gr-spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}
    </div>
  );
}
