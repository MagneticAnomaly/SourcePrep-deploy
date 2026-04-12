# Merged Scope Tree — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the Knowledge Sources tree and Graph Scope Exclude Tree into a single "Scope" panel where each file row has include (checkbox) and exclude (icon) affordances, with mutual exclusion enforced in the UI.

**Architecture:** The existing `FolderTree` component already supports both modes — we remove the `mode` prop and accept both `includedPaths` + `excludedPaths` simultaneously. Row click behavior changes: no-op in panel mode, file preview in detail mode. All selection happens via right-side icons. The `GraphStructurePanel` loses its Exclude Tree tab; `FolderTreePanel` gains exclude props and becomes "Scope."

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Lucide icons, Tremor UI, Storybook 7.6

**Spec:** `docs/Phase98_UI-UPDATE/Trees/MERGED-TREE-SPEC.md`

**Testing:** The UI package has no unit test runner (no vitest/jest). All component testing is via Storybook stories. Each task that modifies a component includes a Storybook story update/addition as the verification step.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `packages/ui/src/components/project/FolderTree.tsx` | Major modify | Remove `mode`, add dual-state row with include checkbox + exclude icon, new `variant` prop, `alwaysIgnoredPatterns`, mutual exclusion logic |
| `packages/ui/src/components/project/FolderTreePanel.tsx` | Moderate modify | Accept exclude props, rename default title to "Scope" |
| `packages/ui/src/components/project/FileExplorerDetail.tsx` | Moderate modify | Remove tab bar, single tree with `variant='detail'`, row click previews files |
| `packages/ui/src/components/trace/GraphStructurePanel.tsx` | Moderate modify | Remove Exclude Tree tab + all tree-related props |
| `packages/ui/src/config/panelRegistry.ts` | Minor modify | Update `file-tree` title/description, update `graph-structure` description |
| `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx` | Moderate modify | Move exclude props from graph-structure to file-tree panel content |
| `packages/ui/src/stories/project/FolderTree.stories.tsx` | Major modify | Add MergedScope story demonstrating all four row states |
| `packages/ui/src/stories/trace/GraphStructurePanel.stories.tsx` | Minor modify | Remove exclude-tree references |
| `packages/ui/src/components/project/index.ts` | Minor modify | Export updates if types changed |
| `packages/ui/src/components/index.ts` | Minor modify | Re-export updates |

---

### Task 1: Investigate and fix exclude persistence bug

The exclude tree's state (trace ignore patterns) is reportedly lost on backend restart. Before merging the trees, this must work reliably — otherwise the merged "Scope" panel's exclude side is broken on reload.

**Files:**
- Investigate: `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx:353-379`
- Investigate: `src/codrag/dashboard/src/hooks/useTraceSystem.ts:346-358`
- Investigate: `src/codrag/dashboard/src/hooks/useProjectManager.ts:168-182`
- Investigate: `src/codrag/api/routers/trace_routes/query.py:227-288`

**Context:** The backend endpoint (`/projects/{id}/trace/ignore`) does persist patterns to SQLite via `reg.update_project()`. The frontend re-hydrates from `p.projectConfig?.trace?.ignore_patterns` on load. The re-hydration effect (useDashboardPanels lines 359-379) skips patterns ending in `/**` and those with wildcards — it only keeps clean folder/file paths. The issue may be a race condition where `localExcludedPaths` is initialized empty and the hydration effect either doesn't fire or fires before config is available.

- [ ] **Step 1: Reproduce the bug**

Start the backend, add some excludes via the Exclude Tree tab, verify they appear in the UI. Restart the backend daemon (`codrag serve`), reload the dashboard, check if excludes are still visible.

Run:
```bash
# Check what's persisted in the DB after adding excludes:
.venv/bin/python -c "
from codrag.core.project_registry import ProjectRegistry
reg = ProjectRegistry()
for p in reg.list_projects():
    cfg = reg.get_project(p.id).config
    print(f'{p.name}: trace.ignore_patterns = {cfg.get(\"trace\", {}).get(\"ignore_patterns\", [])}')
"
```

Expected: The patterns should be in the DB. If they are, the bug is frontend re-hydration. If they aren't, the bug is backend persistence.

- [ ] **Step 2: Check the hydration dependency array**

In `useDashboardPanels.tsx` around line 359, the hydration `useEffect` depends on `[p.selectedProject?.id, persistedIgnorePatterns?.length]`. The `.length` dependency is suspicious — if the patterns array changes but has the same length, the effect won't re-fire. Also check if `persistedIgnorePatterns` is derived correctly from `projectTraceConfig`.

Read the exact code:
```typescript
// useDashboardPanels.tsx ~line 353-379
const projectTraceConfig = p.projectConfig?.trace
const persistedIgnorePatterns = (projectTraceConfig as any)?.ignore_patterns as string[] | undefined
```

The `as any` cast suggests `trace` might not have `ignore_patterns` in its TypeScript type definition. Check if `useProjectManager` actually puts `ignore_patterns` into `projectConfig.trace` when it loads from the API.

- [ ] **Step 3: Fix the re-hydration**

Based on investigation, apply the fix. Most likely one of:

**A. Dependency array fix** — if the issue is stale deps:
```typescript
// Change dependency from .length to a stable serialized value:
const ignorePatternKey = persistedIgnorePatterns?.join(',') ?? ''

useEffect(() => {
  if (!persistedIgnorePatterns || !Array.isArray(persistedIgnorePatterns) || persistedIgnorePatterns.length === 0) return
  setLocalExcludedPaths(() => {
    const paths = new Set<string>()
    for (const pattern of persistedIgnorePatterns) {
      if (pattern.endsWith('/**')) continue
      if (pattern.includes('*') || pattern.includes('?')) continue
      const clean = pattern.replace(/\/$/, '')
      if (clean) paths.add(clean)
    }
    return paths
  })
}, [p.selectedProject?.id, ignorePatternKey])
```

