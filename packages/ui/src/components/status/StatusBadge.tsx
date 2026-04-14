import type { StatusState } from '../../types';
import { cn } from '../../lib/utils';

export interface StatusBadgeProps {
  status: StatusState;
  className?: string;
  showLabel?: boolean;
  labelOverride?: string;
}

const statusConfig: Record<StatusState, { label: string; classes: string }> = {
  fresh: {
    label: 'Fresh',
    classes: 'bg-success-muted text-success border-success/20'
  },
  stale: {
    label: 'Stale',
    classes: 'bg-warning-muted text-warning border-warning/20'
  },
  building: {
    label: 'Building',
    classes: 'bg-info-muted text-info border-info/20 animate-pulse'
  },
  pending: {
    label: 'Pending',
    classes: 'bg-surface-raised text-text-muted border-border'
  },
  paused: {
    label: 'Paused',
    classes: 'bg-amber-500/10 text-amber-500 border-amber-500/30'
  },
  cancelled: {
    label: 'Cancelled',
    classes: 'bg-surface-raised text-text-muted border-border line-through'
  },
  error: {
    label: 'Error',
    classes: 'bg-error-muted text-error border-error/20'
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
