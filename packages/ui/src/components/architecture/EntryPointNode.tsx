import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { EntryPointNodeData } from '../../types/architecture';

const TYPE_ICONS: Record<string, string> = {
  api_route: '🌐',
  cli_command: '⌨️',
  main: '▶️',
  webhook: '🔗',
};

function EntryPointNodeInner({ data, selected }: NodeProps & { data: EntryPointNodeData }) {
  const icon = TYPE_ICONS[data.entryType] ?? '◇';

  return (
    <div
      className={`
        relative w-[140px] h-[80px] flex items-center justify-center
        transition-all duration-150
        ${selected ? 'drop-shadow-[0_0_8px_rgba(59,130,246,0.5)]' : ''}
      `}
    >
      <Handle type="target" position={Position.Top} className="!bg-zinc-500 !w-2 !h-2" />

      {/* Diamond shape via rotated square */}
      <div
        className={`
          absolute inset-[10px] rotate-45 rounded-[4px]
          border-2 bg-zinc-900 shadow-md
          ${selected ? 'border-blue-400' : 'border-emerald-500'}
        `}
        style={{
          background: 'linear-gradient(135deg, #18181b 0%, #1e293b 100%)',
        }}
      />

      {/* Content (not rotated) */}
      <div className="relative z-10 flex flex-col items-center text-center px-2">
        <span className="text-xs">{icon}</span>
        <span className="text-[11px] font-medium text-zinc-200 truncate max-w-[100px]">
          {data.label}
        </span>
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-zinc-500 !w-2 !h-2" />
    </div>
  );
}

export const EntryPointNode = memo(EntryPointNodeInner);
