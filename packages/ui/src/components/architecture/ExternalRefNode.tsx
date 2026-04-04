import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { ExternalRefNodeData } from '../../types/architecture';

function ExternalRefNodeInner({ data }: NodeProps & { data: ExternalRefNodeData }) {
  return (
    <div className="rounded-lg border-2 border-dashed border-zinc-600 bg-zinc-900/50 px-4 py-3 min-w-[160px] max-w-[220px] opacity-70">
      <Handle type="target" position={Position.Top} className="!bg-zinc-600 !w-2 !h-2" />

      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs text-zinc-500">{'→'}</span>
        <span className="text-sm text-zinc-400 truncate">{data.label}</span>
      </div>
      <div className="text-xs text-zinc-500 italic">click to navigate</div>

      <Handle type="source" position={Position.Bottom} className="!bg-zinc-600 !w-2 !h-2" />
    </div>
  );
}

export const ExternalRefNode = memo(ExternalRefNodeInner);
