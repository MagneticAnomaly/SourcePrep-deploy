/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['@prep/ui'],
  async redirects() {
    return [
      {
        source: '/privacy',
        destination: '/security#data-collection',
        permanent: true,
      },
      {
        source: '/contact',
        destination: '/support',
        permanent: true,
      },
      {
        // Concept pages are canonical on the docs site (single source of truth).
        source: '/graph-enrichment',
        destination: 'https://docs.sourceprep.io/concepts/graph-enrichment',
        permanent: true,
      },
    ];
  },
};

module.exports = nextConfig;
