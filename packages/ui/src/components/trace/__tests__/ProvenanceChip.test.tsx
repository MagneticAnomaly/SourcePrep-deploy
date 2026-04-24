/**
 * ProvenanceChip tests
 *
 * Pure logic/unit tests following the BarrierIndicator.test.tsx pattern —
 * no DOM rendering, no @testing-library/react. These typecheck and run
 * with vitest once it is wired into the monorepo. Component render tests
 * live in Storybook.
 *
 * The 5 test cases cover:
 *   1. state=match + null chip_text → returns null
 *   2. state=drift → renders a button; onClick calls onRebuild with correct scope
 *   3. state=recovered_stub → chip_text includes "provenance unknown"
 *   4. state=recovered_soft → renders a span (not a button); no onClick handler
 *   5. provenance is undefined/missing → returns null
 */
import { describe, it, expect, vi } from 'vitest';
import { ProvenanceChip } from '../ProvenanceChip';
import type { StageRebuildProvenance } from '../../../types';

// ── Fixtures ─────────────────────────────────────────────────

const MATCH_PROVENANCE: StageRebuildProvenance = {
  state: 'match',
  manifest_model: { provider: 'openai', model_name: 'gpt-4o' },
  current_config_model: { provider: 'openai', model_name: 'gpt-4o' },
  chip_text: null,
  rebuild_scope: null,
};

const DRIFT_PROVENANCE: StageRebuildProvenance = {
  state: 'drift',
  manifest_model: { provider: 'openai', model_name: 'gpt-4o' },
  current_config_model: { provider: 'anthropic', model_name: 'claude-3-5-sonnet' },
  chip_text: 'gpt-4o → claude-3-5-sonnet',
  rebuild_scope: 'enrichment',
};

const STUB_PROVENANCE: StageRebuildProvenance = {
  state: 'recovered_stub',
  manifest_model: null,
  current_config_model: { provider: 'openai', model_name: 'gpt-4o' },
  chip_text: 'provenance unknown',
  rebuild_scope: 'enrichment',
};

const SOFT_PROVENANCE: StageRebuildProvenance = {
  state: 'recovered_soft',
  manifest_model: { provider: 'openai', model_name: 'gpt-4o-mini' },
  current_config_model: { provider: 'openai', model_name: 'gpt-4o' },
  chip_text: 'rebuilt with fallback model',
  rebuild_scope: 'enrichment',
};

// ── ProvenanceChip ───────────────────────────────────────────

describe('ProvenanceChip', () => {
  // Test 1: match + null chip_text → null
  it('returns null when state is match and chip_text is null', () => {
    const result = ProvenanceChip({ provenance: MATCH_PROVENANCE });
    expect(result).toBeNull();
  });

  // Test 2: drift → button that calls onRebuild with correct scope on click
  it('renders a button for drift state that calls onRebuild with scope on click', () => {
    const onRebuild = vi.fn();
    const result = ProvenanceChip({ provenance: DRIFT_PROVENANCE, onRebuild }) as any;
    expect(result).not.toBeNull();
    expect(result.type).toBe('button');
    result.props.onClick();
    expect(onRebuild).toHaveBeenCalledWith('enrichment');
  });

  // Test 3: recovered_stub → chip_text contains "provenance unknown"
  it('chip_text includes "provenance unknown" for recovered_stub state', () => {
    const result = ProvenanceChip({ provenance: STUB_PROVENANCE }) as any;
    expect(result).not.toBeNull();
    const text = JSON.stringify(result.props.children);
    expect(text).toMatch(/provenance unknown/i);
  });

  // Test 4: recovered_soft → span (not a button); no onClick handler
  it('renders a span (not a button) for recovered_soft — no click handler', () => {
    const result = ProvenanceChip({ provenance: SOFT_PROVENANCE }) as any;
    expect(result).not.toBeNull();
    expect(result.type).toBe('span');
    expect(result.props.onClick).toBeUndefined();
  });

  // Test 5: missing state → null
  it('returns null when provenance is undefined', () => {
    const result = ProvenanceChip({ provenance: undefined });
    expect(result).toBeNull();
  });
});
