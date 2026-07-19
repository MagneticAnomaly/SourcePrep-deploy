import { Image as ImageIcon } from 'lucide-react';
import { AnimatedCLI, prepTldrOverviewDemo, auditPrSanityCheckDemo } from '../../components/cli-demos';
import { AnchorHeading } from '../../components/AnchorHeading';
import { DemoIndexStatusLoaded } from '../../components/demos';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/" className="text-sm text-text-muted hover:text-primary transition-colors">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-4xl font-bold tracking-tight">Getting Started</h1>
        <p className="mt-4 text-xl text-text-muted">
          From zero to structural code intelligence in under 10 minutes.
        </p>

        <div className="mt-12 prose  max-w-none">
          <div className="not-prose mb-12">
             <div className="flex items-start gap-4 p-4 bg-surface border border-border rounded-xl">
               <div className="p-2 bg-primary/10 rounded-lg text-primary">
                 <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6"><path d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
               </div>
               <div>
                 <h3 className="font-bold text-text">The &quot;Trust Loop&quot;</h3>
                 <p className="text-sm text-text-muted mt-1">
                   SourcePrep runs locally. You don&apos;t need to create an account or upload code to the cloud to see it work.
                 </p>
               </div>
             </div>
          </div>

          <AnchorHeading id="install" level="h2">1. Install</AnchorHeading>
          <p>
            Download SourcePrep from <a href="https://sourceprep.io/download" className="text-primary hover:underline">sourceprep.io/download</a> and install the desktop app. macOS and Windows are supported today; Linux is planned post-MVP.
          </p>
          <p className="text-sm text-text-muted">
            See the full <a href="/getting-started/installation" className="text-primary hover:underline">Installation Guide</a> for step-by-step instructions.
          </p>

          <AnchorHeading id="start-daemon" level="h2">2. Launch the App</AnchorHeading>
          <p>
            Open SourcePrep from your Applications folder (macOS) or Start Menu (Windows). The app automatically starts the background daemon that manages the Rust indexer and MCP server.
          </p>
          <div className="not-prose my-6">
            <AnimatedCLI script={prepTldrOverviewDemo} />
          </div>
          <p className="text-sm text-text-muted">
            <em>Alternatively, power users can run <code>prep serve</code> from a terminal.</em>
          </p>

          <AnchorHeading id="add-repo" level="h2">3. Add Your Repo</AnchorHeading>
          <p>
            In the SourcePrep dashboard, click the <span className="font-semibold text-text">+</span> button in the sidebar and select your project folder. SourcePrep will immediately start indexing (semantics + structure).
          </p>
          <p className="text-sm text-text-muted mt-2">
            Or via CLI: <code>prep add ~/my-project --name &quot;My Project&quot;</code>
          </p>
          <p>
            You&apos;ll see indexing progress in the dashboard. For a 50k file repo, the Rust trace index takes less than a second once semantic indexing wraps up.
          </p>
          <div className="not-prose">
            <DemoIndexStatusLoaded />
            <p className="text-xs text-text-subtle italic -mt-2 mb-4">
              What the dashboard looks like once your first project is indexed and serving structural context.
            </p>
          </div>

          <AnchorHeading id="connect-editor" level="h2">4. Connect Your Editor</AnchorHeading>
          <p>
            SourcePrep works best when connected to an AI code editor via MCP.
          </p>
          
          <div className="grid sm:grid-cols-2 gap-4 not-prose my-6">
            <a href="/mcp/ides" className="block p-4 border border-border rounded-lg hover:border-primary transition-colors">
              <div className="font-bold">Agentic IDEs</div>
              <div className="text-sm text-text-muted">Cursor, Windsurf, Copilot, Zed</div>
            </a>
            <a href="/mcp/terminal" className="block p-4 border border-border rounded-lg hover:border-primary transition-colors">
              <div className="font-bold">Terminal CLIs</div>
              <div className="text-sm text-text-muted">Claude Code, Gemini CLI, Codex</div>
            </a>
          </div>

          <p>
            Both editors use <span className="font-semibold text-text">stdio</span> (recommended). The MCP config tells your editor to spawn <code>prep mcp</code> as a subprocess &mdash; no URLs to configure.
          </p>
          <p className="text-sm text-text-muted mt-2">
            <em>Advanced: For remote/containerized setups, SourcePrep also supports SSE via the MCP HTTP server at <code>http://localhost:8401/sse</code> (start it with <code>prep mcp --transport http</code>). See the <a href="/mcp" className="text-primary hover:underline">MCP reference</a> for details.</em>
          </p>

          <AnchorHeading id="verify" level="h2">5. Verify</AnchorHeading>
          <p>
            Open your editor&apos;s AI chat (e.g. Cursor Agent or Windsurf Cascade) and call:
          </p>
          <blockquote className="border-l-4 border-primary pl-4 italic text-text-muted my-4">
            &quot;prep&quot;
          </blockquote>
          <p>
            The <code>prep</code> tool returns an ambient project baseline: index status, trace coverage, your selected focus areas, and hub files tailored to your codebase. It&apos;s the best first step after connecting.
          </p>
          <p className="text-sm text-text-muted mt-2">
            Then try a deeper explicit query:
          </p>
          <blockquote className="border-l-4 border-border pl-4 italic text-text-muted my-4">
            &quot;Graph the callers of [Function X] and find where it&apos;s used.&quot;
          </blockquote>
          <p>
            You should see the agent call <code>prep_search</code> with structural tracing and return an expanded graph analysis.
          </p>
          <p className="text-sm text-text-muted mt-2 bg-surface border border-border rounded-lg p-3">
            <span className="font-semibold text-text">Note:</span> Graph expansion requires a trace build. The file watcher rebuilds the trace automatically on file changes. To trigger a manual rebuild, open the dashboard&apos;s <span className="font-semibold text-text">Graph Scope</span> panel.
          </p>

          <AnchorHeading id="audit" level="h2">6. Run a Codebase Audit</AnchorHeading>
          <p>
            Once your index is built, try an architectural audit:
          </p>
          <blockquote className="border-l-4 border-primary pl-4 italic text-text-muted my-4">
            &quot;Audit my codebase&quot;
          </blockquote>
          <p>
            The <code>prep_audit</code> tool analyzes your trace graph for architectural issues, tech debt, test coverage gaps, and more &mdash; using 11 built-in analyzers. No LLM required. Results include severity-tagged findings like <code>ARCH-1</code>, <code>QUAL-3</code>, etc.
          </p>
          <p className="text-sm text-text-muted mt-2">
            To fix a finding, just say <strong>&quot;fix ARCH-1&quot;</strong> &mdash; the AI will call <code>prep_audit</code> with <code>action=&quot;refactor&quot;</code> to get trace context and an action plan for the affected files.
          </p>
          <p className="text-sm text-text-muted mt-2">
            See the full <a href="/guides/codebase-audit" className="text-primary hover:underline">Codebase Audit Guide</a> for details on all analyzers and the refactor workflow.
          </p>
          <div className="not-prose my-6">
            <AnimatedCLI script={auditPrSanityCheckDemo} />
          </div>

          <hr className="my-12 border-border" />

          <AnchorHeading id="next-steps" level="h3">Next Steps</AnchorHeading>
          <ul className="list-disc pl-6 space-y-2">
            <li><a href="/guides/codebase-audit" className="text-primary hover:underline">Codebase Audit Guide</a> &mdash; deep-dive into the 11 analyzers and the refactor workflow.</li>
            <li><a href="/guides/path-weights" className="text-primary hover:underline">Tune Path Weights</a> to focus the AI on what matters.</li>
            <li><a href="/how-it-works/compression" className="text-primary hover:underline">Smart Compression</a> &mdash; structural code compression (3&ndash;20&times;) built in. Language-aware compression for docs is on the roadmap.</li>
            <li><a href="/troubleshooting" className="text-primary hover:underline">Troubleshooting</a> if something didn&apos;t work.</li>
          </ul>
        </div>
      </div>
    </main>
  );
}
