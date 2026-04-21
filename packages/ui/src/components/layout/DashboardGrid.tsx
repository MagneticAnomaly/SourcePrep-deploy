import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import GridLayout from 'react-grid-layout';
import type { Layout } from 'react-grid-layout';
import type { ReactNode } from 'react';
import { cn } from '../../lib/utils';
import type { DashboardLayout, GridLayoutItem, PanelDefinition } from '../../types/layout';
import { toGridLayout, fromGridLayout, computeGridCols, BASE_COLS } from '../../types/layout';

import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

export interface DashboardGridProps {
  layout: DashboardLayout;
  panelDefinitions?: PanelDefinition[];
  onLayoutChange: (layout: DashboardLayout) => void;
  children: ReactNode;
  className?: string;
  rowHeight?: number;
  margin?: [number, number];
  maxColWidth?: number;
}

export function DashboardGrid({
  layout,
  panelDefinitions,
  onLayoutChange,
  children,
  className,
  rowHeight = 20,
  margin = [24, 24],
  maxColWidth = 120,
}: DashboardGridProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1200);

  // Measure container width
  useEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setWidth(entry.contentRect.width);
      }
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Compute dynamic column count from measured width
  const cols = useMemo(
    () => computeGridCols(width, margin[0], maxColWidth),
    [width, margin, maxColWidth],
  );

  // Centering offset: extra cols split evenly left/right
  const colOffset = Math.floor((cols - BASE_COLS) / 2);

  // Convert our layout format to react-grid-layout format, adding centering offset
  const gridLayout = useMemo(
    () => toGridLayout(layout, panelDefinitions).map((item) => ({
      ...item,
      x: Math.max(0, Math.min(item.x + colOffset, cols - item.w)),
    })),
    [layout, panelDefinitions, colOffset, cols],
  );

  const handleLayoutCommit = useCallback(
    (newLayout: Layout[]) => {
      const items: GridLayoutItem[] = newLayout.map((item) => {
        const isResizableItem = (item as any).isResizable;
        const existing = layout.panels.find((p) => p.id === item.i);

        return {
          i: item.i,
          x: Math.max(0, item.x - colOffset),
          y: item.y,
          w: item.w,
          h: isResizableItem === false && existing && !existing.collapsed ? existing.height : item.h,
          minH: item.minH,
          isResizable: isResizableItem,
        };
      });
      const updated = fromGridLayout(layout, items);
      onLayoutChange(updated);
    },
    [layout, onLayoutChange, colOffset]
  );

  return (
    <div
      ref={containerRef}
      className={cn('prep-dashboard-grid w-full overflow-x-hidden', className)}
    >
      <GridLayout
        className="layout"
        layout={gridLayout}
        cols={cols}
        rowHeight={rowHeight}
        width={width}
        margin={margin}
        containerPadding={margin}
        onDragStop={handleLayoutCommit}
        onResizeStop={handleLayoutCommit}
        draggableHandle=".drag-handle"
        isResizable={true}
        resizeHandles={['s', 'e', 'se']}
        compactType="vertical"
        preventCollision={false}
        useCSSTransforms={true}
      >
        {children}
      </GridLayout>
    </div>
  );
}
