import type { LucideIcon } from 'lucide-react';

/**
 * Panel configuration for user-saved layout
 */
export interface PanelConfig {
  id: string;
  visible: boolean;
  height: number;      // Grid row units
  collapsed: boolean;
  x?: number;
  y?: number;
  w?: number;
}

/**
 * Full dashboard layout schema
 */
export interface DashboardLayout {
  version: number;
  panels: PanelConfig[];
  /** Unix ms timestamp of last user-initiated layout change. Used to resolve
   *  conflicts between localStorage (may have unsaved changes) and backend
   *  (may be stale if a save failed). */
  savedAt?: number;
}

/**
 * Panel category for grouping in picker
 */
export type PanelCategory = 'status' | 'search' | 'context' | 'config' | 'projects';

/**
 * Panel definition for registry
 */
export interface PanelDefinition {
  id: string;
  title: string;
  description?: string;
  icon: LucideIcon;
  minHeight: number;
  defaultHeight: number;
  category: PanelCategory;
  closeable?: boolean;  // Can be hidden (default true)
  resizable?: boolean;
  docsUrl?: string;
  fullWidth?: boolean;  // Span all columns
  /** Remove default p-4 body padding (e.g. for flush panels like LogConsole) */
  noPadding?: boolean;
  /** Dev-only panels are hidden from picker and rendering unless developer mode is on. */
  devOnly?: boolean;
}

/**
 * Props passed to panel content components
 */
export interface PanelProps {
  panelId: string;
  collapsed: boolean;
}

/**
 * Grid layout item (react-grid-layout format)
 */
export interface GridLayoutItem {
  i: string;      // Panel ID
  x: number;
  y: number;      // Row position
  w: number;
  h: number;      // Height in grid units
  minH?: number;  // Minimum height
  static?: boolean;
  isResizable?: boolean;
}

/**
 * Default layout configuration
 */
export const DEFAULT_LAYOUT: DashboardLayout = {
  version: 20,
  panels: [
    {
      id: "status",
      visible: true,
      height: 4,
      collapsed: false,
      x: 0,
      y: 0,
      w: 4
    },
    {
      id: "graph-structure",
      visible: true,
      height: 10,
      collapsed: false,
      x: 8,
      y: 0,
      w: 4
    },
    {
      id: "usage-guide",
      visible: true,
      height: 6,
      collapsed: false,
      x: 4,
      y: 0,
      w: 4
    },
    {
      id: "file-tree",
      visible: true,
      height: 16,
      collapsed: false,
      x: 0,
      y: 4,
      w: 4
    },
    {
      id: "context-options",
      visible: true,
      height: 7,
      collapsed: false,
      x: 4,
      y: 6,
      w: 4
    },
    {
      id: "results",
      visible: true,
      height: 9,
      collapsed: false,
      x: 4,
      y: 13,
      w: 4
    },
    {
      id: "trace",
      visible: true,
      height: 13,
      collapsed: false,
      x: 8,
      y: 10,
      w: 4
    },
    {
      id: "search",
      visible: true,
      height: 6,
      collapsed: false,
      x: 0,
      y: 20,
      w: 4
    },
    {
      id: "context-output",
      visible: true,
      height: 10,
      collapsed: false,
      x: 4,
      y: 22,
      w: 4
    },
    {
      id: "llm-status",
      visible: false,
      height: 6,
      collapsed: false,
      x: 0,
      y: 26,
      w: 4
    },
    {
      id: "log-console",
      visible: true,
      height: 6,
      collapsed: false,
      x: 0,
      y: 32,
      w: 4
    },
    {
      id: "trace-pipeline",
      visible: true,
      height: 5,
      collapsed: false,
      x: 8,
      y: 23,
      w: 4
    },
    {
      id: "deep-analysis",
      visible: true,
      height: 12,
      collapsed: false,
      x: 8,
      y: 28,
      w: 4
    },
    {
      id: "watch",
      visible: false,
      height: 4,
      collapsed: false,
      x: 0,
      y: 0,
      w: 4
    },
    {
      id: "agent-ops",
      visible: true,
      height: 6,
      collapsed: false,
      x: 0,
      y: 38,
      w: 4
    },
    {
      id: "agent-scope",
      visible: true,
      height: 10,
      collapsed: false,
      x: 4,
      y: 38,
      w: 4
    }
  ]
};

