const fs = require('fs');
const path = require('path');

const pages = {
  pricing: { title: 'Pricing', description: 'Transparent pricing for SourcePrep. Free tier available, or get a Pro perpetual license with zero cloud token markup.', path: '/pricing' },
  download: { title: 'Download', description: 'Download the SourcePrep desktop app for macOS, Windows, and Linux. Plug it into Cursor, Windsurf, or Claude Code via MCP.', path: '/download' },
  security: { title: 'Security & Privacy', description: 'SourcePrep is local-first by default. Your codebase stays on your machine. Learn about our zero-telemetry architecture.', path: '/security' },
  faq: { title: 'FAQ', description: 'Frequently asked questions about SourcePrep, local RAG, token budgets, and MCP integration.', path: '/faq' },
  about: { title: 'About', description: 'The mission behind SourcePrep: bringing determinism and structural understanding back to AI coding tools.', path: '/about' },
  changelog: { title: 'Changelog', description: 'Latest updates, features, and improvements to the SourcePrep engine and MCP server.', path: '/changelog' },
  community: { title: 'Community', description: 'Join the SourcePrep community of developers building the next generation of AI-assisted software.', path: '/community' },
  contact: { title: 'Contact Us', description: 'Get in touch with the SourcePrep team for support, enterprise inquiries, or general questions.', path: '/contact' },
  terms: { title: 'Terms of Service', description: 'Terms of service and licensing agreement for SourcePrep.', path: '/terms' },
  privacy: { title: 'Privacy Policy', description: 'SourcePrep privacy policy. We believe your code is your business.', path: '/privacy' },
  careers: { title: 'Careers', description: 'Work with us to build the ultimate local codebase context engine.', path: '/careers' },
  support: { title: 'Support', description: 'Get help with SourcePrep installation, usage, and troubleshooting.', path: '/support' },
  blog: { title: 'Blog', description: 'Articles, tutorials, and deep-dives on local RAG, context windows, and AI-assisted engineering.', path: '/blog' },
};

Object.entries(pages).forEach(([route, meta]) => {
  const dir = path.join(__dirname, '../src/app', route);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  const content = `import { constructMetadata } from '../metadata-helper';

export const metadata = constructMetadata({
  title: '${meta.title}',
  description: '${meta.description}',
  path: '${meta.path}',
});

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
`;
  fs.writeFileSync(path.join(dir, 'layout.tsx'), content);
});
console.log('Layouts generated');
