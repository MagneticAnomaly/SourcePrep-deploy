"use client";

import {
  DetailPageLayout,
  ResearchHero,
  ResearchSection,
  RESEARCH_SOURCES,
  type ProblemArea,
} from '@prep/ui';

const SECTIONS = [
  { id: 'retrieval',   label: 'Retrieval & Long Context' },
  { id: 'compression', label: 'Compression & LOD' },
  { id: 'chunking',    label: 'Code Structure & Chunking' },
  { id: 'concepts',    label: 'Concepts, Knowledge & Standards' },
];

const INTROS: Record<ProblemArea, string> = {
  retrieval:
    'Why context engineering matters more than raw context size \u2014 and what changes when language models meet long, noisy windows.',
  compression:
    'Why Prep\u2019s context assembler ladders code from full source down to one-line signatures, and the research that makes signature-only context defensible.',
  chunking:
    'Why chunking on AST boundaries beats character splits for code, and how structural awareness changes retrieval quality.',
  concepts:
    'Why Prep treats concepts as first-class artifacts, where the protocol surface comes from, and the older work that grounds the system in something deeper than recent papers.',
};

const SECTION_TITLES: Record<ProblemArea, string> = {
  retrieval:   'Retrieval & Long Context',
  compression: 'Compression & Levels of Detail',
  chunking:    'Code Structure & Chunking',
  concepts:    'Concepts, Knowledge & Standards',
};

export default function ResearchPage() {
  const byArea = (area: ProblemArea) =>
    RESEARCH_SOURCES.filter((s) => s.problemArea === area);

  return (
    <DetailPageLayout
      title="Research"
      subtitle="Bibliography"
      description="What Prep was built on. Notes on the papers, repositories, essays, and standards that shaped the project."
      sections={SECTIONS}
      docsUrl="https://docs.runprep.io"
      docsLabel="Read the docs"
    >
      <ResearchHero />

      {(['retrieval', 'compression', 'chunking', 'concepts'] as ProblemArea[]).map((area) => (
        <ResearchSection
          key={area}
          id={area}
          title={SECTION_TITLES[area]}
          intro={INTROS[area]}
          sources={byArea(area)}
        />
      ))}

      <footer className="pt-10 text-sm text-text-muted leading-relaxed border-t border-border max-w-3xl">
        This list is incomplete. We add to it as we read, and we welcome
        corrections &mdash; if we&rsquo;ve cited your work badly, or missed work we
        should know about, open an issue on{' '}
        <a
          href="https://github.com/MagneticAnomaly/RunPrep-MCP/issues"
          className="text-primary hover:underline"
          target="_blank"
          rel="noopener noreferrer"
        >
          the repo
        </a>
        . We&rsquo;ll fix it.
      </footer>
    </DetailPageLayout>
  );
}
