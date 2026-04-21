import { Badge, Card, Flex, Text, Title } from '@tremor/react';
import { 
  Search, GitBranch, Zap, Lock, RefreshCw, Plug, 
  AlertTriangle, Lightbulb, TrendingUp 
} from 'lucide-react';

interface Feature {
  icon: React.ReactNode;
  title: string;
  description: string;
  badge?: string;
  highlight?: boolean;
}

interface FeatureBlocksProps {
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
      {features.map((feature) => (
        <Card
          key={feature.title}
          className={`border bg-surface transition-all hover:shadow-lg hover:-translate-y-1 ${
            feature.highlight
              ? 'border-primary/50 bg-gradient-to-br from-primary/5 to-transparent'
              : 'border-border'
          }`}
        >
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
        </Card>
      ))}
    </div>
  );
}

function FeatureList({ features }: { features: Feature[] }) {
  return (
    <div className="space-y-6">
      {features.map((feature, i) => (
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

export const prepFeatures: Feature[] = [
  {
    icon: <Search className="w-8 h-8" />,
    title: 'Semantic Search',
    description: 'Find code by meaning, not just keywords. Ask questions like "where does authentication happen?" and get accurate results.',
    badge: 'Core',
    highlight: true,
  },
  {
    icon: <GitBranch className="w-8 h-8" />,
    title: 'Trace Index',
    description: 'Understand code relationships. See imports, calls, and symbol dependencies at a glance.',
    badge: 'Pro',
  },
  {
    icon: <Zap className="w-8 h-8" />,
    title: 'Instant Context',
    description: 'Assemble LLM-ready context in under 200ms. Perfect chunks with citations, every time.',
  },
  {
    icon: <Lock className="w-8 h-8" />,
    title: 'Local-First',
    description: 'Your code never leaves your machine. No cloud, no telemetry, no compromises on privacy.',
    highlight: true,
  },
  {
    icon: <RefreshCw className="w-8 h-8" />,
    title: 'Auto-Rebuild',
    description: 'File watcher keeps your index fresh. Edit code, get updated search results instantly.',
  },
  {
    icon: <Plug className="w-8 h-8" />,
    title: 'MCP Integration',
    description: 'Works seamlessly with Cursor, Windsurf, and any MCP-compatible IDE.',
    badge: 'New',
  },
  ];

export const marketingFeatures: Feature[] = [
  {
    icon: <AlertTriangle className="w-8 h-8" />,
    title: 'Problem: AI hallucinations from missing context',
    description: 'Your AI assistant makes mistakes because it can\'t see your entire codebase. Manual copy-pasting is slow and error-prone.',
    highlight: true,
  },
  {
    icon: <Lightbulb className="w-8 h-8" />,
    title: 'Solution: Semantic indexing + smart context',
    description: 'Prep builds a semantic understanding of your code and delivers exactly the right context to your AI tools.',
  },
  {
    icon: <TrendingUp className="w-8 h-8" />,
    title: 'Result: 60%+ fewer AI mistakes',
    description: 'Teams using Prep report dramatically fewer hallucinations and faster iteration cycles.',
    badge: 'Measured',
  },
];
