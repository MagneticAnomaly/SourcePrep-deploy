import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import type { RunningTask, SwarmPhasesBreakdown } from '../../types';
import { TASK_LABELS } from '../../types';

export interface SwarmActivityPanelProps {
  runningTasks: RunningTask[];
  className?: string;
}

const ROLE_ROWS: Array<{
  key: keyof SwarmPhasesBreakdown;
  label: string;
  color: string;
}> = [
  { key: 'coordinator', label: 'Coordinator', color: 'text-amber-300' },
  { key: 'workers', label: 'Workers', color: 'text-blue-300' },
  { key: 'synthesizer', label: 'Synthesizer', color: 'text-purple-300' },
];

/**
 * Phase 119 — three-phase swarm role rows for a single running task.
 * Empty role buckets are suppressed so audit-style stages (no
 * coordinator/synthesizer) don't render fake rows.
 *
 * Exported separately so other developer-mode panels can reuse it.
 */
export function SwarmRoleRows({ phases }: { phases: SwarmPhasesBreakdown }) {
  const visible = ROLE_ROWS.filter(r => (phases[r.key]?.active ?? 0) > 0);
  if (visible.length === 0) return null;
  return (
    <div className="space-y-0.5" data-testid="swarm-role-rows">
      {visible.map(r => {
        const bucket = phases[r.key];
        return (
          <div
            key={r.key}
            className="flex items-center gap-1.5 text-[10px] text-text-muted"
          >
            <Loader2 className="w-2 h-2 animate-spin shrink-0" />
            <span className={cn('font-medium shrink-0', r.color)}>{r.label}</span>
            <span className="shrink-0 tabular-nums">×{bucket.active}</span>
            {bucket.model && (
              <span className="truncate text-text-muted/70">{bucket.model}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

/**
 * Phase 119 developer-mode panel — lists ALL running swarms with their
 * coordinator/worker/synthesizer breakdown.
 *
 * This used to be inlined in the AI Gateway sidebar, but per-role rows
 * are debugging detail, not status information for end users.  The
 * sidebar keeps the high-level "Swarm" badge + worker count; the
 * per-role rows now live in the developer popover behind the wrench.
 */
export function SwarmActivityPanel({
  runningTasks,
  className,
}: SwarmActivityPanelProps) {
  const swarming = runningTasks.filter(rt => rt.is_swarm && rt.swarm_phases);
  if (swarming.length === 0) {
    return (
      <p
        className={cn('text-[11px] text-text-muted italic', className)}
        data-testid="swarm-activity-panel-empty"
      >
        No active swarms.
      </p>
    );
  }
  return (
    <div
      className={cn('space-y-2', className)}
      data-testid="swarm-activity-panel"
    >
      {swarming.map(rt => {
        const taskLabel = TASK_LABELS[rt.task_id] ?? rt.task_id;
        const projectLabel = rt.project_name ?? rt.project_id;
        return (
          <div
            key={`${rt.project_id}-${rt.task_id}-${rt.stage}`}
            className="rounded border border-border bg-surface-raised/40 px-2 py-1.5"
          >
            <div className="flex items-center gap-1.5 text-[11px] font-medium text-text">
              <Loader2 className="w-2.5 h-2.5 animate-spin text-blue-400 shrink-0" />
              <span className="truncate">{projectLabel}</span>
              <span className="text-text-muted/60 shrink-0">/</span>
              <span className="text-text-muted truncate">{taskLabel}</span>
              {(rt.concurrent_workers ?? 1) > 1 && (
                <span className="ml-auto inline-flex items-center px-1 rounded text-[9px] font-bold bg-purple-500/20 text-purple-300 shrink-0">
                  {rt.concurrent_workers}×Swarm
                </span>
              )}
            </div>
            <div className="mt-1 ml-4">
              {rt.swarm_phases && <SwarmRoleRows phases={rt.swarm_phases} />}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default SwarmActivityPanel;
