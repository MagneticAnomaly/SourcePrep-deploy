import { constructMetadata } from '../../metadata-helper';

export const metadata = constructMetadata({
  title: 'CoDRAG vs Cursor Codebase Indexing',
  description: 'Understand the difference between Cursor\'s built-in vector search and CoDRAG\'s structural code graph. Learn how to combine them via MCP for perfect context.',
  path: '/compare/codrag-vs-cursor-indexing',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
