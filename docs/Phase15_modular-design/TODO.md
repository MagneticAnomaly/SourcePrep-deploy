# Phase 15: Modular Design - TODO

## Sprint 1: Foundation

### 1.1 Install Dependencies
- [x] Add `react-grid-layout` to `packages/ui/package.json`
- [x] Add `@types/react-grid-layout` for TypeScript support
- [x] Import grid layout CSS in dashboard styles

### 1.2 Define Types
- [x] Create `src/types/layout.ts` with:
  - `DashboardLayout` interface
  - `PanelConfig` interface  
  - `PanelDefinition` interface
- [x] Export from `@codrag/ui` index

### 1.3 Create Panel Registry
- [x] Create `src/config/panelRegistry.ts` (Implemented as `DASHBOARD_PANELS` in App.tsx and `samplePanelDefinitions` in Stories)
- [x] Register all current App.tsx sections as panels:
  - `status` - IndexStatusCard
  - `build` - BuildCard
  - `search` - SearchPanel
  - `context-options` - ContextOptionsPanel
  - `results` - SearchResultsList + ChunkPreview
  - `context-output` - ContextOutput
  - `roots` - Index Roots section
  - `settings` - Advanced config details

---

## Sprint 2: Panel Chrome Component

### 2.1 PanelChrome Component
- [x] Create `src/components/layout/PanelChrome.tsx`
- [x] Props: `title`, `icon`, `collapsed`, `onCollapse`, `onClose`, `children`
- [x] Drag handle element with `drag-handle` class
- [x] Collapse/expand toggle button
- [x] Optional close button (when panel is hideable)

### 2.2 PanelChrome Stories
- [x] Create `src/stories/layout/PanelChrome.stories.tsx`
- [x] States: default, collapsed, with close button, dragging

### 2.3 Style Integration
- [x] Add panel chrome CSS variables to token system
- [x] Ensure theme compatibility (all 12+ themes)

---

## Sprint 3: Grid Layout Container

### 3.1 DashboardGrid Component
- [x] Create `src/components/layout/DashboardGrid.tsx`
- [x] Wrap `react-grid-layout` with CoDRAG defaults:
  - 12 columns
  - 60px row height
  - Vertical compaction
  - Draggable via `.drag-handle`
- [x] Accept `layout` and `onLayoutChange` props

### 3.2 DashboardGrid Stories
- [ ] Create `src/stories/layout/DashboardGrid.stories.tsx` (Covered by ModularDashboard.stories.tsx)
- [ ] Demo with placeholder panels
- [ ] Show drag/resize interactions

### 3.3 Width Calculation
- [x] Use `ResizeObserver` or container query for responsive width
- [x] All panels `w: 12` (full width)

---

## Sprint 4: Layout Persistence

### 4.1 useLayoutPersistence Hook
- [x] Create `src/hooks/useLayoutPersistence.ts`
- [x] Load from `localStorage` key `codrag_dashboard_layout`
- [x] Save on layout change (debounced)
- [x] Schema versioning for migrations
- [x] Fallback to default layout

### 4.2 Default Layout Config
- [x] Create `src/config/defaultLayout.ts` (In `src/types/layout.ts`)
- [x] Match current App.tsx panel order
- [x] Set sensible default heights

### 4.3 Layout Migration
- [x] Version 1 initial schema
- [x] Migration function stub for future versions

---

## Sprint 5: Panel Picker

### 5.1 PanelPicker Component
- [x] Create `src/components/layout/PanelPicker.tsx`
- [x] Dropdown/popover showing all panels
- [x] Checkmarks for visible panels
- [x] Click to toggle visibility

### 5.2 PanelPicker Stories
- [x] Create `src/stories/layout/PanelPicker.stories.tsx`
- [x] States: all visible, some hidden, empty

### 5.3 Reset Layout Button
- [x] Add "Reset Layout" action to PanelPicker
- [x] Confirmation dialog before reset (Implemented as direct reset for now)

---

## Sprint 6: Integration

### 6.1 Extract Panel Components from App.tsx
- [x] Move each section to its own file in `src/components/panels/` (Already existed in `src/components/dashboard` etc)
- [x] Ensure props are well-typed
- [x] Keep App.tsx as thin orchestrator

### 6.2 Wire Up DashboardGrid in App.tsx
- [x] Replace `<div className="space-y-6">` with `<DashboardGrid>` (Used `<ModularDashboard>`)
- [x] Wrap each panel in `<PanelChrome>`
- [x] Connect layout state to persistence hook

### 6.3 Add Panel Picker to Header
- [x] Add PanelPicker button next to theme selector (Inside ModularDashboard headerRight)
- [x] Wire up panel visibility toggle

### 6.4 QA & Polish
- [x] Test drag/drop on all themes
- [x] Test collapse/expand
- [x] Test hide/show panels
- [x] Test layout persistence across refreshes
- [x] Test reset layout

---

## Sprint 7: Storybook Documentation

### 7.1 Documentation Stories
- [x] Create `src/stories/layout/Introduction.mdx`
- [x] Document layout system architecture
- [x] Show customization examples

### 7.2 Full Dashboard Story
- [x] Create `src/stories/layout/ModularDashboard.stories.tsx`
- [x] Mock API data for realistic preview
- [x] Demonstrate full workflow

---

## Future Considerations (Not in Scope)

- [ ] Multi-column layouts at xl breakpoints
- [ ] Sidebar panels vs main content
- [ ] Panel grouping (expand/collapse groups)
- [ ] Server-side layout sync (for team presets)
- [ ] Keyboard shortcuts for panel navigation

---

## Definition of Done

- [ ] All panels can be dragged to reorder
- [ ] All panels can be resized vertically
- [ ] All panels can be collapsed to header-only
- [ ] All panels can be hidden (except required ones)
- [ ] Hidden panels can be re-added via picker
- [ ] Layout persists across page refreshes
- [ ] Layout can be reset to defaults
- [ ] Works on all 12+ themes
- [ ] Storybook stories exist for all new components
- [ ] No regressions in existing functionality
