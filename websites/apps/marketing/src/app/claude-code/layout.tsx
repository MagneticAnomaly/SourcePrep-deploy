import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Claude Code Integration — CoDRAG MCP Server',
  description: 'CoDRAG is the best MCP server for Claude Code. Six tools, auto-approve, skills integration, and client-aware content delivery.',
  path: '/claude-code',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
