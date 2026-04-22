import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Graph Enrichment Pipeline — How SourcePrep Understands Your Code',
  description: 'How SourcePrep learns how your code actually connects — a multi-step pipeline that syncs fast structural context, enriches it with deeper reasoning, and delivers the guides, rules, and safeguards your AI tools consume.',
  path: '/graph-enrichment',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
