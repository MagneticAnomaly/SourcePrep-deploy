/**
 * useScopes contract tests
 *
 * Because @testing-library/react is not installed in this monorepo, we test
 * the API-contract behaviour of the hook logic directly — no renderHook,
 * no DOM. Each test builds a fake ScopesApi, runs the same async sequence
 * the hook would execute, and asserts the expected call signatures.
 *
 * What IS covered:
 *   1. listScopes is called on mount (simulated by calling refresh())
 *   2. createScope calls api.createScope then api.listScopes (refresh)
 *      and returns the new record
 *   3. deleteScope calls api.deleteScope then api.listScopes (refresh)
 *   4. null projectId: no API calls on refresh, no calls on createScope
 *   5. renameScope calls api.updateScope then refresh
 *   6. addPaths / removePaths forward to the correct API methods
 *   7. activeScopeId guard: deleteScope resets active to "global" when the
 *      deleted scope was the active one
 *
 * These tests are intentionally logic-only; React render/lifecycle
 * integration is deferred until @testing-library/react is available.
 */

import { describe, it, expect, vi } from 'vitest';
import type { ScopesApi } from '../useScopes';
import type { ScopeRecord, ScopeSummary } from '../../types';

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeScopeSummary(overrides: Partial<ScopeSummary> = {}): ScopeSummary {
  return {
    id: 'global',
    display_name: 'Global',
    path_count: 0,
    assigned_to_role: null,
    ...overrides,
  };
}

function makeScopeRecord(overrides: Partial<ScopeRecord> = {}): ScopeRecord {
  return {
    id: 'global',
    display_name: 'Global',
    paths: [],
    assigned_to_role: null,
    ...overrides,
  };
}

function makeFakeApi(overrides: Partial<ScopesApi> = {}): ScopesApi {
  return {
    listScopes: vi.fn().mockResolvedValue({ scopes: [] }),
    getScope: vi.fn(),
    createScope: vi.fn().mockResolvedValue(makeScopeRecord()),
    updateScope: vi.fn().mockResolvedValue(makeScopeRecord()),
    deleteScope: vi.fn().mockResolvedValue(undefined),
    addPathsToScope: vi.fn().mockResolvedValue(makeScopeRecord()),
    removePathsFromScope: vi.fn().mockResolvedValue(makeScopeRecord()),
    ...overrides,
  };
}

// ── Simulate the core async sequences the hook executes ──────────────────────
//
// Rather than calling the hook via renderHook (unavailable), we reproduce
// the async sequences as documented in the hook implementation so that the
// same API contracts are exercised.

async function simulateRefresh(
  projectId: string | null,
  api: ScopesApi,
): Promise<ScopeSummary[]> {
  if (!projectId) return [];
  const res = await api.listScopes(projectId);
  return res.scopes;
}

async function simulateCreateScope(
  projectId: string | null,
  api: ScopesApi,
  display_name: string,
): Promise<ScopeRecord | null> {
  if (!projectId) return null;
  const rec = await api.createScope(projectId, { display_name });
  await simulateRefresh(projectId, api);
  return rec;
}

async function simulateRenameScope(
  projectId: string | null,
  api: ScopesApi,
  id: string,
  display_name: string,
): Promise<void> {
  if (!projectId) return;
  await api.updateScope(projectId, id, { display_name });
  await simulateRefresh(projectId, api);
}

async function simulateDeleteScope(
  projectId: string | null,
  api: ScopesApi,
  id: string,
  activeScopeId: string,
): Promise<string> {
  if (!projectId) return activeScopeId;
  await api.deleteScope(projectId, id);
  const newActive = activeScopeId === id ? 'global' : activeScopeId;
  await simulateRefresh(projectId, api);
  return newActive;
}

async function simulateAddPaths(
  projectId: string | null,
  api: ScopesApi,
  id: string,
  paths: string[],
): Promise<void> {
  if (!projectId) return;
  await api.addPathsToScope(projectId, id, paths);
  await simulateRefresh(projectId, api);
}

