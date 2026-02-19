import { cn } from '../../lib/utils';
import type { ReactNode } from 'react';

export interface SettingsRowProps {
  label: string;
  description?: string;
  children: ReactNode;
  htmlFor?: string;
  className?: string;
  /** Stack label on top of control instead of side-by-side */
  stacked?: boolean;
}

/**
 * SettingsRow — a label + optional description paired with a control.
 * Handles horizontal (default) and stacked (vertical) layout.
 */
export function SettingsRow({
  label,
  description,
  children,
  htmlFor,
  className,
  stacked = false,
}: SettingsRowProps) {
  return (
    <div
      className={cn(
        'flex gap-3',
        stacked ? 'flex-col' : 'items-center justify-between',
        className
      )}
    >
      <div className={cn('min-w-0', stacked ? '' : 'flex-1')}>
        <label
          htmlFor={htmlFor}
          className="block text-sm font-medium text-text cursor-pointer"
        >
          {label}
        </label>
        {description && (
          <p className="text-xs text-text-muted mt-0.5 leading-relaxed">{description}</p>
        )}
      </div>
      <div className={cn('shrink-0', stacked && 'w-full')}>{children}</div>
    </div>
  );
}
