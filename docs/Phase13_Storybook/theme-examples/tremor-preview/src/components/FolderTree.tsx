import { useState } from 'react';
import { Text } from '@tremor/react';
import { ChevronRight, ChevronDown, Folder, File } from 'lucide-react';

type FileStatus = 'indexed' | 'pending' | 'ignored' | 'error';

interface TreeNode {
  name: string;
  type: 'file' | 'folder';
  status?: FileStatus;
  children?: TreeNode[];
  chunks?: number;
}

const statusColors: Record<FileStatus, string> = {
  indexed: 'bg-success',
  pending: 'bg-warning',
  ignored: 'bg-text-subtle/30',
  error: 'bg-error',
};

const statusLabels: Record<FileStatus, string> = {
  indexed: 'Indexed',
  pending: 'Pending',
  ignored: 'Ignored',
  error: 'Error',
};

interface FolderTreeProps {
  data: TreeNode[];
  compact?: boolean;
}

function TreeItem({ node, depth = 0 }: { node: TreeNode; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = node.children && node.children.length > 0;
  const isFolder = node.type === 'folder';

  return (
    <div>
      <div
        className={`group flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-surface-raised transition-colors cursor-pointer ${
          depth > 0 ? 'ml-4' : ''
        }`}
        onClick={() => isFolder && setExpanded(!expanded)}
      >
        {isFolder ? (
          <span className="text-text-subtle">
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </span>
        ) : (
          <span className="w-4" />
        )}
        
        <span className={`text-sm flex items-center gap-2 ${isFolder ? 'text-text font-medium' : 'text-text-muted font-mono'}`}>
          {isFolder ? <Folder className="w-4 h-4 text-primary" /> : <File className="w-4 h-4" />} {node.name}
        </span>

        {node.status && (
          <span
            className={`ml-auto flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full ${statusColors[node.status]}/20`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${statusColors[node.status]}`} />
            <span className="text-text-subtle">{statusLabels[node.status]}</span>
          </span>
        )}

        {node.chunks !== undefined && (
          <span className="text-xs text-text-subtle opacity-0 group-hover:opacity-100 transition-opacity">
            {node.chunks} chunks
          </span>
        )}
      </div>

      {hasChildren && expanded && (
        <div className="border-l border-border-subtle ml-4">
          {node.children!.map((child, i) => (
            <TreeItem key={`${child.name}-${i}`} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function FolderTree({ data, compact }: FolderTreeProps) {
  return (
    <div className={`${compact ? 'text-sm' : ''}`}>
      {data.map((node, i) => (
        <TreeItem key={`${node.name}-${i}`} node={node} />
      ))}
    </div>
  );
}

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
              { name: 'embedding.py', type: 'file', status: 'pending', chunks: 0 },
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
      { name: 'ROADMAP.md', type: 'file', status: 'pending', chunks: 0 },
    ],
  },
  {
    name: 'tests',
    type: 'folder',
    children: [
      { name: 'test_registry.py', type: 'file', status: 'ignored' },
      { name: 'test_search.py', type: 'file', status: 'ignored' },
    ],
  },
];
