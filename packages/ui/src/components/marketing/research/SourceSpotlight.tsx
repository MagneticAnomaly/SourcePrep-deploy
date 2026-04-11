"use client";

import { ExternalLink } from 'lucide-react';
import { cn } from '../../../lib/utils';
import type { ResearchSource } from '../../../data/researchSources';

const TYPE_LABELS: Record<ResearchSource['type'], string> = {
  paper: 'Paper',
  repo:  'Repository',
  blog:  'Essay',
  spec:  'Specification',
  book:  'Book',
};

export interface SourceSpotlightProps {
  source: ResearchSource;
  className?: string;
}

export function SourceSpotlight({ source, className }: SourceSpotlightProps) {
  const typeLabel = TYPE_LABELS[source.type];
  const citation = [source.authors, source.venue, source.year].filter(Boolean).join(' \u00b7 ');
  const accessibleName = `${typeLabel}: ${source.title} (opens in new tab)`;

  return (
    <article
      className={cn(
        'rounded-2xl border border-border bg-surface-raised p-6 sm:p-8 transition-shadow hover:shadow-lg',
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-3">
        <span className="text-[11px] font-mono font-semibold uppercase tracking-widest text-primary">
          {typeLabel}
        </span>
        {citation && <span className="text-xs text-text-muted">{citation}</span>}
      </div>
      <h3 className="text-xl sm:text-2xl font-semibold text-text mb-3 leading-snug tracking-tight">
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={accessibleName}
          className="hover:text-primary transition-colors inline-flex items-baseline gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 rounded"
        >
          {source.title}
          <ExternalLink className="w-4 h-4 self-center" aria-hidden="true" />
        </a>
      </h3>
      <p className="text-text-muted leading-relaxed text-base">
        {source.spotlightProse}
      </p>
    </article>
  );
}
