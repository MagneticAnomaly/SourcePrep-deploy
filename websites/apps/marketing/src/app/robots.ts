import { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      // /private/ and /dev/ are internal-only routes excluded from indexing.
      disallow: ['/private/', '/dev/'],
    },
    sitemap: 'https://sourceprep.io/sitemap.xml',
  };
}
