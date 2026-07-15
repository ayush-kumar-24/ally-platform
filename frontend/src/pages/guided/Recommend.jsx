import { useNavigate } from 'react-router-dom';

export default function Recommend() {
  const navigate = useNavigate();

  return (
    <section className="view j-stage active">
      <div className="j-inner" style={{ width: '100%', maxWidth: '620px' }}>
        <div className="j-eye">The right next step for you</div>
        <h1 className="j-title">
          Ally recommends a <em>Retention Sprint.</em>
        </h1>
        <p className="j-sub">
          Based on your diagnosis and how you lead, this is the GoXL engagement that fits where you actually are - not a template.
        </p>

        <div className="rec-card">
          <span className="rc-badge">Recommended · matched to your root cause</span>
          <h3>90-Day Retention Sprint</h3>
          <p className="rc-d">
            A focused GoXL engagement to seal the week-two leak before you scale spend, sequenced to your fast-moving, growth-led style.
          </p>
          <ul className="rec-fit">
            <li>
              <span className="fk">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6 9 17l-5-5" /></svg>
              </span>
              <span>Directly targets your #1 constraint — retention</span>
            </li>
            <li>
              <span className="fk">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6 9 17l-5-5" /></svg>
              </span>
              <span>Paced to how you actually execute</span>
            </li>
            <li>
              <span className="fk">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><path d="M20 6 9 17l-5-5" /></svg>
              </span>
              <span>Ends with one weekly north-star metric</span>
            </li>
          </ul>
          <button
            className="btn btn-em j-btn-lg"
            type="button"
            onClick={() => navigate('/guided/discovery')}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></svg>
            Book your discovery call
          </button>
        </div>
      </div>
    </section>
  );
}
