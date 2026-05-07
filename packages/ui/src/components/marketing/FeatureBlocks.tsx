import { Badge, Card, Text } from '@tremor/react';
import {
  Search, GitBranch, RefreshCw, Plug,
  AlertTriangle, Lightbulb, TrendingUp, SlidersHorizontal, Shrink, Brain, Shield, Waypoints, Users, Activity,
  BookOpen, MessageSquare
} from 'lucide-react';

export interface Feature {
  icon: React.ReactNode;
  title: string;
  description: string;
  badge?: string;
  highlight?: boolean;
  href?: string;
  external?: boolean;
}

export interface FeatureBlocksProps {
  features: Feature[];
  variant?: 'cards' | 'list' | 'bento';
}

export function FeatureBlocks({ features, variant = 'cards' }: FeatureBlocksProps) {
  if (variant === 'bento') {
    return <BentoGrid features={features} />;
  }
  if (variant === 'list') {
    return <FeatureList features={features} />;
  }
  return <FeatureCards features={features} />;
}

function FeatureCards({ features }: { features: Feature[] }) {
  return (
    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
      {features.map((feature) => {
        const CardContent = (
          <>
            <div className="flex items-start justify-between">
              <span className="text-primary">{feature.icon}</span>
            </div>
            <h3 className="mt-4 text-lg font-mono font-medium text-text">{feature.title}</h3>
            <Text className="mt-2 text-text-muted">{feature.description}</Text>
          </>
        );

        const className = `border bg-surface transition-all hover:shadow-lg hover:-translate-y-1 block h-full p-6 rounded-lg text-left ${feature.highlight
          ? 'border-primary/50 bg-gradient-to-br from-primary/5 to-transparent'
          : 'border-border'
          }`;

        if (feature.href) {
          return (
            <a
              key={feature.title}
              href={feature.href}
              target={feature.external ? "_blank" : undefined}
              rel={feature.external ? "noopener noreferrer" : undefined}
              className={`${className} cursor-pointer no-underline`}
            >
              {CardContent}
            </a>
          );
        }

        return (
          <Card
            key={feature.title}
            className={className}
          >
            {CardContent}
          </Card>
        );
      })}
    </div>
  );
}

function FeatureList({ features }: { features: Feature[] }) {
  return (
    <div
      className="rounded-2xl border border-primary/30 bg-surface p-2 sm:p-6"
      style={{ boxShadow: '0 0 70px -10px color-mix(in srgb, var(--primary) 20%, transparent)' }}
    >
      {features.map((feature) => (
        <div
          key={feature.title}
          className="flex flex-col sm:flex-row gap-4 sm:gap-6 items-start px-4 py-6 sm:px-10 sm:py-8"
        >
          <div className="flex-shrink-0 w-14 h-14 sm:w-16 sm:h-16 rounded-xl bg-surface-raised border border-border-subtle flex items-center justify-center text-primary [&>svg]:w-6 [&>svg]:h-6 sm:[&>svg]:w-8 sm:[&>svg]:h-8">
            {feature.icon}
          </div>
          <div className="flex-1 w-full">
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-2 sm:gap-0">
              <h3 className="text-lg font-mono font-medium text-text">{feature.title}</h3>
              {feature.badge && <Badge color="blue">{feature.badge}</Badge>}
            </div>
            <Text className="mt-2 text-text-muted leading-relaxed">{feature.description}</Text>
          </div>
        </div>
      ))}
    </div>
  );
}

