import { ReactNode } from 'react';
import { cn } from '../../lib/utils';

export interface SettingRowProps {
  label: string;
  description?: ReactNode;
  control: ReactNode;
  /** suppresses the bottom border — use for the last row in a Section */
  last?: boolean;
  className?: string;
}

export function SettingRow({ label, description, control, last, className }: SettingRowProps) {
  return (
    <div
      className={cn(
        'flex items-start justify-between gap-6 py-4',
        !last && 'border-b border-border-subtle',
        className,
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-text">{label}</div>
        {description && (
          <div className="mt-1 text-sm text-text-muted">{description}</div>
        )}
      </div>
      <div className="flex-shrink-0 w-[260px] flex justify-end">
        {control}
      </div>
    </div>
  );
}
