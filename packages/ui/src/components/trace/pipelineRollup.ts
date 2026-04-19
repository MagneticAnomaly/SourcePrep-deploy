import type { EnrichmentStage } from './GraphEnrichmentPipeline';

export interface GroupRollup {
  state: 'complete' | 'disabled' | 'idle' | 'running' | 'error' | 'mixed';
  progress: number | undefined;
  stats: string;
}

/**
 * Compute a single summary for a group of 5 enrichment stages.
 * Rules (first match wins):
 *   1. all complete           → complete
 *   2. all disabled           → disabled
 *   3. all waiting/queued     → idle
 *   4. any running AND no error → running (averaged progress of running stages)
 *   5. any error              → error
 *   6. otherwise              → mixed (orange warning — expand to inspect)
 */
export function computeGroupRollup(stages: EnrichmentStage[]): GroupRollup {
  if (stages.every((s) => s.state === 'complete')) {
    return { state: 'complete', progress: undefined, stats: 'complete' };
  }
  if (stages.every((s) => s.state === 'disabled')) {
    return { state: 'disabled', progress: undefined, stats: 'disabled' };
  }
  if (stages.every((s) => s.state === 'waiting' || s.state === 'queued')) {
    return { state: 'idle', progress: undefined, stats: `${stages.length} stages · idle` };
  }

  const hasError = stages.some((s) => s.state === 'error');
  const runningIndex = stages.findIndex((s) => s.state === 'running' || s.state === 'rerunning' || s.state === 'rebuilding');

  if (runningIndex >= 0 && !hasError) {
    const runningStages = stages.filter((s) => s.state === 'running' || s.state === 'rerunning' || s.state === 'rebuilding');
    const withProgress = runningStages.filter((s) => typeof s.progress === 'number');
    const avg = withProgress.length
      ? Math.round(withProgress.reduce((acc, s) => acc + (s.progress as number), 0) / withProgress.length)
      : undefined;
    return {
      state: 'running',
      progress: avg,
      stats: `running stage ${runningIndex + 1} of ${stages.length}`,
    };
  }

  if (hasError) {
    return { state: 'error', progress: undefined, stats: 'error — expand to inspect' };
  }

  return { state: 'mixed', progress: undefined, stats: 'mixed — expand to inspect' };
}
