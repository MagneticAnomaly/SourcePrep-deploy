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
    ];
  },
};

const withMDX = require('@next/mdx')()

module.exports = withMDX(nextConfig)
