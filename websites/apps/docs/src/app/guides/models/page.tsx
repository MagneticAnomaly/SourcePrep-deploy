import { Image as ImageIcon } from 'lucide-react';
import { AnchorHeading } from '../../../components/AnchorHeading';
import { DemoAIModelsSettings } from '../../../components/demos';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/" className="text-sm text-text-muted">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">
          AI Gateway
        </h1>
        <p className="mt-4 text-lg text-text-muted">
          Connect SourcePrep to the LLMs that power deep enrichment, code reasoning, and large-context synthesis.
        </p>

        <div className="mt-8 prose  max-w-none">
          <p>
            SourcePrep uses a tiered architecture where different model slots handle different jobs based on their strengths.
            The AI Gateway is where you wire each slot to an endpoint (Ollama Cloud, OpenRouter, a local Ollama instance, or any OpenAI-compatible server).
            You can run everything with a single model in a pinch, but a small stack gives you the best speed / cost / quality balance.
          </p>

          <AnchorHeading id="recommended-stack" level="h2">Recommended stack (cloud-first)</AnchorHeading>
          <p>
            The simplest setup that performs well today. Ollama Cloud handles the bulk of the work; OpenRouter picks up large-context synthesis where its long context window helps.
          </p>

          <div className="my-6 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-text">
                  <th className="py-2 pr-4 font-medium">Slot</th>
                  <th className="py-2 pr-4 font-medium">Endpoint</th>
                  <th className="py-2 pr-4 font-medium">Model</th>
                  <th className="py-2 font-medium">Why</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text">Fast</td>
                  <td className="py-2 pr-4">Ollama Cloud</td>
                  <td className="py-2 pr-4 font-mono text-xs">gemini-3-flash-preview:cloud</td>
                  <td className="py-2">Cheap and fast for cataloguing, intent detection, and tagging.</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text">Code</td>
                  <td className="py-2 pr-4">Ollama Cloud</td>
                  <td className="py-2 pr-4 font-mono text-xs">kimi-k2.6:cloud</td>
                  <td className="py-2">Strong code-aware reasoning for inferred-edge discovery.</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text">Thinking</td>
                  <td className="py-2 pr-4">Ollama Cloud</td>
                  <td className="py-2 pr-4 font-mono text-xs">kimi-k2.6:cloud</td>
                  <td className="py-2">Same model handles deep reasoning + per-file swarm workers.</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-semibold text-text">Swarm Coordinator</td>
                  <td className="py-2 pr-4">OpenRouter</td>
                  <td className="py-2 pr-4 font-mono text-xs">qwen/qwen3.6-plus</td>
                  <td className="py-2">Cluster routing + module synthesis benefit from a fast, JSON-reliable model with a different context profile.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <AnchorHeading id="simpler-stack" level="h2">Simpler stack (all Ollama Cloud)</AnchorHeading>
          <p>
            One endpoint, no API keys to juggle, no OpenRouter account needed. Slightly slower on the synthesis stage; perfectly fine for day-to-day use.
          </p>

          <div className="my-6 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-text">
                  <th className="py-2 pr-4 font-medium">Slot</th>
                  <th className="py-2 pr-4 font-medium">Endpoint</th>
                  <th className="py-2 pr-4 font-medium">Model</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text">Fast</td>
                  <td className="py-2 pr-4">Ollama Cloud</td>
                  <td className="py-2 pr-4 font-mono text-xs">gemini-3-flash-preview:cloud</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text">Code</td>
                  <td className="py-2 pr-4">Ollama Cloud</td>
                  <td className="py-2 pr-4 font-mono text-xs">kimi-k2.6:cloud</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text">Thinking</td>
                  <td className="py-2 pr-4">Ollama Cloud</td>
                  <td className="py-2 pr-4 font-mono text-xs">kimi-k2.6:cloud</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-semibold text-text">Swarm Coordinator</td>
                  <td className="py-2 pr-4">Ollama Cloud</td>
                  <td className="py-2 pr-4 font-mono text-xs">kimi-k2.6:cloud (inherit)</td>
                </tr>
              </tbody>
            </table>
          </div>

          <AnchorHeading id="local-only-stack" level="h2">Local-only stack (no cloud)</AnchorHeading>
          <p>
            Fully offline. Requires a GPU and Ollama installed locally. The <span className="font-semibold text-text">Qwen3</span> family is the recommended baseline — best-in-class small models with reliable JSON output.
          </p>
          <ul className="mt-3 list-disc pl-6 space-y-2 text-sm">
            <li><span className="font-semibold text-text">Fast:</span> <code>qwen3:4b</code> (2.5 GB) — cataloguing, intent, tagging. Falls back here as the single model if you only configure one slot.</li>
            <li><span className="font-semibold text-text">Code:</span> <code>qwen3-coder</code> family — inferred-edge discovery on AST gaps. Falls back to Fast if unset.</li>
            <li><span className="font-semibold text-text">Thinking:</span> <code>qwen3:8b</code> (5.2 GB) — epistemic enrichment, clustering. Step up to <code>qwen3:14b</code> (9.3 GB) or <code>qwen3:30b</code> MoE (19 GB) for higher quality.</li>
            <li><span className="font-semibold text-text">Swarm Coordinator:</span> inherits Thinking by default.</li>
          </ul>
          <p className="mt-3 text-sm text-text-muted">
            See <a href="/how-it-works/dynamic-model-loading" className="text-primary hover:underline">Dynamic Model Loading</a> for how SourcePrep balances multiple local models against VRAM.
          </p>

          <hr className="my-8 border-border" />

          <AnchorHeading id="model-slots" level="h2">Model Slots Explained</AnchorHeading>
          <p>
            SourcePrep defines five &quot;slots&quot; for AI models. You can configure these in the <span className="font-semibold text-text">Settings &gt; AI Models</span> tab of the dashboard.<br/> <br/>
          </p>

          <div className="not-prose">
            <DemoAIModelsSettings />
            <p className="text-xs text-text-subtle italic -mt-4">
              Live preview: Configure the model slots in the dashboard.
            </p>
          </div>

          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold">1. Embedding Model (Required)</h3>
              <p className="text-sm text-text-muted mb-2"><code>Default: nomic-embed-text-v1.5 (built-in ONNX, CPU)</code></p>
              <p>
                Converts code and documentation into vectors for semantic search.
                SourcePrep supports three tiers — pick the one that fits your hardware:
              </p>
              <ul className="mt-3 space-y-2 text-sm list-disc pl-5">
                <li>
                  <span className="font-semibold text-text">nomic-embed-code via Ollama</span> — recommended for GPU users.
                  Code-specialized model (7B Qwen2 backbone), best retrieval quality for code-heavy
                  repos. ~4 GB download. GPU strongly recommended (Ollama silently falls back to CPU, but a 7B model is too slow on CPU for practical indexing).{' '}
                  <code className="text-xs">ollama pull manutic/nomic-embed-code</code>
                </li>
                <li>
                  <span className="font-semibold text-text">nomic-embed-text via Ollama</span> — good quality, much smaller (~274 MB).
                  Works with or without a GPU. Good for mixed text/code repos.{' '}
                  <code className="text-xs">ollama pull nomic-embed-text</code>
                </li>
                <li>
                  <span className="font-semibold text-text">Built-in ONNX (default)</span> — the same nomic-embed-text model shipped
                  as a ~132 MB quantized ONNX file. <span className="font-semibold text-text">Runs entirely on CPU</span> — no GPU,
                  no Ollama, no external service. Downloads automatically on first build and is cached
                  at <code className="text-xs">~/.cache/huggingface/</code>.
                  CPU inference is perfectly fine: embedding happens at build time (not per-query),
                  and query-time embedding takes under 10 ms regardless.
                </li>
              </ul>
              <p className="mt-3 text-sm text-text-muted">
                See the <a href="/how-it-works/embeddings" className="text-primary hover:underline">Embedding Models guide</a> for
                setup instructions and a full comparison table.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold">2. Single / Fast Model</h3>
              <p className="text-sm text-text-muted mb-2"><code>Recommended: qwen3:4b</code> (2.5GB)</p>
              <p>
                A high-speed model used for background tasks like file cataloguing,
                tagging, and intent detection during indexing. If you only configure
                this one slot, it also handles Thinking-tier work as a fallback.
                Alt: <code>qwen3:1.7b</code> for very limited VRAM.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold">3. Code Model</h3>
              <p className="text-sm text-text-muted mb-2"><code>Recommended: qwen3-coder</code> family or any code-specialized local/cloud model</p>
              <p>
                A code-specialized slot used for code-aware analysis like inferred-edge
                discovery (which call edges the AST parser missed). Falls back to the
                Single / Fast Model if not configured.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold">4. Thinking Model</h3>
              <p className="text-sm text-text-muted mb-2"><code>Recommended: qwen3:8b</code> (5.2GB) or <code>qwen3:14b</code> (9.3GB)</p>
              <p className="text-sm text-text-muted mb-2"><code>BYOK examples: gpt-4.1-mini, claude-sonnet-4.6, gemini-2.5-flash</code></p>
              <p>
                The reasoning model used for epistemic enrichment, clustering, and
                deep analysis. It takes each file with its neighbor context and produces
                extended summaries and domain tags. For BYOK, any mid-tier cloud model
                works well — you don&apos;t need the most expensive option.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold">5. Swarm Coordinator (optional)</h3>
              <p className="text-sm text-text-muted mb-2">Inherits from Thinking Model by default</p>
              <p>
                Used during the Group Reasoning stage for cluster routing and
                large-context synthesis when swarm mode is enabled. Most users
                leave this inheriting from the Thinking slot; configure it
                explicitly only when you want a different model for the
                coordinator step.
              </p>
            </div>
          </div>

          <div className="mt-6 rounded-lg border border-border bg-surface p-4 text-sm">
            <span className="font-semibold text-text">Smart Compression</span> is
            not a model slot — it&apos;s a built-in feature that runs alongside
            the slots above. It uses structural Level-of-Detail rendering
            (no model needed) plus an optional 178 MB BERT model for prose
            compression. <a href="/how-it-works/compression" className="text-primary hover:underline">Read the compression guide →</a>
          </div>

          <div className="mt-8 rounded-lg bg-surface border border-border p-4">
            <h4 className="font-semibold flex items-center gap-2">
              <span className="text-xl">💡</span>
              Single Model Fallback
            </h4>
            <p className="mt-2 text-sm">
              If you only have resources to run one model (e.g., <code>qwen3:4b</code>), SourcePrep will use it for both &quot;Fast&quot; and &quot;Thinking&quot; tasks.
              You can simply select the same endpoint and model for both slots in the settings.
            </p>
          </div>

          <hr className="my-12 border-border" />

          <AnchorHeading id="managing-endpoints" level="h2">Managing Endpoints</AnchorHeading>
          <p>
            SourcePrep isn't tied to one provider. The <span className="font-semibold text-text">Endpoint Manager</span> at the bottom of the AI Models settings allows you to connect to any OpenAI-compatible API.
          </p>

          <AnchorHeading id="adding-endpoint" level="h3" className="text-xl font-semibold mt-8 mb-4">Adding a Custom Endpoint</AnchorHeading>
          <p>
            To add a local server (like LM Studio or vLLM) or a cloud provider (like Groq or OpenRouter):
          </p>
          <ol className="list-decimal pl-5 mt-2 space-y-2">
            <li>Scroll to <span className="font-semibold text-text">Saved Endpoints</span> and click <span className="font-semibold text-text">Add New Endpoint</span>.</li>
            <li><span className="font-semibold text-text">Display Name:</span> Give it a recognizable name (e.g., "LM Studio Local").</li>
            <li><span className="font-semibold text-text">Provider:</span> Select <code>OpenAI Compatible</code> for most generic servers.</li>
            <li><span className="font-semibold text-text">URL:</span> Enter the base URL.
              <ul className="list-disc pl-5 mt-1 text-sm text-text-muted">
                <li>Ollama: <code>http://localhost:11434</code></li>
                <li>LM Studio: <code>http://localhost:1234/v1</code></li>
                <li>vLLM: <code>http://localhost:8000/v1</code></li>
              </ul>
            </li>
            <li><span className="font-semibold text-text">API Key:</span> Required for cloud providers; often optional ("sk-dummy") for local servers.</li>
          </ol>

          <AnchorHeading id="testing-connection" level="h3" className="text-xl font-semibold mt-8 mb-4">Testing Connections</AnchorHeading>
          <p>
            Before assigning an endpoint to a model slot, use the <span className="font-semibold text-text">Test Connection</span> button on the model card. This performs a lightweight "handshake" (usually a list models call or a tiny completion) to verify:
          </p>
          <ul className="list-disc pl-5 mt-2 space-y-2">
            <li>The server is reachable.</li>
            <li>The API key is valid.</li>
            <li>The specific model name you entered exists on that server.</li>
          </ul>
          <div className="mt-4 p-4 rounded-md border border-warning/20 bg-warning/5 text-sm text-warning-text">
            <span className="font-semibold text-text">Troubleshooting Tip:</span> If a test fails, check your CORS settings if the server is running on a different port, or ensure the container is exposing the port to localhost.
          </div>
        </div>
      </div>
    </main>
  );
}
