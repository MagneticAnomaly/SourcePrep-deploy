import { useState, useCallback, useEffect } from 'react';
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  File,
  FileText,
  Loader2,
  Square,
  CheckSquare,
  MinusSquare,
  Ban,
} from 'lucide-react';
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

/** Check if a path or any of its ancestor folders is in the excluded set */
function isPathOrAncestorExcluded(path: string, excludedPaths: Set<string>): boolean {
  if (excludedPaths.has(path)) return true;
  const parts = path.split('/');
  for (let i = 1; i < parts.length; i++) {
    if (excludedPaths.has(parts.slice(0, i).join('/'))) return true;
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
      const childState = getFolderSelectionState(child, currentPath, includedPaths);
      if (childState === 'all') selectedCount++;
      else if (childState === 'partial') return 'partial';
    }
  }

  if (selectedCount === 0) return 'none';
  if (selectedCount === selectableChildren.length) return 'all';
  return 'partial';
}

/** Check exclude state of a folder's children */
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

/** Match a path against a minimal glob pattern subset used by DEFAULT_EXCLUDE_FILE_GLOBS.
 *  Supports: leading `**​/` (match at any depth), literal path segments, and a
 *  trailing `*.ext` pattern on the basename. Directory segments are matched as
 *  path components, not substrings — so pattern `**​/.cursor/rules/*.mdc` won't
 *  falsely match `a.cursor/rules/x.mdc`. */
function pathMatchesGlob(path: string, raw: string): boolean {
  const pathSegs = path.split('/');
  const fileName = pathSegs[pathSegs.length - 1] ?? '';

  const stripped = raw.startsWith('**/') ? raw.slice(3) : raw;
  const patternSegs = stripped.split('/');
  const lastPat = patternSegs[patternSegs.length - 1];

  // Basename gate: the pattern's last segment must match the path's basename
  const basenameMatches =
    (lastPat.startsWith('*.') && fileName.endsWith(lastPat.slice(1))) ||
    (!lastPat.includes('*') && fileName === lastPat);
  if (!basenameMatches) return false;

  // Directory gate: the pattern's directory segments must appear contiguously
  // somewhere in the path's directory segments (so `**​/.cursor/rules/` needs
  // `.cursor` followed by `rules` as actual segments, not as a substring).
  const dirPat = patternSegs.slice(0, -1);
  if (dirPat.length === 0) return true;

  const dirPath = pathSegs.slice(0, -1);
  if (dirPath.length < dirPat.length) return false;

  outer: for (let start = 0; start <= dirPath.length - dirPat.length; start++) {
    for (let j = 0; j < dirPat.length; j++) {
      if (dirPath[start + j] !== dirPat[j]) continue outer;
    }
    return true;
  }
  return false;
}

/** Returns true if the path matches any always-ignored glob pattern */
function isAlwaysIgnored(path: string, patterns: string[]): boolean {
  if (!patterns || patterns.length === 0) return false;
  for (const pattern of patterns) {
    if (pathMatchesGlob(path, pattern)) return true;
  }
  return false;
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
  /** Called when user toggles knowledge inclusion */
  onToggleInclude?: (paths: string[], action: 'add' | 'remove') => void;
  /** Per-path weight overrides (0.0–2.0, default 1.0). Folder weights propagate to children. */
  pathWeights?: Record<string, number>;
  /** Called when user changes weight. null removes the override (inherits parent weight). */
  onWeightChange?: (path: string, weight: number | null) => void;
  /** Paths excluded from the trace graph (and knowledge) */
  excludedPaths?: Set<string>;
  /** Called when user toggles trace exclusion */
  onToggleExclude?: (paths: string[], action: 'add' | 'remove') => void;
  /** Display variant: 'panel' = row click is no-op; 'detail' = row click previews file */
  variant?: 'panel' | 'detail';
  /** Called when a file row is clicked in 'detail' variant */
  onPreviewFile?: (node: TreeNode, path: string) => void;
  /** Always-ignored glob patterns (rendered as status='ignored', non-interactive) */
  alwaysIgnoredPatterns?: string[];
  /** Called when a depth-truncated folder is expanded — returns children to merge into the tree */
  onLoadChildren?: (path: string) => Promise<TreeNode[]>;
  className?: string;
  /**
   * Phase 120 — Named Scopes.
   * When true, the exclude column is rendered disabled with a tooltip directing
   * the user to switch to the global scope to edit exclusions.
   */
  scopeReadOnlyExclude?: boolean;
  /**
   * Phase 120 — Named Scopes.
   * When true, per-path weight controls are rendered disabled.
   */
  scopeReadOnlyWeights?: boolean;
}

