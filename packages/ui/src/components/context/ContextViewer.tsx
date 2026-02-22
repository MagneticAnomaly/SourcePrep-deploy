import { CopyButton } from './CopyButton';
import { CitationBlock } from './CitationBlock';
import { cn } from '../../lib/utils';
import { FileText } from 'lucide-react';

export interface ContextChunk {
  chunk_id?: string;
  source_path: string;
  span?: {
    start_line: number;
    end_line: number;
  };
  score?: number;
  truncated?: boolean;
  lod?: number;
  compression_ratio?: number;
}

export interface ContextViewerProps {
  context: string;
  chunks?: ContextChunk[];
  totalChars?: number;
  estimatedTokens?: number;
  showSources?: boolean;
  showScores?: boolean;
  className?: string;
}

/**
 * ContextViewer - Assembled context output display
 * 
 * Displays:
 * - Full context text (copyable)
 * - Citation headers per chunk
 * - Sources list view
 * - Token/char estimates
 */
export function ContextViewer({
  context,
  chunks = [],
  totalChars,
  estimatedTokens,
  showSources = true,
  showScores = false,
  className,
}: ContextViewerProps) {
  return (
    <div className={cn('rounded-lg border border-border bg-surface p-6 shadow-sm', className)}>
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold text-text flex items-center gap-2">
            <FileText className="w-5 h-5 text-primary" />
            Generated Context
          </h3>
          {(totalChars || estimatedTokens) && (
            <p className="mt-1 text-sm text-text-muted">
              {totalChars && `${totalChars.toLocaleString()} chars`}
              {totalChars && estimatedTokens && ' · '}
              {estimatedTokens && `~${estimatedTokens.toLocaleString()} tokens`}
            </p>
          )}
        </div>
        <CopyButton text={context} label="Copy Context" />
      </div>

      {/* Sources list */}
      {showSources && chunks.length > 0 && (
        <div className="mb-6">
          <div className="border-t border-border my-4" />
          <h4 className="text-sm font-medium text-text mb-3">Sources ({chunks.length})</h4>
          <div className="space-y-2">
            {chunks.map((chunk, i) => (
              <CitationBlock
                key={chunk.chunk_id ?? `${chunk.source_path}-${i}`}
                sourcePath={chunk.source_path}
                span={chunk.span}
                score={chunk.score}
                showScore={showScores}
                lod={chunk.lod}
                compressionRatio={chunk.compression_ratio}
              />
            ))}
          </div>
        </div>
      )}

      {/* Context content */}
      <div className="border-t border-border my-4" />
      <div className="bg-surface-raised border border-border rounded-lg overflow-auto max-h-[50vh]">
        <pre className="p-4 text-sm font-mono whitespace-pre-wrap text-text">
          {context}
        </pre>
      </div>
    </div>
  );
}
