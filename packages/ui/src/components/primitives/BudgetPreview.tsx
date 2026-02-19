import { cn } from '../../lib/utils';
import { BudgetPill } from './BudgetPill';

export interface BudgetPreviewProps {
  /** Estimated character count */
  chars?: number;
  /** Estimated token count (chars / 4 if not provided) */
  tokens?: number;
  /** Max character budget */
  maxChars?: number;
  /** Max token budget */
  maxTokens?: number;
  /** Number of chunks contributing to this context */
  chunkCount?: number;
  className?: string;
  /** Compact single-line display */
  compact?: boolean;
}

/**
 * BudgetPreview — shows estimated context size (chars + tokens) against budgets.
 * Used in context assembler panels to give the user a sense of prompt size.
 */
export function BudgetPreview({
  chars,
  tokens,
  maxChars,
  maxTokens,
  chunkCount,
  className,
  compact = false,
}: BudgetPreviewProps) {
  const estimatedTokens = tokens ?? (chars != null ? Math.round(chars / 4) : undefined);

  if (compact) {
    return (
      <div className={cn('flex items-center gap-2 flex-wrap', className)}>
        {chars != null && (
          <BudgetPill value={chars} unit="chars" max={maxChars} />
        )}
        {estimatedTokens != null && (
          <BudgetPill value={estimatedTokens} unit="tokens" max={maxTokens} />
        )}
        {chunkCount != null && (
          <span className="text-xs text-text-subtle tabular-nums">{chunkCount} chunks</span>
        )}
      </div>
    );
  }

  return (
    <div className={cn('rounded-md border border-border bg-surface-raised/50 p-3 space-y-2', className)}>
      <p className="text-xs font-medium text-text-muted">Context Budget</p>
      <div className="flex items-center gap-3 flex-wrap">
        {chars != null && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-text-subtle">Chars</span>
            <BudgetPill value={chars} unit="" max={maxChars} />
          </div>
        )}
        {estimatedTokens != null && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-text-subtle">~Tokens</span>
            <BudgetPill value={estimatedTokens} unit="" max={maxTokens} />
          </div>
        )}
        {chunkCount != null && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-text-subtle">Chunks</span>
            <span className="text-xs font-medium text-text tabular-nums">{chunkCount}</span>
          </div>
        )}
      </div>
      {maxChars != null && chars != null && chars > maxChars && (
        <p className="text-xs text-error">
          Context exceeds budget by {Math.round((chars - maxChars) / 1000)}k chars — reduce K or lower max chars.
        </p>
      )}
    </div>
  );
}