**B. Config loading fix** — if `trace.ignore_patterns` isn't being set in `projectConfig`:

In `useProjectManager.ts` (~line 172), verify the `trace` field is being spread correctly:
```typescript
setProjectConfig((prev) => ({
  ...prev,
  trace: cfg.trace ?? prev.trace,
}))
```

The `cfg.trace` must include `ignore_patterns`. Check the API response shape from `api.getProject()`.

- [ ] **Step 4: Verify the fix**

Restart backend + reload dashboard. Excludes should persist.

Run:
```bash
# Restart daemon
scripts/dev.sh --kill && scripts/dev.sh
```

Reload dashboard in browser. Previously-excluded paths should still show as excluded.

- [ ] **Step 5: Commit**

```bash
git add -p  # stage only the fix
git commit -m "fix(scope): persist trace exclude paths across backend restarts"
```

---

### Task 2: Add dual-state row to FolderTree — include checkbox + exclude icon

This is the core UI change. Replace the row click toggle with explicit right-side icons for include and exclude, enforce mutual exclusion.

**Files:**
- Modify: `packages/ui/src/components/project/FolderTree.tsx`

- [ ] **Step 1: Update FolderTreeProps interface**

Remove the `mode` prop. Add the new props for dual-state and variant.

```typescript
// In FolderTree.tsx, replace the existing FolderTreeProps:
export interface FolderTreeProps {
  data: TreeNode[];
  compact?: boolean;
  /** Knowledge scope: paths included in RAG index */
  includedPaths?: Set<string>;
  /** Called when user toggles knowledge inclusion */
  onToggleInclude?: (paths: string[], action: 'add' | 'remove') => void;
  /** Called when user clicks a node (for navigation/preview) */
  onNodeClick?: (node: TreeNode, path: string) => void;
  /** Per-path weight overrides (0.0–2.0, default 1.0). Folder weights propagate to children. */
  pathWeights?: Record<string, number>;
  /** Called when user changes weight. null removes the override (inherits parent weight). */
  onWeightChange?: (path: string, weight: number | null) => void;
  /** Trace exclusions: paths excluded from structural graph */
  excludedPaths?: Set<string>;
  /** Called when user toggles trace exclusion */
  onToggleExclude?: (paths: string[], action: 'add' | 'remove') => void;
  /** Display variant: 'panel' = no row click; 'detail' = row click previews file */
  variant?: 'panel' | 'detail';
  /** Always-ignored glob patterns (rendered as strikethrough, non-interactive) */
  alwaysIgnoredPatterns?: string[];
  /** Called when a depth-truncated folder is expanded — returns children to merge into the tree */
  onLoadChildren?: (path: string) => Promise<TreeNode[]>;
  className?: string;
}
```

- [ ] **Step 2: Update TreeItemProps to match**

Remove `mode` from `TreeItemProps`. Add the new props:

```typescript
interface TreeItemProps {
  node: TreeNode;
  depth?: number;
  path?: string;
  variant?: 'panel' | 'detail';
  // Include state
  includedPaths?: Set<string>;
  onToggleInclude?: (paths: string[], action: 'add' | 'remove') => void;
  onNodeClick?: (node: TreeNode, path: string) => void;
  pathWeights?: Record<string, number>;
  onWeightChange?: (path: string, weight: number | null) => void;
  // Exclude state
  excludedPaths?: Set<string>;
  onToggleExclude?: (paths: string[], action: 'add' | 'remove') => void;
  // Always-ignored
  alwaysIgnoredPatterns?: string[];
  // Expand state
  expandedPaths: Set<string>;
  onToggleExpand: (path: string) => void;
  onLoadChildren?: (path: string) => Promise<TreeNode[]>;
  loadingPaths: Set<string>;
  onSetLoading: (path: string, loading: boolean) => void;
  onMergeChildren: (path: string, children: TreeNode[]) => void;
}
```

- [ ] **Step 3: Add helper to check if a path matches always-ignored patterns**

```typescript
/** Check if a path matches any of the always-ignored glob patterns */
function isAlwaysIgnored(path: string, patterns: string[]): boolean {
  if (!patterns || patterns.length === 0) return false;
  const fileName = path.split('/').pop() ?? '';
  for (const pattern of patterns) {
    // Simple glob: **/FILENAME matches any path ending with that filename
    if (pattern.startsWith('**/')) {
      const suffix = pattern.slice(3);
      if (suffix.includes('/')) {
        // Pattern like **/.cursor/rules/*.mdc — check if path ends with the suffix structure
        if (path.endsWith(suffix.replace('*', '')) || path.includes(suffix.replace('*', ''))) return true;
      } else if (suffix.includes('*')) {
        // Pattern like *.mdc — match extension
        const ext = suffix.replace('*', '');
        if (fileName.endsWith(ext)) return true;
      } else {
        // Pattern like **/AGENTS.md — exact filename match
        if (fileName === suffix) return true;
      }
    }
  }
  return false;
}

/** Check if a path or any ancestor is in the excluded set */
function isPathOrAncestorExcluded(path: string, excludedPaths: Set<string>): boolean {
  if (excludedPaths.has(path)) return true;
  const parts = path.split('/');
  for (let i = 1; i < parts.length; i++) {
    if (excludedPaths.has(parts.slice(0, i).join('/'))) return true;
  }
  return false;
}

/** Check exclude selection state of a folder's children */
function getFolderExcludeState(
  node: TreeNode,
  basePath: string,
  excludedPaths: Set<string>
): 'none' | 'partial' | 'all' {
  if (!node.children || node.children.length === 0) return 'none';
  const currentPath = basePath ? `${basePath}/${node.name}` : node.name;
  let excludedCount = 0;
  for (const child of node.children) {
    const childPath = `${currentPath}/${child.name}`;
    if (isPathOrAncestorExcluded(childPath, excludedPaths)) {
      excludedCount++;
    } else if (child.type === 'folder') {
      const childState = getFolderExcludeState(child, currentPath, excludedPaths);
      if (childState === 'all') excludedCount++;
      else if (childState === 'partial') return 'partial';
    }
  }
  if (excludedCount === 0) return 'none';
  if (excludedCount === node.children.length) return 'all';
  return 'partial';
}
```

