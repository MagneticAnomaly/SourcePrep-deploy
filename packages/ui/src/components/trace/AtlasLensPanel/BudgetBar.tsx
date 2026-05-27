import { cn } from '../../../lib/utils';

export interface BudgetBarProps {
  /** Effective budget for this role (built-in or override). */
  value: number;
  /** Built-in default, used as the baseline marker. */
  defaultValue: number;
  /** Global ceiling — Total-artifact budget. */
  ceiling?: number;
  className?: string;
}

/**
 * Read-only visualisation of the role's char budget. Shows:
 *   - a fill proportional to `value / ceiling`
 *   - a tick mark at the built-in default so the user sees they have
 *     tuned away from it
 *
 * Step 6 renders this as read-only. Step 7 swaps in an interactive slider.
 */
export function BudgetBar({
  value,
  defaultValue,
  ceiling = 8000,
  className,
}: BudgetBarProps) {
  const fillPct = Math.min(100, Math.round((value / ceiling) * 100));
  const defaultPct = Math.min(100, Math.round((defaultValue / ceiling) * 100));
  const deviates = value !== defaultValue;

  return (
    <div className={cn('space-y-1', className)}>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-text-muted">Char budget</span>
        <span className="tabular-nums font-medium">
          {value.toLocaleString()}
          <span className="text-text-muted">
            {' / '}
            {ceiling.toLocaleString()}
          </span>
        </span>
      </div>
      <div className="relative h-2 bg-surface-raised rounded overflow-hidden">
        <div
          className={cn(
            'absolute left-0 top-0 bottom-0 transition-all',
            deviates ? 'bg-primary' : 'bg-primary/60',
          )}
          style={{ width: `${fillPct}%` }}
        />
        {/* Default marker */}
        <div
          aria-hidden
          className="absolute top-0 bottom-0 w-0.5 bg-border-strong/80"
          style={{ left: `${defaultPct}%` }}
          title={`Default: ${defaultValue.toLocaleString()} chars`}
        />
      </div>
      {deviates && (
        <div className="text-[11px] text-primary">
          Tuned from default {defaultValue.toLocaleString()} chars.
        </div>
      )}
    </div>
  );
}
