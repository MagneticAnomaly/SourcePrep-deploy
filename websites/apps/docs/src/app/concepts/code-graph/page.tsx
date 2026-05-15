"use client";

import { Cpu, Network, Eye, Zap, Code2, FileSearch } from 'lucide-react';
import { AnimatedCLI, impactExtractServiceDemo } from '../../../components/cli-demos';
import { AnchorHeading } from '../../../components/AnchorHeading';
import { StoryEmbed } from '../../../components/StoryEmbed';
import { ConceptPageShell } from '../../../components/ConceptPageShell';

const SECTIONS = [
  { id: 'why',           label: 'Why a Graph' },
  { id: 'rust-engine',   label: 'Rust Engine' },
  { id: 'the-graph',     label: 'What It Maps' },
  { id: 'visualization', label: 'Visualizing the Graph' },
  { id: 'usage',         label: 'How Agents Use It' },
  { id: 'beyond',        label: 'Beyond the Graph' },
];

const RELATIONSHIPS = [
  { icon: <Code2 className="w-4 h-4" />,    title: 'Definitions', body: 'Where is a symbol declared? Files, classes, functions, types.' },
  { icon: <FileSearch className="w-4 h-4" />, title: 'References', body: 'Where is the symbol used? Every call site, every import.' },
  { icon: <Network className="w-4 h-4" />,  title: 'Imports',     body: 'What does file A depend on? Module-level dependency edges.' },
];

export default function Page() {
  return (
    <ConceptPageShell
      subtitle="Structural Backbone"
      title="Code Graph"
      description="Vector search is great for fuzzy questions; it&apos;s terrible at precision. SourcePrep maintains a parallel structural graph of your codebase — a directed graph of imports, definitions, and references — so your AI can answer &quot;where is the User struct defined and what calls it?&quot; with zero hallucinations."
      sections={SECTIONS}
    >
      <section id="why">
        <h2 className="text-2xl font-semibold text-text mb-4">Why a Graph</h2>
        <p className="text-text-muted leading-relaxed">
          Vector embeddings are excellent at semantic similarity but blind to structure. Asking &quot;where is X
          defined and what calls it?&quot; through a vector store gets you files that <em>talk about</em> X —
          not files that <em>contain</em> X. The Code Graph is the precision layer: parser-derived ground
          truth, no LLM in the loop, no hallucinations.
        </p>
      </section>

      <section id="rust-engine">
        <h2 className="text-2xl font-semibold text-text mb-4">Rust Engine</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          The Code Graph is built by a high-performance Rust engine (<code>prep-engine</code>) that runs
          alongside the Python daemon. Tree-sitter generates concrete syntax trees for accurate symbol
          extraction.
        </p>
        <div className="rounded-lg border border-border bg-surface p-5 flex items-start gap-4">
          <div className="text-primary flex-shrink-0 mt-0.5"><Cpu className="w-5 h-5" /></div>
          <div className="space-y-2">
            <p className="text-sm text-text"><span className="font-semibold">Speed:</span> parses ~50k files in seconds.</p>
            <p className="text-sm text-text"><span className="font-semibold">Accuracy:</span> Tree-sitter CSTs, not regex.</p>
            <p className="text-sm text-text"><span className="font-semibold">Multi-language:</span> Python, TypeScript, JavaScript, Go, Rust, Java, C, C++ — and growing.</p>
          </div>
        </div>
      </section>

      <section id="the-graph">
        <h2 className="text-2xl font-semibold text-text mb-2">What It Maps</h2>
        <p className="text-text-muted leading-relaxed mb-6">Three relationship types form the graph&apos;s edges:</p>
        <div className="space-y-3">
          {RELATIONSHIPS.map((r) => (
            <div key={r.title} className="flex items-start gap-4 rounded-lg border border-border bg-surface px-5 py-4">
              <div className="flex-shrink-0 mt-1 text-primary">{r.icon}</div>
              <div className="flex-1 min-w-0">
                <div className="font-mono font-bold text-sm text-text mb-1">{r.title}</div>
                <p className="text-sm text-text-muted">{r.body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section id="visualization">
        <h2 className="text-2xl font-semibold text-text mb-4">Visualizing the Graph</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          The <span className="font-semibold text-text">Code Graph</span> panel in the dashboard provides an
          interactive way to explore relationships. Click any file to see its immediate dependencies (upstream)
          and consumers (downstream); toggle to a list view for exact import counts and symbol references.
        </p>
        <div className="rounded-lg overflow-hidden border border-border">
          <StoryEmbed
            storyId="dashboard-trace-graph--default"
            height={450}
            title="Interactive Code Graph"
            caption="Live preview: file-level dependencies and import relationships."
          />
        </div>

        <div className="mt-6 rounded-lg overflow-hidden border border-border">
          <StoryEmbed
            storyId="dashboard-trace-nodedetailpanel--file-node"
            height={380}
            title="Node Detail Panel"
            caption="Click any node in the graph to drill down — definitions, references, and import chain for that symbol."
          />
        </div>
      </section>

      <section id="usage">
        <h2 className="text-2xl font-semibold text-text mb-4">How Agents Use It</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          You don&apos;t query the graph directly. Instead, your agent enables{' '}
          <span className="font-semibold text-text">trace expansion</span> in its context request (or uses
          the &quot;Trace&quot; keywords in the MCP editor). When enabled, SourcePrep:
        </p>
        <ol className="list-decimal pl-5 space-y-1 text-text-muted">
          <li>Finds the primary chunks via vector search.</li>
          <li>Identifies key symbols in those chunks.</li>
          <li>Queries the Code Graph for their definition sites and usages.</li>
          <li>Expands the context to include those related files, even if they didn&apos;t match the search keywords.</li>
        </ol>

        <div className="mt-6 rounded-lg border border-info/40 bg-info/10 p-4">
          <p className="text-sm font-semibold text-text mb-2"><Eye className="inline w-4 h-4 mr-1" />Example</p>
          <p className="text-sm text-text-muted">
            You ask &quot;how is billing calculated?&quot; Vector search finds <code>billing.py</code>. The
            Code Graph notices <code>billing.py</code> imports <code>tax_rates.py</code> — so SourcePrep
            includes <code>tax_rates.py</code> in the context automatically, preventing the AI from
            hallucinating tax logic.
          </p>
        </div>

        <div className="mt-6">
          <AnimatedCLI script={impactExtractServiceDemo} />
        </div>
        <p className="text-xs text-text-muted text-center italic mt-2">
          What blast-radius expansion looks like when an agent calls <code>prep_impact</code> before a refactor.
        </p>
      </section>

      <section id="beyond">
        <AnchorHeading id="beyond" level="h2">Beyond the Graph</AnchorHeading>
        <p className="mt-3 text-text-muted leading-relaxed">
          The Code Graph is not a static artifact. It&apos;s the structural foundation for a 15-stage{' '}
          <a href="/concepts/graph-enrichment" className="text-primary hover:underline">Graph Enrichment</a>{' '}
          pipeline that layers in meaning, module relationships, and architectural summaries — turning raw
          structure into navigable knowledge your AI can actually reason over.
        </p>
        <a
          href="/concepts/graph-enrichment"
          className="inline-flex items-center gap-2 mt-4 text-sm font-medium text-primary hover:underline"
        >
          Read the Graph Enrichment guide <Zap className="w-4 h-4" />
        </a>
      </section>
    </ConceptPageShell>
  );
}