/**
 * Storage key for localStorage
 */
export const LAYOUT_STORAGE_KEY = 'prep_dashboard_layout';

/**
 * Convert DashboardLayout to react-grid-layout format
 */
export function toGridLayout(layout: DashboardLayout, definitions?: PanelDefinition[]): GridLayoutItem[] {
  const visiblePanels = layout.panels.filter((p) => p.visible);
  const defaultById = new Map(DEFAULT_LAYOUT.panels.map((p) => [p.id, p] as const));

  // Group by (x,w) so each column stacks independently.
  const groups = new Map<string, PanelConfig[]>();
  for (const p of visiblePanels) {
    const def = defaultById.get(p.id);
    const x = typeof p.x === 'number' ? p.x : (def?.x ?? 0);
    const w = typeof p.w === 'number' ? p.w : (def?.w ?? 12);
    const key = `${x}:${w}`;
    const list = groups.get(key);
    if (list) list.push(p);
    else groups.set(key, [p]);
  }

  const orderKeyFor = (id: string): number => {
    const def = defaultById.get(id);
    if (!def) return Number.POSITIVE_INFINITY;
    return typeof def.y === 'number' ? def.y : DEFAULT_LAYOUT.panels.findIndex((p) => p.id === id);
  };

  const result: GridLayoutItem[] = [];

  for (const group of groups.values()) {
    const sorted = [...group].sort((a, b) => orderKeyFor(a.id) - orderKeyFor(b.id));
    let nextY = 0;

    for (const panel of sorted) {
      const defaultPanel = defaultById.get(panel.id);
      const def = definitions?.find((d) => d.id === panel.id);
      const x = typeof panel.x === 'number' ? panel.x : (defaultPanel?.x ?? 0);
      let w = typeof panel.w === 'number' ? panel.w : (defaultPanel?.w ?? 12);
      
      if (def?.fullWidth) {
        w = BASE_COLS;
      }

      const y = typeof panel.y === 'number' ? panel.y : nextY;
      const h = panel.collapsed ? 2 : Math.max(2, panel.height);
      const minH = panel.collapsed ? 2 : Math.max(2, def?.minHeight ?? 2);
      const isResizable = panel.collapsed ? false : (def?.resizable ?? true);

      result.push({
        i: panel.id,
        x: def?.fullWidth ? 0 : x, // Force x=0 for full logic
        y,
        w,
        h,
        minH,
        isResizable,
      });

      nextY = Math.max(nextY, y + h);
    }
  }

  return result;
}
/**
 * Base column count for the dashboard grid.
 * The grid dynamically adds columns on the sides when the window is wide enough.
 */
export const BASE_COLS = 12;

/**
 * Compute how many grid columns to use for a given container width.
 * Columns grow wider until they exceed maxColWidth, then we add 2 more
 * (one on each side) and repeat.
 *
 * @returns An even number >= BASE_COLS
 */
export function computeGridCols(
  width: number,
  marginX: number,
  maxColWidth: number = 120,
): number {
  // colWidth = (width - margin * (cols + 1)) / cols
  // We want colWidth <= maxColWidth:
  //   (width - margin * (cols + 1)) / cols <= maxColWidth
  //   width - margin <= cols * (maxColWidth + margin)
  //   cols >= (width - margin) / (maxColWidth + margin)
  const minCols = Math.ceil((width - marginX) / (maxColWidth + marginX));

  if (minCols <= BASE_COLS) return BASE_COLS;

  // Round up to BASE_COLS + even number (symmetric: 1 col added per side)
  const extra = minCols - BASE_COLS;
  const roundedExtra = extra % 2 === 0 ? extra : extra + 1;
  return BASE_COLS + roundedExtra;
}

