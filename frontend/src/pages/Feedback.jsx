import { useState } from 'react';
import { useApp } from '../context/AppContext';
import FeedbackPrompt from '../components/FeedbackPrompt';
import { FEEDBACK } from '../services/feedback';

/**
 * The feedback section, as its own page in the sidebar.
 *
 * Two different things live here, deliberately kept apart:
 *
 *  - The written note (this page's form) is FRONTEND-ONLY. There is no
 *    feedback-inbox endpoint to post to, so rather than swallow a founder's
 *    words into a form that goes nowhere, it builds a mailto: link and hands
 *    off to their own mail client. Every word lands in our inbox exactly as
 *    typed, with no server piece to build or keep running. The tradeoff is
 *    real and worth naming: it needs a mail client configured, and it needs
 *    them to press send once it opens.
 *
 *  - The star rating (the modal below) DOES post to the backend, via the
 *    existing /feedback endpoint. That one is a number we can aggregate;
 *    this page's note is prose we want to actually read.
 */

// Where a founder's typed-in feedback goes.
const FEEDBACK_EMAIL = 'info@goxl.in';

const TOPICS = [
  { id: 'bug', label: 'Something is broken' },
  { id: 'idea', label: 'I have an idea' },
  { id: 'confusing', label: 'Something confused me' },
  { id: 'praise', label: 'Something worked well' },
  { id: 'other', label: 'Something else' },
];

const TOPIC_LABEL = Object.fromEntries(TOPICS.map((t) => [t.id, t.label]));

export default function Feedback() {
  const { user, showToast } = useApp();
  const [topic, setTopic] = useState('idea');
  const [message, setMessage] = useState('');
  const [ratingOpen, setRatingOpen] = useState(false);

  const canSend = message.trim().length > 0;

  const send = () => {
    const trimmed = message.trim();
    if (!trimmed) return;

    const name = user?.name || '';
    const email = user?.email || '';

    const subject = `Ally feedback · ${TOPIC_LABEL[topic]}${name ? ` · ${name}` : ''}`;
    const body = [
      trimmed,
      '',
      '---',
      `Topic: ${TOPIC_LABEL[topic]}`,
      email ? `From: ${name || 'A founder'} <${email}>` : `From: ${name || 'A founder'}`,
      `Page: ${window.location.origin}`,
    ].join('\n');

    // A real navigation, not window.open -- mail-client handoff wants the same
    // tab; window.open just leaves a blank one behind.
    window.location.href =
      `mailto:${FEEDBACK_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

    showToast('Opening your mail app with this ready to send.');
    setMessage('');
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
            {/* Said plainly rather than discovered after clicking -- a button
                that hijacks you into Outlook without warning is a small
                betrayal. */}
            <span className="fb-send-note">
              Opens your mail app, addressed to {FEEDBACK_EMAIL}
            </span>
            <button className="btn btn-em" type="button" onClick={send} disabled={!canSend}>
              Send feedback
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
