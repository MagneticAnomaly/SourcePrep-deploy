import { cn } from '@prep/ui';
import type { SettingsPageId } from './routeParser';
import { filterPagesForBuild, isDevBuild } from './devGate';

export interface SettingsNavProps {
  activePage: SettingsPageId | null;
  onNavigate: (page: SettingsPageId) => void;
  /** project name to show in the group label; null if no project active */
  projectName: string | null;
}

const LABELS: Record<SettingsPageId, string> = {
  'sources': 'Sources & Scope',
  'trace-indexing': 'Trace & Indexing',
  'deep-analysis': 'Deep Analysis',
  'danger-zone': 'Danger Zone',
  'appearance': 'Appearance',
  'chunking-embeddings': 'Chunking & Embeddings',
  'pipeline-defaults': 'Pipeline Defaults',
  'license': 'License',
  'integrations': 'Integrations',
  'developer-debug': 'Debug Toggles',
  'developer-diagnostics': 'Diagnostics',
  'developer-reset': 'Selective Reset',
};

export function SettingsNav({ activePage, onNavigate, projectName }: SettingsNavProps) {
  const pages = filterPagesForBuild(isDevBuild());
  const projectDisabled = projectName === null;

  const renderItem = (id: SettingsPageId, disabled = false) => {
    const active = activePage === id && !disabled;
    return (
      <li key={id}>
        <button
          type="button"
          disabled={disabled}
          aria-current={active ? 'page' : undefined}
          onClick={() => !disabled && onNavigate(id)}
          className={cn(
            'block w-full text-left px-2 py-1.5 text-sm rounded-md transition-colors',
            disabled
              ? 'text-text-subtle cursor-not-allowed'
              : 'text-text-muted hover:text-text hover:bg-surface-raised cursor-pointer',
            active && 'bg-primary/10 text-primary font-medium',
          )}
        >
          {LABELS[id]}
        </button>
      </li>
    );
  };

  const sectionHeading = (label: string, first = false) => (
    <h4
      className={cn(
        'font-semibold text-xs uppercase tracking-wider text-primary mb-3 px-2',
        first ? '' : 'border-t border-border pt-4 mt-2',
      )}
    >
      {label}
    </h4>
  );

  return (
    <nav aria-label="Settings" className="w-4/5">
      <ul className="space-y-4">
        <li>
          {sectionHeading(
            projectDisabled
              ? 'Project · none selected'
              : `Project · ${projectName}`,
            true,
          )}
          <ul className="space-y-1">
            {pages.project.map((id) => renderItem(id, projectDisabled))}
          </ul>
          {projectDisabled && (
            <p className="text-xs text-text-muted mt-2 px-2">Select a project first.</p>
          )}
        </li>

        <li>
          {sectionHeading('Global')}
          <ul className="space-y-1">
            {pages.global.map((id) => renderItem(id))}
          </ul>
        </li>

        {pages.developer.length > 0 && (
          <li>
            {sectionHeading('Developer')}
            <ul className="space-y-1">
              {pages.developer.map((id) => renderItem(id))}
            </ul>
          </li>
        )}
      </ul>
    </nav>
  );
}