interface TreeItemProps {
  node: TreeNode;
  depth?: number;
  path?: string;
  variant?: 'panel' | 'detail';
  includedPaths?: Set<string>;
  onToggleInclude?: (paths: string[], action: 'add' | 'remove') => void;
  pathWeights?: Record<string, number>;
  onWeightChange?: (path: string, weight: number | null) => void;
  excludedPaths?: Set<string>;
  onToggleExclude?: (paths: string[], action: 'add' | 'remove') => void;
  onPreviewFile?: (node: TreeNode, path: string) => void;
  alwaysIgnoredPatterns?: string[];
  expandedPaths: Set<string>;
  onToggleExpand: (path: string) => void;
  onLoadChildren?: (path: string) => Promise<TreeNode[]>;
  loadingPaths: Set<string>;
  onSetLoading: (path: string, loading: boolean) => void;
  onMergeChildren: (path: string, children: TreeNode[]) => void;
  scopeReadOnlyExclude?: boolean;
  scopeReadOnlyWeights?: boolean;
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

function TreeItem({
  node,
  depth = 0,
  path = '',
  variant = 'panel',
  includedPaths,
  onToggleInclude,
  pathWeights,
  onWeightChange,
  excludedPaths,
  onToggleExclude,
  onPreviewFile,
  alwaysIgnoredPatterns,
  expandedPaths,
  onToggleExpand,
  onLoadChildren,
  loadingPaths,
  onSetLoading,
  onMergeChildren,
  scopeReadOnlyExclude = false,
  scopeReadOnlyWeights = false,
}: TreeItemProps) {
  const currentPath = path ? `${path}/${node.name}` : node.name;
  const expanded = expandedPaths.has(currentPath);
  const hasChildren = node.children && node.children.length > 0;
  const isFolder = node.type === 'folder';
  const isLazyLoadable = isFolder && !hasChildren && node.has_children;
  const isLoading = loadingPaths.has(currentPath);

  // Include state
  const isIncluded = includedPaths ? isPathOrAncestorIncluded(currentPath, includedPaths) : (node.selected ?? false);
  const folderSelectionState = isFolder && includedPaths
    ? getFolderSelectionState(node, path, includedPaths)
    : 'none';
  const isFolderPartiallyIncluded = isFolder && folderSelectionState === 'partial';
  const isFolderFullyIncluded = isFolder && (isIncluded || folderSelectionState === 'all');

  // Exclude state
  const isExcluded = excludedPaths ? isPathOrAncestorExcluded(currentPath, excludedPaths) : false;
  const folderExcludeState = isFolder && excludedPaths
    ? getFolderExcludeState(node, path, excludedPaths)
    : 'none';
  const isFolderPartiallyExcluded = isFolder && folderExcludeState === 'partial';
  const isFolderFullyExcluded = isFolder && (isExcluded || folderExcludeState === 'all');

  // Always-ignored (glob-pattern match)
  const isAlwaysIgnoredNode = isAlwaysIgnored(currentPath, alwaysIgnoredPatterns ?? []);
  const isIgnored = node.status === 'ignored' || isAlwaysIgnoredNode;

  const { weight: effectiveWeight, inherited: isWeightInherited, source: weightSource } =
    getEffectiveWeight(currentPath, pathWeights ?? {});

  // Auto-load children for folders restored as "expanded" from localStorage
  // but whose children haven't been fetched yet (beyond API depth limit).
  useEffect(() => {
    if (expanded && isLazyLoadable && onLoadChildren && !isLoading) {
      onSetLoading(currentPath, true);
      onLoadChildren(currentPath).then((children) => {
        onMergeChildren(currentPath, children);
      }).catch(() => {}).finally(() => {
        onSetLoading(currentPath, false);
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded, isLazyLoadable]);

  // Core expand/collapse logic shared by the chevron button and row click.
  // Handles lazy-loading for depth-truncated folders.
  const performExpandToggle = () => {
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

  const handleExpandToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    performExpandToggle();
  };

  // Row click: folders expand/collapse; files preview in 'detail', no-op in 'panel'
  const handleRowClick = () => {
    if (isAlwaysIgnoredNode || isIgnored) return;
    if (isFolder) {
      performExpandToggle();
      return;
    }
    if (variant === 'detail' && onPreviewFile) {
      onPreviewFile(node, currentPath);
    }
  };

  const handleIncludeClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onToggleInclude || isAlwaysIgnoredNode || isIgnored) return;

    const effectivelyIncluded = isIncluded || isFolderFullyIncluded;
    if (effectivelyIncluded) {
      onToggleInclude([currentPath], 'remove');
      return;
    }
    // Mutual exclusion: un-exclude first if currently excluded
    if (excludedPaths && isPathOrAncestorExcluded(currentPath, excludedPaths) && onToggleExclude) {
      onToggleExclude([currentPath], 'remove');
    }
    onToggleInclude([currentPath], 'add');
  };

  const handleExcludeClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onToggleExclude || isAlwaysIgnoredNode || isIgnored) return;

    const effectivelyExcluded = isExcluded || isFolderFullyExcluded;
    if (effectivelyExcluded) {
      onToggleExclude([currentPath], 'remove');
      return;
    }
    // Mutual exclusion: un-include first if currently included
    if (includedPaths && isPathOrAncestorIncluded(currentPath, includedPaths) && onToggleInclude) {
      onToggleInclude([currentPath], 'remove');
    }
    onToggleExclude([currentPath], 'add');
  };

