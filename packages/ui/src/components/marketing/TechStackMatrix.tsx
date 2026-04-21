import { Box, Cpu, Server, Layers, Search, GitBranch, Plug, Eye, SlidersHorizontal, Shrink, Gauge } from 'lucide-react';

export interface StackComponent {
  name: string;
  required: boolean;
  description: string;
  provides: string[];
  icon: React.ReactNode;
  tag?: string;
  accent?: string;
}

export interface TechStackMatrixProps {
  className?: string;
}

const stackComponents: StackComponent[] = [
  {
    name: 'RunPrep Engine',
    required: true,
    tag: 'One install — batteries included',
    accent: 'primary',
    icon: <Box className="w-6 h-6" />,
    description: 'The Rust-powered daemon runs entirely on your machine. It indexes codebases of any size — 500 files or 500,000 — with built-in local semantic embeddings. The core index requires no GPU, no cloud, and no external AI sidecars. You optionally plug in cloud LLMs just for reasoning.',
    provides: [
      'Built-in embeddings (nomic-embed-text via ONNX — no Ollama needed)',
      'Structural Code Graph (imports, calls, symbol graphs)',
      'Semantic + keyword + structural search in one engine',
      'Context assembly with source citations and budget control',
      'Path weights — boost core modules, suppress vendor and generated code',
      'MCP server for Cursor, Windsurf, VS Code, Claude Desktop',
      'Real-time file watcher with incremental rebuild',
    ],
  },
  {
    name: 'Smart Context Compression',
    required: false,
    tag: 'Built-in — dual-engine compression for code & docs',
    accent: 'success',
    icon: <Shrink className="w-6 h-6" />,
    description: 'Two compression engines, each optimized for what it compresses. Code files are structurally compressed — the engine understands functions, classes, and imports, so it keeps what matters and summarizes the rest (3–20×). Documentation and markdown are compressed with a lightweight language model that removes filler while preserving meaning. Both run on CPU, no GPU needed. Tier-adaptive: the compression level adjusts to your AI tool\'s context window.',
    provides: [
      '3–20× structural compression for code (understands your code\'s shape)',
      'Language-aware compression for docs and markdown (LLMLingua-2, ~2.4× at standard)',
      'Tier-adaptive — adjusts compression per client (Opus gets more detail, local models get tighter compression)',
      'Score-aware — high-relevance stays full, low-relevance compresses more',
      'Built-in — no GPU, no cloud, works via API, MCP, and dashboard',
    ],
  },
];

export const techStackComponents = stackComponents;

