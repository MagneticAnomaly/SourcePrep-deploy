"use client";

import { ExternalLink } from 'lucide-react';
import { cn } from '../../../lib/utils';
import type { ResearchSource } from '../../../data/researchSources';

const TYPE_BADGES: Record<ResearchSource['type'], { label: string; cls: string }> = {
  paper: { label: 'Paper', cls: 'bg-primary/10 text-primary border-primary/30' },
  repo:  { label: 'Repo',  cls: 'bg-success/10 text-success border-success/30' },
  blog:  { label: 'Essay', cls: 'bg-warning/10 text-warning border-warning/30' },
  spec:  { label: 'Spec',  cls: 'bg-text/10 text-text border-border' },
  book:  { label: 'Book',  cls: 'bg-text-muted/10 text-text-muted border-border' },
};

export interface SourceCardProps {
  source: ResearchSource;
  className?: string;
}

export function SourceCard({ source, className }: SourceCardProps) {
  const badge = TYPE_BADGES[source.type];
  const citation = [source.authors, source.venue, source.year].filter(Boolean).join(' \u00b7 ');
  const accessibleName = `${badge.label}: ${source.title} (opens in new tab)`;

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={accessibleName}
      className={cn(
        'group flex flex-col rounded-lg border border-border bg-surface p-4 transition-colors hover:border-primary/40 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
        className,
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className={cn('text-[10px] font-mono font-semibold uppercase tracking-wider rounded-full px-2 py-0.5 border', badge.cls)}>
          {badge.label}
        </span>
        <ExternalLink className="w-3 h-3 text-text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
      <h4 className="text-sm font-semibold text-text leading-snug mb-1 group-hover:text-primary transition-colors">
        {source.title}
      </h4>
      {citation && <p className="text-xs text-text-muted mb-2">{citation}</p>}
      <p className="text-xs text-text-muted leading-relaxed mt-auto">{source.usage}</p>
    </a>
  );
}
