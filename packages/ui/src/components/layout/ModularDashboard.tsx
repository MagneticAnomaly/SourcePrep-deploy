import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { X } from 'lucide-react';
import { DashboardGrid } from './DashboardGrid';
import { PanelChrome } from './PanelChrome';
import { PanelPicker } from './PanelPicker';
import { useLayoutPersistence } from './useLayoutPersistence';
import type { PanelDefinition } from '../../types/layout';
import { DEFAULT_LAYOUT } from '../../types/layout';
import { cn } from '../../lib/utils';
import { AutoHeightPanel } from './AutoHeightPanel';
import { Button } from '../primitives/Button';

export interface PanelContentMap {
  [panelId: string]: ReactNode;
}

export interface DashboardLayoutApi {
  addPanel: (panelId: string, options?: { height?: number; x?: number; w?: number }) => void;
  removePanel: (panelId: string) => void;
  togglePanelVisibility: (panelId: string) => void;
  openDetails: (panelId: string) => void;
  resetLayout: () => void;
  reflowLayout: () => void;
  copyLayout: () => void;
  pasteLayout: () => void;
}

export interface ModularDashboardProps {
  panelDefinitions: PanelDefinition[];
  panelContent: PanelContentMap;
  panelDetails?: PanelContentMap;
  className?: string;
  headerLeft?: ReactNode;
  headerRight?: ReactNode;
  rowHeight?: number;
  margin?: [number, number];
  maxColWidth?: number;
  storageKey?: string;
  /** Called when a closeable panel is closed (before visibility toggle). */
  onPanelClose?: (panelId: string) => void;
  /** Called once with layout API methods for dynamic panel management. */
  onLayoutReady?: (api: DashboardLayoutApi) => void;
  /** Hide the built-in PanelPicker (when rendering it externally). */
  hidePanelPicker?: boolean;
  /** Called whenever dashboard layout changes (for external PanelPicker). */
  onLayoutChange?: (layout: import('../../types/layout').DashboardLayout) => void;
}

/**
 * ModularDashboard - A complete modular dashboard layout
 * 
 * Wraps DashboardGrid with panel chrome, picker, and persistence.
 * Pass panelDefinitions and panelContent to render panels.
 */
