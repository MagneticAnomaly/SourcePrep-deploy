import { useState } from 'react';
import { Badge } from '@tremor/react';
import { ChevronDown, ChevronUp, Clock, FileText, Cpu } from 'lucide-react';
import { cn } from '../../lib/utils';
import type { AtlasStatus } from '../../types';

export interface AtlasStatusCardProps {
  atlas: AtlasStatus | null;
  className?: string;
}

/**
 * AtlasStatusCard - Displays Codebase Atlas status and content preview.
 *
 * Shows:
 * - Existence / freshness / staleness badge
 * - Character count, module count, file count
 * - Generated timestamp and model
 * - Collapsible content preview
 *
 * Atlas regeneration is handled automatically by the enrichment pipeline.
 */
export function AtlasStatusCard({
  atlas,
  className,
}: AtlasStatusCardProps) {
  const [expanded, setExpanded] = useState(false);

  const exists = atlas?.exists ?? false;
  const stale = atlas?.stale ?? false;

  return (
    <div className={cn('space-y-4', className)}>
      {/* Status badge */}
      <div className="flex items-center gap-1.5">
        {!exists && (
          <Badge color="gray" size="xs">Not Generated</Badge>
        )}
        {exists && !stale && (
          <Badge color="green" size="xs">Fresh</Badge>
        )}
        {exists && stale && (
          <Badge color="yellow" size="xs">Stale — rebuild to update</Badge>
        )}
      </div>

      {/* Stats row */}
      {exists && atlas && (
        <div className="grid grid-cols-3 gap-3">
          <div>
            <p className="text-lg font-bold">{atlas.char_count?.toLocaleString() ?? 0}</p>
            <p className="text-xs text-gray-500">chars</p>
          </div>
          <div>
            <p className="text-lg font-bold">{atlas.module_count ?? 0}</p>
            <p className="text-xs text-gray-500">modules</p>
          </div>
          <div>
            <p className="text-lg font-bold">{atlas.file_count?.toLocaleString() ?? 0}</p>
            <p className="text-xs text-gray-500">files</p>
          </div>
        </div>
      )}

      {/* Metadata */}
      {exists && atlas && (
        <div className="space-y-1">
          {atlas.generated_at && (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Clock className="w-3.5 h-3.5" />
              <span>Generated: {new Date(atlas.generated_at).toLocaleString()}</span>
            </div>
          )}
          {atlas.model && atlas.model !== 'structural' && (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Cpu className="w-3.5 h-3.5" />
              <span>Model: {atlas.model}</span>
            </div>
          )}
        </div>
      )}

      {/* Collapsible content preview */}
      {exists && atlas?.content && (
        <div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>{expanded ? 'Hide' : 'Preview'} Atlas Content</span>
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          {expanded && (
            <div className="mt-2 bg-surface-raised border border-border rounded-lg overflow-hidden">
              <pre className="p-3 text-xs whitespace-pre-wrap font-mono text-text overflow-y-auto max-h-48 custom-scrollbar">
                {atlas.content}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
