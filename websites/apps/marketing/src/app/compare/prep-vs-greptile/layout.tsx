import { constructMetadata } from '../../metadata-helper';

export const metadata = constructMetadata({
  title: 'RunPrep vs Greptile: Why Epistemic Code Understanding Wins',
  description: 'A detailed comparison of RunPrep and Greptile for codebase RAG. See why enterprise teams are switching to sophisticated epistemic tracing and Sovereign Context.',
  path: '/compare/prep-vs-greptile',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
