import type { ArchSummaryResponse } from '../../types/architecture';

export interface ArchitectureDiagramPanelProps {
  summary: ArchSummaryResponse | null;
  loading: boolean;
  error: string | null;
  onOpenDetail: () => void;
}

export function ArchitectureDiagramPanel({
  summary,
  loading,
  error,
  onOpenDetail,
}: ArchitectureDiagramPanelProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
        Loading architecture...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-sm">
        <span className="text-red-400">Failed to load architecture</span>
        <span className="text-zinc-500 text-xs">{error}</span>
      </div>
    );
  }

  if (!summary || !summary.exists) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-sm text-zinc-500">
        <span>No architecture data yet</span>
        <span className="text-xs">Run the pipeline to generate module synthesis</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-zinc-100">{summary.module_count}</div>
          <div className="text-xs text-zinc-500">Modules</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-zinc-100">{summary.file_count}</div>
          <div className="text-xs text-zinc-500">Files</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-zinc-100">{summary.note_count}</div>
          <div className="text-xs text-zinc-500">Notes</div>
        </div>
      </div>

      <button
        onClick={onOpenDetail}
        className="mt-auto w-full py-2 px-4 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
      >
        Open Architecture Diagram
      </button>
    </div>
  );
}
