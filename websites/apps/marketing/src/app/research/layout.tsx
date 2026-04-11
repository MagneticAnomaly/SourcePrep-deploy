import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Research \u2014 CoDRAG',
  description:
    'A bibliography of the papers, repositories, essays, and standards CoDRAG was built on, with notes on how each one was used.',
  openGraph: {
    title: 'Research \u2014 CoDRAG',
    description:
      'A bibliography of the papers, repositories, essays, and standards CoDRAG was built on.',
    type: 'website',
  },
};

export default function ResearchLayout({ children }: { children: React.ReactNode }) {
  return children;
}
