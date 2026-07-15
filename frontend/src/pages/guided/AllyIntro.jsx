import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const TABS = [
  { id: 'founder', label: 'Founder-First' },
  { id: 'biz', label: 'Root-Cause Chain' },
  { id: 'clarity', label: 'The Clarity Method' }
];

const CAPTIONS = {
  founder: "Most tools diagnose the business. Ally starts by understanding you — your decision patterns, stress triggers, and founder blind spots. Your Founder DNA is the lens through which every business challenge is viewed.",
  biz: "Symptoms masquerade as problems. Ally traces each business signal back through the chain until the single root constraint emerges. No more treating symptoms.",
  clarity: "Clarity isn't just a report — it's a method. Ally gives you a live, evolving diagnosis that gets sharper with every conversation. You don't guess; you navigate."
};

export default function AllyIntro() {
  const navigate = useNavigate();
  const [mode, setMode] = useState('founder');

  return (
    <section className="view j-stage active ai-intro" id="v-allyintro">
      <div className="j-inner">
        <div className="j-eye">
          <span className="lv" />
          Introducing myself
        </div>
        <h1 className="j-title">Meet Ally, your clarity partner</h1>
        
        <div className="ai-tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={`ai-tab ff-t ${mode === tab.id ? 'on' : ''}`}
              type="button"
              onClick={() => setMode(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className={`ai-ff ${mode}`}>
          <span className="ff-line" />
          {/* Founder-First */}
          <div className={`ff-node founder ${mode === 'founder' || mode === 'biz' || mode === 'clarity' ? 'active' : ''}`}>
            <span className="ff-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
            </span>
            <span className="ff-lbl">Founder DNA</span>
            <span className="ff-desc">How you think, lead and make decisions.</span>
          </div>
          {/* Business DNA */}
          <div className={`ff-node biz ${mode === 'biz' || mode === 'clarity' ? 'active' : ''}`}>
            <span className="ff-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" /></svg>
            </span>
            <span className="ff-lbl">Business DNA</span>
            <span className="ff-desc">Then how your business actually runs.</span>
          </div>
        </div>

        <div className="ai-cap" id="ffCap">
          {CAPTIONS[mode]}
        </div>
      </div>

      <div className="j-bar on" id="jBar" style={{ position: 'fixed', bottom: 0, left: 0, width: '100%', zIndex: 100 }}>
        <span className="jb-note" id="jbNote">Setting the scene.</span>
        <div className="spacer"></div>
        <button
          className="btn btn-em"
          type="button"
          onClick={() => navigate('/guided/profile')}
        >
          I'm ready, let's begin <svg viewBox="0 0 24 24" className="w-4 h-4 inline-block ml-1" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </button>
      </div>
    </section>
  );
}
