import { useCallback, useEffect, useRef, useState } from 'react';
import type { DashboardLayout } from '../../types/layout';
import { DEFAULT_LAYOUT, LAYOUT_STORAGE_KEY, reflowLayout as reflowLayoutUtil } from '../../types/layout';

interface UseLayoutPersistenceOptions {
  storageKey?: string;
  debounceMs?: number;
}

interface UseLayoutPersistenceReturn {
  layout: DashboardLayout;
  updateLayout: (layout: DashboardLayout) => void;
  togglePanelVisibility: (panelId: string) => void;
  togglePanelCollapsed: (panelId: string) => void;
  resetLayout: () => void;
  reflowLayout: () => void;
  setPanelHeight: (panelId: string, height: number) => void;
  addPanel: (panelId: string, options?: { height?: number; x?: number; w?: number }) => void;
  removePanel: (panelId: string) => void;
}

/** Stamp the current time on a layout so we can resolve local-vs-backend conflicts. */
function stamp(layout: DashboardLayout): DashboardLayout {
  return { ...layout, savedAt: Date.now() };
}

function loadLayout(key: string): DashboardLayout | null {
  try {
    const stored = localStorage.getItem(key);
    if (!stored) {
      console.debug('[Layout] No saved layout found in localStorage');
      return null;
    }
    const parsed = JSON.parse(stored) as DashboardLayout;
    // Basic validation
    if (typeof parsed.version !== 'number' || !Array.isArray(parsed.panels)) {
      console.warn('[Layout] Saved layout failed validation, using defaults');
      return null;
    }
    console.debug('[Layout] Restored saved layout (v%d, %d panels)', parsed.version, parsed.panels.length);
    return parsed;
  } catch (e) {
    console.warn('[Layout] Failed to parse saved layout:', e);
    return null;
  }
}

function saveLayout(key: string, layout: DashboardLayout): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(key, JSON.stringify(layout));
  } catch {
    // Storage full or unavailable
  }
}

function migrateLayout(layout: DashboardLayout): DashboardLayout {
  const isOutdated = layout.version < 20;

  // We gently upgrade the layout rather than wiping it
  const upgradedLayout = {
    ...layout,
    version: DEFAULT_LAYOUT.version,
    // Preserve existing savedAt if present; stamp only if missing so the
    // migrated layout won't be overwritten by stale backend data on init.
    savedAt: layout.savedAt ?? Date.now(),
    panels: isOutdated ? layout.panels.map(p => ({
      ...p,
      // Provide backwards compatibility fixes for individual panels here if needed
    })) : layout.panels
  };

  // Ensure all default panels exist (newly added panels)
  const existingIds = new Set(upgradedLayout.panels.map((p) => p.id));
  const missingPanels = DEFAULT_LAYOUT.panels.filter(
    (p) => !existingIds.has(p.id)
  );

  if (missingPanels.length > 0) {
    return {
      ...upgradedLayout,
      panels: [...upgradedLayout.panels, ...missingPanels],
    };
  }

  return upgradedLayout;
}

export function useLayoutPersistence(
  options: UseLayoutPersistenceOptions = {}
): UseLayoutPersistenceReturn {
  const { storageKey = LAYOUT_STORAGE_KEY } = options;

  const [layout, setLayoutState] = useState<DashboardLayout>(() => {
    const stored = loadLayout(storageKey);
    if (stored) {
      return migrateLayout(stored);
    }
    return DEFAULT_LAYOUT;
  });

  // Save to localStorage on every layout change.
  // No debounce — localStorage.setItem is synchronous and fast (~1ms).
  // The previous 500ms debounce caused data loss on page refresh.
  const layoutRef = useRef(layout);
  layoutRef.current = layout;

  useEffect(() => {
    saveLayout(storageKey, layout);
  }, [layout, storageKey]);

  // Safety net: flush on tab close and visibility change (mobile background)
  useEffect(() => {
    const flush = () => saveLayout(storageKey, layoutRef.current);
    const onVisibilityChange = () => { if (document.hidden) flush(); };
    window.addEventListener('beforeunload', flush);
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      window.removeEventListener('beforeunload', flush);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [storageKey]);

  const updateLayout = useCallback((newLayout: DashboardLayout) => {
    setLayoutState(stamp(newLayout));
  }, []);

  const togglePanelVisibility = useCallback((panelId: string) => {
    setLayoutState((current) => {
      const exists = current.panels.some((p) => p.id === panelId);
      if (exists) {
        return stamp({
          ...current,
          panels: current.panels.map((p) =>
            p.id === panelId ? { ...p, visible: !p.visible } : p
          ),
        });
      }
      // Panel not yet in layout — add it as visible
      const maxY = current.panels.reduce((m, p) => {
        const py = (p.y ?? 0) + (p.visible ? p.height : 0);
        return py > m ? py : m;
      }, 0);
      return stamp({
        ...current,
        panels: [
          ...current.panels,
          { id: panelId, visible: true, height: 8, collapsed: false, x: 0, y: maxY, w: 12 },
        ],
      });
    });
  }, []);

  const togglePanelCollapsed = useCallback((panelId: string) => {
    setLayoutState((current) => stamp({
      ...current,
      panels: current.panels.map((p) => {
        if (p.id !== panelId) return p;
        const willCollapse = !p.collapsed;
        if (willCollapse) {
          return { ...p, collapsed: true };
        }
        // Uncollapse — restore to DEFAULT_LAYOUT height as the full-height guideline
        const defaultPanel = DEFAULT_LAYOUT.panels.find((d) => d.id === panelId);
        const fullHeight = defaultPanel?.height ?? p.height;
        return { ...p, collapsed: false, height: Math.max(fullHeight, p.height) };
      }),
    }));
  }, []);

  const resetLayout = useCallback(() => {
    setLayoutState(stamp(DEFAULT_LAYOUT));
  }, []);

  const reflowLayout = useCallback(() => {
    setLayoutState((current) => stamp(reflowLayoutUtil(current)));
  }, []);

  const setPanelHeight = useCallback((panelId: string, height: number) => {
    setLayoutState((current) => stamp({
      ...current,
      panels: current.panels.map((p) =>
        p.id === panelId ? { ...p, height: Math.max(1, height) } : p
      ),
    }));
  }, []);

  const addPanel = useCallback((panelId: string, options?: { height?: number; x?: number; w?: number }) => {
    setLayoutState((current) => {
      const exists = current.panels.some((p) => p.id === panelId);
      if (exists) {
        // Already exists — just make it visible
        return stamp({
          ...current,
          panels: current.panels.map((p) =>
            p.id === panelId ? { ...p, visible: true, collapsed: false } : p
          ),
        });
      }
      // Add new panel entry as visible
      const maxY = current.panels.reduce((m, p) => {
        const py = (p.y ?? 0) + (p.visible ? p.height : 0);
        return py > m ? py : m;
      }, 0);
      return stamp({
        ...current,
        panels: [
          ...current.panels,
          {
            id: panelId,
            visible: true,
            height: options?.height ?? 8,
            collapsed: false,
            x: options?.x ?? 0,
            y: maxY,
            w: options?.w ?? 12,
          },
        ],
      });
    });
  }, []);

  const removePanel = useCallback((panelId: string) => {
    setLayoutState((current) => stamp({
      ...current,
      panels: current.panels.filter((p) => p.id !== panelId),
    }));
  }, []);

  return {
    layout,
    updateLayout,
    togglePanelVisibility,
    togglePanelCollapsed,
    resetLayout,
    reflowLayout,
    setPanelHeight,
    addPanel,
    removePanel,
  };
}
