import { AlertTriangle } from 'lucide-react';
import type { BarrierStatus } from '../../types';

const STALE_THRESHOLD_SECONDS = 60 * 60;

export interface BarrierIndicatorProps {
  barrier: BarrierStatus;
  onClear?: () => void;
}

export function isBarrierStale(barrier: BarrierStatus): boolean {
  if (!barrier.active) return false;
  return (barrier.age_seconds ?? 0) > STALE_THRESHOLD_SECONDS;
}

// Barrier reasons written by the backend:
//   rebuild | full_reset | atlas_reset | group_reasoning_reset |
//   deep_enrichment_reset | enrichment_reset | finalize_reset |
//   startup_recovery | watchdog_heartbeat_stale
// Guidance keys into these so users know whether to Clear, re-run Finalize,
// or just wait.
export function barrierGuidance(barrier: BarrierStatus): string {
  if (!barrier.active) return '';
  const stale = isBarrierStale(barrier);
  const reason = barrier.reason ?? '';

  if (reason === 'startup_recovery' || reason === 'watchdog_heartbeat_stale') {
    return stale
      ? 'A stale heartbeat set this barrier — if no pipeline run is active, click Clear to unblock selfheal.'
      : 'Safety barrier after unclean shutdown. Will auto-clear once finalize completes.';
  }

  // All _reset / rebuild / full_reset variants follow the same recovery pattern:
  // finalize must complete to auto-clear. If stale, the run has almost certainly stalled.
  if (stale) {
    return 'Finalize has not completed for over an hour. Re-run the pipeline to finish finalize, or click Clear if the run is truly abandoned.';
  }
  return 'Blocks selfheal until finalize completes. Will auto-clear on a successful run.';
}

export function BarrierIndicator({ barrier, onClear }: BarrierIndicatorProps) {
  if (!barrier.active) return null;

  const ageMin = Math.floor((barrier.age_seconds ?? 0) / 60);
  const isStale = isBarrierStale(barrier);
  const guidance = barrierGuidance(barrier);

  return (
    <div
      // aria-live=polite (not role=alert) so screen readers don't re-announce
      // on every 10s health poll when age_seconds ticks over a minute boundary.
      // Status-type announcement; new content is queued politely.
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className={`flex items-start gap-2 rounded-md border px-3 py-2 text-xs ${
        isStale
          ? 'border-warning/40 bg-warning/10 text-warning'
          : 'border-muted/40 bg-muted/10 text-text-muted'
      }`}
    >
      <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" aria-hidden />
      <div className="flex-1 min-w-0">
        <div className="flex items-center flex-wrap gap-x-1">
          <span className="font-medium">Barrier active</span>
          {barrier.reason && (
            <span className="text-text-muted">— {barrier.reason}</span>
          )}
          <span className="opacity-70">({ageMin} min ago)</span>
          {isStale && <span className="font-medium">stale</span>}
        </div>
        {guidance && (
          <p className="mt-1 text-[11px] opacity-80 leading-snug">{guidance}</p>
        )}
      </div>
      {onClear && (
        <button
          type="button"
          onClick={onClear}
          className="rounded border border-current px-2 py-0.5 text-xs hover:bg-current/10 shrink-0"
        >
          Clear
        </button>
      )}
    </div>
  );
}
