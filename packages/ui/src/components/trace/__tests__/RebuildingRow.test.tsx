/**
 * RebuildingRow tests
 *
 * Pure logic/unit tests following the ProvenanceChip.test.tsx pattern —
 * no DOM rendering, no @testing-library/react. These typecheck and run
 * with vitest. Component render tests live in Storybook.
 *
 * The 4 test cases cover:
 *   1. scope="sync"        → renders scope label "Rebuilding Sync", stage 3/5, label, 38%
 *   2. scope="enrichment"  → renders "Rebuilding Enrichment"
 *   3. scope="all"         → renders "Rebuilding All"
 *   4. Stop button         → finds button in tree, calls onClick, onStop is invoked
 */
import { describe, it, expect, vi } from 'vitest';
import { RebuildingRow } from '../RebuildingRow';
import type { RebuildScope } from '../../../types';

// ── Helpers ───────────────────────────────────────────────────

/** Recursively stringify a React element tree for text-content assertions. */
function treeText(node: unknown): string {
  return JSON.stringify(node);
}

/** Walk the element tree to find the first node where type === 'button'. */
function findButton(node: unknown): { type: string; props: Record<string, unknown> } | null {
  if (!node || typeof node !== 'object') return null;
  const el = node as { type?: unknown; props?: Record<string, unknown> };
  if (el.type === 'button') return el as { type: string; props: Record<string, unknown> };
  if (el.props) {
    const children = el.props.children;
    if (Array.isArray(children)) {
      for (const child of children) {
        const found = findButton(child);
        if (found) return found;
      }
    } else {
      const found = findButton(children);
      if (found) return found;
    }
  }
  return null;
}

// ── RebuildingRow ─────────────────────────────────────────────

describe('RebuildingRow', () => {
  // Test 1: sync scope — renders scope label, stage 3/5, stage name, 38%
  it('renders scope "Rebuilding Sync", stage 3/5, stage label, and 38% for sync scope', () => {
    const result = RebuildingRow({
      scope: 'sync' as RebuildScope,
      currentStageIndex: 2,
      totalStagesInScope: 5,
      currentStageLabel: 'Fast Catalogue',
      percent: 38,
      onStop: vi.fn(),
    }) as any;

    expect(result).not.toBeNull();
    expect(result.type).toBe('div');

    const text = treeText(result);
    expect(text).toMatch(/Rebuilding Sync/i);
    expect(text).toMatch(/stage 3\/5: Fast Catalogue/);
    expect(text).toMatch(/38%/);
  });

  // Test 2: enrichment scope → "Rebuilding Enrichment"
  it('renders "Rebuilding Enrichment" for enrichment scope', () => {
    const result = RebuildingRow({
      scope: 'enrichment' as RebuildScope,
      currentStageIndex: 0,
      totalStagesInScope: 3,
      currentStageLabel: 'Epistemic Enrichment',
      percent: 20,
      onStop: vi.fn(),
    }) as any;

    expect(result).not.toBeNull();
    const text = treeText(result);
    expect(text).toMatch(/Rebuilding Enrichment/i);
  });

  // Test 3: all scope → "Rebuilding All"
  it('renders "Rebuilding All" for all scope', () => {
    const result = RebuildingRow({
      scope: 'all' as RebuildScope,
      currentStageIndex: 11,
      totalStagesInScope: 15,
      currentStageLabel: 'Atlas',
      percent: 60,
      onStop: vi.fn(),
    }) as any;

    expect(result).not.toBeNull();
    const text = treeText(result);
    expect(text).toMatch(/Rebuilding All/i);
  });

  // Test 4: Stop button — find button in tree and invoke its onClick; onStop called
  it('calls onStop when the Stop button is clicked', () => {
    const onStop = vi.fn();
    const result = RebuildingRow({
      scope: 'sync' as RebuildScope,
      currentStageIndex: 0,
      totalStagesInScope: 5,
      currentStageLabel: 'Structural',
      percent: 25,
      onStop,
    }) as any;

    expect(result).not.toBeNull();
    const btn = findButton(result);
    expect(btn).not.toBeNull();
    expect(btn!.props['aria-label']).toBe('Stop rebuild');
    // Invoke the click handler directly
    (btn!.props.onClick as () => void)();
    expect(onStop).toHaveBeenCalledOnce();
  });
});
