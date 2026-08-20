import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getLatestReport, getRecommendations } from '../services/reports';
import { DnaError, DnaLoading } from '../components/DnaState';
import { IconChat, IconLock } from '../utils/icons';

/**
 * Recommendations — Ally's synthesized next moves, from the real diagnosis.
 *
 * Unlike Vision/Goals/Achievements, nothing here is founder-authored: these
 * come only from the report's recommendations endpoint. Same parsing as
 * NextSteps.jsx's toActions (duplicated rather than imported -- NextSteps
 * doesn't export it either, and the two pages are allowed to read the same
 * report differently without being coupled to each other).
 *
 * The reference mockup's cards also show per-item tags ("Diagnosis · 92%",
 * "Retention · 64") and a synthesis line naming vision/energy/goals as
 * inputs. Neither is real: /reports/:id/recommendations returns plain
 * action strings, no per-action scores or source dimensions, and nothing
 * on the backend actually reads Vision or Goals when generating these yet.
 * Shown here is only what the endpoint actually returns.
 */
function toActions(recs) {
  const facts = recs?.section?.facts;
  if (!facts) return [];
  const groups = [...(facts.solve_actions ?? []), ...(facts.confirm_actions ?? [])]
    .slice()
    .sort((a, b) => (a.priority ?? 99) - (b.priority ?? 99));
  return groups.flatMap((g) => g.next_actions ?? []);
}

export default function RecommendationsPage() {
  const navigate = useNavigate();
  const [state, setState] = useState({ status: 'loading' });

  const load = useCallback(() => {
    setState({ status: 'loading' });
    getLatestReport()
      .then(async (latest) => {
        if (!latest) return setState({ status: 'no-report' });
        const recs = await getRecommendations(latest.report_id).catch(() => null);
        setState({ status: 'ready', actions: toActions(recs) });
      })
      .catch((error) => setState({ status: 'error', error }));
  }, []);

  useEffect(load, [load]);

  const discuss = (text) => {
    navigate('/app/ally-chat', {
      state: { prefill: `Let's talk through this recommendation: "${text}"` },
    });
  };

  return (
    <div className="rcm-page">
      <section className="rcm-hero">
        <div className="rcm-kicker">Ally Recommendations</div>
        <h1>What to do next — after reading the whole picture.</h1>
        <p>Synthesized from your diagnosis, Founder DNA and Business DNA.</p>
      </section>

      {state.status === 'loading' && <DnaLoading label="Pulling your recommendations…" />}
      {state.status === 'error' && <DnaError onRetry={load} />}

      {state.status === 'no-report' && (
        <section className="rcm-locked">
          <div className="rcm-locked-ic"><IconLock /></div>
          <h2>Complete your diagnosis to open this section</h2>
          <p>
            Recommendations are synthesized from your diagnosis, Founder DNA and Business
            DNA — there's nothing for Ally to work from until you've run one.
          </p>
          <button type="button" className="btn btn-em" onClick={() => navigate('/app/founder-dna-journey')}>
            Start Founder Diagnosis
          </button>
        </section>
      )}

      {state.status === 'ready' && (
        state.actions.length === 0 ? (
          <div className="rcm-empty">
            <p>Your latest report didn't produce any recommendations to show here.</p>
          </div>
        ) : (
          <ol className="rcm-list">
            {state.actions.map((text, i) => (
              <li key={i} className="rcm-item">
                <span className="rcm-num">{String(i + 1).padStart(2, '0')}</span>
                <div className="rcm-body">
                  <p>{text}</p>
                  <button type="button" className="btn btn-em rcm-discuss" onClick={() => discuss(text)}>
                    <IconChat /> Discuss
                  </button>
                </div>
              </li>
            ))}
          </ol>
        )
      )}
    </div>
  );
}
