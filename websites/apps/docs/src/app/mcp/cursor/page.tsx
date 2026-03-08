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
             {/* Cursor Logo Placeholder */}
             <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-8 h-8"><path d="M12 19l7-7 3 3-7 7-3-3z"></path><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"></path><path d="M2 2l7.586 7.586"></path><path d="M11 11l-4 4"></path></svg>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">
            CoDRAG + Cursor
          </h1>
        </div>
        
        <p className="mt-4 text-lg text-text-muted">
          Connect CoDRAG&apos;s structural index to Cursor&apos;s Agent mode.
        </p>

        <div className="mt-8 prose  max-w-none">
          <AnchorHeading id="setup" level="h2">Setup</AnchorHeading>
          <ol className="list-decimal pl-6 space-y-4">
            <li>
              <span className="font-semibold text-text">Ensure CoDRAG is running.</span> Open the CoDRAG desktop app or run <code>codrag serve</code> in your terminal. 
              The server runs on <code>http://localhost:8400</code> by default.
            </li>
            <li>
              <span className="font-semibold text-text">Open Cursor Settings.</span> Go to <code>Cursor Settings &gt; Features &gt; MCP</code>.
              <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2 not-prose">
                <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
                  <ImageIcon className="w-6 h-6" />
                </div>
                <p className="font-medium text-text">Screenshot: Cursor MCP Settings</p>
                <p className="text-sm text-center">Show the Cursor Settings window navigated to the &apos;Features &gt; MCP&apos; tab.</p>
              </div>
            </li>
            <li>
              <span className="font-semibold text-text">Add New MCP Server.</span> Click &quot;+ Add New MCP Server&quot;.
              <p className="mt-2 text-sm text-text-muted">
                Tip: Run <code>codrag mcp-config --ide cursor</code> to get the exact JSON configuration.
              </p>
              <ul className="list-disc pl-6 mt-2 space-y-1 text-sm text-text-muted">
                <li><span className="font-semibold text-text">Type:</span> <code>command</code> (Stdio)</li>
                <li><span className="font-semibold text-text">Name:</span> <code>codrag</code></li>
                <li><span className="font-semibold text-text">Command:</span> <code>codrag</code> (or absolute path if not in PATH)</li>
                <li><span className="font-semibold text-text">Args:</span> <code>mcp</code></li>
              </ul>
              <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2 not-prose">
                <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
                  <ImageIcon className="w-6 h-6" />
                </div>
                <p className="font-medium text-text">Screenshot: Add Server Dialog</p>
                <p className="text-sm text-center">Show the &apos;Add New MCP Server&apos; form filled out with the correct values.</p>
              </div>
            </li>
            <li>
              <span className="font-semibold text-text">Verify Connection.</span> You should see a green indicator next to &quot;codrag&quot;.
              <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2 not-prose">
                <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
                  <ImageIcon className="w-6 h-6" />
                </div>
                <p className="font-medium text-text">Screenshot: Connected Status</p>
                <p className="text-sm text-center">Show the green &apos;Connected&apos; light next to the codrag server in the list.</p>
              </div>
            </li>
          </ol>

          <hr className="my-8 border-border" />

          <AnchorHeading id="usage" level="h2">How to Use</AnchorHeading>
          <p>
            Once connected, Cursor&apos;s &quot;Agent&quot; mode (Cmd+K or Chat) will automatically detect and use CoDRAG tools when it needs to find context.
            You generally do not need to invoke it explicitly, but you can guide it.
          </p>

          <h3 className="text-xl font-semibold mt-6">Natural Language (Implicit)</h3>
          <p>Just ask questions that require codebase knowledge. Cursor will decide to call <code>codrag_search</code>, <code>codrag</code>, or <code>codrag_audit</code>.</p>
          <div className="bg-surface border border-border p-4 rounded-lg font-mono text-sm my-4">
            <span className="text-primary font-bold">User:</span> How does the authentication middleware handle expired tokens?<br/><br/>
            <span className="text-text-muted italic">Cursor (Thinking): Use codrag_search query=&quot;authentication middleware expired token&quot;...</span><br/><br/>
            <span className="text-text-muted italic">Tool Output: [Found 3 chunks in src/middleware/auth.ts...]</span><br/><br/>
            <span className="text-text font-bold">Cursor:</span> The authentication middleware checks for expiration in `validateToken`...
          </div>

          <h3 className="text-xl font-semibold mt-6">Explicit Invocation</h3>
          <p>If Cursor is being stubborn or using its own limited search, you can explicitly tell it to use CoDRAG tools.</p>
          <div className="bg-surface border border-border p-4 rounded-lg font-mono text-sm my-4">
            <span className="text-primary font-bold">User:</span> Use @codrag to find all calls to `processPayment` and map out the flow.<br/>
          </div>
          <p>
            Common triggers:
            <ul className="list-disc pl-6 mt-2">
              <li>&quot;Use codrag to search for...&quot;</li>
              <li>&quot;Get the code graph for symbol X...&quot; (uses <code>codrag</code> with <code>trace_expand=true</code>)</li>
              <li>&quot;Compress the context for the auth module...&quot; (uses <code>compression: &quot;auto&quot;</code>)</li>
              <li>&quot;Audit my codebase&quot; (uses <code>codrag_audit</code> &mdash; 11 structural analyzers, no LLM needed)</li>
            </ul>
          </p>

          <div className="mt-6 bg-info/10 border border-info/20 p-4 rounded-lg">
             <h4 className="font-bold text-info flex items-center gap-2">Pro Tip: Graph Expansion</h4>
             <p className="text-sm mt-1">
               Cursor doesn&apos;t know about structural code graphs by default. Ask it to &quot;trace the dependencies&quot; to encourage it to use the <code>trace_expand</code> parameter in CoDRAG&apos;s tools.
             </p>
          </div>
        </div>
      </div>
    </main>
  );
}
