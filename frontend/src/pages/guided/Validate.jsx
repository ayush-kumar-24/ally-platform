import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

function buildQuote(profile) {
  const challenge = (profile.challenges || 'growth').toLowerCase();
  if (challenge.includes('retention')) return 'Your instinct when retention slips is to double down on what already feels proven.';
  if (challenge.includes('acquisition')) return 'Your instinct when growth stalls is to push harder on what already works.';
  if (challenge.includes('focus')) return 'Your instinct when things blur is to move faster so clarity can catch up later.';
  return 'Your instinct when growth stalls is to push harder on what already works.';
}

export default function Validate() {
  const navigate = useNavigate();
  const { user, setUser } = useApp();
  const profile = user?.founderProfile || {};
  const quote = useMemo(() => buildQuote(profile), [profile]);

  const handleAnswer = (value) => {
    setUser((prev) => ({ ...prev, founderProfile: { ...(prev?.founderProfile || {}), validation: value } }));
    navigate('/guided/problem');
  };

  return (
    <section className="view j-stage active">
      <div className="j-inner">
        <div className="j-eye">Did I get you right?</div>
        <h1
          className="j-title"
          style={{ textAlign: 'center', maxWidth: 'none' }}
        >
          “{quote.split(' ').slice(0, -3).join(' ')} <em style={{ color: 'var(--emerald-glow)', fontStyle: 'italic' }}>{quote.split(' ').slice(-3).join(' ')}</em>”
        </h1>
        <p className="j-sub" style={{ marginTop: '22px' }}>
          Tell me if this feels true. Your answer shapes everything that comes next.
        </p>

        <div className="j-actions">
          <button className="btn btn-em j-btn-lg" type="button" onClick={() => handleAnswer('yes')}>
            Yes — that's me
          </button>
          <button className="btn btn-dark-ghost j-btn-lg" type="button" onClick={() => handleAnswer('nuance')}>
            Mostly, with nuance
          </button>
        </div>
      </div>
    </section>
  );
}

