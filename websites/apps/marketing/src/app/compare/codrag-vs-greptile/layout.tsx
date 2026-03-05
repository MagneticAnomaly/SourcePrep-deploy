import { constructMetadata } from '../../metadata-helper';

export const metadata = constructMetadata({
  title: 'CoDRAG vs Greptile: Why Local Code Indexing Wins',
  description: 'A detailed comparison of CoDRAG and Greptile for codebase RAG. See why enterprise teams are switching to local-first structural indexing to protect their code.',
  path: '/compare/codrag-vs-greptile',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
