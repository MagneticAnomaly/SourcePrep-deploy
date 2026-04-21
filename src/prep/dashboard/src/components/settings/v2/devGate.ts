import { PROJECT_PAGES, GLOBAL_PAGES, DEVELOPER_PAGES } from './routeParser';
import type { SettingsPageId } from './routeParser';

export function isDevBuild(): boolean {
  return !!import.meta.env.DEV;
}

export interface PageSet {
  project: readonly SettingsPageId[];
  global: readonly SettingsPageId[];
  developer: readonly SettingsPageId[];
}

export function filterPagesForBuild(dev: boolean): PageSet {
  return {
    project: [...PROJECT_PAGES],
    global: [...GLOBAL_PAGES],
    developer: dev ? [...DEVELOPER_PAGES] : [],
  };
}
