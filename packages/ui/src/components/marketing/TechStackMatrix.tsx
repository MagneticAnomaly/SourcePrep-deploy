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
    name: 'CoDRAG Engine',
    required: true,
    tag: 'One install — batteries included',
    accent: 'primary',
    icon: <Box className="w-6 h-6" />,
    description: 'The Rust-powered daemon that runs entirely on your machine. Indexes codebases of any size — 500 files or 500,000 — with built-in semantic embeddings. No Ollama, no cloud, no GPU required.',
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
    name: 'CLaRa Compression',
    required: false,
    tag: 'Optional — 10-16× context compression',
    accent: 'success',
    icon: <Shrink className="w-6 h-6" />,
    description: 'An optional sidecar for when you need to maximize context efficiency. Compresses retrieved code and docs so you can fit more relevant signal into your prompt window.',
    provides: [
      '10–16× context compression with CLaRa-7B',
      'Query-aware — compression focuses on what you asked for',
      'Increases signal density for complex tasks',
      'Best-effort — falls back to uncompressed if CLaRa is offline',
      'Works via API, MCP, and dashboard',
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
  '10–16×': <Shrink className="w-3.5 h-3.5 text-success flex-shrink-0" />,
  'Query-aware': <Search className="w-3.5 h-3.5 text-success flex-shrink-0" />,
  'Increases signal': <Gauge className="w-3.5 h-3.5 text-success flex-shrink-0" />,
  'Best-effort': <Eye className="w-3.5 h-3.5 text-success flex-shrink-0" />,
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
          <span className="font-semibold text-text">CoDRAG ships with everything you need.</span>{' '}
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
          <strong>Recommended:</strong> Install CoDRAG — embeddings, search, and context assembly work immediately.
          The built-in model (~130 MB) downloads automatically on first build. For massive codebases, add CLaRa to
          compress context 10–16× and fit more relevant signal into your prompt window.
        </span>
      </div>
    </div>
  );
}