function BentoGrid({ features }: { features: Feature[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 auto-rows-[180px]">
      {features.map((feature, i) => {
        const isLarge = i === 0 || i === 3;
        return (
          <div
            key={feature.title}
            className={`rounded-2xl border p-6 transition-all hover:shadow-lg ${feature.highlight
              ? 'border-primary/50 bg-gradient-to-br from-primary/10 to-primary/5'
              : 'border-border bg-surface'
              } ${isLarge ? 'col-span-2 row-span-2' : ''}`}
          >
            <div className={isLarge ? 'text-primary [&>svg]:w-12 [&>svg]:h-12' : 'text-primary [&>svg]:w-8 [&>svg]:h-8'}>
              {feature.icon}
            </div>
            <h3 className={`mt-4 font-heading font-medium text-text ${isLarge ? 'text-2xl' : 'text-lg'}`}>
              {feature.title}
            </h3>
            <Text className={`mt-2 text-text-muted ${isLarge ? '' : 'text-sm line-clamp-2'}`}>
              {feature.description}
            </Text>
            {feature.badge && (
              <Badge color="blue" className="mt-3">
                {feature.badge}
              </Badge>
            )}
          </div>
        );
      })}
    </div>
  );
}

export const prepFeatures: Feature[] = [
  // Tier 1: Structural Intelligence
  {
    icon: <GitBranch className="w-8 h-8" />,
    title: 'Structural Code Graph',
    description: 'Goes beyond vector search. A Rust engine traces your codebase to map imports, call graphs, and symbol hierarchies — giving agents the what, why, when, and how.',
    badge: 'Built-in',
    highlight: true,
  },
  {
    icon: <Brain className="w-8 h-8" />,
    title: 'Graph Enrichment Pipeline',
    description: 'A multi-stage pipeline deepens understanding over time — from Rust parsing to deep LLM reasoning to architectural synthesis. Supports swarm mode for parallel LLM processing.',
    badge: 'Built-in',
    href: 'https://docs.sourceprep.io/concepts/graph-enrichment',
  },
  {
    icon: <Activity className="w-8 h-8" />,
    title: 'Audit Enrichment',
    description: 'Supercharge your existing linters. Feed findings from ruff, semgrep, or CodeQL into SourcePrep and get them back enriched with structural context — dependent count, hub status, risk score, and related concepts. Outputs SARIF for CI integration.',
    highlight: true,
  },

  // Tier 2: Agentic Leverage
  {
    icon: <Users className="w-8 h-8" />,
    title: 'Role-Aware Context',
    description: 'Different agents need different slices. A security reviewer sees auth boundaries; a UI agent sees design tokens. SourcePrep shapes context delivery around the role of the agent asking.',
    highlight: true,
  },
  {
    icon: <Waypoints className="w-8 h-8" />,
    title: 'Atlas Routing',
    description: 'Your codebase is mapped into subsystem segments at build time. When an agent asks for context, the Atlas routes the query to the correct architectural neighborhood before search begins.',
    highlight: true,
  },
  {
    icon: <SlidersHorizontal className="w-8 h-8" />,
    title: 'Path Weights',
    description: 'Fine-grained signal control. Boost your style-guide to 1.5× or suppress vendor directories to 0.5×. You steer what your agents prioritize.',
  },
  {
    icon: <Search className="w-8 h-8" />,
    title: 'Instant Context Assembly',
    description: 'One call assembles citation-rich, graph-backed context for any LLM. Budget-aware chunking fits the right code into your prompt window — even for sprawling repositories.',
  },

  // Tier 3: The Enablers
  {
    icon: <Shrink className="w-8 h-8" />,
    title: 'Smart Context Compression',
    description: 'Intelligently shrinks the payload without losing structural integrity. Full source for top results, signatures for mid-relevance — delivering 3–20× more signal per token.',
    badge: 'Built-in',
  },
  {
    icon: <Shield className="w-8 h-8" />,
    title: 'Any LLM, Your Choice',
    description: 'Works with Ollama Kimi2.6 (recommended), local models via Ollama, or frontier APIs like Claude and GPT. Swarm mode runs multiple LLM workers in parallel for faster enrichment.',
  },
  {
    icon: <RefreshCw className="w-8 h-8" />,
    title: 'Always-Fresh Index',
    description: 'A real-time file watcher detects edits and rebuilds incrementally in Rust — so search results and AI context are never stale.',
  },
  {
    icon: <Plug className="w-8 h-8" />,
    title: 'Native MCP Server',
    description: 'SourcePrep is an MCP server. Connect it to Claude Code, Antigravity, Cursor, VS Code, or any tool that supports the Model Context Protocol.',
    badge: 'MCP',
  },

  // Tier 4: Knowledge Persistence
  {
    icon: <MessageSquare className="w-8 h-8" />,
    title: 'Persistent Agent Memory',
    description: 'Observations about decisions, bugs, and patterns persist across sessions — linked to specific files. When those files change, linked observations are flagged [STALE] so your AI knows to re-evaluate.',
    highlight: true,
  },
  {
    icon: <BookOpen className="w-8 h-8" />,
    title: 'Concept System',
    description: 'Record the "why" behind your architecture — business rationale, design decisions, constraints. Concepts have testable assertions that auto-generate immune system rules, catching violations before they ship.',
    highlight: true,
  },
];

export const marketingFeatures: Feature[] = [
  {
    icon: <AlertTriangle className="w-8 h-8" />,
    title: 'The Problem: Naive search finds "Where" and has to figure out the rest',
    description: 'Large repos with 100k files with thousands or many large markdown docs can be challenge. Basic vector search grabs random files without understanding how code connects, flooding your agent\'s context window with noise and causing hallucinations.',
    highlight: true,
  },
  {
    icon: <Lightbulb className="w-8 h-8" />,
    title: 'The Fix: Structural Tracing + Enrichment',
    description: 'SourcePrep\'s Rust engine traces your entire codebase — mapping imports, call graphs, symbols, and hierarchies. Then it iterates though enriching it\'s understanding. It delivers structurally-aware context precisely scoped an agent\'s request or for each agent\'s role.',
  },
  {
    icon: <TrendingUp className="w-8 h-8" />,
    title: 'The Result: Agents That Understand Architecture and Concepts',
    description: 'Connect the SourcePrep MCP server to Claude Code, Antigravity, or Cursor and watch your AI instantly understand the codebase. By providing the "what, why, when, and how", agents get the structural awareness they need to make grep more stategic, your audit infomed or design more structually aware.',
  },
];
