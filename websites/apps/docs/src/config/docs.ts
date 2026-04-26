import { type DocNode } from '@prep/ui';

const isDev = process.env.NODE_ENV !== 'production';
const MARKETING_URL = isDev ? 'http://localhost:3000' : 'https://sourceprep.io';

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
      { title: 'Context Compression', href: '/guides/compression' },
      { title: 'Path Weights', href: '/guides/path-weights' },
      { title: 'Knowledge Scope', href: '/guides/knowledge-scope' },
      { title: 'BYOK Batch Processing', href: '/guides/byok-batching' },
      { title: 'Cloud Concurrency Discovery', href: '/guides/concurrency-discovery' },
      { title: 'Team Sync', href: '/guides/team-sync' },
      { title: 'Model Setup Advisor', href: '/guides/model-advisor' },
      { title: 'Codebase Audit', href: '/guides/codebase-audit' },
    ],
  },
  {
    title: 'Deployment',
    href: '/guides/team-sync',
    children: [
      { title: 'Team Sync (CI/CD)', href: '/guides/team-sync' },
      { title: 'Enterprise Deploy', href: '/guides/enterprise-deploy' },
    ],
  },
  {
    title: 'Integrations',
    href: '/mcp',
    children: [
      { title: 'MCP Server', href: '/mcp' },
      { title: 'Cursor', href: '/mcp/cursor' },
      { title: 'Windsurf', href: '/mcp/windsurf' },
      { title: 'Paperclip Plugin', href: '/mcp/paperclip' },
    ],
  },
  {
    title: 'Help',
    href: '/troubleshooting',
    children: [
      { title: 'Troubleshooting', href: '/troubleshooting' },
      { title: 'FAQ', href: `${MARKETING_URL}/faq` },
      { title: 'Support', href: `${MARKETING_URL}/support` },
    ],
  },
];