/**
 * Adjust panel positions when the grid column count changes.
 *
 * When cols increases the panels are shifted right so empty columns
 * appear symmetrically on the left and right. When cols decreases the
 * panels are shifted left and any that fall outside the new bounds are
 * clamped. react-grid-layout's vertical compaction will resolve any
 * overlaps introduced by clamping.
 */
export function adjustLayoutForColChange(
  layout: DashboardLayout,
  prevCols: number,
  newCols: number,
): DashboardLayout {
  if (prevCols === newCols) return layout;

  const delta = Math.floor((newCols - prevCols) / 2);

  return {
    ...layout,
    panels: layout.panels.map((panel) => {
      if (!panel.visible) return panel;

      const w = Math.min(panel.w ?? BASE_COLS, newCols);
      const rawX = (panel.x ?? 0) + delta;
      const x = Math.max(0, Math.min(rawX, newCols - w));

      return { ...panel, x, w };
    }),
  };
}

/**
 * Reflow layout so all panels fit within a given column count.
 *
 * Panels are sorted by visual position (y then x), then placed row by row.
 * A panel that would overflow the current row wraps to the next one.
 * Hidden panels are preserved unchanged.
 */
export function reflowLayout(
  layout: DashboardLayout,
  cols: number = 12
): DashboardLayout {
  const visible = layout.panels.filter((p) => p.visible);
  const hidden = layout.panels.filter((p) => !p.visible);

  // Sort by y then x to preserve visual reading order
  const sorted = [...visible].sort((a, b) => {
    const ay = a.y ?? 0;
    const by = b.y ?? 0;
    if (ay !== by) return ay - by;
    return (a.x ?? 0) - (b.x ?? 0);
  });

  let currentX = 0;
  let currentY = 0;
  let rowMaxH = 0;

  const reflowed: PanelConfig[] = sorted.map((panel) => {
    const w = Math.min(panel.w ?? cols, cols);

    if (currentX + w > cols) {
      // Wrap to next row
      currentY += rowMaxH;
      currentX = 0;
      rowMaxH = 0;
    }

    const result: PanelConfig = {
      ...panel,
      x: currentX,
      y: currentY,
      w,
    };

    currentX += w;
    rowMaxH = Math.max(rowMaxH, panel.height);
    return result;
  });

  return {
    ...layout,
    panels: [...reflowed, ...hidden],
  };
}

/**
 * Update DashboardLayout from react-grid-layout changes
 */
export function fromGridLayout(
  current: DashboardLayout,
  gridItems: GridLayoutItem[]
): DashboardLayout {
  // Sort by y position to get order
  const sorted = [...gridItems].sort((a, b) => a.y - b.y);
  
  // Build new panels array preserving hidden panels
  const visibleIds = new Set(sorted.map(item => item.i));
  const hiddenPanels = current.panels.filter(p => !visibleIds.has(p.id));
  
  const updatedPanels: PanelConfig[] = sorted.map(item => {
    const existing = current.panels.find(p => p.id === item.i);
    const isCollapsed = existing?.collapsed ?? false;
    return {
      id: item.i,
      visible: true,
      // Keep the stored height when collapsed — the grid h=2 is just a display value
      height: isCollapsed ? (existing?.height ?? item.h) : item.h,
      collapsed: isCollapsed,
      x: item.x,
      y: item.y,
      w: item.w,
    };
  });
  
  // Append hidden panels at the end
  hiddenPanels.forEach(p => updatedPanels.push({ ...p, visible: false }));
  
  return {
    version: current.version,
    panels: updatedPanels,
  };
}
