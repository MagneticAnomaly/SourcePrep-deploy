/**
 * Dashboard-scoped wrapper that hooks AtlasLensPanel up to the Phase 104
 * fetchers and mutators. Keeping the hook wiring here (not in @codrag/ui)
 * so the shared UI package stays free of project-specific dependencies.
 */
import { useCallback, useEffect, useState } from 'react';
import { AtlasLensPanel } from '@codrag/ui';
import { useAtlasLens } from '../hooks/useAtlasLens';
import { useRoleOverrides } from '../hooks/useRoleOverrides';

export interface AtlasLensContainerProps {
  projectId: string | null;
  className?: string;
}

/**
 * Built-in role → default max_chars budget. Keep this in lockstep with
 * ``src/codrag/core/atlas/role_vectors.py``'s BUILT_IN_ROLES so the
 * slider's "default" tick anchors correctly. If the backend ever exposes
 * these defaults as an endpoint we should switch to that — tracked as a
 * follow-on in docs/Phase104_SubAtlas/README.md.
 */
const BUILT_IN_DEFAULT_MAX_CHARS: Record<string, number> = {
  ceo: 1500,
  cto: 2500,
  architect: 3000,
  engineering: 4000,
  security: 3500,
  design: 3500,
  qa: 3500,
  devops: 3500,
  pm: 2500,
};

export function AtlasLensContainer({ projectId, className }: AtlasLensContainerProps) {
  const { atlasStatus, role, setRole, regenerate, regenerating, refresh } = useAtlasLens(projectId);
  const { putMaxChars, resetRole, unpinConcept } = useRoleOverrides(projectId);

  // Cache concept id → title so the pinned-list renders readable labels.
  // We fetch lazily as new IDs appear (typically a handful per project).
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

  const getDefaultMaxChars = useCallback((roleId: string) => {
    return BUILT_IN_DEFAULT_MAX_CHARS[roleId];
  }, []);

  const handleCommitMaxChars = useCallback(async (roleId: string, maxChars: number) => {
    await putMaxChars(roleId, maxChars);
    // Re-fetch the role projection so the preview reflects the new budget.
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

  const resolveConceptTitle = useCallback((conceptId: string) => {
    return conceptTitles[conceptId];
  }, [conceptTitles]);

  return (
    <AtlasLensPanel
      atlas={atlasStatus}
      role={role}
      onRoleChange={setRole}
      regenerating={regenerating}
      onRegenerate={regenerate}
      getDefaultMaxChars={getDefaultMaxChars}
      onCommitMaxChars={handleCommitMaxChars}
      onResetOverride={handleResetOverride}
      onUnpinConcept={handleUnpinConcept}
      resolveConceptTitle={resolveConceptTitle}
      className={className}
    />
  );
}
