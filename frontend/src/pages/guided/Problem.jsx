import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { updateBusinessSection } from '../../services/profile';
import { primary } from '../../utils/profileDisplay';

function buildExamples(profile) {
  // profile.biggestChallenge is a jsonb array (current_challenges) -- primary()
  // reads it back as one plain string instead of handing the raw array to
  // setProblem, which made `problem` a non-string and crashed handleContinue's
  // `.trim()`. Was keyed to 'challenges', which stopped existing when the
  // 2026-08-17 redesign renamed it -- same class of silent-fallback bug this
  // file's own comment already once described.
  const suggestions = [primary('biggestChallenge', profile.biggestChallenge), 'Growth flatlined', 'Users don\'t activate', 'Cash feels tight'].filter(Boolean);
  return Array.from(new Set(suggestions)).slice(0, 3);
}

export default function Problem() {
  const navigate = useNavigate();
  const { user, setUser } = useApp();
  const profile = user?.founderProfile || {};
  const examples = useMemo(() => buildExamples(profile), [profile]);
  const [problem, setProblem] = useState(user?.problem || profile.problem || '');
  const [starting, setStarting] = useState(false);

  /**
   * Hands off into the REAL diagnosis (/app/diagnosis, backend-driven, gated on
   * the server's is_complete flag). This used to navigate into a scripted
   * `/guided/reveal -> root-cause -> conclusion -> report` sequence that was
   * entirely hardcoded UI theater -- fixed dialogue and a fixed "root cause"
   * regardless of what a founder typed here -- so every founder saw a finished
   * report after one tap. That sequence has been removed; this is now the only
   * diagnosis a founder goes through.
   */
  const handleContinue = async () => {
    if (starting) return;
    setStarting(true);
    setUser((prev) => ({
      ...prev,
      problem,
      founderProfile: {
        ...(prev?.founderProfile || {}),
        perceivedProblem: problem,
      },
    }));
    try {
      await updateBusinessSection({ problem_statement: problem });
    } catch {
      // Not fatal -- the diagnosis itself doesn't depend on this having saved.
    }
    navigate('/app/diagnosis');
  };

  return (
    <section className="view j-stage active">
      <div className="j-inner" style={{ width: '100%', maxWidth: '620px' }}>
        <div className="j-eye">In your own words</div>
        <h1 className="j-title">
          What feels most <em style={{ color: 'var(--emerald-glow)', fontStyle: 'italic' }}>stuck</em> right now?
        </h1>
        <p className="j-sub">
          Don't diagnose it — just describe it. Ally will find what's really causing it.
        </p>

        <label className="sr-only" htmlFor="gp-problem">Describe the problem you are facing</label>
        {/* Submit sits ON the field, not only in the fixed bottom bar. That bar
            was the sole way to continue, and on a short viewport it is the
            first thing off-screen -- a founder who has typed their answer is
            then looking at a box with no visible way forward. Enter submits
            too, matching every other answer box in the app. */}
        <div className="gp-field">
          <textarea
            id="gp-problem"
            className="j-input"
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleContinue(); }
            }}
            placeholder="e.g. we're spending more on marketing but growth has completely flatlined..."
            rows={3}
            style={{ marginTop: '24px', resize: 'none', paddingRight: '58px' }}
          />
          <button
            className="ci-btn send gp-send"
            type="button"
            onClick={handleContinue}
            disabled={!problem.trim() || starting}
            title="Start diagnosis"
            aria-label="Start diagnosis"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>

        <div className="chip-row" style={{ justifyContent: 'center', marginTop: '14px' }}>
          {examples.map((item) => (
            <button key={item} className="opt" type="button" onClick={() => setProblem(item)}>
              {item}
            </button>
          ))}
        </div>
      </div>

      <div className="j-bar on" id="jBar" style={{ position: 'fixed', bottom: 0, left: 0, width: '100%', zIndex: 100 }}>
        <span className="jb-note" id="jbNote">Describe it in your own words.</span>
        <div className="spacer"></div>
        <button
          className="btn btn-em"
          type="button"
          onClick={handleContinue}
          disabled={!problem.trim() || starting}
          style={{ opacity: problem.trim() && !starting ? 1 : 0.4, pointerEvents: problem.trim() && !starting ? 'auto' : 'none' }}
        >
          {starting ? 'Starting…' : 'Start diagnosis'} <svg viewBox="0 0 24 24" className="w-4 h-4 inline-block ml-1" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </button>
      </div>
    </section>
  );
}

