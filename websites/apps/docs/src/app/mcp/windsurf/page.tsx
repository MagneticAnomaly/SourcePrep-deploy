import { Image as ImageIcon } from 'lucide-react';
import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/mcp" className="text-sm text-text-muted">
          ← Back to Integrations
        </a>

        <div className="flex items-center gap-4 mt-6">
          <div className="p-3 bg-surface rounded-xl border border-border">
             {/* Windsurf Logo Placeholder */}
             <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-8 h-8"><path d="M2 12h20"></path><path d="M2 12l10-10 10 10-10 10-10-10z"></path></svg>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">
            CoDRAG + Windsurf
          </h1>
        </div>
        
        <p className="mt-4 text-lg text-text-muted">
          Power Cascade&apos;s flow with CoDRAG&apos;s structural intelligence.
        </p>

        <div className="mt-8 prose  max-w-none">
          <AnchorHeading id="setup" level="h2">Setup</AnchorHeading>
          <ol className="list-decimal pl-6 space-y-4">
            <li>
              <span className="font-semibold text-text">Ensure CoDRAG is running.</span> Open the CoDRAG desktop app or run <code>codrag serve</code>.
            </li>
            <li>
              <span className="font-semibold text-text">Configure MCP.</span> Windsurf reads MCP configuration from <code>~/.codeium/windsurf/mcp_config.json</code> (or via the UI in recent versions).
              <p className="mt-2 text-sm text-text-muted">
                Tip: Run <code>codrag mcp-config --ide windsurf</code> to generate the config block below.
              </p>
            </li>
            <li>
              <span className="font-semibold text-text">Add Server Config.</span> Add the CoDRAG command to your config:
              <pre className="mt-2 overflow-x-auto text-sm">
{`{
  "mcpServers": {
    "codrag": {
      "command": "codrag",
      "args": ["mcp"]
    }
  }
}`}
              </pre>
              <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2 not-prose">
                <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
                  <ImageIcon className="w-6 h-6" />
                </div>
                <p className="font-medium text-text">Screenshot: Windsurf Config File</p>
                <p className="text-sm text-center">Show the &apos;mcp_config.json&apos; file open in an editor with the codrag configuration added.</p>
              </div>
              <p className="text-sm text-text-muted mt-2">
                <em>Note: If <code>codrag</code> is not in your system PATH, use the absolute path (e.g., <code>/Applications/CoDRAG.app/Contents/MacOS/codrag</code> on macOS).</em>
              </p>
            </li>
          </ol>

          <hr className="my-8 border-border" />

          <AnchorHeading id="usage" level="h2">How to Use</AnchorHeading>
          <p>
            Cascade (Windsurf&apos;s agent) is highly proactive. It will see the <code>codrag</code> tools (<code>codrag_search</code>, <code>codrag</code>, <code>codrag_audit</code>, etc.) and call them automatically.
          </p>

          <h3 className="text-xl font-semibold mt-6">Start with <code>hi_codrag</code></h3>
          <p>
            The best way to start any session is to select files in the CoDRAG <span className="font-semibold text-text">Knowledge Sources</span> tree, then type <code>hi_codrag</code> in Cascade&apos;s chat. CoDRAG will tell the AI exactly which files you selected and suggest what to do next.
          </p>

          <div className="bg-surface border border-border p-4 rounded-lg font-mono text-sm my-4 space-y-4">
            <div>
                <span className="text-primary font-bold">You:</span> hi_codrag
            </div>
            <div className="pl-4 border-l-2 border-border-subtle">
                <span className="text-xs text-text-muted uppercase tracking-wider">Cascade calls hi_codrag</span>
            </div>
            <div>
                <span className="text-primary font-bold">Cascade:</span> I&apos;m looking at your project &mdash; you&apos;ve selected 8 design docs and 18 React components in <code>src/components/</code>.
                <br/><br/>
                <span className="font-sans text-text-muted text-xs">Your design docs cover: &quot;Overall Upgrade Plan&quot; (phased site redesign), &quot;Hero Section Design&quot; (parallax layout), and &quot;Trust Section with Parallax&quot;. It looks like you&apos;re working on <span className="font-semibold text-text">animation &amp; visuals</span> (<code>ParallaxController.tsx</code>, <code>CanvasBackground.tsx</code>) and <span className="font-semibold text-text">UI components</span> (<code>EnhancedHero.tsx</code>, <code>CardsSection.tsx</code>). The most connected components are <code>EnhancedHero.tsx</code> (6 connections) and <code>ParallaxController.tsx</code> (4 connections).</span>
                <ol className="list-decimal pl-5 mt-2 space-y-1 font-sans text-text-muted">
                  <li>What UI components are here and how do they connect?</li>
                  <li>Compare the design docs to the implementation &mdash; anything out of sync?</li>
                  <li>Summarize the design docs and identify next steps</li>
                </ol>
            </div>
            <div>
                <span className="text-primary font-bold">You:</span> 3
            </div>
            <div className="pl-4 border-l-2 border-border-subtle">
                <span className="text-xs text-text-muted uppercase tracking-wider">Cascade calls codrag_search</span>
            </div>
            <div>
                <span className="text-primary font-bold">Cascade:</span> Looking at your design docs vs the code, I can see the hero section design specifies a parallax scroll effect &mdash; and you have both <code>EnhancedHero.tsx</code> and <code>PercentageBasedHero.tsx</code>. It looks like you&apos;re mid-migration...
            </div>
          </div>

          <h3 className="text-xl font-semibold mt-6">Other Triggers</h3>
          <p>
            While Cascade is smart, you can trigger specific CoDRAG behaviors with keywords:
          </p>
          
          <div className="space-y-4 mt-4">
            <div className="border-l-4 border-primary pl-4 py-1">
              <div className="font-bold text-sm">&quot;hi_codrag&quot;</div>
              <div className="text-sm text-text-muted">See what CoDRAG knows about your selected files. Best first step for any new conversation.</div>
            </div>

            <div className="border-l-4 border-primary pl-4 py-1">
              <div className="font-bold text-sm">&quot;Find the context...&quot;</div>
              <div className="text-sm text-text-muted">Triggers <code>codrag_search</code>. Great for finding relevant files based on meaning, not just keywords.</div>
            </div>

            <div className="border-l-4 border-primary pl-4 py-1">
              <div className="font-bold text-sm">&quot;Graph the callers of...&quot;</div>
              <div className="text-sm text-text-muted">Encourages usage of <code>codrag</code> with <code>trace_expand: true</code>. This uses the Rust code graph to pull in dependencies.</div>
            </div>

            <div className="border-l-4 border-primary pl-4 py-1">
              <div className="font-bold text-sm">&quot;Compress the context...&quot;</div>
              <div className="text-sm text-text-muted">Triggers <code>codrag</code> with <code>compression: &quot;auto&quot;</code> &mdash; structural for code, language-aware for docs.</div>
            </div>

            <div className="border-l-4 border-primary pl-4 py-1">
              <div className="font-bold text-sm">&quot;Audit my codebase&quot;</div>
              <div className="text-sm text-text-muted">Triggers <code>codrag_audit</code>. Runs 11 structural analyzers against your trace graph &mdash; no LLM required. Say &quot;fix ARCH-1&quot; to get trace context + action plan. <a href="/guides/codebase-audit" className="text-primary hover:underline">Learn more →</a></div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
