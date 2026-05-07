"use client";

import { Search, Scale, Ruler, Minimize2, FileCode } from 'lucide-react';
import { AnchorHeading } from '../../../components/AnchorHeading';
import { ConceptPageShell } from '../../../components/ConceptPageShell';

const SECTIONS = [
  { id: 'why',         label: 'Why Assembly Matters' },
  { id: 'retrieval',   label: 'Retrieval' },
  { id: 'scoring',     label: 'Scoring & Weighting' },
  { id: 'budgeting',   label: 'Budgeting' },
  { id: 'compression', label: 'Smart Compression' },
  { id: 'formatting',  label: 'Formatting' },
  { id: 'ui-controls', label: 'Panel Controls' },
];

const STEPS = [
  {
    icon: <Search className="w-4 h-4" />,
    name: 'RETRIEVAL',
    title: 'Retrieval',
    body: (
      <>Candidates from multiple sources — semantic search (top-K vector similarity), keyword search (BM25), and the Code Graph (related definitions and call sites, when trace expansion is on).</>
    ),
  },
  {
    icon: <Scale className="w-4 h-4" />,
    name: 'SCORING',
    title: 'Scoring & Weighting',
    body: (
      <>Re-scored on relevance (vector distance), query intent (auto-classified — &quot;docs&quot;, &quot;tests&quot;, &quot;code&quot;, or &quot;default&quot; — adjusts role weights accordingly), path weights (per-directory multipliers), priming (<code>AGENTS.md</code> and primer files get a global boost), and recency.</>
    ),
  },
  {
    icon: <Ruler className="w-4 h-4" />,
    name: 'BUDGETING',
    title: 'Budgeting & Truncation',
    body: (
      <>You specify a <code>max_chars</code> or <code>max_tokens</code> budget. Chunks are sorted by final score, greedily added until near full, with class headers and function signatures preserved as &quot;glue&quot; for context.</>
    ),
  },
  {
    icon: <Minimize2 className="w-4 h-4" />,
    name: 'COMPRESSION',
    title: 'Smart Compression',
    body: (
      <>Two engines, both CPU-only. Code is structurally compressed at a Level of Detail (LOD) determined by relevance — top results stay full, mid-relevance shows signatures, peripheral files show names only (3–20×, no model). Documentation is compressed with a lightweight language model that strips filler while preserving meaning (~2.4×).</>
    ),
  },
  {
    icon: <FileCode className="w-4 h-4" />,
    name: 'FORMATTING',
    title: 'Formatting',
    body: (
      <>Final output is XML, Markdown, or JSON, with file path citations (<code>@src/file.ts:10-20</code>) that AI editors parse to render &quot;Click to Open&quot; links.</>
    ),
  },
];

function StepCard({ step, index }: { step: typeof STEPS[number]; index: number }) {
  return (
    <div className="flex items-start gap-4 rounded-lg border border-border bg-surface px-5 py-4">
      <div className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full border border-border bg-background text-xs font-bold font-mono text-text-muted">
        {index + 1}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-primary">{step.icon}</span>
          <span className="font-mono font-bold text-sm text-text">{step.name}</span>
        </div>
        <p className="text-sm text-text-muted">{step.body}</p>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <ConceptPageShell
      subtitle="Pipeline"
      title="Context Assembly"
      description="Retrieving code is easy. Assembling it into a coherent prompt that fits the context window while maximizing information density is hard. Five steps: retrieve, score, budget, compress, format — each tunable, all running locally on your machine."
      sections={SECTIONS}
    >
      <section id="why">
        <h2 className="text-2xl font-semibold text-text mb-4">Why Assembly Matters</h2>
        <p className="text-text-muted leading-relaxed">
          Naive RAG dumps top-K chunks and hopes the model picks signal from noise. SourcePrep treats context
          as a budget to be allocated — every chunk is scored, weighted by intent, compressed by relevance,
          and formatted with citations the AI can actually navigate.
        </p>
      </section>

      <section id="retrieval">
        <h2 className="text-2xl font-semibold text-text mb-2">The Assembly Pipeline</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          Five steps run in sequence. Each step has knobs in the dashboard&apos;s Context Assembler panel.
        </p>
        <div className="space-y-3">
          {STEPS.map((step, i) => (
            <div key={step.name} id={i === 0 ? 'retrieval' : i === 1 ? 'scoring' : i === 2 ? 'budgeting' : i === 3 ? 'compression' : 'formatting'} className="scroll-mt-24">
              <StepCard step={step} index={i} />
            </div>
          ))}
        </div>
      </section>

      <section id="ui-controls">
        <AnchorHeading id="ui-controls" level="h2">Panel Controls</AnchorHeading>
        <p className="mt-3 text-text-muted leading-relaxed mb-6">
          The <span className="font-semibold text-text">Context Assembler</span> panel in the dashboard lets you
          tune the pipeline.
        </p>

        <div className="grid gap-6 md:grid-cols-2">
          <div className="rounded-lg border border-border bg-surface p-6">
            <h3 className="font-semibold text-text mb-3">Retrieval Settings</h3>
            <ul className="space-y-3 text-sm text-text-muted">
              <li>
                <span className="font-semibold text-text">Chunks (k):</span> how many distinct code blocks to
                retrieve from the vector database.
                <br /><span className="text-xs">Default: 20. Increase for broad queries, decrease for precision.</span>
              </li>
              <li>
                <span className="font-semibold text-text">Max chars:</span> hard limit for the final output.
                Chunks stop being added once this budget is hit.
                <br /><span className="text-xs">Default: 24,000 (fits comfortably in 32k windows).</span>
              </li>
            </ul>
          </div>

          <div className="rounded-lg border border-border bg-surface p-6">
            <h3 className="font-semibold text-text mb-3">Output Toggles</h3>
            <ul className="space-y-3 text-sm text-text-muted">
              <li>
                <span className="font-semibold text-text">Sources:</span> adds the
                <code> @path/to/file:line-line</code> citation header to each chunk.
                <br /><span className="text-xs">Essential for AI editors to render clickable links.</span>
              </li>
              <li>
                <span className="font-semibold text-text">Scores:</span> appends the relevance score (0.0–1.0)
                to each chunk.
                <br /><span className="text-xs">Useful when debugging why a chunk was included.</span>
              </li>
              <li>
                <span className="font-semibold text-text">Structured:</span> returns a JSON object instead of
                a text blob.
                <br /><span className="text-xs">For programmatic integrations.</span>
              </li>
            </ul>
          </div>
        </div>
      </section>
    </ConceptPageShell>
  );
}
