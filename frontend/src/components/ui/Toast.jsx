export default function Toast({ message }) {
  if (!message) return null;
  return (
    <div className={`fixed left-1/2 bottom-7 z-50 -translate-x-1/2 transition-all duration-400 ${
      message ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5 pointer-events-none'
    }`}>
      <div className="bg-forest text-white px-5 py-3 rounded-xl text-sm font-medium shadow-[0_18px_40px_-12px_rgba(0,0,0,.5)] flex items-center gap-2.5 max-w-[90vw]">
        <span className="w-2 h-2 rounded-full bg-emerald-bright shrink-0" />
        {message}
      </div>
    </div>
  );
}
