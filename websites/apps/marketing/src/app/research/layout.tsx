import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Research \u2014 SourcePrep',
  description:
    'A bibliography of the papers, repositories, essays, and standards SourcePrep was built on, with notes on how each one was used.',
  openGraph: {
    title: 'Research \u2014 SourcePrep',
    description:
      'A bibliography of the papers, repositories, essays, and standards SourcePrep was built on.',
    type: 'website',
  },
};

export default function ResearchLayout({ children }: { children: React.ReactNode }) {
  return children;
}
