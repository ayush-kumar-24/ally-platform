import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { primary } from '../../utils/profileDisplay';
import { useFounderRead } from '../../hooks/useFounderRead';

/* Keyed to the challenge values onboarding actually stores. The previous
   version matched 'retention' / 'acquisition' / 'focus' -- none of which exist
   in the question set any more -- so every founder fell through to the same
   default line. `challenges` is also a list now, hence primary() rather than
   calling .toLowerCase() on an array. */
const INSTINCT_BY_CHALLENGE = {
  'Getting customers': 'Your instinct when growth stalls is to push harder on what already works.',
  Sales: 'Your instinct when the pipeline thins is to sell your way out of it personally.',
  Marketing: 'Your instinct when nobody is listening is to say it louder rather than differently.',
  Hiring: 'Your instinct when the team is stretched is to absorb the work yourself first.',
  Team: 'Your instinct when the team wobbles is to carry more of it yourself.',
  Leadership: 'Your instinct under pressure is to take the weight rather than share it.',
  'Cash flow': 'Your instinct when money is tight is to cut before you ask for help.',
  Fundraising: 'Your instinct when runway shortens is to keep building rather than start raising.',
  Scaling: 'Your instinct when something works is to pour more into it before it is ready.',
  Operations: 'Your instinct when things get messy is to hold the process together manually.',
  'Building the product': 'Your instinct when unsure is to build a little more before you ask.',
  'Finding the right idea': 'Your instinct when the path is unclear is to keep exploring rather than commit early.',
  'Decision making': 'Your instinct when the call is close is to sit with it longer than you need to.',
  Productivity: 'Your instinct when the day gets away from you is to work later rather than narrower.',
};

function buildQuote(profile) {
  const top = primary('challenges', profile.challenges);
  return INSTINCT_BY_CHALLENGE[top]
    || 'Your instinct when growth stalls is to push harder on what already works.';
}

export default function Validate() {
  const navigate = useNavigate();
  const { setUser } = useApp();

  /* The same stored impression the previous two screens showed -- asking a
     founder to confirm a sentence Ally never actually said would be theatre. */
  const { answers: profile, impression } = useFounderRead();
  const quote = useMemo(
    () => impression?.instinct || buildQuote(profile),
    [impression, profile],
  );

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

