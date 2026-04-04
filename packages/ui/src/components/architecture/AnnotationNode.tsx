import { memo, useState, useCallback } from 'react';
import type { NodeProps } from '@xyflow/react';
import type { AnnotationNodeData } from '../../types/architecture';

const COLOR_MAP: Record<string, string> = {
  yellow: 'bg-yellow-900/40 border-yellow-700',
  blue: 'bg-blue-900/40 border-blue-700',
  green: 'bg-green-900/40 border-green-700',
  red: 'bg-red-900/40 border-red-700',
};

function AnnotationNodeInner({ data }: NodeProps & { data: AnnotationNodeData }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(data.content);
  const colorClass = COLOR_MAP[data.color] ?? COLOR_MAP.yellow;

  const typeLabel = data.noteType === 'adr' ? '📌 ADR' :
    data.noteType === 'agent_note' ? '🤖 Agent' : '💬 Note';

  const handleSave = useCallback(() => {
    setEditing(false);
    data.onEdit?.(data.noteId, draft);
  }, [data, draft]);

  return (
    <div className={`rounded-lg border ${colorClass} px-3 py-2 min-w-[160px] max-w-[240px] shadow-sm`}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-zinc-300">{typeLabel}</span>
        <div className="flex gap-1">
          {data.onEdit && (
            <button
              onClick={() => setEditing(!editing)}
              className="text-[10px] text-zinc-500 hover:text-zinc-300 nodrag"
            >
              {editing ? 'cancel' : 'edit'}
            </button>
          )}
          {data.onDelete && (
            <button
              onClick={() => data.onDelete?.(data.noteId)}
              className="text-[10px] text-zinc-500 hover:text-red-400 nodrag"
            >
              {'×'}
            </button>
          )}
        </div>
      </div>

      {editing ? (
        <div className="nodrag">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && e.metaKey) handleSave(); }}
            className="w-full bg-transparent border border-zinc-600 rounded text-xs text-zinc-200 p-1 resize-none"
            rows={3}
            autoFocus
          />
          <button
            onClick={handleSave}
            className="mt-1 text-[10px] px-2 py-0.5 bg-zinc-700 rounded text-zinc-300 hover:bg-zinc-600"
          >
            Save
          </button>
        </div>
      ) : (
        <div className="text-xs text-zinc-300 whitespace-pre-wrap">{data.content}</div>
      )}

      <div className="text-[10px] text-zinc-500 mt-1">— {data.author}</div>
    </div>
  );
}

export const AnnotationNode = memo(AnnotationNodeInner);
