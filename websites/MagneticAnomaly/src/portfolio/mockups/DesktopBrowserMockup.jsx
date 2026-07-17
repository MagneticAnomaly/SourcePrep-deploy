// Desktop browser mockup (SourcePrep). One browser frame with a top bar +
// two side-by-side screenshot cells in a 200%-wide inner scroll container.
// Inner anim is xPercent (horizontal pan). Owns its entire mockup-column
// wrapper end-to-end — <Panel> must NOT wrap this in a shared column div.
//
// The frame chrome is shared via <DesktopFrame> (same component the hybrid's
// desktop state uses), so every desktop renders at the same size. Only the
// column wrapper + the 2-screen xPercent inner are specific to this variant.

import DesktopFrame from './DesktopFrame';

export default function DesktopBrowserMockup({ innerClass, title, screens }) {
  return (
    <div className="w-full lg:w-7/12 scale-100 sm:scale-75 md:scale-100 origin-top relative flex items-center justify-center max-md:items-start max-md:min-h-0 max-md:mt-0 max-md:flex-1 max-md:-ml-2">
      <DesktopFrame title={title} className="w-[110%] lg:translate-x-6">
        <div className={`${innerClass} flex w-[200%] h-full`}>
          {screens.map((s, i) => (
            <div key={i} className="w-1/2 h-full flex items-center justify-center bg-void">
              <img src={s.src} alt={s.alt} className="w-full h-full object-cover" />
            </div>
          ))}
        </div>
      </DesktopFrame>
    </div>
  );
}