function RequiredBadge({ required, tag, accent }: { required: boolean; tag?: string; accent?: string }) {
  if (required) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-primary/15 text-primary border border-primary/25">
        <span className="w-1.5 h-1.5 rounded-full bg-primary" />
        {tag || 'Required'}
      </span>
    );
  }
  const isSuccess = accent === 'success';
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
      isSuccess
        ? 'bg-success/10 text-success border-success/25'
        : 'bg-surface-raised text-text-muted border-border'
    }`}>
      {tag || 'Optional'}
    </span>
  );
}

const capabilityIcons: Record<string, React.ReactNode> = {
  'Built-in embeddings': <Cpu className="w-3.5 h-3.5 text-primary flex-shrink-0" />,
  'Structural Code Graph': <GitBranch className="w-3.5 h-3.5 text-primary flex-shrink-0" />,
  'Context assembly': <Layers className="w-3.5 h-3.5 text-primary flex-shrink-0" />,
  'Path weights': <SlidersHorizontal className="w-3.5 h-3.5 text-primary flex-shrink-0" />,
  'MCP server': <Plug className="w-3.5 h-3.5 text-primary flex-shrink-0" />,
  'CLI for': <Server className="w-3.5 h-3.5 text-primary flex-shrink-0" />,
  'Real-time': <Eye className="w-3.5 h-3.5 text-primary flex-shrink-0" />,
  'Semantic +': <Search className="w-3.5 h-3.5 text-primary flex-shrink-0" />,
  '3–20×': <Shrink className="w-3.5 h-3.5 text-success flex-shrink-0" />,
  'Score-aware': <Search className="w-3.5 h-3.5 text-success flex-shrink-0" />,
  'Increases signal': <Gauge className="w-3.5 h-3.5 text-success flex-shrink-0" />,
  'Built-in': <Eye className="w-3.5 h-3.5 text-success flex-shrink-0" />,
  'Works via': <Plug className="w-3.5 h-3.5 text-success flex-shrink-0" />,
};

function getCapabilityIcon(text: string): React.ReactNode {
  for (const [prefix, icon] of Object.entries(capabilityIcons)) {
    if (text.startsWith(prefix)) return icon;
  }
  return <Layers className="w-3.5 h-3.5 text-text-subtle flex-shrink-0" />;
}

export function TechStackMatrix({ className = '' }: TechStackMatrixProps) {
  return (
    <div className={`w-full space-y-8 ${className}`}>
      {/* Callout */}
      <div className="p-5 rounded-xl bg-surface-raised border border-border">
        <p className="text-sm text-text-muted leading-relaxed">
          <span className="font-semibold text-text">RunPrep ships with everything you need.</span>{' '}
          The built-in embedding model (nomic-embed-text via ONNX) runs on CPU out of the box.
          Semantic search, structural code graph, and context assembly all work from a single install.
        </p>
      </div>

      {/* Stack cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {stackComponents.map((component) => (
          <div
            key={component.name}
            className={`flex flex-col rounded-xl border p-6 transition-all hover:shadow-lg ${
              component.required
                ? 'border-primary/30 bg-gradient-to-b from-primary/5 to-transparent shadow-sm'
                : component.accent === 'success'
                  ? 'border-success/30 bg-gradient-to-b from-success/5 to-transparent'
                  : 'border-border bg-surface'
            }`}
          >
            {/* Header */}
            <div className="flex items-start justify-between gap-3 mb-4">
              <div className={`p-2.5 rounded-lg ${
                component.required
                  ? 'bg-primary/15 text-primary'
                  : component.accent === 'success'
                    ? 'bg-success/15 text-success'
                    : 'bg-surface-raised text-text-muted'
              }`}>
                {component.icon}
              </div>
              <RequiredBadge required={component.required} tag={component.tag} accent={component.accent} />
            </div>

            {/* Name & description */}
            <h3 className="text-lg font-bold text-text mb-2">{component.name}</h3>
            <p className="text-sm text-text-muted leading-relaxed mb-5">{component.description}</p>

            {/* What it provides */}
            <div className="mt-auto">
              <span className="text-xs font-bold uppercase tracking-wider text-text-subtle mb-3 block">
                What it provides
              </span>
              <ul className="space-y-2.5">
                {component.provides.map((item) => (
                  <li key={item} className="flex items-start gap-2 text-sm text-text leading-snug">
                    {getCapabilityIcon(item)}
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ))}
      </div>

      {/* Path Weights callout */}
      <div className="relative overflow-hidden rounded-xl border border-primary/20 bg-gradient-to-r from-primary/5 via-transparent to-primary/5 p-6">
        <div className="flex items-start gap-4">
          <div className="p-2.5 rounded-lg bg-primary/15 text-primary flex-shrink-0">
            <SlidersHorizontal className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-text mb-1">You decide what matters.</h3>
            <p className="text-sm text-text-muted leading-relaxed">
              Path weights give you fine-grained control over what your AI sees.
              Boost <code className="text-xs bg-surface px-1.5 py-0.5 rounded border border-border font-mono">src/core/</code> to 1.5× so your domain logic always surfaces first.
              Set <code className="text-xs bg-surface px-1.5 py-0.5 rounded border border-border font-mono">vendor/</code> to 0 to hide generated noise entirely.
              Weights are hierarchical, instant, and require no rebuild — every search and context call respects them immediately.
            </p>
          </div>
        </div>
      </div>

      {/* Bottom note */}
      <div className="flex items-start gap-3 text-xs text-text-muted">
        <span className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 flex-shrink-0" />
        <span>
          <strong>Recommended:</strong> Install RunPrep — embeddings, search, and context assembly work immediately.
          The built-in model (~130 MB) downloads automatically on first build. Smart compression is built in —
          structural compression for code (3–20×), language-aware compression for docs (~2.4×).
        </span>
      </div>
    </div>
  );
}
