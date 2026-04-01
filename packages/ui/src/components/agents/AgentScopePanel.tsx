import { useState, useEffect, useCallback } from 'react';
import { Card, Flex, Title, Badge } from '@tremor/react';
import { Users, Plus, Trash2, ChevronDown, Sparkles, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from '../primitives/Button';
import { FolderTree } from '../project/FolderTree';
import type { TreeNode } from '../project/FolderTree';

export interface AutoPopulateResult {
  role: string;
  resolved_as: string;
  recommended_paths: string[];
  scored: Array<{ path: string; score: number; layer: string; tags: string[] }>;
  count: number;
  total_scored: number;
  applied: boolean;
  elapsed_ms: number;
}

export interface AgentScopePanelProps {
  /** The project ID currently selected */
  projectId: string | null;
  /** Full file tree data (same as global Knowledge Sources) */
  data: TreeNode[];
  /** Fetch scopes from backend: GET /projects/{id}/agent-scope */
  onFetchScopes: (projectId: string) => Promise<{ roles: string[]; scopes: Record<string, string[]> }>;
  /** Update agent scope: POST /projects/{id}/agent-scope/{role}/set */
  onSetScope: (projectId: string, role: string, paths: string[]) => Promise<void>;
  /** Add paths to agent scope: POST /projects/{id}/agent-scope/{role}/add */
  onAddPaths: (projectId: string, role: string, paths: string[]) => Promise<void>;
  /** Remove paths from agent scope: POST /projects/{id}/agent-scope/{role}/remove */
  onRemovePaths: (projectId: string, role: string, paths: string[]) => Promise<void>;
  /** Delete an agent scope entirely: DELETE /projects/{id}/agent-scope/{role} */
  onDeleteScope: (projectId: string, role: string) => Promise<void>;
  /** Phase 67: Auto-populate scope via role projection engine */
  onAutoPopulate?: (projectId: string, role: string) => Promise<AutoPopulateResult>;
  /** Load lazy tree children (same callback as FolderTreePanel) */
  onLoadChildren?: (path: string) => Promise<TreeNode[]>;
  className?: string;
  bare?: boolean;
}

/** Default role presets — users can also type custom names */
const ROLE_PRESETS = [
  'CEO', 'CTO', 'VP Product', 'UX Designer', 'CMO',
  'QA Lead', 'DevOps', 'Data Engineer', 'Security Lead',
];

export function AgentScopePanel({
  projectId,
  data,
  onFetchScopes,
  onSetScope,
  onAddPaths,
  onRemovePaths,
  onDeleteScope,
  onAutoPopulate,
  onLoadChildren,
  className,
  bare = false,
}: AgentScopePanelProps) {
  const Container = bare ? 'div' : Card;

  // State
  const [roles, setRoles] = useState<string[]>([]);
  const [scopes, setScopes] = useState<Record<string, string[]>>({});
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [showAddRole, setShowAddRole] = useState(false);
  const [newRoleName, setNewRoleName] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);

  // Phase 67: Auto-populate state
  const [autoPopulating, setAutoPopulating] = useState(false);
  const [autoPopulateResult, setAutoPopulateResult] = useState<AutoPopulateResult | null>(null);

  // Derived state
  const selectedPaths = selectedRole ? new Set(scopes[selectedRole] || []) : new Set<string>();

  // Load scopes on mount or project change
  useEffect(() => {
    if (!projectId) return;
    onFetchScopes(projectId).then(({ roles: r, scopes: s }) => {
      setRoles(r);
      setScopes(s);
      // Auto-select first role if available
      if (r.length > 0 && !selectedRole) {
        setSelectedRole(r[0]);
      }
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // Clear auto-populate result when switching roles
  useEffect(() => {
    setAutoPopulateResult(null);
  }, [selectedRole]);

  // Handle toggling a path on/off for the current agent
  const handleToggleInclude = useCallback(
    (paths: string[], action: 'add' | 'remove') => {
      if (!projectId || !selectedRole) return;

      // Optimistic update
      setScopes(prev => {
        const current = new Set(prev[selectedRole] || []);
        for (const p of paths) {
          if (action === 'add') {
            current.add(p);
            // Remove descendants — parent covers them
            const prefix = p + '/';
            for (const existing of [...current]) {
              if (existing.startsWith(prefix) && existing !== p) {
                current.delete(existing);
              }
            }
          } else {
            current.delete(p);
            // Also remove descendants
            const prefix = p + '/';
            for (const existing of [...current]) {
              if (existing.startsWith(prefix)) {
                current.delete(existing);
              }
            }
          }
        }
        return { ...prev, [selectedRole]: [...current].sort() };
      });

      // Persist to backend
      if (action === 'add') {
        onAddPaths(projectId, selectedRole, paths).catch(() => {});
      } else {
        onRemovePaths(projectId, selectedRole, paths).catch(() => {});
      }
    },
    [projectId, selectedRole, onAddPaths, onRemovePaths],
  );

  // Add a new agent role
  const handleAddRole = useCallback(() => {
    const name = newRoleName.trim();
    if (!name || !projectId) return;
    if (roles.some(existing => existing.toLowerCase().replace(/[^a-z0-9]+/g, '_') === name.toLowerCase().replace(/[^a-z0-9]+/g, '_'))) return;

    setRoles(prev => [...prev, name]);
    setScopes(prev => ({ ...prev, [name]: [] }));
    setSelectedRole(name);
    setNewRoleName('');
    setShowAddRole(false);
    // Create the scope on backend (empty initially)
    onSetScope(projectId, name, []).catch(() => {});
  }, [newRoleName, projectId, roles, onSetScope]);

  // Delete scope for a role
  const handleDeleteRole = useCallback(() => {
    if (!projectId || !selectedRole) return;
    onDeleteScope(projectId, selectedRole).then(() => {
      setRoles(prev => prev.filter(r => r !== selectedRole));
      setScopes(prev => {
        const next = { ...prev };
        delete next[selectedRole!];
        return next;
      });
      setSelectedRole(null);
    }).catch(() => {});
  }, [projectId, selectedRole, onDeleteScope]);

  // Phase 67: Auto-populate handler
  const handleAutoPopulate = useCallback(async () => {
    if (!projectId || !selectedRole || !onAutoPopulate || autoPopulating) return;

    setAutoPopulating(true);
    setAutoPopulateResult(null);
    try {
      const result = await onAutoPopulate(projectId, selectedRole);
      setAutoPopulateResult(result);

      // Merge the recommended paths into local state
      if (result.recommended_paths.length > 0) {
        setScopes(prev => ({
          ...prev,
          [selectedRole]: [...result.recommended_paths].sort(),
        }));
      }
    } catch (err) {
      console.error('[AgentScope] Auto-populate failed:', err);
    } finally {
      setAutoPopulating(false);
    }
  }, [projectId, selectedRole, onAutoPopulate, autoPopulating]);

  const pathCount = selectedRole ? (scopes[selectedRole]?.length ?? 0) : 0;

  return (
    <Container className={cn(
      !bare && 'border border-border bg-surface shadow-sm',
      'h-full min-h-0 flex flex-col',
      className,
    )}>
      {/* Header */}
      <Flex justifyContent="between" alignItems="center" className="mb-3 gap-2 shrink-0">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-primary" />
          <Title className="text-text text-sm">Agent Knowledge Scopes</Title>
        </div>
        <div className="flex items-center gap-1.5">
          {pathCount > 0 && (
            <Badge color="neutral" size="xs">{pathCount} files</Badge>
          )}
          {/* Phase 67: Auto-populate button */}
          {selectedRole && onAutoPopulate && (
            <Button
              variant="ghost"
              size="icon-sm"
              className={cn(
                'shrink-0 transition-all',
                autoPopulating && 'animate-pulse',
                autoPopulateResult && 'text-emerald-400',
              )}
              onClick={handleAutoPopulate}
              disabled={autoPopulating}
              title={autoPopulating ? 'Analyzing codebase...' : `Auto-populate files for ${selectedRole}`}
            >
              {autoPopulating ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
            </Button>
          )}
        </div>
      </Flex>

      {/* Phase 67: Auto-populate result banner */}
      {autoPopulateResult && (
        <div className="mb-2 px-2.5 py-1.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-xs shrink-0">
          <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
            <Sparkles className="w-3 h-3" />
            Auto-populated {autoPopulateResult.count} files
            <span className="text-text-subtle font-normal ml-1">
              (resolved as {autoPopulateResult.resolved_as} • {autoPopulateResult.elapsed_ms}ms • {autoPopulateResult.total_scored} scored)
            </span>
          </div>
        </div>
      )}

      {/* Auto-populate loading overlay */}
      {autoPopulating && (
        <div className="mb-2 px-2.5 py-2 rounded-md bg-primary/5 border border-primary/20 text-xs shrink-0">
          <div className="flex items-center gap-2 text-primary">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span className="font-medium">Analyzing code graph for {selectedRole}...</span>
          </div>
          <div className="text-text-subtle mt-1 ml-5.5">
            Scoring files against role vectors, filtering by relevance threshold
          </div>
        </div>
      )}

      {/* Role selector */}
      <div className="flex items-center gap-2 mb-3 shrink-0">
        <div className="relative flex-1">
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className={cn(
              'w-full flex items-center justify-between gap-2 px-3 py-1.5 rounded-md',
              'text-sm bg-surface-raised border border-border hover:border-primary/50',
              'transition-colors cursor-pointer',
              selectedRole ? 'text-text font-medium' : 'text-text-subtle',
            )}
          >
            <span className="truncate">
              {selectedRole || 'Select an agent role...'}
            </span>
            <ChevronDown className={cn(
              'w-4 h-4 text-text-subtle transition-transform shrink-0',
              dropdownOpen && 'rotate-180',
            )} />
          </button>

          {dropdownOpen && (
            <div className="absolute z-20 top-full left-0 right-0 mt-1 bg-surface border border-border rounded-md shadow-lg max-h-48 overflow-y-auto">
              {roles.map(role => (
                <button
                  key={role}
                  onClick={() => {
                    setSelectedRole(role);
                    setDropdownOpen(false);
                  }}
                  className={cn(
                    'w-full text-left px-3 py-1.5 text-sm hover:bg-surface-raised transition-colors',
                    role === selectedRole && 'bg-primary/10 text-primary font-medium',
                  )}
                >
                  {role}
                  <span className="text-xs text-text-subtle ml-2">
                    ({scopes[role]?.length ?? 0} files)
                  </span>
                </button>
              ))}
              {roles.length === 0 && (
                <div className="px-3 py-2 text-sm text-text-subtle italic">
                  No agent scopes configured yet
                </div>
              )}
            </div>
          )}
        </div>

        {/* Add role button */}
        <Button
          variant="ghost"
          size="icon-sm"
          className="shrink-0"
          onClick={() => setShowAddRole(!showAddRole)}
          title="Add agent role"
        >
          <Plus className="w-4 h-4" />
        </Button>

        {/* Delete role button */}
        {selectedRole && (
          <Button
            variant="ghost"
            size="icon-sm"
            className="shrink-0 text-error hover:text-error"
            onClick={handleDeleteRole}
            title={`Delete ${selectedRole} scope`}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
        )}
      </div>

      {/* Add role input */}
      {showAddRole && (
        <div className="flex items-center gap-2 mb-3 shrink-0">
          <input
            type="text"
            value={newRoleName}
            onChange={e => setNewRoleName(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleAddRole(); if (e.key === 'Escape') setShowAddRole(false); }}
            placeholder="e.g. UX Designer"
            autoFocus
            className="flex-1 px-2 py-1 text-sm bg-surface border border-border rounded-md
                       focus:outline-none focus:ring-1 focus:ring-primary text-text"
          />
          <div className="flex flex-wrap gap-1 max-w-[50%]">
            {ROLE_PRESETS.filter(r => !roles.some(existing => existing.toLowerCase() === r.toLowerCase())).slice(0, 3).map(preset => (
              <button
                key={preset}
                onClick={() => { setNewRoleName(preset); }}
                className="text-[10px] px-1.5 py-0.5 rounded bg-surface-raised text-text-subtle
                           hover:bg-primary/10 hover:text-primary transition-colors"
              >
                {preset}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* File tree (only shown when a role is selected) */}
      {selectedRole ? (
        <div className="flex-1 min-h-0 overflow-y-auto -mx-2 custom-scrollbar">
          <div className="px-2">
            <FolderTree
              data={data}
              compact
              includedPaths={selectedPaths}
              onToggleInclude={handleToggleInclude}
              onLoadChildren={onLoadChildren}
            />
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-sm text-text-subtle">
          <div className="text-center space-y-2">
            <Users className="w-8 h-8 mx-auto opacity-30" />
            <p>Select or create an agent role to configure<br />their specific Knowledge Scope</p>
          </div>
        </div>
      )}
    </Container>
  );
}
