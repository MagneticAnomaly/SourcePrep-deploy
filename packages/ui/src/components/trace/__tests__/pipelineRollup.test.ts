import { describe, it, expect } from 'vitest';
import { computeGroupRollup } from '../pipelineRollup';
import type { EnrichmentStage, EnrichmentStageId } from '../GraphEnrichmentPipeline';
import { Circle } from 'lucide-react';

function stage(id: EnrichmentStageId, state: EnrichmentStage['state'], progress?: number): EnrichmentStage {
  return { id, label: id, icon: Circle, state, progress };
}

describe('computeGroupRollup', () => {
  it('returns complete when all five are complete', () => {
    const stages: EnrichmentStage[] = [
      stage('structural', 'complete'),
      stage('inferred_edges', 'complete'),
      stage('catalogue', 'complete'),
      stage('validation', 'complete'),
      stage('knowledge', 'complete'),
    ];
    const r = computeGroupRollup(stages);
    expect(r.state).toBe('complete');
    expect(r.progress).toBeUndefined();
  });

  it('returns disabled when all five are disabled', () => {
    const stages: EnrichmentStage[] = [
      stage('enrichment', 'disabled'),
      stage('group_reasoning', 'disabled'),
      stage('clustering', 'disabled'),
      stage('deepening', 'disabled'),
      stage('deep_knowledge', 'disabled'),
    ];
    expect(computeGroupRollup(stages).state).toBe('disabled');
  });

  it('returns idle when all five are waiting/queued', () => {
    const stages: EnrichmentStage[] = [
      stage('atlas', 'waiting'),
      stage('rules', 'waiting'),
      stage('concepts', 'queued'),
      stage('audit', 'queued'),
      stage('antibodies', 'waiting'),
    ];
    expect(computeGroupRollup(stages).state).toBe('idle');
  });

  it('returns running with averaged progress when any stage is running and no errors', () => {
    const stages: EnrichmentStage[] = [
      stage('structural', 'complete'),
      stage('inferred_edges', 'complete'),
      stage('catalogue', 'running', 40),
      stage('validation', 'waiting'),
      stage('knowledge', 'waiting'),
    ];
    const r = computeGroupRollup(stages);
    expect(r.state).toBe('running');
    expect(r.progress).toBe(40);
    expect(r.stats).toMatch(/running stage 3 of 5/);
  });

  it('returns running even when most are already complete', () => {
    const stages: EnrichmentStage[] = [
      stage('structural', 'complete'),
      stage('inferred_edges', 'complete'),
      stage('catalogue', 'complete'),
      stage('validation', 'running', 10),
      stage('knowledge', 'waiting'),
    ];
    expect(computeGroupRollup(stages).state).toBe('running');
  });

  it('returns error when any stage has error (no running)', () => {
    const stages: EnrichmentStage[] = [
      stage('structural', 'complete'),
      stage('inferred_edges', 'error'),
      stage('catalogue', 'waiting'),
      stage('validation', 'waiting'),
      stage('knowledge', 'waiting'),
    ];
    expect(computeGroupRollup(stages).state).toBe('error');
  });

  it('prefers running over error per rule order when both present', () => {
    // Rule 4 requires "no error" — so this case should fall through to rule 5 (error).
    const stages: EnrichmentStage[] = [
      stage('structural', 'running', 50),
      stage('inferred_edges', 'error'),
      stage('catalogue', 'waiting'),
      stage('validation', 'waiting'),
      stage('knowledge', 'waiting'),
    ];
    expect(computeGroupRollup(stages).state).toBe('error');
  });

  it('returns mixed for everything else (stale + complete + waiting, no running, no error)', () => {
    const stages: EnrichmentStage[] = [
      stage('structural', 'complete'),
      stage('inferred_edges', 'stale'),
      stage('catalogue', 'complete'),
      stage('validation', 'waiting'),
      stage('knowledge', 'complete'),
    ];
    const r = computeGroupRollup(stages);
    expect(r.state).toBe('mixed');
    expect(r.stats).toMatch(/expand/i);
  });

  it('returns mixed for all-stale (no explicit all-stale rule)', () => {
    const stages: EnrichmentStage[] = [
      stage('atlas', 'stale'),
      stage('rules', 'stale'),
      stage('concepts', 'stale'),
      stage('audit', 'stale'),
      stage('antibodies', 'stale'),
    ];
    expect(computeGroupRollup(stages).state).toBe('mixed');
  });
});
