import { describe, it, expect } from 'vitest';
import {
  isPipelineRebuilding,
  perStageRebuildPercent,
  computeOverallRebuildPercent,
  type RebuildStageSnapshot,
} from '../rebuildProgress';
import type { BarrierStatus } from '../../../types';

describe('isPipelineRebuilding', () => {
  it('returns true when barrier is active and reason is rebuild', () => {
    const barrier: BarrierStatus = { active: true, reason: 'rebuild' };
    expect(isPipelineRebuilding(barrier)).toBe(true);
  });

  it('returns false when barrier is inactive', () => {
    const barrier: BarrierStatus = { active: false, reason: 'rebuild' };
    expect(isPipelineRebuilding(barrier)).toBe(false);
  });

  it('returns false when barrier reason is not rebuild', () => {
    const barrier: BarrierStatus = { active: true, reason: 'enrichment_reset' };
    expect(isPipelineRebuilding(barrier)).toBe(false);
  });

  it('returns false when barrier is undefined', () => {
    expect(isPipelineRebuilding(undefined)).toBe(false);
  });
});

describe('perStageRebuildPercent', () => {
  it('returns 100 for a completed stage', () => {
    const s: RebuildStageSnapshot = { state: 'complete', progress: undefined };
    expect(perStageRebuildPercent(s)).toBe(100);
  });

  it('returns the stage progress when rebuilding', () => {
    const s: RebuildStageSnapshot = { state: 'rebuilding', progress: 42 };
    expect(perStageRebuildPercent(s)).toBe(42);
  });

  it('returns 0 when rebuilding but progress is undefined', () => {
    const s: RebuildStageSnapshot = { state: 'rebuilding', progress: undefined };
    expect(perStageRebuildPercent(s)).toBe(0);
  });

  it('clamps progress into the 0-100 range', () => {
    expect(perStageRebuildPercent({ state: 'rebuilding', progress: 150 })).toBe(100);
    expect(perStageRebuildPercent({ state: 'rebuilding', progress: -5 })).toBe(0);
  });

  it('returns 0 for queued / waiting stages', () => {
    expect(perStageRebuildPercent({ state: 'queued', progress: undefined })).toBe(0);
    expect(perStageRebuildPercent({ state: 'waiting', progress: undefined })).toBe(0);
    expect(perStageRebuildPercent({ state: 'idle', progress: undefined })).toBe(0);
  });
});

describe('computeOverallRebuildPercent', () => {
  it('returns 0 for an empty list', () => {
    expect(computeOverallRebuildPercent([])).toBe(0);
  });

  it('averages per-stage percentages', () => {
    const stages: RebuildStageSnapshot[] = [
      { state: 'complete', progress: undefined },    // 100
      { state: 'complete', progress: undefined },    // 100
      { state: 'rebuilding', progress: 40 },         //  40
      { state: 'queued', progress: undefined },      //   0
      { state: 'queued', progress: undefined },      //   0
    ];
    // (100 + 100 + 40 + 0 + 0) / 5 = 48
    expect(computeOverallRebuildPercent(stages)).toBe(48);
  });

  it('returns 100 when every stage is complete', () => {
    const stages: RebuildStageSnapshot[] = [
      { state: 'complete', progress: undefined },
      { state: 'complete', progress: undefined },
    ];
    expect(computeOverallRebuildPercent(stages)).toBe(100);
  });

  it('rounds to an integer percent', () => {
    // (33 + 0 + 0) / 3 = 11
    const stages: RebuildStageSnapshot[] = [
      { state: 'rebuilding', progress: 33 },
      { state: 'queued', progress: undefined },
      { state: 'queued', progress: undefined },
    ];
    expect(computeOverallRebuildPercent(stages)).toBe(11);
  });
});
