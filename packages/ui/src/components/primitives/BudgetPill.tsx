import { cn } from '../../lib/utils';

export interface BudgetPillProps {
  /** Raw number value */
  value: number;
  /** Unit label shown after the value (e.g. 'chars', 'tokens', 'nodes') */
  unit?: string;
  /** Optional max — shows value/max when provided */
  max?: number;
  /** Colour variant based on utilisation */
  variant?: 'default' | 'warning' | 'danger' | 'ok';
  className?: string;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return String(n);
}

/**
 * BudgetPill — compact badge for displaying budget / limit values.
 * Automatically colours itself based on variant or utilisation ratio.
 */
export function BudgetPill({
  value,
  unit,
  max,
  variant,
  className,
}: BudgetPillProps) {
  const resolved = variant ?? (() => {
    if (!max) return 'default';
    const ratio = value / max;
    if (ratio >= 0.9) return 'danger';
    if (ratio >= 0.7) return 'warning';
    return 'ok';
  })();

  const colours: Record<string, string> = {
    default: 'border-border bg-surface-raised text-text-muted',
    ok:      'border-success/30 bg-success/10 text-success',
    warning: 'border-amber-400/40 bg-amber-50/60 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400',
    danger:  'border-error/30 bg-error/10 text-error',
  };

  const label = max
    ? `${formatNumber(value)} / ${formatNumber(max)}${unit ? ` ${unit}` : ''}`
    : `${formatNumber(value)}${unit ? ` ${unit}` : ''}`;

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium tabular-nums',
        colours[resolved],
        className
      )}
    >
      {label}
    </span>
  );
}
