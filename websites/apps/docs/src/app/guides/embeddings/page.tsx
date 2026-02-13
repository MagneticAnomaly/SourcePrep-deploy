import { Image as ImageIcon } from 'lucide-react';
import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <a href="/guides" className="text-sm text-text-muted">
          ← Guides
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Built-in Embeddings</h1>
        <p className="mt-4 text-lg text-text-muted">
          CoDRAG ships with a built-in embedding model so you can index and search your codebase
          without installing Ollama or any external service.
        </p>

        {/* How it works */}
        <section className="mt-10">
          <AnchorHeading id="how-it-works" level="h2">How it works</AnchorHeading>
          <p className="mt-3 text-text-muted leading-relaxed">
            CoDRAG uses <strong>nomic-embed-text-v1.5</strong> — a high-quality, open-source embedding
            model optimised for code and documentation. It runs locally via ONNX Runtime, so there are
            no API keys, no cloud uploads, and no GPU required.
          </p>
          <ul className="mt-4 space-y-2 text-sm text-text-muted list-disc pl-5">
            <li>768-dimensional embeddings with L2 normalisation</li>
            <li>Supports up to 8 192 tokens per chunk</li>
            <li>Quantised ONNX model — fast on CPU, ~130 MB download</li>
            <li>Cached in the standard HuggingFace cache folder (<code>~/.cache/huggingface/</code>)</li>
          </ul>
        </section>

        {/* Zero-config default */}
        <section className="mt-10">
          <AnchorHeading id="zero-config-default" level="h2">Zero-config default</AnchorHeading>
          <p className="mt-3 text-text-muted leading-relaxed">
            When you create a project and run your first build, CoDRAG automatically downloads the
            model and starts embedding. No configuration needed.
          </p>
          <div className="mt-4 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div className="text-text-muted"># Add a project and build — embeddings happen automatically</div>
            <div className="mt-1">codrag add my-project /path/to/repo</div>
            <div>codrag build my-project</div>
          </div>
        </section>

        {/* Pre-download the model */}
        <section className="mt-10">
          <AnchorHeading id="pre-download-the-model" level="h2">Pre-download the model</AnchorHeading>
          <p className="mt-3 text-text-muted leading-relaxed">
            If you want to download the model before your first build (e.g. on a restricted network),
            use the download endpoint or the dashboard.
          </p>

          <h3 className="mt-6 text-lg font-medium">Via API</h3>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div className="text-text-muted"># Check embedding status</div>
            <div>curl http://localhost:8400/embedding/status</div>
            <div className="mt-3 text-text-muted"># Trigger download</div>
            <div>curl -X POST http://localhost:8400/embedding/download</div>
          </div>

          <h3 className="mt-6 text-lg font-medium">Via CLI</h3>
          <p className="mt-2 text-sm text-text-muted">
            You can also use the CLI to download the model without starting the daemon:
          </p>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div>codrag models</div>
          </div>
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium">Screenshot: CLI Model Download</p>
            <p className="text-sm text-center">Show the terminal output of &apos;codrag models&apos; downloading the ONNX artifacts.</p>
          </div>

          <h3 className="mt-6 text-lg font-medium">Via Dashboard</h3>
          <p className="mt-2 text-sm text-text-muted">
            Go to <strong>Settings → AI Models → Embedding</strong>. If the model is not yet
            downloaded, click the download button. The progress bar shows download status.
          </p>
          <div className="my-6 p-8 border-2 border-dashed border-border rounded-lg bg-surface flex flex-col items-center justify-center text-text-muted gap-2">
            <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center">
              <ImageIcon className="w-6 h-6" />
            </div>
            <p className="font-medium">Screenshot: Embedding Settings</p>
            <p className="text-sm text-center">Show the dashboard settings panel for Embeddings with the &#39;Native ONNX&#39; option selected and status &#39;Ready&#39;.</p>
          </div>
        </section>

        {/* Switching to Ollama */}
        <section className="mt-10">
          <AnchorHeading id="switching-to-ollama" level="h2">Switching to Ollama</AnchorHeading>
          <p className="mt-3 text-text-muted leading-relaxed">
            If you prefer to use Ollama for embeddings (e.g. you already have it running with a
            different model), switch the embedding source in the dashboard:
          </p>
          <ol className="mt-4 space-y-2 text-sm text-text-muted list-decimal pl-5">
            <li>Go to <strong>Settings → AI Models → Embedding</strong></li>
            <li>Switch the source from <strong>HuggingFace</strong> to <strong>Endpoint</strong></li>
            <li>Select your Ollama endpoint and model (e.g. <code>nomic-embed-text</code>)</li>
            <li>Rebuild your project to re-embed with the new model</li>
          </ol>
          <div className="mt-4 rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-4 text-sm text-text-muted">
            <strong className="text-yellow-600">Note:</strong> Switching embedding models requires a
            full rebuild. Embeddings from different models are not compatible.
          </div>
        </section>

        {/* API Reference */}
        <section className="mt-10">
          <AnchorHeading id="api-reference" level="h2">API reference</AnchorHeading>
          <div className="mt-4 space-y-4">
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-mono text-sm font-medium">GET /embedding/status</div>
              <p className="mt-1 text-sm text-text-muted">
                Returns whether native embeddings are available, the model cache path, and HuggingFace
                repo info.
              </p>
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-mono text-sm font-medium">POST /embedding/download</div>
              <p className="mt-1 text-sm text-text-muted">
                Downloads the ONNX model from HuggingFace Hub. Blocking — returns when complete.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
