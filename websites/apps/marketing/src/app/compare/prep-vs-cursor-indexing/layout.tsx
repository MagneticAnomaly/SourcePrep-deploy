import { constructMetadata } from '../../metadata-helper';

export const metadata = constructMetadata({
  title: 'RunPrep vs Cursor Codebase Indexing',
  description: 'Understand the difference between Cursor\'s built-in vector search and RunPrep\'s structural code graph. Learn how to combine them via MCP for perfect context.',
  path: '/compare/prep-vs-cursor-indexing',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
