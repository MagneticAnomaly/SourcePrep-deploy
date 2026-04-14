/**
 * useRoleOverrides — Phase 104 hook for the tunable affordances on the
 * AtlasLensPanel role lens.
 *
 * Owns the per-project override map (role_id → RoleOverride) and exposes
 * mutators for the budget slider and concept-pin actions. Each mutator
 * optimistically updates local state, then reconciles with the server's
 * response.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { RoleOverride } from '@codrag/ui';

export interface UseRoleOverridesReturn {
  overrides: Record<string, RoleOverride>;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  putMaxChars: (roleId: string, maxChars: number) => Promise<void>;
  resetRole: (roleId: string) => Promise<void>;
  pinConcept: (roleId: string, conceptId: string) => Promise<void>;
  unpinConcept: (roleId: string, conceptId: string) => Promise<void>;
}

function unwrap<T = unknown>(body: { data?: T } | T): T {
  if (body && typeof body === 'object' && 'data' in (body as object)) {
    return (body as { data: T }).data;
  }
  return body as T;
}

export function useRoleOverrides(
  projectId: string | null,
  opts: { signal?: AbortSignal } = {},
): UseRoleOverridesReturn {
  const [overrides, setOverrides] = useState<Record<string, RoleOverride>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cancelledRef = useRef(false);

  const refresh = useCallback(async () => {
    if (!projectId) {
      setOverrides({});
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/projects/${encodeURIComponent(projectId)}/role-overrides`,
        { signal: opts.signal },
      );
      if (!res.ok) {
        throw new Error(`list role overrides failed: ${res.status}`);
      }
      const body = await res.json();
      const data = unwrap<{ overrides: RoleOverride[] }>(body);
      const map: Record<string, RoleOverride> = {};
      for (const ov of data?.overrides ?? []) {
        map[ov.role_id] = ov;
      }
      if (!cancelledRef.current) {
        setOverrides(map);
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') return;
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [projectId, opts.signal]);

  useEffect(() => {
    cancelledRef.current = false;
    void refresh();
    return () => {
      cancelledRef.current = true;
    };
  }, [refresh]);

  const putMaxChars = useCallback(async (roleId: string, maxChars: number) => {
    if (!projectId) return;
    // Optimistic update — rolled back on failure.
    const previous = overrides[roleId];
    setOverrides((prev) => ({
      ...prev,
      [roleId]: {
        role_id: roleId,
        max_chars: maxChars,
        pinned_concept_ids: previous?.pinned_concept_ids ?? [],
        updated_at: Date.now() / 1000,
      },
    }));
    try {
      const res = await fetch(
        `/projects/${encodeURIComponent(projectId)}/role-overrides/${encodeURIComponent(roleId)}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ max_chars: maxChars }),
        },
      );
      if (!res.ok) throw new Error(`put override failed: ${res.status}`);
      const body = await res.json();
      const data = unwrap<{ override: RoleOverride }>(body);
      if (data?.override) {
        setOverrides((prev) => ({ ...prev, [roleId]: data.override }));
      }
    } catch (e) {
      // Roll back
      setOverrides((prev) => {
        const next = { ...prev };
        if (previous) next[roleId] = previous;
        else delete next[roleId];
        return next;
      });
      setError((e as Error).message);
    }
  }, [projectId, overrides]);

  const resetRole = useCallback(async (roleId: string) => {
    if (!projectId) return;
    const previous = overrides[roleId];
    setOverrides((prev) => {
      const next = { ...prev };
      delete next[roleId];
      return next;
    });
    try {
      const res = await fetch(
        `/projects/${encodeURIComponent(projectId)}/role-overrides/${encodeURIComponent(roleId)}`,
        { method: 'DELETE' },
      );
      if (!res.ok) throw new Error(`delete override failed: ${res.status}`);
    } catch (e) {
      if (previous) {
        setOverrides((prev) => ({ ...prev, [roleId]: previous }));
      }
      setError((e as Error).message);
    }
  }, [projectId, overrides]);

  const pinConcept = useCallback(async (roleId: string, conceptId: string) => {
    if (!projectId) return;
    const previous = overrides[roleId];
    // Optimistic
    setOverrides((prev) => {
      const existing = prev[roleId] ?? {
        role_id: roleId,
        pinned_concept_ids: [],
        updated_at: Date.now() / 1000,
      };
      if (existing.pinned_concept_ids.includes(conceptId)) return prev;
      return {
        ...prev,
        [roleId]: {
          ...existing,
          pinned_concept_ids: [...existing.pinned_concept_ids, conceptId],
          updated_at: Date.now() / 1000,
        },
      };
    });
    try {
      const res = await fetch(
        `/projects/${encodeURIComponent(projectId)}/role-overrides/${encodeURIComponent(roleId)}/pin`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ concept_id: conceptId }),
        },
      );
      if (!res.ok) throw new Error(`pin failed: ${res.status}`);
    } catch (e) {
      setOverrides((prev) => {
        const next = { ...prev };
        if (previous) next[roleId] = previous;
        else delete next[roleId];
        return next;
      });
      setError((e as Error).message);
    }
  }, [projectId, overrides]);

  const unpinConcept = useCallback(async (roleId: string, conceptId: string) => {
    if (!projectId) return;
    const previous = overrides[roleId];
    setOverrides((prev) => {
      const existing = prev[roleId];
      if (!existing) return prev;
      return {
        ...prev,
        [roleId]: {
          ...existing,
          pinned_concept_ids: existing.pinned_concept_ids.filter(id => id !== conceptId),
          updated_at: Date.now() / 1000,
        },
      };
    });
    try {
      const res = await fetch(
        `/projects/${encodeURIComponent(projectId)}/role-overrides/${encodeURIComponent(roleId)}/pin/${encodeURIComponent(conceptId)}`,
        { method: 'DELETE' },
      );
      if (!res.ok) throw new Error(`unpin failed: ${res.status}`);
    } catch (e) {
      if (previous) {
        setOverrides((prev) => ({ ...prev, [roleId]: previous }));
      }
      setError((e as Error).message);
    }
  }, [projectId, overrides]);

  return {
    overrides,
    loading,
    error,
    refresh,
    putMaxChars,
    resetRole,
    pinConcept,
    unpinConcept,
  };
}
