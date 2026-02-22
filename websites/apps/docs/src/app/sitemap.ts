import { MetadataRoute } from 'next';

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = 'https://docs.codrag.io';
  
  const routes = [
    '',
    '/getting-started',
    '/getting-started/installation',
    '/getting-started/quick-start',
    '/mcp',
    '/mcp/cursor',
    '/mcp/windsurf',
    '/concepts',
    '/concepts/indexing',
    '/concepts/trace-index',
    '/concepts/context',
    '/dashboard',
    '/dashboard/projects',
    '/dashboard/settings',
    '/cli',
    '/cli/commands',
    '/cli/config',
    '/guides',
    '/guides/embeddings',
    '/guides/models',
    '/guides/compression',
    '/guides/path-weights',
    '/troubleshooting',
    '/faq',
  ].map((route) => ({
    url: `${baseUrl}${route}`,
    lastModified: new Date().toISOString(),
    changeFrequency: 'weekly' as const,
    priority: route === '' ? 1.0 : 0.8,
  }));

  return routes;
}
