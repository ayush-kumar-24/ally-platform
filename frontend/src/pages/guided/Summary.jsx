import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { labelFor, listed, midSentence, primary, readable } from '../../utils/profileDisplay';
import { saveProfileEdits } from '../../services/profile';
import { useFounderRead } from '../../hooks/useFounderRead';

/* Order and labels mirror data/onboardingQuestions.js. Two keys here were stale
   after onboarding was rebuilt -- 'customer' is now 'audience' and 'working' is
   now 'support' -- so both rows rendered permanently blank.

   `edit: true` marks the answers a founder typed, which they can retype here.
   The rest were chosen from a fixed set (a stage, a capped multi-select, an
   enum the database constrains); free-texting those would either be discarded
   on save or rejected as invalid, so they are shown, not offered for edit. */
const FIELD_ORDER = [
  ['stage', 'Entrepreneurial Stage'],
  ['building', "What You're Building", { edit: true }],
  ['problem', 'Problem Statement', { edit: true }],
  ['audience', 'Who You Serve'],
  ['industry', 'Industry'],
  ['challenges', 'Biggest Challenges'],
  ['goal90', '90-Day Breakthrough', { edit: true }],
  ['vision', 'One-Year Vision', { edit: true }],
  ['why', 'Founder Story', { edit: true }],
  ['support', 'How Ally Helps'],
  ['experience', 'Experience Level'],
  ['feeling', 'Today’s Mindset'],
  ['reflection', 'Stage Reflection', { edit: true }],
];

/** Guided key -> the /profile/* field it saves back to. */
const SAVE_AS = {
  building: 'building_summary',
  problem: 'problem_statement',
  goal90: 'goal_90_day',
  vision: 'vision_1_year',
  why: 'founder_motivation',
  reflection: 'adaptive_reflection',
};

/** Fallback used until the generated read arrives (or if it never does). */
function buildRead(profile) {
  const stage = profile.stage || 'this stage';
  const challenge = readable('challenges', profile.challenges) || 'focus';
  const why = profile.why || 'you care deeply about the problem itself';
  return `You lead with conviction and move fast — the instinct that got you to ${midSentence(stage)}. You have strong momentum, but I can already see attention pulling toward ${midSentence(challenge)}. The reason underneath it all feels personal: ${midSentence(why)}`;
}

function buildTags(profile) {
  return [
    labelFor('stage', profile.stage),
    primary('support', profile.support),
    labelFor('experience', profile.experience),
    primary('challenges', profile.challenges),
  ].filter(Boolean).slice(0, 4);
}

export default function Summary() {
  const navigate = useNavigate();
  const { user, setUser, showToast } = useApp();
  const { answers: profile, impression, loaded } = useFounderRead();
  // Only the typed answers are editable, so only those live in form state.
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  /* Seed the editable boxes once the founder's real answers land. Without this
     the form is built from React state, which a reload has already emptied --
     every field read "Not answered" while the answers sat in the database. */
  useEffect(() => {
    if (!loaded) return;
    setForm((prev) => Object.fromEntries(
      FIELD_ORDER.filter(([, , o]) => o?.edit)
        .map(([key]) => [key, prev[key] ?? (profile[key] || '')]),
    ));
  }, [loaded, profile]);

  const merged = useMemo(() => ({ ...profile, ...form }), [profile, form]);
  const allyRead = impression?.read || buildRead(merged);
  const tags = useMemo(() => buildTags(merged), [merged]);

  const handleChange = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleConfirm = async () => {
    if (saving) return;
    setSaving(true);

    /* Persist the edits. Previously this only wrote to React state, so
       "Edit anything that isn't quite right" was a lie -- the correction was
       gone by the next reload and never reached the diagnosis that reads it. */
    const changed = Object.entries(form).reduce((acc, [key, value]) => {
      const text = (value ?? '').trim();
      if (text && text !== (profile[key] ?? '')) acc[SAVE_AS[key]] = text;
      return acc;
    }, {});

    if (Object.keys(changed).length > 0) {
      try {
        await saveProfileEdits(changed);
      } catch {
        // Keep going: the founder's corrections stay in this session either
        // way, and blocking the hand-off to the diagnosis would cost more.
        showToast?.('Saved locally — we could not reach the server just now.');
      }
    }

    setUser((prev) => ({
      ...prev,
      stage: merged.stage || prev.stage,
      problem: merged.problem || prev.problem,
      company: merged.building || prev.company,
      founderProfile: { ...(prev?.founderProfile || {}), ...form },
    }));
    setSaving(false);
    navigate('/guided/validate');
  };

  return (
    <section className="view j-stage active">
      <div className="j-inner wide" style={{ textAlign: 'left' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="j-avatar"><img src="/ally-logo.png" alt="" /></div>
          <div className="j-eye">How Ally read you</div>
          <h1 className="j-title" style={{ textAlign: 'center', maxWidth: 'none' }}>
            Here's what I've got, <em style={{ fontStyle: 'italic', color: 'var(--emerald-glow)' }}>{user?.name ? user.name.split(' ')[0] : 'there'}</em>.
          </h1>
          <p className="j-sub" style={{ marginBottom: '6px' }}>
            From our conversation, this is your founder profile. Reword anything you wrote that isn't quite right — then confirm, and we'll begin the diagnosis.
          </p>
        </div>

        <div className="summary-card">
          <div className="sc-fields" style={{ maxHeight: 'calc(100vh - 290px)', overflowY: 'auto' }}>
            {FIELD_ORDER.map(([key, label, opts]) => (
              <div key={key} className="sc-f">
                <label htmlFor={`sc-${key}`}>{label}</label>
                {opts?.edit ? (
                  <input
                    id={`sc-${key}`}
                    value={form[key] ?? ''}
                    onChange={(e) => handleChange(key, e.target.value)}
                  />
                ) : (
                  /* Chosen from a fixed set, so shown as chosen. Rendering an
                     array or an enum into a text box gave "Hiring,Cash flow"
                     and "one_company" and quietly broke on save. */
                  <p className="sc-f-static" id={`sc-${key}`}>
                    {listed(key, profile[key]) || <span className="sc-f-empty">Not answered</span>}
                  </p>
                )}
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
          disabled={saving}
          onClick={handleConfirm}
        >
          {saving ? 'Saving…' : 'Confirm — this is me'} <svg viewBox="0 0 24 24" className="w-4 h-4 inline-block ml-1" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </button>
      </div>
    </section>
  );
}

