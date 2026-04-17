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

export function BarrierIndicator({ barrier, onClear }: BarrierIndicatorProps) {
  if (!barrier.active) return null;

  const ageMin = Math.floor((barrier.age_seconds ?? 0) / 60);
  const isStale = isBarrierStale(barrier);

  return (
    <div
      role="alert"
      className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs ${
        isStale
          ? 'border-warning/40 bg-warning/10 text-warning'
          : 'border-muted/40 bg-muted/10 text-text-muted'
      }`}
    >
      <AlertTriangle className="h-4 w-4" aria-hidden />
      <div className="flex-1">
        <span className="font-medium">Barrier active</span>
        {barrier.reason && (
          <span className="ml-1 text-text-muted">— {barrier.reason}</span>
        )}
        <span className="ml-2 opacity-70">({ageMin} min ago)</span>
        {isStale && <span className="ml-2 font-medium">stale</span>}
      </div>
      {onClear && (
        <button
          type="button"
          onClick={onClear}
          className="rounded border border-current px-2 py-0.5 text-xs hover:bg-current/10"
        >
          Clear
        </button>
      )}
    </div>
  );
}
