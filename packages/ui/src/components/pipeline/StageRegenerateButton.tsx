import { RefreshCw } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface StageRegenerateButtonProps {
  /** Fired when the user clicks the button. Caller is responsible for
   *  posting to the orchestrator and driving state. */
  onRegenerate: () => void;
  /** True while a regenerate is in flight (POST accepted + pipeline running).
   *  Disables the button and swaps the label to "Regenerating…". */
  regenerating?: boolean;
  /** Override the default "Regenerate" label (e.g., when a stage has
   *  a different user-facing word). */
  label?: string;
  /** Extra classes for layout. */
  className?: string;
}

/**
 * Unified Regenerate button used across atlas / concepts / audit panels
 * (Phase 105b). The visual and disabled-state semantics are intentionally
 * the same everywhere so every stage's "re-run" affordance behaves
 * identically.
 *
 * The button itself is dumb — it only renders and fires onRegenerate.
 * Callers wire `useStageRegenerate` to the click handler.
 */
export function StageRegenerateButton({
  onRegenerate,
  regenerating = false,
  label,
  className,
}: StageRegenerateButtonProps) {
  return (
    <button
      type="button"
      onClick={onRegenerate}
      disabled={regenerating}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-xs font-medium',
        'hover:bg-surface-raised transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
        className,
      )}
    >
      <RefreshCw className={cn('w-3.5 h-3.5', regenerating && 'animate-spin')} />
      {regenerating ? 'Regenerating…' : (label ?? 'Regenerate')}
    </button>
  );
}
