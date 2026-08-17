import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { labelFor, listed, midSentence, primary, readable } from '../../utils/profileDisplay';
import { saveProfileEdits } from '../../services/profile';
import { useFounderRead } from '../../hooks/useFounderRead';
import { PATH_1, PATH_2, QUESTIONS, STAGE_BY_NAME } from '../../data/onboardingQuestions';

/* Rewritten 2026-08-17 for the 4-section, path-branching onboarding redesign.
   The previous FIELD_ORDER/SAVE_AS were never updated when that rewrite
   happened -- 'goal90', 'challenges', 'vision' etc. were the OLD guided-answer
   keys, none of which toGuidedAnswers() emits any more (the current keys are
   'biggestChallenge', 'ninetyDayGoal'/'oneYearSuccess', ...), so those rows
   silently rendered "Not answered" forever despite the real data sitting in
   the database. Also dropped here: why/support/feeling/reflection, which the
   redesign retired from onboarding entirely -- this screen has no business
   still asking a founder to review answers to questions nobody asks anymore.

   `edit: true` marks the answers a founder typed, which they can retype here.
   `yesno: true` marks the two reality-check blocks (a fixed object, not free
   text or a simple pick-list) and gets its own formatter. Everything else was
   chosen from a fixed set; free-texting those would either be discarded on
   save or rejected as invalid, so they are shown, not offered for edit. */
function fieldOrder(path) {
  const rows = [
    ['stage', 'Entrepreneurial Stage'],
    ['socialHandle', 'Social Handle', { edit: true }],
  ];
  if (path === PATH_2) {
    rows.push(
      ['building', "What You're Building", { edit: true }],
      ['productDescription', 'What It Is', { edit: true }],
    );
  } else if (path === PATH_1) {
    rows.push(['ideaName', 'Idea Name', { edit: true }]);
  }
  rows.push(
    ['problem', 'Problem Statement', { edit: true }],
    ['audience', 'Who You Serve'],
    ['industry', 'Industry'],
  );
  if (path === PATH_2) rows.push(['revenue', 'Monthly Revenue']);
  rows.push(['founderReality', 'Founder Reality', { yesno: true }]);
  if (path === PATH_2) rows.push(['businessReality', 'Business Reality', { yesno: true }]);
  rows.push(
    ['invisibleGaps', 'Invisible Gaps'],
    ['biggestChallenge', 'Biggest Challenge'],
  );
  if (path === PATH_2) rows.push(['oneYearSuccess', 'One-Year Vision', { edit: true }]);
  else if (path === PATH_1) rows.push(['ninetyDayGoal', '90-Day Goal', { edit: true }]);
  rows.push(['experience', 'Experience Level']);
  return rows;
}

/** Guided key -> the /profile/* field it saves back to. Only needs entries
 * for `edit: true` rows above -- static rows are never retyped. */
const SAVE_AS = {
  socialHandle: 'linkedin_url',
  building: 'building_summary',
  ideaName: 'building_summary', // same column, mutually exclusive by path
  productDescription: 'product_description',
  problem: 'problem_statement',
  oneYearSuccess: 'vision_1_year',
  ninetyDayGoal: 'goal_90_day',
};

/** The 5-item reality-check blocks are a fixed object ({itemKey: bool}), not
 * free text or a simple pick-list -- listed()/labelFor() would stringify it
 * to "[object Object]". Same per-item Yes/No summary the live onboarding
 * flow and its resume path already build. */
function yesNoSummary(key, value) {
  const q = QUESTIONS.find((x) => x.key === key);
  if (!q || !value) return '';
  return q.items.map((it) => `${it.text}: ${value[it.key] ? 'Yes' : 'No'}`).join(' · ');
}

/** Fallback used until the generated read arrives (or if it never does). */
function buildRead(profile) {
  const stage = profile.stage || 'this stage';
  const challenge = readable('biggestChallenge', profile.biggestChallenge) || 'focus';
  const problem = profile.problem || 'the problem you set out to solve';
  return `You lead with conviction and move fast — the instinct that got you to ${midSentence(stage)}. You have strong momentum, but I can already see attention pulling toward ${midSentence(challenge)}. What you're solving feels real and specific: ${midSentence(problem)}`;
}

function buildTags(profile) {
  return [
    labelFor('stage', profile.stage),
    labelFor('experience', profile.experience),
    primary('biggestChallenge', profile.biggestChallenge),
    primary('invisibleGaps', profile.invisibleGaps),
  ].filter(Boolean).slice(0, 4);
}

export default function Summary() {
  const navigate = useNavigate();
  const { user, setUser, showToast } = useApp();
  const { answers: profile, impression, loaded } = useFounderRead();
  const path = profile.stage ? (STAGE_BY_NAME[profile.stage]?.path || null) : null;
  const FIELD_ORDER = useMemo(() => fieldOrder(path), [path]);
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
  }, [loaded, profile, FIELD_ORDER]);

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
      company: merged.building || merged.ideaName || prev.company,
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
          <div className="sc-fields">
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
                  /* Chosen from a fixed set (or, for the two reality checks, a
                     fixed object), so shown as chosen, not offered for edit. */
                  <p className="sc-f-static" id={`sc-${key}`}>
                    {(opts?.yesno ? yesNoSummary(key, profile[key]) : listed(key, profile[key]))
                      || <span className="sc-f-empty">Not answered</span>}
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
