import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { CURRENT_VERSIONS, grantDiagnosisConsent } from '../../services/consents';

export default function Welcome() {
  const navigate = useNavigate();
  const { user, setUser, showToast } = useApp();
  const [showModal, setShowModal] = useState(false);
  const [agreeModalDiagnosis, setAgreeModalDiagnosis] = useState(false);
  const [savingConsent, setSavingConsent] = useState(false);

  // Same fabricated-identity bug as everywhere else this session, but on the
  // very first screen a founder sees their own name on: with no name yet, this
  // greeted every founder as "Ayush" signed in as "ayush@brightloom.in".
  /* F11 is the Windows/Linux full-screen key; macOS uses Ctrl-Cmd-F, so naming
     F11 to everyone would send Mac founders after a key that does nothing. */
  const fullscreenKey =
    typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/i.test(navigator.userAgent)
      ? '\u2303\u2318F'
      : 'F11';

  const firstName = user?.name ? user.name.split(' ')[0] : 'there';
  const email = user?.email || '';

  const handleContinue = () => {
    if (user?.consents?.diagnosisConsent) {
      navigate('/guided/profile');
    } else {
      setShowModal(true);
    }
  };

  /* The consent has to reach the LEDGER, not just this component's state.
     Before this awaited grantDiagnosisConsent, the handler set
     `diagnosisConsent: true` on the in-memory user and navigated on, and
     nothing was ever posted to /consents. The founder saw consent given and
     the backend never recorded it -- which surfaces much later, and
     unrecognisably, as a 403 from POST /diagnosis/start (the only phase gated
     by `require_diagnosis_consent`; Founder DNA and current-problem are not),
     after the whole interview has been answered.

     So: persist first, and only move on if the write succeeded. On failure the
     modal stays open -- navigating would put the founder back in exactly the
     state this fixes. */
  const handleModalSubmit = async () => {
    if (savingConsent) return;
    setSavingConsent(true);
    try {
      await grantDiagnosisConsent();
    } catch {
      showToast('Could not save your consent just now. Please try again.');
      return;
    } finally {
      setSavingConsent(false);
    }
    setUser(prev => ({
      ...prev,
      consents: {
        ...prev?.consents,
        termsAccepted: prev?.consents?.termsAccepted ?? true,
        // From the constants, never a literal: a hardcoded version here stamps
        // the consent with a document the founder was not shown the moment the
        // policy is bumped, which is the one thing a consent record must not do.
        termsVersion: prev?.consents?.termsVersion ?? CURRENT_VERSIONS.terms,
        privacyVersion: prev?.consents?.privacyVersion ?? CURRENT_VERSIONS.privacy,
        diagnosisConsent: true,
        consentedAt: new Date().toISOString()
      }
    }));
    setShowModal(false);
    navigate('/guided/profile');
  };

  const handleModalCancel = () => {
    setShowModal(false);
    showToast('Diagnostic consent is required to begin the assessment.');
  };

  return (
    <>
      <section className="view j-stage active" id="v-welcome">
        <div className="j-inner wide wc-inner">
          <div className="j-avatar"><img src="/ally-logo-mark.png" alt="" /></div>
          {/* AppContext hydrates the real email a beat after this page mounts;
              showing "Signed in · " with nothing after the dot is worse than
              showing nothing until it lands. */}
          {email && (
            <div className="j-eye" style={{ justifyContent: 'center' }}>
              Signed in · <span data-fe="true">{email}</span>
            </div>
          )}
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

            <div className="wc-node" style={{ '--wd': '0s', '--wl': '0s' }}>
              <span className="wc-ic">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                  <path d="M9 4H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2" />
                  <rect x="9" y="2.5" width="6" height="3.5" rx="1.2" />
                  <path d="M9 13.2l2 2 4-4.4" />
                </svg>
              </span>
              <span className="wc-k">Onboarding</span>
              <span className="wc-t">A few basics so I know who I'm talking to.</span>
            </div>

            <div className="wc-node" style={{ '--wd': '.13s', '--wl': '.7s' }}>
              <span className="wc-ic">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                  <circle cx="12" cy="8" r="4" />
                  <path d="M4 21a8 8 0 0 1 16 0" />
                </svg>
              </span>
              <span className="wc-k">Founder DNA</span>
              <span className="wc-t">How you think — not just the company.</span>
            </div>

            <div className="wc-node" style={{ '--wd': '.27s', '--wl': '1.4s' }}>
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

            {/* Founder DNA and Business DNA are not two separate quizzes -- they are
                one adaptive read, each question shaped by the answer before it. The
                brace says that visually instead of asking the founder to infer it. */}
            <div className="wc-group">
              <span className="wc-group-brace" aria-hidden="true"></span>
              <span className="wc-group-k">Adaptive Diagnosis</span>
              {/* Once the grid collapses the brace stops pointing at anything, so
                  the pairing has to be said in words instead of drawn. */}
              <span className="wc-group-scope">Founder DNA + Business DNA</span>
              <span className="wc-group-t">One adaptive read — every question follows your last answer.</span>
            </div>

            <div className="wc-node" style={{ '--wd': '.41s', '--wl': '2.1s' }}>
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

            <div className="wc-node" style={{ '--wd': '.55s', '--wl': '2.8s' }}>
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

            <div className="wc-node wc-node-live" style={{ '--wd': '.69s', '--wl': '3.5s' }}>
              <span className="wc-ic">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                  <path d="M21 11.5a8.4 8.4 0 0 1-9 8.4A8.4 8.4 0 0 1 3.6 15L3 20.5l5.5-.6" />
                  <path d="M3 11.5a8.4 8.4 0 0 1 9-8.4 8.4 8.4 0 0 1 8.4 4.9" />
                  <circle cx="8.5" cy="11.5" r="1" />
                  <circle cx="12" cy="11.5" r="1" />
                  <circle cx="15.5" cy="11.5" r="1" />
                </svg>
              </span>
              <span className="wc-k">Daily Support<i className="wc-live" aria-hidden="true"></i></span>
              <span className="wc-t">Active every day after the report.</span>
            </div>
          </div>

          <div className="wc-daily">
            <span className="wc-daily-ic">✦</span>
            <span>
              The report is the start, not the end — I stay on to brainstorm, plan and decide with you, <b>every day</b>.
            </span>
          </div>
          <p className="wc-device">
            <span className="wc-device-ic" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                <rect x="2.5" y="4" width="19" height="13" rx="2" />
                <path d="M8.5 21h7M12 17v4" />
              </svg>
            </span>
            <span>
              Use a <b>desktop</b> for the best experience — more room to think, and nothing gets cut off.
              {/* No keyboard on a phone, so the shortcut is desktop-only advice. */}
              <span className="wc-device-key"> Press <kbd>{fullscreenKey}</kbd> for full screen.</span>
            </span>
          </p>
        </div>

        <div className="j-bar on" id="jBar" style={{ position: 'fixed', bottom: 0, left: 0, width: '100%', zIndex: 100 }}>
          <span className="jb-note" id="jbNote">About 20 minutes — a conversation, not a form.</span>
          <div className="spacer"></div>
          <button 
            className="btn btn-em cta-pulse" 
            id="jbBtn" 
            type="button" 
            onClick={handleContinue}
          >
            I'm ready <svg viewBox="0 0 24 24" className="w-4 h-4 inline-block ml-1" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
          </button>
        </div>
      </section>

      {showModal && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div className="modal-content">
            <div className="modal-logo">✦</div>
            <h2 className="modal-title" id="modal-title">Diagnostic Consent Required</h2>
            <p className="modal-desc">
              To analyze your leadership style and startup metrics, Ally needs your explicit permission to collect and process your business's diagnostic information.
            </p>
            
            <div className="modal-points">
              <div className="modal-point">
                <span className="modal-point-ic">✓</span>
                <span>Your responses are private, encrypted, and never shared with external parties.</span>
              </div>
              <div className="modal-point">
                <span className="modal-point-ic">✓</span>
                <span>You are in full control: you can request data deletion or withdraw consent at any time from your Privacy Center.</span>
              </div>
              <div className="modal-point">
                <span className="modal-point-ic">✓</span>
                <span>Consent is unbundled—you are opting in specifically for business analysis processing.</span>
              </div>
            </div>

            <div style={{ marginBottom: '24px' }}>
              <label className="consent-item">
                <input 
                  type="checkbox" 
                  checked={agreeModalDiagnosis} 
                  onChange={(e) => setAgreeModalDiagnosis(e.target.checked)} 
                />
                <span className="consent-text" style={{ color: '#fff' }}>
                  I consent to the collection and processing of my business's diagnostic information to generate my founder DNA report.
                </span>
              </label>
            </div>

            <div className="modal-actions">
              <button 
                className="modal-btn secondary" 
                onClick={handleModalCancel}
                type="button"
              >
                Go Back
              </button>
              <button 
                className="modal-btn primary" 
                onClick={handleModalSubmit}
                disabled={!agreeModalDiagnosis || savingConsent}
                type="button"
              >
                {savingConsent ? 'Saving\u2026' : 'Agree & Proceed'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
