// Dual-phone mockup with remote screenshot images (HomeColab). Two phone
// frames (phone 2 staggered md:translate-y-16), each with two stacked image
// cells in a 200%-tall inner scroll container. Inner anim is yPercent
// (vertical pan). Owns its entire mockup-column wrapper end-to-end.

import PhoneFrame from './PhoneFrame';

export default function DualPhoneImageMockup({ innerClass, phones }) {
  const cellElements = (cells) =>
    cells.map((c) => ({
      cellClass: c.cellClass,
      content: <img src={c.src} alt={c.alt} className="w-full h-full object-cover" />,
    }));

  return (
    <div className="w-full lg:w-7/12 h-[340px] md:h-[600px] scale-[0.65] sm:scale-90 md:scale-100 origin-top relative flex items-center justify-center gap-6 md:gap-10 pb-[1em] md:pb-[4em] max-md:items-start max-md:min-h-0 max-md:mt-0 max-md:flex-1 max-md:h-auto">
      <PhoneFrame innerClass={innerClass} cellElements={cellElements(phones[0].cells)} />
      <PhoneFrame innerClass={innerClass} cellElements={cellElements(phones[1].cells)} staggered />
    </div>
  );
}