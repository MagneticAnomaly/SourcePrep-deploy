// Desktop browser mockup (SourcePrep). One browser frame with a top bar +
// two side-by-side screenshot cells in a 200%-wide inner scroll container.
// Inner anim is xPercent (horizontal pan). Owns its entire mockup-column
// wrapper end-to-end — <Panel> must NOT wrap this in a shared column div.

export default function DesktopBrowserMockup({ innerClass, title, screens }) {
  return (
    <div className="w-full lg:w-7/12 scale-100 sm:scale-75 md:scale-100 origin-top relative flex items-center justify-center max-md:items-start max-md:min-h-0 max-md:mt-0 max-md:flex-1 max-md:-ml-2">
      <div className="w-[110%] aspect-[1078/799] bg-void border border-white/10 rounded-xl shadow-[0_20px_60px_-15px_rgba(0,0,0,0.8)] relative overflow-hidden flex flex-col lg:translate-x-6">
        <div className="h-6 border-b border-white/10 bg-white/5 flex items-center px-2 space-x-1.5 z-10 relative">
          <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
          <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
          <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
          <span className="ml-4 font-mono text-[10px] text-white/30 tracking-widest">{title}</span>
        </div>
        {/* Inner Scroll Container */}
        <div className="flex-1 relative overflow-hidden bg-gradient-to-br from-void to-white/5">
          <div className={`${innerClass} flex w-[200%] h-full`}>
            {screens.map((s, i) => (
              <div key={i} className="w-1/2 h-full flex items-center justify-center bg-void">
                <img src={s.src} alt={s.alt} className="w-full h-full object-cover" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}