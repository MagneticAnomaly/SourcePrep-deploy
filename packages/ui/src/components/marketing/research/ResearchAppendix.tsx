"use client";

import { useMemo, useState } from 'react';
import { cn } from '../../../lib/utils';
import type { ResearchSource, SourceType } from '../../../data/researchSources';
import { SourceCard } from './SourceCard';
import { SourceFilterChips, type FilterValue } from './SourceFilterChips';

export interface ResearchAppendixProps {
  /** Heading shown above the chips */
  title?: string;
  sources: ResearchSource[];
  className?: string;
}

export function ResearchAppendix({
  title = 'Further reading',
  sources,
  className,
}: ResearchAppendixProps) {
  const [filter, setFilter] = useState<FilterValue>('all');

  const available = useMemo<Set<SourceType>>(
    () => new Set(sources.map((s) => s.type)),
    [sources],
  );

  const filtered = useMemo(
    () => (filter === 'all' ? sources : sources.filter((s) => s.type === filter)),
    [filter, sources],
  );

  if (sources.length === 0) return null;

  return (
    <div className={cn('mt-12', className)}>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
        <h4 className="text-xs font-mono font-semibold text-text uppercase tracking-widest">
          {title}
        </h4>
        <SourceFilterChips active={filter} onChange={setFilter} available={available} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((source) => (
          <SourceCard key={source.id} source={source} />
        ))}
      </div>
      {filtered.length === 0 && (
        <p className="text-sm text-text-muted italic mt-4">
          No sources of this type in this section.
        </p>
      )}
    </div>
  );
}
