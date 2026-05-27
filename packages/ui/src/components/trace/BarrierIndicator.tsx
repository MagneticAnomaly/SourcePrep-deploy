import { AlertTriangle } from 'lucide-react';
import type { BarrierStatus } from '../../types';

const STALE_THRESHOLD_SECONDS = 60 * 60;

export interface BarrierIndicatorProps {
  barrier: BarrierStatus;
  onClear?: () => void;
  /**
   * when a pipeline group is actively running we hide the
   * banner entirely — the rebuild progress bar already shows the user
   * what they need to know, and a duplicate "Barrier active" indicator
   * is just clutter that exposes internal plumbing terms.
   */
  pipelineActive?: boolean;
}

export function isBarrierStale(barrier: BarrierStatus): boolean {
  if (!barrier.active) return false;
  return (barrier.age_seconds ?? 0) > STALE_THRESHOLD_SECONDS;
}

// user-facing copy for each barrier reason.
// Goals:
//   - No internal jargon ("barrier", "selfheal", "finalize", "stale heartbeat")
//   - Tell the user what happened and what to do next
//   - Match the action the Clear button actually performs in that context
//
// Backend barrier reasons:
//   rebuild | full_reset | enrichment_reset | finalize_reset |
//   startup_recovery | watchdog_heartbeat_stale
//   (legacy: atlas_reset | group_reasoning_reset | deep_enrichment_reset)
//
// Returns: { title, body, actionLabel } — actionLabel is what the
// "Clear"-equivalent button says in user terms.
export interface BarrierUiCopy {
  title: string;
  body: string;
  actionLabel: string;
}

export function barrierUiCopy(barrier: BarrierStatus): BarrierUiCopy {
  const stale = isBarrierStale(barrier);
  const reason = barrier.reason ?? '';

  if (reason === 'rebuild') {
    return stale
      ? {
          title: 'Rebuild not finished',
          body: "It's been over an hour since the rebuild was running. Click Resume to continue, or Discard to keep the prior data and stop trying.",
          actionLabel: 'Discard',
        }
      : {
          title: 'Rebuild incomplete',
          body: 'The rebuild was interrupted. Some stages still show their prior data, untouched. Click Resume to continue from where it stopped, or Discard to keep prior data.',
          actionLabel: 'Discard',
        };
  }

  if (reason === 'full_reset') {
    return {
      title: 'Project reset',
      body: 'The pipeline data was wiped. Run the pipeline to rebuild from scratch.',
      actionLabel: 'Dismiss',
    };
  }

  if (reason === 'enrichment_reset') {
    return {
      title: 'Enrichment reset',
      body: 'Stages 6–15 were wiped. Run Deep Enrichment to rebuild them; fast-sync stages (1–5) are intact.',
      actionLabel: 'Dismiss',
    };
  }

  if (reason === 'finalize_reset') {
    return {
      title: 'Finalize reset',
      body: 'Stages 11–15 were wiped. Run Finalize to rebuild them; earlier stages are intact.',
      actionLabel: 'Dismiss',
    };
  }

  if (reason === 'startup_recovery' || reason === 'watchdog_heartbeat_stale') {
    return stale
      ? {
          title: 'Pipeline appears stalled',
          body: "It's been over an hour without progress. Run again to retry, or Discard if the run is abandoned.",
          actionLabel: 'Discard',
        }
      : {
          title: 'Pipeline interrupted',
          body: 'The pipeline was interrupted (likely by a server restart). Run again to continue, or Discard.',
          actionLabel: 'Discard',
        };
  }

  // Generic/legacy reasons fall back to a neutral message.
  return stale
    ? {
        title: 'Last run incomplete',
        body: "It's been over an hour. Run again to retry, or Discard to clear this notice.",
        actionLabel: 'Discard',
      }
    : {
        title: 'Last run incomplete',
        body: 'Run again to continue, or Discard to clear this notice.',
        actionLabel: 'Dismiss',
      };
}

// Legacy export — preserved so existing callers (and tests) that expect a
// string-returning function don't break. Returns the body of barrierUiCopy.
export function barrierGuidance(barrier: BarrierStatus): string {
  if (!barrier.active) return '';
  return barrierUiCopy(barrier).body;
}

export function BarrierIndicator({ barrier, onClear, pipelineActive }: BarrierIndicatorProps) {
  if (!barrier.active) return null;
  // hide entirely while a pipeline group is actively running.
  // The rebuild progress bar at the top of the panel already tells the user
  // what's happening; a duplicate "Barrier active" notice is just noise that
  // exposes internal plumbing terms (selfheal, finalize, barrier).
  if (pipelineActive) return null;

  const ageMin = Math.floor((barrier.age_seconds ?? 0) / 60);
  const isStale = isBarrierStale(barrier);
  const copy = barrierUiCopy(barrier);
  const ageLabel = ageMin <= 0 ? 'just now' : ageMin === 1 ? '1 min ago' : `${ageMin} min ago`;

  return (
    <div
      // aria-live=polite (not role=alert) so screen readers don't re-announce
      // on every 10s health poll when age_seconds ticks over a minute boundary.
      role="status"
      aria-live="polite"
      aria-atomic="true"
      data-testid="pipeline-barrier-indicator"
      data-barrier-scope={barrier.scope ?? undefined}
      data-barrier-reason={barrier.reason ?? undefined}
      className={`flex items-start gap-2 rounded-md border px-3 py-2 text-xs ${
        isStale
          ? 'border-warning/40 bg-warning/10 text-warning'
          : 'border-muted/40 bg-muted/10 text-text-muted'
      }`}
    >
      <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" aria-hidden />
      <div className="flex-1 min-w-0">
        <div className="flex items-center flex-wrap gap-x-1">
          <span className="font-medium">{copy.title}</span>
          <span className="opacity-70">({ageLabel})</span>
        </div>
        <p className="mt-1 text-[11px] opacity-80 leading-snug">{copy.body}</p>
      </div>
      {onClear && (
        <button
          type="button"
          onClick={onClear}
          className="rounded border border-current px-2 py-0.5 text-xs hover:bg-current/10 shrink-0"
          aria-label={copy.actionLabel}
        >
          {copy.actionLabel}
        </button>
      )}
    </div>
  );
}
