import { Badge, Card, Flex, Text, Title } from '@tremor/react';
import { 
  Search, GitBranch, Zap, Lock, RefreshCw, Plug, 
  AlertTriangle, Lightbulb, TrendingUp, SlidersHorizontal, Shrink, Brain
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
              {feature.badge && (
                <Badge color="blue" size="xs">
                  {feature.badge}
                </Badge>
              )}
            </div>
            <Title className="mt-4 text-text">{feature.title}</Title>
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
    <div className="space-y-6">
      {features.map((feature) => (
        <div
          key={feature.title}
          className={`flex gap-6 items-start p-6 rounded-xl border transition-all hover:shadow-md ${
            feature.highlight
              ? 'border-primary/50 bg-primary/5'
              : 'border-border bg-surface'
          }`}
        >
          <div className="flex-shrink-0 w-16 h-16 rounded-xl bg-surface-raised border border-border-subtle flex items-center justify-center text-primary">
            {feature.icon}
          </div>
          <div className="flex-1">
            <Flex justifyContent="between" alignItems="start">
              <Title className="text-text">{feature.title}</Title>
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
            <Title className={`mt-4 text-text ${isLarge ? 'text-2xl' : 'text-base'}`}>
              {feature.title}
            </Title>
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
    icon: <Search className="w-8 h-8" />,
    title: 'Semantic + Structural Search',
    description: 'Ask "where is the auth middleware?" and get ranked results in under 100 ms. Built-in ONNX embeddings (nomic-embed-text) work out of the box — no LLM or API key required. Connect Ollama or a cloud API if you prefer an alternative model.',
    badge: 'Built-in',
    highlight: true,
  },
  {
    icon: <GitBranch className="w-8 h-8" />,
    title: 'Structural Code Graph',
    description: 'Goes beyond vector search. A Rust-powered engine maps imports, call graphs, and symbol hierarchies across your entire monorepo — so your AI sees how 100k files connect.',
    badge: 'Pro',
    highlight: true,
  },
  {
    icon: <Brain className="w-8 h-8" />,
    title: 'Graph Enrichment',
    description: 'A multi-pass pipeline that deepens understanding over time. Rust builds the structural skeleton, a 3b model catalogues every file, then a 14b model adds domain tags, architecture layers, and doc↔code cross-references — with epistemic scoring that measures how well each file is understood.',
    badge: 'Pro',
    href: 'https://docs.codrag.io/concepts/graph-enrichment',
    external: true,
  },
  {
    icon: <Zap className="w-8 h-8" />,
    title: 'Instant Context Assembly',
    description: 'One call assembles citation-rich context for any LLM. Budget-aware chunking fits the right code into your prompt window — even for massive codebases and sprawling doc trees.',
  },
  {
    icon: <SlidersHorizontal className="w-8 h-8" />,
    title: 'Path Weights — You Steer the Signal',
    description: 'Boost src/core/ to 1.5× so your domain logic always surfaces first. Set vendor/ to zero to silence noise. Hierarchical, instant, no rebuild required.',
    badge: 'New',
    highlight: true,
  },
  {
    icon: <Shrink className="w-8 h-8" />,
    title: '10–16× Context Compression',
    description: 'CLaRa compresses retrieved context before it reaches your LLM — fitting more relevant signal into your prompt window. Query-aware, best-effort, runs locally.',
    badge: 'CLaRa',
  },
  {
    icon: <Lock className="w-8 h-8" />,
    title: 'Runs 100% on Your Machine',
    description: 'Your code never leaves localhost. No cloud upload, no telemetry. Embeddings, search, and compression all run locally — zero network traffic by default.',
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
    description: 'CoDRAG\'s Rust engine indexes your entire codebase — semantics, symbols, and call graphs — then you steer what matters with path weights. Boost core modules, suppress vendor noise, compress the rest with CLaRa. Every prompt gets exactly the right context, automatically.',
  },
  {
    icon: <TrendingUp className="w-8 h-8" />,
    title: 'The Result: AI That Understands Your Architecture',
    description: 'More relevant suggestions, fewer corrections, faster iteration — even on the largest codebases and doc trees. Built-in embeddings, structural code graph, multi-pass enrichment with epistemic scoring, path weights, and 10–16× compression work together so your AI finally sees the whole picture.',
  },
];
