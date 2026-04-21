# Phase 15: Modular Dashboard Design

## Overview

The Prep dashboard needs a modular, user-configurable layout system that allows components to be rearranged and resized. This enables users to customize their workspace based on their workflow preferences.

## Core Constraints

| Constraint | Decision |
|------------|----------|
| **Component Width** | Always 100% of grid column (no side-by-side within a cell) |
| **Layout Scope** | App dashboard only (not marketing/web views). Marketing sites use standard responsive layouts. |
| **Persistence** | User preferences stored locally, restored on reload |
| **Defaults** | Ship with sensible default positions; users override as needed |

## Architecture Decision: `react-grid-layout`

After researching options, **react-grid-layout** is the recommended library:

- **Battle-tested**: 19k+ GitHub stars, actively maintained
- **Drag & drop**: Native support for rearranging
- **Resizable**: Grid-snapped resizing with min/max constraints
- **Responsive**: Breakpoint support (though we'll use single-column for now)
- **Persistence-ready**: Layout is a simple JSON array, easy to save/restore
- **Storybook-friendly**: Components can be developed in isolation

### Alternative Considered

| Library | Pros | Cons |
|---------|------|------|
| `react-grid-layout` | Mature, full-featured, well-documented | Slightly larger bundle |
| `@dnd-kit/core` | Modern, tree-shakeable | Requires more custom work for grid snapping |
| `react-mosaic` | IDE-like tiling | Overkill for our use case |
| Custom CSS Grid | Zero deps | Significant dev time for drag/resize |

**Decision**: Use `react-grid-layout` for fastest time-to-value.

---

## Design Principles

### 1. Component Agnostic Layout

The layout system wraps existing components without modifying them:

```tsx
<GridLayout layout={userLayout} onLayoutChange={saveLayout}>
  <div key="status"><IndexStatusCard {...props} /></div>
  <div key="build"><BuildCard {...props} /></div>
  <div key="search"><SearchPanel {...props} /></div>
  {/* ... */}
</GridLayout>
```

### 2. 100% Width Assumption

All components span the full width of their grid cell. This simplifies:
- Responsive behavior
- Component design (no width variants needed)
- User mental model (vertical stacking only)

### 3. User Preference Persistence

```typescript
interface DashboardLayout {
  version: number;           // Schema version for migrations
  panels: PanelConfig[];     // Ordered list of visible panels
}

interface PanelConfig {
  id: string;                // e.g., "status", "search", "context"
  visible: boolean;          // Can hide panels
  height: number;            // Grid units (min 1)
  collapsed: boolean;        // Collapsed to header-only
}
```

Storage: `localStorage` key `prep_dashboard_layout`

### 4. Default Layout

Ship with a sensible default that matches current hardcoded layout:

```typescript
const DEFAULT_LAYOUT: DashboardLayout = {
  version: 1,
  panels: [
    { id: 'status', visible: true, height: 2, collapsed: false },
    { id: 'build', visible: true, height: 2, collapsed: false },
    { id: 'search', visible: true, height: 3, collapsed: false },
    { id: 'context-options', visible: true, height: 2, collapsed: false },
    { id: 'results', visible: true, height: 4, collapsed: false },
    { id: 'context-output', visible: true, height: 4, collapsed: false },
    { id: 'roots', visible: true, height: 5, collapsed: false },
    { id: 'settings', visible: true, height: 4, collapsed: true },
  ]
};
```

---

## Component Registry

Each panel must be registered with metadata:

```typescript
interface PanelDefinition {
  id: string;
  title: string;
  icon: LucideIcon;
  minHeight: number;         // Minimum grid units
  defaultHeight: number;     // Initial grid units
  component: React.ComponentType<PanelProps>;
  category: 'status' | 'search' | 'context' | 'config';
}

const PANEL_REGISTRY: PanelDefinition[] = [
  { id: 'status', title: 'Index Status', icon: Database, minHeight: 2, defaultHeight: 2, component: IndexStatusCard, category: 'status' },
  { id: 'build', title: 'Build', icon: Hammer, minHeight: 2, defaultHeight: 2, component: BuildCard, category: 'status' },
  // ...
];
```

---

## UI Elements

### Panel Chrome

Each panel gets a consistent wrapper:

```
┌─────────────────────────────────────────┐
│ ≡ [Icon] Title                    ▼ ✕ │  <- Drag handle, collapse, close
├─────────────────────────────────────────┤
│                                         │
│           Panel Content                 │
│                                         │
├─────────────────────────────────────────┤
│ ════════════════════════════════════════│  <- Resize handle (bottom edge)
└─────────────────────────────────────────┘
```

**Controls**:
- **Drag handle** (≡): Click-and-drag to reorder
- **Collapse** (▼): Toggle between full/collapsed
- **Close** (✕): Hide panel (recoverable from panel picker)

### Panel Picker

A toolbar or dropdown to add hidden panels back:

```
[+ Add Panel] -> Dropdown:
  □ Index Status (visible)
  □ Build (visible)  
  ☑ Search (hidden - click to show)
  ...
```

### Reset Layout

Button to restore default layout:

```
[Reset Layout] -> Confirmation dialog -> Restore defaults
```

---

## Storybook Integration

### Stories to Create

1. **PanelChrome.stories.tsx** - Panel wrapper with drag/collapse/close
2. **GridLayout.stories.tsx** - Layout container with sample panels
3. **PanelPicker.stories.tsx** - Add panel dropdown
4. **ModularDashboard.stories.tsx** - Full integration example

### Storybook Addons

Consider `@storybook/addon-viewport` for testing different screen sizes.

---

## Migration Path

### Phase 1: Extract Panel Components
Current `App.tsx` has inline JSX. Extract each section into standalone panel components.

### Phase 2: Add Panel Chrome
Wrap each panel with the chrome component (drag handle, controls).

### Phase 3: Integrate Grid Layout
Replace the current `<div className="space-y-6">` with `<GridLayout>`.

### Phase 4: Add Persistence
Save/restore layout from localStorage.

### Phase 5: Add Panel Picker
Let users add back hidden panels.

---

## Technical Notes

### react-grid-layout Basics

```bash
npm install react-grid-layout
```

```tsx
import GridLayout from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

const layout = [
  { i: 'a', x: 0, y: 0, w: 12, h: 2 },
  { i: 'b', x: 0, y: 2, w: 12, h: 3 },
];

<GridLayout
  className="layout"
  layout={layout}
  cols={12}
  rowHeight={60}
  width={1200}
  onLayoutChange={(newLayout) => saveToStorage(newLayout)}
  draggableHandle=".drag-handle"
  isResizable={true}
  compactType="vertical"
>
  <div key="a">Panel A</div>
  <div key="b">Panel B</div>
</GridLayout>
```

### Responsive Consideration

For now, single breakpoint (desktop). Future: `<ResponsiveGridLayout>` with breakpoints.

### Performance

- Use `useMemo` for layout calculations
- Avoid re-renders during drag with proper key stability
- Consider `React.memo` for panel components

---

## Open Questions

1. **Sidebar panels?** Current design has main content only. Should settings/roots be in a collapsible sidebar instead?
2. **Multi-column?** Current spec is 100% width. Allow 2-column at xl breakpoints?
3. **Panel groups?** Group related panels (e.g., all search panels) that expand/collapse together?

---

## References

- [react-grid-layout GitHub](https://github.com/react-grid-layout/react-grid-layout)
- [react-grid-layout Demo](https://react-grid-layout.github.io/react-grid-layout/examples/0-showcase.html)
- [Storybook Addon Viewport](https://storybook.js.org/docs/essentials/viewport)
