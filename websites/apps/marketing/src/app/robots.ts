import { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: ['/private/', '/dev/'],
    },
    sitemap: 'https://sourceprep.io/sitemap.xml',
  };
}
