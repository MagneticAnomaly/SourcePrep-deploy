import { describe, it, expect } from 'vitest';
import {
  PROJECT_PAGES, GLOBAL_PAGES, DEVELOPER_PAGES,
  parseSettingsParam, buildSettingsParam, isKnownPage,
} from '../routeParser';

describe('parseSettingsParam', () => {
  it('returns null when search string has no settings param', () => {
    expect(parseSettingsParam('?foo=bar')).toBeNull();
  });
  it('returns the page id when present and known', () => {
    expect(parseSettingsParam('?settings=sources')).toBe('sources');
  });
  it('returns null when the page id is unknown', () => {
    expect(parseSettingsParam('?settings=not-a-page')).toBeNull();
  });
  it('preserves hyphenated page ids', () => {
    expect(parseSettingsParam('?settings=trace-indexing')).toBe('trace-indexing');
  });
});

describe('buildSettingsParam', () => {
  it('writes the param preserving other query keys', () => {
    const s = buildSettingsParam('?foo=bar', 'appearance');
    expect(s).toContain('foo=bar');
    expect(s).toContain('settings=appearance');
  });
  it('removes the param when page is null', () => {
    const s = buildSettingsParam('?foo=bar&settings=sources', null);
    expect(s).toContain('foo=bar');
    expect(s).not.toContain('settings=');
  });
});

describe('isKnownPage', () => {
  it('accepts every Project page', () => {
    for (const p of PROJECT_PAGES) expect(isKnownPage(p)).toBe(true);
  });
  it('accepts every Global page', () => {
    for (const p of GLOBAL_PAGES) expect(isKnownPage(p)).toBe(true);
  });
  it('accepts every Developer page', () => {
    for (const p of DEVELOPER_PAGES) expect(isKnownPage(p)).toBe(true);
  });
  it('rejects unknown ids', () => {
    expect(isKnownPage('zzz')).toBe(false);
  });
});
