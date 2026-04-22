import { Check, Minus } from 'lucide-react';

export interface TierFeature {
  name: string;
  free: boolean | string;
  pro: boolean | string;
  category?: string;
  tooltip?: string;
}

export interface TierComparisonProps {
  className?: string;
}

const tiers = [
  {
    name: 'Free',
    price: '$0',
    period: 'forever',
    description: 'Get started with one project.',
    highlight: false,
  },
  {
    name: 'Pro',
    price: '$79',
    period: 'one-time',
    description: 'Unlimited projects. All features. Available as $79 one-time or $7/mo.',
    highlight: true,
  },
];

const features: TierFeature[] = [
  // Indexing
  { category: 'Indexing & Search', name: 'Semantic code search', free: true, pro: true },
  { category: 'Indexing & Search', name: 'Context assembly with citations', free: true, pro: true },
  { category: 'Indexing & Search', name: 'Structural Code Graph (imports, calls, symbol graphs)', free: false, pro: true },
  { category: 'Indexing & Search', name: 'Incremental rebuild on file change', free: false, pro: true },

  // Projects
  { category: 'Projects', name: 'Active projects', free: '1', pro: 'Unlimited' },
  { category: 'Projects', name: 'Real-time file watcher', free: false, pro: true },
  { category: 'Projects', name: 'Multi-repo agent context', free: false, pro: true },

  // IDE & MCP
  { category: 'IDE Integration', name: 'MCP server (Cursor, Windsurf, VS Code, Claude Desktop)', free: true, pro: true },
  { category: 'IDE Integration', name: 'Full MCP tool suite', free: 'Basic', pro: true },

  // Privacy & Runtime
  { category: 'Privacy & Runtime', name: '100% local — no cloud upload', free: true, pro: true },
  { category: 'Privacy & Runtime', name: 'Optional Ollama for local reasoning', free: true, pro: true },
  { category: 'Privacy & Runtime', name: 'Optional cloud LLM (BYOK)', free: true, pro: true },

  // License
  { category: 'License', name: 'License type', free: 'Free forever', pro: 'One-time ($79) or monthly ($7/mo)' },
  { category: 'License', name: 'Offline activation', free: false, pro: true },
];

export const tierComparisonFeatures = features;

function CellValue({ value }: { value: boolean | string }) {
  if (value === true) {
    return (
      <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-success/15 text-success">
        <Check className="w-4 h-4" strokeWidth={3} />
      </span>
    );
  }
  if (value === false) {
    return (
      <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-surface-raised text-text-subtle">
        <Minus className="w-4 h-4" />
      </span>
    );
  }
  return <span className="text-sm font-medium text-text">{value}</span>;
}

export function TierComparison({ className = '' }: TierComparisonProps) {
  // Group features by category
  const categories: { label: string; items: TierFeature[] }[] = [];
  let current: { label: string; items: TierFeature[] } | null = null;

  for (const f of features) {
    if (f.category && (!current || current.label !== f.category)) {
      current = { label: f.category, items: [] };
      categories.push(current);
    }
    current?.items.push(f);
  }

  return (
    <div className={`w-full ${className}`}>
      {/* Header row */}
      <div className="grid grid-cols-[1fr_120px_120px] md:grid-cols-[1fr_160px_160px] gap-0 mb-2">
        <div />
        {tiers.map((tier) => (
          <div
            key={tier.name}
            className={`text-center px-3 py-6 rounded-t-xl ${
              tier.highlight
                ? 'bg-primary/10 border border-b-0 border-primary/25'
                : 'bg-surface-raised border border-b-0 border-border'
            }`}
          >
            <div className="text-lg font-bold text-text">{tier.name}</div>
            <div className="mt-1">
              <span className={`text-2xl font-bold ${tier.highlight ? 'text-primary' : 'text-text'}`}>
                {tier.price}
              </span>
              <span className="text-xs text-text-muted ml-1">/{tier.period}</span>
            </div>
            <div className="mt-2 text-xs text-text-muted leading-snug">{tier.description}</div>
          </div>
        ))}
      </div>

      {/* Feature rows grouped by category */}
      {categories.map((cat) => (
        <div key={cat.label}>
          {/* Category header */}
          <div className="grid grid-cols-[1fr_120px_120px] md:grid-cols-[1fr_160px_160px] gap-0">
            <div className="px-4 py-3 bg-surface-raised border-y border-border">
              <span className="text-xs font-bold uppercase tracking-wider text-text-muted">{cat.label}</span>
            </div>
            {tiers.map((tier) => (
              <div
                key={tier.name}
                className={`border-y px-3 py-3 ${
                  tier.highlight ? 'border-primary/25 bg-primary/5' : 'border-border bg-surface-raised'
                }`}
              />
            ))}
          </div>

          {/* Feature rows */}
          {cat.items.map((feature, i) => (
            <div
              key={feature.name}
              className={`grid grid-cols-[1fr_120px_120px] md:grid-cols-[1fr_160px_160px] gap-0 ${
                i % 2 === 0 ? 'bg-surface' : 'bg-background'
              }`}
            >
              <div className="px-4 py-3 text-sm text-text border-b border-border/50 flex items-center">
                {feature.name}
              </div>
              {[feature.free, feature.pro].map((value, j) => (
                <div
                  key={j}
                  className={`px-3 py-3 flex items-center justify-center border-b ${
                    tiers[j].highlight
                      ? 'border-primary/15 bg-primary/[0.03]'
                      : 'border-border/50'
                  }`}
                >
                  <CellValue value={value} />
                </div>
              ))}
            </div>
          ))}
        </div>
      ))}

      {/* Bottom CTA row */}
      <div className="grid grid-cols-[1fr_120px_120px] md:grid-cols-[1fr_160px_160px] gap-0">
        <div />
        {tiers.map((tier) => (
          <div
            key={tier.name}
            className={`text-center px-3 py-5 rounded-b-xl ${
              tier.highlight
                ? 'bg-primary/10 border border-t-0 border-primary/25'
                : 'bg-surface-raised border border-t-0 border-border'
            }`}
          >
            <span
              className={`inline-block text-sm font-semibold px-4 py-2 rounded-lg transition-colors cursor-pointer ${
                tier.highlight
                  ? 'bg-primary text-white hover:bg-primary-hover'
                  : 'bg-surface border border-border text-text hover:bg-surface-raised'
              }`}
            >
              {tier.highlight ? 'Get Pro' : 'Download Free'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
