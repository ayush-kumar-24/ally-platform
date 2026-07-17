import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

export default function Welcome() {
  const navigate = useNavigate();
  const { user } = useApp();

  const firstName = user?.name ? user.name.split(' ')[0] : 'Ayush';
  const email = user?.email || 'ayush@brightloom.in';

  return (
    <section className="view j-stage active" id="v-welcome">
      <div className="j-inner wide wc-inner">
        <div className="j-avatar"><img src="/ally-logo.png" alt="" /></div>
        <div className="j-eye" style={{ justifyContent: 'center' }}>
          Signed in · <span data-fe="true">{email}</span>
        </div>
        <h1 className="j-title wc-title">
          Good to meet you, <em data-ff="true">{firstName}</em>.
        </h1>
        <p className="j-sub wc-sub">
          I'm Ally. Here's how the next ~20 minutes work — a conversation, not a form. We'll get to real clarity together.
        </p>
        
        <div className="wc-expect" aria-hidden="true">
          <span>~20 minutes</span>
          <span>A conversation, not a form</span>
          <span>Clarity you keep</span>
        </div>

        <div className="wc-flow">
          <span className="wc-line" aria-hidden="true">
            <i className="wc-spark"></i>
          </span>
          <div className="wc-node">
            <span className="wc-ic">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                <circle cx="12" cy="8" r="4" />
                <path d="M4 21a8 8 0 0 1 16 0" />
              </svg>
            </span>
            <span className="wc-k">Founder DNA</span>
            <span className="wc-t">How you think — not just the company.</span>
          </div>
          
          <div className="wc-node">
            <span className="wc-ic">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                <path d="M3 3v18h18" />
                <rect x="7" y="12" width="3" height="6" />
                <rect x="12" y="8" width="3" height="10" />
                <rect x="17" y="5" width="3" height="13" />
              </svg>
            </span>
            <span className="wc-k">Business DNA</span>
            <span className="wc-t">Then how your business really runs.</span>
          </div>
          
          <div className="wc-node">
            <span className="wc-ic">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                <circle cx="12" cy="12" r="9" />
                <circle cx="12" cy="12" r="4" />
                <circle cx="12" cy="12" r="1" />
              </svg>
            </span>
            <span className="wc-k">Root Cause</span>
            <span className="wc-t">I connect it to the one real cause.</span>
          </div>
          
          <div className="wc-node">
            <span className="wc-ic">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <path d="M14 2v6h6" />
                <line x1="9" y1="13" x2="15" y2="13" />
                <line x1="9" y1="17" x2="13" y2="17" />
              </svg>
            </span>
            <span className="wc-k">Clarity Report</span>
            <span className="wc-t">Your founder report — yours to keep.</span>
          </div>
        </div>

        <div className="wc-daily">
          <span className="wc-daily-ic">✦</span>
          <span>
            Then I stay — to brainstorm, plan and decide with you, <b>every day</b>.
          </span>
        </div>
      </div>

      <div className="j-bar on" id="jBar" style={{ position: 'fixed', bottom: 0, left: 0, width: '100%', zIndex: 100 }}>
        <span className="jb-note" id="jbNote">About 20 minutes — a conversation, not a form.</span>
        <div className="spacer"></div>
        <button 
          className="btn btn-em cta-pulse" 
          id="jbBtn" 
          type="button" 
          onClick={() => navigate('/guided/profile')}
        >
          I'm ready <svg viewBox="0 0 24 24" className="w-4 h-4 inline-block ml-1" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </button>
      </div>
    </section>
  );
}
