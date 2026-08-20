import { useMemo, useRef, useState } from 'react';
import { useApp } from '../context/AppContext';
import { useNavigate } from 'react-router-dom';
import { useCallAccess } from '../hooks/useCallAccess';
import Modal from '../components/Modal';
import { FEEDBACK, submitFeedback } from '../services/feedback';
import { ApiError } from '../services/api';

/* Answers are checked against what the code actually does, not what the product
   is meant to do eventually. Four of the originals were wrong -- the worst
   claimed Pro "unlocks unlimited diagnoses", while every tier including Pro is
   capped at diagnosis_lifetime_limit = 1 (backend/app/plans/catalog.py), and
   described a two-tier ladder when Starter exists. A support page that
   overstates a paid plan is worse than no support page. */
const FAQS = [
  {
    q: 'How do I start a diagnosis?',
    a: 'Click "New diagnosis" at the top right of any page — or "Start Founder Diagnosis" on your dashboard. Ally begins with Founder DNA (how you decide and work), then moves to your current problem, then the business itself.'
  },
  {
    q: 'How do plans work?',
    a: 'There are three: Free (₹0), Starter (₹450/month) and Pro (₹999/month). All three include the diagnosis, Founder DNA, Business DNA, reports and next steps. What changes is daily chat allowance (Free 4,000 tokens, Starter 6,000, Pro 8,000), free discovery calls per month (Free none, Starter 1, Pro 2), and voice inside Ally Chat plus Plan Your Day, which are paid features.'
  },
  {
    q: 'How many diagnoses do I get?',
    a: 'One full diagnosis per account, on every plan including Pro — it is a deep one-time mapping, not something to re-run weekly. Upgrading raises your chat allowance and calls, not the diagnosis count. If you genuinely need a second run, contact support and we will look at it case by case.'
  },
  {
    q: 'How do reminders work?',
    a: 'Tasks you set in Plan Your Day show up as "Next due", and Ally nudges you about anything overdue or due today while you are in the app. There are no push notifications or reminder emails yet, so Ally cannot reach you when the app is closed.'
  },
  {
    q: 'How do I upgrade?',
    a: 'Go to Profile, then the Subscription & billing card, and click "Upgrade plan".'
  },
  {
    q: 'Can I edit my Founder Profile?',
    a: 'Yes. Go to Profile, click "Edit" in the Founder Identity section, change your name, email or LinkedIn URL, and save.'
  },
  {
    q: 'Can I export or download my report?',
    a: 'Not yet from the report page — there is no download or share button there today. What you can do right now is export everything Ally holds about you, including your full diagnosis history, from Profile → Privacy Center → "Download my data". It arrives as a JSON file immediately.'
  },
  {
    q: 'What happens to my data, and can I delete it?',
    a: 'Profile → Privacy Center is the single place for this. You can download everything we hold, see a category-by-category summary, pause AI processing, withdraw consent, or request account deletion — which is scheduled with a 30-day recovery window before anything is permanently erased.'
  }
];

