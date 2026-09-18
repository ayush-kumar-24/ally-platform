import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { labels } from '../../utils/profileDisplay';

function buildExamples(profile) {
  /* The founder's OWN challenges first. They picked these minutes ago, so they
     are the only suggestions guaranteed to mean something for their business.
     biggestChallenge is a jsonb array (current_challenges) -- labels() reads it
     back as one plain string per answer, instead of handing the raw array to
     setProblem, which made `problem` a non-string and crashed handleContinue's
     `.trim()`. Was keyed to 'challenges', which stopped existing when the
     2026-08-17 redesign renamed it -- same class of silent-fallback bug this
     file's own comment already once described.

     The padding behind them is deliberately industry-neutral. It used to read
     "Growth flatlined" / "Users don't activate", which is SaaS talk: live-
     reported by a founder running an industrial construction firm, who was
     offered "Users don't activate" as a way to describe what felt stuck. A
     suggestion that cannot apply is worse than no suggestion -- it tells the
     founder this product was not built for them. These three hold for a
     contractor, a clinic and a SaaS alike. */
  const suggestions = [
    ...labels('biggestChallenge', profile.biggestChallenge),
    'Cash feels tight',
    'Growth has stalled',
    'Too much depends on me',
  ].filter(Boolean);
  return Array.from(new Set(suggestions)).slice(0, 3);
}

export default function Problem() {
  const navigate = useNavigate();
  const { user, setUser } = useApp();
  const profile = user?.founderProfile || {};
  const examples = useMemo(() => buildExamples(profile), [profile]);
  /* Seeded from this screen's OWN previous answer, never from `problem`.
     `problem` is the answer to onboarding Q5, "What problem are you trying to
     solve?" -- the problem the BUSINESS exists to solve. This screen asks
     "What feels most stuck right now?", which is the founder's current pain
     and a different question entirely. Live-reported: a founder arrived here
     to find the box already holding their company description, one tap from
     sending it as the symptom the whole diagnosis is built on. */
  const [problem, setProblem] = useState(profile.perceivedProblem || '');
  const [starting, setStarting] = useState(false);

  /**
   * Hands off into the REAL diagnosis: backend-driven, and entered at
   * /app/founder-dna-journey. This used to navigate into a scripted
   * `/guided/reveal -> root-cause -> conclusion -> report` sequence that was
   * entirely hardcoded UI theater -- fixed dialogue and a fixed "root cause"
   * regardless of what a founder typed here -- so every founder saw a finished
   * report after one tap. That sequence has been removed; this is now the only
   * diagnosis a founder goes through.
   *
   * That removal pointed this at /app/diagnosis, which is the THIRD of three
   * phases. POST /diagnosis/start refuses with 409 until Founder DNA and the
   * Current Problem capture are both done (see diagnosis/service.py's
   * start_session), so every founder finishing onboarding landed on a chat
   * that could only say "I couldn't start your diagnosis just now. Please
   * refresh to try again." -- advice that can never work, on the very first
   * screen after they finished setting themselves up.
   *
   * The journey entry point is where every other "start your diagnosis"
   * affordance in the app already sends them: the sidebar item (PlatformLayout),
   * the dashboard's empty state and compass loop, DnaState, the recommendations
   * page, and Ally's own missing_information suggestion. This makes the last
   * step of onboarding agree with all six.
   */
  const handleContinue = async () => {
    if (starting) return;
    setStarting(true);
    /* perceivedProblem only. `user.problem` is the session copy of onboarding
       Q5's answer -- ProfileBuild and Summary both write it from there and read
       it back as that -- and AppContext persists the whole user object to
       localStorage, so writing this screen's answer into it made the same
       swap the server-side one did, and made it survive a reload. */
    setUser((prev) => ({
      ...prev,
      founderProfile: {
        ...(prev?.founderProfile || {}),
        perceivedProblem: problem,
      },
    }));
    /* Deliberately NOT written to problem_statement. That column holds the
       answer to onboarding Q5 -- a different question -- and the founder has
       already reviewed and confirmed it on the summary screen. Saving here
       overwrote it with the answer to this one, so "What problem are you
       trying to solve?" silently became whatever felt stuck that morning, and
       the summary they had just approved was gone.

       Nothing is lost by not saving: the Current Problem phase that this
       hand-off leads into asks for the symptom properly and persists it
       server-side, which is what the report's page 3 reads. */
    navigate('/app/founder-dna-journey');
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