- [ ] **Step 4: Rewrite the TreeItem row click handler**

Replace the existing `handleRowClick` with variant-aware behavior:

```typescript
const handleRowClick = () => {
  if (isAlwaysIgnoredNode || node.status === 'ignored') return;

  if (isFolder) {
    // Folders: always expand/collapse on row click
    handleExpandToggle(new MouseEvent('click') as unknown as React.MouseEvent);
    return;
  }

  // Files: variant determines behavior
  if (variant === 'detail' && onNodeClick) {
    onNodeClick(node, currentPath);
  }
  // panel variant: no-op on row click
};
```

- [ ] **Step 5: Add the include checkbox and exclude icon to the row**

Replace the existing right-side section (currently gated by `!isExcludeMode`) with a new layout that always shows both controls:

```typescript
import { Check, Square, Ban, CheckSquare, MinusSquare } from 'lucide-react';

// Inside TreeItem, after the name span, replace the right-side block:

{/* Right side: chunks, status, weight, include checkbox, exclude icon */}
<span className="ml-auto flex items-center gap-1.5 shrink-0">
  {/* Chunk count — only when included and indexed */}
  {isIncluded && node.chunks !== undefined && effectiveStatus === 'indexed' && (
    <span className="text-xs text-text-subtle">
      {node.chunks} chunks
    </span>
  )}

  {/* Status badge — only when included with pending/indexed status */}
  {isIncluded && showStatus && effectiveStatus && (
    <span
      className={cn(
        "flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full",
        `${statusColors[effectiveStatus]}/20`
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full", statusColors[effectiveStatus])} />
      <span className="text-text-subtle hidden sm:inline">{statusLabels[effectiveStatus]}</span>
    </span>
  )}

  {/* Weight editor — only when included */}
  {isIncluded && (showFolderWeight || ((effectiveStatus === 'indexed' || effectiveStatus === 'pending') && isIncluded)) && (
    <WeightEditor
      effectiveWeight={effectiveWeight}
      isInherited={isWeightInherited}
      inheritedFrom={weightSource}
      onWeightChange={onWeightChange}
      currentPath={currentPath}
      isFolder={isFolder}
      childOverridePaths={childOverridePaths}
    />
  )}

  {/* Include checkbox — hidden for always-ignored files */}
  {!isAlwaysIgnoredNode && onToggleInclude && (
    <button
      onClick={handleIncludeClick}
      className={cn(
        'p-0.5 rounded transition-colors',
        isIncluded
          ? 'text-primary hover:text-primary/80'
          : isFolderPartiallyIncluded
            ? 'text-primary/60 hover:text-primary'
            : 'text-text-subtle/40 hover:text-text-subtle'
      )}
      title={isIncluded ? 'Remove from knowledge scope' : 'Add to knowledge scope'}
    >
      {isIncluded
        ? <CheckSquare className="w-4 h-4" />
        : isFolderPartiallyIncluded
          ? <MinusSquare className="w-4 h-4" />
          : <Square className="w-4 h-4" />
      }
    </button>
  )}

  {/* Exclude icon — hidden for always-ignored files */}
  {!isAlwaysIgnoredNode && onToggleExclude && (
    <button
      onClick={handleExcludeClick}
      className={cn(
        'p-0.5 rounded transition-colors',
        isExcluded
          ? 'text-error hover:text-error/80'
          : isFolderPartiallyExcluded
            ? 'text-error/60 hover:text-error'
            : 'text-text-subtle/40 hover:text-text-subtle'
      )}
      title={isExcluded ? 'Remove trace exclusion' : 'Exclude from trace'}
    >
      <Ban className={cn('w-4 h-4', isExcluded && 'fill-error/10')} />
    </button>
  )}
</span>
```

- [ ] **Step 6: Add the mutual-exclusion click handlers**

```typescript
const handleIncludeClick = (e: React.MouseEvent) => {
  e.stopPropagation();
  if (!onToggleInclude || isAlwaysIgnoredNode || node.status === 'ignored') return;

  const effectivelyIncluded = isIncluded || (isFolder && (folderSelectionState === 'all'));

  if (effectivelyIncluded) {
    // Un-include
    onToggleInclude([currentPath], 'remove');
  } else {
    // Include — first un-exclude if needed
    if (excludedPaths && isPathOrAncestorExcluded(currentPath, excludedPaths)) {
      onToggleExclude?.([currentPath], 'remove');
    }
    onToggleInclude([currentPath], 'add');
  }
};

const handleExcludeClick = (e: React.MouseEvent) => {
  e.stopPropagation();
  if (!onToggleExclude || isAlwaysIgnoredNode || node.status === 'ignored') return;

  const effectivelyExcluded = isExcluded || (isFolder && (folderExcludeState === 'all'));

  if (effectivelyExcluded) {
    // Un-exclude
    onToggleExclude([currentPath], 'remove');
  } else {
    // Exclude — first un-include if needed
    if (includedPaths && isPathOrAncestorIncluded(currentPath, includedPaths)) {
      onToggleInclude?.([currentPath], 'remove');
    }
    onToggleExclude([currentPath], 'add');
  }
};
```

