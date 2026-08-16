import { useCallback, useEffect, useState } from 'react';
import { getLatestReport, getRecommendations } from '../services/reports';
import { DnaError, DnaLoading, DnaNoReport } from '../components/DnaState';
import { useNavigate } from 'react-router-dom';

/* Two hardcoded lists used to live here and both have been deleted, not just
   unhooked. ACTIONS was landing-page marketing copy that every founder saw as
   their own diagnosis output -- actions now come only from the report, see
   toActions. ROADMAP went the same way; see the note where its grid was
   rendered, below. */

function NextStepsView({ actions }) {
  const navigate = useNavigate();
  /* No static fallback. The deleted ACTIONS list was demo copy lifted from the
     landing page ("fix the 30-day churn cliff", "your 3 highest-LTV customer
     types") and every founder saw it: the loader read recommendations off
     `recs.recommendations`/`recs.items`, but the endpoint nests them under
     `section.facts`, so `actions` was ALWAYS empty and the fallback ALWAYS won.
     A D2C tea founder was told to instrument her week-two user drop-off.
     Generic advice presented as the output of someone's own diagnosis is worse
     than an empty state, so this now renders only what the report produced. */
  const items = (actions ?? []).map((a, i) => ({
    num: a.num ?? String(i + 1),
    title: a.title ?? a.heading ?? a.name ?? '',
    body: a.body ?? a.description ?? a.detail ?? a.rationale ?? '',
    ...a,
  }));

  return (
    <div className="fd-container">
      {/* Dark Forest Hero Banner */}
      <div className="fd-hero stagger d1">
        <div className="fd-hero-content">
          <div className="fd-hero-kicker">Next steps</div>
          {/* Was the literal "Three moves" -- only ever true because the list
              below was a hardcoded three. Real reports return however many
              actions the diagnosis produced (this founder's returned six), so
              the count comes from the data or the heading contradicts the page. */}
          <h2 className="fd-hero-title">
            {items.length === 1 ? 'One move' : `${items.length} moves`}, sequenced to compound.
          </h2>
          <p className="fd-hero-desc">
            Not a to-do list. The first move unlocks the second. Work top to
            bottom — Ally tracks momentum as you go.
          </p>
        </div>
      </div>

      {/* Priority Actions */}
      <div className="fd-section-head stagger d2" style={{ marginTop: 32 }}>
        <h3 className="fd-section-title">Priority actions</h3>
      </div>

      <div className="rep-act-list stagger d2">
        {items.map((act) => (
          <div key={act.num} className="rep-act-card" style={{ padding: '24px' }}>
            <div className="rep-act-num">{act.num}</div>
            <div className="rep-act-content">
              <p className="rep-act-text" style={{ fontSize: '14.5px', fontWeight: 500 }}>
                {act.text || act.title || act.body}
              </p>
              {act.tagLabel && (
                <span className={`rep-act-tag ${act.tag}`} style={{ marginTop: 8 }}>{act.tagLabel}</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* The "90-day roadmap" grid that sat here has been removed. It was three
          hardcoded phases -- "Instrument the week-two drop-off", "Interview 10
          churned users", "Redesign onboarding for top-LTV segment" -- rendered
          under the founder's own name with no data behind them, so every founder
          got an identical SaaS retention plan regardless of what their diagnosis
          actually said. Nothing in the report currently produces a phased
          roadmap, so there is nothing to bind it to; restore this section when
          the reasoning pipeline emits real phases, not before. The priority
          actions above ARE the founder's real sequenced output. */}

      {/* Book a session button at the bottom */}
      <div className="stagger d4" style={{ marginTop: 24 }}>
        <button
          onClick={() => navigate('/app/billing')}
          className="btn btn-primary"
          style={{
            background: '#10B981',
            color: '#06231a',
            fontWeight: 750,
            padding: '12px 20px',
            borderRadius: '10px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            boxShadow: '0 10px 24px -8px rgba(16, 185, 129, 0.4)'
          }}
          type="button"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            style={{ width: 16, height: 16 }}
          >
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          Book a session to pressure-test this plan
        </button>
      </div>
    </div>
  );
}


/**
 * Flatten GET /reports/:id/recommendations into the flat list the view renders.
 *
 * The endpoint returns a narrative *section* -- `{report_id, section:{key,
 * heading, prose, facts}}` -- and the actionable items live in
 * `facts.confirm_actions` / `facts.solve_actions`, each `{priority,
 * next_actions:[string]}`. The previous reader looked for `recommendations` or
 * `items` at the top level; neither has ever existed, so it always produced an
 * empty array and the page silently showed its hardcoded demo list instead.
 *
 * `solve_actions` first: a solve is something to change, a confirm is something
 * to verify, and the sequencing copy above ("the first move unlocks the second")
 * only reads true if the doing comes before the checking. Within each group the
 * server's `priority` is respected.
 */
function toActions(recs) {
  const facts = recs?.section?.facts;
  if (!facts) return [];
  const groups = [...(facts.solve_actions ?? []), ...(facts.confirm_actions ?? [])]
    .slice()
    .sort((a, b) => (a.priority ?? 99) - (b.priority ?? 99));
  return groups.flatMap((g) => g.next_actions ?? []).map((text) => ({ text }));
}

/**
 * Next steps come from the diagnosis recommendations, not a fixed list — they are
 * the output of the founder's own report. Without a report there is nothing
 * honest to recommend, so the page says so instead of showing generic advice.
 */
export default function NextSteps() {
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

  if (state.status === 'loading') return <DnaLoading label="Loading your next steps…" />;
  if (state.status === 'no-report') return <DnaNoReport kind="next steps" />;
  if (state.status === 'error') return <DnaError onRetry={load} />;
  return <NextStepsView actions={state.actions} />;
}
