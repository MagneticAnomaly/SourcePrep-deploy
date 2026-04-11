"use client";

import { cn } from '../../../lib/utils';
import type { ResearchSource } from '../../../data/researchSources';
import { SourceSpotlight } from './SourceSpotlight';
import { ResearchAppendix } from './ResearchAppendix';

export interface ResearchSectionProps {
  /** Anchor id used by the sidebar TOC */
  id: string;
  title: string;
  intro: string;
  sources: ResearchSource[];
  className?: string;
}

export function ResearchSection({
  id,
  title,
  intro,
  sources,
  className,
}: ResearchSectionProps) {
  const spotlights = sources.filter((s) => s.spotlight);
  const appendix = sources.filter((s) => !s.spotlight);

  return (
    <section
      id={id}
      className={cn(
        'scroll-mt-24 py-12 first:pt-0 border-b border-border last:border-b-0',
        className,
      )}
    >
      <h3 className="text-2xl sm:text-3xl font-semibold text-text mb-3 tracking-tight">
        {title}
      </h3>
      <p className="text-text-muted leading-relaxed max-w-3xl mb-8">{intro}</p>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {spotlights.map((source) => (
          <SourceSpotlight key={source.id} source={source} />
        ))}
      </div>
      <ResearchAppendix sources={appendix} />
    </section>
  );
}
