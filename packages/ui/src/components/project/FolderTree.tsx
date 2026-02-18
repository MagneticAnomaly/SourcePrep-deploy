import { useState, useCallback } from 'react';
import { ChevronRight, ChevronDown, Folder, FolderOpen, File, FileText, Loader2, Eye } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';

export type FileStatus = 'indexed' | 'pending' | 'pending_removal' | 'ignored' | 'error';

export interface TreeNode {
  name: string;
  type: 'file' | 'folder';
  status?: FileStatus;
  children?: TreeNode[];
  chunks?: number;
  selected?: boolean;
  has_children?: boolean;
}

const statusColors: Record<FileStatus, string> = {
  indexed: 'bg-success',
  pending: 'bg-warning',
  pending_removal: 'bg-error/70',
  ignored: 'bg-text-subtle/30',
  error: 'bg-error',
};

const statusLabels: Record<FileStatus, string> = {
  indexed: 'Indexed',
  pending: 'Pending',
  pending_removal: 'Removing',
  ignored: 'Ignored',
  error: 'Error',
};

/** Check if a path or any of its ancestor folders is in the included set */
function isPathOrAncestorIncluded(path: string, includedPaths: Set<string>): boolean {
  if (includedPaths.has(path)) return true;
  const parts = path.split('/');
  for (let i = 1; i < parts.length; i++) {
    if (includedPaths.has(parts.slice(0, i).join('/'))) return true;
  }
  return false;
}

/** Check selection state of a folder's children */
function getFolderSelectionState(
  node: TreeNode, 
  basePath: string, 
  includedPaths: Set<string>
): 'none' | 'partial' | 'all' {
  if (!node.children || node.children.length === 0) return 'none';
  
  const selectableChildren = node.children.filter(c => c.status !== 'ignored');
  if (selectableChildren.length === 0) return 'none';
  
  let selectedCount = 0;
  const currentPath = basePath ? `${basePath}/${node.name}` : node.name;
  
  for (const child of selectableChildren) {
    const childPath = `${currentPath}/${child.name}`;
    if (isPathOrAncestorIncluded(childPath, includedPaths)) {
      selectedCount++;
    } else if (child.type === 'folder') {
      // Check if folder has any selected descendants
      const childState = getFolderSelectionState(child, currentPath, includedPaths);
      if (childState === 'all') selectedCount++;
      else if (childState === 'partial') return 'partial';
    }
  }
  
  if (selectedCount === 0) return 'none';
  if (selectedCount === selectableChildren.length) return 'all';
  return 'partial';
}

/** Collect descendant paths that have explicit weight overrides */
function collectChildWeightPaths(
  node: TreeNode,
  basePath: string,
  pathWeights: Record<string, number>
): string[] {
  const results: string[] = [];
  const currentPath = basePath ? `${basePath}/${node.name}` : node.name;
  if (node.children) {
    for (const child of node.children) {
      const childPath = `${currentPath}/${child.name}`;
      if (childPath in pathWeights) results.push(childPath);
      if (child.children) results.push(...collectChildWeightPaths(child, currentPath, pathWeights));
    }
  }
  return results;
}

/** Resolve effective weight for a path by walking up the hierarchy */
function getEffectiveWeight(
  path: string,
  pathWeights: Record<string, number>
): { weight: number; inherited: boolean; source: string | null } {
  if (path in pathWeights) {
    return { weight: pathWeights[path], inherited: false, source: path };
  }
  const parts = path.split('/');
  for (let i = parts.length - 1; i >= 1; i--) {
    const parentPath = parts.slice(0, i).join('/');
    if (parentPath in pathWeights) {
      return { weight: pathWeights[parentPath], inherited: true, source: parentPath };
    }
  }
  return { weight: 1.0, inherited: false, source: null };
}

