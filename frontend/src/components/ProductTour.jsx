import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { getOverview, markTourSeen } from '../services/dashboard';
import { useCallAccess } from '../hooks/useCallAccess';

/* The tour runs once the diagnosis is done, so it is the first time a founder
   sees the whole product rather than the one screen they were sent to. It now
   walks every section the sidebar offers, in the order the work actually flows
   after a diagnosis -- what Ally found, what to do about it, the tools for
   doing it, then the account -- rather than the order the nav happens to list
   them in.

   Steps are filtered per founder before use -- see `steps` below. A step whose
   sidebar item is hidden has nothing to spotlight: position() looks up
   [data-nav="..."] and would find nothing, leaving the highlight stranded over
   a tour stop the founder cannot visit anyway.

   `needsReport` and `comingSoon` mirror the same flags in PlatformLayout's
   NAV_GROUPS. They are repeated rather than imported because the two lists
   answer different questions -- the nav asks what to LOCK, the tour asks what
   is worth INTRODUCING -- and a locked item is a worse tour stop than no stop
   at all: it advertises a door that does not open yet. */
const TOUR_STEPS = [
  // Where the diagnosis lands.
  { nav: '/app', emoji: '🧭', title: 'Your dashboard', text: 'Where you land each time — your current read, what changed, and what Ally suggests next.' },
  { nav: '/app/report', emoji: '📄', title: 'Your Clarity Report', text: 'The full diagnosis: your root cause, the evidence behind it, and your three steps. Every report you ever run is kept here.', needsReport: true },

  // What it found.
  { nav: '/app/founder-dna', emoji: '🧠', title: 'Founder DNA', text: 'How you decide, what drives you, and where your blind spots sit — read from your own answers, not a quiz.', needsReport: true },
  { nav: '/app/business-dna', emoji: '🏢', title: 'Business DNA', text: 'Where the business stands across the six pillars, and which one is deciding your next few months.', needsReport: true },

  // What to do about it.
  { nav: '/app/recommendations', emoji: '💡', title: 'Recommendations', text: 'The specific moves Ally suggests for your diagnosis, with the reasoning attached.', needsReport: true },
  { nav: '/app/next-steps', emoji: '➡️', title: 'Next steps', text: 'Your plan in order — what to confirm first, what to fix after, and why that sequence.', needsReport: true },

  // The tools for doing it.
  { nav: '/app/ally-chat', emoji: '💬', title: 'Chat with Ally', text: 'Think out loud any time. Ally already knows your diagnosis, so you never start from scratch.' },
  { nav: '/app/plan', emoji: '📅', title: 'Plan Your Day', text: 'Set today’s priorities yourself or let Ally draft them, then get reminders to stay on them.' },
  { nav: '/app/goals', emoji: '🎯', title: 'Goals', text: 'The bigger arcs you are working toward, tracked beyond a single day.' },
  { nav: '/app/vision', emoji: '👁️', title: 'Your Vision', text: 'Where you want this to end up, in your words. Ally reads it when it advises you.' },
  { nav: '/app/frameworks', emoji: '📚', title: 'Frameworks', text: 'Practical models to reach for when you are stuck on a decision.' },
  { nav: '/app/founder-dna-journey', emoji: '🔄', title: 'Run it again', text: 'Come back and re-run the diagnosis once your steps are done — that is when the picture actually moves.' },
  { nav: '/app/discovery-call', emoji: '📞', title: 'Discovery call', text: 'When you want a person in the room, book a short call with a GoXL advisor.' },

  /* One stop, three items. Profile, Help and Send feedback each took their own
     step, which pushed a founder with a report to sixteen -- long enough that
     the last few stops are skipped rather than read. They sit next to each
     other at the bottom of the nav and none of them needs its own explanation,
     so `navs` highlights all three at once and one sentence covers them. */
  {
    navs: ['/app/feedback', '/app/profile', '/app/help'],
    emoji: '⚙️',
    title: 'Your account',
    text: 'Down here: your profile — keep the stage current and Ally’s advice stays aimed at where you actually are — plus Help & Support, where you can replay this tour, and Send feedback, which we read.',
  },

  { final: true, emoji: '✨', title: 'You’re all set.', text: 'Ally is now your daily strategic partner.' },
];