- [ ] **Step 7: Compute exclude state in TreeItem body**

Add these derivations alongside the existing include state:

```typescript
// Exclude state
const isExcluded = excludedPaths ? isPathOrAncestorExcluded(currentPath, excludedPaths) : false;
const folderExcludeState = isFolder && excludedPaths
  ? getFolderExcludeState(node, path, excludedPaths)
  : 'none';
const isFolderPartiallyExcluded = isFolder && folderExcludeState === 'partial';
const isFolderFullyExcluded = isFolder && (isExcluded || folderExcludeState === 'all');

// Always-ignored
const isAlwaysIgnoredNode = isAlwaysIgnored(currentPath, alwaysIgnoredPatterns ?? []);

// Rename for clarity
const isFolderPartiallyIncluded = isPartiallySelected;
```

- [ ] **Step 8: Update row styling for the new states**

Update the row `className` to handle exclude + always-ignored visual states:

```typescript
className={cn(
  'group flex items-center gap-1 rounded-md px-2 py-1 my-px transition-colors',
  depth > 0 && 'ml-4',
  // Always-ignored: strikethrough, no hover
  isAlwaysIgnoredNode && 'cursor-default',
  // Selectable items: hover state
  !isAlwaysIgnoredNode && !isIgnored && 'hover:bg-surface-raised',
  // Cursor: pointer for detail variant files, default otherwise
  !isAlwaysIgnoredNode && !isIgnored && variant === 'detail' && !isFolder && 'cursor-pointer',
  !isAlwaysIgnoredNode && !isIgnored && (variant === 'panel' || isFolder) && 'cursor-default',
  // Ignored items are dimmed
  isIgnored && !isAlwaysIgnoredNode && 'opacity-50 cursor-default',
  // Included items
  isIncluded && !isIgnored && !isExcluded && 'bg-primary/5',
  // Excluded items
  isExcluded && !isIgnored && 'bg-error/8',
  // Weight-based opacity (only for included items)
  isIncluded && effectiveWeight < 1 && effectiveWeight > 0 && 'opacity-75',
  isIncluded && effectiveWeight === 0 && 'opacity-40'
)}
```

Update the name span styling:

```typescript
<span className={cn(
  "text-sm ml-1 truncate transition-all font-mono",
  isAlwaysIgnoredNode
    ? "text-text-subtle line-through decoration-text-subtle/60"
    : isIgnored
      ? "text-text-subtle"
      : isExcluded
        ? "text-error line-through decoration-error/60"
        : (isIncluded || isFolderPartiallyIncluded)
          ? "text-text font-semibold"
          : isFolder
            ? "text-text font-medium"
            : "text-text-muted"
)}>
  {node.name}
</span>
```

- [ ] **Step 9: Update icon coloring for exclude state**

```typescript
<span
  className={cn(
    'flex items-center justify-center w-5 h-5 transition-colors shrink-0',
    isAlwaysIgnoredNode
      ? 'text-text-subtle/50'
      : isIgnored
        ? 'text-text-subtle/50'
        : isExcluded
          ? 'text-error'
          : (isIncluded || isFolderPartiallyIncluded)
            ? 'text-primary'
            : 'text-text-subtle'
  )}
>
```

- [ ] **Step 10: Remove the Eye hover button**

Delete the existing Eye button block (currently around line 466-476). In detail mode, the row click handles preview. In panel mode, no preview action exists.

- [ ] **Step 11: Update the FolderTree root component**

Remove the `mode` prop from the `FolderTree` function signature. Remove the `storageKey` logic that varied by mode (both share the same expanded state now). Pass new props through to `TreeItem`:

```typescript
export function FolderTree({
  data,
  compact,
  includedPaths,
  onToggleInclude,
  onNodeClick,
  pathWeights,
  onWeightChange,
  excludedPaths,
  onToggleExclude,
  variant = 'panel',
  alwaysIgnoredPatterns,
  onLoadChildren,
  className,
}: FolderTreeProps) {
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(() => {
    if (typeof window === 'undefined') return new Set();
    try {
      const stored = localStorage.getItem(EXPANDED_STORAGE_KEY);
      return stored ? new Set(JSON.parse(stored)) : new Set();
    } catch { return new Set(); }
  });
  // ... rest unchanged, just pass new props to TreeItem
```

- [ ] **Step 12: Verify with typecheck**

Run:
```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG && npm run typecheck
```

Expected: No type errors in FolderTree.tsx. There WILL be errors in files that consume the old `mode` prop — that's expected and fixed in subsequent tasks.

- [ ] **Step 13: Commit**

```bash
git add packages/ui/src/components/project/FolderTree.tsx
git commit -m "feat(scope): unified FolderTree with include checkbox + exclude icon"
```

---

### Task 3: Update FolderTreePanel to accept exclude props

**Files:**
- Modify: `packages/ui/src/components/project/FolderTreePanel.tsx`

- [ ] **Step 1: Update FolderTreePanelProps**

```typescript
export interface FolderTreePanelProps {
  data: TreeNode[];
  /** Paths included in the RAG index */
  includedPaths?: Set<string>;
  /** Scope orchestrator status (Phase 24) */
  scopeStatus?: ScopeStatus;
  /** Called when user toggles inclusion of paths */
  onToggleInclude?: (paths: string[], action: 'add' | 'remove') => void;
  /** Called when user clicks a node (for navigation/preview in detail view) */
  onNodeClick?: (node: TreeNode, path: string) => void;
  /** Per-path weight overrides (0.0–2.0) */
  pathWeights?: Record<string, number>;
  /** Called when user changes weight */
  onWeightChange?: (path: string, weight: number | null) => void;
  /** Paths excluded from trace graph */
  excludedPaths?: Set<string>;
  /** Called when user toggles trace exclusion */
  onToggleExclude?: (paths: string[], action: 'add' | 'remove') => void;
  /** Always-ignored glob patterns */
  alwaysIgnoredPatterns?: string[];
  /** Called when a depth-truncated folder is expanded */
  onLoadChildren?: (path: string) => Promise<TreeNode[]>;
  title?: string;
  className?: string;
  bare?: boolean;
}
```

