/**
 * App-wide toast (rendered once, from App.jsx).
 *
 * The live region is always mounted and only its *text* changes. Mounting a
 * region at the same moment its content appears is the classic reason a toast
 * never gets announced -- assistive tech has to be observing the node before
 * the text lands. Returning null on an empty message, as this did, meant every
 * "Profile saved", "Couldn't send that just now" and attachment result was
 * silent to a screen reader.
 *
 * max-w-[90vw] was also 90 *viewport* width including the scrollbar gutter;
 * with a long message on a narrow window that pushed the page horizontally.
 */
export default function Toast({ message }) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className={`fixed left-1/2 bottom-7 z-50 -translate-x-1/2 transition-all duration-400 ${
        message ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5 pointer-events-none'
      }`}
    >
      {message && (
        <div className="bg-forest text-white px-5 py-3 rounded-xl text-sm font-medium shadow-[0_18px_40px_-12px_rgba(0,0,0,.5)] flex items-center gap-2.5 max-w-[min(90vw,26rem)]">
          <span className="w-2 h-2 rounded-full bg-emerald-bright shrink-0" aria-hidden="true" />
          {message}
        </div>
      )}
    </div>
  );
}
