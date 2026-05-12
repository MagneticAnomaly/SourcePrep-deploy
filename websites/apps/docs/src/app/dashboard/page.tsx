import { AnchorHeading } from '../../components/AnchorHeading';
import { StoryEmbed } from '../../components/StoryEmbed';

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

          <StoryEmbed
            storyId="dashboard-layouts-fulldashboard--full-dashboard"
            height={600}
            caption="A populated dashboard — drag, resize, and close panels to suit your workflow."
          />

          <AnchorHeading id="panel-categories" level="h2">Panel categories</AnchorHeading>
          <p>
            Every panel belongs to one of four categories. Use this when
            choosing what to add to your layout.
          </p>
          <ul className="list-disc pl-6 space-y-2">
            <li><span className="font-semibold text-text">Status:</span> what the engine is doing — Index Status, Pipeline progress, Code-Graph coverage, Atlas, Audit, Activity Heatmap, Goalposts, Roadmap.</li>
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

          <StoryEmbed
            storyId="patterns-panelpicker--default"
            height={350}
            caption="Panel Picker — toggle visibility, reset, refit, and copy/paste your layout."
          />

          <AnchorHeading id="key-panels" level="h2">Key panels</AnchorHeading>
          <p className="text-sm text-text-muted">
            Most users start with these. The full list lives in the Panel Picker.
          </p>

          <AnchorHeading id="index-status" level="h3" className="text-xl font-semibold mt-8 mb-2">Index Status</AnchorHeading>
          <p className="text-sm">
            High-level health of the index — file counts, coverage, last build,
            and stale-file count. The fastest way to see whether the engine has
            kept up with your last edits.
          </p>
          <StoryEmbed
            storyId="dashboard-index-indexstatuscard--loaded"
            height={220}
            caption="Index Status Card — index size, coverage, and freshness at a glance."
          />

          <AnchorHeading id="code-graph-coverage" level="h3" className="text-xl font-semibold mt-8 mb-2">Code-Graph Coverage</AnchorHeading>
          <p className="text-sm">
            Inventory view of which files made it into the structural code graph,
            which are queued, which were excluded, and which need re-tracing
            after a recent change. Use the Untraced and Stale tabs to nudge
            specific files into the pipeline.
          </p>
          <StoryEmbed
            storyId="dashboard-trace-coveragepanel--default"
            height={350}
            caption="Code-Graph Coverage — manage the inventory of indexed files."
          />

          <AnchorHeading id="pipeline" level="h3" className="text-xl font-semibold mt-8 mb-2">Pipeline</AnchorHeading>
          <p className="text-sm">
            Visualizes the 15-stage enrichment pipeline (Sync → Enrich →
            Finalize). Each stage shows its status, last run, and provenance
            (deterministic re-use vs. fresh build). For a full breakdown of what
            each stage does and why,
            see <a href="/concepts/graph-enrichment" className="text-primary hover:underline">Concepts → Graph Enrichment</a>.
          </p>
          <StoryEmbed
            storyId="dashboard-pipeline-graphenrichmentpipeline--full-pipeline-running"
            height={450}
            caption="Pipeline panel — every stage visible with live progress."
          />

          <AnchorHeading id="search-context" level="h3" className="text-xl font-semibold mt-8 mb-2">Search & Context</AnchorHeading>
          <p className="text-sm">
            The Search panel runs queries against the index; results stream in,
            and the Context Output panel renders the assembled context as it would
            be sent to your AI. Pair them with Context Options to control budget,
            atlas routing, and trace expansion.
          </p>
          <StoryEmbed
            storyId="dashboard-search-searchpanel--full-search-demo"
            height={350}
            caption="Search panel — find code by meaning, with the assembled context preview alongside."
          />

          <AnchorHeading id="settings" level="h2">Settings</AnchorHeading>
          <p>
            The Settings panel (Config category) is the configuration surface for
            the project. It is organized into sub-pages: Pipeline defaults,
            Chunking and Embeddings, Source globs, Trace, Integrations, and
            Destructive Actions. Most settings autosave; look for the
            inline status indicator next to each field.
          </p>

          <AnchorHeading id="learn-more" level="h2">Learn more</AnchorHeading>
          <ul className="list-disc pl-6 space-y-2">
            <li><a href="/dashboard/projects" className="text-primary hover:underline">Managing projects</a> — adding repos, scope control, per-project settings.</li>
            <li><a href="/concepts/graph-enrichment" className="text-primary hover:underline">Graph Enrichment</a> — what the 15 pipeline stages do.</li>
            <li><a href="/concepts/code-graph" className="text-primary hover:underline">Code Graph</a> — the structural backbone the dashboard surfaces.</li>
          </ul>

        </div>
      </div>
    </main>
  );
}
