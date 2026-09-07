/**
 * What founders tell us — and what we could not tell them.
 *
 * WHY THIS PAGE EXISTS. `founder_feedback` collects every bug report, support
 * message, idea and star rating in the product, and `GET /admin/founder-feedback`
 * has existed to read it back — with nothing in the UI calling it. So the table
 * filled up and nobody could see it, while Help & Support toasted "our team will
 * get back to you by email" and the Feedback page said "we read every one of
 * these". Both were untrue. This page is the half that makes them true.
 *
 * TWO TABS, BECAUSE THEY ARE TWO JOBS.
 *
 *   Messages    — someone is waiting on a reply. Read in order, answer people.
 *   Unanswered  — questions the help bot missed, grouped and counted. Not a
 *                 queue at all: it is the backlog of help answers worth writing,
 *                 and the count is the priority order. These used to be thrown
 *                 away without even a log line.
 *
 * SUPPORT REQUESTS ARE SORTED FIRST. Anything sent from Help & Support or the
 * widget is tagged `[Support request]` by the client. That tag is the difference
 * between "shared an idea" and "is stuck right now", so it leads — a five-star
 * rating should never push a payment problem down the page.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import {
  can, founderFeedbackStats, listFounderFeedback, listSupportMisses,
} from '../../services/admin';
import { EmptyState, ErrorState, Loading } from './AdminUI';

const CAPABILITY = 'view_users';

/** The tag the client puts on anything sent from a support box. */
const SUPPORT_TAG = '[Support request]';

const TYPE_LABELS = {
  general: 'General',
  report_rating: 'Report rating',
  diagnosis_rating: 'Diagnosis rating',
  recommendation_helpful: 'Recommendation',
  outcome_30day: '30-day outcome',
  outcome_60day: '60-day outcome',
  outcome_90day: '90-day outcome',
};

function whenLabel(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-IN', {
    day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', hour12: true,
  });
}

/** Filled and empty stars, so a rating reads at a glance rather than as a digit. */
function Stars({ n }) {
  if (!n) return <span className="adm-dim">—</span>;
  return (
    <span title={`${n} out of 5`} aria-label={`${n} out of 5`}>
      {'★'.repeat(n)}<span className="adm-dim">{'☆'.repeat(5 - n)}</span>
    </span>
  );
}

