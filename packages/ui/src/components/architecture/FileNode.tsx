import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { FileNodeData } from '../../types/architecture';
import { IssueBadge } from './IssueBadge';

const LANG_ICONS: Record<string, string> = {
  python: '🐍', typescript: '📘', tsx: '📘', javascript: '📒',
  rust: '🦀', go: '🐹', java: '☕', ruby: '💎',
};

function FileNodeInner({ data, selected }: NodeProps & { data: FileNodeData }) {
  const icon = LANG_ICONS[data.language] ?? '📄';

  return (
    <div
      className={`
        relative rounded-full border bg-zinc-900 shadow-sm px-4 py-2 min-w-[140px] max-w-[220px]
        transition-all duration-150
        ${selected ? 'border-blue-400 ring-2 ring-blue-400/50' : 'border-zinc-700'}
        ${data.isHub ? 'border-purple-500 shadow-purple-500/20' : ''}
      `}
    >
      <IssueBadge issueCount={data.issueCount} acrCount={data.acrCount} maxPriority={data.maxPriority} />
      <Handle type="target" position={Position.Top} className="!bg-zinc-500 !w-2 !h-2" />

      <div className="flex items-center gap-2">
        <span className="text-xs">{icon}</span>
        <span className="text-sm text-zinc-200 truncate">{data.label}</span>
      </div>

      <div className="flex items-center gap-2 text-[10px] text-zinc-500 mt-1">
        {data.lineCount > 0 && <span>{data.lineCount} lines</span>}
        {data.isHub && <span className="text-purple-400">{'★'} hub</span>}
        {data.noteCount > 0 && <span>{'💬'} {data.noteCount}</span>}
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-zinc-500 !w-2 !h-2" />
    </div>
  );
}

export const FileNode = memo(FileNodeInner);
