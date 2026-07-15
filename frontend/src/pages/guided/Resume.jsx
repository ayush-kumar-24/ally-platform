import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

export default function Resume() {
  const navigate = useNavigate();
  const { user } = useApp();

  const firstName = user?.name ? user.name.split(' ')[0] : 'Ayush';

  return (
    <section className="view j-stage active" id="v-resume">
      <div className="j-inner" style={{ maxWidth: '568px' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'center' }}>
            <div className="ring" style={{ width: '110px', height: '110px' }}>
              <svg viewBox="0 0 132 132">
                <circle className="bg" cx="66" cy="66" r="57" />
                <circle className="fg" cx="66" cy="66" r="57" style={{ strokeDashoffset: '130.68px' }} />
              </svg>
              <div className="mid">
                <div className="n" style={{ fontSize: '26px' }}>
                  64<span style={{ fontSize: '12px', color: 'var(--emerald)' }}>%</span>
                </div>
              </div>
            </div>
          </div>
          <h1 className="j-title">
            Welcome back, <em style={{ fontStyle: 'italic', color: 'var(--emerald-glow)' }}>{firstName}</em>.
          </h1>
          <p className="j-sub" style={{ marginBottom: '32px' }}>
            Let's finish what we started. You're 64% of the way to your Founder Report.
          </p>
        </div>

        <div className="j-cards" style={{ gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '32px' }}>
          <div className="card j-c">
            <span className="jc-l">Founder DNA</span>
            <div className="jc-val">64%</div>
            <div className="jc-st">Analyzing style</div>
          </div>
          <div className="card j-c">
            <span className="jc-l">Business DNA</span>
            <div className="jc-val">55%</div>
            <div className="jc-st">Mapping dimensions</div>
          </div>
        </div>

        <div className="j-actions" style={{ marginTop: 0 }}>
          <button
            className="btn btn-em j-btn-lg"
            type="button"
            onClick={() => navigate('/guided/expectation')}
          >
            Continue assessment
            <svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
          </button>
        </div>
      </div>
    </section>
  );
}
