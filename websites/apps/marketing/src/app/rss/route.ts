import { NextResponse } from 'next/server';

const SITE_URL = 'https://runprep.io';

const POSTS = [
  {
    slug: 'why-structural-context-matters',
    title: 'Why Structural Context Matters for AI Coding Tools',
    excerpt: 'AI assistants already index your code — but they grab files, not relationships. Here\'s why the structural layer changes everything.',
    date: '2026-03-01',
    author: 'RunPrep Team',
  },
  {
    slug: 'introducing-code-graph',
    title: 'Introducing the Code Graph',
    excerpt: 'Vector search finds similar text. The Code Graph maps how code connects — imports, calls, symbol hierarchies.',
    date: '2026-02-15',
    author: 'Engineering',
  },
  {
    slug: 'mcp-the-universal-connector',
    title: 'MCP: The Universal Connector',
    excerpt: 'How the Model Context Protocol lets RunPrep integrate with Cursor, Windsurf, VS Code, and Claude Code.',
    date: '2026-02-01',
    author: 'Integration',
  },
];

export async function GET() {
  const feed = `<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>RunPrep Blog</title>
    <link>${SITE_URL}/blog</link>
    <description>Notes on the intersection of human creativity and machine intelligence.</description>
    <language>en-us</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <atom:link href="${SITE_URL}/rss" rel="self" type="application/rss+xml" />
    ${POSTS.map((post) => `
    <item>
      <title><![CDATA[${post.title}]]></title>
      <link>${SITE_URL}/blog/${post.slug}</link>
      <guid isPermaLink="true">${SITE_URL}/blog/${post.slug}</guid>
      <description><![CDATA[${post.excerpt}]]></description>
      <pubDate>${new Date(post.date).toUTCString()}</pubDate>
      <author>${post.author}</author>
    </item>`).join('')}
  </channel>
</rss>`;

  return new NextResponse(feed, {
    headers: {
      'Content-Type': 'application/xml',
      'Cache-Control': 'public, s-maxage=3600, stale-while-revalidate=86400',
    },
  });
}
