import { MetadataRoute } from 'next';

// Source of truth: every route below maps to a page.tsx under src/app/.
// If you add or remove a page, update this list. Per Phase 130, we no
// longer list deleted hubs (/concepts, /guides) or routes that don't
// exist (/mcp/cursor, /mcp/windsurf, /concepts/trace-index, etc.).
export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = 'https://docs.sourceprep.io';

  const routes = [
    '',
    '/getting-started',
    '/getting-started/installation',
    '/getting-started/quick-start',
    '/concepts/indexing',
    '/concepts/code-graph',
    '/concepts/graph-enrichment',
    '/concepts/context',
    '/dashboard',
    '/dashboard/projects',
    '/cli',
    '/cli/commands',
    '/cli/config',
    '/mcp',
    '/mcp/ides',
    '/mcp/terminal',
    '/mcp/paperclip',
    '/guides/embeddings',
    '/guides/models',
    '/guides/model-advisor',
    '/guides/dynamic-model-loading',
    '/guides/compression',
    '/guides/smart-search',
    '/guides/path-weights',
    '/guides/knowledge-scope',
    '/guides/byok-batching',
    '/guides/concurrency-discovery',
    '/guides/codebase-audit',
    '/guides/audit-enrichment',
    '/guides/team-sync',
    '/guides/enterprise-deploy',
    '/troubleshooting',
    '/search',
  ].map((route) => ({
    url: `${baseUrl}${route}`,
    lastModified: new Date().toISOString(),
    changeFrequency: 'weekly' as const,
    priority: route === '' ? 1.0 : 0.8,
  }));

  return routes;
}
