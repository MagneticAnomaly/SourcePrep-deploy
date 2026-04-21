import { cn } from '../../../lib/utils';

export interface ResearchHeroProps {
  className?: string;
}

/**
 * Editorial hero rendered inside DetailPageLayout's main content column.
 * The page-level h1 lives in DetailPageLayout's sidebar, so this hero uses h2.
 */
export function ResearchHero({ className }: ResearchHeroProps) {
  return (
    <header className={cn('text-center max-w-3xl mx-auto pb-10 sm:pb-14 border-b border-border', className)}>
      <p className="text-[11px] font-mono font-semibold uppercase tracking-[0.2em] text-primary mb-4">
        Bibliography
      </p>
      <h2 className="text-4xl sm:text-5xl font-semibold text-text leading-tight tracking-tight mb-6">
        What RunPrep was built on.
      </h2>
      <p className="text-lg text-text-muted leading-relaxed">
        A working list of the papers, repositories, essays, and standards RunPrep draws on. Each entry includes a one-line note on how it shaped the project &mdash; and what we changed when we disagreed.
      </p>
    </header>
  );
}
