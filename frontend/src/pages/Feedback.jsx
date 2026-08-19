import { useState } from 'react';
import { useApp } from '../context/AppContext';
import FeedbackPrompt from '../components/FeedbackPrompt';
import { FEEDBACK, submitFeedback } from '../services/feedback';
import { ApiError } from '../services/api';

/**
 * The feedback section, as its own page in the sidebar.
 *
 * Both things on this page now post to the same backend endpoint and land in
 * the same founder_feedback table, visible to the team from the admin panel:
 *
 *  - The written note (this page's form) used to be FRONTEND-ONLY -- it built
 *    a mailto: link and handed off to the founder's own mail client. That
 *    silently did nothing for anyone without one configured, or who didn't
 *    personally press send once it opened. It now posts here instead
 *    (feedback_type="general", no rating), same as the star rating below.
 *
 *  - The star rating (the modal below) already posted to the backend via the
 *    existing /feedback endpoint -- unchanged.
 */

const TOPICS = [
  { id: 'bug', label: 'Something is broken' },
  { id: 'idea', label: 'I have an idea' },
  { id: 'confusing', label: 'Something confused me' },
  { id: 'praise', label: 'Something worked well' },
  { id: 'other', label: 'Something else' },
];

const TOPIC_LABEL = Object.fromEntries(TOPICS.map((t) => [t.id, t.label]));

export default function Feedback() {
  const { showToast } = useApp();
  const [topic, setTopic] = useState('idea');
  const [message, setMessage] = useState('');
  const [ratingOpen, setRatingOpen] = useState(false);
  const [sending, setSending] = useState(false);

  const canSend = message.trim().length > 0 && !sending;

  const send = async () => {
    const trimmed = message.trim();
    if (!trimmed || sending) return;

    // Topic has no column of its own on founder_feedback -- folded into the
    // comment as a prefix so the admin panel shows it without a schema change.
    const comment = `[${TOPIC_LABEL[topic]}] ${trimmed}`;

    setSending(true);
    try {
      await submitFeedback({ type: FEEDBACK.GENERAL, comment });
      showToast('Feedback sent — thank you, we read every one of these.');
      setMessage('');
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail : 'Could not send that just now — please try again.');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="dc-container" style={{ paddingBottom: '80px' }}>
      <div className="hp-help-header stagger d1">
        <div className="hp-header-icon">
          <svg viewBox="0 0 24 24">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </div>
        <h2 className="hp-help-title">Tell us what you think</h2>
        <p className="hp-help-subtitle">
          Ally is early, and the sharp edges are easier for you to see than for us.
          If something is broken, confusing, or missing — tell us plainly. We read
          every one of these.
        </p>
      </div>

      <div className="fb-page-grid stagger d2">
        <div className="hp-card">
          <div className="hp-card-head">
            <svg viewBox="0 0 24 24">
              <path d="M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" />
              <path d="m22 6-10 7L2 6" />
            </svg>
            Send us a note
          </div>

          <div className="fb-topics" role="group" aria-label="What is this about?">
            {TOPICS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`fb-topic${topic === t.id ? ' on' : ''}`}
                aria-pressed={topic === t.id}
                onClick={() => setTopic(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <label className="sr-only" htmlFor="fb-page-message">Your feedback</label>
          <textarea
            id="fb-page-message"
            className="fb-textarea"
            rows={7}
            placeholder="What happened, what you expected, or what you'd like to see…"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
          />

          <div className="fb-send-row">
            <span className="fb-send-note">
              Goes straight to our team — no mail app required
            </span>
            <button className="btn btn-em" type="button" onClick={send} disabled={!canSend}>
              {sending ? 'Sending…' : 'Send feedback'}
            </button>
          </div>
        </div>

        <div className="hp-card">
          <div className="hp-card-head">
            <svg viewBox="0 0 24 24">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
            Rate your experience
          </div>

          <p className="fb-aside-copy">
            Short on time? Leave a rating instead — it takes a few seconds and still
            tells us whether we're heading the right way.
          </p>

          <button className="btn btn-ghost fb-rate-btn" type="button" onClick={() => setRatingOpen(true)}>
            Rate Ally
          </button>

          <div className="fb-aside-divider" />

          <p className="fb-aside-copy small">
            Need an answer rather than a suggestion box? The{' '}
            <a className="hp-contact-val link" href="/app/help">Help &amp; Support</a>{' '}
            page has our direct contact details and the questions we get asked most.
          </p>
        </div>
      </div>

      <FeedbackPrompt
        type={FEEDBACK.GENERAL}
        when={ratingOpen}
        dedupe={false}
        onResolved={() => setRatingOpen(false)}
        title="How's Ally working for you?"
        subtitle="Anything at all — what's useful, what isn't, what's missing."
      />
    </div>
  );
}
