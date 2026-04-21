import { describe, it, expect } from 'vitest';
import { scopeChipLabel, scopeAriaLabel } from '../scope';

describe('scopeChipLabel', () => {
  it('returns "Project" for project', () => {
    expect(scopeChipLabel('project')).toBe('Project');
  });
  it('returns "Global" for global', () => {
    expect(scopeChipLabel('global')).toBe('Global');
  });
  it('returns "Developer" for developer', () => {
    expect(scopeChipLabel('developer')).toBe('Developer');
  });
});

describe('scopeAriaLabel', () => {
  it('describes project-scope', () => {
    expect(scopeAriaLabel('project')).toBe('Project-scoped setting');
  });
  it('describes global-scope', () => {
    expect(scopeAriaLabel('global')).toBe('Global-scoped setting');
  });
  it('describes developer-scope', () => {
    expect(scopeAriaLabel('developer')).toBe('Developer-only setting');
  });
});
