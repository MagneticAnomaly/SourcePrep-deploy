import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/getting-started" className="text-sm text-text-muted">
          ← Getting Started
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Quick Start</h1>
        <p className="mt-4 text-lg text-text-muted">
          The fastest way to get structural context into your AI editor.
        </p>

        <div className="mt-12 prose  max-w-none">
          
          <AnchorHeading id="five-minute-guide" level="h2">The 5-Minute Guide</AnchorHeading>
          
          <div className="space-y-8 mt-6">
            <div>
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs">1</span>
                Launch CoDRAG
              </h3>
              <p className="text-sm text-text-muted mb-2 ml-8">
                Open the CoDRAG desktop app. It automatically starts the background daemon that manages the index and serves requests.
              </p>
              <p className="text-xs text-text-muted ml-8">
                Power users: you can also run <code>codrag serve</code> in a terminal.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs">2</span>
                Index Your Repo
              </h3>
              <p className="text-sm text-text-muted mb-2 ml-8">
                Click the <span className="font-semibold text-text">+</span> button in the sidebar, select your project folder, and CoDRAG will scan and build the Code Graph immediately.
              </p>
              <p className="text-xs text-text-muted ml-8">
                Or via CLI: <code>codrag add ~/my-project</code>
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs">3</span>
                Connect MCP
              </h3>
              <p className="text-sm text-text-muted mb-2 ml-8">
                Configure your editor (Cursor/Windsurf) to use the local server.
              </p>
              <div className="ml-8 grid grid-cols-2 gap-4">
                <a href="/mcp/cursor" className="block p-3 border border-border rounded hover:border-primary">
                  <span className="font-semibold text-text">Cursor Guide →</span>
                </a>
                <a href="/mcp/windsurf" className="block p-3 border border-border rounded hover:border-primary">
                  <span className="font-semibold text-text">Windsurf Guide →</span>
                </a>
              </div>
            </div>

            <div>
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs">4</span>
                Select Files &amp; Say Hi
              </h3>
              <p className="text-sm text-text-muted mb-2 ml-8">
                In the CoDRAG dashboard, use the <span className="font-semibold text-text">Knowledge Sources</span> tree to select the files and folders you want to work with. Then in your editor&apos;s AI chat, type:
              </p>
              <blockquote className="ml-8 border-l-2 border-primary pl-4 py-1 italic text-text-muted">
                &quot;hi_codrag&quot;
              </blockquote>
              <p className="text-sm text-text-muted mt-2 ml-8">
                CoDRAG will tell your AI exactly which files you selected &mdash; your design docs, code files, tests &mdash; and suggest relevant next steps. For example:
              </p>
              <div className="ml-8 mt-3 bg-surface border border-border p-4 rounded-lg text-sm space-y-3">
                <p className="text-text-muted">
                  <span className="font-semibold text-text">AI:</span> I&apos;m looking at your project &mdash; you&apos;ve selected 8 design docs and 18 React components in <code>src/components/</code>.
                </p>
                <p className="text-text-muted text-xs">
                  Your design docs cover: &quot;Overall Upgrade Plan&quot; (phased site redesign), &quot;Hero Section Design&quot; (parallax layout). It looks like you&apos;re working on <span className="font-semibold text-text">animation &amp; visuals</span> and <span className="font-semibold text-text">UI components</span>. The most connected are <code>EnhancedHero.tsx</code> (6 imports) and <code>ParallaxController.tsx</code> (4 imports).
                </p>
                <ol className="list-decimal pl-5 text-text-muted space-y-1">
                  <li>What UI components are here and how do they connect?</li>
                  <li>Compare the design docs to the implementation &mdash; anything out of sync?</li>
                  <li>Summarize the design docs and identify next steps</li>
                </ol>
              </div>
              <p className="text-sm text-text-muted mt-3 ml-8">
                Pick a number, or ask your own question &mdash; the AI already knows your context:
              </p>
              <blockquote className="ml-8 border-l-2 border-border pl-4 py-1 italic text-text-muted mt-2">
                &quot;How does the authentication middleware interact with the user service? Trace the calls.&quot;
              </blockquote>
            </div>
            <div>
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs">5</span>
                Audit Your Codebase
              </h3>
              <p className="text-sm text-text-muted mb-2 ml-8">
                Once your index is built, run a structural audit to find architectural issues, tech debt, and quality gaps &mdash; no LLM required:
              </p>
              <blockquote className="ml-8 border-l-2 border-primary pl-4 py-1 italic text-text-muted">
                &quot;Audit my codebase&quot;
              </blockquote>
              <p className="text-sm text-text-muted mt-2 ml-8">
                The AI calls <code>codrag_audit</code>, which runs 11 analyzers against your trace graph. You&apos;ll get severity-tagged findings like <code>ARCH-1</code> (circular dependency) or <code>QUAL-3</code> (oversized files). To act on a finding:
              </p>
              <blockquote className="ml-8 border-l-2 border-border pl-4 py-1 italic text-text-muted mt-2">
                &quot;Fix ARCH-1&quot;
              </blockquote>
              <p className="text-xs text-text-muted ml-8 mt-2">
                The AI calls <code>codrag_audit_refactor</code> to get trace context and an action plan for the affected files. See the <a href="/guides/codebase-audit" className="text-primary hover:underline">Codebase Audit Guide</a> for details.
              </p>
            </div>
          </div>

          <hr className="my-12 border-border" />

          <AnchorHeading id="cli-tips" level="h2">Pro Tips</AnchorHeading>
          <ul className="list-disc pl-5 text-sm text-text-muted">
            <li>
              <span className="font-semibold text-text">Search via CLI:</span> You can test retrieval without an editor using <code>codrag search &quot;query&quot;</code>.
            </li>
            <li>
              <span className="font-semibold text-text">Force Rebuild:</span> If you switched branches massively, run <code>codrag build</code> to ensure the index is fresh (though the watcher handles this mostly).
            </li>
            <li>
              <span className="font-semibold text-text">Check Status:</span> Run <code>codrag status</code> to see index stats and coverage.
            </li>
          </ul>

        </div>
      </div>
    </main>
  );
}
