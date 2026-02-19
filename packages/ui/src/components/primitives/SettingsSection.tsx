import { cn } from '../../lib/utils';
import type { ReactNode } from 'react';

export interface SettingsSectionProps {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
  /** Visually separate from sections above it */
  bordered?: boolean;
}

/**
 * SettingsSection — titled group of settings rows.
 * Use as a container inside any settings panel or drawer.
 */
export function SettingsSection({
  title,
  description,
  children,
  className,
  bordered = false,
}: SettingsSectionProps) {
  return (
    <section
      className={cn(
        'space-y-3',
        bordered && 'pt-4 border-t border-border',
        className
      )}
    >
      <div>
        <h3 className="text-sm font-semibold text-text">{title}</h3>
        {description && (
          <p className="text-xs text-text-muted mt-0.5 leading-relaxed">{description}</p>
        )}
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}
