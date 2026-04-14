import { cn } from '../../../lib/utils';
import type { AtlasStatus } from '../../../types';
import { StatusStrip } from './StatusStrip';
import { SubAtlasTree } from './SubAtlasTree';
import { RoleLens } from './RoleLens';

export interface AtlasLensPanelProps {
  atlas: AtlasStatus | null;
  /** Role currently selected in the lens picker. `null` disables projection. */
  role: string | null;
  onRoleChange: (role: string | null) => void;
  /** Options for the role dropdown. Caller provides the list from
   *  role_vectors defaults + any custom roles discovered in the project. */
  roleOptions?: { id: string; label: string }[];
  regenerating?: boolean;
  onRegenerate?: () => void;
  getSegmentContent?: (segmentId: string) => string | undefined;
  /** Step 7 — interactive affordances. Undefined → read-only panel. */
  getDefaultMaxChars?: (roleId: string) => number | undefined;
  onCommitMaxChars?: (roleId: string, maxChars: number) => void;
  onResetOverride?: (roleId: string) => void;
  onUnpinConcept?: (roleId: string, conceptId: string) => void;
  resolveConceptTitle?: (conceptId: string) => string | undefined;
  className?: string;
}

const DEFAULT_ROLE_OPTIONS: { id: string; label: string }[] = [
  { id: 'ceo', label: 'CEO' },
  { id: 'cto', label: 'CTO' },
  { id: 'architect', label: 'Architect' },
  { id: 'engineering', label: 'Software Engineer' },
  { id: 'security', label: 'Security' },
  { id: 'design', label: 'Designer' },
  { id: 'qa', label: 'QA' },
  { id: 'devops', label: 'DevOps' },
  { id: 'pm', label: 'Product Manager' },
];

/**
 * AtlasLensPanel — Phase 104.
 *
 * Three stacked bands:
 *   1. StatusStrip   — freshness, counts, regenerate button.
 *   2. SubAtlasTree  — segmented atlas list with per-segment preview.
 *   3. RoleLens      — role picker → projection preview + applied lens summary.
 *
 * This component is the read-only shell. Interactive budget tuning and
 * concept pinning arrive in Step 7 on top of this structure.
 */
export function AtlasLensPanel({
  atlas,
  role,
  onRoleChange,
  roleOptions = DEFAULT_ROLE_OPTIONS,
  regenerating,
  onRegenerate,
  getSegmentContent,
  getDefaultMaxChars,
  onCommitMaxChars,
  onResetOverride,
  onUnpinConcept,
  resolveConceptTitle,
  className,
}: AtlasLensPanelProps) {
  if (!atlas || !atlas.exists) {
    return (
      <div className={cn('flex flex-col gap-3 h-full', className)}>
        <StatusStrip atlas={atlas} regenerating={regenerating} onRegenerate={onRegenerate} />
        <p className="text-sm text-text-muted italic px-1">
          No atlas yet. Regenerate or wait for the enrichment pipeline to finish.
        </p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'flex flex-col gap-4 h-full overflow-y-auto custom-scrollbar pr-1',
        className,
      )}
    >
      <StatusStrip
        atlas={atlas}
        regenerating={regenerating}
        onRegenerate={onRegenerate}
      />

      <div className="border-t border-border -mx-1" />

      <SubAtlasTree
        segments={atlas.segments}
        getSegmentContent={getSegmentContent}
      />

      <div className="border-t border-border -mx-1" />

      <RoleLens
        atlas={atlas}
        role={role}
        roleOptions={roleOptions}
        onRoleChange={onRoleChange}
        defaultMaxChars={role ? getDefaultMaxChars?.(role) : undefined}
        onCommitMaxChars={role && onCommitMaxChars
          ? (chars) => onCommitMaxChars(role, chars)
          : undefined}
        onResetOverride={role && onResetOverride
          ? () => onResetOverride(role)
          : undefined}
        onUnpinConcept={role && onUnpinConcept
          ? (conceptId) => onUnpinConcept(role, conceptId)
          : undefined}
        resolveConceptTitle={resolveConceptTitle}
      />
    </div>
  );
}
