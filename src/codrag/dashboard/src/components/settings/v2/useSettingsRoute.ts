// src/codrag/dashboard/src/components/settings/v2/useSettingsRoute.ts
import { useCallback, useEffect, useState } from 'react';
import {
  parseSettingsParam, buildSettingsParam, type SettingsPageId,
} from './routeParser';

/**
 * Reads `?settings=<page>` and exposes a setter that updates the URL via
 * replaceState (no history spam) while syncing an internal React state.
 */
export function useSettingsRoute() {
  const [page, setPageState] = useState<SettingsPageId | null>(
    () => parseSettingsParam(window.location.search),
  );

  useEffect(() => {
    const onPop = () => setPageState(parseSettingsParam(window.location.search));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const setPage = useCallback((next: SettingsPageId | null) => {
    const nextSearch = buildSettingsParam(window.location.search, next);
    const url = window.location.pathname + nextSearch + window.location.hash;
    // replaceState: clicking nav items does not pollute history
    window.history.replaceState(window.history.state, '', url);
    setPageState(next);
  }, []);

  const openAt = useCallback((next: SettingsPageId) => {
    const nextSearch = buildSettingsParam(window.location.search, next);
    const url = window.location.pathname + nextSearch + window.location.hash;
    // pushState: opening settings creates a single history entry so
    // browser back closes it.
    window.history.pushState(window.history.state, '', url);
    setPageState(next);
  }, []);

  const close = useCallback(() => {
    const nextSearch = buildSettingsParam(window.location.search, null);
    const url = window.location.pathname + nextSearch + window.location.hash;
    window.history.replaceState(window.history.state, '', url);
    setPageState(null);
  }, []);

  return { page, setPage, openAt, close };
}
