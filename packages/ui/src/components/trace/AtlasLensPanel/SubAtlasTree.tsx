import { useState } from 'react';
import { ChevronDown, ChevronRight, FolderTree } from 'lucide-react';
import { StatusBadge } from '../../status/StatusBadge';
import { cn } from '../../../lib/utils';
import type { AtlasSegmentStatus } from '../../../types';

export interface SubAtlasTreeProps {
  segments: AtlasSegmentStatus[] | undefined;
  className?: string;
  /** When provided, renders a segment's stored preview in an expandable panel.
   *  Today the API does not return per-segment content on GET /atlas — the UI
   *  asks via a follow-up fetch. This prop lets callers inject that lookup. */
  getSegmentContent?: (segmentId: string) => string | undefined;
}

/**
 * Renders the list of segmented sub-atlases. Each row shows segment name,
 * dir path, file/char counts, and a freshness badge. Clicking the row
 * expands it to show whatever preview the caller provides.
 */
export function SubAtlasTree({
  segments,
  className,
  getSegmentContent,
}: SubAtlasTreeProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  if (!segments || segments.length === 0) {
    return (
      <div className={cn('text-xs text-text-muted italic px-2 py-3', className)}>
        No sub-atlases yet — this project is single-segment or the atlas
        has not been regenerated since segmentation landed.
      </div>
    );
  }

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className={cn('space-y-1', className)}>
      <div className="flex items-center gap-1.5 text-xs font-medium text-text-muted uppercase tracking-wide px-1">
        <FolderTree className="w-3 h-3" />
        Sub-Atlases ({segments.length})
      </div>
      <ul className="space-y-0.5">
        {segments.map((seg) => {
          const isOpen = expanded.has(seg.segment_id);
          const preview = getSegmentContent?.(seg.segment_id);
          return (
            <li
              key={seg.segment_id}
              className="rounded-md hover:bg-surface-raised/50 transition-colors"
            >
              <button
                type="button"
                onClick={() => toggle(seg.segment_id)}
                className="w-full flex items-center gap-2 text-left px-2 py-1.5 text-sm"
              >
                {isOpen ? (
                  <ChevronDown className="w-3.5 h-3.5 shrink-0 text-text-muted" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5 shrink-0 text-text-muted" />
                )}
                <span className="font-medium truncate">{seg.segment_name}</span>
                <span className="text-xs text-text-muted truncate">· {seg.dir_path}</span>
                <span className="ml-auto flex items-center gap-2 text-xs text-text-muted shrink-0">
                  <span className="tabular-nums">{seg.file_count.toLocaleString()} files</span>
                  <span className="tabular-nums">{(seg.char_count / 1000).toFixed(1)}K</span>
                  {seg.stale
                    ? <StatusBadge status="stale" />
                    : <StatusBadge status="fresh" />}
                </span>
              </button>
              {isOpen && (
                <div className="px-4 pb-3">
                  {preview ? (
                    <pre className="text-xs bg-surface-raised border border-border rounded p-2 whitespace-pre-wrap font-mono max-h-40 overflow-auto custom-scrollbar">
                      {preview}
                    </pre>
                  ) : (
                    <p className="text-xs text-text-muted italic">
                      Preview not loaded. The panel requests segment contents lazily.
                    </p>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
