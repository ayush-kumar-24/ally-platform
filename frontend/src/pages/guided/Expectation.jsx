import { useNavigate } from 'react-router-dom';

export default function Expectation() {
  const navigate = useNavigate();

  return (
    <section className="view j-stage active exp" id="v-expectation">
      <div className="j-inner">
        <div className="j-eye">How it works</div>
        <h1 className="j-title">How the next 20 minutes work</h1>
        <p className="j-sub" style={{ marginBottom: '28px' }}>
          Three simple phases to get you from uncertainty to clarity.
        </p>

        <div className="j-cards" style={{ gridTemplateColumns: '1fr', gap: '12px', marginBottom: '28px' }}>
          <div className="card j-c">
            <span className="jc-l">Phase 1</span>
            <div className="jc-val">We talk</div>
            <div className="jc-st">
              A guided conversation about your founder journey, decision patterns, and business challenges. (~10 min)
            </div>
          </div>
          <div className="card j-c">
            <span className="jc-l">Phase 2</span>
            <div className="jc-val">Ally connects</div>
            <div className="jc-st">
              Founder patterns are mapped to business dimensions to find the hidden root cause.
            </div>
          </div>
          <div className="card j-c">
            <span className="jc-l">Phase 3</span>
            <div className="jc-val">You get clarity</div>
            <div className="jc-st">
              A clear report with your root constraint, blind spots, and actionable next steps.
            </div>
          </div>
        </div>
      </div>

      <div className="j-bar on" id="jBar" style={{ position: 'fixed', bottom: 0, left: 0, width: '100%', zIndex: 100 }}>
        <span className="jb-note" id="jbNote">About 20 minutes — a conversation, not a form.</span>
        <div className="spacer"></div>
        <button
          className="btn btn-em"
          type="button"
          onClick={() => navigate('/guided/ally-intro')}
        >
          Let's go <svg viewBox="0 0 24 24" className="w-4 h-4 inline-block ml-1" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </button>
      </div>
    </section>
  );
}
