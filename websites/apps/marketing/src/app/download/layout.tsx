import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: 'Download',
  description: 'Get SourcePrep for macOS and Windows — free and open source under Apache 2.0. Install with pip or brew, and plug into Cursor, Windsurf, or Claude Code via MCP.',
  path: '/download',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
