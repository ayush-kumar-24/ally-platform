import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import AuthTransition from '../../components/AuthTransition';

export default function Login() {
  const navigate = useNavigate();
  const { setUser } = useApp();
  const [showAuthTransition, setShowAuthTransition] = useState(false);

  const handleAuth = (provider) => {
    setUser(prev => ({
      ...prev,
      authProvider: provider,
      name: 'Ayush Sharma',
      email: provider === 'linkedin' ? 'ayush.sharma@brightloom.in' : 'ayush@brightloom.in',
      initials: 'AS'
    }));
    setShowAuthTransition(true);
  };

  return (
    <section className="view j-stage active auth-active" id="v-login">
      {showAuthTransition && (
        <AuthTransition
          onNavigate={() => navigate('/guided/welcome')}
          onComplete={() => setShowAuthTransition(false)}
        />
      )}
      <div className="j-inner">
        <div className="j-avatar"><img src="/ally-logo.png" alt="" /></div>
        <div className="j-eye"><span className="lv"></span> GoXL &middot; Ally</div>
        <h1 className="j-title">Meet Ally, your <em>founder DNA</em> engine.</h1>
        <p className="j-sub">In about 20 minutes, Ally learns how you lead and finds what's really holding your business back. You'll leave with a clarity report and your next move.</p>
        <div className="j-auth">
          <button className="auth-btn" onClick={() => handleAuth('google')} type="button">
            <svg className="g" viewBox="0 0 48 48" aria-hidden="true">
              <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.8-6.8C35.6 2.4 30.1 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.2 17.7 9.5 24 9.5z" />
              <path fill="#4285F4" d="M46.1 24.6c0-1.6-.1-3.1-.4-4.6H24v9.1h12.4c-.5 2.9-2.1 5.3-4.6 7l7.1 5.5c4.2-3.9 6.6-9.6 6.6-16.4z" />
              <path fill="#FBBC05" d="M10.5 28.3c-.5-1.4-.7-2.9-.7-4.3s.3-3 .7-4.3l-7.9-6.1C1 16.7 0 20.2 0 24s1 7.3 2.6 10.4l7.9-6.1z" />
              <path fill="#34A853" d="M24 48c6.1 0 11.3-2 15-5.5l-7.1-5.5c-2 1.4-4.6 2.2-7.9 2.2-6.3 0-11.6-3.7-13.5-9.1l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
            </svg>
            Continue with Google
          </button>
          <button className="auth-btn li" onClick={() => handleAuth('linkedin')} type="button">
            <svg className="g" viewBox="0 0 24 24" fill="#fff" aria-hidden="true">
              <path d="M4.98 3.5A2.5 2.5 0 1 0 5 8.5a2.5 2.5 0 0 0-.02-5zM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21H19.6v-5.3c0-1.26-.02-2.9-1.77-2.9-1.77 0-2.04 1.38-2.04 2.8V21H9z" />
            </svg>
            Continue with LinkedIn
          </button>
        </div>
        <p className="j-fine">Private &amp; encrypted &middot; we never share your business. <span style={{ opacity: 0.7 }}>(Demo — simulated login, no account created)</span></p>
      </div>
    </section>
  );
}
