import { Image as ImageIcon } from 'lucide-react';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <a href="/guides" className="text-sm text-text-muted">
          ← Guides
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Context Compression (CLaRa)</h1>
        <p className="mt-4 text-lg text-text-muted">
          CLaRa compresses retrieved context before it reaches your LLM — fitting more relevant
          information into the same token budget. Compression ratios of 10–16× are typical.
        </p>

        {/* What is CLaRa */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">What is CLaRa?</h2>
          <p className="mt-3 text-text-muted leading-relaxed">
            <a href="https://github.com/EricBintner/CLaRa-Remembers-It-All" className="text-primary hover:underline">
              CLaRa-Remembers-It-All
            </a>{' '}
            is a local sidecar server that runs Apple&apos;s CLaRa-7B compression model. CoDRAG sends
            retrieved code chunks to CLaRa as &quot;memories,&quot; and CLaRa returns a compressed
            summary focused on your query.
          </p>
          <ul className="mt-4 space-y-2 text-sm text-text-muted list-disc pl-5">
            <li>Runs locally — no data leaves your machine</li>
            <li>Query-aware — compression focuses on what you asked for</li>
            <li>Best-effort — if CLaRa is unavailable, CoDRAG returns uncompressed context</li>
            <li>Works via API and MCP</li>
          </ul>
        </section>

        {/* Architecture */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">Architecture</h2>
          <div className="mt-4 rounded-lg bg-surface border border-border p-6 font-mono text-sm leading-relaxed">
            <div className="text-text-muted">┌─────────────┐    ┌──────────────┐    ┌─────────────┐</div>
            <div className="text-text-muted">│  Your IDE   │───▶│   CoDRAG     │───▶│   CLaRa     │</div>
            <div className="text-text-muted">│  (Cursor,   │    │  :4966       │    │  :8765      │</div>
            <div className="text-text-muted">│  Windsurf)  │◀───│  search +    │◀───│  /compress  │</div>
            <div className="text-text-muted">└─────────────┘    │  compress    │    └─────────────┘</div>
            <div className="text-text-muted">                   └──────────────┘</div>
          </div>
          <p className="mt-3 text-sm text-text-muted">
            CoDRAG retrieves the best chunks, assembles context, then sends it to CLaRa for
            compression. The compressed result is returned to your IDE.
          </p>
        </section>

        {/* Setup */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">Setup</h2>

          <h3 className="mt-6 text-lg font-medium">1. Start the CLaRa server</h3>
          <p className="mt-2 text-sm text-text-muted">
            The easiest way is Docker:
          </p>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div>docker run -d --name clara \</div>
            <div>  -p 8765:8765 \</div>
            <div>  --gpus all \</div>
            <div>  ericbintner/clara-server:latest</div>
          </div>
          
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface-raised flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium">Screenshot: CLaRa Docker Terminal</p>
            <p className="text-sm text-center">Show the terminal output of the docker container running CLaRa successfully.</p>
          </div>

          <p className="mt-3 text-sm text-text-muted">
            Or run from source:
          </p>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div>git clone https://github.com/EricBintner/CLaRa-Remembers-It-All</div>
            <div>cd CLaRa-Remembers-It-All</div>
            <div>pip install -r requirements.txt</div>
            <div>python server.py</div>
          </div>

          <h3 className="mt-6 text-lg font-medium">2. Verify CLaRa is running</h3>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div className="text-text-muted"># Health check</div>
            <div>curl http://localhost:8765/health</div>
            <div className="mt-2 text-text-muted"># Or via CoDRAG</div>
            <div>curl http://localhost:8400/clara/status</div>
          </div>

          <h3 className="mt-6 text-lg font-medium">3. Configure in dashboard (optional)</h3>
          <p className="mt-2 text-sm text-text-muted">
            Go to <strong>Settings → AI Models → CLaRa</strong> to configure the server URL or
            download the model via HuggingFace.
          </p>
          
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface-raised flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium">Screenshot: Settings - CLaRa Config</p>
            <p className="text-sm text-center">Show the AI Models Settings panel with the CLaRa section expanded and configured.</p>
          </div>
        </section>

        {/* Usage */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">Usage</h2>

          <h3 className="mt-6 text-lg font-medium">Via Dashboard</h3>
          <p className="mt-2 text-sm text-text-muted">
            In the <strong>Context Assembler</strong> panel, toggle the <strong>Compression</strong> switch.
            When you click "Assemble", CoDRAG will pass the retrieved chunks through CLaRa before displaying the final prompt.
          </p>
          <div className="mt-2 p-3 bg-surface-raised border border-border rounded text-xs text-text-subtle">
            <strong>Note:</strong> Compression adds latency (usually 2-5 seconds depending on hardware). The "Timing" stats in the response will show the breakdown.
          </div>

          <h3 className="mt-6 text-lg font-medium">Via API</h3>
          <p className="mt-2 text-sm text-text-muted">
            Add <code>compression</code> to your context request:
          </p>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div>curl -X POST http://localhost:8400/projects/my-project/context \</div>
            <div>  -H &quot;Content-Type: application/json&quot; \</div>
            <div>  -d &apos;{'{'}</div>
            <div>    &quot;query&quot;: &quot;How does authentication work?&quot;,</div>
            <div>    &quot;k&quot;: 10,</div>
            <div>    &quot;max_chars&quot;: 12000,</div>
            <div>    &quot;compression&quot;: &quot;clara&quot;,</div>
            <div>    &quot;compression_level&quot;: &quot;standard&quot;</div>
            <div>  {'}'}&apos;</div>
          </div>

          <h3 className="mt-6 text-lg font-medium">Via MCP (Cursor / Windsurf)</h3>
          <p className="mt-2 text-sm text-text-muted">
            The <code>codrag</code> tool now accepts compression parameters:
          </p>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div>{'{'}</div>
            <div>  &quot;query&quot;: &quot;How does authentication work?&quot;,</div>
            <div>  &quot;compression&quot;: &quot;clara&quot;,</div>
            <div>  &quot;compression_level&quot;: &quot;standard&quot;</div>
            <div>{'}'}</div>
          </div>
        </section>

        {/* Parameters */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">Parameters</h2>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="py-2 pr-4 font-medium">Parameter</th>
                  <th className="py-2 pr-4 font-medium">Type</th>
                  <th className="py-2 pr-4 font-medium">Default</th>
                  <th className="py-2 font-medium">Description</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono">compression</td>
                  <td className="py-2 pr-4">string</td>
                  <td className="py-2 pr-4"><code>&quot;none&quot;</code></td>
                  <td className="py-2"><code>&quot;none&quot;</code> or <code>&quot;clara&quot;</code></td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono">compression_level</td>
                  <td className="py-2 pr-4">string</td>
                  <td className="py-2 pr-4"><code>&quot;standard&quot;</code></td>
                  <td className="py-2"><code>&quot;light&quot;</code>, <code>&quot;standard&quot;</code>, or <code>&quot;aggressive&quot;</code></td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono">compression_target_chars</td>
                  <td className="py-2 pr-4">int</td>
                  <td className="py-2 pr-4"><code>max_chars</code></td>
                  <td className="py-2">Target output size. Defaults to <code>max_chars</code>.</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-mono">compression_timeout_s</td>
                  <td className="py-2 pr-4">float</td>
                  <td className="py-2 pr-4"><code>30</code></td>
                  <td className="py-2">Hard timeout for the compression step (seconds).</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Response metadata */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">Response metadata</h2>
          <p className="mt-3 text-text-muted leading-relaxed">
            When compression is active, the response includes a <code>compression</code> object:
          </p>
          <div className="mt-3 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <pre className="text-text-muted">{`{
  "context": "...",
  "compression": {
    "enabled": true,
    "mode": "clara",
    "level": "standard",
    "input_chars": 8500,
    "output_chars": 620,
    "input_tokens": 2125,
    "output_tokens": 155,
    "compression_ratio": 13.7,
    "timing_ms": 342.1,
    "error": null
  }
}`}</pre>
          </div>
        </section>

        {/* Fallback behavior */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">Fallback behavior</h2>
          <p className="mt-3 text-text-muted leading-relaxed">
            Compression is <strong>best-effort</strong>. If CLaRa is offline, times out, or returns
            an error, CoDRAG returns the original uncompressed context. The <code>compression.error</code> field
            will contain the reason.
          </p>
          <div className="mt-4 rounded-lg border border-blue-500/20 bg-blue-500/5 p-4 text-sm text-text-muted">
            <strong className="text-blue-600">Tip:</strong> You can set <code>compression_timeout_s</code> to
            control how long CoDRAG waits for CLaRa. For interactive use, 10–15s is reasonable.
            For batch workflows, 60s+ is fine.
          </div>
        </section>

        {/* API Endpoints */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">API endpoints</h2>
          <div className="mt-4 space-y-4">
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-mono text-sm font-medium">GET /clara/status</div>
              <p className="mt-1 text-sm text-text-muted">
                Returns CLaRa server status including model info, device, and availability.
              </p>
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-mono text-sm font-medium">GET /clara/health</div>
              <p className="mt-1 text-sm text-text-muted">
                Quick health check. Returns <code>{`{ "available": true/false }`}</code>.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