  const FolderIcon = expanded ? FolderOpen : Folder;
  const FileIcon = isIncluded ? FileText : File;

  // Derive effective status (existing logic, only relevant when included)
  const effectiveStatus: FileStatus | undefined =
    (node.status === 'indexed' && !isIncluded) ? 'pending_removal'
    : node.status ? node.status
    : (isIncluded && !isFolder) ? 'pending'
    : undefined;

  const childOverridePaths = isFolder ? collectChildWeightPaths(node, path, pathWeights ?? {}) : [];

  const showFolderWeight = isFolder && !isIgnored && (isFolderFullyIncluded || isFolderPartiallyIncluded);
  const showStatus = isIncluded && effectiveStatus && effectiveStatus !== 'error';

  return (
    <div>
      <div
        className={cn(
          'group flex items-center gap-1 rounded-md px-2 py-1 my-px transition-colors',
          depth > 0 && 'ml-4',
          // Always-ignored: no hover, no cursor
          isAlwaysIgnoredNode && 'cursor-default',
          // Selectable items hover
          !isAlwaysIgnoredNode && !isIgnored && 'hover:bg-surface-raised',
          // Cursor behavior
          !isAlwaysIgnoredNode && !isIgnored && variant === 'detail' && !isFolder && 'cursor-pointer',
          !isAlwaysIgnoredNode && !isIgnored && isFolder && 'cursor-pointer',
          !isAlwaysIgnoredNode && !isIgnored && variant === 'panel' && !isFolder && 'cursor-default',
          // Node-status ignored (from backend)
          isIgnored && !isAlwaysIgnoredNode && 'opacity-50 cursor-default',
          // Included rows no longer get a bg tint — the checkbox state
          // already signals inclusion. (Removed 2026-05-15: was bg-primary/5,
          // redundant with the checkbox and visually noisy in docs embeds.)
          // Excluded background
          isExcluded && !isIgnored && 'bg-error/8',
          // Weight opacity (only for included)
          isIncluded && effectiveWeight < 1 && effectiveWeight > 0 && 'opacity-75',
          isIncluded && effectiveWeight === 0 && 'opacity-40'
        )}
        onClick={handleRowClick}
        title={
          isAlwaysIgnoredNode
            ? 'Always available to AI assistants — excluded from indexing.'
            : isIgnored
              ? 'This item is excluded from indexing'
              : isFolder
                ? (expanded ? 'Click to collapse' : 'Click to expand')
                : variant === 'detail'
                  ? 'Click to preview'
                  : ''
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

        {/* File/folder icon reflects include/exclude state */}
        <span
          className={cn(
            'flex items-center justify-center w-5 h-5 transition-colors shrink-0',
            isAlwaysIgnoredNode
              ? 'text-text-subtle/50'
              : isIgnored
                ? 'text-text-subtle/50'
                : isExcluded
                  ? 'text-error'
                  : (isFolderFullyIncluded || isIncluded)
                    ? 'text-primary'
                    : isFolderPartiallyIncluded
                      ? 'text-primary/60'
                      : 'text-text-subtle'
          )}
        >
          {isFolder
            ? <FolderIcon className={cn(
                'w-4 h-4',
                isFolderFullyIncluded && !isIgnored && !isExcluded && 'fill-primary/20',
                isFolderPartiallyIncluded && !isIgnored && !isExcluded && 'fill-primary/10',
                isExcluded && !isIgnored && 'fill-error/20'
              )} />
            : <FileIcon className={cn(
                'w-4 h-4',
                isIncluded && !isIgnored && !isExcluded && 'fill-primary/20',
                isExcluded && !isIgnored && 'fill-error/20'
              )} />
          }
        </span>

        <span className={cn(
          'text-sm ml-1 truncate transition-all font-mono',
          isAlwaysIgnoredNode
            ? 'text-text-subtle line-through decoration-text-subtle/60'
            : isIgnored
              ? 'text-text-subtle'
              : isExcluded
                ? 'text-error line-through decoration-error/60'
                : (isIncluded || isFolderPartiallyIncluded)
                  ? 'text-text font-semibold'
                  : isFolder
                    ? 'text-text font-medium'
                    : 'text-text-muted'
        )}>
          {node.name}
        </span>

        {/* Right side: chunks, status, weight, include checkbox, exclude icon */}
        <span className="ml-auto flex items-center gap-1.5 shrink-0">
          {/* Chunk count — only in detail variant (panel is too narrow) */}
          {variant === 'detail' && isIncluded && node.chunks !== undefined && effectiveStatus === 'indexed' && (
            <span className="text-xs text-text-subtle">
              {node.chunks} chunks
            </span>
          )}

          {/* Status indicator — full pill in detail variant, just a colored
              dot in panel variant (with a tooltip carrying the label). The
              full badge crowds filenames in the compact panel view. */}
          {showStatus && effectiveStatus && (
            variant === 'detail' ? (
              <span
                className={cn(
                  'flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full',
                  `${statusColors[effectiveStatus]}/20`
                )}
              >
                <span className={cn('w-1.5 h-1.5 rounded-full', statusColors[effectiveStatus])} />
                <span className="text-text-subtle hidden sm:inline">{statusLabels[effectiveStatus]}</span>
              </span>
            ) : (
              <span
                className={cn('w-2 h-2 rounded-full shrink-0', statusColors[effectiveStatus])}
                title={statusLabels[effectiveStatus]}
              />
            )
          )}

          {/* Weight editor — only when included. Disabled on non-global scopes (v1). */}
          {(showFolderWeight || (isIncluded && (effectiveStatus === 'indexed' || effectiveStatus === 'pending'))) && (
            scopeReadOnlyWeights ? (
              <span
                className="text-xs font-mono px-1.5 py-0.5 rounded text-text-subtle/30 cursor-not-allowed"
                title="Path weights are disabled in named scopes (v1). Switch to the global scope to edit."
              >
                ×{effectiveWeight.toFixed(1)}
              </span>
            ) : (
              <WeightEditor
                effectiveWeight={effectiveWeight}
                isInherited={isWeightInherited}
                inheritedFrom={weightSource}
                onWeightChange={onWeightChange}
                currentPath={currentPath}
                isFolder={isFolder}
                childOverridePaths={childOverridePaths}
              />
            )
          )}

          {/* Include checkbox — hidden for always-ignored files */}
          {!isAlwaysIgnoredNode && onToggleInclude && (
            <button
              onClick={handleIncludeClick}
              className={cn(
                'p-0.5 rounded transition-colors',
                (isIncluded || isFolderFullyIncluded)
                  ? 'text-primary hover:text-primary/80'
                  : isFolderPartiallyIncluded
                    ? 'text-primary/60 hover:text-primary'
                    : 'text-text-subtle/40 hover:text-text-subtle'
              )}
              title={(isIncluded || isFolderFullyIncluded) ? 'Remove from knowledge scope' : 'Add to knowledge scope'}
            >
              {(isIncluded || isFolderFullyIncluded)
                ? <CheckSquare className="w-4 h-4" />
                : isFolderPartiallyIncluded
                  ? <MinusSquare className="w-4 h-4" />
                  : <Square className="w-4 h-4" />
              }
            </button>
          )}

          {/* Exclude icon — hidden for always-ignored files. Disabled on non-global scopes. */}
          {!isAlwaysIgnoredNode && onToggleExclude && (
            <button
              onClick={scopeReadOnlyExclude ? undefined : handleExcludeClick}
              disabled={scopeReadOnlyExclude}
              className={cn(
                'p-0.5 rounded transition-colors',
                scopeReadOnlyExclude
                  ? 'text-text-subtle/20 cursor-not-allowed'
                  : (isExcluded || isFolderFullyExcluded)
                    ? 'text-error hover:text-error/80'
                    : isFolderPartiallyExcluded
                      ? 'text-error/60 hover:text-error'
                      : 'text-text-subtle/40 hover:text-text-subtle'
              )}
              title={
                scopeReadOnlyExclude
                  ? 'Excludes are global. Switch to the global scope to edit.'
                  : (isExcluded || isFolderFullyExcluded)
                    ? 'Remove trace exclusion'
                    : 'Exclude from trace and knowledge'
              }
            >
              <Ban className={cn('w-4 h-4', (isExcluded || isFolderFullyExcluded) && 'fill-error/10')} />
            </button>
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
              variant={variant}
              includedPaths={includedPaths}
              onToggleInclude={onToggleInclude}
              pathWeights={pathWeights}
              onWeightChange={onWeightChange}
              excludedPaths={excludedPaths}
              onToggleExclude={onToggleExclude}
              onPreviewFile={onPreviewFile}
              alwaysIgnoredPatterns={alwaysIgnoredPatterns}
              expandedPaths={expandedPaths}
              onToggleExpand={onToggleExpand}
              onLoadChildren={onLoadChildren}
              loadingPaths={loadingPaths}
              onSetLoading={onSetLoading}
              onMergeChildren={onMergeChildren}
              scopeReadOnlyExclude={scopeReadOnlyExclude}
              scopeReadOnlyWeights={scopeReadOnlyWeights}
            />
          ))}
        </div>
      )}
    </div>
  );
}

