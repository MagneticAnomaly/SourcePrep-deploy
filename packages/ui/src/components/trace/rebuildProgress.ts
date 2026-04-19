import type { BarrierStatus } from '../../types';

export interface RebuildStageSnapshot {
  state: string;       // StageState from GraphEnrichmentPipeline — kept as string to avoid circular imports
  progress: number | undefined;
}

/** True iff the pipeline is in a full-rebuild run right now. */
export function isPipelineRebuilding(barrier: BarrierStatus | undefined): boolean {
  return Boolean(barrier?.active && barrier?.reason === 'rebuild');
}

/**
 * Per-stage contribution to the overall rebuild bar.
 * - complete → 100 (final green)
 * - rebuilding → clamped stage.progress (or 0 if undefined)
 * - anything else → 0 (queued / waiting / idle count as not-yet-started)
 */
export function perStageRebuildPercent(stage: RebuildStageSnapshot): number {
  if (stage.state === 'complete') return 100;
  if (stage.state === 'rebuilding') {
    const p = stage.progress;
    if (typeof p !== 'number' || Number.isNaN(p)) return 0;
    return Math.min(100, Math.max(0, p));
  }
  return 0;
}

/** Aggregate: average of per-stage percentages, rounded to an integer 0-100. */
export function computeOverallRebuildPercent(stages: RebuildStageSnapshot[]): number {
  if (stages.length === 0) return 0;
  const sum = stages.reduce((acc, s) => acc + perStageRebuildPercent(s), 0);
  return Math.round(sum / stages.length);
}
