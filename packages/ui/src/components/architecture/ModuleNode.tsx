import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { ModuleNodeData } from '../../types/architecture';
import { IssueBadge } from './IssueBadge';

function ModuleNodeInner({ data, selected }: NodeProps & { data: ModuleNodeData }) {
  const statusColor = data.componentStatus === 'complete' ? 'border-blue-500' :
    data.componentStatus === 'deprecated' ? 'border-red-500' : 'border-amber-500';

  return (
    <div
      className={`
        relative rounded-lg border-2 bg-zinc-900 shadow-md px-4 py-3 min-w-[180px] max-w-[260px]
        transition-all duration-150
        ${statusColor}
        ${selected ? 'ring-2 ring-blue-400 shadow-blue-500/20' : ''}
        ${data.isHub ? 'shadow-purple-500/30 shadow-lg' : ''}
      `}
    >
      <IssueBadge issueCount={data.issueCount} acrCount={data.acrCount} maxPriority={data.maxPriority} />
      <Handle type="target" position={Position.Top} className="!bg-zinc-500 !w-2 !h-2" />

      {data.architectureLayer && data.architectureLayer !== 'unknown' && (
        <div className="text-[9px] uppercase tracking-wider text-zinc-500 mb-1 font-medium">
          {data.architectureLayer}
        </div>
      )}

      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs text-zinc-500">{'📦'}</span>
        <span className="text-sm font-semibold text-zinc-100 truncate">{data.label}</span>
      </div>

      <div className="text-xs text-zinc-400 truncate mb-2">
        {data.description}
      </div>

      <div className="flex items-center gap-2 text-xs text-zinc-500">
        <span>{data.fileCount} files</span>
        {data.noteCount > 0 && <span>{'💬'} {data.noteCount}</span>}
        {data.isHub && <span className="text-purple-400">{'★'} hub</span>}
      </div>

      {data.domainTags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {data.domainTags.slice(0, 3).map((tag) => (
            <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
              {tag}
            </span>
          ))}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-zinc-500 !w-2 !h-2" />
    </div>
  );
}

export const ModuleNode = memo(ModuleNodeInner);
