import { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: ['/success', '/recover'], // Don't index transactional pages
    },
    sitemap: 'https://payments.sourceprep.io/sitemap.xml',
  };
}