const EXPANDED_STORAGE_KEY = 'prep_tree_expanded';

export function FolderTree({
  data,
  compact,
  includedPaths,
  onToggleInclude,
  pathWeights,
  onWeightChange,
  excludedPaths,
  onToggleExclude,
  variant = 'panel',
  onPreviewFile,
  alwaysIgnoredPatterns,
  onLoadChildren,
  className,
  scopeReadOnlyExclude = false,
  scopeReadOnlyWeights = false,
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
      function mergeInto(nodes: TreeNode[], segments: string[], idx: number): TreeNode[] {
        return nodes.map((n) => {
          if (n.name === segments[idx]) {
            if (idx === segments.length - 1) {
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
          variant={variant}
          includedPaths={includedPaths}
          onToggleInclude={onToggleInclude}
          pathWeights={pathWeights}
          onWeightChange={onWeightChange}
          excludedPaths={excludedPaths}
          onToggleExclude={onToggleExclude}
          onPreviewFile={onPreviewFile}
          alwaysIgnoredPatterns={alwaysIgnoredPatterns}
          expandedPaths={expandedPaths}
          onToggleExpand={handleToggleExpand}
          onLoadChildren={onLoadChildren}
          loadingPaths={loadingPaths}
          onSetLoading={handleSetLoading}
          onMergeChildren={handleMergeChildren}
          scopeReadOnlyExclude={scopeReadOnlyExclude}
          scopeReadOnlyWeights={scopeReadOnlyWeights}
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
        name: 'prep',
        type: 'folder',
        children: [
          { name: 'server.py', type: 'file', status: 'indexed', chunks: 24 },
          { name: 'cli.py', type: 'file', status: 'indexed', chunks: 18 },
          { name: '__init__.py', type: 'file', status: 'indexed', chunks: 2 },
          {
            name: 'core',
            type: 'folder',
            children: [
              { name: 'registry.py', type: 'file', status: 'indexed', chunks: 31 },
              { name: 'embedding.py', type: 'file', status: 'pending' },
              { name: 'trace.py', type: 'file', status: 'indexed', chunks: 45 },
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
      { name: 'ROADMAP.md', type: 'file', status: 'pending' },
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
      { name: 'test_registry.py', type: 'file' },
      { name: 'test_search.py', type: 'file' },
      { name: 'conftest.py', type: 'file' },
    ],
  },
];
