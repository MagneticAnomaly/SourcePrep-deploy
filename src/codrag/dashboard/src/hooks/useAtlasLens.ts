/**
 * useAtlasLens — Phase 104 hook backing the AtlasLensPanel.
 *
 * Coordinates three reads:
 *   1. GET /projects/{id}/atlas           — root + segments
 *   2. GET /projects/{id}/atlas?role=X    — projection + applied_role + override
 *   3. POST /projects/{id}/atlas/regenerate on demand
 *
 * Role changes are debounced so rapid clicks through the role list don't
 * swamp the daemon; reuses the AbortSignal cancellation pattern from the
 * existing hydration-controller hooks.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { AtlasStatus } from '@codrag/ui';

const ROLE_DEBOUNCE_MS = 200;

export interface UseAtlasLensReturn {
  atlasStatus: AtlasStatus | null;
  loading: boolean;
  error: string | null;
  regenerating: boolean;
  role: string | null;
  setRole: (next: string | null) => void;
  refresh: () => Promise<void>;
  runAtlasStage: () => Promise<void>;
}

function unwrap<T = unknown>(body: { data?: T } | T): T {
  // Envelope: { success, data } — fall through for bare payloads.
  if (body && typeof body === 'object' && 'data' in (body as object)) {
    return (body as { data: T }).data;
  }
  return body as T;
}

export function useAtlasLens(
  projectId: string | null,
  opts: { signal?: AbortSignal } = {},
): UseAtlasLensReturn {
  const [atlasStatus, setAtlasStatus] = useState<AtlasStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [role, setRoleState] = useState<string | null>(null);

  // Abort role-projection requests when a newer role is selected.
  const roleAbortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchBase = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/projects/${encodeURIComponent(projectId)}/atlas`,
        { signal: opts.signal },
      );
      if (!res.ok) {
        throw new Error(`atlas fetch failed: ${res.status}`);
      }
      const body = await res.json();
      const data = unwrap<AtlasStatus>(body);
      setAtlasStatus(data);
    } catch (e) {
      if ((e as Error).name === 'AbortError') return;
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [projectId, opts.signal]);

  const fetchForRole = useCallback(async (roleId: string) => {
    if (!projectId) return;
    roleAbortRef.current?.abort();
    const ctrl = new AbortController();
    roleAbortRef.current = ctrl;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/projects/${encodeURIComponent(projectId)}/atlas?role=${encodeURIComponent(roleId)}`,
        { signal: ctrl.signal },
      );
      if (!res.ok) {
        throw new Error(`role projection failed: ${res.status}`);
      }
      const body = await res.json();
      const data = unwrap<AtlasStatus>(body);
      setAtlasStatus(data);
    } catch (e) {
      if ((e as Error).name === 'AbortError') return;
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // Initial + project-change fetch.
  useEffect(() => {
    void fetchBase();
  }, [fetchBase]);

  // Debounced role change — prevents a thrash when the user arrows through
  // the role picker. Also cancels any in-flight role fetch.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (role == null) {
      void fetchBase();
      return;
    }
    debounceRef.current = setTimeout(() => {
      void fetchForRole(role);
    }, ROLE_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [role, fetchForRole, fetchBase]);

  const setRole = useCallback((next: string | null) => {
    setRoleState(next);
  }, []);

  const refresh = useCallback(async () => {
    if (role) {
      await fetchForRole(role);
    } else {
      await fetchBase();
    }
  }, [role, fetchForRole, fetchBase]);

  const runAtlasStage = useCallback(async () => {
    if (!projectId) return;
    setRegenerating(true);
    setError(null);
    try {
      const res = await fetch(
        `/projects/${encodeURIComponent(projectId)}/pipeline/stages/atlas/run`,
        { method: 'POST' },
      );
      if (!res.ok) {
        // 409 is "another group active" or "up-to-date" — surface to user.
        const body = await res.json().catch(() => ({}));
        const msg = body?.error?.message ?? `run atlas failed: ${res.status}`;
        throw new Error(msg);
      }
      // Re-fetch so we show the fresh atlas + (if a role is active) the
      // updated role projection. The orchestrator owns the pipeline panel's
      // stage-state update via its own channel.
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRegenerating(false);
    }
  }, [projectId, refresh]);

  return {
    atlasStatus,
    loading,
    error,
    regenerating,
    role,
    setRole,
    refresh,
    runAtlasStage,
  };
}
