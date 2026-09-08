/**
 * The Ally splash: the mark rising in behind a soft glow, the two words, and
 * three dots keeping time. Drawn, not filmed.
 *
 * Two places show it -- SplashScreen when a founder first arrives, and
 * AuthTransition in the moment after they sign in -- and they must look the
 * same, so the picture lives here and each of them supplies only the timing
 * around it. Built from the splash in assests/GoXL Ally standalone.html: its
 * gradient, its glow, its rise and its dot stagger, drawn with the app's own
 * type tokens rather than the bundle's fonts.
 *
 * This replaced a 957 KB H.264 film. As a 101 KB image and some CSS there is
 * nothing to buffer, nothing to decode, no codec a given browser might not
 * have, and it cannot arrive late on a slow connection -- which is the failure
 * the film had to guard against with a timeout.
 *
 * Fills whatever positioned box it is placed in. The keyframes live in
 * styles/animations.css, where the global reduced-motion rule flattens them:
 * the splash then simply appears, still and legible.
 */

const RISE = 'cubic-bezier(.2,.7,.2,1)';

/* How long the splash holds before whoever is showing it moves on. The length
   of the animation itself and not a second longer: the founder is waiting to
   be let in. Shared so the two showings cannot drift apart. */
export const SPLASH_MS = 2200;

/* One object at module scope so it is not rebuilt on every render. */
const s = {
  screen: {
    position: 'absolute',
    inset: 0,
    background:
      'radial-gradient(130% 90% at 50% 18%, #0c3a2b 0%, #071812 60%, #04100b 100%)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 26,
  },
  markWrap: {
    position: 'relative',
    width: 132,
    height: 132,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  glow: {
    position: 'absolute',
    inset: -18,
    borderRadius: '50%',
    background: 'radial-gradient(circle, rgba(52,224,166,.35), transparent 70%)',
    animation: 'gxGlow 2.4s ease-in-out infinite',
  },
  mark: {
    width: 112,
    height: 112,
    objectFit: 'contain',
    animation: `gxRise .7s ${RISE} both`,
  },
  words: { textAlign: 'center', animation: `gxRise .7s ${RISE} .12s both` },
  name: {
    fontFamily: 'var(--display-tight)',
    fontWeight: 800,
    fontSize: 30,
    letterSpacing: '-.02em',
    color: '#fff',
  },
  tagline: {
    fontFamily: 'var(--serif)',
    fontStyle: 'italic',
    fontSize: 17,
    color: '#7fe9c2',
    marginTop: 4,
  },
  dots: { display: 'flex', gap: 7, marginTop: 6 },
  dot: {
    width: 7,
    height: 7,
    borderRadius: '50%',
    background: '#34E0A6',
    animation: 'gxDot 1.2s ease infinite',
  },
};

/**
 * @param {{ label: string }} props  what a screen reader announces -- the
 *   splash is a status, and the two showings mean different things
 */
export default function AllySplash({ label }) {
  return (
    <div style={s.screen} role="status" aria-label={label}>
      <div style={s.markWrap}>
        <div style={s.glow} />
        <img src="/ally-logo-mark-on-dark.png" alt="" style={s.mark} />
      </div>
      <div style={s.words}>
        <div style={s.name}>GoXL Ally</div>
        <div style={s.tagline}>The Founder&rsquo;s Compass</div>
      </div>
      <div style={s.dots}>
        {[0, 0.2, 0.4].map((delay) => (
          <span key={delay} style={{ ...s.dot, animationDelay: `${delay}s` }} />
        ))}
      </div>
    </div>
  );
}