export default function ProductTour() {
  const navigate = useNavigate();
  const { tourOpen, endTour, sidebarCollapsed, toggleSidebar, sidebarOpen, openSidebar, closeSidebar } = useApp();
  const { canBook: canBookCall } = useCallAccess();

  /* Same signal PlatformLayout locks the nav on, read the same way. The tour
     normally opens straight after a diagnosis, so a report exists and none of
     these are skipped -- but it can also be replayed later from Help, and a
     founder whose report has not landed would otherwise be walked past four
     doors that do not open. Defaults to true so a slow or failed lookup shows
     the full tour rather than silently hiding half the product. */
  const [hasReport, setHasReport] = useState(true);
  useEffect(() => {
    if (!tourOpen) return;
    let cancelled = false;
    getOverview()
      .then((o) => { if (!cancelled && o) setHasReport(Boolean(o.latest_diagnosis?.available)); })
      .catch(() => { /* keep the default: show everything */ });
    return () => { cancelled = true; };
  }, [tourOpen]);

  const steps = useMemo(
    () => TOUR_STEPS.filter((s) => {
      if (s.comingSoon) return false;
      if (s.needsReport && !hasReport) return false;
      if (s.nav === '/app/discovery-call' && !canBookCall) return false;
      return true;
    }),
    [canBookCall, hasReport],
  );
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

  /* Every element a step points at. A step normally names one, but the account
     stop covers three adjacent nav items and highlighting all of them together
     is what makes it a real introduction rather than a single spotlight with a
     list read out beside it. */
  const targetsFor = (step) => (step?.navs || (step?.nav ? [step.nav] : []))
    .map((n) => document.querySelector(`[data-nav="${n}"]`))
    .filter(Boolean);

  const position = () => {
    const step = steps[stepIndex];
    if (!step || step.final) return;
    const targets = targetsFor(step);
    const pop = document.getElementById('tourPop');
    if (!targets.length) {
      setSpotStyle((s) => ({ ...s, opacity: 0 }));
      return;
    }
    // Union of every target, so a multi-item stop gets one box around the lot.
    const boxes = targets.map((t) => t.getBoundingClientRect());
    const r = {
      left: Math.min(...boxes.map((b) => b.left)),
      top: Math.min(...boxes.map((b) => b.top)),
      right: Math.max(...boxes.map((b) => b.right)),
      bottom: Math.max(...boxes.map((b) => b.bottom)),
    };
    r.width = r.right - r.left;
    r.height = r.bottom - r.top;
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
    const step = steps[stepIndex];
    if (!step) return;
    setPopShow(false);
    if (step.final) {
      setSpotStyle((s) => ({ ...s, opacity: 0 }));
      setPopStyle({});
      if (reduceRef.current) setPopShow(true);
      else requestAnimationFrame(() => setPopShow(true));
      return;
    }
    /* Bring the target into view before measuring it. The sidebar is a
       scrolling column, and on a phone it is a 288px drawer -- the items near
       the bottom (Profile, Help, Send feedback) sit below the fold, so
       position() measured a rect outside the viewport and left the spotlight
       off-screen with the popover clamped to the edge, pointing at nothing.
       Measuring after the scroll settles rather than before is the whole fix;
       position() itself still just reads getBoundingClientRect(). */
    const [target] = targetsFor(step);
    if (target?.scrollIntoView) {
      target.scrollIntoView({
        block: 'center',
        behavior: reduceRef.current ? 'auto' : 'smooth',
      });
    }
    const settle = window.setTimeout(() => {
      position();
      setPopShow(true);
    }, reduceRef.current ? 0 : 260);
    return () => window.clearTimeout(settle);
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
    /* Last hop of the first-time journey: onboarding -> diagnosis -> report ->
       tour -> here. The tour walks the sidebar, so it can finish anywhere;
       without this the founder is left on whichever screen the last step
       pointed at rather than the home they'll return to from now on. */
    navigate('/app');
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

  const step = steps[stepIndex];
  const isLast = stepIndex >= steps.length - 1;
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
            {steps.map((_, i) => (
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
