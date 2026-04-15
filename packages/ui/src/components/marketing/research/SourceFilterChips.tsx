"use client";

import { cn } from '../../../lib/utils';
import type { SourceType } from '../../../data/researchSources';

export type FilterValue = 'all' | SourceType;

const FILTERS: { value: FilterValue; label: string }[] = [
  { value: 'all',   label: 'All' },
  { value: 'paper', label: 'Papers' },
  { value: 'repo',  label: 'Repos' },
  { value: 'blog',  label: 'Essays' },
  { value: 'spec',  label: 'Specs' },
  { value: 'book',  label: 'Books' },
];

export interface SourceFilterChipsProps {
  active: FilterValue;
  onChange: (value: FilterValue) => void;
  /** Set of types present in the section. Filters not in this set are hidden. */
  available: Set<SourceType>;
  className?: string;
}

export function SourceFilterChips({ active, onChange, available, className }: SourceFilterChipsProps) {
  return (
    <div role="group" aria-label="Filter sources by type" className={cn('flex flex-wrap gap-2', className)}>
      {FILTERS.filter((f) => f.value === 'all' || available.has(f.value as SourceType)).map((f) => {
        const isActive = active === f.value;
        return (
          <button
            key={f.value}
            type="button"
            aria-pressed={isActive}
            onClick={() => onChange(f.value)}
            className={cn(
              'text-xs font-medium px-3 py-1.5 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
              isActive
                ? 'bg-primary text-white border-primary'
                : 'bg-surface text-text-muted border-border hover:border-primary/40 hover:text-text',
            )}
          >
            {f.label}
          </button>
        );
      })}
    </div>
  );
}
