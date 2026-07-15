import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

const STAGE_LABELS = {
  Idea: 'idea-stage',
  'Early traction': 'growth-led',
  Scaling: 'scale-building',
  Plateau: 'plateau-watch',
};

function buildFirstImpression(profile) {
  const stage = profile.stage || 'Idea';
  const challenge = (profile.challenges || profile.problem || 'Focus').toLowerCase();
  const industry = profile.industry || 'your market';
  const feeling = (profile.feeling || 'Steady').replace(/^[^A-Za-z]+\s*/, '').toLowerCase();

  return [
    `Noticed a ${stage.toLowerCase()} founder energy with fast, intuitive calls`,
    `Flagged pressure building around ${challenge}`,
    `Mapped your context through the lens of ${industry}`,
    `Reading your pace as ${feeling} — ready to go deeper with you`,
  ];
}

export default function Tour() {
  const navigate = useNavigate();
  const { user } = useApp();
  const [active, setActive] = useState(0);
  const profile = user?.founderProfile || {};
  const bullets = useMemo(() => buildFirstImpression(profile), [profile]);
  const eyebrow = (profile.stage && STAGE_LABELS[profile.stage]) || 'first-impression';

  useEffect(() => {
    setActive(0);
    const timers = bullets.map((_, index) => setTimeout(() => setActive(index + 1), 450 + index * 320));
    return () => timers.forEach(clearTimeout);
  }, [bullets]);

  return (
    <section className="view j-stage active">
      <div className="j-inner">
        <div className="j-eye">
          <span className="lv" />
          Ally is forming a {eyebrow.replace('-', ' ')}
        </div>

        <h1 className="j-title" style={{ textAlign: 'center', maxWidth: 'none' }}>
          Reading between the lines…
        </h1>

        <div className="tl" style={{ maxWidth: '440px', margin: '28px auto 0', textAlign: 'center' }}>
          {bullets.map((item, index) => {
            const isOn = active > index;
            return (
              <div
                key={item}
                className={`tl-i ${isOn ? (index === bullets.length - 1 ? 'now' : 'done') : ''}`}
                style={{
                  opacity: isOn ? 1 : 0.28,
                  transform: isOn ? 'translateY(0)' : 'translateY(8px)',
                  transition: 'opacity .45s var(--primary), transform .45s var(--primary)',
                }}
              >
                <div className="tl-rail">
                  <div className="tl-dot" />
                  <div className="tl-line" />
                </div>
                <div className="tl-t">{item}</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="j-bar on" id="jBar" style={{ position: 'fixed', bottom: 0, left: 0, width: '100%', zIndex: 100 }}>
        <span className="jb-note" id="jbNote">Ally has a first read of you.</span>
        <div className="spacer"></div>
        <button
          className="btn btn-em"
          type="button"
          onClick={() => navigate('/guided/summary')}
        >
          Continue <svg viewBox="0 0 24 24" className="w-4 h-4 inline-block ml-1" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </button>
      </div>
    </section>
  );
}

