import { Image as ImageIcon } from 'lucide-react';
import { AnchorHeading } from '../../components/AnchorHeading';

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
                   CoDRAG runs locally. You don&apos;t need to create an account or upload code to the cloud to see it work.
                 </p>
               </div>
             </div>
          </div>

          <AnchorHeading id="install" level="h2">1. Install</AnchorHeading>
          <p>
            Download CoDRAG from <a href="https://codrag.io/download" className="text-primary hover:underline">codrag.io/download</a> and install the desktop app. It&apos;s also available on the Mac App Store and Microsoft Store.
          </p>
          <p className="text-sm text-text-muted">
            See the full <a href="/getting-started/installation" className="text-primary hover:underline">Installation Guide</a> for step-by-step instructions.
          </p>

          <AnchorHeading id="start-daemon" level="h2">2. Launch the App</AnchorHeading>
          <p>
            Open CoDRAG from your Applications folder (macOS) or Start Menu (Windows). The app automatically starts the background daemon that manages the Rust indexer and MCP server.
          </p>
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium text-text">Screenshot: CoDRAG Dashboard</p>
            <p className="text-sm text-center">Show the CoDRAG dashboard with a green &apos;Connected&apos; status indicator.</p>
          </div>
          <p className="text-sm text-text-muted">
            <em>Alternatively, power users can run <code>codrag serve</code> from a terminal.</em>
          </p>

          <AnchorHeading id="add-repo" level="h2">3. Add Your Repo</AnchorHeading>
          <p>
            In the CoDRAG dashboard, click the <span className="font-semibold text-text">+</span> button in the sidebar and select your project folder. CoDRAG will immediately start indexing (semantics + structure).
          </p>
          <p className="text-sm text-text-muted mt-2">
            Or via CLI: <code>codrag add ~/my-project --name &quot;My Project&quot;</code>
          </p>
          <p>
            You&apos;ll see indexing progress in the dashboard. For a 50k file repo, the Rust trace index takes less than a second once semantic indexing wraps up.
          </p>

          <AnchorHeading id="connect-editor" level="h2">4. Connect Your Editor</AnchorHeading>
          <p>
            CoDRAG works best when connected to an AI code editor via MCP.
          </p>
          
          <div className="grid sm:grid-cols-2 gap-4 not-prose my-6">
            <a href="/mcp/cursor" className="block p-4 border border-border rounded-lg hover:border-primary transition-colors">
              <div className="font-bold">Cursor</div>
              <div className="text-sm text-text-muted">Settings &gt; Features &gt; MCP</div>
            </a>
            <a href="/mcp/windsurf" className="block p-4 border border-border rounded-lg hover:border-primary transition-colors">
              <div className="font-bold">Windsurf</div>
              <div className="text-sm text-text-muted">~/.codeium/windsurf/mcp_config.json</div>
            </a>
          </div>

          <p>
             Use the default local URL: <code>http://localhost:8400/mcp/sse</code>
          </p>

          <AnchorHeading id="verify" level="h2">5. Verify</AnchorHeading>
          <p>
            Open your editor&apos;s AI chat (e.g. Cursor Agent or Windsurf Cascade) and ask:
          </p>
          <blockquote className="border-l-4 border-primary pl-4 italic text-text-muted my-4">
            &quot;Use hi_codrag to get oriented&quot;
          </blockquote>
          <p>
            The <code>hi_codrag</code> tool returns a project overview: index status, trace coverage, your selected files, health notes, and suggested prompts tailored to your codebase. It&apos;s the best first step after connecting.
          </p>
          <p className="text-sm text-text-muted mt-2">
            Then try a deeper query:
          </p>
          <blockquote className="border-l-4 border-border pl-4 italic text-text-muted my-4">
            &quot;Graph the callers of [Function X] and find where it&apos;s used.&quot;
          </blockquote>
          <p>
            You should see the agent call <code>codrag</code> with <code>trace_expand=true</code> and return a structural graph analysis.
          </p>
          <p className="text-sm text-text-muted mt-2 bg-surface border border-border rounded-lg p-3">
            <span className="font-semibold text-text">Free tier note:</span> Graph expansion requires a trace build. On the Free tier, trigger this manually from the dashboard (Graph Status → Build) before trying the graph query above. Paid tiers build the trace automatically on file save.
          </p>
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium text-text">Screenshot: Editor Verification</p>
            <p className="text-sm text-center">Show an IDE chat window (Cursor or Windsurf) successfully calling the &apos;codrag&apos; tool and displaying graph results.</p>
          </div>

          <hr className="my-12 border-border" />

          <AnchorHeading id="next-steps" level="h3">Next Steps</AnchorHeading>
          <ul className="list-disc pl-6 space-y-2">
            <li><a href="/guides/path-weights" className="text-primary hover:underline">Tune Path Weights</a> to focus the AI on what matters.</li>
            <li><a href="/guides/compression" className="text-primary hover:underline">Smart Compression</a> &mdash; structural for code (3&ndash;20&times;), language-aware for docs. Built in.</li>
            <li><a href="/troubleshooting" className="text-primary hover:underline">Troubleshooting</a> if something didn&apos;t work.</li>
          </ul>
        </div>
      </div>
    </main>
  );
}
