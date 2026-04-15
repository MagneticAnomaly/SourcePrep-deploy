import { Badge } from '@tremor/react';
import { Clock, Cpu } from 'lucide-react';
import { cn } from '../../../lib/utils';
import type { AtlasStatus } from '../../../types';
import { StageRegenerateButton } from '../../pipeline/StageRegenerateButton';

export interface StatusStripProps {
  atlas: AtlasStatus | null;
  regenerating?: boolean;
  onRegenerate?: () => void;
  className?: string;
}

/**
 * Compact header strip for the AtlasLensPanel:
 *   [Fresh | Stale | Not Generated]  547 files · 8 modules · 3.1K chars · structural
 *   Generated 2h ago · Model: structural        [Regenerate]
 */
export function StatusStrip({
  atlas,
  regenerating,
  onRegenerate,
  className,
}: StatusStripProps) {
  const exists = atlas?.exists ?? false;
  const stale = atlas?.stale ?? false;
  const mode = atlas?.mode ?? 'structural';

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          {!exists && <Badge color="gray" size="xs">Not Generated</Badge>}
          {exists && !stale && <Badge color="green" size="xs">Fresh</Badge>}
          {exists && stale && <Badge color="yellow" size="xs">Stale</Badge>}
          {exists && (
            <Badge color={mode === 'llm' ? 'indigo' : 'gray'} size="xs">
              {mode}
            </Badge>
          )}
        </div>
        {onRegenerate && (
          <StageRegenerateButton
            onRegenerate={onRegenerate}
            regenerating={regenerating}
          />
        )}
      </div>

      {exists && atlas && (
        <div className="flex items-baseline gap-4 text-sm flex-wrap">
          <span>
            <span className="font-semibold tabular-nums">{atlas.file_count?.toLocaleString() ?? 0}</span>
            <span className="text-text-muted ml-1">files</span>
          </span>
          <span>
            <span className="font-semibold tabular-nums">{atlas.module_count ?? 0}</span>
            <span className="text-text-muted ml-1">modules</span>
          </span>
          <span>
            <span className="font-semibold tabular-nums">{((atlas.char_count ?? 0) / 1000).toFixed(1)}K</span>
            <span className="text-text-muted ml-1">chars</span>
          </span>
          {atlas.segmented && (
            <span className="text-text-muted">·</span>
          )}
          {atlas.segmented && (
            <span>
              <span className="font-semibold tabular-nums">{atlas.segments?.length ?? 0}</span>
              <span className="text-text-muted ml-1">segments</span>
            </span>
          )}
        </div>
      )}

      {exists && atlas && (
        <div className="flex items-center gap-4 text-xs text-text-muted flex-wrap">
          {atlas.generated_at && (
            <span className="inline-flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {new Date(atlas.generated_at).toLocaleString()}
            </span>
          )}
          {atlas.model && (
            <span className="inline-flex items-center gap-1">
              <Cpu className="w-3 h-3" />
              {atlas.model}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
