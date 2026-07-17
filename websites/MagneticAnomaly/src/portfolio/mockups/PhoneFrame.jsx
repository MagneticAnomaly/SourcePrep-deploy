// Shared phone frame for the dual-phone mockup variants. Both phones in a
// panel share the SAME `innerClass` (e.g. "mockup-inner-2") so GSAP's single
// inner-scroll target drives both phones in lockstep — matching the original
// hand-written JSX.
//
// `cellElements` is an array of { cellClass, content } where `content` is the
// already-rendered JSX for that cell (an <img> for dual-phone-image, a <p> +
// optional bar for dual-phone-placeholder). The variant owns cell content;
// PhoneFrame owns the frame chrome + the inner scroll container.

export default function PhoneFrame({ innerClass, cellElements, staggered }) {
  const phoneClass = staggered
    ? 'w-[240px] h-[520px] shrink-0 bg-void border border-white/10 rounded-[3rem] p-3 relative shadow-[0_20px_60px_-15px_rgba(0,0,0,0.8)] flex flex-col md:translate-y-16 z-10'
    : 'w-[240px] h-[520px] shrink-0 bg-void border border-white/10 rounded-[3rem] p-3 relative shadow-[0_20px_60px_-15px_rgba(0,0,0,0.8)] flex flex-col z-20';
  return (
    <div className={phoneClass}>
      <div className="w-16 h-2 bg-white/20 rounded-full mx-auto mb-4 absolute top-5 left-1/2 -translate-x-1/2 z-30" />
      <div className="flex-1 rounded-[1.75rem] overflow-hidden relative">
        <div className={`${innerClass} flex flex-col h-[200%] w-full`}>
          {cellElements.map((el, i) => (
            <div key={i} className={el.cellClass}>
              {el.content}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}