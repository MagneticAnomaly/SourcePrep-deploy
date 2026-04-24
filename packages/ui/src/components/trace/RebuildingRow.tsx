/**
 * RebuildingRow — Phase 117 Rebuild Granularity
 *
 * Sticky queue row that appears at the top of the pipeline panel during an
 * active rebuild. Shows which scope is rebuilding (Sync / Enrichment / All),
 * the current stage within that scope (e.g. "stage 3/5: Fast Catalogue"),
 * an overall progress percentage, and a Stop button.
 *
 * Designed to be rendered once per active rebuild; the parent component is
 * responsible for detecting an active rebuild (via `isPipelineRebuilding`)
 * and passing the relevant snapshot data as props.
 */
import type { RebuildScope } from '../../types';

export interface RebuildingRowProps {
  /** Which rebuild scope is currently active. */
  scope: RebuildScope;
  /** 0-based index of the stage currently running within the scope. */
  currentStageIndex: number;
  /** Total number of stages in this scope. */
  totalStagesInScope: number;
  /** Human-readable label for the current stage (e.g. "Fast Catalogue"). */
  currentStageLabel: string;
  /** Overall rebuild progress as a 0–100 integer. */
  percent: number;
  /** Called when the user presses the Stop button. */
  onStop: () => void;
}

const SCOPE_LABEL: Record<RebuildScope, string> = {
  sync:       'Rebuilding Sync',
  enrichment: 'Rebuilding Enrichment',
  all:        'Rebuilding All',
};

export function RebuildingRow({
  scope,
  currentStageIndex,
  totalStagesInScope,
  currentStageLabel,
  percent,
  onStop,
}: RebuildingRowProps) {
  const label = SCOPE_LABEL[scope];

  return (
    <div className="flex items-center gap-3 px-3 py-2 bg-blue-500/10 border border-blue-500/20 rounded-md text-sm">
      {/* Left: scope + stage info */}
      <div className="flex-1 min-w-0">
        <span className="font-medium text-blue-400">{label}</span>
        <span className="text-text-muted ml-2">
          {`stage ${Math.max(1, currentStageIndex + 1)}/${totalStagesInScope}: ${currentStageLabel}`}
        </span>
      </div>

      {/* Center: percentage */}
      <span className="text-blue-300 font-mono text-xs tabular-nums shrink-0">
        {`${Math.round(percent)}%`}
      </span>

      {/* Right: Stop button */}
      <button
        type="button"
        aria-label="Stop rebuild"
        className="shrink-0 px-2 py-0.5 rounded border border-blue-500/40 text-blue-300 text-xs hover:bg-blue-500/20 transition-colors"
        onClick={onStop}
      >
        Stop
      </button>
    </div>
  );
}
