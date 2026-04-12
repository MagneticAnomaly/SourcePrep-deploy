import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Graph Enrichment Pipeline — How CoDRAG Understands Your Code',
  description: 'A 15-stage pipeline in three groups of five: Sync, Enrich, Finalize. From Rust parsing to deep LLM reasoning to architectural synthesis.',
  path: '/graph-enrichment',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
