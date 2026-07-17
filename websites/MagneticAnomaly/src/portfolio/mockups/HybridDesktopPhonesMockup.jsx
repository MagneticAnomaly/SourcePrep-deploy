// Hybrid mockup: 1 desktop browser frame (back layer) + 2 phones (front,
// flanking). For apps that are BOTH desktop AND mobile — Applivation ships as
// a Mac app + Safari extension AND an iOS/iPadOS app, so neither the pure
// desktop-browser nor the pure dual-phone variant tells its whole story.
//
// All three devices share the SAME `innerClass` (e.g. "mockup-inner-1") so
// GSAP's single yPercent inner-anim drives all three in lockstep — each device
// has a 200%-tall inner with two stacked cells, and yPercent:-50 reveals the
// second screen. This matches the per-slide feel of the dual-phone variants
// exactly (1.5-unit yPercent inner anim); the timeline loop picks yPercent for
// any type that isn't 'desktop-browser', so no App.jsx change is needed.
//
// Each cell is either an image ({ src, alt }) or a placeholder
// ({ label, labelClass, emoji?, barClass? }) — decided by the presence of
// `src`. So the same variant ships NOW with branded placeholder cells and
// swaps to real screenshots later by adding `src` to each cell (a data-only
// change in panels-data.js).
//
// Owns its entire mockup-column wrapper end-to-end — <Panel> must NOT wrap
// this in a shared column div (same contract as the other variants).

import PhoneFrame from './PhoneFrame';

// Render the inner content of one cell. Image if `src` present, else the
// branded placeholder (emoji + label + optional bar).
function cellContent(c) {
  if (c.src) {
    return <img src={c.src} alt={c.alt} className="w-full h-full object-cover" />;
  }
  return (
    <>
      {c.emoji && <span className="text-[20px] mb-2 drop-shadow-md">{c.emoji}</span>}
      <p className={c.labelClass}>{c.label}</p>
      {c.barClass && <div className={c.barClass} />}
    </>
  );
}

const toCellElements = (cells) =>
  cells.map((c) => ({ cellClass: c.cellClass, content: cellContent(c) }));

// Desktop browser frame. If `cellElements` has 2 entries, the inner is a
// 200%-tall scroll container carrying `innerClass` (animates in lockstep with
// the phones). If 1 entry, the desktop is static (full-height single screen)
// and does NOT carry `innerClass` — GSAP then animates only the phones.
function DesktopFrame({ innerClass, title, cellElements }) {
  const animated = cellElements.length === 2;
  const innerClassName = animated
    ? `${innerClass} flex flex-col h-[200%] w-full`
    : 'flex flex-col h-full w-full';
  return (
    <div className="w-full aspect-[1078/799] bg-void border border-white/10 rounded-xl shadow-[0_20px_60px_-15px_rgba(0,0,0,0.8)] relative overflow-hidden flex flex-col">
      <div className="h-6 border-b border-white/10 bg-white/5 flex items-center px-2 space-x-1.5 z-10 relative">
        <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
        <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
        <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
        <span className="ml-4 font-mono text-[10px] text-white/30 tracking-widest">{title}</span>
      </div>
      <div className="flex-1 relative overflow-hidden bg-gradient-to-br from-void to-white/5">
        <div className={innerClassName}>
          {cellElements.map((el, i) => (
            <div
              key={i}
              className={`w-full flex flex-col items-center justify-center ${el.cellClass} ${animated ? 'h-1/2' : 'h-full'}`}
            >
              {el.content}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function HybridDesktopPhonesMockup({ innerClass, desktop, phones }) {
  const desktopCells = toCellElements(desktop.cells);
  const phone1 = toCellElements(phones[0].cells);
  const phone2 = toCellElements(phones[1].cells);

  return (
    <div className="w-full lg:w-7/12 h-[340px] md:h-[600px] scale-[0.65] sm:scale-90 md:scale-100 origin-top relative max-md:h-auto max-md:flex-1 max-md:flex max-md:flex-col max-md:items-center max-md:gap-4 max-md:mt-0">
      {/* Desktop — back layer on md+, in-flow on top on mobile. */}
      <div className="md:absolute md:left-1/2 md:top-1/2 md:-translate-x-1/2 md:-translate-y-1/2 md:w-[78%] md:z-0 w-full max-w-[380px]">
        <DesktopFrame innerClass={innerClass} title={desktop.title} cellElements={desktopCells} />
      </div>

      {/* Phones — flanking the desktop on md+ (left/right edges, in front),
          side-by-side row on mobile. justify-between keeps the two phones at
          the stage edges so they never overlap each other; they overlap only
          the desktop (which sits behind them at z-0). */}
      <div className="md:absolute md:inset-0 flex items-end justify-between md:px-2 max-md:mt-2">
        <div className="md:z-20">
          <PhoneFrame innerClass={innerClass} cellElements={phone1} />
        </div>
        <div className="md:z-10 md:-translate-y-8">
          <PhoneFrame innerClass={innerClass} cellElements={phone2} />
        </div>
      </div>
    </div>
  );
}