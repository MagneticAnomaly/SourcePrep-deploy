/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['@prep/ui'],
  pageExtensions: ['js', 'jsx', 'mdx', 'ts', 'tsx'],
  async redirects() {
    return [
      {
        source: '/guides/clara',
        destination: '/guides/compression',
        permanent: true,
      },
      // Pure-hub pages removed — land direct hits on the first child instead of 404.
      {
        source: '/concepts',
        destination: '/concepts/indexing',
        permanent: true,
      },
      {
        source: '/guides',
        destination: '/guides/embeddings',
        permanent: true,
      },
    ];
  },
};

const withMDX = require('@next/mdx')()

module.exports = withMDX(nextConfig)
