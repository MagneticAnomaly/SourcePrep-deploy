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

  const renderItem = (id: SettingsPageId, disabled = false) => (
    <button
      key={id}
      type="button"
      disabled={disabled}
      aria-current={activePage === id ? 'page' : undefined}
      onClick={() => !disabled && onNavigate(id)}
      className={cn(
        'w-full text-left text-sm rounded-md mx-0 px-3 py-1.5',
        disabled
          ? 'text-text-subtle cursor-not-allowed'
          : 'text-text-muted hover:bg-surface-raised cursor-pointer',
        activePage === id && !disabled && 'bg-surface-raised text-text font-medium',
      )}
    >
      {LABELS[id]}
    </button>
  );

  return (
    <nav aria-label="Settings" className="w-60 border-r border-border-subtle overflow-y-auto py-2">
      <div className="px-3">
        <div className="text-xs uppercase tracking-wide text-text-muted pt-4 pb-1">
          {projectDisabled
            ? 'Project · none selected'
            : `Project · ${projectName}`}
        </div>
        <div className="space-y-0.5">
          {pages.project.map(id => renderItem(id, projectDisabled))}
        </div>
        {projectDisabled && (
          <p className="text-xs text-text-muted mt-2 px-1">Select a project first.</p>
        )}
      </div>

      <div className="border-t border-border-subtle mt-4 pt-2 px-3">
        <div className="text-xs uppercase tracking-wide text-text-muted pt-2 pb-1">Global</div>
        <div className="space-y-0.5">
          {pages.global.map(id => renderItem(id))}
        </div>
      </div>

      {pages.developer.length > 0 && (
        <div className="border-t border-border-subtle mt-4 pt-2 px-3">
          <div className="text-xs uppercase tracking-wide text-text-muted pt-2 pb-1">
            Developer
          </div>
          <div className="space-y-0.5">
            {pages.developer.map(id => renderItem(id))}
          </div>
        </div>
      )}
    </nav>
  );
}
