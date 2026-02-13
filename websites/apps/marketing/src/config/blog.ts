export interface BlogPost {
  slug: string;
  title: string;
  excerpt: string;
  date: string;
  author: string;
  tags: string[];
  featured?: boolean;
}

export const BLOG_POSTS: BlogPost[] = [
  {
    slug: 'why-structural-context-matters',
    title: 'Why Structural Context Matters for AI Coding Tools',
    excerpt:
      'AI assistants already index your code — but they grab files, not relationships. Here\'s why the structural layer changes everything.',
    date: 'March 1, 2026',
    author: 'CoDRAG Team',
    tags: ['Product', 'Philosophy'],
    featured: true,
  },
  {
    slug: 'introducing-code-graph',
    title: 'Introducing the Code Graph',
    excerpt:
      'Vector search finds similar text. The Code Graph maps how code connects — imports, calls, symbol hierarchies.',
    date: 'Feb 15, 2026',
    author: 'Engineering',
    tags: ['Deep Dive'],
  },
  {
    slug: 'mcp-the-universal-connector',
    title: 'MCP: The Universal Connector',
    excerpt:
      'How the Model Context Protocol lets CoDRAG integrate with Cursor, Windsurf, VS Code, and Claude Desktop.',
    date: 'Feb 01, 2026',
    author: 'Integration',
    tags: ['Ecosystem'],
  },
];
