"use client";

import { Search, FileSearch, Cpu, Database, RefreshCw, FilterX } from 'lucide-react';
import { AnchorHeading } from '../../../components/AnchorHeading';
import { ConceptPageShell } from '../../../components/ConceptPageShell';

const SECTIONS = [
  { id: 'why',          label: 'Why Vector Indexing' },
  { id: 'pipeline',     label: 'The Indexing Process' },
  { id: 'incremental',  label: 'Incremental Updates' },
  { id: 'exclusions',   label: 'Exclusions' },
  { id: 'ui-controls',  label: 'Dashboard Controls' },
];

const STEPS = [
  {
    icon: <FileSearch className="w-4 h-4" />,
    title: 'Discovery',
    body: (
      <>The <code>prep-walker</code> crate (Rust) scans your directory, respecting <code>.gitignore</code> and user-defined exclusions. It computes BLAKE3 hashes for change detection.</>
    ),
  },
  {
    icon: <Cpu className="w-4 h-4" />,
    title: 'Parsing & Chunking',
    body: (
      <>Files are parsed using Tree-sitter. Code is split into logical chunks — functions, classes — rather than arbitrary text windows. Markdown docs are split by headers.</>
    ),
  },
  {
    icon: <Search className="w-4 h-4" />,
    title: 'Embedding',
    body: (
      <>Chunks are passed to the <span className="font-semibold text-text">Native Embedder</span> (ONNX/nomic-embed-text) or an optional Ollama instance. This converts text into 768-dimensional vectors.</>
    ),
  },
  {
    icon: <Database className="w-4 h-4" />,
    title: 'Storage',
    body: (
      <>Vectors and metadata are stored in a local LanceDB instance (or Qdrant/Chroma if configured). The raw text is never sent to the cloud.</>
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
          <span className="font-mono font-bold text-sm text-text">{step.title}</span>
        </div>
        <p className="text-sm text-text-muted">{step.body}</p>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <ConceptPageShell
      subtitle="Local-first Search"
      title="Local Indexing"
      description="How SourcePrep finds the right code when you describe what you want instead of naming it exactly. The structural Code Graph gives you the skeleton; vector indexing adds the muscle, so &quot;how authentication works&quot; surfaces the right files even if none of them contain the word verbatim — all on your localhost."
      sections={SECTIONS}
    >
      <section id="why">
        <h2 className="text-2xl font-semibold text-text mb-4">Why Vector Indexing</h2>
        <p className="text-text-muted leading-relaxed">
          Vector indexing is what lets SourcePrep answer fuzzy questions — the kind where you describe intent
          instead of typing exact names. Combined with the <a href="/concepts/code-graph" className="text-primary hover:underline">Code Graph</a> for
          precise structural lookups, it gives your AI both meaning-based and reference-based retrieval, on
          your machine, with no source code leaving your localhost.
        </p>
      </section>

      <section id="pipeline">
        <h2 className="text-2xl font-semibold text-text mb-2">The Indexing Process</h2>
        <p className="text-text-muted leading-relaxed mb-6">
          Four steps, all local. Tree-sitter handles parsing for 15+ languages; the embedder runs on CPU
          (ONNX) or your local Ollama if you prefer.
        </p>
        <div className="space-y-3">
          {STEPS.map((step, i) => (
            <StepCard key={step.title} step={step} index={i} />
          ))}
        </div>
      </section>

      <section id="incremental">
        <h2 className="text-2xl font-semibold text-text mb-4">Incremental Updates</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          A real-time file watcher (<code>watchdog</code>) keeps the index current. When you save a file, the
          watcher detects the modify event, debounces rapid changes, re-hashes the content, and re-parses /
          re-embeds only the changed file.
        </p>
        <div className="rounded-lg border border-border bg-surface p-5 flex items-start gap-4">
          <div className="text-primary flex-shrink-0 mt-0.5"><RefreshCw className="w-5 h-5" /></div>
          <div>
            <h3 className="font-medium text-sm text-text mb-1">Typically &lt; 200 ms per save</h3>
            <p className="text-sm text-text-muted">
              Your AI always sees the current state of your code. No batched daily rebuilds, no &quot;wait for
              indexing&quot; banners.
            </p>
          </div>
        </div>
      </section>

      <section id="exclusions">
        <h2 className="text-2xl font-semibold text-text mb-4">Exclusions</h2>
        <p className="text-text-muted leading-relaxed mb-4">
          Control what gets indexed via the Dashboard or <code>.sourceprep/ignore</code>. Common build
          artifacts and dependency directories are excluded by default.
        </p>
        <div className="rounded-lg border border-border bg-surface p-5 flex items-start gap-4">
          <div className="text-primary flex-shrink-0 mt-0.5"><FilterX className="w-5 h-5" /></div>
          <div>
            <h3 className="font-medium text-sm text-text mb-1">Default exclusions</h3>
            <p className="text-sm text-text-muted font-mono text-xs">
              node_modules/ · dist/ · build/ · .git/ · .next/ · target/ · venv/ · __pycache__/
            </p>
          </div>
        </div>
      </section>

      <section id="ui-controls">
        <AnchorHeading id="ui-controls" level="h2">Dashboard Controls</AnchorHeading>
        <p className="mt-3 text-text-muted leading-relaxed">
          The <span className="font-semibold text-text">Knowledge Base</span> column in the dashboard gives you
          visibility and control over indexing.
        </p>

        <h3 className="text-lg font-semibold text-text mt-6 mb-3">Index Status Card</h3>
        <p className="text-text-muted leading-relaxed mb-3">
          Real-time health check. The status badge shows current state:
        </p>
        <ul className="list-disc pl-5 space-y-1 text-text-muted">
          <li><span className="text-emerald-500 font-medium">Fresh</span>: index is perfectly synced with disk.</li>
          <li><span className="text-amber-500 font-medium">Stale</span>: files have changed but the index hasn&apos;t updated yet (usually brief during debounce).</li>
          <li><span className="text-blue-500 font-medium">Building</span>: the background worker is actively processing files.</li>
        </ul>
        <p className="text-text-muted leading-relaxed mt-3 mb-2">It also breaks down composition:</p>
        <ul className="list-disc pl-5 space-y-1 text-text-muted">
          <li><span className="font-semibold text-text">Code:</span> source files (parsed into AST chunks).</li>
          <li><span className="font-semibold text-text">Instructions:</span> Markdown, text, and documentation files (parsed by headers).</li>
          <li><span className="font-semibold text-text">Graph:</span> structural nodes (symbols, imports) used for graph traversal.</li>
        </ul>

        <h3 className="text-lg font-semibold text-text mt-8 mb-3">Manual Rebuild</h3>
        <p className="text-text-muted leading-relaxed mb-3">
          The watcher handles 99% of changes. The <span className="font-semibold text-text">Build Index</span> card
          covers the rest:
        </p>
        <ul className="list-disc pl-5 space-y-1 text-text-muted">
          <li><span className="font-semibold text-text">Branch switching:</span> if thousands of files change at once, a manual rebuild ensures everything is caught.</li>
          <li><span className="font-semibold text-text">Config changes:</span> changing <code>path_weights</code> or exclusion patterns applies them across the whole codebase.</li>
          <li><span className="font-semibold text-text">Troubleshooting:</span> if search feels off, a full rebuild (<code>--full</code>) clears the vector store and starts fresh.</li>
        </ul>
      </section>
    </ConceptPageShell>
  );
}
