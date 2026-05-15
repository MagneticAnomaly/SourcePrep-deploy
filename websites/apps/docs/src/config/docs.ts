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
    // No hub page — section header is non-clickable; concepts listed below.
    title: 'Core Concepts',
    href: '',
    children: [
      { title: 'Knowledge', href: '/concepts/indexing' },
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
    // No hub page — guide list lives in the sidebar itself.
    title: 'Guides',
    href: '',
    children: [
      { title: 'AI Gateway (Models)', href: '/guides/models' },
      { title: 'Knowledge Scope', href: '/guides/knowledge-scope' },
      { title: 'Path Weights', href: '/guides/path-weights' },
      { title: 'Smart Search', href: '/guides/smart-search' },
      { title: 'Codebase Audit', href: '/guides/codebase-audit' },
      { title: 'Audit Enrichment', href: '/guides/audit-enrichment' },
      { title: 'Built-in Embeddings', href: '/guides/embeddings' },
      { title: 'Context Compression', href: '/guides/compression' },
      { title: 'BYOK Batch Processing', href: '/guides/byok-batching' },
      { title: 'Cloud Concurrency Discovery', href: '/guides/concurrency-discovery' },
      { title: 'Local LLM Setup', href: '/guides/dynamic-model-loading' },
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
