import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'FAQ',
  description: 'Frequently asked questions about RunPrep, local RAG, token budgets, and MCP integration.',
  path: '/faq',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
