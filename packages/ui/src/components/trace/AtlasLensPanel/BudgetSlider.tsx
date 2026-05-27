import { useEffect, useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { cn } from '../../../lib/utils';

export interface BudgetSliderProps {
  /** Currently-applied char budget. */
  value: number;
  /** Built-in default for this role — shown as a tick mark. */
  defaultValue: number;
  /** Global ceiling (Recommended ceiling: 8000 cold-start limit). */
  ceiling?: number;
  /** Hard min enforced by the API (200). */
  floor?: number;
  /** True when the current value came from an override rather than default. */
  hasOverride: boolean;
  /** Called after the user releases the slider, not on every drag tick. */
  onCommit: (maxChars: number) => void;
  /** Clear the override (revert to built-in default). */
  onReset: () => void;
  disabled?: boolean;
  className?: string;
}

/**
 * Interactive budget slider for the role lens.
 *
 * Drag updates local state only; commit fires once on release (and on
 * keyboard input finalization) so we don't hammer the daemon with a PUT
 * per pixel. Matches the typical pattern used elsewhere in the dashboard.
 */
export function BudgetSlider({
  value,
  defaultValue,
  ceiling = 8000,
  floor = 200,
  hasOverride,
  onCommit,
  onReset,
  disabled,
  className,
}: BudgetSliderProps) {
  const [draft, setDraft] = useState(value);

  // Re-sync when the value prop changes (e.g. role switch, optimistic
  // update reconciliation, reset).
  useEffect(() => {
    setDraft(value);
  }, [value]);

  const pct = Math.min(100, Math.round(((draft - floor) / (ceiling - floor)) * 100));
  const defaultPct = Math.min(100, Math.round(((defaultValue - floor) / (ceiling - floor)) * 100));

  function commit() {
    if (draft !== value) onCommit(draft);
  }

  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-text-muted">Char budget</span>
        <span className="tabular-nums font-medium">
          {draft.toLocaleString()}
          <span className="text-text-muted">
            {' / '}
            {ceiling.toLocaleString()}
          </span>
        </span>
      </div>

      <div className="relative">
        <input
          type="range"
          min={floor}
          max={ceiling}
          step={100}
          value={draft}
          disabled={disabled}
          onChange={(e) => setDraft(Number(e.currentTarget.value))}
          onMouseUp={commit}
          onTouchEnd={commit}
          onKeyUp={(e) => {
            if (e.key === 'Enter' || e.key === 'ArrowLeft' || e.key === 'ArrowRight') commit();
          }}
          onBlur={commit}
          className="w-full h-2 appearance-none bg-surface-raised rounded cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Char budget"
        />
        {/* Default marker — purely visual overlay, does not intercept events. */}
        <div
          aria-hidden
          className="pointer-events-none absolute top-1/2 -translate-y-1/2 w-0.5 h-3 bg-border-strong/80"
          style={{ left: `calc(${defaultPct}% - 1px)` }}
          title={`Default: ${defaultValue.toLocaleString()} chars`}
        />
      </div>

      <div className="flex items-center justify-between text-[11px] text-text-muted">
        <span>
          default {defaultValue.toLocaleString()}
        </span>
        <div className="flex items-center gap-2">
          {hasOverride && (
            <span className="text-primary">tuned from default</span>
          )}
          {hasOverride && !disabled && (
            <button
              type="button"
              onClick={onReset}
              className="inline-flex items-center gap-1 rounded hover:text-text transition-colors"
              aria-label="Reset to default budget"
            >
              <RotateCcw className="w-3 h-3" />
              reset
            </button>
          )}
        </div>
      </div>

      {/* Stylized track fill (purely visual, under the native input). */}
      <div aria-hidden className="hidden" style={{ width: `${pct}%` }} />
    </div>
  );
}
