import { useEffect, useRef, useState } from 'react';
import { useApp } from '../context/AppContext';
import { markTourSeen } from '../services/dashboard';

const TOUR_STEPS = [
  { nav: '/app/ally-chat', emoji: '💬', title: 'Chat with Ally', text: 'Ask questions, brainstorm ideas and make better decisions with Ally anytime.' },
  { nav: '/app/plan', emoji: '📅', title: 'Plan Your Day', text: 'Create your daily goals manually or with Ally — with reminders and preparation support.' },
  { nav: '/app/founder-dna', emoji: '🧠', title: 'Founder DNA', text: 'Understand your decision-making patterns and leadership style.' },
  { nav: '/app/business-dna', emoji: '🏢', title: 'Business DNA', text: 'See how Ally understands your business and identifies patterns.' },
  { nav: '/app/report', emoji: '📄', title: 'Reports', text: 'Access all your previous Founder Clarity Reports anytime.' },
  { nav: '/app/discovery-call', emoji: '📞', title: 'Discovery Call', text: 'When you’re ready, connect with a GoXL advisor.' },
  { final: true, emoji: '✨', title: 'You’re all set.', text: 'Ally is now your daily strategic partner.' },
];

export default function ProductTour() {
  const { tourOpen, endTour, sidebarCollapsed, toggleSidebar, sidebarOpen, openSidebar, closeSidebar } = useApp();
  const [stepIndex, setStepIndex] = useState(0);
  const [spotStyle, setSpotStyle] = useState({ opacity: 0 });
  const [popStyle, setPopStyle] = useState({});
  const [popShow, setPopShow] = useState(false);
  const restoreRef = useRef({ collapsed: false, wasOpen: false });
  const reduceRef = useRef(false);

  useEffect(() => {
    reduceRef.current = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }, []);

  // start/reset when opened
  useEffect(() => {
    if (!tourOpen) return;
    setStepIndex(0);
    setPopShow(false);

    const mobile = window.innerWidth <= 767;
    restoreRef.current = { collapsed: sidebarCollapsed, wasOpen: sidebarOpen };
    if (mobile) {
      openSidebar();
    } else if (sidebarCollapsed) {
      toggleSidebar();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tourOpen]);

  const position = () => {
    const step = TOUR_STEPS[stepIndex];
    if (!step || step.final) return;
    const target = document.querySelector(`[data-nav="${step.nav}"]`);
    const pop = document.getElementById('tourPop');
    if (!target) {
      setSpotStyle((s) => ({ ...s, opacity: 0 }));
      return;
    }
    const r = target.getBoundingClientRect();
    const pd = 8;
    setSpotStyle({
      opacity: 1,
      left: r.left - pd,
      top: r.top - pd,
      width: r.width + pd * 2,
      height: r.height + pd * 2,
    });
    const pw = pop?.offsetWidth || 304;
    const ph = pop?.offsetHeight || 170;
    const gap = 16;
    let left = r.right + gap;
    let top = r.top + r.height / 2 - ph / 2;
    if (left + pw > window.innerWidth - 12) {
      left = r.left;
      top = r.bottom + gap;
    }
    left = Math.max(12, Math.min(left, window.innerWidth - pw - 12));
    top = Math.max(12, Math.min(top, window.innerHeight - ph - 12));
    setPopStyle({ transform: 'none', left, top });
  };

  // (re)render current step
  useEffect(() => {
    if (!tourOpen) return;
    const step = TOUR_STEPS[stepIndex];
    if (!step) return;
    setPopShow(false);
    if (step.final) {
      setSpotStyle((s) => ({ ...s, opacity: 0 }));
      setPopStyle({});
      if (reduceRef.current) setPopShow(true);
      else requestAnimationFrame(() => setPopShow(true));
      return;
    }
    position();
    if (reduceRef.current) setPopShow(true);
    else requestAnimationFrame(() => setPopShow(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tourOpen, stepIndex]);

  // keep the spotlight anchored while the sidebar expand/collapse transition settles, and on resize
  useEffect(() => {
    if (!tourOpen) return;
    window.addEventListener('resize', position);
    let iv;
    if (!reduceRef.current) {
      let reps = 0;
      iv = setInterval(() => {
        position();
        if (++reps >= 9) clearInterval(iv);
      }, 70);
    }
    return () => {
      window.removeEventListener('resize', position);
      if (iv) clearInterval(iv);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tourOpen, stepIndex]);

  const finish = () => {
    const { collapsed, wasOpen } = restoreRef.current;
    if (!wasOpen) closeSidebar();
    if (collapsed && !sidebarCollapsed) toggleSidebar();
    // Tell the server it has been seen -- whether they finished it or skipped
    // it, they have been offered it and should not be offered it again. This
    // call is why founders.tour_seen_at exists; nothing had ever made it.
    markTourSeen();
    endTour();
  };

  useEffect(() => {
    if (!tourOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape') finish();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tourOpen]);

  if (!tourOpen) return null;

  const step = TOUR_STEPS[stepIndex];
  const isLast = stepIndex >= TOUR_STEPS.length - 1;
  const handleNext = () => {
    if (isLast) finish();
    else setStepIndex((i) => i + 1);
  };

  return (
    <div className="tour on" aria-hidden="false">
      <div className="tour-spot" style={spotStyle} />
      <div
        id="tourPop"
        className={`tour-pop${popShow ? ' show' : ''}${step.final ? ' center' : ''}`}
        style={step.final ? {} : popStyle}
        role="dialog"
        aria-modal="true"
        aria-label="Product tour"
      >
        <div className="tp-emoji">{step.emoji}</div>
        <div className="tp-t">{step.title}</div>
        <div className="tp-x">{step.text}</div>
        <div className="tp-foot">
          <div className="tp-dots">
            {TOUR_STEPS.map((_, i) => (
              <i key={i} className={i === stepIndex ? 'on' : ''} />
            ))}
          </div>
          <div className="tp-btns">
            {!step.final && (
              <button className="tp-skip" type="button" onClick={finish}>
                Skip
              </button>
            )}
            <button className="tp-next" type="button" onClick={handleNext}>
              {isLast ? 'Start Exploring' : (
                <>
                  Next
                  <svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
