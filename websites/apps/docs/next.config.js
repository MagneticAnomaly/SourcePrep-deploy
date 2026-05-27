/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['@prep/ui'],
  pageExtensions: ['js', 'jsx', 'mdx', 'ts', 'tsx'],
  async redirects() {
    return [
      // Phase 138 — /concepts/ section renamed to /how-it-works/ to disambiguate
      // from the prep_concepts MCP tool. Permanent redirects keep external links alive.
      { source: '/concepts', destination: '/how-it-works/indexing', permanent: true },
      { source: '/concepts/indexing', destination: '/how-it-works/indexing', permanent: true },
      { source: '/concepts/code-graph', destination: '/how-it-works/code-graph', permanent: true },
      { source: '/concepts/graph-enrichment', destination: '/how-it-works/graph-enrichment', permanent: true },
      { source: '/concepts/context', destination: '/how-it-works/context', permanent: true },
      // Phase 138 — 4 explainer guides moved from /guides/ into /how-it-works/ to live
      // alongside the existing 4 conceptual pages they're closer in spirit to.
      { source: '/guides/embeddings', destination: '/how-it-works/embeddings', permanent: true },
      { source: '/guides/compression', destination: '/how-it-works/compression', permanent: true },
      { source: '/guides/smart-search', destination: '/how-it-works/smart-search', permanent: true },
      { source: '/guides/dynamic-model-loading', destination: '/how-it-works/dynamic-model-loading', permanent: true },
      { source: '/guides/clara', destination: '/how-it-works/compression', permanent: true },
      // Pure-hub pages removed — land direct hits on the first child instead of 404.
      { source: '/guides', destination: '/guides/models', permanent: true },
    ];
  },
};

const withMDX = require('@next/mdx')()

module.exports = withMDX(nextConfig)
