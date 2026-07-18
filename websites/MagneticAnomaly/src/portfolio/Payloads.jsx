import React, { useRef } from 'react';
import { panels } from './panels-data';
import Panel from './Panel';

// "PAYLOADS" portfolio section. Maps the `panels` array to <Panel> components.
// The GSAP timeline lives in App.jsx (it references ceresOrbit / ceresLookAt /
// globalCamera in App.jsx scope) and targets .app-panel-N / .mockup-inner-N
// by class — those selectors resolve across module boundaries because the
// useGSAP scope (appContainer) contains this rendered tree.

export default function Payloads() {
  const container = useRef();

  return (
    <>
      <div id="gap-to-payloads" className="h-[150vh] pointer-events-none" />
      <section id="payloads" ref={container} className="w-full min-h-[100dvh] flex flex-col justify-center pt-8 pb-12 md:py-12 relative z-10 max-md:h-[100dvh] max-md:justify-start max-md:pt-28 max-md:pb-2">

        {/* Header matching Navbar width */}
        <div className="max-w-7xl w-full px-6 mx-auto mb-6 md:mb-12 lg:mb-20 max-md:mb-4 max-md:shrink-0">
          <h3 className="font-mono text-sm tracking-[0.2em] text-titan mb-4 uppercase max-md:mb-0 hidden md:block">// OUR WORK</h3>
          <h2 className="font-sans font-bold text-4xl md:text-5xl uppercase tracking-wider text-ice hidden md:block">Portfolio</h2>
          <h3 className="font-mono text-sm tracking-[0.2em] text-titan mb-0 uppercase md:hidden">// PORTFOLIO</h3>
        </div>

        {/* Portfolio Cards matching wider layout */}
        <div className="max-w-[1400px] w-full px-0 sm:px-4 md:px-8 mx-auto max-md:flex-1 max-md:flex max-md:flex-col max-md:min-h-0">
          <div className="overflow-hidden w-full relative max-md:h-full max-md:flex-1">
            <div className="payloads-track relative w-full h-[550px] md:h-[700px] max-md:h-full">
              {panels.map((panel, index) => (
                <Panel key={panel.id} index={index} panel={panel} />
              ))}
            </div>
          </div>
        </div>
      </section>
    </>
  );
}