export interface FolderTreeProps {
  data: TreeNode[];
  compact?: boolean;
  /** Paths included in the RAG index */
  includedPaths?: Set<string>;
  /** Called when user toggles inclusion of paths (array for bulk operations) */
  onToggleInclude?: (paths: string[], action: 'add' | 'remove') => void;
  /** Called when user clicks a node (for navigation/preview) */
  onNodeClick?: (node: TreeNode, path: string) => void;
  /** Per-path weight overrides (0.0–2.0, default 1.0). Folder weights propagate to children. */
  pathWeights?: Record<string, number>;
  /** Called when user changes weight. null removes the override (inherits parent weight). */
  onWeightChange?: (path: string, weight: number | null) => void;
  /** Called when a depth-truncated folder is expanded — returns children to merge into the tree */
  onLoadChildren?: (path: string) => Promise<TreeNode[]>;
  className?: string;
}

interface TreeItemProps {
  node: TreeNode;
  depth?: number;
  path?: string;
  includedPaths?: Set<string>;
  onToggleInclude?: (paths: string[], action: 'add' | 'remove') => void;
  onNodeClick?: (node: TreeNode, path: string) => void;
  pathWeights?: Record<string, number>;
  onWeightChange?: (path: string, weight: number | null) => void;
  expandedPaths: Set<string>;
  onToggleExpand: (path: string) => void;
  onLoadChildren?: (path: string) => Promise<TreeNode[]>;
  loadingPaths: Set<string>;
  onSetLoading: (path: string, loading: boolean) => void;
  onMergeChildren: (path: string, children: TreeNode[]) => void;
}

function WeightEditor({
  effectiveWeight,
  isInherited,
  inheritedFrom,
  onWeightChange,
  currentPath,
  isFolder = false,
  childOverridePaths = [],
}: {
  effectiveWeight: number;
  isInherited: boolean;
  inheritedFrom: string | null;
  onWeightChange?: (path: string, weight: number | null) => void;
  currentPath: string;
  isFolder?: boolean;
  childOverridePaths?: string[];
}) {
  const [editing, setEditing] = useState(false);
  const [inputValue, setInputValue] = useState(effectiveWeight.toFixed(1));
  const [overrideChildren, setOverrideChildren] = useState(true);

  if (!onWeightChange) return null;

  const hasChildOverrides = childOverridePaths.length > 0;

  const handleSave = () => {
    setEditing(false);
    const parsed = parseFloat(inputValue);
    if (isNaN(parsed)) return;
    const clamped = Math.max(0, Math.min(2, Math.round(parsed * 10) / 10));
    // For folders: clear child overrides first if requested
    if (isFolder && overrideChildren && hasChildOverrides) {
      for (const childPath of childOverridePaths) {
        onWeightChange(childPath, null);
      }
    }
    onWeightChange(currentPath, clamped);
  };

  const handleReset = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditing(false);
    onWeightChange(currentPath, null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSave();
    if (e.key === 'Escape') {
      setEditing(false);
      setInputValue(effectiveWeight.toFixed(1));
    }
    e.stopPropagation();
  };

  if (editing) {
    return (
      <span className="flex items-center gap-1.5" onClick={e => e.stopPropagation()}>
        {!isInherited && (
          <button
            onMouseDown={e => { e.preventDefault(); handleReset(e); }}
            className="text-[10px] text-text-subtle hover:text-primary px-0.5 leading-none"
            title="Reset to inherited weight"
          >
            reset
          </button>
        )}
        <input
          type="number"
          min="0"
          max="2"
          step="0.1"
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          onBlur={handleSave}
          onKeyDown={handleKeyDown}
          onFocus={e => e.target.select()}
          autoFocus
          className="w-14 text-xs text-center bg-surface border border-border rounded px-1 py-0.5 font-mono
                     focus:outline-none focus:ring-1 focus:ring-primary"
        />
        {isFolder && (
          <label
            className="flex items-center gap-0.5 text-[10px] text-text-subtle whitespace-nowrap cursor-pointer"
            title="Clear individual weight overrides within this folder"
            onMouseDown={e => e.preventDefault()}
          >
            <input
              type="checkbox"
              checked={overrideChildren}
              onChange={e => setOverrideChildren(e.target.checked)}
              className="w-3 h-3 rounded border-border accent-primary"
            />
            override
          </label>
        )}
      </span>
    );
  }

  const isDefault = effectiveWeight === 1.0 && !isInherited;

  return (
    <button
      onClick={e => {
        e.stopPropagation();
        setInputValue(effectiveWeight.toFixed(1));
        setEditing(true);
      }}
      title={
        isInherited && inheritedFrom
          ? `×${effectiveWeight.toFixed(1)} inherited from ${inheritedFrom}`
          : isFolder
            ? `Click to set folder weight (applies to all children${hasChildOverrides ? `, ${childOverridePaths.length} override${childOverridePaths.length > 1 ? 's' : ''} exist` : ''})`
            : effectiveWeight === 1.0
              ? 'Click to set context weight (default 1.0)'
              : `×${effectiveWeight.toFixed(1)} (click to edit)`
      }
      className={cn(
        'text-xs font-mono px-1.5 py-0.5 rounded transition-all whitespace-nowrap',
        isDefault && 'text-text-subtle/40 hover:text-text-subtle hover:bg-surface-raised',
        !isDefault && effectiveWeight < 1 && 'bg-warning/10 text-warning hover:bg-warning/20',
        !isDefault && effectiveWeight > 1 && 'bg-success/10 text-success hover:bg-success/20',
        !isDefault && effectiveWeight === 1 && 'text-text-subtle',
        isInherited && 'italic',
      )}
    >
      ×{effectiveWeight.toFixed(1)}
    </button>
  );
}

