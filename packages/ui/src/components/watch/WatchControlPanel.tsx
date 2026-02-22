import { cn } from '../../lib/utils';
import type { WatchStatus } from '../../types';
import { Eye, EyeOff, Lock, ArrowUpRight } from 'lucide-react';
import { Button } from '../primitives/Button';
import { WatchStatusIndicator } from './WatchStatusIndicator';

export interface WatchControlPanelProps {
  status: WatchStatus;
  onStartWatch: () => void;
  onStopWatch: () => void;
  onRebuildNow?: () => void;
  loading?: boolean;
  className?: string;
  bare?: boolean;
  /** When true, show a locked upgrade prompt instead of the enable button */
  isFree?: boolean;
  /** Called when the user clicks the upgrade CTA */
  onUpgrade?: () => void;
}

export function WatchControlPanel({
  status,
  onStartWatch,
  onStopWatch,
  onRebuildNow,
  loading = false,
  className,
  bare = false,
  isFree = false,
  onUpgrade,
}: WatchControlPanelProps) {
  const isActive = status.state !== 'disabled';
  const Container = bare ? 'div' : 'div';

  return (
    <Container
      className={cn(
        !bare && 'rounded-lg border border-border bg-surface p-4 shadow-sm',
        bare && 'p-2',
        'flex flex-col gap-3',
        className
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <WatchStatusIndicator
          status={status}
          onRebuildNow={onRebuildNow}
          showDetails
        />

        {isFree ? (
          <button
            type="button"
            onClick={onUpgrade}
            className="flex items-center gap-1.5 rounded-md border border-amber-400/40 bg-amber-50/60 dark:bg-amber-900/20 px-2.5 py-1.5 text-xs font-medium text-amber-700 dark:text-amber-400 hover:bg-amber-100/80 dark:hover:bg-amber-900/40 transition-colors"
            title="Live Sync requires Monthly plan or above"
          >
            <Lock className="w-3 h-3 shrink-0" />
            <span>Monthly feature</span>
            <ArrowUpRight className="w-3 h-3 shrink-0" />
          </button>
        ) : (
          <Button
            onClick={isActive ? onStopWatch : onStartWatch}
            variant={isActive ? 'outline' : 'default'}
            size="sm"
            loading={loading}
            icon={isActive ? EyeOff : Eye}
          >
            {isActive ? 'Disable Sync' : 'Enable Sync'}
          </Button>
        )}
      </div>

      {isFree && (
        <p className="text-xs text-text-subtle leading-relaxed">
          Live Sync automatically rebuilds your knowledge base when files change.
          {onUpgrade && (
            <>
              {' '}
              <button
                type="button"
                onClick={onUpgrade}
                className="text-primary underline underline-offset-2 hover:no-underline"
              >
                Upgrade to Monthly
              </button>
              {' '}to enable.
            </>
          )}
        </p>
      )}
    </Container>
  );
}
