import type { DocNode } from '@codrag/ui';

const isDev = process.env.NODE_ENV !== 'production';
const MARKETING_URL = isDev ? 'http://localhost:3000' : 'https://codrag.io';

export const docsSidebar: DocNode[] = [
  {
    title: 'Getting Started',
    href: '/getting-started',
    children: [
      { title: 'Introduction', href: '/getting-started' },
      { title: 'Installation', href: '/getting-started/installation' },
      { title: 'Quick Start', href: '/getting-started/quick-start' },
    ],
  },
  {
    title: 'Core Concepts',
    href: '/concepts',
    children: [
      { title: 'Local Indexing', href: '/concepts/indexing' },
      { title: 'Code Graph', href: '/concepts/code-graph' },
      { title: 'Graph Enrichment', href: '/concepts/graph-enrichment' },
      { title: 'Context Assembly', href: '/concepts/context' },
    ],
  },
  {
    title: 'Dashboard',
    href: '/dashboard',
    children: [
      { title: 'Overview', href: '/dashboard' },
      { title: 'Projects', href: '/dashboard/projects' },
    ],
  },
  {
    title: 'CLI Reference',
    href: '/cli',
    children: [
      { title: 'Overview', href: '/cli' },
      { title: 'Commands', href: '/cli/commands' },
      { title: 'Configuration', href: '/cli/config' },
    ],
  },
  {
    title: 'Guides',
    href: '/guides',
    children: [
      { title: 'Overview', href: '/guides' },
      { title: 'Built-in Embeddings', href: '/guides/embeddings' },
      { title: 'Model Configuration', href: '/guides/models' },
      { title: 'Context Compression (CLaRa)', href: '/guides/clara' },
      { title: 'Path Weights', href: '/guides/path-weights' },
    ],
  },
  {
    title: 'Integrations',
    href: '/mcp',
    children: [
      { title: 'MCP Server', href: '/mcp' },
      { title: 'Cursor', href: '/mcp/cursor' },
      { title: 'Windsurf', href: '/mcp/windsurf' },
    ],
  },
  {
    title: 'Help',
    href: '/troubleshooting',
    children: [
      { title: 'Troubleshooting', href: '/troubleshooting' },
      { title: 'FAQ', href: '/faq' },
      { title: 'Support', href: `${MARKETING_URL}/support` },
    ],
  },
];