export default function AdminFeedback() {
  const { me } = useOutletContext();
  const allowed = can(me, CAPABILITY);

  const [tab, setTab] = useState('messages');
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState(null);
  const [misses, setMisses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [withWordsOnly, setWithWordsOnly] = useState(true);

  const load = useCallback(() => {
    if (!allowed) { setLoading(false); return; }
    setLoading(true);
    setError(null);
    // Both tabs load together: they are small reads, and switching tabs after
    // a round trip each makes the page feel like it is fetching twice.
    Promise.all([
      listFounderFeedback({ limit: 200 }),
      founderFeedbackStats(),
      listSupportMisses({ limit: 200 }),
    ])
      .then(([fb, st, ms]) => {
        setRows(Array.isArray(fb?.items) ? fb.items : []);
        setStats(st || null);
        setMisses(Array.isArray(ms?.items) ? ms.items : []);
      })
      .catch(setError)
      .finally(() => setLoading(false));
  }, [allowed]);

  useEffect(load, [load]);

  const messages = useMemo(() => {
    const isSupport = (r) => (r.comment || '').startsWith(SUPPORT_TAG);
    return rows
      .filter((r) => (withWordsOnly ? Boolean((r.comment || '').trim()) : true))
      .sort((a, b) =>
        (isSupport(b) ? 1 : 0) - (isSupport(a) ? 1 : 0) ||
        new Date(b.collected_at) - new Date(a.collected_at));
  }, [rows, withWordsOnly]);

  const waitingCount = useMemo(
    () => rows.filter((r) => (r.comment || '').startsWith(SUPPORT_TAG)).length,
    [rows]);

  if (!allowed) {
    return (
      <section>
        <h1 className="adm-h1">Feedback</h1>
        <EmptyState
          title="You do not have access to this"
          hint="Reading founder feedback needs the users permission. Ask a super admin to add it."
        />
      </section>
    );
  }

  return (
    <section>
      <h1 className="adm-h1">Feedback &amp; support</h1>
      <p className="adm-sub">
        Everything founders write to us. Anyone who used Help &amp; Support was told
        &ldquo;our team will get back to you by email&rdquo; — those are marked
        <strong> Support</strong> and come first.
      </p>

      <div className="adm-panel">
        <div className="adm-filters">
          <button
            className={`adm-btn${tab === 'messages' ? ' adm-btn--primary' : ''}`}
            type="button"
            onClick={() => setTab('messages')}
          >
            Messages &amp; ratings{waitingCount ? ` (${waitingCount} support)` : ''}
          </button>
          <button
            className={`adm-btn${tab === 'misses' ? ' adm-btn--primary' : ''}`}
            type="button"
            onClick={() => setTab('misses')}
          >
            Unanswered questions{misses.length ? ` (${misses.length})` : ''}
          </button>
          <button className="adm-btn" type="button" onClick={load} disabled={loading}>
            Refresh
          </button>
        </div>

        {loading && <Loading label="Loading feedback…" />}
        {error && !loading && <ErrorState error={error} onRetry={load} />}

        {/* ---- messages & ratings ---- */}
        {!loading && !error && tab === 'messages' && (
          <>
            {stats && (
              <p className="adm-dim" style={{ margin: '0 0 12px' }}>
                {stats.total} total · {stats.rated_count} rated ·
                {' '}average {stats.average_rating ? stats.average_rating.toFixed(1) : '—'}/5
              </p>
            )}
            <label className="adm-check" style={{ marginBottom: 12, display: 'inline-flex' }}>
              <input
                type="checkbox"
                checked={withWordsOnly}
                onChange={(e) => setWithWordsOnly(e.target.checked)}
              />
              Only the ones where someone wrote something
            </label>

            {messages.length === 0 ? (
              <EmptyState
                title={withWordsOnly ? 'Nothing written yet' : 'No feedback yet'}
                hint={withWordsOnly
                  ? 'Star ratings with no comment are hidden. Untick the box to include them.'
                  : 'When a founder rates something or writes to us it will appear here.'}
              />
            ) : (
              <div className="adm-table-wrap">
                <table className="adm-table">
                  <thead>
                    <tr>
                      <th>From</th>
                      <th>What they said</th>
                      <th>Rating</th>
                      <th>When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {messages.map((f) => {
                      const support = (f.comment || '').startsWith(SUPPORT_TAG);
                      const body = support
                        ? f.comment.slice(SUPPORT_TAG.length).trim()
                        : f.comment;
                      return (
                        <tr key={f.feedback_id}>
                          <td>
                            <Link to={`/admin/users/${f.founder_id}`}>
                              {f.founder_name || `Founder ${f.founder_id}`}
                            </Link>
                            {/* The address, plainly, because answering these
                                means writing back and nothing here does it for
                                you. */}
                            <div className="adm-mono adm-dim">{f.founder_email || '—'}</div>
                            {support && <span className="adm-tag">Support</span>}
                          </td>
                          <td className="adm-wrap">
                            {body || <span className="adm-dim">No words — rating only</span>}
                            <div className="adm-dim" style={{ marginTop: 4 }}>
                              {TYPE_LABELS[f.feedback_type] || f.feedback_type}
                            </div>
                          </td>
                          <td><Stars n={f.rating} /></td>
                          <td className="adm-dim">{whenLabel(f.collected_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {/* ---- unanswered bot questions ---- */}
        {!loading && !error && tab === 'misses' && (
          <>
            <p className="adm-dim" style={{ margin: '0 0 12px' }}>
              Questions founders asked the help bot that our help content does not
              answer, grouped and counted. The top of this list is the answer worth
              writing next.
            </p>
            {misses.length === 0 ? (
              <EmptyState
                title="Nothing missed yet"
                hint="Either the help content is covering what founders ask, or nobody has asked since this started being recorded."
              />
            ) : (
              <div className="adm-table-wrap">
                <table className="adm-table">
                  <thead>
                    <tr>
                      <th>Question</th>
                      <th>Asked</th>
                      <th>Founders</th>
                      <th>Last asked</th>
                    </tr>
                  </thead>
                  <tbody>
                    {misses.map((m) => (
                      <tr key={`${m.question}-${m.last_asked}`}>
                        <td className="adm-wrap">{m.question}</td>
                        <td>
                          {/* Bolded past two, where it stops being one person's
                              odd phrasing and starts being a gap. */}
                          <strong>{m.times_asked}×</strong>
                        </td>
                        <td>{m.founders}</td>
                        <td className="adm-dim">{whenLabel(m.last_asked)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
