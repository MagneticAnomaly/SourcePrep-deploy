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
    ];
  },
};

module.exports = nextConfig;