- [ ] **Step 2: Pass new props to FolderTree and update defaults**

```typescript
export function FolderTreePanel({
  data,
  includedPaths,
  scopeStatus,
  onToggleInclude,
  onNodeClick,
  pathWeights,
  onWeightChange,
  excludedPaths,
  onToggleExclude,
  alwaysIgnoredPatterns,
  onLoadChildren,
  title = 'Scope',
  className,
  bare = false,
}: FolderTreePanelProps) {
  // ... Container, includedCount, statusBadge unchanged ...

  // Add exclude count
  const excludedCount = excludedPaths?.size ?? 0;

  return (
    <Container className={cn(!bare && 'border border-border bg-surface shadow-sm', 'h-full min-h-0 flex flex-col', className)}>
      {!bare && (
        <Flex justifyContent="between" alignItems="center" className="mb-4 gap-2">
          <div className="flex items-center gap-2">
            <Title className="text-text">{title}</Title>
            {statusBadge}
          </div>
          <div className="flex items-center gap-2">
            {excludedCount > 0 && (
              <Badge color="red" size="xs">{excludedCount} excluded</Badge>
            )}
            {includedCount > 0 && (
              <Badge color="neutral" size="xs">{includedCount} included</Badge>
            )}
          </div>
        </Flex>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto -mx-2 custom-scrollbar">
        <div className="px-2">
          <FolderTree
            data={data}
            compact
            includedPaths={includedPaths}
            onToggleInclude={onToggleInclude}
            onNodeClick={onNodeClick}
            pathWeights={pathWeights}
            onWeightChange={onWeightChange}
            excludedPaths={excludedPaths}
            onToggleExclude={onToggleExclude}
            alwaysIgnoredPatterns={alwaysIgnoredPatterns}
            onLoadChildren={onLoadChildren}
          />
        </div>
      </div>
    </Container>
  );
}
```

- [ ] **Step 3: Verify with typecheck**

Run:
```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG && npm run typecheck
```

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/project/FolderTreePanel.tsx
git commit -m "feat(scope): FolderTreePanel accepts exclude props, rename to Scope"
```

---

### Task 4: Update FileExplorerDetail — remove tabs, single unified tree

**Files:**
- Modify: `packages/ui/src/components/project/FileExplorerDetail.tsx`

- [ ] **Step 1: Remove tab state and tab bar**

Remove the `FileExplorerTab` type export, `activeTab` state, `initialTab` prop, and the tab bar JSX. The component now renders a single `FolderTree` with `variant='detail'`.

Updated interface:

```typescript
export interface FileExplorerDetailProps {
  treeData: TreeNode[];
  pinnedPaths: Set<string>;
  onPinFile: (path: string) => void;
  onUnpinFile: (path: string) => void;
  onLoadFileContent?: (path: string) => Promise<string>;
  // Include
  includedPaths?: Set<string>;
  scopeStatus?: ScopeStatus;
  onToggleInclude?: (paths: string[], action: 'add' | 'remove') => void;
  pathWeights?: Record<string, number>;
  onWeightChange?: (path: string, weight: number | null) => void;
  // Exclude
  excludedPaths?: Set<string>;
  onToggleExclude?: (paths: string[], action: 'add' | 'remove') => void;
  // Common
  onLoadChildren?: (path: string) => Promise<TreeNode[]>;
  alwaysIgnoredPatterns?: string[];
  initialTreeWidth?: number;
  className?: string;
}
```

- [ ] **Step 2: Replace tab-conditional rendering with single tree**

Replace both the desktop and mobile tree renders with one `FolderTree` using `variant='detail'`:

```typescript
{/* Desktop tree */}
<div className="hidden md:block h-full overflow-y-auto custom-scrollbar" style={{ width: treeWidth }}>
  <div className="p-4">
    <h3 className="text-sm font-semibold text-text mb-3 flex items-center gap-2">
      <FolderTreeIcon className="w-4 h-4" />
      Scope
      {statusBadge}
    </h3>
    <FolderTree
      data={treeData}
      compact
      variant="detail"
      includedPaths={includedPaths}
      onToggleInclude={onToggleInclude}
      onNodeClick={handleNodeClick}
      pathWeights={pathWeights}
      onWeightChange={onWeightChange}
      excludedPaths={excludedPaths}
      onToggleExclude={onToggleExclude}
      alwaysIgnoredPatterns={alwaysIgnoredPatterns}
      onLoadChildren={onLoadChildren}
    />
  </div>
</div>
```

Same for the mobile section, minus the resize logic.

- [ ] **Step 3: Remove unused imports**

Remove `EyeOff` import (no longer needed for the tab icon).
Remove the `FileExplorerTab` type — it's no longer exported.

- [ ] **Step 4: Verify with typecheck**

Run:
```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG && npm run typecheck
```

Callers that pass `initialTab` will now error — fix them in Task 6 (wiring).

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/project/FileExplorerDetail.tsx
git commit -m "feat(scope): FileExplorerDetail uses single unified tree, remove tabs"
```

---

### Task 5: Remove Exclude Tree tab from GraphStructurePanel

**Files:**
- Modify: `packages/ui/src/components/trace/GraphStructurePanel.tsx`

- [ ] **Step 1: Remove exclude-tree-related props from interface**

