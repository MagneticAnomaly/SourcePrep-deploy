import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Paperclip Integration — Agent Orchestration with SourcePrep',
  description: 'SourcePrep provides deep structural codebase intelligence to Paperclip agent teams. Auto-push findings, SourcePrep addresses, and hybrid MCP+REST integration.',
  path: '/paperclip',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
