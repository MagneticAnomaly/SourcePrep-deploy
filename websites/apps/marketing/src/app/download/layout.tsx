import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Download',
  description: 'Download the CoDRAG desktop app for macOS, Windows, and Linux. Plug it into Cursor, Windsurf, or Claude Code via MCP.',
  path: '/download',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
