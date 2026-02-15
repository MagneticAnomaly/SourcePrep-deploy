import { useState, useCallback, useRef, useEffect } from 'react';
import { FolderTree as FolderTreeIcon, RefreshCw, AlertCircle, Clock } from 'lucide-react';
import { cn } from '../../lib/utils';
import { FolderTree } from './FolderTree';
import type { TreeNode } from './FolderTree';
import { FilePreviewPane } from './FilePreviewPane';
import { Badge } from '@tremor/react';
import type { ScopeStatus } from '../../types';

export interface FileExplorerDetailProps {
  treeData: TreeNode[];
  pinnedPaths: Set<string>;
  onPinFile: (path: string) => void;
  onUnpinFile: (path: string) => void;
  /** Async loader for file content. If omitted, mock content is shown. */
  onLoadFileContent?: (path: string) => Promise<string>;
  includedPaths?: Set<string>;
  /** Scope orchestrator status (Phase 24) */
  scopeStatus?: ScopeStatus;
  onToggleInclude?: (paths: string[], action: 'add' | 'remove') => void;
  /** Per-path weight overrides (0.0–2.0, default 1.0). */
  pathWeights?: Record<string, number>;
  /** Called when user changes weight. null removes the override. */
  onWeightChange?: (path: string, weight: number | null) => void;
  /** Called when a depth-truncated folder is expanded — returns children to merge into the tree */
  onLoadChildren?: (path: string) => Promise<TreeNode[]>;
  /** Initial width of the tree pane in pixels (default 384 = w-96) */
  initialTreeWidth?: number;
  className?: string;
}

export function FileExplorerDetail({
  treeData,
  pinnedPaths,
  onPinFile,
  onUnpinFile,
  onLoadFileContent,
  includedPaths,
  scopeStatus,
  onToggleInclude,
  pathWeights,
  onWeightChange,
  onLoadChildren,
  initialTreeWidth = 768,
  className,
}: FileExplorerDetailProps) {
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);

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

  // Resizable tree pane width
  const [treeWidth, setTreeWidth] = useState(initialTreeWidth);
  const containerRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!draggingRef.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const newWidth = Math.max(200, Math.min(e.clientX - rect.left, rect.width - 200));
      setTreeWidth(newWidth);
    };

    const handleMouseUp = () => {
      if (draggingRef.current) {
        draggingRef.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  const handleDividerMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    draggingRef.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  const handleNodeClick = useCallback(
    async (node: TreeNode, path: string) => {
      if (node.type !== 'file') return;

      setSelectedPath(path);
      setFileContent(null);
      setFileError(null);

      if (onLoadFileContent) {
        setFileLoading(true);
        try {
          const content = await onLoadFileContent(path);
          setFileContent(content);
        } catch (e) {
          setFileError(e instanceof Error ? e.message : 'Failed to load file');
        } finally {
          setFileLoading(false);
        }
      } else {
        setFileContent(
          `// Content of ${path}\n// (mock data — connect onLoadFileContent for real content)\n`
        );
      }
    },
    [onLoadFileContent]
  );

  return (
    <div ref={containerRef} className={cn('h-full flex flex-col md:flex-row', className)}>
      {/* Tree pane */}
      <div
        className="shrink-0 border-b md:border-b-0 overflow-y-auto custom-scrollbar w-full md:w-auto"
        style={{ width: undefined, minWidth: 0 }}
      >
        <div className="hidden md:block h-full overflow-y-auto custom-scrollbar" style={{ width: treeWidth }}>
          <div className="p-4">
            <h3 className="text-sm font-semibold text-text mb-3 flex items-center gap-2">
              <FolderTreeIcon className="w-4 h-4" />
              Knowledge Scope
              {statusBadge}
            </h3>
            <FolderTree
              data={treeData}
              compact
              includedPaths={includedPaths}
              onToggleInclude={onToggleInclude}
              onNodeClick={handleNodeClick}
              pathWeights={pathWeights}
              onWeightChange={onWeightChange}
              onLoadChildren={onLoadChildren}
            />
          </div>
        </div>
        {/* Mobile: full width, no resize */}
        <div className="md:hidden p-4">
          <h3 className="text-sm font-semibold text-text mb-3 flex items-center gap-2">
            <FolderTreeIcon className="w-4 h-4" />
            Knowledge Scope
            {statusBadge}
          </h3>
          <FolderTree
            data={treeData}
            compact
            includedPaths={includedPaths}
            onToggleInclude={onToggleInclude}
            onNodeClick={handleNodeClick}
            pathWeights={pathWeights}
            onWeightChange={onWeightChange}
            onLoadChildren={onLoadChildren}
          />
        </div>
      </div>

      {/* Draggable divider */}
      <div
        className="hidden md:flex items-center justify-center w-1.5 cursor-col-resize group hover:bg-primary/10 active:bg-primary/20 transition-colors shrink-0"
        onMouseDown={handleDividerMouseDown}
        title="Drag to resize"
      >
        <div className="w-px h-full bg-border group-hover:bg-primary/40 group-active:bg-primary/60 transition-colors" />
      </div>

      {/* Preview pane */}
      <div className="flex-1 min-w-0 min-h-0">
        <FilePreviewPane
          path={selectedPath}
          content={fileContent}
          loading={fileLoading}
          error={fileError}
          isPinned={selectedPath ? pinnedPaths.has(selectedPath) : false}
          onPin={onPinFile}
          onUnpin={onUnpinFile}
        />
      </div>
    </div>
  );
}
