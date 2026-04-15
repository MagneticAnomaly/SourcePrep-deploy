import { Badge } from '@tremor/react';
import { Eye, Layers, Sliders } from 'lucide-react';
import { cn } from '../../../lib/utils';
import type { AtlasStatus, RoleVectorPayload } from '../../../types';
import { BudgetBar } from './BudgetBar';
import { BudgetSlider } from './BudgetSlider';
import { PinnedConceptsList } from './PinnedConceptsList';

export interface RoleLensProps {
  atlas: AtlasStatus | null;
  role: string | null;
  roleOptions: { id: string; label: string }[];
  onRoleChange: (role: string | null) => void;
  /** Built-in default budget for the current role. Parent resolves it
   *  from the role_vectors defaults so the slider can anchor correctly
   *  even when an override is active. */
  defaultMaxChars?: number;
  /** Optional write affordances — when present, the lens becomes
   *  interactive. Leave undefined for a read-only preview (Step 6). */
  onCommitMaxChars?: (maxChars: number) => void;
  onResetOverride?: () => void;
  onUnpinConcept?: (conceptId: string) => void;
  /** Resolves pinned concept IDs to readable titles. */
  resolveConceptTitle?: (conceptId: string) => string | undefined;
  className?: string;
}

const LAYER_ORDER: (keyof RoleVectorPayload['layer_weights'] | string)[] = [
  'presentation',
  'business_logic',
  'data',
  'infrastructure',
  'configuration',
  'testing',
  'documentation',
  'build',
  'unknown',
];

/**
 * Role picker + preview + applied-lens summary.
 *
 * Read-only in Step 6. Step 7 layers the interactive budget slider and
 * concept pinning UI on top.
 */
export function RoleLens({
  atlas,
  role,
  roleOptions,
  onRoleChange,
  defaultMaxChars,
  onCommitMaxChars,
  onResetOverride,
  onUnpinConcept,
  resolveConceptTitle,
  className,
}: RoleLensProps) {
  const applied = atlas?.applied_role;
  const override = atlas?.override;
  const projection = atlas?.role_atlas ?? '';
  const error = atlas?.role_atlas_error;
  const interactive = Boolean(onCommitMaxChars);

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex items-center gap-2">
        <Eye className="w-4 h-4 text-text-muted" />
        <label htmlFor="atlas-role-picker" className="text-sm font-medium">
          Role Lens
        </label>
        <select
          id="atlas-role-picker"
          value={role ?? ''}
          onChange={(e) => onRoleChange(e.target.value || null)}
          className="ml-auto rounded-md border border-border bg-surface-raised px-2 py-1 text-sm"
        >
          <option value="">— none —</option>
          {roleOptions.map((opt) => (
            <option key={opt.id} value={opt.id}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {!role && (
        <p className="text-xs text-text-muted italic">
          Pick a role to preview the sub-atlas an agent using that role would
          receive from CoDRAG MCP. No changes here — this is what is actually
          served right now.
        </p>
      )}

      {role && error && (
        <div className="text-xs rounded border border-red-500/40 bg-red-500/10 p-2 text-red-400">
          Role projection failed: {error}
        </div>
      )}

      {role && applied && !error && (
        <div className="grid gap-3 md:grid-cols-[1fr_240px]">
          {/* Preview */}
          <div className="rounded-md border border-border bg-surface-raised overflow-hidden">
            <div className="flex items-center justify-between border-b border-border px-2 py-1 text-xs text-text-muted">
              <span>Preview · {applied.display_name}</span>
              <span className="tabular-nums">
                {(atlas?.role_atlas_chars ?? projection.length).toLocaleString()} chars
              </span>
            </div>
            <pre className="p-3 text-xs whitespace-pre-wrap font-mono max-h-64 overflow-auto custom-scrollbar">
              {projection || '(empty)'}
            </pre>
          </div>

          {/* Applied lens summary */}
          <div className="space-y-3 text-xs">
            <div className="flex items-center gap-1.5 font-medium text-text-muted uppercase tracking-wide">
              <Sliders className="w-3 h-3" />
              Applied lens
            </div>

            {interactive && onCommitMaxChars ? (
              <BudgetSlider
                value={applied.max_chars}
                defaultValue={defaultMaxChars ?? applied.max_chars}
                hasOverride={Boolean(override?.max_chars && override.max_chars !== (defaultMaxChars ?? applied.max_chars))}
                onCommit={onCommitMaxChars}
                onReset={onResetOverride ?? (() => {})}
              />
            ) : (
              <BudgetBar
                value={applied.max_chars}
                defaultValue={defaultMaxChars ?? applied.max_chars}
                ceiling={8000}
              />
            )}

            <div>
              <div className="text-text-muted mb-1 inline-flex items-center gap-1">
                <Layers className="w-3 h-3" />
                Layer weights
              </div>
              <div className="space-y-1">
                {LAYER_ORDER
                  .filter((key) => key in applied.layer_weights)
                  .map((key) => {
                    const v = applied.layer_weights[key as string] ?? 0;
                    return (
                      <div key={String(key)} className="flex items-center gap-2">
                        <span className="w-28 shrink-0 text-[11px] text-text-muted truncate">
                          {String(key).replace(/_/g, ' ')}
                        </span>
                        <div className="flex-1 h-1.5 bg-surface rounded overflow-hidden">
                          <div
                            className="h-full bg-primary/70"
                            style={{ width: `${Math.max(0, Math.min(1, v)) * 100}%` }}
                          />
                        </div>
                        <span className="w-8 text-right tabular-nums text-[11px] text-text-muted">
                          {v.toFixed(2)}
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>

            {applied.domain_affinity.length > 0 && (
              <div>
                <div className="text-text-muted mb-1">Domain affinity</div>
                <div className="flex flex-wrap gap-1">
                  {applied.domain_affinity.slice(0, 8).map((tag) => (
                    <Badge key={tag} color="gray" size="xs">{tag}</Badge>
                  ))}
                  {applied.domain_affinity.length > 8 && (
                    <span className="text-[11px] text-text-muted">
                      +{applied.domain_affinity.length - 8}
                    </span>
                  )}
                </div>
              </div>
            )}

            <div className="flex items-center justify-between text-text-muted pt-1 border-t border-border">
              <span>Centrality</span>
              <span className="tabular-nums">{applied.centrality_weight.toFixed(2)}</span>
            </div>
            <div className="flex items-center justify-between text-text-muted">
              <span>Detail</span>
              <span>
                {applied.detail_level < 0.3
                  ? 'executive'
                  : applied.detail_level <= 0.7
                    ? 'manager'
                    : 'practitioner'}
              </span>
            </div>

            <div className="pt-1 border-t border-border space-y-1.5">
              <div className="text-text-muted">
                Pinned concepts{' '}
                <span className="font-medium text-text">
                  ({override?.pinned_concept_ids?.length ?? 0})
                </span>
              </div>
              <PinnedConceptsList
                pinnedIds={override?.pinned_concept_ids ?? []}
                resolveTitle={resolveConceptTitle}
                onUnpin={interactive ? onUnpinConcept : undefined}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
