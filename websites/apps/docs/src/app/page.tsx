"use client";

import { Rocket, LayoutDashboard, Terminal, Plug, Wrench, LifeBuoy, BookOpen } from 'lucide-react';

const docFeatures = [
  {
    icon: <Rocket className="w-8 h-8" />,
    title: 'Getting Started',
    description: 'The trust loop: add → build → search → context.',
    href: '/getting-started',
  },
  {
    icon: <LayoutDashboard className="w-8 h-8" />,
    title: 'Dashboard UI',
    description: 'Configure projects, builds, and context settings.',
    href: '/dashboard',
  },
  {
    icon: <Terminal className="w-8 h-8" />,
    title: 'CLI Reference',
    description: 'Commands and flags for extracting structural context.',
    href: '/cli',
  },
  {
    icon: <Plug className="w-8 h-8" />,
    title: 'MCP Integration',
    description: 'Use RunPrep from Cursor/Windsurf via MCP.',
    href: '/mcp',
  },
  {
    icon: <BookOpen className="w-8 h-8" />,
    title: 'Guides',
    description: 'Embeddings, context compression, path weights, and more.',
    href: '/guides',
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
    description: 'Ticketing, bugs, questions, and security reporting.',
    href: 'https://runprep.io/support',
    external: true,
  },
];

export default function Page() {
  return (
    <div className="space-y-12 max-w-3xl mx-auto pt-6">
      <div>
        <h1 className="text-4xl font-bold tracking-tight mb-4">RunPrep Documentation</h1>
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