Remove from `GraphStructurePanelProps`:
- `fileTree?: TreeNode[]`
- `excludedPaths?: Set<string>`
- `onToggleExclude?: (paths: string[], action: 'add' | 'remove') => void`
- `onLoadChildren?: (path: string) => Promise<TreeNode[]>`
- `onExpandExcludeTree?: () => void`

- [ ] **Step 2: Remove the Exclude Tree tab button**

Remove the third tab button (the one for `'exclude-tree'`). Change the tab type:

```typescript
const [activeTab, setActiveTab] = useState<'queue' | 'patterns'>('queue');
```

- [ ] **Step 3: Remove the Exclude Tree tab content**

Delete the `{activeTab === 'exclude-tree' && ( ... )}` block (lines ~679-714).

- [ ] **Step 4: Remove unused imports**

Remove: `FolderTree`, `TreeNode` type import, `Maximize2`, `FolderTree as FolderTreeIcon`. Keep all other imports.

- [ ] **Step 5: Remove the destructured props from the function signature**

Remove `fileTree`, `excludedPaths`, `onToggleExclude`, `onLoadChildren`, `onExpandExcludeTree` from the destructuring.

- [ ] **Step 6: Verify with typecheck**

Run:
```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG && npm run typecheck
```

Callers that pass the removed props will error — fixed in Task 6.

- [ ] **Step 7: Commit**

```bash
git add packages/ui/src/components/trace/GraphStructurePanel.tsx
git commit -m "feat(scope): remove Exclude Tree tab from GraphStructurePanel"
```

---

### Task 6: Rewire dashboard panel content

This is where the state is moved from one panel to the other.

**Files:**
- Modify: `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx`

- [ ] **Step 1: Add always-ignored patterns constant**

At the top of the file (or in a shared constants file):

```typescript
const DEFAULT_ALWAYS_IGNORED_PATTERNS = [
  '**/AGENTS.md',
  '**/CLAUDE.md',
  '**/GEMINI.md',
  '**/.cursorrules',
  '**/.cursorignore',
  '**/.windsurfrules',
  '**/.clinerules',
  '**/.roorules',
  '**/.clineignore',
  '**/.qwencoderules',
  '**/.cursor/rules/*.mdc',
  '**/.windsurf/rules/*.md',
  '**/.github/copilot-instructions.md',
];
```

- [ ] **Step 2: Update the `file-tree` panel content**

Find the `'file-tree'` entry (~line 687-698) and add exclude props + alwaysIgnoredPatterns:

```typescript
'file-tree': (
  <FolderTreePanel
    data={p.fileTree}
    includedPaths={p.includedPaths}
    scopeStatus={p.scopeStatus}
    onToggleInclude={p.handleToggleInclude}
    pathWeights={p.pathWeights}
    onWeightChange={p.handlePathWeightChange}
    excludedPaths={excludedPaths}
    onToggleExclude={handleToggleExclude}
    alwaysIgnoredPatterns={DEFAULT_ALWAYS_IGNORED_PATTERNS}
    onLoadChildren={p.handleLoadChildren}
    title="Scope"
    bare
  />
),
```

- [ ] **Step 3: Remove exclude props from `graph-structure` panel content**

Find the `'graph-structure'` entry (~line 869-893) and remove the tree-related props:

```typescript
'graph-structure': (
  <GraphStructurePanel
    summary={p.traceCoverage.summary}
    epistemic={p.epistemicStatus}
    augmentation={p.augmentationStatus}
    moduleStatus={p.moduleStatus}
    knowledgeStatus={p.knowledgeStatus}
    untracedFiles={p.traceCoverage.untraced}
    staleFiles={p.traceCoverage.stale}
    tracedFiles={p.traceCoverage.traced}
    excludedFiles={p.traceCoverage.excluded}
    building={p.traceStatus.building || p.traceCoverage.building || p.inferredEdgesRunning || p.augmenting || p.validating || p.fastKnowledgeBuilding}
    progress={p.findActiveTask('trace_build')}
    loading={p.traceCoverage.loading}
    onTraceAll={p.handleTraceAll}
    onRetraceStale={p.handleRetraceStale}
    onAddExcludePattern={p.handleAddExcludePattern}
    onRemoveExcludePattern={p.handleRemoveExcludePattern}
    onRefresh={p.fetchTraceCoverage}
    traceExists={p.traceStatus.exists}
  />
),
```

Note: `fileTree`, `excludedPaths`, `onToggleExclude`, `onLoadChildren`, `onExpandExcludeTree` are all removed.

- [ ] **Step 4: Update detail-view panel wiring**

Search for other places where `FileExplorerDetail` is rendered (around lines 1250-1280) and update to pass exclude props + remove `initialTab`:

```typescript
<FileExplorerDetail
  treeData={p.fileTree}
  pinnedPaths={p.pinnedPaths}
  onPinFile={p.handlePinFile}
  onUnpinFile={p.handleUnpinFile}
  onLoadFileContent={p.handleLoadFileContent}
  includedPaths={p.includedPaths}
  scopeStatus={p.scopeStatus}
  onToggleInclude={p.handleToggleInclude}
  pathWeights={p.pathWeights}
  onWeightChange={p.handlePathWeightChange}
  excludedPaths={excludedPaths}
  onToggleExclude={handleToggleExclude}
  alwaysIgnoredPatterns={DEFAULT_ALWAYS_IGNORED_PATTERNS}
  onLoadChildren={p.handleLoadChildren}
/>
```

Remove any `initialTab` or `initialTab="exclude"` props.

- [ ] **Step 5: Update useMemo dependency arrays**

The `useMemo` blocks that wrap panel content need `excludedPaths` and `handleToggleExclude` in the `file-tree` dependency array (they may already be there for `graph-structure` — move them). Remove them from the `graph-structure` memo deps.

