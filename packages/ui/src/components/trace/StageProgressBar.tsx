import { cn } from '../../lib/utils';

export type StageProgressBarVariant = 'initialize' | 'incremental' | 'rebuild';

export interface StageProgressBarProps {
  progress?: number;               // 0-100 for initialize/incremental fills
  className?: string;
  color?: string;                  // initialize fill color (e.g. "bg-blue-500", "bg-purple-500")
  rerun?: { donePercent: number; stalePercent: number };
  /** Explicit variant. Defaults to 'incremental' when `rerun` is set, otherwise 'initialize'. */
  variant?: StageProgressBarVariant;
  /** Orange top-half fill percent (0-100) when variant === 'rebuild'. */
  rebuildPercent?: number;
  /** Sub-state overlays used by the rebuild variant. */
  rebuildStateOverlay?: 'paused' | 'failed';
}

function clamp(n: number | undefined): number {
  if (typeof n !== 'number' || Number.isNaN(n)) return 0;
  return Math.min(100, Math.max(0, n));
}

export function StageProgressBar({
  progress = 0,
  className,
  color = 'bg-blue-500',
  rerun,
  variant,
  rebuildPercent,
  rebuildStateOverlay,
}: StageProgressBarProps) {
  const resolvedVariant: StageProgressBarVariant =
    variant ?? (rerun ? 'incremental' : 'initialize');

  if (resolvedVariant === 'rebuild') {
    const paused = rebuildStateOverlay === 'paused';
    const failed = rebuildStateOverlay === 'failed';
    const indeterminate =
      !failed && (rebuildPercent === undefined || rebuildPercent === null);
    const topPct = clamp(rebuildPercent);
    const topFill = failed ? 'bg-red-500' : 'bg-orange-500';
    const topWidth = failed ? 100 : topPct;
    return (
      <div
        className={cn(
          'w-full bg-surface-raised overflow-hidden rounded-full flex flex-col',
          paused && 'opacity-60',
          className,
        )}
      >
        <div className="h-1/2 w-full">
          {indeterminate ? (
            <div className={cn(topFill, 'h-full w-full animate-pulse')} />
          ) : (
            <div
              className={cn(topFill, 'h-full transition-all duration-500 ease-out')}
              style={{ width: `${topWidth}%` }}
            />
          )}
        </div>
        <div className="h-1/2 w-full bg-success" />
      </div>
    );
  }

  if (resolvedVariant === 'incremental' && rerun) {
    const donePct = clamp(rerun.donePercent);
    const stalePct = Math.min(100 - donePct, Math.max(0, rerun.stalePercent));
    const staleCompletedPct = stalePct * (clamp(progress) / 100);
    const stalePendingPct = stalePct - staleCompletedPct;
    return (
      <div className={cn('w-full bg-surface-raised overflow-hidden rounded-full', className)}>
        <div className="h-full flex">
          <div className="h-full bg-success/80 transition-all duration-300" style={{ width: `${donePct}%` }} />
          <div className="h-full bg-orange-500 transition-all duration-300" style={{ width: `${staleCompletedPct}%` }} />
          <div className="h-full bg-orange-500/40 transition-all duration-300" style={{ width: `${stalePendingPct}%` }} />
        </div>
      </div>
    );
  }

  const clamped = clamp(progress);
  return (
    <div className={cn('h-1 w-full bg-surface-raised rounded-full overflow-hidden mt-1.5', className)}>
      <div
        className={cn('h-full transition-all duration-500 ease-out', color)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
