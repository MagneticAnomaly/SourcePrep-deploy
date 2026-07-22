// Shared desktop browser frame — the chrome every desktop mockup uses.
//
// This is the desktop-side counterpart of PhoneFrame: the frame (border,
// rounded corners, shadow, top bar with 3 dots + title, fixed
// `aspect-[1078/799]` proportions) and a content area. The proportions live
// here so every variant that shows a desktop renders the SAME shape.
//
// What this does NOT own: the WIDTH, the column wrapper, the reveal axis, or
// the inner scroll container. Width is contextual — SourcePrep's desktop is
// `w-[110%]` of an unclipped column; the hybrid's desktop is `w-full` of a
// `w-[110%]` clip container (same 110%-of-column rendered width, just
// delivered through a clipping ancestor so the vertical reveal works). Both
// arrive at the same rendered size; the width class is the caller's job, passed
// via `className`. This keeps the chrome shared without forcing a one-size
// container that would either clip or double-amplify.
//
// Pass the content (a 2-screen xPercent inner for the desktop-browser variant,
// a single static screen for the hybrid's desktop state, or a placeholder) as
// `children`. `className` merges onto the frame div (width + positioning).

export default function DesktopFrame({ title, children, className = '', hideChrome = false }) {
  return (
    <div className={`aspect-[1078/799] bg-void border border-white/10 rounded-xl shadow-[0_20px_60px_-15px_rgba(0,0,0,0.8)] relative overflow-hidden flex flex-col ${className}`}>
      {!hideChrome && (
        <div className="h-6 border-b border-white/10 bg-white/5 flex items-center px-2 space-x-1.5 z-10 relative">
          <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
          <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
          <div className="w-2.5 h-2.5 rounded-full bg-white/20" />
          <span className="ml-4 font-mono text-[10px] text-white/30 tracking-widest">{title}</span>
        </div>
      )}
      {/* Content area — variant supplies the inner / screen / placeholder. */}
      <div className={`relative overflow-hidden bg-gradient-to-br from-void to-white/5 ${hideChrome ? 'h-full' : 'flex-1'}`}>
        {children}
      </div>
    </div>
  );
}