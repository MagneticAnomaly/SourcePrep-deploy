import { cn } from '../../lib/utils';

export interface CitationBlockProps {
  sourcePath: string;
  span?: {
    start_line: number;
    end_line: number;
  };
  score?: number;
  showScore?: boolean;
  lod?: number;
  compressionRatio?: number;
  className?: string;
}

/**
 * CitationBlock - Source attribution for context chunks
 * 
 * Displays:
 * - Source file path
 * - Line range (when available)
 * - Relevance score (optional)
 */
const LOD_LABELS: Record<number, string> = {
  0: 'full',
  1: 'no-comments',
  2: 'sigs+docs',
  3: 'class-only',
  4: 'names',
  5: 'summary',
};

export function CitationBlock({
  sourcePath,
  span,
  score,
  showScore = false,
  lod,
  compressionRatio,
  className,
}: CitationBlockProps) {
  return (
    <div
      className={cn(
        'flex items-center gap-2 text-sm',
        'px-3 py-2 bg-surface-raised border border-border rounded-md',
        'font-mono text-text-muted',
        className
      )}
    >
      <span className="text-text font-medium truncate max-w-[300px]" title={sourcePath}>
        {sourcePath}
      </span>
      {span && (
        <span className="text-text-subtle">
          :{span.start_line}–{span.end_line}
        </span>
      )}
      {lod !== undefined && lod > 0 && (
        <span className="text-xs px-1.5 py-0.5 rounded bg-primary/10 border border-primary/20 text-primary" title={`LOD ${lod}: ${LOD_LABELS[lod] ?? 'compressed'}`}>
          LOD{lod}
        </span>
      )}
      {compressionRatio !== undefined && compressionRatio > 1.05 && (
        <span className="text-xs text-text-subtle" title="Compression ratio">
          {compressionRatio.toFixed(1)}×
        </span>
      )}
      {showScore && score !== undefined && (
        <span className="ml-auto text-xs px-1.5 py-0.5 rounded bg-surface border border-border text-text-subtle">
          {(score * 100).toFixed(0)}%
        </span>
      )}
    </div>
  );
}
