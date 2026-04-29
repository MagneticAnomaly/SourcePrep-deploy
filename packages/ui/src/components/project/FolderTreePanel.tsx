import { useState, useRef, useEffect } from 'react';
import { Card, Flex, Title, Badge } from '@tremor/react';
import { RefreshCw, AlertCircle, Clock, ChevronDown, Pencil, Trash2, Check } from 'lucide-react';
import { cn } from '../../lib/utils';
import { FolderTree } from './FolderTree';
import type { TreeNode } from './FolderTree';
import type { ScopeStatus } from '../../types';
import type { ScopeRecord, ScopeSummary } from '../../types';

// ── ScopeDropdown ────────────────────────────────────────────────────────────

interface ScopeDropdownProps {
  scopes: ScopeSummary[];
  activeScopeId: string;
  onSelect?: (id: string) => void;
}

function ScopeDropdown({ scopes, activeScopeId, onSelect }: ScopeDropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const active = scopes.find(s => s.id === activeScopeId) ?? scopes[0];

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-label={active?.display_name ?? 'Select scope'}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen(v => !v)}
        className={cn(
          'flex items-center gap-1.5 px-2 py-1 rounded text-sm font-medium',
          'bg-surface-raised border border-border hover:border-primary/50 transition-colors',
          'text-text'
        )}
      >
        <span>{active?.display_name ?? activeScopeId}</span>
        {active && active.path_count > 0 && (
          <span className="text-xs text-text-subtle">({active.path_count})</span>
        )}
        <ChevronDown className={cn('w-3.5 h-3.5 text-text-subtle transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <ul
          role="listbox"
          className={cn(
            'absolute top-full left-0 mt-1 z-50 min-w-[180px]',
            'bg-surface border border-border rounded-md shadow-lg py-1',
            'max-h-64 overflow-y-auto'
          )}
        >
          {scopes.map(scope => (
            <li
              key={scope.id}
              role="option"
              aria-selected={scope.id === activeScopeId}
              onClick={() => {
                onSelect?.(scope.id);
                setOpen(false);
              }}
              className={cn(
                'flex items-center justify-between px-3 py-1.5 text-sm cursor-pointer',
                'hover:bg-surface-raised transition-colors',
                scope.id === activeScopeId && 'text-primary font-medium'
              )}
            >
              <span>{scope.display_name}</span>
              <span className="text-xs text-text-subtle ml-3">{scope.path_count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── ScopeCreateInline ────────────────────────────────────────────────────────

interface ScopeCreateInlineProps {
  onCancel: () => void;
  onSubmit: (name: string) => Promise<void>;
}

function ScopeCreateInline({ onCancel, onSubmit }: ScopeCreateInlineProps) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = async () => {
    const trimmed = name.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    try {
      await onSubmit(trimmed);
    } finally {
      setBusy(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSubmit();
    if (e.key === 'Escape') onCancel();
  };

  return (
    <div className="flex items-center gap-2 mb-2">
      <input
        ref={inputRef}
        type="text"
        placeholder="Scope name"
        value={name}
        onChange={e => setName(e.target.value)}
        onKeyDown={handleKeyDown}
        aria-label="Scope name"
        className={cn(
          'flex-1 text-sm px-2 py-1 rounded border border-border bg-surface',
          'focus:outline-none focus:ring-1 focus:ring-primary',
          'text-text placeholder:text-text-subtle'
        )}
      />
      <button
        type="button"
        onClick={handleSubmit}
        disabled={!name.trim() || busy}
        className={cn(
          'text-sm px-2 py-1 rounded transition-colors',
          'bg-primary text-white hover:bg-primary/90',
          'disabled:opacity-40 disabled:cursor-not-allowed'
        )}
      >
        Create
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="text-sm px-1.5 py-1 rounded text-text-subtle hover:text-text hover:bg-surface-raised transition-colors"
      >
        Cancel
      </button>
    </div>
  );
}

// ── ScopeEditPopover ─────────────────────────────────────────────────────────

interface ScopeEditPopoverProps {
  scope: ScopeSummary;
  onRename?: (id: string, display_name: string) => Promise<void>;
  onDelete?: (id: string) => Promise<void>;
}

function ScopeEditPopover({ scope, onRename, onDelete }: ScopeEditPopoverProps) {
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [newName, setNewName] = useState(scope.display_name);
  const ref = useRef<HTMLDivElement>(null);

  // Reset rename state when scope changes
  useEffect(() => {
    setNewName(scope.display_name);
    setRenaming(false);
  }, [scope.id, scope.display_name]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setRenaming(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const handleRename = async () => {
    const trimmed = newName.trim();
    if (!trimmed || trimmed === scope.display_name) {
      setRenaming(false);
      return;
    }
    await onRename?.(scope.id, trimmed);
    setRenaming(false);
    setOpen(false);
  };

  const handleDelete = async () => {
    const confirmed = window.confirm(`Delete scope "${scope.display_name}"? This cannot be undone.`);
    if (!confirmed) return;
    await onDelete?.(scope.id);
    setOpen(false);
  };

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-label="Edit scope"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen(v => !v)}
        className={cn(
          'flex items-center gap-1 px-2 py-1 rounded text-sm',
          'text-text-subtle hover:text-text hover:bg-surface-raised transition-colors',
          'border border-transparent hover:border-border'
        )}
      >
        <Pencil className="w-3.5 h-3.5" />
        <span>Edit</span>
        <ChevronDown className={cn('w-3 h-3 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div
          className={cn(
            'absolute right-0 top-full mt-1 z-50 w-52',
            'bg-surface border border-border rounded-md shadow-lg p-2'
          )}
        >
          {renaming ? (
            <div className="flex items-center gap-1.5">
              <input
                type="text"
                value={newName}
                onChange={e => setNewName(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') handleRename();
                  if (e.key === 'Escape') { setRenaming(false); setNewName(scope.display_name); }
                }}
                autoFocus
                className={cn(
                  'flex-1 text-sm px-2 py-1 rounded border border-border bg-surface',
                  'focus:outline-none focus:ring-1 focus:ring-primary text-text'
                )}
              />
              <button
                type="button"
                onClick={handleRename}
                title="Confirm rename"
                className="p-1 rounded hover:bg-surface-raised text-primary"
              >
                <Check className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setRenaming(true)}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm text-text hover:bg-surface-raised transition-colors text-left"
            >
              <Pencil className="w-3.5 h-3.5 text-text-subtle" />
              Rename
            </button>
          )}

          <button
            type="button"
            onClick={handleDelete}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm text-error hover:bg-error/10 transition-colors text-left mt-0.5"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

// ── FolderTreePanel ──────────────────────────────────────────────────────────

export interface FolderTreePanelProps {
  data: TreeNode[];
  /** Paths included in the RAG index */
  includedPaths?: Set<string>;
  /** Scope orchestrator status (Phase 24) */
  scopeStatus?: ScopeStatus;
  /** Called when user toggles inclusion of paths (array for bulk operations) */
  onToggleInclude?: (paths: string[], action: 'add' | 'remove') => void;
  /** Per-path weight overrides (0.0–2.0, default 1.0). Folder weights propagate to children. */
  pathWeights?: Record<string, number>;
  /** Called when user changes weight. null removes the override (inherits parent weight). */
  onWeightChange?: (path: string, weight: number | null) => void;
  /** Paths excluded from trace graph (and knowledge) */
  excludedPaths?: Set<string>;
  /** Called when user toggles trace exclusion */
  onToggleExclude?: (paths: string[], action: 'add' | 'remove') => void;
  /** Always-ignored glob patterns (rendered as strikethrough, non-interactive) */
  alwaysIgnoredPatterns?: string[];
  /** Called when a depth-truncated folder is expanded — returns children to merge into the tree */
  onLoadChildren?: (path: string) => Promise<TreeNode[]>;
  title?: string;
  className?: string;
  bare?: boolean;

  // Phase 120 — Named Scopes
  /** List of all scopes for the active project. When omitted, header falls back to the legacy single-scope appearance. */
  scopes?: ScopeSummary[];
  /** ID of the currently active scope (e.g. "global" or a uuid). */
  activeScopeId?: string;
  /** Called when user selects a different scope from the dropdown. */
  onSetActiveScope?: (id: string) => void;
  /** Called when user creates a new scope. Returns the created ScopeRecord or null on error. */
  onCreateScope?: (display_name: string) => Promise<ScopeRecord | null>;
  /** Called when user renames the active scope. */
  onRenameScope?: (id: string, display_name: string) => Promise<void>;
  /** Called when user deletes the active scope. */
  onDeleteScope?: (id: string) => Promise<void>;
}

export function FolderTreePanel({
  data,
  includedPaths,
  scopeStatus,
  onToggleInclude,
  pathWeights,
  onWeightChange,
  excludedPaths,
  onToggleExclude,
  alwaysIgnoredPatterns,
  onLoadChildren,
  title = 'Scope',
  className,
  bare = false,
  // Phase 120 — Named Scopes
  scopes,
  activeScopeId,
  onSetActiveScope,
  onCreateScope,
  onRenameScope,
  onDeleteScope,
}: FolderTreePanelProps) {
  const [showCreate, setShowCreate] = useState(false);

  const Container = bare ? 'div' : Card;
  const includedCount = includedPaths?.size ?? 0;
  const excludedCount = excludedPaths?.size ?? 0;

  // Whether scopes feature is active (Task 18 will always pass scopes)
  const scopesEnabled = !!scopes && scopes.length > 0;
  const isGlobalScope = !activeScopeId || activeScopeId === 'global';
  const activeScope = scopesEnabled ? scopes!.find(s => s.id === activeScopeId) : undefined;
  const isEmpty = scopesEnabled && !isGlobalScope && (activeScope?.path_count ?? 0) === 0 && includedCount === 0;

  // Determine status badge (legacy single-scope path)
  let statusBadge = null;
  if (scopeStatus) {
    if (scopeStatus.state === 'building') {
      statusBadge = (
        <Badge icon={RefreshCw} className="animate-pulse" size="xs" color="blue">
          Building...
        </Badge>
      );
    } else if (scopeStatus.state === 'debouncing') {
      statusBadge = (
        <Badge icon={Clock} size="xs" color="yellow">
          Pending...
        </Badge>
      );
    } else if (scopeStatus.is_stale) {
      statusBadge = (
        <Badge icon={AlertCircle} size="xs" color="orange">
          Stale
        </Badge>
      );
    } else if (scopeStatus.error) {
       statusBadge = (
        <Badge icon={AlertCircle} size="xs" color="red">
          Error
        </Badge>
      );
    }
  }

  return (
    <Container className={cn(!bare && 'border border-border bg-surface shadow-sm', 'h-full min-h-0 flex flex-col', className)}>
      {!bare && (
        scopesEnabled ? (
          /* ── Phase 120: scope-aware header ── */
          <div className="mb-3 shrink-0">
            <div className="flex items-center gap-2">
              <ScopeDropdown
                scopes={scopes!}
                activeScopeId={activeScopeId ?? 'global'}
                onSelect={onSetActiveScope}
              />
              <button
                type="button"
                aria-label="Add scope"
                onClick={() => setShowCreate(v => !v)}
                className={cn(
                  'flex items-center justify-center w-7 h-7 rounded text-sm font-bold',
                  'bg-surface-raised border border-border hover:border-primary/50 transition-colors',
                  'text-text-subtle hover:text-primary'
                )}
              >
                +
              </button>
              {!isGlobalScope && activeScope && (
                <div className="ml-auto">
                  <ScopeEditPopover
                    scope={activeScope}
                    onRename={onRenameScope}
                    onDelete={onDeleteScope}
                  />
                </div>
              )}
            </div>

            {showCreate && (
              <div className="mt-2">
                <ScopeCreateInline
                  onCancel={() => setShowCreate(false)}
                  onSubmit={async (name) => {
                    if (!onCreateScope) return;
                    await onCreateScope(name);
                    setShowCreate(false);
                  }}
                />
              </div>
            )}
          </div>
        ) : (
          /* ── Legacy header (no scopes passed) ── */
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
        )
      )}

      {/* Empty-state banner for freshly-created named scopes */}
      {isEmpty && (
        <p className="px-2 py-3 text-sm text-text-subtle italic">
          This scope is empty. Click files and folders to add them.
        </p>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto -mx-2 custom-scrollbar">
        <div className="px-2">
          <FolderTree
            data={data}
            compact
            includedPaths={includedPaths}
            onToggleInclude={onToggleInclude}
            pathWeights={pathWeights}
            onWeightChange={onWeightChange}
            excludedPaths={excludedPaths}
            onToggleExclude={onToggleExclude}
            alwaysIgnoredPatterns={alwaysIgnoredPatterns}
            onLoadChildren={onLoadChildren}
            scopeReadOnlyExclude={scopesEnabled && !isGlobalScope}
            scopeReadOnlyWeights={scopesEnabled && !isGlobalScope}
          />
        </div>
      </div>
    </Container>
  );
}
