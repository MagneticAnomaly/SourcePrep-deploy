/**
 * Dashboard-scoped wrapper that hooks AtlasLensPanel up to the Phase 104
 * fetchers. Keeping the hook wiring here (not in @codrag/ui) so the shared
 * UI package stays free of project-specific dependencies.
 */
import { AtlasLensPanel } from '@codrag/ui';
import { useAtlasLens } from '../hooks/useAtlasLens';

export interface AtlasLensContainerProps {
  projectId: string | null;
  className?: string;
}

export function AtlasLensContainer({ projectId, className }: AtlasLensContainerProps) {
  const { atlasStatus, role, setRole, regenerate, regenerating } = useAtlasLens(projectId);

  return (
    <AtlasLensPanel
      atlas={atlasStatus}
      role={role}
      onRoleChange={setRole}
      regenerating={regenerating}
      onRegenerate={regenerate}
      className={className}
    />
  );
}
