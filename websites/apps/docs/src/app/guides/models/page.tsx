import { Image as ImageIcon } from 'lucide-react';
import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 py-16">
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

          <AnchorHeading id="recommended-stack" level="h2">Recommended Stack</AnchorHeading>
          <p>
            We recommend the <strong>Ministral 3</strong> family (by Mistral AI) for the core analysis and reasoning loops.
            These models are optimized for edge devices and share the same architecture as our compression model (CLaRa), ensuring consistent behavior.
          </p>

          <div className="my-6 grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-semibold text-primary">⚡ Small Model</div>
              <div className="text-sm font-mono mt-1">ministral-3:3b</div>
              <p className="mt-2 text-xs text-text-muted">
                Used for fast parsing, intent detection, and auto-tagging during indexing.
                Low latency is critical here.
              </p>
              <a 
                href="https://ollama.com/library/ministral-3" 
                target="_blank" 
                rel="noreferrer"
                className="mt-3 inline-block text-xs text-primary hover:underline"
              >
                View on Ollama ↗
              </a>
            </div>

            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-semibold text-primary">🧠 Large Model</div>
              <div className="text-sm font-mono mt-1">ministral-3:8b</div>
              <p className="mt-2 text-xs text-text-muted">
                Used for complex reasoning, synthesis, and answering &quot;explain this&quot; style questions.
                Prioritizes quality over speed.
              </p>
              <a 
                href="https://ollama.com/library/ministral-3" 
                target="_blank" 
                rel="noreferrer"
                className="mt-3 inline-block text-xs text-primary hover:underline"
              >
                View on Ollama ↗
              </a>
            </div>
          </div>

          <AnchorHeading id="why-ministral" level="h3">Why Ministral 3?</AnchorHeading>
          <ul className="list-disc pl-6 space-y-2">
            <li>
              <strong>Edge Optimization:</strong> Designed specifically for local inference, offering SOTA performance for models under 10B parameters.
            </li>
            <li>
              <strong>CLaRa Compatibility:</strong> Our optional compression model, <a href="/guides/clara" className="text-primary hover:underline">CLaRa</a>, is based on the Mistral-7B architecture. 
              Using Ministral for generation ensures consistent tokenization and allows for potential shared memory optimizations in future updates.
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
              <p className="text-sm text-text-muted mb-2"><code>Default: nomic-embed-text</code></p>
              <p>
                Converts code and documentation into vectors for semantic search. 
                CoDRAG includes a built-in ONNX runtime for this, so you don&apos;t need Ollama running to get basic semantic search working, but you can also run it in Ollama -- really makes no difference.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold">2. Small Model</h3>
              <p className="text-sm text-text-muted mb-2"><code>Default: ministral-3:3b</code></p>
              <p>
                A high-speed model used for background tasks. When you import a project, this model (if enabled)
                scans files to generate tags and detect purpose without slowing down the indexing process.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold">3. Large Model</h3>
              <p className="text-sm text-text-muted mb-2"><code>Default: ministral-3:8b</code></p>
              <p className="text-sm text-text-muted mb-2"><code>Recommended: ministral-3:14b</code></p>
              <p className="text-sm text-text-muted mb-2"><code>BYOK: Any frontier model, Claude </code></p>
              <p>
                The &quot;smart&quot; model used when you ask questions in the chat interface. 
                It takes the retrieved context and synthesizes an answer.<br/>
                For BYOK models, something like a Claude Sonnet model works well -- you don&apos;t need the best model out there. BYOK is good for speed and convienience.
              </p>
            </div>

            <div>
              <h3 className="text-lg font-semibold">4. CLaRa (Compression)</h3>
              <p className="text-sm text-text-muted mb-2">Default: <code>apple/CLaRa-7B-Instruct</code></p>
              <p>
                An optional specialized model that compresses retrieved context by up to 16x. 
                This allows you to fit vastly more files into the context window of your Large Model. We do NOT reccommend leveraging this to &quot;use your whole codebase&quot; as RAG
                 -- rather it&apos;s better to use it strategically. For instance after your codebase grows and an your docs + design + planning folder grows to a massive size 
                 (very common in AI augmented workflows), you can use CLaRa to compress those files and fit more <em>*targeted*</em> context into the context window.
                <a href="/guides/clara" className="ml-1 text-primary hover:underline">Read the full CLaRa guide →</a>
              </p>
            </div>
          </div>

          <div className="mt-8 rounded-lg bg-surface border border-border p-4">
            <h4 className="font-semibold flex items-center gap-2">
              <span className="text-xl">💡</span>
              Single Model Fallback
            </h4>
            <p className="mt-2 text-sm">
              If you only have resources to run one model (e.g., <code>ministral-3:8b</code>), CoDRAG will use it for both &quot;Small&quot; and &quot;Large&quot; tasks.
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