export function ModularDashboard({
  panelDefinitions,
  panelContent,
  panelDetails,
  className,
  headerLeft,
  headerRight,
  rowHeight = 20,
  margin = [24, 24],
  maxColWidth = 120,
  storageKey,
  onPanelClose,
  onLayoutReady,
  hidePanelPicker,
  onLayoutChange,
}: ModularDashboardProps) {
  const {
    layout,
    updateLayout,
    togglePanelVisibility,
    togglePanelCollapsed,
    reflowLayout,
    setPanelHeight,
    addPanel,
    removePanel,
  } = useLayoutPersistence({ storageKey });

  // Reset to default layout — DashboardGrid handles centering at display time
  const handleResetLayout = useCallback(() => {
    updateLayout(DEFAULT_LAYOUT);
  }, [updateLayout]);

  // Copy current layout JSON to clipboard
  const handleCopyLayout = useCallback(() => {
    const json = JSON.stringify(layout, null, 2);
    navigator.clipboard.writeText(json).then(
      () => window.alert('Layout copied to clipboard'),
      () => window.alert('Failed to copy layout'),
    );
  }, [layout]);

  // Paste layout JSON from clipboard
  const handlePasteLayout = useCallback(() => {
    navigator.clipboard.readText().then(
      (text) => {
        try {
          const parsed = JSON.parse(text);
          if (!parsed.panels || !Array.isArray(parsed.panels)) {
            window.alert('Invalid layout: missing panels array');
            return;
          }
          updateLayout(parsed);
        } catch {
          window.alert('Invalid JSON in clipboard');
        }
      },
      () => window.alert('Failed to read clipboard'),
    );
  }, [updateLayout]);

  // Expose layout API to parent once
  useEffect(() => {
    onLayoutReady?.({
      addPanel,
      removePanel,
      togglePanelVisibility,
      openDetails: (panelId: string) => setDetailsPanelId(panelId),
      resetLayout: handleResetLayout,
      reflowLayout,
      copyLayout: handleCopyLayout,
      pasteLayout: handlePasteLayout,
    });
  }, [onLayoutReady, addPanel, removePanel, togglePanelVisibility, handleResetLayout, reflowLayout, handleCopyLayout, handlePasteLayout]);

  // Notify parent of layout changes
  useEffect(() => {
    onLayoutChange?.(layout);
  }, [layout, onLayoutChange]);

  const [pendingHeights, setPendingHeights] = useState<Record<string, number>>({});
  const [detailsPanelId, setDetailsPanelId] = useState<string | null>(null);

  const handleAutoHeight = useCallback(
    (panelId: string, gridUnits: number) => {
      setPendingHeights((prev: Record<string, number>) => {
        if (prev[panelId] === gridUnits) return prev;
        return { ...prev, [panelId]: gridUnits };
      });
    },
    []
  );

  useEffect(() => {
    const entries = Object.entries(pendingHeights) as Array<[string, number]>;
    if (entries.length === 0) return;

    for (const [panelId, height] of entries) {
      const panel = layout.panels.find((p) => p.id === panelId);
      if (panel && panel.height !== height && !panel.collapsed) {
        setPanelHeight(panelId, height);
      }
    }

    setPendingHeights({});
  }, [pendingHeights, layout.panels, setPanelHeight]);

  useEffect(() => {
    if (!detailsPanelId) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setDetailsPanelId(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [detailsPanelId]);

  useEffect(() => {
    if (!detailsPanelId) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [detailsPanelId]);

  // Get collapse state for a panel
  const getCollapseState = useCallback(
    (panelId: string) => {
      const panel = layout.panels.find((p) => p.id === panelId);
      return panel?.collapsed ?? false;
    },
    [layout.panels]
  );


  // Get panel definition
  const getDefinition = useCallback(
    (panelId: string) => {
      return panelDefinitions.find((d) => d.id === panelId);
    },
    [panelDefinitions]
  );

  // Visible panels only
  const visiblePanels = useMemo(() => {
    return layout.panels.filter((p) => p.visible);
  }, [layout.panels]);

  const detailsDef = useMemo(() => {
    if (!detailsPanelId) return undefined;
    return getDefinition(detailsPanelId);
  }, [detailsPanelId, getDefinition]);

  const detailsContent = useMemo(() => {
    if (!detailsPanelId) return undefined;
    return panelDetails?.[detailsPanelId];
  }, [detailsPanelId, panelDetails]);

  const DetailsIcon = detailsDef?.icon;

  return (
    <div className={cn('prep-modular-dashboard', className)}>
      {/* Header with Panel Picker — only rendered when there's content */}
      {(headerLeft || headerRight || !hidePanelPicker) && (
        <div className="flex items-center justify-between mb-4">
          <div className="flex-1">
            {headerLeft}
          </div>
          <div className="flex items-center gap-4">
            {headerRight}
            {!hidePanelPicker && (
              <PanelPicker
                layout={layout}
                panelDefinitions={panelDefinitions}
                onTogglePanel={togglePanelVisibility}
                onResetLayout={handleResetLayout}
                onRefitLayout={reflowLayout}
                onCopyLayout={handleCopyLayout}
                onPasteLayout={handlePasteLayout}
              />
            )}
          </div>
        </div>
      )}

      {/* Dashboard Grid */}
      <DashboardGrid
        layout={layout}
        panelDefinitions={panelDefinitions}
        onLayoutChange={updateLayout}
        rowHeight={rowHeight}
        margin={margin}
        maxColWidth={maxColWidth}
      >
        {visiblePanels.map((panel) => {
          const def = getDefinition(panel.id);
          if (!def) return null;

          const collapsed = getCollapseState(panel.id);
          const content = panelContent[panel.id];
          const detailsNode = panelDetails?.[panel.id];
          const canShowDetails = detailsNode != null;

          const isPanelResizable = def.resizable ?? true;

          const contentNode = (
            <div
              className={cn(
                'prep-panel-body flex flex-col',
                !def.noPadding && 'p-4',
                isPanelResizable && 'h-full min-h-0 overflow-hidden'
              )}
            >
              {content ?? (
                <div className="text-sm text-text-muted">Panel content not provided</div>
              )}
            </div>
          );

          const panelNode = (
            <PanelChrome
              title={def.title}
              description={def.description}
              docsUrl={def.docsUrl}
              icon={def.icon}
              collapsed={collapsed}
              onCollapse={() => togglePanelCollapsed(panel.id)}
              onDetails={canShowDetails ? () => setDetailsPanelId(panel.id) : undefined}
              closeable={def.closeable}
              onClose={def.closeable ? () => { onPanelClose?.(panel.id); togglePanelVisibility(panel.id); } : undefined}
              fillHeight={true}
            >
              {contentNode}
            </PanelChrome>
          );

          return (
            <div key={panel.id} className="h-full">
              {isPanelResizable ? (
                panelNode
              ) : (
                <AutoHeightPanel
                  panelId={panel.id}
                  rowHeight={rowHeight}
                  marginY={margin[1] ?? 0}
                  minHeight={def.minHeight}
                  onHeightChange={handleAutoHeight}
                >
                  {panelNode}
                </AutoHeightPanel>
              )}
            </div>
          );
        })}
      </DashboardGrid>

      {detailsPanelId && (
        <div
          className="fixed inset-0 z-50"
          role="dialog"
          aria-modal="true"
        >
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
            onClick={() => setDetailsPanelId(null)}
          />
          <div className="relative z-10 h-full w-full bg-background text-text flex flex-col">
            <div className="flex items-center justify-between gap-4 px-6 py-4 border-b border-border">
              <div className="flex items-center gap-2 min-w-0">
                {DetailsIcon && (
                  <DetailsIcon className="w-5 h-5 text-text-muted flex-shrink-0" />
                )}
                <span className="text-lg font-semibold truncate">
                  {detailsDef?.title ?? 'Details'}
                </span>
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setDetailsPanelId(null)}
                aria-label="Close details"
              >
                <X className="w-5 h-5" />
              </Button>
            </div>
            <div className="flex-1 min-h-0 overflow-auto">
              {detailsContent ?? (
                <div className="p-6 text-sm text-text-muted">No details available</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
