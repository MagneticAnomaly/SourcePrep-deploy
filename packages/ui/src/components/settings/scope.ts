export type SettingsScope = 'project' | 'global' | 'developer';

export function scopeChipLabel(scope: SettingsScope): string {
  switch (scope) {
    case 'project': return 'Project';
    case 'global': return 'Global';
    case 'developer': return 'Developer';
  }
}

export function scopeAriaLabel(scope: SettingsScope): string {
  switch (scope) {
    case 'project': return 'Project-scoped setting';
    case 'global': return 'Global-scoped setting';
    case 'developer': return 'Developer-only setting';
  }
}