export default function HelpSupport() {
  const { showToast } = useApp();
  const navigate = useNavigate();
  const { canBook: canBookCall } = useCallAccess();
  const [openFaq, setOpenFaq] = useState(null);
  const [query, setQuery] = useState('');
  const [supportOpen, setSupportOpen] = useState(false);
  const [supportMsg, setSupportMsg] = useState('');
  const [sending, setSending] = useState(false);
  const faqRef = useRef(null);

  /* Every quick action used to call one handler that only showed a toast
     ending in a tick -- five buttons plus the primary "Email support" CTA, all
     of them inert, on the page a founder reaches precisely because they are
     already stuck. Each now does the thing its label promises. */

  const toggleFaq = (idx) => {
    setOpenFaq(prev => (prev === idx ? null : idx));
  };

  // The intro copy always said "search the answers below"; there was never a
  // search box. Matches every word separately across question AND answer text,
  // not the phrase as typed -- someone asking "delete my data" should land on
  // the privacy answer even though that exact phrase appears in neither its
  // question nor its wording. Phrase matching found nothing for that query.
  const filteredFaqs = useMemo(() => {
    const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (!words.length) return FAQS;
    return FAQS.filter(f => {
      const haystack = `${f.q} ${f.a}`.toLowerCase();
      return words.every(w => haystack.includes(w));
    });
  }, [query]);

  const scrollToFaqs = () => {
    // Honour reduced-motion: a long smooth scroll is exactly the kind of
    // unrequested movement that setting exists to suppress.
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    faqRef.current?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
  };

  const sendSupportMessage = async () => {
    const trimmed = supportMsg.trim();
    if (!trimmed || sending) return;
    setSending(true);
    try {
      // Same pipeline as the Feedback page: lands in founder_feedback and shows
      // up in the admin panel. Tagged so the team can tell a support request
      // apart from general feedback in that queue.
      await submitFeedback({ type: FEEDBACK.GENERAL, comment: `[Support request] ${trimmed}` });
      showToast('Sent — our team will get back to you by email.');
      setSupportMsg('');
      setSupportOpen(false);
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail : "Couldn't send that just now — your message is still here.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="dc-container" style={{ paddingBottom: '80px' }}>
      {/* Page Header */}
      <div className="hp-help-header stagger d1">
        <div className="hp-header-icon">
          <svg viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10" />
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        </div>
        <h2 className="hp-help-title">Need help?</h2>
        <p className="hp-help-subtitle">
          If you're facing any issue, our team is here to help. Search the
          answers below, or message us directly and we'll reply by email.
        </p>
      </div>

      {/* Panels Grid */}
      <div className="hp-grid stagger d2">
        {/* Left card */}
        <div className="hp-card">
          <div className="hp-card-head">
            <svg viewBox="0 0 24 24">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            Contact Support
          </div>

          <div className="hp-contact-rows">
            <div className="hp-contact-line">
              <span className="hp-contact-lbl">Email</span>
              {/* info@goxl.in, not support@goxl.ai: every other contact point in
                  the product (landing footer, 404, Terms, Privacy, Feedback)
                  already uses info@goxl.in, and goxl.ai is a different domain
                  from both goxl.in and goxlally.ai -- so this was the one link
                  pointing at a mailbox nothing else claims exists. */}
              <a href="mailto:info@goxl.in" className="hp-contact-val link">
                info@goxl.in
              </a>
            </div>
            {/* Phone row removed: it shipped as the literal placeholder
                "+91 XXXXX XXXXX", which on a support page reads as an abandoned
                product. Restore it as a real tel: link once there is a number
                someone actually answers -- an unanswered line is worse than
                none, since email already sets a 3-hour expectation below. */}
            <div className="hp-contact-line">
              <span className="hp-contact-lbl">Hours</span>
              <span className="hp-contact-val">Mon–Fri · 9 AM – 6 PM IST</span>
            </div>
          </div>

          {/* Was "Ally is online now · avg. reply under 3 hours" beside a green
              dot -- a hardcoded string, not a live status, which claimed
              someone was online at 3am Sunday and contradicted the Mon-Fri
              hours two lines above it. Stated as an aim now, with no fake
              presence indicator. */}
          <div className="hp-contact-footer">
            We aim to reply within one working day.
          </div>
        </div>

        {/* Right card */}
        <div className="hp-card">
          <div className="hp-card-head">
            <svg viewBox="0 0 24 24">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
            Quick Actions
          </div>

          <div className="hp-actions-grid">
            <button
              className="hp-action-btn"
              onClick={() => navigate('/app/feedback', { state: { topic: 'bug' } })}
              type="button"
            >
              <span className="hp-action-ic">
                <svg viewBox="0 0 24 24">
                  <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" />
                  <path d="M12 6v6l4 2" />
                </svg>
              </span>
              <span className="hp-action-lbl">Report a bug</span>
            </button>

            <button
              className="hp-action-btn"
              onClick={() => navigate('/app/feedback', { state: { topic: 'idea' } })}
              type="button"
            >
              <span className="hp-action-ic">
                <svg viewBox="0 0 24 24">
                  <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 14 18.465V19a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.535c0-.9.36-1.76.99-2.393l.553-.553z" />
                </svg>
              </span>
              <span className="hp-action-lbl">Request a feature</span>
            </button>

            <button
              className="hp-action-btn"
              onClick={() => setSupportOpen(true)}
              type="button"
            >
              <span className="hp-action-ic">
                <svg viewBox="0 0 24 24">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </span>
              <span className="hp-action-lbl">Contact support</span>
            </button>

            <button
              className="hp-action-btn"
              onClick={() => navigate('/app/discovery-call')}
              type="button"
            >
              <span className="hp-action-ic">
                <svg viewBox="0 0 24 24">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
              </span>
              <span className="hp-action-lbl">Schedule assistance</span>
            </button>

            <button
              className="hp-action-btn"
              style={{ gridColumn: '1 / -1' }}
              onClick={scrollToFaqs}
              type="button"
            >
              <span className="hp-action-ic">
                <svg viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              </span>
              <span className="hp-action-lbl">FAQs</span>
            </button>
          </div>
        </div>
      </div>

      {/* FAQs Section */}
      <h3 className="hp-faq-title-sec stagger d3" ref={faqRef}>Frequently asked questions</h3>

      <div className="hp-faq-search stagger d3">
        <label className="sr-only" htmlFor="hp-faq-search">Search the answers</label>
        <input
          id="hp-faq-search"
          type="search"
          className="hp-faq-search-input"
          placeholder="Search the answers…"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpenFaq(null); }}
        />
      </div>

      <div className="hp-faq-list stagger d3">
        {filteredFaqs.length === 0 && (
          <p className="hp-faq-empty">
            Nothing here matches “{query.trim()}”. Try fewer words, or message
            support above and a person will answer.
          </p>
        )}
        {/* Keyed by question text, not list index: once the list can be
            filtered, index 0 is a different question depending on the search,
            so index keys would leave the wrong row expanded. */}
        {filteredFaqs.map((faq, idx) => (
          <div
            key={faq.q}
            className={`hp-faq-row ${openFaq === faq.q ? 'open' : ''}`}
          >
            {/* The trigger announced no expanded/collapsed state, and the answer
                panel stayed in the DOM (hidden by CSS only) — so all six answers
                were read out continuously regardless of what was open. */}
            <button
              className="hp-faq-trigger"
              onClick={() => toggleFaq(faq.q)}
              type="button"
              id={`faq-trigger-${idx}`}
              aria-expanded={openFaq === faq.q}
              aria-controls={`faq-panel-${idx}`}
            >
              <span className="hp-faq-q">{faq.q}</span>
              <span className="hp-faq-chevron" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </span>
            </button>
            {/* `inert`, not `hidden`: the panel collapses via a max-height
                transition, and display:none would kill the animation. inert
                takes it out of the accessibility tree and the tab order while
                leaving it animatable. */}
            <div
              className="hp-faq-answer"
              id={`faq-panel-${idx}`}
              role="region"
              aria-labelledby={`faq-trigger-${idx}`}
              inert={openFaq !== faq.q}
            >
              <div className="hp-faq-answer-inner">{faq.a}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Footer Banner */}
      <div className="hp-footer-card stagger d4">
        <div className="hp-footer-info">
          <h4 className="hp-footer-title">Still need help?</h4>
          <p className="hp-footer-desc">
            Our founders' support team and Ally are one click away. Tell us what's
            happening and we'll get you unblocked.
          </p>
        </div>
        <div className="hp-footer-actions">
          <button
            className="hp-footer-btn-green"
            onClick={() => setSupportOpen(true)}
            type="button"
          >
            <svg viewBox="0 0 24 24">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
              <polyline points="22,6 12,13 2,6" />
            </svg>
            Message support
          </button>
          {/* A support page is the worst place to offer something they cannot
              have -- someone reaches it precisely because they are already
              stuck. */}
          {canBookCall && (
            <button
              className="hp-footer-btn-ghost"
              onClick={() => navigate('/app/discovery-call')}
              type="button"
            >
              <svg viewBox="0 0 24 24">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
              Book discovery call
            </button>
          )}
          <button
            className="hp-footer-btn-ghost"
            onClick={() => navigate('/app/ally-chat')}
            type="button"
          >
            <svg viewBox="0 0 24 24">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            Chat with Ally
          </button>
        </div>
      </div>

      {/* Posts through the same pipeline as the Feedback page rather than a
          mailto: handoff -- there is no server-side email sender configured
          yet, and a mailto: silently does nothing for anyone without a mail
          client set up, which is the exact failure this page existed to
          rescue people from. */}
      <Modal
        open={supportOpen}
        onClose={() => !sending && setSupportOpen(false)}
        title="Message support"
      >
        <p className="modal-sub">
          Tell us what's happening and we'll reply by email, usually within one
          working day. Your name and email come along automatically.
        </p>
        <label className="sr-only" htmlFor="hp-support-msg">Your message</label>
        <textarea
          id="hp-support-msg"
          className="modal-textarea"
          rows={5}
          placeholder="What's happening? Include what you expected and what you saw instead."
          value={supportMsg}
          disabled={sending}
          onChange={(e) => setSupportMsg(e.target.value)}
        />
        <div className="modal-actions">
          <button
            className="btn btn-ghost"
            type="button"
            onClick={() => setSupportOpen(false)}
            disabled={sending}
          >
            Cancel
          </button>
          <button
            className="btn btn-em"
            type="button"
            onClick={sendSupportMessage}
            disabled={!supportMsg.trim() || sending}
          >
            {sending ? 'Sending…' : 'Send message'}
          </button>
        </div>
      </Modal>
    </div>
  );
}
