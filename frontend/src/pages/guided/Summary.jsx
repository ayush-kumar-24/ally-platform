import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

const FIELD_ORDER = [
  ['stage', 'Entrepreneurial Stage'],
  ['building', "What You're Building"],
  ['problem', 'Problem Statement'],
  ['customer', 'Customer Segment'],
  ['industry', 'Industry'],
  ['challenges', 'Biggest Challenges'],
  ['goal90', '90-Day Goal'],
  ['vision', 'One-Year Vision'],
  ['why', 'Why You Started'],
  ['working', 'Working Style'],
  ['experience', 'Experience Level'],
  ['feeling', 'Current Feeling'],
  ['reflection', 'Stage Reflection'],
];

function buildRead(profile) {
  const stage = profile.stage || 'this stage';
  const challenge = (profile.challenges || 'focus').toLowerCase();
  const why = profile.why || 'you care deeply about the problem itself';
  return `You lead with conviction and move fast — the instinct that got you to ${stage.toLowerCase()}. You have strong momentum, but I can already see attention pulling toward ${challenge}. The reason underneath it all feels personal: ${why.toLowerCase()}.`;
}

function buildTags(profile) {
  const tags = [];
  if (profile.stage) tags.push(profile.stage);
  if (profile.working) tags.push(profile.working);
  if (profile.experience) tags.push(profile.experience);
  if (profile.challenges) tags.push(profile.challenges);
  return tags.slice(0, 4);
}

export default function Summary() {
  const navigate = useNavigate();
  const { user, setUser } = useApp();
  const profile = user?.founderProfile || {};
  const [form, setForm] = useState(() => Object.fromEntries(FIELD_ORDER.map(([key]) => [key, profile[key] || ''])));
  const allyRead = useMemo(() => buildRead(form), [form]);
  const tags = useMemo(() => buildTags(form), [form]);

  const handleChange = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleConfirm = () => {
    setUser((prev) => ({
      ...prev,
      stage: form.stage || prev.stage,
      problem: form.problem || prev.problem,
      company: form.building || prev.company,
      founderProfile: {
        ...(prev?.founderProfile || {}),
        ...form,
      },
    }));
    navigate('/guided/validate');
  };

  return (
    <section className="view j-stage active">
      <div className="j-inner wide" style={{ textAlign: 'left' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="j-avatar"><img src="/ally-logo.png" alt="" /></div>
          <div className="j-eye">How Ally read you</div>
          <h1 className="j-title" style={{ textAlign: 'center', maxWidth: 'none' }}>
            Here's what I've got, <em style={{ fontStyle: 'italic', color: 'var(--emerald-glow)' }}>{user?.name ? user.name.split(' ')[0] : 'Ayush'}</em>.
          </h1>
          <p className="j-sub" style={{ marginBottom: '6px' }}>
            From our conversation, this is your founder profile. Edit anything that isn't quite right — then confirm, and we'll begin the diagnosis.
          </p>
        </div>

        <div className="summary-card">
          <div className="sc-fields" style={{ maxHeight: 'calc(100vh - 290px)', overflowY: 'auto' }}>
            {FIELD_ORDER.map(([key, label]) => (
              <div key={key} className="sc-f">
                <label>{label}</label>
                <input
                  value={form[key]}
                  onChange={(e) => handleChange(key, e.target.value)}
                />
              </div>
            ))}
          </div>

          <div className="sc-read">
            <div className="sc-read-l">Ally's early read</div>
            <p className="sc-read-p">{allyRead}</p>
            <div className="traits">
              {tags.map((tag) => (
                <span key={tag} className="trait">{tag}</span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="j-bar on" id="jBar" style={{ position: 'fixed', bottom: 0, left: 0, width: '100%', zIndex: 100 }}>
        <span className="jb-note" id="jbNote">Edit anything, then confirm.</span>
        <div className="spacer"></div>
        <button
          className="btn btn-em"
          type="button"
          onClick={handleConfirm}
        >
          Confirm — this is me <svg viewBox="0 0 24 24" className="w-4 h-4 inline-block ml-1" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </button>
      </div>
    </section>
  );
}

