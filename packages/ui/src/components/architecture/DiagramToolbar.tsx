import { memo } from 'react';
import type { ArchStats } from '../../types/architecture';

export interface DiagramToolbarProps {
  onAutoLayout: () => void;
  onGoBack: (() => void) | null;
  stats: ArchStats;
}

function DiagramToolbarInner({ onAutoLayout, onGoBack, stats }: DiagramToolbarProps) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-800 bg-zinc-950">
      <button
        onClick={onAutoLayout}
        className="text-xs px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
      >
        Auto-layout
      </button>
      {onGoBack && (
        <button
          onClick={onGoBack}
          className="text-xs px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
        >
          {'← Back'}
        </button>
      )}
      <div className="ml-auto text-xs text-zinc-500">
        {stats.total_modules > 0 && `${stats.total_modules} modules · `}
        {stats.total_files > 0 && `${stats.total_files} files · `}
        {stats.total_edges} edges
      </div>
    </div>
  );
}

export const DiagramToolbar = memo(DiagramToolbarInner);
