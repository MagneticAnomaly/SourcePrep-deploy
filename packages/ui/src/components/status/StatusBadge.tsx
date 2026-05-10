import type { StatusState } from '../../types';
import { cn } from '../../lib/utils';

export interface StatusBadgeProps {
  status: StatusState;
  className?: string;
  showLabel?: boolean;
  labelOverride?: string;
}

// Tones use the Tailwind palette directly (emerald/amber/sky/red) with the
// text at the 300 shade (~75% lightness) so it stays legible on the faint
// /10 tinted backgrounds in dark mode. The semantic `--success` etc. tokens
// resolve to medium-lightness greens (~50%) which produced unreadable
// green-on-green when paired with their own /10 tint; using a paired shade
// from the same hue family fixes the contrast without theme work.
// Trade-off: status tones are no longer remapped by theme switches — if we
// want themable status colors later, introduce per-tone `--{tone}-foreground`
// tokens and swap back to the semantic class names.
const statusConfig: Record<StatusState, { label: string; classes: string }> = {
  fresh: {
    label: 'Fresh',
    classes: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/40'
  },
  stale: {
    label: 'Stale',
    classes: 'bg-amber-500/10 text-amber-300 border-amber-500/40'
  },
  building: {
    label: 'Building',
    classes: 'bg-sky-500/10 text-sky-300 border-sky-500/40 animate-pulse'
  },
  pending: {
    label: 'Pending',
    classes: 'bg-surface-raised text-text-muted border-border'
  },
  paused: {
    label: 'Paused',
    classes: 'bg-amber-500/10 text-amber-300 border-amber-500/40'
  },
  cancelled: {
    label: 'Cancelled',
    classes: 'bg-surface-raised text-text-muted border-border line-through'
  },
  error: {
    label: 'Error',
    classes: 'bg-red-500/10 text-red-300 border-red-500/40'
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
