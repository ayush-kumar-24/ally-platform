import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { labelFor, midSentence, readable } from '../../utils/profileDisplay';
import { useFounderRead } from '../../hooks/useFounderRead';

/* Keyed to the eight stages the database actually stores. The previous map
   listed 'Idea' / 'Early traction' / 'Scaling' / 'Plateau', none of which are
   real stage names, so the eyebrow always fell through to 'first-impression'. */
const STAGE_LABELS = {
  Ideation: 'idea-stage',
  Validation: 'signal-hunting',
  'Prototype / MVP': 'build-led',
  'Early Traction': 'traction-led',
  'Growth / Scaling': 'scale-building',
  Expansion: 'expansion-minded',
  Maturity: 'steward-led',
  Exit: 'legacy-minded',
};

/** Fallback used until the generated read arrives (or if it never does). */
function buildFirstImpression(profile) {
  const stage = profile.stage || 'Ideation';
  const challenge = readable('challenges', profile.challenges) || profile.problem || 'focus';
  const industry = profile.industry || 'your market';
  const feeling = labelFor('feeling', profile.feeling) || 'Steady';

  return [
    `Noticed a ${midSentence(stage)} founder energy with fast, intuitive calls`,
    `Flagged pressure building around ${midSentence(challenge)}`,
    `Mapped your context through the lens of ${midSentence(industry)}`,
    `Reading your pace as ${midSentence(feeling)} — ready to go deeper with you`,
  ];
}

export default function Tour() {
  const navigate = useNavigate();
  const [active, setActive] = useState(0);

  /* The server forms one impression from the founder's stored answers and keeps
     it, so it never rewrites itself under them. Fetched rather than built here:
     swapping words into fixed sentences is not a read, and the answers live on
     the server rather than in this tab's memory. */
  const { answers: profile, impression } = useFounderRead();

  // Until it arrives (or if it never does), fall back to what we can derive.
  const bullets = useMemo(
    () => (impression?.bullets?.length ? impression.bullets : buildFirstImpression(profile)),
    [impression, profile],
  );
  /* Every STAGE_LABELS value is an adjective ("scale-building", "traction-led"),
     so the eyebrow needs a noun after it -- rendered bare it read
     "ALLY IS FORMING A SCALE BUILDING". The fallback is 'founder' rather than
     'first-impression' for the same reason: "your founder read" is a sentence,
     "your first-impression read" is a stutter. */
  const eyebrow = (profile.stage && STAGE_LABELS[profile.stage]) || 'founder';

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
          {/* Hyphen kept: these are compound adjectives, and "scale-building
              read" is easier to parse than "scale building read". */}
          Ally is forming your {eyebrow} read
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

