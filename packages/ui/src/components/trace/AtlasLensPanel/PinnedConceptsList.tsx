import { X, Pin } from 'lucide-react';
import { cn } from '../../../lib/utils';

export interface PinnedConceptLite {
  id: string;
  title: string;
}

export interface PinnedConceptsListProps {
  pinnedIds: string[];
  /** Lookup for id → title so the UI can show readable labels. Caller
   *  (dashboard) is in charge of resolving these from the concept store. */
  resolveTitle?: (conceptId: string) => string | undefined;
  onUnpin?: (conceptId: string) => void;
  disabled?: boolean;
  className?: string;
}

/**
 * Compact list of concepts pinned to the current role.
 *
 * Rendered inside the RoleLens summary column. Each entry is a chip
 * showing the concept title (or id if the caller has not resolved it yet)
 * with a one-click unpin affordance. Clicking unpin optimistically
 * removes the entry via ``onUnpin`` — the parent hook handles rollback.
 */
export function PinnedConceptsList({
  pinnedIds,
  resolveTitle,
  onUnpin,
  disabled,
  className,
}: PinnedConceptsListProps) {
  if (pinnedIds.length === 0) {
    return (
      <div className={cn('text-[11px] text-text-muted italic', className)}>
        No pinned concepts. Pin from the concepts panel to seed every
        role lens projection with this knowledge.
      </div>
    );
  }
  return (
    <ul className={cn('flex flex-wrap gap-1', className)}>
      {pinnedIds.map((id) => {
        const title = resolveTitle?.(id) ?? id;
        return (
          <li
            key={id}
            className={cn(
              'inline-flex items-center gap-1 rounded-full border border-border bg-surface-raised px-2 py-0.5 text-[11px]',
            )}
          >
            <Pin className="w-3 h-3 text-primary shrink-0" />
            <span className="truncate max-w-[160px]" title={title}>{title}</span>
            {onUnpin && !disabled && (
              <button
                type="button"
                onClick={() => onUnpin(id)}
                className="ml-0.5 inline-flex items-center justify-center rounded-full hover:bg-surface w-4 h-4 text-text-muted hover:text-text"
                aria-label={`Unpin ${title}`}
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
