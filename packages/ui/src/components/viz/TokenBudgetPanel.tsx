import { cn } from '../../lib/utils';

export interface TokenBudgetData {
  tokens_used: number;
  max_tokens: number;
  window_minutes: number;
  remaining: number;
  window_resets_in: number;
}

export interface TokenBudgetPanelProps {
  data: TokenBudgetData | null;
  deepMode: string;
  className?: string;
}

export function TokenBudgetPanel({ data, deepMode, className }: TokenBudgetPanelProps) {
  if (!data || data.max_tokens <= 0) {
    return (
      <div className={cn('h-full flex flex-col items-center justify-center text-center', className)}>
        <div className="text-2xl mb-2">∞</div>
        <div className="text-sm text-text-muted">
          {deepMode === 'manual' ? 'Manual mode — no budget' : 'Token budget unlimited'}
        </div>
        <div className="text-xs text-text-muted mt-1">
          Configure a budget in Deep Enrichment settings to track usage.
        </div>
      </div>
    );
  }

  const pct = data.max_tokens > 0 ? Math.min(100, (data.tokens_used / data.max_tokens) * 100) : 0;
  const isExhausted = data.remaining <= 0;
  const isWarning = pct > 75 && !isExhausted;

  const barColor = isExhausted
    ? 'bg-red-500'
    : isWarning
    ? 'bg-amber-500'
    : 'bg-emerald-500';

  const resetMinutes = Math.ceil(data.window_resets_in / 60);

  return (
    <div className={cn('h-full space-y-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold text-text-muted uppercase tracking-wider">
          Token Budget
        </div>
        <div className={cn(
          'text-xs px-2 py-0.5 rounded-full font-medium',
          isExhausted ? 'bg-red-500/20 text-red-400' :
          isWarning ? 'bg-amber-500/20 text-amber-400' :
          'bg-emerald-500/20 text-emerald-400',
        )}>
          {isExhausted ? 'Exhausted' : isWarning ? 'Warning' : 'Available'}
        </div>
      </div>

      {/* Usage Bar */}
      <div>
        <div className="h-3 bg-surface-raised rounded-full overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all duration-500', barColor)}
            style={{ width: `${Math.min(100, pct)}%` }}
          />
        </div>
        <div className="flex justify-between mt-1.5 text-xs text-text-muted">
          <span>{data.tokens_used.toLocaleString()} used</span>
          <span>{data.max_tokens.toLocaleString()} max</span>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-surface-raised rounded-lg px-3 py-2">
          <div className="text-[10px] text-text-muted uppercase">Remaining</div>
          <div className={cn('text-sm font-semibold', isExhausted ? 'text-red-400' : 'text-text')}>
            {data.remaining >= 0 ? data.remaining.toLocaleString() : '∞'}
          </div>
        </div>
        <div className="bg-surface-raised rounded-lg px-3 py-2">
          <div className="text-[10px] text-text-muted uppercase">Window</div>
          <div className="text-sm font-semibold text-text">{data.window_minutes}m</div>
        </div>
      </div>

      {/* Reset Timer */}
      {data.window_resets_in > 0 && (
        <div className="text-xs text-text-muted text-center">
          Window resets in {resetMinutes < 60 ? `${resetMinutes}m` : `${Math.round(resetMinutes / 60)}h`}
        </div>
      )}

      {/* Exhausted Warning */}
      {isExhausted && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-xs text-red-400">
          Auto-chain deep enrichment is paused until the budget window resets.
        </div>
      )}
    </div>
  );
}
