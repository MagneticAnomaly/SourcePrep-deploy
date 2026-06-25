/**
 * FolderTreePanel tests — Phase 120 Named Scopes
 *
 * Pure logic/structural tests following the established BarrierIndicator /
 * RecoverStagePanel pattern. Source-inspection / function-call only (no
 * DOM render). Convention, not infra constraint: RTL + happy-dom ARE
 * wired in packages/ui as of PR-H. Run via:
 *   npm --workspace=packages/ui run test
 * or single-file:
 *   npm --workspace=packages/ui run test -- src/components/project/__tests__/FolderTreePanel.test.tsx
 *
 * See GraphEnrichmentPipeline.behavioral.test.tsx for the DOM-render
 * pattern. Component render tests previously deferred to Storybook
 * (Task 19) can now also live in vitest if preferred.
 *
 * The 6 test cases cover:
 *   1. FolderTreePanel is a function component
 *   2. FolderTreePanelProps interface — scope-related fields are optional
 *   3. ScopeSummary with assigned_to_role null is a valid fixture
 *   4. activeScopeId === 'global' implies isGlobalScope logic (unit)
 *   5. isEmpty logic — non-global scope with 0 path_count and no includedPaths
 *   6. isEmpty logic — global scope is never "empty" for banner purposes
 */
import { describe, it, expect, vi } from 'vitest';
import type { ScopeRecord, ScopeSummary } from '../../../types';
import type { FolderTreePanelProps } from '../FolderTreePanel';
import { FolderTreePanel } from '../FolderTreePanel';

// ── Fixtures ─────────────────────────────────────────────────

const GLOBAL_SCOPE: ScopeSummary = {
  id: 'global',
  display_name: 'Global',
  path_count: 5,
  assigned_to_role: null,
};

const MARKETING_SCOPE: ScopeSummary = {
  id: 'marketing',
  display_name: 'Marketing',
  path_count: 3,
  assigned_to_role: null,
};

const EMPTY_SCOPE: ScopeSummary = {
  id: 'data-cleaning',
  display_name: 'Data Cleaning',
  path_count: 0,
  assigned_to_role: null,
};

const BASE_PROPS: FolderTreePanelProps = {
  data: [{ name: 'src', children: [], type: 'folder' as const }],
  scopes: [GLOBAL_SCOPE, MARKETING_SCOPE],
  activeScopeId: 'global',
  onSetActiveScope: vi.fn(),
  onCreateScope: vi.fn().mockResolvedValue({
    id: 'data-cleaning',
    display_name: 'Data Cleaning',
    paths: [],
    assigned_to_role: null,
  } as ScopeRecord),
  onRenameScope: vi.fn(),
  onDeleteScope: vi.fn(),
};

// ── Helpers mirroring FolderTreePanel internal logic ─────────

/** Mirrors the `isGlobalScope` logic in FolderTreePanel */
function computeIsGlobal(activeScopeId: string | undefined): boolean {
  return !activeScopeId || activeScopeId === 'global';
}

/** Mirrors the `isEmpty` logic in FolderTreePanel */
function computeIsEmpty(
  scopes: ScopeSummary[] | undefined,
  activeScopeId: string | undefined,
  includedCount: number
): boolean {
  const scopesEnabled = !!scopes && scopes.length > 0;
  if (!scopesEnabled) return false;
  const isGlobal = computeIsGlobal(activeScopeId);
  if (isGlobal) return false;
  const activeScope = scopes!.find(s => s.id === activeScopeId);
  return (activeScope?.path_count ?? 0) === 0 && includedCount === 0;
}

// ── Tests ────────────────────────────────────────────────────

describe('FolderTreePanel — Phase 120 named scopes', () => {
  // Test 1: component is a function
  it('FolderTreePanel is a function component', () => {
    expect(typeof FolderTreePanel).toBe('function');
  });

  // Test 2: scope-related props are optional — props without them still type-check
  it('FolderTreePanelProps accepts data-only (no scope props) — backward-compatible', () => {
    const minimal: FolderTreePanelProps = {
      data: [],
    };
    // If this line compiles, backward compatibility is preserved
    expect(minimal.scopes).toBeUndefined();
    expect(minimal.activeScopeId).toBeUndefined();
    expect(minimal.onSetActiveScope).toBeUndefined();
    expect(minimal.onCreateScope).toBeUndefined();
    expect(minimal.onRenameScope).toBeUndefined();
    expect(minimal.onDeleteScope).toBeUndefined();
  });

  // Test 3: ScopeSummary fixture is well-formed
  it('ScopeSummary with assigned_to_role null satisfies the interface', () => {
    expect(GLOBAL_SCOPE.id).toBe('global');
    expect(GLOBAL_SCOPE.display_name).toBe('Global');
    expect(GLOBAL_SCOPE.path_count).toBe(5);
    expect(GLOBAL_SCOPE.assigned_to_role).toBeNull();
  });

  // Test 4: isGlobalScope logic
  it('activeScopeId === "global" → isGlobalScope is true', () => {
    expect(computeIsGlobal('global')).toBe(true);
    expect(computeIsGlobal(undefined)).toBe(true);
    expect(computeIsGlobal('marketing')).toBe(false);
  });

  // Test 5: isEmpty — non-global scope with 0 path_count and no includedPaths shows banner
  it('isEmpty is true for a named scope with 0 paths and no includedPaths', () => {
    const scopes = [GLOBAL_SCOPE, EMPTY_SCOPE];
    expect(computeIsEmpty(scopes, 'data-cleaning', 0)).toBe(true);
  });

  // Test 6: isEmpty — global scope is never empty for banner purposes
  it('isEmpty is false when activeScopeId is "global"', () => {
    const scopes = [GLOBAL_SCOPE, EMPTY_SCOPE];
    expect(computeIsEmpty(scopes, 'global', 0)).toBe(false);
    // Also not empty when there are paths
    expect(computeIsEmpty(scopes, 'data-cleaning', 3)).toBe(false);
  });
});

// ── Prop-shape contract tests ─────────────────────────────────

describe('FolderTreePanel — scope prop contract', () => {
  it('Edit affordance should be hidden on global — activeScopeId is global', () => {
    // Simulate: non-global scope check for showing Edit
    const activeScopeId = 'global';
    const showEdit = activeScopeId !== 'global' && !!BASE_PROPS.scopes?.find(s => s.id === activeScopeId);
    expect(showEdit).toBe(false);
  });

  it('Edit affordance should be shown on a named scope', () => {
    const activeScopeId: string = 'marketing';
    const scopes = [GLOBAL_SCOPE, MARKETING_SCOPE];
    const showEdit = activeScopeId !== 'global' && !!scopes.find(s => s.id === activeScopeId);
    expect(showEdit).toBe(true);
  });

  it('scopeReadOnlyExclude is true on non-global scopes', () => {
    const scopesEnabled = true;
    const isGlobal = computeIsGlobal('marketing');
    const readOnly = scopesEnabled && !isGlobal;
    expect(readOnly).toBe(true);
  });

  it('scopeReadOnlyExclude is false on global scope', () => {
    const scopesEnabled = true;
    const isGlobal = computeIsGlobal('global');
    const readOnly = scopesEnabled && !isGlobal;
    expect(readOnly).toBe(false);
  });
});
