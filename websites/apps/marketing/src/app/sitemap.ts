import { MetadataRoute } from 'next';

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = 'https://codrag.io';
  
  // Core pages
  const routes = [
    '',
    '/download',
    '/setup',
    '/pricing',
    '/faq',
    '/security',
    '/contact',
    '/careers',
    '/changelog',
    '/blog',
    '/research',
    '/privacy',
    '/terms',
  ].map((route) => ({
    url: `${baseUrl}${route}`,
    lastModified: new Date().toISOString(),
    changeFrequency: 'weekly' as const,
    priority: route === '' ? 1.0 : 0.8,
  }));

  return routes;
}
