import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'IDE Integrations — One MCP Server, Every Editor',
  description: 'CoDRAG connects to Claude Code, Antigravity, Cursor, Windsurf, VS Code, and any MCP-compatible tool. One server, every editor.',
  path: '/integrations',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
