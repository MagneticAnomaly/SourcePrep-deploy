import { Image as ImageIcon } from 'lucide-react';
import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/guides" className="text-sm text-text-muted">
          ← Back to Guides
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">
          Model Configuration
        </h1>
        <p className="mt-4 text-lg text-text-muted">
          Configure local LLMs for analysis, reasoning, and compression.
        </p>

        <div className="mt-8 prose  max-w-none">
          <p>
            CoDRAG uses a tiered architecture where different models handle specific tasks based on their strengths.
            While you can run everything with a single model, we recommend a specialized stack for the best balance of speed and intelligence.
          </p>

          <div className="my-6 rounded-lg border border-primary/30 bg-primary/5 p-4">
            <p className="text-sm">
              <strong>New:</strong> Use the{' '}
              <a href="/guides/model-advisor" className="text-primary hover:underline font-semibold">Model Setup Advisor</a>
              {' '}to get personalized recommendations based on your GPU and preferences.
            </p>
          </div>

          <AnchorHeading id="recommended-stack" level="h2">Recommended Stack</AnchorHeading>
          <p>
            We recommend the <strong>Qwen3</strong> family for the core analysis and reasoning loops.
            These models deliver excellent local inference performance at every size class.
          </p>

          <div className="my-6 grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-semibold text-primary">⚡ Fast Model</div>
              <div className="text-sm font-mono mt-1">qwen3:4b</div>
              <p className="mt-2 text-xs text-text-muted">
                Used for fast file cataloguing, intent detection, and auto-tagging during indexing.
                Only 2.5GB. Rivals 72B models at this size.
              </p>
              <a 
                href="https://ollama.com/library/qwen3" 
                target="_blank" 
                rel="noreferrer"
                className="mt-3 inline-block text-xs text-primary hover:underline"
              >
                View on Ollama ↗
              </a>
            </div>

            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-semibold text-primary">🧠 Thinking Model</div>
              <div className="text-sm font-mono mt-1">qwen3:8b</div>
              <p className="mt-2 text-xs text-text-muted">
                Used for complex reasoning, epistemic enrichment, and deep analysis.
                5.2GB. Alt: qwen3:14b (9.3GB) or qwen3:30b MoE (19GB) for better quality.
              </p>
              <a 
                href="https://ollama.com/library/qwen3" 
                target="_blank" 
                rel="noreferrer"
                className="mt-3 inline-block text-xs text-primary hover:underline"
              >
                View on Ollama ↗
              </a>
            </div>
          </div>

          <AnchorHeading id="why-qwen3" level="h3">Why Qwen3?</AnchorHeading>
          <ul className="list-disc pl-6 space-y-2">
            <li>
              <strong>Best-in-class small models:</strong> Qwen3:4b rivals Qwen2.5-72B on benchmarks while being tiny enough for any GPU.
            </li>
            <li>
              <strong>MoE efficiency:</strong> The 30B model only activates 3B parameters per token &mdash; outstanding reasoning with efficient VRAM use.
            </li>
            <li>
              <strong>Reliable JSON output:</strong> CoDRAG&apos;s pipeline needs structured JSON responses. Qwen3 excels at this.
            </li>
          </ul>

          <hr className="my-8 border-border" />

          <AnchorHeading id="model-slots" level="h2">Model Slots Explained</AnchorHeading>
          <p>
            CoDRAG defines four &quot;slots&quot; for AI models. You can configure these in the <strong>Settings &gt; AI Models</strong> tab of the dashboard.<br/> <br/> 
          </p>
          
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium">Screenshot: AI Models Settings</p>
            <p className="text-sm text-center">Show the dashboard settings tab with the 4 model slots (Embedding, Small, Large, Compression) visible.</p>
          </div>

          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold">1. Embedding Model (Required)</h3>
              <p className="text-sm text-text-muted mb-2"><code>Default: nomic-embed-text-v1.5 (built-in ONNX, CPU)</code></p>
              <p>
                Converts code and documentation into vectors for semantic search.
                CoDRAG supports three tiers — pick the one that fits your hardware:
              </p>
              <ul className="mt-3 space-y-2 text-sm list-disc pl-5">
                <li>
                  <strong>nomic-embed-code via Ollama</strong> — recommended for GPU users.
                  Code-specialized model (7B Qwen2 backbone), best retrieval quality for code-heavy
                  repos. ~4 GB download. Requires a GPU.{' '}
                  <code className="text-xs">ollama pull manutic/nomic-embed-code</code>
                </li>
                <li>
                  <strong>nomic-embed-text via Ollama</strong> — good quality, much smaller (~274 MB).
                  Works with or without a GPU. Good for mixed text/code repos.{' '}
                  <code className="text-xs">ollama pull nomic-embed-text</code>
                </li>
                <li>
                  <strong>Built-in ONNX (default)</strong> — the same nomic-embed-text model shipped
                  as a ~132 MB quantized ONNX file. <strong>Runs entirely on CPU</strong> — no GPU,
                  no Ollama, no external service. Downloads automatically on first build and is cached
                  at <code className="text-xs">~/.cache/huggingface/</code>.
                  CPU inference is perfectly fine: embedding happens at build time (not per-query),
                  and query-time embedding takes under 10 ms regardless.
                </li>
              </ul>
              <p className="mt-3 text-sm text-text-muted">
                See the <a href="/guides/embeddings" className="text-primary hover:underline">Embedding Models guide</a> for
                setup instructions and a full comparison table.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold">2. Fast Model</h3>
              <p className="text-sm text-text-muted mb-2"><code>Recommended: qwen3:4b</code> (2.5GB)</p>
              <p>
                A high-speed model used for background tasks. When you import a project, this model (if enabled)
                scans files to generate tags and detect purpose without slowing down the indexing process.
                Alt: <code>qwen3:1.7b</code> for very limited VRAM.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold">3. Thinking Model</h3>
              <p className="text-sm text-text-muted mb-2"><code>Recommended: qwen3:8b</code> (5.2GB)</p>
              <p className="text-sm text-text-muted mb-2"><code>Better: qwen3:14b</code> (9.3GB) or <code>qwen3:30b</code> MoE (19GB)</p>
              <p className="text-sm text-text-muted mb-2"><code>BYOK: gpt-4.1-mini, claude-sonnet-4.5, gemini-2.5-flash</code></p>
              <p>
                The reasoning model used for epistemic enrichment, clustering, and deep analysis.
                It takes each file with its neighbor context and produces extended summaries and domain tags.
                For BYOK, any mid-tier cloud model works well &mdash; you don&apos;t need the most expensive option.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold">4. Smart Compression (built-in)</h3>
              <p className="text-sm text-text-muted mb-2">No GPU required</p>
              <p>
                Two engines: <strong>structural compression</strong> for code extracts at variable Levels of Detail (LOD 0&ndash;5) based on relevance &mdash;
                3&ndash;20&times;, no model needed. <strong>Language compression</strong> for docs uses a lightweight BERT model (~178 MB) to remove filler while preserving meaning.
                <a href="/guides/compression" className="ml-1 text-primary hover:underline">Read the full compression guide &rarr;</a>
              </p>
            </div>
          </div>

          <div className="mt-8 rounded-lg bg-surface border border-border p-4">
            <h4 className="font-semibold flex items-center gap-2">
              <span className="text-xl">💡</span>
              Single Model Fallback
            </h4>
            <p className="mt-2 text-sm">
              If you only have resources to run one model (e.g., <code>qwen3:4b</code>), CoDRAG will use it for both &quot;Fast&quot; and &quot;Thinking&quot; tasks.
              You can simply select the same endpoint and model for both slots in the settings.
            </p>
          </div>

          <hr className="my-12 border-border" />

          <AnchorHeading id="managing-endpoints" level="h2">Managing Endpoints</AnchorHeading>
          <p>
            CoDRAG isn't tied to one provider. The <strong>Endpoint Manager</strong> at the bottom of the AI Models settings allows you to connect to any OpenAI-compatible API.
          </p>

          <AnchorHeading id="adding-endpoint" level="h3" className="text-xl font-semibold mt-8 mb-4">Adding a Custom Endpoint</AnchorHeading>
          <p>
            To add a local server (like LM Studio or vLLM) or a cloud provider (like Groq or OpenRouter):
          </p>
          <ol className="list-decimal pl-5 mt-2 space-y-2">
            <li>Scroll to <strong>Saved Endpoints</strong> and click <strong>Add New Endpoint</strong>.</li>
            <li><strong>Display Name:</strong> Give it a recognizable name (e.g., "LM Studio Local").</li>
            <li><strong>Provider:</strong> Select <code>OpenAI Compatible</code> for most generic servers.</li>
            <li><strong>URL:</strong> Enter the base URL.
              <ul className="list-disc pl-5 mt-1 text-sm text-text-muted">
                <li>Ollama: <code>http://localhost:11434</code></li>
                <li>LM Studio: <code>http://localhost:1234/v1</code></li>
                <li>vLLM: <code>http://localhost:8000/v1</code></li>
              </ul>
            </li>
            <li><strong>API Key:</strong> Required for cloud providers; often optional ("sk-dummy") for local servers.</li>
          </ol>

          <AnchorHeading id="testing-connection" level="h3" className="text-xl font-semibold mt-8 mb-4">Testing Connections</AnchorHeading>
          <p>
            Before assigning an endpoint to a model slot, use the <strong>Test Connection</strong> button on the model card. This performs a lightweight "handshake" (usually a list models call or a tiny completion) to verify:
          </p>
          <ul className="list-disc pl-5 mt-2 space-y-2">
            <li>The server is reachable.</li>
            <li>The API key is valid.</li>
            <li>The specific model name you entered exists on that server.</li>
          </ul>
          <div className="mt-4 p-4 rounded-md border border-warning/20 bg-warning/5 text-sm text-warning-text">
            <strong>Troubleshooting Tip:</strong> If a test fails, check your CORS settings if the server is running on a different port, or ensure the container is exposing the port to localhost.
          </div>
        </div>
      </div>
    </main>
  );
}