function TreeItem({ node, depth = 0, path = '', includedPaths, onToggleInclude, onNodeClick, pathWeights, onWeightChange, expandedPaths, onToggleExpand, onLoadChildren, loadingPaths, onSetLoading, onMergeChildren }: TreeItemProps) {
  const currentPath = path ? `${path}/${node.name}` : node.name;
  const expanded = expandedPaths.has(currentPath);
  const hasChildren = node.children && node.children.length > 0;
  const isFolder = node.type === 'folder';
  const isLazyLoadable = isFolder && !hasChildren && node.has_children;
  const isLoading = loadingPaths.has(currentPath);
  const isIncluded = includedPaths ? isPathOrAncestorIncluded(currentPath, includedPaths) : (node.selected ?? false);
  const isIgnored = node.status === 'ignored';
  const isSelectable = !isIgnored;
  
  // For folders, check if partially selected (some children selected but not all)
  const folderSelectionState = isFolder && includedPaths 
    ? getFolderSelectionState(node, path, includedPaths) 
    : 'none';
  const isPartiallySelected = isFolder && folderSelectionState === 'partial';
  const isFolderFullySelected = isFolder && (isIncluded || folderSelectionState === 'all');

  const { weight: effectiveWeight, inherited: isWeightInherited, source: weightSource } =
    getEffectiveWeight(currentPath, pathWeights ?? {});

  const handleRowClick = () => {
    if (!isSelectable || !onToggleInclude) return;
    
    if (isFolder) {
      // For folders: toggle the folder path itself
      // If fully selected -> remove (deselect all)
      // If partial or none -> add (select all)
      const shouldSelect = folderSelectionState !== 'all';
      onToggleInclude([currentPath], shouldSelect ? 'add' : 'remove');
    } else {
      // For files: just toggle this file
      onToggleInclude([currentPath], isIncluded ? 'remove' : 'add');
    }
  };

  const handleExpandToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    // Lazy-load children for depth-truncated folders
    if (isLazyLoadable && !expanded && onLoadChildren && !isLoading) {
      onSetLoading(currentPath, true);
      onLoadChildren(currentPath).then((children) => {
        onMergeChildren(currentPath, children);
        onToggleExpand(currentPath);
      }).catch(() => {}).finally(() => {
        onSetLoading(currentPath, false);
      });
      return;
    }
    onToggleExpand(currentPath);
  };

  // Determine icon based on type and inclusion state
  const FolderIcon = expanded ? FolderOpen : Folder;
  const FileIcon = isIncluded ? FileText : File;
  
  // Effective inclusion for display (folder is "included" if it or all its children are)
  const effectivelyIncluded = isFolder ? (isIncluded || isFolderFullySelected) : isIncluded;

  // For ancestor-included items, treat as included for status display
  const isIncludedForStatus = isIncluded;

  // Derive effective status:
  // - indexed but unselected → pending_removal (will be removed on next rebuild)
  // - included file with no explicit status → pending
  // - otherwise use node.status
  const effectiveStatus: FileStatus | undefined = 
    (node.status === 'indexed' && !isIncludedForStatus) ? 'pending_removal'
    : node.status ? node.status
    : (isIncludedForStatus && !isFolder) ? 'pending'
    : undefined;

  // Collect child paths with explicit weight overrides (for folder weight bulk operations)
  const childOverridePaths = isFolder ? collectChildWeightPaths(node, path, pathWeights ?? {}) : [];

  // Show weight editor on included folders or included/pending files
  const showFolderWeight = isFolder && !isIgnored && (effectivelyIncluded || isPartiallySelected);

  // Only show status badge for ignored items, included items with pending/indexed, or pending_removal
  const showStatus = isIgnored || effectiveStatus === 'pending_removal' || (isIncluded && effectiveStatus && effectiveStatus !== 'error');

  return (
    <div>
      <div
        className={cn(
          'group flex items-center gap-1 rounded-md px-2 py-1 my-px transition-colors',
          depth > 0 && 'ml-4',
          // Hover state only for selectable items
          isSelectable && 'hover:bg-surface-raised cursor-pointer',
          // Ignored items are dimmed and not interactive
          isIgnored && 'opacity-50 cursor-default',
          // Selected/included items get a subtle background
          isIncluded && !isIgnored && 'bg-primary/5',
          effectiveWeight < 1 && effectiveWeight > 0 && (showFolderWeight || (isIncluded && (effectiveStatus === 'indexed' || effectiveStatus === 'pending'))) && 'opacity-75',
          effectiveWeight === 0 && (showFolderWeight || (isIncluded && (effectiveStatus === 'indexed' || effectiveStatus === 'pending'))) && 'opacity-40'
        )}
        onClick={handleRowClick}
        title={isIgnored 
          ? 'This item is excluded from indexing' 
          : isFolder
            ? (effectivelyIncluded || isPartiallySelected) 
              ? 'Click to remove folder and all contents from RAG index'
              : 'Click to add folder and all contents to RAG index'
            : isIncluded 
              ? 'Click to remove from RAG index' 
              : 'Click to add to RAG index'
        }
      >
        {isFolder ? (
          <Button
            variant="ghost"
            size="icon-sm"
            className="h-5 w-5 p-0 hover:bg-surface-raised text-text-subtle"
            onClick={handleExpandToggle}
          >
            {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          </Button>
        ) : (
          <span className="w-5" />
        )}

        {/* Icon indicates inclusion state */}
        <span
          className={cn(
            'flex items-center justify-center w-5 h-5 transition-colors shrink-0',
            isIgnored 
              ? 'text-text-subtle/50'
              : effectivelyIncluded 
                ? 'text-primary' 
                : isPartiallySelected
                  ? 'text-primary/60'
                  : 'text-text-subtle'
          )}
        >
          {isFolder 
            ? <FolderIcon className={cn(
                'w-4 h-4', 
                effectivelyIncluded && !isIgnored && 'fill-primary/20',
                isPartiallySelected && !isIgnored && 'fill-primary/10'
              )} />
            : <FileIcon className={cn('w-4 h-4', isIncluded && !isIgnored && 'fill-primary/20')} />
          }
        </span>

        <span className={cn(
          "text-sm ml-1 truncate transition-all",
          isIgnored
            ? "text-text-subtle font-mono"
            : (effectivelyIncluded || isPartiallySelected)
              ? "text-text font-semibold font-mono" 
              : isFolder 
                ? "text-text font-medium" 
                : "text-text-muted font-mono"
        )}>
          {node.name}
        </span>

        {/* View file button — only for files when onNodeClick is provided */}
        {!isFolder && onNodeClick && (
          <Button
            variant="ghost"
            size="icon-sm"
            className="h-5 w-5 p-0 opacity-0 group-hover:opacity-100 text-text-subtle hover:text-primary transition-opacity shrink-0"
            onClick={(e: React.MouseEvent) => { e.stopPropagation(); onNodeClick(node, currentPath); }}
            title="View file"
          >
            <Eye className="w-3.5 h-3.5" />
          </Button>
        )}

        {/* Right side: chunk count, status badge, then weight - always at far right */}
        <span className="ml-auto flex items-center gap-2 shrink-0">
          {/* Chunk count for indexed items */}
          {node.chunks !== undefined && effectiveStatus === 'indexed' && (
            <span className="text-xs text-text-subtle">
              {node.chunks} chunks
            </span>
          )}
          
          {/* Status badge: show for ignored items or included items with pending/indexed status */}
          {showStatus && effectiveStatus && (
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

          {/* Weight editor: for indexed/pending files OR included folders */}
          {(showFolderWeight || ((effectiveStatus === 'indexed' || effectiveStatus === 'pending') && isIncluded)) && (
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
        </span>
      </div>

      {hasChildren && expanded && (
        <div className="border-l border-border-subtle ml-[1.1rem]">
          {node.children!.map((child, i) => (
            <TreeItem 
              key={`${child.name}-${i}`} 
              node={child} 
              depth={depth + 1}
              path={currentPath}
              includedPaths={includedPaths}
              onToggleInclude={onToggleInclude}
              onNodeClick={onNodeClick}
              pathWeights={pathWeights}
              onWeightChange={onWeightChange}
              expandedPaths={expandedPaths}
              onToggleExpand={onToggleExpand}
              onLoadChildren={onLoadChildren}
              loadingPaths={loadingPaths}
              onSetLoading={onSetLoading}
              onMergeChildren={onMergeChildren}
            />
          ))}
        </div>
      )}
    </div>
  );
}

const EXPANDED_STORAGE_KEY = 'codrag_tree_expanded';

export function FolderTree({
  data,
  compact,
  includedPaths,
  onToggleInclude,
  onNodeClick,
  pathWeights,
  onWeightChange,
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

  const [loadingPaths, setLoadingPaths] = useState<Set<string>>(new Set());
  const [mergedData, setMergedData] = useState<TreeNode[]>(data);

  // Keep mergedData in sync when data prop changes (e.g. project switch)
  const [prevData, setPrevData] = useState(data);
  if (data !== prevData) {
    setPrevData(data);
    setMergedData(data);
  }

  const handleToggleExpand = useCallback((path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      if (typeof window !== 'undefined') {
        localStorage.setItem(EXPANDED_STORAGE_KEY, JSON.stringify([...next]));
      }
      return next;
    });
  }, []);

  const handleSetLoading = useCallback((path: string, loading: boolean) => {
    setLoadingPaths((prev) => {
      const next = new Set(prev);
      if (loading) next.add(path); else next.delete(path);
      return next;
    });
  }, []);

  const handleMergeChildren = useCallback((path: string, children: TreeNode[]) => {
    setMergedData((prev) => {
      // Deep-clone and merge children into the node at path
      function mergeInto(nodes: TreeNode[], segments: string[], idx: number): TreeNode[] {
        return nodes.map((n) => {
          if (n.name === segments[idx]) {
            if (idx === segments.length - 1) {
              // Found target — set children, clear has_children flag
              return { ...n, children, has_children: undefined };
            }
            if (n.children) {
              return { ...n, children: mergeInto(n.children, segments, idx + 1) };
            }
          }
          return n;
        });
      }
      const segments = path.split('/');
      return mergeInto(prev, segments, 0);
    });
  }, []);

  return (
    <div className={cn(compact ? 'text-sm' : '', className)}>
      {mergedData.map((node, i) => (
        <TreeItem
          key={`${node.name}-${i}`}
          node={node}
          includedPaths={includedPaths}
          onToggleInclude={onToggleInclude}
          onNodeClick={onNodeClick}
          pathWeights={pathWeights}
          onWeightChange={onWeightChange}
          expandedPaths={expandedPaths}
          onToggleExpand={handleToggleExpand}
          onLoadChildren={onLoadChildren}
          loadingPaths={loadingPaths}
          onSetLoading={handleSetLoading}
          onMergeChildren={handleMergeChildren}
        />
      ))}
    </div>
  );
}

/**
 * Sample file tree demonstrating the status flow:
 * - Unselected items: no status indicator (user hasn't added them to RAG)
 * - Selected items: 'pending' until indexed, then 'indexed' with chunk count
 * - 'ignored' items: always shown, not selectable (e.g., node_modules)
 * - 'error' items: something went wrong during indexing
 */
export const sampleFileTree: TreeNode[] = [
  {
    name: 'src',
    type: 'folder',
    children: [
      {
        name: 'codrag',
        type: 'folder',
        children: [
          // These are selected and indexed
          { name: 'server.py', type: 'file', status: 'indexed', chunks: 24 },
          { name: 'cli.py', type: 'file', status: 'indexed', chunks: 18 },
          { name: '__init__.py', type: 'file', status: 'indexed', chunks: 2 },
          {
            name: 'core',
            type: 'folder',
            children: [
              { name: 'registry.py', type: 'file', status: 'indexed', chunks: 31 },
              // Selected but still indexing
              { name: 'embedding.py', type: 'file', status: 'pending' },
              { name: 'trace.py', type: 'file', status: 'indexed', chunks: 45 },
              // Error during indexing
              { name: 'watcher.py', type: 'file', status: 'error' },
            ],
          },
          {
            name: 'api',
            type: 'folder',
            children: [
              { name: 'routes.py', type: 'file', status: 'indexed', chunks: 28 },
              { name: 'auth.py', type: 'file', status: 'indexed', chunks: 15 },
            ],
          },
        ],
      },
    ],
  },
  {
    name: 'docs',
    type: 'folder',
    children: [
      { name: 'ARCHITECTURE.md', type: 'file', status: 'indexed', chunks: 42 },
      { name: 'API.md', type: 'file', status: 'indexed', chunks: 38 },
      // Just selected, waiting to be indexed
      { name: 'ROADMAP.md', type: 'file', status: 'pending' },
      // Was indexed but user removed it — shows "Removing" until next rebuild
      { name: 'CHANGELOG.md', type: 'file', status: 'indexed', chunks: 12 },
    ],
  },
  {
    name: 'node_modules',
    type: 'folder',
    status: 'ignored',
    children: [
      { name: 'react', type: 'folder', status: 'ignored', children: [] },
      { name: 'typescript', type: 'folder', status: 'ignored', children: [] },
    ],
  },
  {
    name: 'tests',
    type: 'folder',
    children: [
      // These are not selected (no status) - user can click to add
      { name: 'test_registry.py', type: 'file' },
      { name: 'test_search.py', type: 'file' },
      { name: 'conftest.py', type: 'file' },
    ],
  },
];
