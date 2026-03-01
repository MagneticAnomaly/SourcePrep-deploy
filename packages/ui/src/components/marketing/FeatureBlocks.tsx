import { Badge, Card, Flex, Text } from '@tremor/react';
import { 
  Search, GitBranch, Zap, Lock, RefreshCw, Plug, 
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
      className="rounded-2xl border border-primary/30 bg-surface p-6"
      style={{ boxShadow: '0 0 70px -10px color-mix(in srgb, var(--primary) 20%, transparent)' }}
    >
      {features.map((feature) => (
        <div
          key={feature.title}
          className="flex gap-6 items-start px-10 py-8"
        >
          <div className="flex-shrink-0 w-16 h-16 rounded-xl bg-surface-raised border border-border-subtle flex items-center justify-center text-primary">
            {feature.icon}
          </div>
          <div className="flex-1">
            <Flex justifyContent="between" alignItems="start">
              <h3 className="text-lg font-mono font-medium text-text">{feature.title}</h3>
              {feature.badge && <Badge color="blue">{feature.badge}</Badge>}
            </Flex>
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
  {
    icon: <Activity className="w-8 h-8" />,
    title: 'AutoAudit V2 — Autonomous Codebase Health',
    description: 'Transform your codebase intelligence into an active taskmaster. Run zero-config audits that map architecture bottlenecks and tech debt. Select a finding, click "Copy AI Command", and instantly hand off the context assembly to Cursor or Windsurf for a perfect refactor.',
    badge: 'New',
    highlight: true,
  },
  {
    icon: <Search className="w-8 h-8" />,
    title: 'Semantic + Structural Search',
    description: 'Ask "where is the auth middleware?" and get ranked results in under 100 ms. Built-in ONNX embeddings (nomic-embed-text) work out of the box — or connect Ollama or a cloud API like OpenAI if you prefer an alternative model.',
    badge: 'Built-in',
    highlight: true,
  },
  {
    icon: <GitBranch className="w-8 h-8" />,
    title: 'Structural Code Graph',
    description: 'Goes beyond vector search. A Rust-powered engine maps imports, call graphs, and symbol hierarchies across your entire monorepo — so your AI sees how 100k files connect.',
    badge: 'Built-in',
    highlight: true,
  },
  {
    icon: <Brain className="w-8 h-8" />,
    title: 'Graph Enrichment',
    description: 'A 9-stage pipeline that deepens understanding over time. Rust builds the structural skeleton, a Fast model catalogues every file, then a Thinking model reasons about each node in graph context — adding domain tags, architecture layers, and doc↔code cross-references. An understanding score (0.0–1.0) tracks how well the system comprehends each file, decaying when code changes and rising as knowledge crystallizes.',
    badge: 'Pro',
    href: 'https://docs.codrag.io/concepts/graph-enrichment',
    external: true,
  },
  {
    icon: <Waypoints className="w-8 h-8" />,
    title: 'Smarter Retrieval — The Atlas Routes Every Query',
    description: 'CoDRAG maps your codebase into subsystem segments at build time. When your AI asks for context, the Atlas routes the query to the right subsystem first — so the trace graph search is scoped before it starts. Better results. No extra tokens.',
    badge: 'New',
    highlight: true,
  },
  {
    icon: <Zap className="w-8 h-8" />,
    title: 'Instant Context Assembly',
    description: 'One call assembles citation-rich context for any LLM. Budget-aware chunking fits the right code into your prompt window — even for massive codebases and sprawling doc trees.',
  },
  {
    icon: <SlidersHorizontal className="w-8 h-8" />,
    title: 'Path Weights — You Steer the Signal',
    description: 'Boost docs/style-guide.md to 1.5× so your design rules always surface first. Dial down src/components/ui/ to 0.5× to lower the volume on generic components. Hierarchical, instant, no rebuild required.',
    badge: 'New',
    highlight: true,
  },
  {
    icon: <Shrink className="w-8 h-8" />,
    title: 'Smart Context Compression',
    description: 'Two built-in engines work together: code files are structurally compressed (3–20×) — keeping full source for top results, signatures for mid-relevance, and names for the rest. Documentation is compressed with a lightweight language model that preserves meaning while removing filler. No GPU required.',
    badge: 'Built-in',
  },
  {
    icon: <Lock className="w-8 h-8" />,
    title: 'Runs on Your Machine',
    description: 'Your code index stays on localhost. Use the built-in local models for zero network traffic, or connect to a cloud provider (BYOK) for enhanced trace understanding — you\'re in control.',
  },
  {
    icon: <RefreshCw className="w-8 h-8" />,
    title: 'Always-Fresh Index',
    description: 'A real-time file watcher detects edits and rebuilds incrementally in Rust — so your search results and AI context are never stale, even across thousands of files.',
  },
  {
    icon: <Plug className="w-8 h-8" />,
    title: 'Works With Every AI Tool',
    description: 'Native MCP integration means CoDRAG plugs directly into Cursor, Windsurf, VS Code, and Claude Desktop — no config gymnastics.',
    badge: 'MCP',
  },
  {
    icon: <Shield className="w-8 h-8" />,
    title: 'Privacy-First & Cloud-Ready',
    description: 'Run 100% locally with zero network traffic, or seamlessly plug in your preferred cloud AI provider (BYOK). Every embedding, search, and compression step is configurable and auditable.',
  },
  {
    icon: <Users className="w-8 h-8" />,
    title: 'Team Sync — Build Once, Share Instantly',
    description: 'A headless Docker image runs the full enrichment pipeline in your CI/CD on every push. The enriched trace graph is uploaded to S3-compatible storage. Every developer downloads it instantly — only their uncommitted changes are re-enriched locally.',
    badge: 'Team',
    href: 'https://docs.codrag.io/guides/team-sync',
    external: true,
  },
];

export const marketingFeatures: Feature[] = [
  {
    icon: <AlertTriangle className="w-8 h-8" />,
    title: 'The Problem: Large Codebases Break AI Context',
    description: 'Monorepos with 100k files. Thousands of markdown docs. AI tools grab random files without understanding how code connects — and their context windows overflow with noise. You waste time re-explaining architecture and pasting missing context.',
    highlight: true,
  },
  {
    icon: <Lightbulb className="w-8 h-8" />,
    title: 'The Fix: Index Everything, Control What Surfaces',
    description: 'CoDRAG\'s Rust engine indexes your entire codebase — semantics, symbols, and call graphs — then you steer what matters with path weights. Boost core modules, suppress vendor noise, and smart compression fits 3–20× more signal into every prompt. Every query gets exactly the right context, automatically.',
  },
  {
    icon: <TrendingUp className="w-8 h-8" />,
    title: 'The Result: AI That Understands Your Architecture',
    description: 'More relevant suggestions, fewer corrections, faster iteration — even on the largest codebases and doc trees. Built-in embeddings, structural code graph, deep reasoning with understanding scores, codebase atlas routing, path weights, and smart context compression work together so your AI finally sees the whole picture.',
  },
];
