// src/prep/dashboard/src/components/settings/v2/useSettingsRoute.ts
import { useCallback, useEffect, useState } from 'react';
import {
  parseSettingsParam, buildSettingsParam, type SettingsPageId,
} from './routeParser';

/**
 * Reads `?settings=<page>` and exposes a setter that updates the URL via
 * replaceState (no history spam) while syncing an internal React state.
 *
 * @param confirmCloseIfDirty Optional guard invoked when a popstate event
 * would close the overlay (e.g. browser back). Return `true` to allow the
 * close, `false` to cancel — the URL is re-pushed to the previous page so
 * the overlay stays open.
 */
export function useSettingsRoute(confirmCloseIfDirty?: () => boolean) {
  const [page, setPageState] = useState<SettingsPageId | null>(
    () => parseSettingsParam(window.location.search),
  );

  useEffect(() => {
    const onPop = () => {
      const nextPage = parseSettingsParam(window.location.search);
      if (page !== null && nextPage === null && confirmCloseIfDirty && !confirmCloseIfDirty()) {
        // User cancelled close — push the old page back into URL so the
        // overlay remains open on the page they were editing.
        const restoreUrl = window.location.pathname +
          buildSettingsParam('', page) + window.location.hash;
        window.history.pushState(window.history.state, '', restoreUrl);
        return;
      }
      setPageState(nextPage);
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, [page, confirmCloseIfDirty]);

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
