import React from 'react';
import { ExternalLink } from 'lucide-react';
import { mockupVariants } from './mockups';

// Generic portfolio panel. Renders the identical outer `.app-panel-N` chrome
// + card + text column from `panel`, then slots the mockup variant in as a
// sibling. The variant OWNS its entire mockup-column wrapper — <Panel> does
// NOT wrap it in a shared column div (that would reintroduce per-variant
// class branches).
//
// `index` is 0-based; panelClass/innerClass are derived here in ONE place
// (the off-by-one guard): app-panel-{index+1}, mockup-inner-{index+1}.

export default function Panel({ index, panel }) {
  const N = index + 1;
  const panelClass = `app-panel-${N}`;
  const innerClass = `mockup-inner-${N}`;
  const Variant = mockupVariants[panel.mockup.type];

  return (
    <div className={`${panelClass} absolute inset-0 w-full h-full flex flex-col justify-center px-2 sm:px-4 md:px-8 max-md:justify-start max-md:pb-2`}>
      <div className="payload-card w-full relative glass-panel rounded-[2.5rem] p-2 md:p-3 overflow-hidden transition-all duration-700 hover:border-titan/50 hover:shadow-[0_0_40px_rgba(229,141,87,0.15)] md:bg-void/80 min-h-[500px] md:min-h-[650px] max-md:h-full max-md:rounded-[2rem] max-md:flex max-md:flex-col">
        {panel.cardOverlay && (
          <div className="absolute inset-0 bg-gradient-to-br from-titan/5 to-transparent opacity-0 hover:opacity-100 transition-opacity duration-500" />
        )}
        <div className="relative z-10 w-full h-full p-4 md:p-14 flex flex-col lg:flex-row gap-4 md:gap-8 lg:gap-12 items-center max-md:items-start max-md:min-h-0">

          {/* Text Column */}
          <div className="w-full lg:w-5/12 max-md:shrink-0">
            <div className="flex flex-row items-center justify-between mb-6 gap-4">
              <div className="flex items-center space-x-4">
                <div className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden flex-shrink-0">
                  {panel.icon ? (
                    <img src={panel.icon} alt={`${panel.name} Icon`} className="w-full h-full object-cover" />
                  ) : (
                    <span className="font-mono text-xs text-white/40">{panel.name.slice(0, 2).toUpperCase()}</span>
                  )}
                </div>
                <div>
                  <span className="font-mono text-xs text-telemetry tracking-widest block">{panel.tag}</span>
                  <h4 className="font-sans text-2xl md:text-3xl font-bold text-ice">{panel.name}</h4>
                </div>
              </div>
              {panel.url && (
                <a href={panel.url} target="_blank" rel="noreferrer" className="md:hidden flex-shrink-0 w-10 h-10 flex items-center justify-center rounded-xl bg-white/5 hover:bg-titan text-ice hover:text-void border border-white/10 hover:border-titan transition-all">
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>

            <p className="font-mono text-[11px] md:text-sm text-telemetry max-md:text-[#A1AAB5] mb-4 md:mb-6 leading-relaxed">
              <strong className="text-ice">{panel.tagline}</strong><br /><br />
              {panel.blurb}
            </p>

            <div className="space-y-1.5 md:space-y-2 mb-4 md:mb-8 font-mono text-[10px] md:text-xs text-telemetry max-md:text-[#A1AAB5]">
              {panel.bullets.map((b) => (
                <p key={b} className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-titan mr-2"></span> {b}</p>
              ))}
            </div>

            {panel.url && (
              <a href={panel.url} target="_blank" rel="noreferrer" className="hidden md:inline-block font-mono text-xs bg-white/5 hover:bg-titan hover:text-void text-ice border border-white/10 hover:border-titan px-8 py-4 rounded-full transition-all uppercase tracking-wider">
                View Website
              </a>
            )}
          </div>

          {/* Mockup Column — variant owns its wrapper end-to-end */}
          {Variant && <Variant innerClass={innerClass} {...panel.mockup} />}

        </div>
      </div>
    </div>
  );
}