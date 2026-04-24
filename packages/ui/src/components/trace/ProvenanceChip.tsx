/**
 * ProvenanceChip — Phase 117 Rebuild Granularity
 *
 * Renders a small chip next to a pipeline stage when the stage's model
 * provenance has drifted from the current config, was recovered as a stub,
 * or was rebuilt with a fallback model. Returns null for `match` state (no
 * chip needed) or when provenance data is missing.
 *
 * If an `onRebuild` callback is provided and the state is actionable (drift
 * or recovered_stub), the chip renders as a <button> that triggers a
 * scoped rebuild. Non-actionable states (recovered_soft) render as a plain
 * <span> for informational display only.
 */
import type { StageRebuildProvenance, RebuildScope } from '../../types';

export interface ProvenanceChipProps {
  provenance: StageRebuildProvenance | undefined;
  onRebuild?: (scope: RebuildScope) => void;
}

const STATE_STYLES: Record<string, string> = {
  drift:          'bg-warning/15 border-warning/40 text-warning',
  recovered_stub: 'bg-warning/15 border-warning/40 text-warning',
  recovered_soft: 'bg-surface-raised border-border text-text-muted',
};

/**
 * Returns true when the provenance state warrants an inline rebuild button.
 */
function isActionable(state: StageRebuildProvenance['state']): boolean {
  return state === 'drift' || state === 'recovered_stub';
}

export function ProvenanceChip({ provenance, onRebuild }: ProvenanceChipProps) {
  if (!provenance) return null;
  if (provenance.state === 'match') return null;
  if (provenance.state === 'missing') return null;
  if (!provenance.chip_text) return null;

  const style = STATE_STYLES[provenance.state] ?? STATE_STYLES['recovered_soft'];
  const baseClass = `inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-medium leading-none ${style}`;

  if (isActionable(provenance.state) && onRebuild && provenance.rebuild_scope) {
    const scope = provenance.rebuild_scope;
    return (
      <button
        type="button"
        className={`${baseClass} cursor-pointer hover:opacity-80`}
        title="Click to rebuild this stage with the current model"
        onClick={() => onRebuild(scope)}
      >
        {provenance.chip_text}
      </button>
    );
  }

  return (
    <span className={baseClass} title={provenance.chip_text}>
      {provenance.chip_text}
    </span>
  );
}
