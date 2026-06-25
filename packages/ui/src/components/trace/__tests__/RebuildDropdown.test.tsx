/**
 * RebuildDropdown tests
 *
 * Pure logic/unit tests following the RecoverStagePanel pattern —
 * source-inspection / function-call only (no DOM render). Convention,
 * not infra constraint: vitest + happy-dom + @testing-library/react ARE
 * wired in packages/ui as of PR-H (commits b3ca8d5f + dd1ff75c).
 *
 * This file stays source-inspection because the contract under test is
 * the exported pure helpers / option-list shape — RTL render would add
 * runtime cost without strengthening the pin. For interactive contracts
 * (open/close toggle, keyboard navigation, outside-click dismiss) use
 * the GraphEnrichmentPipeline.behavioral.test.tsx pattern or Storybook
 * play() functions.
 *
 * The 5 test cases cover:
 *   1. PRIMARY_SCOPE — locks in "clicking Rebuild alone = all" contract
 *   2. MENU_ITEMS — exactly 3 items in the correct scope order
 *   3. MENU_ITEMS sync label — matches /rebuild sync/i
 *   4. MENU_ITEMS enrichment label — matches /rebuild enrichment/i
 *   5. RebuildDropdown — is a function component (typeof check)
 */
import { describe, it, expect } from 'vitest';
import { RebuildDropdown, MENU_ITEMS, PRIMARY_SCOPE } from '../RebuildDropdown';

// ── Test 1: PRIMARY_SCOPE contract ────────────────────────────

describe('PRIMARY_SCOPE', () => {
  it('is "all" — clicking the primary Rebuild button triggers a full rebuild', () => {
    expect(PRIMARY_SCOPE).toBe('all');
  });
});

// ── Test 2-4: MENU_ITEMS content ─────────────────────────────

describe('MENU_ITEMS', () => {
  it('contains exactly 3 items with scopes ["sync", "enrichment", "all"] in order', () => {
    expect(MENU_ITEMS).toHaveLength(3);
    expect(MENU_ITEMS.map((i) => i.scope)).toEqual(['sync', 'enrichment', 'all']);
  });

  it('sync item label matches /rebuild sync/i', () => {
    const item = MENU_ITEMS.find((i) => i.scope === 'sync');
    expect(item).toBeDefined();
    expect(item!.label).toMatch(/rebuild sync/i);
  });

  it('enrichment item label matches /rebuild enrichment/i', () => {
    const item = MENU_ITEMS.find((i) => i.scope === 'enrichment');
    expect(item).toBeDefined();
    expect(item!.label).toMatch(/rebuild enrichment/i);
  });
});

// ── Test 5: Component structural check ───────────────────────

describe('RebuildDropdown', () => {
  it('is a function component', () => {
    expect(typeof RebuildDropdown).toBe('function');
  });
});
