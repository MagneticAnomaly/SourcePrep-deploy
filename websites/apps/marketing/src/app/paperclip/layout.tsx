import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Paperclip Integration — Agent Orchestration with Prep',
  description: 'Prep provides deep structural codebase intelligence to Paperclip agent teams. Auto-push findings, Prep addresses, and hybrid MCP+REST integration.',
  path: '/paperclip',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
