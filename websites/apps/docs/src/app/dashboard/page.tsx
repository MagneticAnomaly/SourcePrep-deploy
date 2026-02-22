import { Image as ImageIcon } from 'lucide-react';
import { AnchorHeading } from '../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/" className="text-sm text-text-muted hover:text-primary transition-colors">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-4xl font-bold tracking-tight">Dashboard Guide</h1>
        <p className="mt-4 text-xl text-text-muted">
          A comprehensive tour of the CoDRAG desktop interface panels and controls.
        </p>

        <div className="mt-12 prose  max-w-none">
          
          <AnchorHeading id="overview" level="h2">Overview</AnchorHeading>
          <p>
            The dashboard adopts a unified <strong>Two-Pane Architecture</strong> designed to separate concerns:
          </p>
          <ol className="list-decimal pl-5 space-y-2 mt-4 mb-6">
            <li><strong>Graph Scope (Panel A)</strong>: Managing the inventory of files (what enters the graph).</li>
            <li><strong>Graph Engine (Panel B)</strong>: Orchestrating the 9-stage knowledge pipeline (how it’s processed).</li>
          </ol>
          <p>
            This layout streamlines the workflow: you define the scope, and the AI engine handles the heavy lifting of tracing, indexing, and enriching your codebase.
          </p>

          <div className="my-8 p-12 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-16 h-16 rounded-full bg-surface border border-border flex items-center justify-center mb-2">
              <ImageIcon className="w-8 h-8" />
            </div>
            <p className="font-medium">Screenshot: Two-Pane Dashboard</p>
            <p className="text-sm max-w-md text-center">Capture the unified dashboard showing the Scope (left) and Engine (right) panels.</p>
          </div>

          <hr className="my-12 border-border" />

          <AnchorHeading id="panel-a" level="h2" className="text-2xl font-bold mt-12 mb-6">1. Graph Scope (Panel A)</AnchorHeading>
          <p>
            The <strong>Graph Scope</strong> panel (left pane) is your inventory control. It defines exactly <em>what</em> code and documentation CoDRAG is allowed to see.
          </p>

          <AnchorHeading id="scope-header" level="h3" className="text-xl font-semibold mt-8 mb-4">Header & Health</AnchorHeading>
          <p>
            The header displays the total file count tracked by the system and a <strong>Health Indicator</strong> (e.g., "97% Traced").
          </p>
          <ul className="list-disc pl-5 space-y-2 mb-6 text-sm">
            <li><strong>Green Bar:</strong> High coverage. Most files are successfully parsed and indexed.</li>
            <li><strong>Yellow/Red:</strong> Low coverage. You may need to check the Queue or Excluded tabs.</li>
          </ul>

          <AnchorHeading id="scope-tabs" level="h3" className="text-xl font-semibold mt-8 mb-4">Management Tabs</AnchorHeading>
          
          <h4 className="font-semibold mt-4 mb-2">Queue Tab</h4>
          <p className="mb-4 text-sm">
            Lists files that have been detected by the file watcher but are not yet fully integrated into the graph.
          </p>
          <ul className="list-disc pl-5 space-y-2 mb-6 text-sm">
            <li><strong>Untraced:</strong> New files waiting for analysis.</li>
            <li><strong>Stale:</strong> Modified files that need re-parsing.</li>
            <li><strong>Action:</strong> Click <strong>Trace Selected</strong> or <strong>Trace All</strong> to hand these off to the Engine.</li>
          </ul>

          <h4 className="font-semibold mt-4 mb-2">Excluded Tab</h4>
          <p className="mb-4 text-sm">
            Manage files that are intentionally ignored.
          </p>
          <ul className="list-disc pl-5 space-y-2 mb-6 text-sm">
            <li>View active exclusion patterns (e.g., `**/*.min.js`).</li>
            <li><strong>Un-ignore:</strong> Select files to remove them from the blocklist and add them to the Queue.</li>
          </ul>

          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium">Screenshot: Graph Scope Panel</p>
            <p className="text-sm">Show the Scope panel with the Queue tab active.</p>
          </div>

          <hr className="my-12 border-border" />

          <AnchorHeading id="panel-b" level="h2" className="text-2xl font-bold mt-12 mb-6">2. Knowledge Pipeline (Panel B)</AnchorHeading>
          <p>
            The <strong>Knowledge Pipeline</strong> panel (right pane) is the “Factory”. It visualizes the 9-stage process that transforms your files (Scope) into intelligent context.
          </p>

          <AnchorHeading id="pipeline-controls" level="h3" className="text-xl font-semibold mt-8 mb-4">Controls</AnchorHeading>
          <ul className="list-disc pl-5 space-y-2 mb-6">
            <li><strong>Auto-Pilot:</strong> Master toggle. When ON, the engine automatically advances files through the pipeline stages as resources allow.</li>
            <li><strong>Budget Info:</strong> Real-time tracking of token usage (e.g., "12k / 50k tokens") to ensure no surprise costs.</li>
          </ul>

          <AnchorHeading id="pipeline-stages" level="h3" className="text-xl font-semibold mt-8 mb-4">The 9 Stages</AnchorHeading>
          <p className="text-sm text-text-muted mb-4">Stages 1–4 form <strong>Fast Sync</strong> (runs on every file save). Stages 5–9 form <strong>Deep Enrichment</strong> (runs on idle or schedule).</p>
          <div className="space-y-4 mb-8">
            <div className="p-4 border border-border rounded bg-surface">
              <div className="font-semibold text-sm">1. Structural Graph <span className="text-xs font-normal text-text-muted">(Rust)</span></div>
              <div className="text-xs text-text-muted">Tree-sitter AST parsing: symbols, imports, call edges, Markdown section extraction.</div>
            </div>
            <div className="p-4 border border-border rounded bg-surface">
              <div className="font-semibold text-sm">2. Fast Catalogue <span className="text-xs font-normal text-text-muted">(3b LLM)</span></div>
              <div className="text-xs text-text-muted">Rapid triage — classifies each file’s role and produces an initial summary.</div>
            </div>
            <div className="p-4 border border-border rounded bg-surface">
              <div className="font-semibold text-sm">3. Relationship Validation <span className="text-xs font-normal text-text-muted">(Rust)</span></div>
              <div className="text-xs text-text-muted">LLM-hypothesized relationships validated against the filesystem. Hallucinations discarded.</div>
            </div>
            <div className="p-4 border border-border rounded bg-surface">
              <div className="font-semibold text-sm">4. Knowledge Embedding <span className="text-xs font-normal text-text-muted">(Embeddings)</span></div>
              <div className="text-xs text-text-muted">Validated nodes embedded for semantic search. Makes catalogue immediately searchable.</div>
            </div>
            <div className="p-4 border border-primary/30 rounded bg-surface">
              <div className="font-semibold text-sm">5. Deep Reasoning <span className="text-xs font-normal text-text-muted">(14b LLM)</span></div>
              <div className="text-xs text-text-muted"><em>Epistemic enrichment.</em> A larger model reasons about each node in graph context — adding domain tags, architecture layers, design patterns, and computing an understanding score (0.0–1.0).</div>
            </div>
            <div className="p-4 border border-primary/30 rounded bg-surface">
              <div className="font-semibold text-sm">6. Module Synthesis <span className="text-xs font-normal text-text-muted">(14b LLM)</span></div>
              <div className="text-xs text-text-muted"><em>Cluster synthesis.</em> Groups enriched nodes by domain into subsystem modules with navigable summaries.</div>
            </div>
            <div className="p-4 border border-primary/30 rounded bg-surface">
              <div className="font-semibold text-sm">7. Codebase Atlas <span className="text-xs font-normal text-text-muted">(Routing)</span></div>
              <div className="text-xs text-text-muted">Builds a pre-retrieval routing index from synthesized modules. Scopes queries to the right subsystem.</div>
            </div>
            <div className="p-4 border border-primary/30 rounded bg-surface">
              <div className="font-semibold text-sm">8. Continuous Deepening <span className="text-xs font-normal text-text-muted">(Loop)</span></div>
              <div className="text-xs text-text-muted"><em>Convergence loop.</em> Re-enriches nodes with decayed understanding scores until the graph stabilizes. Inspired by belief propagation.</div>
            </div>
            <div className="p-4 border border-primary/30 rounded bg-surface">
              <div className="font-semibold text-sm">9. Deep Knowledge Embedding <span className="text-xs font-normal text-text-muted">(Embeddings)</span></div>
              <div className="text-xs text-text-muted">Re-embeds all enriched knowledge, module summaries, and refined connections for maximum retrieval accuracy.</div>
            </div>
          </div>

          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium">Screenshot: Knowledge Pipeline</p>
            <p className="text-sm">Show the vertical pipeline list with status indicators.</p>
          </div>

          <hr className="my-12 border-border" />

          <AnchorHeading id="global-settings" level="h2" className="text-2xl font-bold mt-12 mb-6">3. Global Settings</AnchorHeading>
          <p>
            The <strong>Engine Room</strong> where you configure the behavior of the AI.
          </p>
          <ul className="list-disc pl-5 space-y-2 mb-6">
            <li><strong>Model Selection:</strong> Toggle between efficiency (3b models) and depth (14b+ models) for the enrichment stages.</li>
            <li><strong>Budget Limits:</strong> Set hard caps on tokens or processing time.</li>
            <li><strong>Schedule:</strong> Configure auto-save triggers and background processing intervals.</li>
          </ul>

          <AnchorHeading id="search-context" level="h2" className="text-2xl font-bold mt-12 mb-6">4. Search & Context</AnchorHeading>
          <p>
            (Legacy View) The search interface remains available for direct queries against the graph.
          </p>
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium">Screenshot: Search Panel</p>
            <p className="text-sm">Show the search input field.</p>
          </div>

        </div>
      </div>
    </main>
  );
}
