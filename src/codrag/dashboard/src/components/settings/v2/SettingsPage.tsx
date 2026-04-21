// src/codrag/dashboard/src/components/settings/v2/SettingsPage.tsx
import { ReactNode } from 'react';
import { scopeChipLabel, scopeAriaLabel, type SettingsScope } from '@codrag/ui';

export interface SettingsPageProps {
  title: string;
  scope: SettingsScope;
  description?: ReactNode;
  /** right-aligned header actions — Save button for Project pages */
  actions?: ReactNode;
  /** "Unsaved changes" banner (Project pages) */
  dirty?: boolean;
  children: ReactNode;
}

export function SettingsPage({
  title, scope, description, actions, dirty, children,
}: SettingsPageProps) {
  return (
    <div className="max-w-3xl mx-auto px-8 py-8">
      <header
        className="sticky top-0 bg-surface z-10 pb-4 border-b border-border-subtle mb-6"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-text">{title}</h1>
              <span
                className="bg-surface-raised text-text-muted text-xs rounded-full px-2 py-0.5"
                aria-label={scopeAriaLabel(scope)}
              >
                {scopeChipLabel(scope)}
              </span>
            </div>
            {description && (
              <p className="mt-1 text-sm text-text-muted">{description}</p>
            )}
          </div>
          {actions && <div className="flex-shrink-0">{actions}</div>}
        </div>
        {dirty && (
          <div className="mt-3 rounded-md bg-warning-muted text-warning text-sm px-3 py-2">
            Unsaved changes
          </div>
        )}
      </header>

      <div className="space-y-8">{children}</div>
    </div>
  );
}
