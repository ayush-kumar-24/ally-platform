import { useState } from 'react';
import { useApp } from '../context/AppContext';
import { useNavigate } from 'react-router-dom';

const FAQS = [
  {
    q: 'How do I start a diagnosis?',
    a: 'Click "New diagnosis" in the top right corner of the dashboard to initialize a full diagnostic chat session. Ally will guide you through questions to evaluate your leadership archetype and operational priorities.'
  },
  {
    q: 'How do plans work?',
    a: 'We offer a Free plan with core diagnostics, and a Pro subscription that unlocks unlimited diagnoses, team sharing, document uploading/analysis, and direct access to GoXL advisors.'
  },
  {
    q: 'How do reminders work?',
    a: 'Your active tasks from the "Plan Your Day" dashboard generate upcoming indicators. Reminder alerts will trigger automatically at the set times to keep you accountable.'
  },
  {
    q: 'How do I upgrade?',
    a: 'To upgrade your account, go to the Profile section and click the "Upgrade plan" button under the Subscription details card.'
  },
  {
    q: 'Can I edit my Founder Profile?',
    a: 'Yes! Go to the Profile page, click "Edit" in the Founder Identity section, adjust your name, location, or social links, and click "Save" to apply changes.'
  },
  {
    q: 'Can I export reports?',
    a: 'Absolutely. On the Executive Report page, you will find action buttons to "Download PDF" or "Share" your diagnostic results instantly.'
  }
];

export default function HelpSupport() {
  const { showToast } = useApp();
  const navigate = useNavigate();
  const [openFaq, setOpenFaq] = useState(null);

  const toggleFaq = (idx) => {
    setOpenFaq(prev => (prev === idx ? null : idx));
  };

  const handleAction = (act) => {
    showToast(`Quick action triggered: ${act} ✓`);
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
          If you're facing any issue, our team is here to help — usually within a
          few hours. Search the answers below or reach us directly.
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
              <a href="mailto:support@goxl.ai" className="hp-contact-val link">
                support@goxl.ai
              </a>
            </div>
            <div className="hp-contact-line">
              <span className="hp-contact-lbl">Phone</span>
              <span className="hp-contact-val">+91 XXXXX XXXXX</span>
            </div>
            <div className="hp-contact-line">
              <span className="hp-contact-lbl">Hours</span>
              <span className="hp-contact-val">Mon–Fri · 9 AM – 6 PM IST</span>
            </div>
          </div>

          <div className="hp-contact-footer">
            <span className="dot" />
            Ally is online now · avg. reply under 3 hours
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
              onClick={() => handleAction('Report a bug')}
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
              onClick={() => handleAction('Request a feature')}
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
              onClick={() => handleAction('Contact support')}
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
              onClick={() => handleAction('Schedule assistance')}
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
              onClick={() => handleAction('View FAQs')}
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
      <h3 className="hp-faq-title-sec stagger d3">Frequently asked questions</h3>
      <div className="hp-faq-list stagger d3">
        {FAQS.map((faq, idx) => (
          <div
            key={idx}
            className={`hp-faq-row ${openFaq === idx ? 'open' : ''}`}
          >
            <button
              className="hp-faq-trigger"
              onClick={() => toggleFaq(idx)}
              type="button"
            >
              <span className="hp-faq-q">{faq.q}</span>
              <span className="hp-faq-chevron">
                <svg viewBox="0 0 24 24">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </span>
            </button>
            <div className="hp-faq-answer">
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
            onClick={() => handleAction('Email Support')}
            type="button"
          >
            <svg viewBox="0 0 24 24">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
              <polyline points="22,6 12,13 2,6" />
            </svg>
            Email support
          </button>
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
    </div>
  );
}
