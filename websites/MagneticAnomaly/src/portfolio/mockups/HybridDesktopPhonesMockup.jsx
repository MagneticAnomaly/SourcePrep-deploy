// Hybrid mockup that COMPOSES the two existing templates as the two states of
// one reveal — for apps that are BOTH mobile AND desktop (Applivation: Mac app
// + Safari extension AND iOS/iPadOS app).
//
//   State 1 = a set of 2 phones   (the dual-phone template, static — exactly
//                                  like the first state of HomeColab /
//                                  DinnerVision / DebateHaus). Uses the shared
//                                  <PhoneFrame>.
//   State 2 = 1 desktop browser    (the desktop-browser template, static —
//                                  exactly like SourcePrep's frame). Uses the
//                                  shared <DesktopFrame>, so the desktop is
//                                  the SAME SIZE as SourcePrep's by
//                                  construction (no bespoke frame, no drift).
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
// Sizing note: the reveal's vertical clip lives on a `w-full` container (the
// same width as the column, 100% — NOT 110%). The desktop inside is
// `w-[110%]` (the SAME width class SourcePrep passes to <DesktopFrame>), and
// because the state-2 cell is a flex row (`flex items-center justify-center`),
// the `w-[110%]` desktop flex-shrinks to the cell width — exactly the same
// flex-clamp that makes SourcePrep's `w-[110%]` desktop render at the column
// width. Net: same <DesktopFrame>, same `w-[110%]` width class, same
// flex-clamp behavior -> identical rendered size. (Only difference: no
// `lg:translate-x-6` on the hybrid desktop, since it sits centered in its
// state cell rather than right-shifted in a plain column.) The clip
// container's overflow-hidden is for the VERTICAL reveal only; the desktop
// fits the cell exactly (flex-clamped), so it is not clipped horizontally.
//
// Owns its entire mockup-column wrapper end-to-end — <Panel> must NOT wrap
// this in a shared column div (same contract as the other variants).

import PhoneFrame from './PhoneFrame';
import DesktopFrame from './DesktopFrame';

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

// One desktop screen -> the content for <DesktopFrame> (image or branded
// placeholder). The frame itself (size, chrome, top bar) comes from the shared
// <DesktopFrame> — identical to SourcePrep's.
function desktopContent({ src, alt, label, emoji, labelClass }) {
  if (src) {
    return <img src={src} alt={alt} className="w-full h-full object-cover" />;
  }
  return (
    <div className="w-full h-full flex flex-col items-center justify-center">
      {emoji && <span className="text-[28px] mb-3 drop-shadow-md">{emoji}</span>}
      <p className={labelClass}>{label}</p>
    </div>
  );
}

export default function HybridDesktopPhonesMockup({ innerClass, desktop, phones }) {
  const [p1, p2] = phones;
  const c1 = [phoneCell(p1)];
  const c2 = [phoneCell(p2)];

  return (
    <div className="w-full lg:w-7/12 scale-[0.65] sm:scale-90 md:scale-100 origin-top relative max-md:h-auto max-md:flex-1 max-md:flex max-md:items-center max-md:justify-center md:h-[600px]">
      {/* Mobile (<768px): static 2 phones, no reveal. The stage is too narrow
          for 2 phones side by side, so we skip the desktop state here and show
          the phones exactly like dual-phone mobile. */}
      <div className="md:hidden flex items-end justify-center gap-6">
        <PhoneFrame innerClass={STATIC_INNER} cellElements={c1} />
        <PhoneFrame innerClass={STATIC_INNER} cellElements={c2} staggered />
      </div>

      {/* md+ (>=768px): the 2-state reveal.
          - The clip container is `w-[110%]` (NOT the column) so the desktop —
            also `w-[110%]` via <DesktopFrame> — is not clipped narrower than
            SourcePrep's at lg. Vertical clip here clips the off-screen state.
          - `max-md:hidden` keeps it display:none on mobile so the yPercent
            tween is harmless there. This element carries the real
            `mockup-inner-N`; GSAP drives it. */}
      <div className="max-md:hidden w-full md:h-[600px] md:overflow-hidden md:relative">
        <div className={`${innerClass} flex flex-col md:h-[200%] w-full`}>
          {/* State 1: 2 phones (dual-phone template, static). `md:pb-16` lifts
              the pair 64px so the staggered phone 2 (md:translate-y-16) reaches
              the state bottom exactly — without it, the clip container's
              overflow-hidden (required for the reveal) would clip phone 2's
              lower 64px. */}
          <div className="md:h-1/2 w-full flex items-end justify-center gap-6 md:gap-10 md:pb-16">
            <PhoneFrame innerClass={STATIC_INNER} cellElements={c1} />
            <PhoneFrame innerClass={STATIC_INNER} cellElements={c2} staggered />
          </div>
          {/* State 2: 1 desktop (desktop-browser template, static). Same
              <DesktopFrame> chrome + same `w-[110%]` width class as SourcePrep;
              the flex-row cell flex-clamps it to the cell width, so it renders
              at the same size as SourcePrep's desktop. No lg:translate-x-6
              (this desktop sits centered in its state cell). */}
          <div className="md:h-1/2 w-full flex items-center justify-center">
            <DesktopFrame title={desktop.title} className="w-[110%]">
              {desktopContent(desktop)}
            </DesktopFrame>
          </div>
        </div>
      </div>
    </div>
  );
}