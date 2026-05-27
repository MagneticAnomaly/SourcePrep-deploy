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
    // No hub page — section header is non-clickable; pages listed below.
    title: 'How It Works',
    href: '',
    children: [
      { title: 'Knowledge', href: '/how-it-works/indexing' },
      { title: 'Code Graph', href: '/how-it-works/code-graph' },
      { title: 'Graph Enrichment', href: '/how-it-works/graph-enrichment' },
      { title: 'Context Assembly', href: '/how-it-works/context' },
      { title: 'Built-in Embeddings', href: '/how-it-works/embeddings' },
      { title: 'Context Compression', href: '/how-it-works/compression' },
      { title: 'Smart Search', href: '/how-it-works/smart-search' },
      { title: 'Local LLM Setup', href: '/how-it-works/dynamic-model-loading' },
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
    // No hub page — guide list lives in the sidebar itself.
    title: 'Guides',
    href: '',
    children: [
      { title: 'AI Gateway (Models)', href: '/guides/models' },
      { title: 'Knowledge Scope', href: '/guides/knowledge-scope' },
      { title: 'Path Weights', href: '/guides/path-weights' },
      { title: 'Codebase Audit', href: '/guides/codebase-audit' },
      { title: 'Audit Enrichment', href: '/guides/audit-enrichment' },
      { title: 'BYOK Batch Processing', href: '/guides/byok-batching' },
      { title: 'Cloud Concurrency Discovery', href: '/guides/concurrency-discovery' },
      { title: 'Team Sync', href: '/guides/team-sync' },
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
      { title: 'IDEs (Cursor, Windsurf, VS Code)', href: '/mcp/ides' },
      { title: 'Terminal (Claude Code, Codex, Gemini)', href: '/mcp/terminal' },
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
