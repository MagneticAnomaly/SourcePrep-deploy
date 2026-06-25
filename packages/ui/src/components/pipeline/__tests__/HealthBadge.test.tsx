/**
 * HealthBadge tests
 *
 * Pure logic/unit tests following the BarrierIndicator.test.tsx pattern —
 * source-inspection / function-call only (no DOM render). Convention,
 * not infra constraint: vitest + happy-dom + @testing-library/react ARE
 * wired in packages/ui as of PR-H (commits b3ca8d5f + dd1ff75c). See
 * GraphEnrichmentPipeline.behavioral.test.tsx for the DOM-render pattern.
 *
 * The 5 test cases cover:
 *   1. computeHealthSummary — Healthy when no warnings
 *   2. computeHealthSummary — singular "1 warning" label
 *   3. computeHealthSummary — plural "N warnings" label
 *   4. computeHealthSummary — barrier + stuck_runs do not affect summary
 *   5. HealthBadge — is a function component
 */
import { describe, it, expect } from 'vitest';
import { computeHealthSummary, HealthBadge } from '../HealthBadge';
import type { PipelineHealth } from '../../../types';

const baseHealth: PipelineHealth = {
  project_id: 'p',
  barrier: { active: false },
  stages: [],
  stuck_runs: 0,
  warnings: [],
};

describe('computeHealthSummary', () => {
  it('returns Healthy when no warnings', () => {
    const s = computeHealthSummary(baseHealth);
    expect(s.ok).toBe(true);
    expect(s.warnCount).toBe(0);
    expect(s.label).toBe('Healthy');
  });

  it('returns "1 warning" (singular) for one warning', () => {
    const s = computeHealthSummary({ ...baseHealth, warnings: ['boom'] });
    expect(s.ok).toBe(false);
    expect(s.warnCount).toBe(1);
    expect(s.label).toBe('1 warning');
  });

  it('returns "3 warnings" (plural) for multiple', () => {
    const s = computeHealthSummary({
      ...baseHealth,
      warnings: ['a', 'b', 'c'],
    });
    expect(s.ok).toBe(false);
    expect(s.warnCount).toBe(3);
    expect(s.label).toBe('3 warnings');
  });

  it('counts only warnings array — barrier and stuck_runs do not affect summary', () => {
    const s = computeHealthSummary({
      ...baseHealth,
      barrier: { active: true, age_seconds: 7200 },
      stuck_runs: 5,
    });
    expect(s.ok).toBe(true);
    expect(s.label).toBe('Healthy');
  });
});

describe('HealthBadge', () => {
  it('is a function component', () => {
    expect(typeof HealthBadge).toBe('function');
  });
});
