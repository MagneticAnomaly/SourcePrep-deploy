import { describe, it, expect } from 'vitest';
import { filterPagesForBuild } from '../devGate';
import { PROJECT_PAGES, GLOBAL_PAGES, DEVELOPER_PAGES } from '../routeParser';

describe('filterPagesForBuild', () => {
  it('keeps all pages in dev builds', () => {
    const result = filterPagesForBuild(true);
    expect(result.project).toEqual([...PROJECT_PAGES]);
    expect(result.global).toEqual([...GLOBAL_PAGES]);
    expect(result.developer).toEqual([...DEVELOPER_PAGES]);
  });
  it('drops Developer pages in production builds', () => {
    const result = filterPagesForBuild(false);
    expect(result.project).toEqual([...PROJECT_PAGES]);
    expect(result.global).toEqual([...GLOBAL_PAGES]);
    expect(result.developer).toEqual([]);
  });
});