- [ ] **Step 6: Verify with typecheck**

Run:
```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG && npm run typecheck
```

Expected: Clean build. All consumers now pass the correct props.

- [ ] **Step 7: Commit**

```bash
git add src/codrag/dashboard/src/hooks/useDashboardPanels.tsx
git commit -m "feat(scope): rewire exclude state from graph-structure to file-tree panel"
```

---

### Task 7: Update panelRegistry

**Files:**
- Modify: `packages/ui/src/config/panelRegistry.ts`

- [ ] **Step 1: Update file-tree entry**

```typescript
{
  id: 'file-tree',
  title: 'Scope',
  description: 'Manage which files CoDRAG indexes. Include files with weights for RAG priority, or exclude files from the trace graph entirely.',
  icon: FolderTree,
  minHeight: 6,
  defaultHeight: 10,
  category: 'search',
  closeable: true,
  resizable: true,
  docsUrl: 'https://docs.codrag.io/dashboard#scope',
},
```

- [ ] **Step 2: Update graph-structure entry**

```typescript
{
  id: 'graph-structure',
  title: 'Graph Scope',
  description: 'Pipeline file inventory: Queue of untraced/stale files, and glob-based exclude patterns.',
  icon: Database,
  minHeight: 6,
  defaultHeight: 10,
  category: 'status',
  closeable: true,
  resizable: true,
  docsUrl: 'https://docs.codrag.io/concepts/graph-scope',
},
```

- [ ] **Step 3: Commit**

```bash
git add packages/ui/src/config/panelRegistry.ts
git commit -m "feat(scope): update panel titles and descriptions"
```

---

### Task 8: Update exports

**Files:**
- Modify: `packages/ui/src/components/project/index.ts`
- Modify: `packages/ui/src/components/index.ts`

- [ ] **Step 1: Check and update project/index.ts**

If `FileExplorerTab` was exported, remove it. Ensure `FolderTree`, `FolderTreePanel`, `FileExplorerDetail`, and their prop types are still exported.

Read the current file and remove any reference to `FileExplorerTab`:

```bash
grep -n 'FileExplorerTab' packages/ui/src/components/project/index.ts
```

If found, remove that export line.

- [ ] **Step 2: Check and update components/index.ts**

Same — remove `FileExplorerTab` if re-exported:

```bash
grep -n 'FileExplorerTab' packages/ui/src/components/index.ts packages/ui/src/index.ts
```

- [ ] **Step 3: Verify with full build**

Run:
```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG && npm run typecheck && npm run build
```

Expected: Clean build across all workspaces.

- [ ] **Step 4: Commit**

```bash
git add packages/ui/src/components/project/index.ts packages/ui/src/components/index.ts packages/ui/src/index.ts
git commit -m "chore(scope): clean up exports after tree merge"
```

---

### Task 9: Update Storybook stories

**Files:**
- Modify: `packages/ui/src/stories/project/FolderTree.stories.tsx`
- Modify: `packages/ui/src/stories/trace/GraphStructurePanel.stories.tsx`

- [ ] **Step 1: Add MergedScope story to FolderTree.stories.tsx**

This story demonstrates all four row states (default, included, excluded, always-ignored) in the unified tree:

```typescript
export const MergedScope: Story = {
  render: () => {
    const [includedPaths, setIncludedPaths] = useState<Set<string>>(new Set([
      'src/codrag',
      'src/codrag/server.py',
      'src/codrag/cli.py',
      'src/codrag/core',
      'src/codrag/core/registry.py',
      'src/codrag/core/trace.py',
      'src/codrag/api',
      'src/codrag/api/routes.py',
      'src/codrag/api/auth.py',
      'docs',
      'docs/ARCHITECTURE.md',
      'docs/API.md',
    ]));

    const [excludedPaths, setExcludedPaths] = useState<Set<string>>(new Set([
      'tests',
    ]));

    const [pathWeights, setPathWeights] = useState<Record<string, number>>({
      'docs': 0.5,
      'src/codrag/core': 1.5,
    });

    const handleToggleInclude = (paths: string[], action: 'add' | 'remove') => {
      setIncludedPaths((prev) => {
        const next = new Set(prev);
        for (const p of paths) {
          if (action === 'remove') next.delete(p);
          else next.add(p);
        }
        return next;
      });
    };

    const handleToggleExclude = (paths: string[], action: 'add' | 'remove') => {
      setExcludedPaths((prev) => {
        const next = new Set(prev);
        for (const p of paths) {
          if (action === 'remove') next.delete(p);
          else next.add(p);
        }
        return next;
      });
    };

    const handleWeightChange = (path: string, weight: number | null) => {
      setPathWeights((prev) => {
        const next = { ...prev };
        if (weight === null) delete next[path];
        else next[path] = weight;
        return next;
      });
    };

    // Sample tree with an AGENTS.md to show always-ignored state
    const treeWithAgentsMd: TreeNode[] = [
      ...sampleFileTree,
      { name: 'AGENTS.md', type: 'file' },
      { name: 'CLAUDE.md', type: 'file' },
    ];

    return (
      <div className="space-y-4">
        <div className="p-3 bg-surface-raised rounded-lg border border-border">
          <div className="text-xs text-text-subtle mb-1">Merged Scope Tree — Four States</div>
          <div className="text-sm text-text-muted space-y-1">
            <div>• <strong>Default</strong>: traced but not in knowledge base (checkbox unchecked)</div>
            <div>• <span className="text-primary font-semibold">Included</span>: in knowledge base with weight (checkbox checked)</div>
            <div>• <span className="text-error line-through">Excluded</span>: invisible to CoDRAG (ban icon active)</div>
            <div>• <span className="text-text-subtle line-through">Always-ignored</span>: AGENTS.md, CLAUDE.md etc. (non-interactive)</div>
            <div className="mt-2 text-xs">Include and exclude are mutually exclusive — checking one unchecks the other.</div>
          </div>
        </div>
        <div className="text-xs text-text-subtle flex gap-4">
          <span>Included: {includedPaths.size}</span>
          <span>Excluded: {excludedPaths.size}</span>
          <span>Weight overrides: {Object.keys(pathWeights).length}</span>
        </div>
        <FolderTree
          data={treeWithAgentsMd}
          includedPaths={includedPaths}
          onToggleInclude={handleToggleInclude}
          excludedPaths={excludedPaths}
          onToggleExclude={handleToggleExclude}
          pathWeights={pathWeights}
          onWeightChange={handleWeightChange}
          alwaysIgnoredPatterns={['**/AGENTS.md', '**/CLAUDE.md']}
        />
      </div>
    );
  },
  parameters: {
    docs: {
      description: {
        story: `
