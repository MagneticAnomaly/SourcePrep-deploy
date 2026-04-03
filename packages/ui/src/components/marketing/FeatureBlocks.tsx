import { Badge, Card, Text } from '@tremor/react';
import { 
  Search, GitBranch, RefreshCw, Plug, 
  AlertTriangle, Lightbulb, TrendingUp, SlidersHorizontal, Shrink, Brain, Shield, Waypoints, Users, Activity
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

        const className = `border bg-surface transition-all hover:shadow-lg hover:-translate-y-1 block h-full p-6 rounded-lg text-left ${
          feature.highlight
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
            className={`rounded-2xl border p-6 transition-all hover:shadow-lg ${
              feature.highlight
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

export const codragFeatures: Feature[] = [
  // Tier 1: Epistemic Understanding
  {
    icon: <GitBranch className="w-8 h-8" />,
    title: 'Structural Code Graph',
    description: 'Goes beyond vector search. A Rust engine meticulously traces your DB and codebase to map imports, call graphs, and symbol hierarchies — giving agents the what, why, when, and how.',
    badge: 'Built-in',
    highlight: true,
  },
  {
    icon: <Brain className="w-8 h-8" />,
    title: 'Graph Enrichment',
    description: 'A 9-stage pipeline that deepens understanding over time. A Fast model catalogues every file, then a Thinking model reasons about each node in graph context — crystallizing knowledge as your architecture evolves.',
    badge: 'Pro',
    href: 'https://docs.codrag.io/concepts/graph-enrichment',
    external: true,
  },
  {
    icon: <Activity className="w-8 h-8" />,
    title: 'AutoAudit V2 — Autonomous Codebase Health',
    description: 'Transform static codebase intelligence into an active taskmaster. Run audits that map architecture bottlenecks and tech debt, then instantly hand off the context assembly to agentic tools for a perfect refactor.',
    badge: 'New',
    highlight: true,
  },

  // Tier 2: Agentic Leverage
  {
    icon: <Users className="w-8 h-8" />,
    title: 'Role-Aware Context — The right view for every agent',
    description: 'Different agents need different slices of your codebase. A security reviewer sees auth boundaries; a UI agent sees design tokens. CoDRAG automatically shapes context delivery around the role of the agent asking.',
    badge: 'New',
    highlight: true,
  },
  {
    icon: <Waypoints className="w-8 h-8" />,
    title: 'Smarter Retrieval — Atlas Routing',
    description: 'CoDRAG maps your codebase into subsystem segments at build time. When your AI asks for context, the Atlas routes the query to the correct architectural neighborhood before the search even starts.',
    badge: 'New',
    highlight: true,
  },
  {
    icon: <SlidersHorizontal className="w-8 h-8" />,
    title: 'Path Weights — Sophisticated Signal Steering',
    description: 'Elegant signal steering for power users. Boost your style-guide to 1.5× or dial down vendor directories to 0.5×. You control the priority of the structural context.',
    badge: 'New',
    highlight: true,
  },
  {
    icon: <Search className="w-8 h-8" />,
    title: 'Instant Context Assembly',
    description: 'One call assembles citation-rich, graph-backed context for any LLM. Budget-aware chunking fits the exact right code into your prompt window — even for sprawling repositories.',
  },

  // Tier 3: The Enablers
  {
    icon: <Shrink className="w-8 h-8" />,
    title: 'Smart Context Compression',
    description: 'Intelligently shrinks the payload without losing structural integrity. Code files are compressed keeping full source for top results and signatures for mid-relevance, delivering significantly higher signal per token.',
    badge: 'Built-in',
  },
  {
    icon: <Shield className="w-8 h-8" />,
    title: 'Privacy by Design — Sovereign Context',
    description: 'Your codebase index is built and managed completely locally. When it\'s time for AI reasoning, you control the network: route context securely to Ollama Cloud (recommended), or bring your own frontier APIs.',
  },
  {
    icon: <RefreshCw className="w-8 h-8" />,
    title: 'Always-Fresh Index',
    description: 'A real-time file watcher detects edits and rebuilds incrementally in Rust — so your search results and AI context are never stale.',
  },
  {
    icon: <Plug className="w-8 h-8" />,
    title: 'Native MCP Integration',
    description: 'Plug-and-play connectivity. CoDRAG natively connects to Paperclip, Cursor, Windsurf, VS Code, and Claude Desktop to supercharge any agentic workflow.',
    badge: 'MCP',
  },
  {
    icon: <Users className="w-8 h-8" />,
    title: 'Team Sync — Build Once, Share Instantly',
    description: 'A headless Docker image runs the full enrichment pipeline in CI/CD. The epistemic graph is uploaded to S3-compatible storage, letting every developer download instant context syncs.',
    badge: 'Team',
    href: 'https://docs.codrag.io/guides/team-sync',
    external: true,
  },
];

export const marketingFeatures: Feature[] = [
  {
    icon: <AlertTriangle className="w-8 h-8" />,
    title: 'The Problem: Naive Search Fails Agents',
    description: 'Monorepos with 100k files. Thousands of markdown docs. Basic vector search grabs random files without understanding how code connects, flooding your agent\'s context window with noise and causing hallucinations.',
    highlight: true,
  },
  {
    icon: <Lightbulb className="w-8 h-8" />,
    title: 'The Fix: Deep Epistemic Tracing',
    description: 'CoDRAG\'s engine traces your entire database and codebase — mapping semantics, symbols, and call hierarchies. It delivers a graph of structurally aware context, precisely scoped for the agent\'s specific role.',
  },
  {
    icon: <TrendingUp className="w-8 h-8" />,
    title: 'The Result: Agents With A Brain',
    description: 'Connect your autonomous tools to Paperclip and watch them instantly understand their tasks. By providing the "what, why, when, and how", CoDRAG gives your agents the sophisticated awareness they need to actually do the work.',
  },
];
