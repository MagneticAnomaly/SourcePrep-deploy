import { useState, useCallback, useRef, useEffect } from 'react';
import { FolderTree as FolderTreeIcon, EyeOff, RefreshCw, AlertCircle, Clock } from 'lucide-react';
import { cn } from '../../lib/utils';
import { FolderTree } from './FolderTree';
import type { TreeNode } from './FolderTree';
import { FilePreviewPane } from './FilePreviewPane';
import { Badge } from '@tremor/react';
import type { ScopeStatus } from '../../types';

export type FileExplorerTab = 'knowledge' | 'exclude';

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
  /** Paths excluded from trace (for exclude tab) */
  excludedPaths?: Set<string>;
  /** Toggle a path's exclusion from trace */
  onToggleExclude?: (paths: string[], action: 'add' | 'remove') => void;
  /** Which tab to show initially */
  initialTab?: FileExplorerTab;
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
  excludedPaths,
  onToggleExclude,
  initialTab = 'knowledge',
  initialTreeWidth = 768,
  className,
}: FileExplorerDetailProps) {
  const [activeTab, setActiveTab] = useState<FileExplorerTab>(initialTab);
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
            {/* Tabs for Knowledge Sources / Exclude from Trace */}
            {(onToggleExclude || excludedPaths) && (
              <div className="flex border-b border-border mb-3 -mx-2">
                <button
                  className={cn(
                    'flex-1 text-xs font-medium py-2 px-3 transition-colors border-b-2 flex items-center justify-center gap-1.5',
                    activeTab === 'knowledge'
                      ? 'border-primary text-primary'
                      : 'border-transparent text-text-muted hover:text-text'
                  )}
                  onClick={() => setActiveTab('knowledge')}
                >
                  <FolderTreeIcon className="w-3.5 h-3.5" />
                  Knowledge Sources
                </button>
                <button
                  className={cn(
                    'flex-1 text-xs font-medium py-2 px-3 transition-colors border-b-2 flex items-center justify-center gap-1.5',
                    activeTab === 'exclude'
                      ? 'border-error text-error'
                      : 'border-transparent text-text-muted hover:text-text'
                  )}
                  onClick={() => setActiveTab('exclude')}
                >
                  <EyeOff className="w-3.5 h-3.5" />
                  Exclude from Trace
                  {excludedPaths && excludedPaths.size > 0 && (
                    <span className="text-[10px] bg-error/15 text-error px-1.5 py-0.5 rounded-full font-mono">
                      {excludedPaths.size}
                    </span>
                  )}
                </button>
              </div>
            )}

            {!onToggleExclude && !excludedPaths && (
              <h3 className="text-sm font-semibold text-text mb-3 flex items-center gap-2">
                <FolderTreeIcon className="w-4 h-4" />
                Knowledge Scope
                {statusBadge}
              </h3>
            )}

            {activeTab === 'knowledge' && (
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
            )}

            {activeTab === 'exclude' && (
              <>
                <p className="text-xs text-text-muted mb-3">Select files and folders to exclude from the structural trace.</p>
                <FolderTree
                  data={treeData}
                  compact
                  mode="exclude"
                  includedPaths={excludedPaths}
                  onToggleInclude={onToggleExclude}
                  onNodeClick={handleNodeClick}
                  onLoadChildren={onLoadChildren}
                />
              </>
            )}
          </div>
        </div>
        {/* Mobile: full width, no resize */}
        <div className="md:hidden p-4">
          <h3 className="text-sm font-semibold text-text mb-3 flex items-center gap-2">
            <FolderTreeIcon className="w-4 h-4" />
            {activeTab === 'exclude' ? 'Exclude from Trace' : 'Knowledge Scope'}
            {activeTab === 'knowledge' && statusBadge}
          </h3>
          <FolderTree
            data={treeData}
            compact
            mode={activeTab === 'exclude' ? 'exclude' : 'include'}
            includedPaths={activeTab === 'exclude' ? excludedPaths : includedPaths}
            onToggleInclude={activeTab === 'exclude' ? onToggleExclude : onToggleInclude}
            onNodeClick={handleNodeClick}
            pathWeights={activeTab === 'exclude' ? undefined : pathWeights}
            onWeightChange={activeTab === 'exclude' ? undefined : onWeightChange}
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
