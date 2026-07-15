import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

export default function Success() {
  const navigate = useNavigate();
  const { exitGuided } = useApp();
  const [show, setShow] = useState(false);

  useEffect(() => { setShow(true); }, []);

  const handleDashboard = () => {
    exitGuided();
    navigate('/app');
  };

  return (
    <section className="view j-stage active" style={{ minHeight: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '100px 18px 92px' }}>
      <div style={{ width: '100%', maxWidth: '760px', textAlign: 'center' }}>
        <div style={{ marginBottom: '20px', opacity: show ? 1 : 0, transform: show ? 'none' : 'translateY(10px)', transition: 'all .55s var(--primary)' }}>
          <div style={{ width: '120px', height: '120px', margin: '0 auto', borderRadius: '50%', border: '1px solid rgba(16,185,129,.22)', display: 'grid', placeItems: 'center', boxShadow: '0 0 0 1px rgba(16,185,129,.08)' }}>
            <div style={{ width: '70px', height: '70px', borderRadius: '50%', background: 'rgba(16,185,129,.2)', display: 'grid', placeItems: 'center', boxShadow: '0 0 30px rgba(16,185,129,.2)' }}>
              <svg viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
            </div>
          </div>
        </div>
        <div style={{ fontSize: '12px', fontWeight: 800, letterSpacing: '.16em', textTransform: 'uppercase', color: 'var(--emerald-bright)', marginBottom: '16px', opacity: show ? 1 : 0, transform: show ? 'none' : 'translateY(10px)', transition: 'all .55s var(--primary) .05s' }}>You're all set, Ayush</div>
        <h1 style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 'clamp(40px, 5vw, 70px)', lineHeight: 1.02, color: '#f7f1eb', opacity: show ? 1 : 0, transform: show ? 'none' : 'translateY(10px)', transition: 'all .55s var(--primary) .08s' }}>Your discovery call is <em style={{ color: 'var(--emerald-glow)', fontStyle: 'italic' }}>booked.</em></h1>
        <p style={{ maxWidth: '640px', margin: '18px auto 0', fontSize: '18px', lineHeight: 1.6, color: 'var(--on-dark-muted)', opacity: show ? 1 : 0, transform: show ? 'none' : 'translateY(10px)', transition: 'all .55s var(--primary) .1s' }}>A calendar invite is on its way to ayush@brightloom.in, and your advisor already has your Founder Report. You've completed your first diagnosis - your workspace is now unlocked.</p>
        <button className="btn btn-em" type="button" onClick={handleDashboard} style={{ marginTop: '28px', borderRadius: '16px', padding: '16px 24px', fontSize: '18px', fontWeight: 700, opacity: show ? 1 : 0, transition: 'opacity .55s var(--primary) .12s' }}>
          Enter your workspace
          <svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
        </button>
      </div>
    </section>
  );
}
