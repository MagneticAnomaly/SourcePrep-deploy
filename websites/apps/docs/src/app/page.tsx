"use client";

import { Rocket, LayoutDashboard, Terminal, Plug, Wrench, LifeBuoy, BookOpen, GitBranch } from 'lucide-react';

const docFeatures = [
  {
    icon: <Rocket className="w-8 h-8" />,
    title: 'Getting Started',
    description: 'Install SourcePrep, add a project, and run your first search.',
    href: '/getting-started',
  },
  {
    icon: <GitBranch className="w-8 h-8" />,
    title: 'Core Concepts',
    description: 'How indexing, the code graph, enrichment, and context assembly fit together.',
    href: '/concepts/indexing',
  },
  {
    icon: <LayoutDashboard className="w-8 h-8" />,
    title: 'Dashboard',
    description: 'Configurable workspace of panels for monitoring, search, and tuning.',
    href: '/dashboard',
  },
  {
    icon: <Plug className="w-8 h-8" />,
    title: 'MCP Integration',
    description: 'Connect SourcePrep to Claude Code, Cursor, Windsurf, Codex, and more.',
    href: '/mcp',
  },
  {
    icon: <Terminal className="w-8 h-8" />,
    title: 'CLI Reference',
    description: 'Commands and flags for managing the daemon and your indexes.',
    href: '/cli',
  },
  {
    icon: <BookOpen className="w-8 h-8" />,
    title: 'Embedding Models',
    description: 'Pick the embedding tier that fits your hardware (CPU, GPU, BYOK).',
    href: '/guides/embeddings',
  },
  {
    icon: <Wrench className="w-8 h-8" />,
    title: 'Troubleshooting',
    description: 'Fix common setup and build issues.',
    href: '/troubleshooting',
  },
  {
    icon: <LifeBuoy className="w-8 h-8" />,
    title: 'Support',
    description: 'Tickets, bug reports, and security disclosures.',
    href: 'https://sourceprep.io/support',
    external: true,
  },
];

export default function Page() {
  return (
    <div className="space-y-12 max-w-3xl mx-auto pt-6">
      <div>
        <h1 className="text-4xl font-bold tracking-tight mb-4">SourcePrep Documentation</h1>
        <p className="text-xl text-text-muted">
          Everything you need to build your epistemic graph, connect your AI tools, and get better output from every prompt.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {docFeatures.map((feature) => (
          <a
            key={feature.title}
            href={feature.href}
            target={(feature as any).external ? '_blank' : undefined}
            rel={(feature as any).external ? 'noopener noreferrer' : undefined}
            className="border border-border bg-surface rounded-lg p-6 text-left block no-underline transition-all hover:shadow-lg hover:-translate-y-1"
          >
            <span className="text-primary">{feature.icon}</span>
            <h3 className="mt-4 text-lg font-mono font-medium text-text">{feature.title}</h3>
            <p className="mt-2 text-text-muted">{feature.description}</p>
          </a>
        ))}
      </div>
    </div>
  );
}
