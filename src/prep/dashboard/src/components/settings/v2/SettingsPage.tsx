// src/prep/dashboard/src/components/settings/v2/SettingsPage.tsx
import { ReactNode } from 'react';
import { scopeChipLabel, scopeAriaLabel, type SettingsScope } from '@prep/ui';

export interface SettingsPageProps {
  title: string;
  scope: SettingsScope;
  description?: ReactNode;
  /** right-aligned header actions — e.g. Project pages' "Saving…" indicator */
  actions?: ReactNode;
  children: ReactNode;
}

export function SettingsPage({
  title, scope, description, actions, children,
}: SettingsPageProps) {
  return (
    <article className="max-w-3xl">
      <header className="mb-8 pb-4 border-b border-border">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold tracking-tight text-text">{title}</h1>
              <span
                className="bg-surface-raised text-text-muted text-xs rounded-full px-2 py-0.5"
                aria-label={scopeAriaLabel(scope)}
              >
                {scopeChipLabel(scope)}
              </span>
            </div>
            {description && (
              <p className="mt-2 text-base text-text-muted leading-relaxed">{description}</p>
            )}
          </div>
          {actions && <div className="flex-shrink-0">{actions}</div>}
        </div>
      </header>

      <div className="space-y-8">{children}</div>
    </article>
  );
}
