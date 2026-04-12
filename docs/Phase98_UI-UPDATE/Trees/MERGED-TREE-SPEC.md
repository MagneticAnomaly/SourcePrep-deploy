# Merged File Tree — Design Spec

**Phase 98 — UI Update: Unified Scope Tree**
**Date:** 2026-04-11

## Problem

The dashboard currently has two separate file tree interfaces for managing codebase scope:

1. **Knowledge Sources** (`FolderTreePanel`) — right-side panel. Additive: user selects files/folders to embed in the RAG knowledge base with per-path weights (0.0–2.0). Files not selected are simply not embedded.
2. **Graph Scope > Exclude Tree** (tab inside `GraphStructurePanel`) — left-side panel. Subtractive: user selects files/folders to exclude from the structural trace graph. Excluded files are never parsed by the Rust engine.

Both use the same underlying `FolderTree` component (toggled via `mode: 'include' | 'exclude'`), but they appear in different panels, have different visual treatments, and write to separate backend state. There's also a full-screen `FileExplorerDetail` that duplicates both as tabs.

**Why merge:** The distinction between "files the RAG knows about" and "files the trace graph parses" is an implementation detail. Users think in terms of "files CoDRAG should care about" — they want to include things (with weights) or exclude things. These two actions are mutually exclusive (you can't embed a file that isn't even parsed), so they belong in the same interface.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Exclude semantics | Exclude from **both** trace graph and knowledge base | Clean mental model: excluded = invisible to CoDRAG entirely |
| Mutual exclusion | UI-enforced: a path is excluded XOR included XOR default | Can't embed an unparsed file; prevents conflicting state |
| Row click behavior | **Panel mode:** no-op. **Detail mode:** opens file preview | Replaces the existing Eye hover button; frees click from toggle duty |
| Folder click | Always expand/collapse only — never affects selections | Prevents accidental bulk state changes |
| All selection via right-side icons | Include checkbox + exclude icon, mutually exclusive | Clear, explicit affordances; no hidden click-to-toggle |
| Panel placement | Replaces "Knowledge Sources" panel | Graph Scope keeps Queue + Patterns (pipeline status); tree is user intent |
| Panel name | **"Scope"** | Covers both "what's included" and "what's excluded" |
| Graph Scope cleanup | Drop the "Exclude Tree" tab | Redundant — merged tree handles it; Patterns tab stays for glob power-users |
| Always-ignored files | Render with strikethrough (non-interactive, not dimmed) | Visually distinct from user-excluded; list sourced from `DEFAULT_EXCLUDE_FILE_GLOBS` |
| Exclude persistence | **Bug:** exclude state currently lost on backend restart — fix as part of this work | Exclude paths must round-trip through the project config API reliably |

## Component Architecture

### Modified: `FolderTree` (`packages/ui/src/components/project/FolderTree.tsx`)

The `mode` prop is removed. Both include and exclude state are accepted simultaneously.

```typescript
interface FolderTreeProps {
  data: TreeNode[]

  // Knowledge scope (additive)
  includedPaths?: Set<string>
  pathWeights?: Record<string, number>
  onToggleInclude?: (paths: string[], action: 'add' | 'remove') => void
  onWeightChange?: (path: string, weight: number | null) => void

  // Trace exclusions (subtractive)
  excludedPaths?: Set<string>
  onToggleExclude?: (paths: string[], action: 'add' | 'remove') => void

  // Display variant
  variant?: 'panel' | 'detail'
  onPreviewFile?: (node: TreeNode, path: string) => void  // detail variant only

  // Always-ignored glob patterns (rendered as status='ignored', non-interactive)
  alwaysIgnoredPatterns?: string[]

  // Existing props retained
  onLoadChildren?: (path: string) => Promise<TreeNode[]>
  compact?: boolean
  className?: string
}
```

### Modified: `FolderTreePanel` (`packages/ui/src/components/project/FolderTreePanel.tsx`)

Renamed conceptually to "Scope." Receives both include and exclude props:

```typescript
interface FolderTreePanelProps {
  data: TreeNode[]
  // Include (knowledge scope)
  includedPaths?: Set<string>
  pathWeights?: Record<string, number>
  onToggleInclude?: (paths: string[], action: 'add' | 'remove') => void
  onWeightChange?: (path: string, weight: number | null) => void
  // Exclude (trace scope)
  excludedPaths?: Set<string>
  onToggleExclude?: (paths: string[], action: 'add' | 'remove') => void
  // Existing
  scopeStatus?: ScopeStatus
  onLoadChildren?: (path: string) => Promise<TreeNode[]>
  alwaysIgnoredPatterns?: string[]
  title?: string  // default: "Scope"
  className?: string
  bare?: boolean
}
```

