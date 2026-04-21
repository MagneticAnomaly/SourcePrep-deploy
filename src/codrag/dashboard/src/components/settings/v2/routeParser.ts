export const PROJECT_PAGES = [
  'sources', 'trace-indexing', 'deep-analysis', 'danger-zone',
] as const;

export const GLOBAL_PAGES = [
  'appearance', 'chunking-embeddings', 'pipeline-defaults', 'license', 'integrations',
] as const;

export const DEVELOPER_PAGES = [
  'developer-debug', 'developer-diagnostics', 'developer-reset',
] as const;

export type ProjectPageId = typeof PROJECT_PAGES[number];
export type GlobalPageId = typeof GLOBAL_PAGES[number];
export type DeveloperPageId = typeof DEVELOPER_PAGES[number];
export type SettingsPageId = ProjectPageId | GlobalPageId | DeveloperPageId;

const ALL: readonly string[] = [...PROJECT_PAGES, ...GLOBAL_PAGES, ...DEVELOPER_PAGES];

export function isKnownPage(id: string): id is SettingsPageId {
  return ALL.includes(id);
}

export function parseSettingsParam(search: string): SettingsPageId | null {
  const params = new URLSearchParams(search);
  const raw = params.get('settings');
  if (!raw) return null;
  return isKnownPage(raw) ? raw : null;
}

export function buildSettingsParam(search: string, page: SettingsPageId | null): string {
  const params = new URLSearchParams(search);
  if (page === null) params.delete('settings');
  else params.set('settings', page);
  const out = params.toString();
  return out ? `?${out}` : '';
}

export function scopeForPage(id: SettingsPageId): 'project' | 'global' | 'developer' {
  if ((PROJECT_PAGES as readonly string[]).includes(id)) return 'project';
  if ((GLOBAL_PAGES as readonly string[]).includes(id)) return 'global';
  return 'developer';
}
