import { MetadataRoute } from 'next';

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = 'https://sourceprep.io';
  
  // Core pages
  // Note: /contact and /privacy are server-side redirects (next.config.js);
  // not listed here so they don't appear as canonical destinations.
  const routes = [
    '',
    '/download',
    '/setup',
    '/pricing',
    '/faq',
    '/security',
    '/careers',
    '/changelog',
    '/blog',
    '/research',
    '/terms',
  ].map((route) => ({
    url: `${baseUrl}${route}`,
    lastModified: new Date().toISOString(),
    changeFrequency: 'weekly' as const,
    priority: route === '' ? 1.0 : 0.8,
  }));

  return routes;
}
