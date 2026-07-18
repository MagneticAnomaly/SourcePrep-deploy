// Dual-phone mockup with bespoke gradient/label/bar cells (DinnerVision,
// DebateHaus, and the placeholder 5th slot). Same phone frame as
// DualPhoneImageMockup; cells render a <p> label (with optional emoji span)
// and an optional bar div instead of an image. Inner anim is yPercent.
// Owns its entire mockup-column wrapper end-to-end.

import PhoneFrame from './PhoneFrame';

function PlaceholderCell({ cell }) {
  return (
    <>
      <p className={cell.labelClass}>
        {cell.emoji && <span className="text-[20px] mb-2 drop-shadow-md">{cell.emoji}</span>}
        {cell.label}
      </p>
      {cell.barClass && <div className={cell.barClass} />}
    </>
  );
}

export default function DualPhonePlaceholderMockup({ innerClass, phones }) {
  const cellElements = (cells) =>
    cells.map((c) => ({
      cellClass: c.cellClass,
      content: <PlaceholderCell cell={c} />,
    }));

  return (
    <div className="w-full lg:w-7/12 h-[340px] md:h-[600px] scale-[0.65] sm:scale-90 md:scale-100 origin-top relative flex items-center justify-center gap-6 md:gap-10 pb-[1em] md:pb-[4em] max-md:items-start max-md:min-h-0 max-md:mt-0 max-md:flex-1 max-md:h-auto">
      <PhoneFrame innerClass={innerClass} cellElements={cellElements(phones[0].cells)} />
      <PhoneFrame innerClass={innerClass} cellElements={cellElements(phones[1].cells)} staggered />
    </div>
  );
}