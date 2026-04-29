import { useState, useEffect, useCallback } from 'react';
import type { ScopeRecord, ScopeSummary, ScopesListResponse } from '../types';

// ── API surface expected by useScopes ───────────────────────────────────────

/**
 * Subset of PrepApiClient that useScopes depends on.
 * Exported so tests and other consumers can build typed mocks without
 * importing the full client.
 */
export interface ScopesApi {
  listScopes(projectId: string): Promise<ScopesListResponse>;
  getScope(projectId: string, scopeId: string): Promise<ScopeRecord>;
  createScope(
    projectId: string,
    body: { display_name: string; paths?: string[]; assigned_to_role?: string | null },
  ): Promise<ScopeRecord>;
  updateScope(
    projectId: string,
    scopeId: string,
    body: { display_name?: string; assigned_to_role?: string | null },
  ): Promise<ScopeRecord>;
  deleteScope(projectId: string, scopeId: string): Promise<void>;
  addPathsToScope(projectId: string, scopeId: string, paths: string[]): Promise<ScopeRecord>;
  removePathsFromScope(projectId: string, scopeId: string, paths: string[]): Promise<ScopeRecord>;
}

// ── Hook ────────────────────────────────────────────────────────────────────

/**
 * useScopes — manage named scopes for a project.
 *
 * Takes `api` as a parameter (not from context) so the dashboard can pass
 * PrepApiClient while Storybook / tests can pass a mock.
 *
 * `activeScopeId` defaults to "global" and resets to "global" when the
 * active scope is deleted.
 */
export function useScopes(projectId: string | null, api: ScopesApi) {
  const [scopes, setScopes] = useState<ScopeSummary[]>([]);
  const [activeScopeId, setActiveScopeId] = useState<string>('global');

  // ── Refresh ──────────────────────────────────────────────────────────────

  const refresh = useCallback(async () => {
    if (!projectId) {
      setScopes([]);
      return;
    }
    try {
      const res = await api.listScopes(projectId);
      setScopes(res.scopes);
    } catch (err) {
      console.error('[useScopes] list failed', err);
    }
  }, [projectId, api]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // ── Mutations ────────────────────────────────────────────────────────────

  const createScope = useCallback(
    async (display_name: string): Promise<ScopeRecord | null> => {
      if (!projectId) return null;
      const rec = await api.createScope(projectId, { display_name });
      await refresh();
      setActiveScopeId(rec.id);
      return rec;
    },
    [projectId, api, refresh],
  );

  const renameScope = useCallback(
    async (id: string, display_name: string): Promise<void> => {
      if (!projectId) return;
      await api.updateScope(projectId, id, { display_name });
      await refresh();
    },
    [projectId, api, refresh],
  );

  const deleteScope = useCallback(
    async (id: string): Promise<void> => {
      if (!projectId) return;
      await api.deleteScope(projectId, id);
      if (activeScopeId === id) setActiveScopeId('global');
      await refresh();
    },
    [projectId, api, refresh, activeScopeId],
  );

  const addPaths = useCallback(
    async (id: string, paths: string[]): Promise<void> => {
      if (!projectId) return;
      await api.addPathsToScope(projectId, id, paths);
      await refresh();
    },
    [projectId, api, refresh],
  );

  const removePaths = useCallback(
    async (id: string, paths: string[]): Promise<void> => {
      if (!projectId) return;
      await api.removePathsFromScope(projectId, id, paths);
      await refresh();
    },
    [projectId, api, refresh],
  );

  // ── Return ───────────────────────────────────────────────────────────────

  return {
    scopes,
    activeScopeId,
    setActiveScopeId,
    createScope,
    renameScope,
    deleteScope,
    addPaths,
    removePaths,
    refresh,
  };
}
