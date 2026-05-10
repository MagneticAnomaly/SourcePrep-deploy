import type { StatusState } from '../../types';
import { cn } from '../../lib/utils';

export interface StatusBadgeProps {
  status: StatusState;
  className?: string;
  showLabel?: boolean;
  labelOverride?: string;
}

// Tones use the opacity-modifier pattern (bg-X/10, text-X, border-X/40) that
// the pill Button uses, instead of the per-theme `--{tone}-muted` token.
// `--success-muted` etc. were defined inconsistently across themes and on
// some surfaces produced text-on-bg pairs at near-equal luminance, e.g. the
// Fresh badge rendering as illegible green-on-green on direction-a.
const statusConfig: Record<StatusState, { label: string; classes: string }> = {
  fresh: {
    label: 'Fresh',
    classes: 'bg-success/10 text-success border-success/40'
  },
  stale: {
    label: 'Stale',
    classes: 'bg-warning/10 text-warning border-warning/40'
  },
  building: {
    label: 'Building',
    classes: 'bg-info/10 text-info border-info/40 animate-pulse'
  },
  pending: {
    label: 'Pending',
    classes: 'bg-surface-raised text-text-muted border-border'
  },
  paused: {
    label: 'Paused',
    classes: 'bg-amber-500/10 text-amber-500 border-amber-500/40'
  },
  cancelled: {
    label: 'Cancelled',
    classes: 'bg-surface-raised text-text-muted border-border line-through'
  },
  error: {
    label: 'Error',
    classes: 'bg-error/10 text-error border-error/40'
  },
  disabled: {
    label: 'Disabled',
    classes: 'bg-surface-raised text-text-subtle border-border opacity-60'
  },
};

/**
 * StatusBadge - Displays index/build status
 * 
 * Maps StatusState to appropriate semantic theme colors.
 */
export function StatusBadge({ status, className, showLabel = true, labelOverride }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <span
      className={cn(
        'inline-flex items-center justify-center rounded-full px-2.5 py-0.5 text-xs font-medium border',
        config.classes,
        className
      )}
    >
      {showLabel && (labelOverride ?? config.label)}
    </span>
  );
}