**Merged Scope Tree** unifies Knowledge Sources and Graph Scope Exclude into a single interface.

Each row has two right-side controls:
- **Include checkbox** (☐/☑): Adds file to knowledge base with optional weight
- **Exclude icon** (⊘): Removes file from trace graph entirely

These are mutually exclusive. Clicking include on an excluded file un-excludes it first.

**Always-ignored** files (AGENTS.md, CLAUDE.md, etc.) appear with strikethrough and no controls — they're always available to AI agents and never indexed.
        `,
      },
    },
  },
};
```

- [ ] **Step 2: Update existing stories that use the old `mode` prop**

If any existing story passes `mode="exclude"`, remove that prop and add `excludedPaths` instead. Most stories should work without changes since `mode` defaulted to `'include'`.

- [ ] **Step 3: Update GraphStructurePanel.stories.tsx**

Remove any `fileTree`, `excludedPaths`, `onToggleExclude` props from the story args:

```typescript
export const WithData: Story = {
  args: {
    summary: mockSummary,
    epistemic: mockEpistemic,
    augmentation: mockAugmentation,
    moduleStatus: mockModuleStatus,
    knowledgeStatus: mockKnowledge,
    untracedFiles,
    staleFiles,
    excludedFiles,
    building: false,
    loading: false,
    traceExists: true,
    onTraceAll: noop,
    onRetraceStale: noop,
    onAddExcludePattern: noop,
    onRemoveExcludePattern: noop,
    onRefresh: noop,
    // fileTree, excludedPaths, onToggleExclude — REMOVED
  },
};
```

Apply the same removal to `Building` and `AllTraced` stories.

- [ ] **Step 4: Verify Storybook builds**

Run:
```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui && npm run build-storybook
```

Expected: Clean build, no errors.

- [ ] **Step 5: Visual verification in Storybook**

Run:
```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG/packages/ui && npm run storybook
```

Open `http://localhost:6006` and verify:
1. MergedScope story renders with all four states visible
2. Clicking include checkbox toggles include state
3. Clicking exclude icon toggles exclude state
4. Mutual exclusion works (including an excluded item un-excludes it)
5. AGENTS.md/CLAUDE.md show as strikethrough, non-interactive
6. Weight editor appears only on included items
7. Existing stories (Default, RagInclusion, ContextWeighting) still work

- [ ] **Step 6: Commit**

```bash
git add packages/ui/src/stories/project/FolderTree.stories.tsx packages/ui/src/stories/trace/GraphStructurePanel.stories.tsx
git commit -m "feat(scope): update Storybook stories for merged scope tree"
```

---

### Task 10: End-to-end dashboard verification

**Files:** None modified — verification only.

- [ ] **Step 1: Start full dev environment**

Run:
```bash
cd /Volumes/4TB-BAD/HumanAI/CoDRAG && scripts/dev.sh
```

Wait for daemon (:8400), dashboard (:5174), and storybook (:6006) to start.

- [ ] **Step 2: Verify Scope panel (formerly Knowledge Sources)**

Open dashboard at `http://localhost:5174`. The panel formerly titled "Knowledge Sources" should now be titled "Scope." Verify:

1. Tree shows file structure with include checkboxes and exclude icons on each row
2. Clicking include checkbox adds file to knowledge scope (check turns primary blue)
3. Clicking exclude icon excludes file (row turns red with strikethrough)
4. Mutual exclusion: including an excluded file un-excludes it first, and vice versa
5. Weight badge appears only on included files/folders
6. AGENTS.md / CLAUDE.md show strikethrough, controls are hidden
7. Folder click expands/collapses only (no selection change)
8. File row click does nothing (panel mode)

- [ ] **Step 3: Verify Graph Scope panel**

Open the Graph Scope panel. Verify:

1. Only two tabs remain: Queue and Patterns
2. No "Exclude Tree" tab
3. Queue and Patterns tabs work as before
4. Adding a pattern in Patterns tab still works

- [ ] **Step 4: Verify detail view**

Expand the Scope panel to full-screen detail view. Verify:

1. No tab bar (no Knowledge/Exclude toggle)
2. Single tree with both include and exclude controls
3. Clicking a file row opens the file preview pane (replaces old Eye button)
4. File preview pane shows content correctly
5. Include/exclude/weight controls work in detail view

- [ ] **Step 5: Verify exclude persistence**

1. Exclude a file/folder via the ban icon
2. Restart the backend: `scripts/dev.sh --kill && scripts/dev.sh`
3. Reload the dashboard
4. Previously excluded items should still show as excluded

- [ ] **Step 6: Final commit if any hot-fixes were needed**

```bash
git add -p
git commit -m "fix(scope): polish merged tree after E2E testing"
```
