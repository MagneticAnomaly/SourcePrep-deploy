// Hybrid mockup that COMPOSES the two existing templates as the two states of
// one reveal — for apps that are BOTH mobile AND desktop (Applivation: Mac app
// + Safari extension AND iOS/iPadOS app).
//
//   State 1 = a set of 2 phones   (the dual-phone template, static — exactly
//                                  like the first state of HomeColab /
//                                  DinnerVision / DebateHaus).
//   State 2 = 1 desktop browser    (the desktop-browser template, static —
//                                  exactly like SourcePrep's frame).
//
// The single yPercent inner-anim reveals state 2, the same reveal mechanism the
// dual-phone variants use (just with a desktop as the second state instead of
// a second phone set). The timeline axis logic is unchanged — any type that
// isn't 'desktop-browser' gets yPercent — so no App.jsx edit is needed.
//
// 3 screenshots total: 2 phone (state 1) + 1 desktop (state 2). Each screen is
// graceful: an <img> when {src, alt} is supplied, else a branded placeholder
// ({label, emoji, labelClass}). Ships now with placeholders; adding src to a
// screen swaps it to the real screenshot (data-only change in panels-data.js).
//
// Responsive: the 2-state reveal runs on md+ only (the stage is ~580-700px
// there, so the 2 phones fit natively and `overflow-hidden` clips only the
// off-screen state). On mobile the stage is too narrow for 2 phones side by
// side, so mobile shows the 2 phones statically — exactly like dual-phone
// mobile. The animated `mockup-inner-N` element is `display:none` on mobile,
// so GSAP's yPercent tween is harmless there.
//
// Owns its entire mockup-column wrapper end-to-end — <Panel> must NOT wrap
// this in a shared column div (same contract as the other variants).

import PhoneFrame from './PhoneFrame';

// Benign innerClass for the static phones — GSAP must NOT animate the phones'
// own inners (only the hybrid's outer 2-state inner carries the real
// `mockup-inner-N` and animates). PhoneFrame still gets a class so its frame
// chrome renders identically to the dual-phone variants.
const STATIC_INNER = 'hybrid-static-inner';

// One phone screen -> a single PhoneFrame cell (image or branded placeholder).
const phoneCell = (s) => {
  if (s.src) {
    return {
      cellClass: 'h-1/2 w-full flex items-center justify-center bg-void',
      content: <img src={s.src} alt={s.alt} className="w-full h-full object-cover" />,
    };
  }
  return {
    cellClass: `h-1/2 w-full flex flex-col items-center justify-center p-4 ${s.cellClass || 'bg-gradient-to-t from-void to-[#0a1830]'}`,
    content: (
      <>
        {s.emoji && <span className="text-[20px] mb-2 drop-shadow-md">{s.emoji}</span>}
        <p className={s.labelClass}>{s.label}</p>
      </>
    ),
  };
};

// One desktop screen -> a static desktop browser frame (the desktop-browser
// template's frame, single screen). Image if `src`, else branded placeholder.
function StaticDesktop({ title, src, alt, label, emoji, labelClass }) {
  return (
    <div className="w-[85%] aspect-[1078/799] bg-void border border-white/10 rounded-xl shadow-[0_20px_60px_-15px_rgba(0,0,0,0.8)] relative overflow-hidden flex flex-col">
      <div className="h-6 border-b border-white/10 bg-white/5 flex items-center px-2 space-x-1.5 z-10 relative">
        <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
        <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
        <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
        <span className="ml-4 font-mono text-[10px] text-white/30 tracking-widest">{title}</span>
      </div>
      <div className="flex-1 relative overflow-hidden bg-gradient-to-br from-void to-white/5 flex items-center justify-center">
        {src ? (
          <img src={src} alt={alt} className="w-full h-full object-cover" />
        ) : (
          <div className="flex flex-col items-center justify-center">
            {emoji && <span className="text-[28px] mb-3 drop-shadow-md">{emoji}</span>}
            <p className={labelClass}>{label}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function HybridDesktopPhonesMockup({ innerClass, desktop, phones }) {
  const [p1, p2] = phones;
  const c1 = [phoneCell(p1)];
  const c2 = [phoneCell(p2)];

  return (
    <div className="w-full lg:w-7/12 scale-[0.65] sm:scale-90 md:scale-100 origin-top relative max-md:h-auto max-md:flex-1 max-md:flex max-md:items-center max-md:justify-center md:h-[600px] md:overflow-hidden">
      {/* Mobile (<768px): static 2 phones, no reveal. The stage is too narrow
          for 2 phones side by side, so we skip the desktop state here and show
          the phones exactly like dual-phone mobile. */}
      <div className="md:hidden flex items-end justify-center gap-6">
        <PhoneFrame innerClass={STATIC_INNER} cellElements={c1} />
        <PhoneFrame innerClass={STATIC_INNER} cellElements={c2} staggered />
      </div>

      {/* md+ (>=768px): the 2-state reveal. This element carries the real
          `mockup-inner-N`; GSAP's yPercent tween drives it. `max-md:hidden`
          keeps it display:none on mobile so the tween is harmless there. */}
      <div className={`${innerClass} max-md:hidden flex flex-col md:h-[200%] w-full`}>
        {/* State 1: 2 phones (dual-phone template, static). `md:pb-16` lifts the
            pair 64px so the staggered phone 2 (md:translate-y-16) reaches the
            state bottom exactly — without it, the stage's overflow-hidden
            (required for the reveal) would clip phone 2's lower 64px. */}
        <div className="md:h-1/2 w-full flex items-end justify-center gap-6 md:gap-10 md:pb-16">
          <PhoneFrame innerClass={STATIC_INNER} cellElements={c1} />
          <PhoneFrame innerClass={STATIC_INNER} cellElements={c2} staggered />
        </div>
        {/* State 2: 1 desktop (desktop-browser template, static). */}
        <div className="md:h-1/2 w-full flex items-center justify-center">
          <StaticDesktop {...desktop} />
        </div>
      </div>
    </div>
  );
}