/**
 * PushSettings — Minimal push configuration form.
 * Three fields: auto-push toggle, significance threshold, Paperclip project.
 */

export interface PushSettingsData {
  auto_push: boolean;
  min_significance: 'all' | 'recommended' | 'mandatory';
  paperclip_project: string;
}

export interface PushSettingsProps {
  settings: PushSettingsData | null;
  loading?: boolean;
  onUpdate?: (settings: PushSettingsData) => void;
  className?: string;
}

const SIGNIFICANCE_OPTIONS = [
  { value: 'all', label: 'All findings' },
  { value: 'recommended', label: 'Recommended+ only' },
  { value: 'mandatory', label: 'Mandatory only' },
] as const;

export function PushSettings({
  settings,
  loading = false,
  onUpdate,
  className = '',
}: PushSettingsProps) {
  if (loading || !settings) {
    return (
      <div className={`text-xs text-muted-foreground ${className}`}>
        {loading ? 'Loading push settings...' : ''}
      </div>
    );
  }

  const handleToggle = () => {
    onUpdate?.({ ...settings, auto_push: !settings.auto_push });
  };

  const handleThreshold = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onUpdate?.({
      ...settings,
      min_significance: e.target.value as PushSettingsData['min_significance'],
    });
  };

  const handleProject = (e: React.ChangeEvent<HTMLInputElement>) => {
    onUpdate?.({ ...settings, paperclip_project: e.target.value });
  };

  return (
    <div className={`space-y-2.5 ${className}`}>
      <h4 className="text-xs font-medium text-muted-foreground">Push Settings</h4>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <input
          type="checkbox"
          checked={settings.auto_push}
          onChange={handleToggle}
          className="rounded border-border"
        />
        <span>Auto-push findings to Paperclip</span>
      </label>
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground shrink-0">Threshold:</label>
        <select
          value={settings.min_significance}
          onChange={handleThreshold}
          className="flex-1 px-2 py-1 text-xs bg-surface border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-primary text-text"
        >
          {SIGNIFICANCE_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground shrink-0">Project:</label>
        <input
          type="text"
          value={settings.paperclip_project}
          onChange={handleProject}
          placeholder="auto-detect"
          className="flex-1 px-2 py-1 text-xs bg-surface border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-primary text-text"
        />
      </div>
    </div>
  );
}
