/**
 * RebuildDropdown tests
 *
 * Pure logic/unit tests following the RecoverStagePanel pattern —
 * no DOM rendering, no @testing-library/react. These typecheck and run
 * with vitest. Component render tests (open/close toggle, keyboard
 * navigation, outside-click dismiss) live in Storybook.
 *
 * Why no DOM tests? The repo uses vitest without jsdom configured and
 * has no @testing-library/react installed. The RecoverStagePanel pattern
 * (see RecoverStagePanel.test.tsx) demonstrates the convention: export
 * pure constants/helpers from the module and test those directly.
 * Interactive behaviour is validated in Storybook stories.
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
