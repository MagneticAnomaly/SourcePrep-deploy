import { cn } from '../../lib/utils';

export interface StageProgressBarProps {
  progress?: number; // 0 to 100, undefined = indeterminate
  className?: string;
  color?: string; // Tailwind bg color class for the bar (e.g. "bg-blue-500")
  rerun?: { donePercent: number; stalePercent: number };
}

export function StageProgressBar({ 
  progress = 0, 
  className,
  color = "bg-blue-500",
  rerun
}: StageProgressBarProps) {
  if (rerun) {
    // Rerun mode: green (unchanged/done) + orange (stale being reprocessed).
    // The orange section fills the ENTIRE remaining space (not transparent).
    // Transparent bg is only for the initial first-time build.
    const donePct = Math.min(100, Math.max(0, rerun.donePercent));
    const stalePct = Math.min(100 - donePct, Math.max(0, rerun.stalePercent));
    // Within the orange section, show brighter portion for completed work
    const staleCompletedPct = stalePct * (progress / 100);
    const stalePendingPct = stalePct - staleCompletedPct;
    return (
      <div className={cn("w-full bg-surface-raised overflow-hidden rounded-full", className)}>
        <div className="h-full flex">
          <div className="h-full bg-success/80 transition-all duration-300" style={{ width: `${donePct}%` }} />
          <div className="h-full bg-orange-500 transition-all duration-300" style={{ width: `${staleCompletedPct}%` }} />
          <div className="h-full bg-orange-500/40 transition-all duration-300" style={{ width: `${stalePendingPct}%` }} />
        </div>
      </div>
    );
  }
  // Default to 0% when no progress data yet — avoids a ~40% flash
  // from the old indeterminate animation before real data arrives.
  const clamped = progress !== undefined ? Math.min(100, Math.max(0, progress)) : 0;
  
  return (
    <div className={cn("h-1 w-full bg-surface-raised rounded-full overflow-hidden mt-1.5", className)}>
      <div 
        className={cn("h-full transition-all duration-500 ease-out", color)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