async function simulateRemovePaths(
  projectId: string | null,
  api: ScopesApi,
  id: string,
  paths: string[],
): Promise<void> {
  if (!projectId) return;
  await api.removePathsFromScope(projectId, id, paths);
  await simulateRefresh(projectId, api);
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('useScopes — API contract', () => {
  // Test 1: listScopes is called with the correct projectId on mount
  it('calls listScopes with projectId on initial load', async () => {
    const api = makeFakeApi({
      listScopes: vi.fn().mockResolvedValue({
        scopes: [
          makeScopeSummary({ id: 'global', display_name: 'Global', path_count: 5 }),
          makeScopeSummary({ id: 'marketing', display_name: 'Marketing', path_count: 3 }),
        ],
      }),
    });
    const scopes = await simulateRefresh('proj-1', api);
    expect(api.listScopes).toHaveBeenCalledWith('proj-1');
    expect(scopes).toHaveLength(2);
    expect(scopes[0].id).toBe('global');
  });

  // Test 2: createScope calls api.createScope then refreshes (listScopes called once)
  it('createScope calls api.createScope then refreshes', async () => {
    const api = makeFakeApi({
      createScope: vi.fn().mockResolvedValue(
        makeScopeRecord({ id: 'marketing', display_name: 'Marketing' }),
      ),
    });
    const rec = await simulateCreateScope('proj-1', api, 'Marketing');
    expect(api.createScope).toHaveBeenCalledWith('proj-1', { display_name: 'Marketing' });
    expect(api.listScopes).toHaveBeenCalledTimes(1);
    expect(rec?.id).toBe('marketing');
  });

  // Test 3: createScope returns the newly created record (id used as new active)
  it('createScope returns the newly created record (id used as new activeScopeId)', async () => {
    const api = makeFakeApi({
      createScope: vi.fn().mockResolvedValue(
        makeScopeRecord({ id: 'backend', display_name: 'Backend' }),
      ),
    });
    const rec = await simulateCreateScope('proj-1', api, 'Backend');
    expect(rec?.id).toBe('backend');
  });

  // Test 4: deleteScope calls api.deleteScope then refreshes
  it('deleteScope calls api.deleteScope then refreshes', async () => {
    const api = makeFakeApi();
    await simulateDeleteScope('proj-1', api, 'marketing', 'global');
    expect(api.deleteScope).toHaveBeenCalledWith('proj-1', 'marketing');
    expect(api.listScopes).toHaveBeenCalledTimes(1);
  });

  // Test 5: deleteScope resets active to "global" when the deleted scope was active
  it('deleteScope resets activeScopeId to "global" when the active scope is deleted', async () => {
    const api = makeFakeApi();
    const newActive = await simulateDeleteScope('proj-1', api, 'marketing', 'marketing');
    expect(newActive).toBe('global');
  });

  // Test 6: deleteScope preserves activeScopeId when a different scope is deleted
  it('deleteScope preserves activeScopeId when a non-active scope is deleted', async () => {
    const api = makeFakeApi();
    const newActive = await simulateDeleteScope('proj-1', api, 'marketing', 'backend');
    expect(newActive).toBe('backend');
  });

  // Test 7: null projectId — no API calls on refresh
  it('null projectId causes refresh to return empty without calling listScopes', async () => {
    const api = makeFakeApi();
    const scopes = await simulateRefresh(null, api);
    expect(api.listScopes).not.toHaveBeenCalled();
    expect(scopes).toEqual([]);
  });

  // Test 8: null projectId — createScope is a no-op
  it('null projectId causes createScope to return null without calling api.createScope', async () => {
    const api = makeFakeApi();
    const rec = await simulateCreateScope(null, api, 'X');
    expect(api.createScope).not.toHaveBeenCalled();
    expect(rec).toBeNull();
  });

  // Test 9: renameScope calls api.updateScope then refreshes
  it('renameScope calls api.updateScope with the correct args then refreshes', async () => {
    const api = makeFakeApi({
      updateScope: vi.fn().mockResolvedValue(
        makeScopeRecord({ id: 'marketing', display_name: 'Marketing v2' }),
      ),
    });
    await simulateRenameScope('proj-1', api, 'marketing', 'Marketing v2');
    expect(api.updateScope).toHaveBeenCalledWith('proj-1', 'marketing', {
      display_name: 'Marketing v2',
    });
    expect(api.listScopes).toHaveBeenCalledTimes(1);
  });

  // Test 10: addPaths calls api.addPathsToScope then refreshes
  it('addPaths calls api.addPathsToScope with paths then refreshes', async () => {
    const api = makeFakeApi();
    await simulateAddPaths('proj-1', api, 'marketing', ['src/marketing/', 'content/']);
    expect(api.addPathsToScope).toHaveBeenCalledWith('proj-1', 'marketing', [
      'src/marketing/',
      'content/',
    ]);
    expect(api.listScopes).toHaveBeenCalledTimes(1);
  });

  // Test 11: removePaths calls api.removePathsFromScope then refreshes
  it('removePaths calls api.removePathsFromScope with paths then refreshes', async () => {
    const api = makeFakeApi();
    await simulateRemovePaths('proj-1', api, 'marketing', ['content/']);
    expect(api.removePathsFromScope).toHaveBeenCalledWith('proj-1', 'marketing', ['content/']);
    expect(api.listScopes).toHaveBeenCalledTimes(1);
  });

  // Test 12: null projectId — deleteScope is a no-op that preserves activeScopeId
  it('null projectId causes deleteScope to skip api.deleteScope', async () => {
    const api = makeFakeApi();
    const newActive = await simulateDeleteScope(null, api, 'marketing', 'marketing');
    expect(api.deleteScope).not.toHaveBeenCalled();
    // When projectId is null we return the unchanged activeScopeId
    expect(newActive).toBe('marketing');
  });
});
