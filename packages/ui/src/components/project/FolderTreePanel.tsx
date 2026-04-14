import { Card, Flex, Title, Badge } from '@tremor/react';
import { RefreshCw, AlertCircle, Clock } from 'lucide-react';
import { cn } from '../../lib/utils';
import { FolderTree } from './FolderTree';
import type { TreeNode } from './FolderTree';
import type { ScopeStatus } from '../../types';

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
}: FolderTreePanelProps) {
  const Container = bare ? 'div' : Card;
  const includedCount = includedPaths?.size ?? 0;
  const excludedCount = excludedPaths?.size ?? 0;

  // Determine status badge
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
