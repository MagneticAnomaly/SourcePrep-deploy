/**
 * Dashboard-scoped wrapper that hooks AtlasLensPanel up to the Phase 104
 * fetchers and mutators.
 *
 * Keeps the hook wiring + project-specific lookups here so @codrag/ui
 * stays free of dashboard dependencies.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AtlasLensPanel, type RoleVectorPayload } from '@codrag/ui';
import { useAtlasLens } from '../hooks/useAtlasLens';
import { useRoleOverrides } from '../hooks/useRoleOverrides';

export interface AtlasLensContainerProps {
  projectId: string | null;
  className?: string;
}

export function AtlasLensContainer({ projectId, className }: AtlasLensContainerProps) {
  const {
    atlasStatus, role, setRole, runAtlasStage, regenerating, refresh,
    error: atlasError,
  } = useAtlasLens(projectId);
  const {
    putMaxChars, resetRole, unpinConcept,
    error: overrideError,
  } = useRoleOverrides(projectId);

  // Built-in roles loaded once from the backend so the dropdown and the
  // slider's default tick stay in sync with role_vectors.py without a
  // hardcoded copy in TypeScript.
  const [builtinRoles, setBuiltinRoles] = useState<RoleVectorPayload[]>([]);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch('/roles');
        if (!res.ok) return;
        const body = await res.json();
        const data = body?.data ?? body;
        if (!cancelled) setBuiltinRoles(data?.roles ?? []);
      } catch {
        /* best effort — panel still works with empty dropdown */
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const roleOptions = useMemo(
    () => builtinRoles.map(r => ({ id: r.role_id, label: r.display_name })),
    [builtinRoles],
  );

  const defaultMaxCharsByRole = useMemo(() => {
    const map: Record<string, number> = {};
    for (const r of builtinRoles) map[r.role_id] = r.max_chars;
    return map;
  }, [builtinRoles]);

  // Cache concept id → title so the pinned-list renders readable labels.
  // Lazy-fetched as new IDs appear in the override map.
  const [conceptTitles, setConceptTitles] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!projectId) return;
    const ids = atlasStatus?.override?.pinned_concept_ids ?? [];
    const missing = ids.filter((id) => !(id in conceptTitles));
    if (missing.length === 0) return;
    let cancelled = false;
    (async () => {
      const updates: Record<string, string> = {};
      await Promise.all(missing.map(async (id) => {
        try {
          const res = await fetch(
            `/projects/${encodeURIComponent(projectId)}/concepts/${encodeURIComponent(id)}`,
          );
          if (!res.ok) return;
          const body = await res.json();
          const data = body?.data ?? body;
          const title = data?.concept?.title ?? data?.title;
          if (title) updates[id] = title;
        } catch {
          /* best effort */
        }
      }));
      if (!cancelled && Object.keys(updates).length > 0) {
        setConceptTitles((prev) => ({ ...prev, ...updates }));
      }
    })();
    return () => { cancelled = true; };
  }, [projectId, atlasStatus?.override?.pinned_concept_ids, conceptTitles]);

  const getDefaultMaxChars = useCallback(
    (roleId: string) => defaultMaxCharsByRole[roleId],
    [defaultMaxCharsByRole],
  );

  const handleCommitMaxChars = useCallback(async (roleId: string, maxChars: number) => {
    await putMaxChars(roleId, maxChars);
    await refresh();
  }, [putMaxChars, refresh]);

  const handleResetOverride = useCallback(async (roleId: string) => {
    await resetRole(roleId);
    await refresh();
  }, [resetRole, refresh]);

  const handleUnpinConcept = useCallback(async (roleId: string, conceptId: string) => {
    await unpinConcept(roleId, conceptId);
    await refresh();
  }, [unpinConcept, refresh]);

  const resolveConceptTitle = useCallback(
    (conceptId: string) => conceptTitles[conceptId],
    [conceptTitles],
  );

  const getSegmentContent = useCallback(
    (segmentId: string) => atlasStatus?.segments?.find(s => s.segment_id === segmentId)?.content,
    [atlasStatus?.segments],
  );

  // Prefer override-mutation errors (the thing the user just attempted)
  // over atlas-fetch errors when both are present.
  const error = overrideError ?? atlasError;

  return (
    <div className="relative h-full">
      {error && (
        <div
          role="alert"
          className="absolute top-0 right-0 z-10 max-w-sm text-[11px] rounded border border-red-500/40 bg-red-500/10 px-2 py-1 text-red-400 m-2"
        >
          {error}
        </div>
      )}
      <AtlasLensPanel
        atlas={atlasStatus}
        role={role}
        onRoleChange={setRole}
        roleOptions={roleOptions.length > 0 ? roleOptions : undefined}
        regenerating={regenerating}
        onRegenerate={runAtlasStage}
        getSegmentContent={getSegmentContent}
        getDefaultMaxChars={getDefaultMaxChars}
        onCommitMaxChars={handleCommitMaxChars}
        onResetOverride={handleResetOverride}
        onUnpinConcept={handleUnpinConcept}
        resolveConceptTitle={resolveConceptTitle}
        className={className}
      />
    </div>
  );
}
