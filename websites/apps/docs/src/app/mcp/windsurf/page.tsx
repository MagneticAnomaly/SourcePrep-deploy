import { Image as ImageIcon } from 'lucide-react';
import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 py-16">
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
              <strong>Ensure CoDRAG is running.</strong> Open the CoDRAG desktop app or run <code>codrag serve</code>.
            </li>
            <li>
              <strong>Configure MCP.</strong> Windsurf reads MCP configuration from <code>~/.codeium/windsurf/mcp_config.json</code> (or via the UI in recent versions).
              <p className="mt-2 text-sm text-text-muted">
                Tip: Run <code>codrag mcp-config --ide windsurf</code> to generate the config block below.
              </p>
            </li>
            <li>
              <strong>Add Server Config.</strong> Add the CoDRAG command to your config:
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
                <p className="font-medium">Screenshot: Windsurf Config File</p>
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
            Cascade (Windsurf&apos;s agent) is highly proactive. It will see the <code>codrag</code> tools (<code>codrag_search</code>, <code>codrag</code> (context), etc.) and call them automatically.
          </p>

          <h3 className="text-xl font-semibold mt-6">The &quot;Magic&quot; Words</h3>
          <p>
            While Cascade is smart, you can trigger specific CoDRAG behaviors with keywords:
          </p>
          
          <div className="space-y-4 mt-4">
            <div className="border-l-4 border-primary pl-4 py-1">
              <div className="font-bold text-sm">&quot;Find the context...&quot;</div>
              <div className="text-sm text-text-muted">Triggers <code>codrag_search</code>. Great for finding relevant files based on meaning, not just keywords.</div>
            </div>

            <div className="border-l-4 border-primary pl-4 py-1">
              <div className="font-bold text-sm">&quot;Graph the callers of...&quot;</div>
              <div className="text-sm text-text-muted">Encourages usage of <code>codrag</code> with <code>trace_expand: true</code>. This uses the Rust code graph to pull in dependencies.</div>
            </div>

            <div className="border-l-4 border-primary pl-4 py-1">
              <div className="font-bold text-sm">&quot;Compress the docs...&quot;</div>
              <div className="text-sm text-text-muted">Triggers <code>codrag</code> with <code>compression: &quot;clara&quot;</code> (if CLaRa is configured).</div>
            </div>
          </div>

          <h3 className="text-xl font-semibold mt-6">Example Conversation</h3>
          <div className="bg-surface border border-border p-4 rounded-lg font-mono text-sm my-4 space-y-4">
            <div>
                <span className="text-primary font-bold">You:</span> I need to fix a bug in the billing logic. Graph where `process_charge` is called and check for error handling gaps.
            </div>
            <div className="pl-4 border-l-2 border-border-subtle">
                <span className="text-xs text-text-muted uppercase tracking-wider">Cascade Actions</span><br/>
                <span className="text-info">Running codrag(query=&quot;callers of process_charge&quot;, trace_expand=true)</span>
            </div>
            <div>
                <span className="text-primary font-bold">Cascade:</span> I found 3 calls to `process_charge` in `payment_service.py` and `invoice_worker.py`. The call in `invoice_worker.py` (line 45) is inside a try/catch, but the one in `payment_service.py` isn&apos;t. Here is the plan...
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