### Modified: `FileExplorerDetail` (`packages/ui/src/components/project/FileExplorerDetail.tsx`)

- Remove the Knowledge/Exclude tab bar entirely.
- Render one `FolderTree` with `variant='detail'` and both include + exclude props.
- Row click triggers file preview (via `onPreviewFile`).
- The `FileExplorerTab` type and `initialTab` prop are removed.

### Modified: `GraphStructurePanel` (`packages/ui/src/components/trace/GraphStructurePanel.tsx`)

- Remove the "Exclude Tree" tab and all related props (`fileTree`, `excludedPaths`, `onToggleExclude`, `onLoadChildren`, `onExpandExcludeTree`).
- Keep Queue + Patterns tabs only.
- The `activeTab` state type becomes `'queue' | 'patterns'`.

### Modified: `panelRegistry.ts`

Update `file-tree` entry:

```typescript
{
  id: 'file-tree',
  title: 'Scope',
  description: 'Manage which files CoDRAG indexes. Include files with weights for RAG priority, or exclude files from the trace graph entirely.',
  icon: FolderTree,
  // ... rest unchanged
}
```

Update `graph-structure` description to remove mention of "Excluded":

```typescript
{
  id: 'graph-structure',
  title: 'Graph Scope',
  description: 'Pipeline file inventory: Queue and exclude patterns.',
  // ... rest unchanged
}
```

### Unchanged

- `AgentScopePanel` — continues using `FolderTree` in its current include-only fashion. It manages per-agent scope, not the main scope. Future profile work will revisit this.
- Backend APIs — `useFileSystem.handleToggleInclude`, `useFileSystem.handlePathWeightChange`, and the exclude-pattern handlers in `useDashboardPanels` are unchanged. The merged tree just dispatches to the appropriate callback.

## Visual Design — Row Layout

### Current row (include mode, left to right)

```
[expand] [icon] [name] ........... [chunks] [status badge] [weight badge]
```

### Current row (exclude mode, left to right)

```
[expand] [icon] [name ~~strikethrough~~]
```

### Merged row (new, left to right)

```
[expand] [icon] [name] ........... [chunks] [status] [weight] [include ☐] [exclude ☐]
```

- **Include control:** Checkbox-style icon. Checked = file is in knowledge scope. Unchecked = not in knowledge scope (but still traced by default).
- **Exclude control:** Ghost/ban icon. Checked = file excluded from trace + knowledge. Unchecked = file is traceable.
- **Mutual exclusion:** Checking one automatically unchecks the other. Both unchecked = default state (traced but not in RAG).
- **Weight badge:** Only visible when include is checked. Clickable to edit (existing `WeightEditor` behavior preserved).
- **Chunks + status badge:** Only visible when include is checked and file has index status.

### Row states

| State | Include icon | Exclude icon | Name style | Background | Right-side extras |
|-------|-------------|-------------|------------|------------|-------------------|
| **Default** | ☐ unchecked | ☐ unchecked | Normal mono | None | — |
| **Included** | ☑ checked (primary) | ☐ unchecked | Bold mono | `bg-primary/5` | chunks, status, weight |
| **Excluded** | ☐ unchecked | ☑ checked (error) | ~~Strikethrough~~ error | `bg-error/8` | — |
| **Always-ignored** | Hidden | Hidden | ~~Strikethrough~~ text-subtle | None | — |

### Folder states

Folders inherit the same four states. Additionally, folders can be **partially included** (some children included but not all):

| Folder state | Include icon | Exclude icon | Visual |
|-------------|-------------|-------------|--------|
| **Partial include** | [—] indeterminate | ☐ | Name semi-bold, `bg-primary/5` faint |
| **Partial exclude** | ☐ | [—] indeterminate | Name semi-dimmed, faint red tint |
| **Mixed** (some children included, others excluded) | [—] | [—] | Both indeterminate; neutral background |

Clicking the include checkbox on a partially-included folder → fully includes (adds folder path). Clicking it on a fully-included folder → removes (existing ancestor-explosion logic applies). Same symmetric behavior for exclude.

### Always-ignored files

Files matching patterns in `DEFAULT_EXCLUDE_FILE_GLOBS` (from `src/codrag/core/repo_profile.py:66-86`) render as `status: 'ignored'`. This list:

- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`
- `.cursorrules`, `.cursorignore`, `.windsurfrules`, `.clinerules`, `.roorules`, `.clineignore`, `.qwencoderules`
- `.cursor/rules/*.mdc`, `.windsurf/rules/*.md`, `.github/copilot-instructions.md`

These render with **strikethrough text** (not dimmed/disabled — they should be visible, just clearly "not yours to toggle"). No include/exclude icons are shown. Tooltip: "Always available to AI assistants — excluded from indexing."

**Delivery mechanism:** The tree receives `alwaysIgnoredPatterns: string[]` as a prop. The component matches each node's path against these patterns (using a simple glob matcher). This keeps the backend authoritative — the dashboard fetches the list from the project config or a new lightweight endpoint, and the UI just renders accordingly.

## Data Flow

### State management (no changes to backend)

```
useDashboardPanels.tsx
├── p.includedPaths        → from useFileSystem (localStorage + API)
├── p.pathWeights           → from useFileSystem (localStorage + API)
├── p.handleToggleInclude   → useFileSystem.handleToggleInclude → api.updateIncludedPaths
├── p.handlePathWeightChange → useFileSystem.handlePathWeightChange → api.updatePathWeights
├── excludedPaths           → local optimistic state (useDashboardPanels ~line 493)
├── handleToggleExclude     → converts path to glob patterns → p.handleAddExcludePattern / p.handleRemoveExcludePattern
└── p.fileTree              → from useFileSystem (shared tree data)
```

The merged `FolderTreePanel` ("Scope") now receives ALL of these. Currently:
- `FolderTreePanel` receives only include-side props.
- `GraphStructurePanel` receives only exclude-side props.

After merge, `FolderTreePanel` receives both. `GraphStructurePanel` loses its tree entirely.

### Mutual exclusion enforcement (in FolderTree click handler)

```typescript
// When user clicks "include" on a currently-excluded path:
if (excludedPaths?.has(path)) {
  onToggleExclude?.([path], 'remove')  // un-exclude first
}
onToggleInclude?.([path], 'add')       // then include

// When user clicks "exclude" on a currently-included path:
if (includedPaths && isPathOrAncestorIncluded(path, includedPaths)) {
  onToggleInclude?.([path], 'remove')  // un-include first
}
onToggleExclude?.([path], 'add')       // then exclude
```

This logic lives in the component, not in `useFileSystem` or `useDashboardPanels`. The backend APIs remain independent — the UI just ensures they're never contradictory.

### Wiring change in `useDashboardPanels.tsx`

The `panelContent['file-tree']` block (currently ~line 687-698) changes from:

```tsx
<FolderTreePanel
  data={p.fileTree}
  includedPaths={p.includedPaths}
  scopeStatus={p.scopeStatus}
  onToggleInclude={p.handleToggleInclude}
  pathWeights={p.pathWeights}
  onWeightChange={p.handlePathWeightChange}
  onLoadChildren={p.handleLoadChildren}
  title="Knowledge Sources"
  bare
/>
```

To:

```tsx
<FolderTreePanel
  data={p.fileTree}
  includedPaths={p.includedPaths}
  scopeStatus={p.scopeStatus}
  onToggleInclude={p.handleToggleInclude}
  pathWeights={p.pathWeights}
  onWeightChange={p.handlePathWeightChange}
  excludedPaths={excludedPaths}
  onToggleExclude={handleToggleExclude}
  onLoadChildren={p.handleLoadChildren}
  alwaysIgnoredPatterns={DEFAULT_EXCLUDE_GLOBS}
  title="Scope"
  bare
/>
```

The `panelContent['graph-structure']` block (~line 869-893) drops `fileTree`, `excludedPaths`, `onToggleExclude`, `onLoadChildren`, and `onExpandExcludeTree`.

## Known Bug: Exclude Persistence

Exclude state is currently lost on backend restart. The exclude-tree UI writes patterns via `handleAddExcludePattern` → `p.handleAddExcludePattern(cleanPath)` + `p.handleAddExcludePattern("${cleanPath}/**")`, which updates `project_config.exclude_globs` through the API. However, these patterns don't survive a daemon restart — they're either not being persisted to the project config file on disk, or they're being overwritten by the config reload on startup.

**Must fix as part of this work.** The merged tree makes exclude a first-class citizen alongside include — if exclude doesn't persist, half the UI is broken after a restart. Investigation needed in:
- `src/codrag/api/routers/projects/` — the endpoint that handles `handleAddExcludePattern`
- `src/codrag/core/registry.py` — project config save/load
- `useTraceSystem.ts` / `useDashboardPanels.tsx` — how the frontend initializes `excludedPaths` on load (currently there's a `localExcludedPaths` optimistic state that may not be re-hydrated from backend)

## Migration Plan

### Step 1 — Update `FolderTree` component

- Remove `mode` prop.
- Accept both `includedPaths` + `excludedPaths` simultaneously.
- Replace row click handler: `variant='panel'` → no-op; `variant='detail'` → `onPreviewFile`.
- Remove Eye hover button (replaced by row click in detail mode).
- Add right-side include checkbox + exclude icon to every row.
- Implement mutual exclusion logic in icon click handlers.
- Add `alwaysIgnoredPatterns` prop; match paths and force `status='ignored'`.
- Update `WeightEditor` visibility: only when include is checked.
- Update folder partial-state logic to handle both include and exclude partial states.

### Step 2 — Update `FolderTreePanel`

- Accept exclude props (`excludedPaths`, `onToggleExclude`).
- Accept `alwaysIgnoredPatterns`.
- Update default title from "Knowledge Scope" to "Scope".
- Pass new props through to `FolderTree`.

### Step 3 — Update `FileExplorerDetail`

- Remove tab bar (Knowledge / Exclude tabs).
- Remove `FileExplorerTab` type and `initialTab` prop.
- Render single `FolderTree` with `variant='detail'`, both include + exclude props.
- Wire `onPreviewFile` to existing file content loading.

### Step 4 — Update `GraphStructurePanel`

- Remove "Exclude Tree" tab and all tree-related props.
- Simplify `activeTab` to `'queue' | 'patterns'`.
- Remove imports: `FolderTree`, `TreeNode`, `Maximize2`, `FolderTree as FolderTreeIcon` (keep only what Patterns tab needs).

### Step 5 — Update wiring in `useDashboardPanels.tsx`

- Move exclude props from `graph-structure` panel content to `file-tree` panel content.
- Add `alwaysIgnoredPatterns` constant (import from shared location or inline).
- Update detail-view panels to pass both sets of props.

### Step 6 — Update `panelRegistry.ts`

- Rename `file-tree` title to "Scope" and update description.
- Update `graph-structure` description to reflect Queue + Patterns only.

### Step 7 — Update exports and stories

- Update `packages/ui/src/components/index.ts` exports if needed.
- Update/add Storybook stories: `FolderTree.stories.tsx` should demonstrate all four row states (default, included, excluded, ignored) and folder partial states.
- Remove any stories that depend on the old `mode` prop.

## Future Work (Not in Scope)

### Profiles (agent/team scoping)

The merged tree manages the **main/master profile** — the canonical scope that applies to the project as a whole. Future work adds:

- **Main profile** = the current scope (include + exclude decisions, weights). This is what the merged tree manages.
- **Agent profiles** (existing `AgentScopePanel`) = per-role subsets of the main scope. An agent profile can only include files that are in the main scope or default (not excluded). The `AgentScopePanel` already handles this but will eventually need to respect exclude state.
- **Team profiles** = named scope configurations for human developers (e.g., "Frontend Dev" sees only `packages/ui` + `src/codrag/dashboard`). Similar to agent profiles but without the auto-populate feature.

The merged tree's data model (`includedPaths` + `excludedPaths` + `pathWeights`) is profile-ready: each profile would get its own copy of these three sets, with the main profile as the authoritative base.

### RAG override for excluded files

A future "force include" backdoor that lets users add a file to the knowledge base even if it's excluded from the trace graph. Use case: large generated files (e.g., API specs) that shouldn't be parsed structurally but should be searchable by content. This would require a fourth state beyond the current three (default/included/excluded) — likely implemented as a separate `forceIncludedPaths` set rather than complicating the mutual-exclusion model.

### Always-ignored list management

Currently `DEFAULT_EXCLUDE_FILE_GLOBS` is hardcoded in `repo_profile.py`. Future work:
- Expose this list via a project config API so the dashboard can fetch it dynamically.
- Allow users to add/remove entries (e.g., "I want CLAUDE.md in my trace graph").
- Show the list in a collapsible section in the Scope panel.

## Files Touched (Implementation Checklist)

| File | Change |
|------|--------|
| `packages/ui/src/components/project/FolderTree.tsx` | Major: remove `mode`, add dual-state, new row layout |
| `packages/ui/src/components/project/FolderTreePanel.tsx` | Moderate: accept exclude props, rename title |
| `packages/ui/src/components/project/FileExplorerDetail.tsx` | Moderate: remove tabs, single tree with `variant='detail'` |
| `packages/ui/src/components/trace/GraphStructurePanel.tsx` | Moderate: remove Exclude Tree tab + props |
| `packages/ui/src/config/panelRegistry.ts` | Minor: update titles/descriptions |
| `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx` | Moderate: rewire exclude props to file-tree panel |
| `packages/ui/src/components/project/index.ts` | Minor: export updates if needed |
| `packages/ui/src/stories/project/FolderTree.stories.tsx` | Moderate: update for new props/states |
| `packages/ui/src/stories/trace/GraphStructurePanel.stories.tsx` | Minor: remove exclude-tree story |
