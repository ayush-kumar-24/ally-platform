/**
 * Journey — Coming soon.
 *
 * The hero matches the reference design (see PROGRESS.md / the mockup this
 * was built from). The timeline itself is deliberately NOT built: the
 * mockup's entries ("2018 · Started the first venture", "2022 · Crossed
 * ₹1Cr revenue"...) are sample copy for one fictional founder, and nothing
 * in this app derives a real founder's actual milestones yet. Shipping that
 * sample copy as if it were assembled from the signed-in founder's own
 * story would be exactly the fabricated-content bug this codebase's other
 * pages go out of their way to avoid (see KnowMyEnergy.jsx, NextSteps.jsx).
 * An honest "coming soon" beneath a real hero, instead.
 */

function IconRoad(props) {
  return (
    <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="1em" height="1em" {...props}>
      <path d="M4 20 9 4h6l5 16M9 14h6M2 20h20" />
    </svg>
  );
}

export default function JourneyPage() {
  return (
    <div className="jny-page">
      <section className="jny-hero">
        <div className="jny-kicker">Your Journey</div>
        <h1>The path that shaped how you build.</h1>
        <p>Decisions, lessons and turning points Ally will capture from your story.</p>
      </section>

      <section className="jny-soon">
        <div className="jny-soon-ic"><IconRoad /></div>
        <h2>Coming soon</h2>
        <p>
          Journey is being built now — it will trace the decisions, pivots and lessons
          Ally learns about from your conversations and diagnoses into one timeline.
          You'll find it here as soon as it's ready.
        </p>
      </section>
    </div>
  );
}
