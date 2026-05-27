import { AnimatedIDE, ideLoadingSkeletonDemo } from '../../components/cli-demos';
import { AnchorHeading } from '../../components/AnchorHeading';
import {
  DemoPanelPicker,
  DemoIndexStatusLoaded,
  DemoTraceCoverage,
  DemoGraphEnrichmentPipelineRunning,
  DemoSearchPanelFullDemo,
  DemoAgentOpsActive,
  DemoRoadmapPanel,
  DemoActivityHeatmapMixed,
} from '../../components/demos';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/" className="text-sm text-text-muted hover:text-primary transition-colors">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-4xl font-bold tracking-tight">Dashboard Guide</h1>
        <p className="mt-4 text-xl text-text-muted">
          A tour of the SourcePrep desktop dashboard — a configurable workspace
          of panels for monitoring your index, searching code, assembling
          context, and tuning the engine.
        </p>

        <div className="mt-12 prose  max-w-none">

          <AnchorHeading id="overview" level="h2">Overview</AnchorHeading>
          <p>
            The dashboard is a <span className="font-semibold text-text">modular grid of panels</span>.
            Pick the panels you want, drag them where you want, and the layout
            persists across sessions. There is no fixed left/right split — every
            panel is independently closeable, resizable, and rearrangeable.
          </p>

          {/*
            The full integrated dashboard (15+ panels with linked state) was previously embedded
            here via iframe. After the iframe migration (Phase 137b) we deferred it — pulling the
            entire ModularDashboard fixture into this route would balloon the docs bundle. The
            individual panel demos below cover the same surface area; see the live app for the
            integrated experience.
          */}
          <p className="text-sm text-text-muted italic">
            See the live SourcePrep dashboard for the full integrated workspace. The individual
            panels below are each rendered with the same components the dashboard uses.
          </p>

          <AnchorHeading id="panel-categories" level="h2">Panel categories</AnchorHeading>
          <p>
            Every panel belongs to one of four categories. Use this when
            choosing what to add to your layout.
          </p>
          <ul className="list-disc pl-6 space-y-2">
            <li><span className="font-semibold text-text">Status:</span> what the engine is doing — Knowledge Status, Pipeline progress, Code-Graph coverage, Atlas, Audit, Knowledge Activity, Goalposts, Roadmap.</li>
            <li><span className="font-semibold text-text">Search:</span> querying the index — Search, Search Results, File Tree, Trace.</li>
            <li><span className="font-semibold text-text">Context:</span> what gets sent to your AI — Context Options, Context Output, Architecture, Concepts.</li>
            <li><span className="font-semibold text-text">Config:</span> tuning the engine — Deep Analysis, Token Budget, Agent Ops.</li>
          </ul>

          <AnchorHeading id="adding-panels" level="h2">Adding, moving, and resetting panels</AnchorHeading>
          <p>
            The <span className="font-semibold text-text">Panel Picker</span> dropdown
            (top-right of the dashboard) is how you add and remove panels from your
            layout. It also exposes layout management:
          </p>
          <ul className="list-disc pl-6 space-y-2">
            <li><span className="font-semibold text-text">Toggle:</span> show or hide any panel — non-essential panels are closeable and persist their hidden state.</li>
            <li><span className="font-semibold text-text">Refit:</span> recompact the grid after closing panels.</li>
            <li><span className="font-semibold text-text">Reset:</span> restore the default layout (with a confirmation step).</li>
            <li><span className="font-semibold text-text">Copy / Paste:</span> serialize the current layout to clipboard so you can share it with a teammate or move it between machines.</li>
          </ul>

          <div className="not-prose">
            <DemoPanelPicker />
            <p className="text-xs text-text-subtle italic -mt-4">
              Panel Picker — toggle visibility, reset, refit, and copy/paste your layout.
            </p>
          </div>

          <AnchorHeading id="key-panels" level="h2">Key panels</AnchorHeading>
          <p className="text-sm text-text-muted">
            Most users start with these. The full list lives in the Panel Picker.
          </p>

          <AnchorHeading id="index-status" level="h3" className="text-xl font-semibold mt-8 mb-2">Knowledge Status</AnchorHeading>
          <p className="text-sm">
            High-level health of the index — file counts, coverage, last build,
            and stale-file count. The fastest way to see whether the engine has
            kept up with your last edits.
          </p>
          <div className="not-prose">
            <DemoIndexStatusLoaded />
            <p className="text-xs text-text-subtle italic -mt-4">
              Knowledge Status — chunks indexed, embedding model, last build, and freshness at a glance.
            </p>
          </div>

          <AnchorHeading id="code-graph-coverage" level="h3" className="text-xl font-semibold mt-8 mb-2">Code-Graph Coverage</AnchorHeading>
          <p className="text-sm">
            Inventory view of which files made it into the structural code graph,
            which are queued, which were excluded, and which need re-tracing
            after a recent change. Use the Untraced and Stale tabs to nudge
            specific files into the pipeline.
          </p>
          <div className="not-prose">
            <DemoTraceCoverage />
            <p className="text-xs text-text-subtle italic -mt-4">
              Code-Graph Coverage — manage the inventory of indexed files.
            </p>
          </div>

          <AnchorHeading id="pipeline" level="h3" className="text-xl font-semibold mt-8 mb-2">Pipeline</AnchorHeading>
          <p className="text-sm">
            Visualizes the 15-stage enrichment pipeline (Sync → Enrich →
            Finalize). Each stage shows its status, last run, and provenance
            (deterministic re-use vs. fresh build). For a full breakdown of what
            each stage does and why,
            see <a href="/how-it-works/graph-enrichment" className="text-primary hover:underline">How It Works → Graph Enrichment</a>.
          </p>
          <div className="not-prose">
            <DemoGraphEnrichmentPipelineRunning />
            <p className="text-xs text-text-subtle italic -mt-4">
              Pipeline panel — every stage visible with live progress.
            </p>
          </div>

          <AnchorHeading id="search-context" level="h3" className="text-xl font-semibold mt-8 mb-2">Search & Context</AnchorHeading>
          <p className="text-sm">
            The Search panel runs queries against the index; results stream in,
            and the Context Output panel renders the assembled context as it would
            be sent to your AI. Pair them with Context Options to control budget,
            atlas routing, and trace expansion.
          </p>
          <div className="not-prose">
            <DemoSearchPanelFullDemo />
            <p className="text-xs text-text-subtle italic -mt-4">
              Search panel — find code by meaning, with the assembled context preview alongside.
            </p>
          </div>

          <AnchorHeading id="agent-ops" level="h3" className="text-xl font-semibold mt-8 mb-2">Agent Operations</AnchorHeading>
          <p className="text-sm">
            Cross-cutting view of MCP-aware agents using your index — which editors are connected,
            which projects they&apos;re scoped to, and how many tool calls they&apos;ve issued. Useful
            when more than one agent is in flight at the same time.
          </p>
          <div className="not-prose">
            <DemoAgentOpsActive />
            <p className="text-xs text-text-subtle italic -mt-4">
              Agent Operations Panel — live connections, scope, and throughput per agent.
            </p>
          </div>

          <AnchorHeading id="roadmap" level="h3" className="text-xl font-semibold mt-8 mb-2">Roadmap</AnchorHeading>
          <p className="text-sm">
            LLM-synthesized roadmap derived from your codebase, open tickets, and recent commits.
            Bi-directional GitHub sync keeps it in step with the work that&apos;s actually moving.
          </p>
          <div className="not-prose">
            <DemoRoadmapPanel />
            <p className="text-xs text-text-subtle italic -mt-4">
              Roadmap Panel — synthesized milestones, sprint suggestions, and burndown.
            </p>
          </div>

          <AnchorHeading id="activity" level="h3" className="text-xl font-semibold mt-8 mb-2">Activity Heatmap</AnchorHeading>
          <p className="text-sm">
            Year-view of indexing and enrichment activity per day. Surface dormant areas of the
            codebase and spot anomalies in incremental-rebuild frequency at a glance.
          </p>
          <div className="not-prose">
            <DemoActivityHeatmapMixed />
            <p className="text-xs text-text-subtle italic -mt-4">
              Activity Heatmap — daily indexing + enrichment volume across the year.
            </p>
          </div>

          <AnchorHeading id="settings" level="h2">Settings</AnchorHeading>
          <p>
            The Settings panel (Config category) is the configuration surface for
            the project. It is organized into sub-pages: Pipeline defaults,
            Chunking and Embeddings, Source globs, Trace, Integrations, and
            Destructive Actions. Most settings autosave; look for the
            inline status indicator next to each field.
          </p>

          <AnchorHeading id="agent-live" level="h2">What it looks like with an agent attached</AnchorHeading>
          <p className="text-sm">
            With the dashboard running and an MCP-aware editor connected, your agent operates
            against the same panels you see — using SourcePrep&apos;s context to navigate the
            codebase while you watch progress in real time.
          </p>
          <div className="not-prose my-6">
            <AnimatedIDE script={ideLoadingSkeletonDemo} />
          </div>
          <p className="text-xs text-text-muted text-center italic -mt-2">
            An agent live-editing UI code with SourcePrep&apos;s structural context loaded alongside the IDE.
          </p>

          <AnchorHeading id="learn-more" level="h2">Learn more</AnchorHeading>
          <ul className="list-disc pl-6 space-y-2">
            <li><a href="/dashboard/projects" className="text-primary hover:underline">Managing projects</a> — adding repos, scope control, per-project settings.</li>
            <li><a href="/how-it-works/graph-enrichment" className="text-primary hover:underline">Graph Enrichment</a> — what the 15 pipeline stages do.</li>
            <li><a href="/how-it-works/code-graph" className="text-primary hover:underline">Code Graph</a> — the structural backbone the dashboard surfaces.</li>
          </ul>

        </div>
      </div>
    </main>
  );
}
