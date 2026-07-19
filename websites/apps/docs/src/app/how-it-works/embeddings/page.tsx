"use client";

import { AnchorHeading } from '../../../components/AnchorHeading';
import { ConceptPageShell } from '../../../components/ConceptPageShell';
import { DemoModelCardConnected } from '../../../components/demos';

const SECTIONS = [
  { id: 'tiers',         label: 'Three Tiers at a Glance' },
  { id: 'cpu-is-fine',   label: 'Why CPU Is Fine' },
  { id: 'configuring',   label: 'Configuring Your Tier' },
  { id: 'pre-download',  label: 'Pre-Downloading' },
  { id: 'api-reference', label: 'API Reference' },
];

export default function Page() {
  return (
    <ConceptPageShell
      subtitle="How It Works"
      title="Embedding Models"
      description="Three embedding tiers — from a zero-dependency CPU fallback to a GPU-accelerated code-specialized model. Pick the one that fits your hardware."
      sections={SECTIONS}
    >
        <section id="tiers">
          <AnchorHeading id="tiers" level="h2">Three tiers at a glance</AnchorHeading>

          <div className="mt-6 space-y-4">
            {/* Tier 1 — nomic-embed-code */}
            <div className="rounded-lg border border-border bg-surface p-5">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-text-muted px-2 py-0.5 rounded-full bg-surface-raised border border-border">GPU Option</span>
                <code className="text-sm font-mono font-semibold">nomic-embed-code</code>
                <span className="text-xs text-text-muted ml-auto">via Ollama · ~4 GB</span>
              </div>
              <p className="text-sm text-text-muted leading-relaxed">
                Code-specialized model built on a 7B-parameter backbone (Qwen2). Trained specifically
                on source code. Useful for very large code-heavy codebases where the broader
                training data may help. In our benchmark the built-in ONNX model scored slightly
                higher, so this is a flexibility option, not a quality upgrade. <span className="font-semibold text-text">GPU strongly recommended.</span> Ollama silently falls back to CPU when no GPU is present, but a 7B model is too slow on CPU for practical indexing of large codebases.
              </p>
              <div className="mt-3 flex flex-wrap gap-4 text-xs text-text-muted">
                <span>3 584-dim embeddings (Matryoshka-truncated to 768)</span>
                <span>·</span>
                <span>GPU required (Ollama)</span>
                <span>·</span>
                <span>~4 GB download</span>
              </div>
              <div className="mt-3 rounded bg-surface border border-border p-3 font-mono text-xs">
                ollama pull manutic/nomic-embed-code
              </div>
            </div>

            {/* Tier 2 — nomic-embed-text via Ollama */}
            <div className="rounded-lg border border-border bg-surface p-5">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-text-muted px-2 py-0.5 rounded-full bg-surface-raised border border-border">GPU Optional</span>
                <code className="text-sm font-mono font-semibold">nomic-embed-text</code>
                <span className="text-xs text-text-muted ml-auto">via Ollama · ~274 MB</span>
              </div>
              <p className="text-sm text-text-muted leading-relaxed">
                General-purpose text + code embedding model. Excellent quality, much smaller footprint
                than the code-specialized model. Good choice if you have Ollama running but lack a
                dedicated GPU, or if your codebase is mixed text and code.
              </p>
              <div className="mt-3 flex flex-wrap gap-4 text-xs text-text-muted">
                <span>768-dim embeddings</span>
                <span>·</span>
                <span>Ollama required</span>
                <span>·</span>
                <span>~274 MB download</span>
              </div>
              <div className="mt-3 rounded bg-surface border border-border p-3 font-mono text-xs">
                ollama pull nomic-embed-text
              </div>
            </div>

            {/* Tier 3 — Built-in ONNX */}
            <div className="rounded-lg border border-primary/30 bg-primary/5 p-5">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-primary px-2 py-0.5 rounded-full bg-primary/10 border border-primary/20">Recommended · Best Accuracy</span>
                <code className="text-sm font-mono font-semibold">nomic-embed-text-v1.5</code>
                <span className="text-xs text-text-muted ml-auto">Built-in ONNX · ~132 MB</span>
              </div>
              <p className="text-sm text-text-muted leading-relaxed">
                The same nomic-embed-text model, shipped as a quantized ONNX file that SourcePrep
                downloads automatically from HuggingFace. <span className="font-semibold text-text">Runs entirely on CPU — no GPU,
                no Ollama, no external service needed.</span> CPU inference is perfectly fine for
                indexing and search; embedding speed is not a bottleneck in normal usage. This is the
                zero-config default for any machine without Ollama.
              </p>
              <div className="mt-3 flex flex-wrap gap-4 text-xs text-text-muted">
                <span>768-dim embeddings</span>
                <span>·</span>
                <span>CPU only · no GPU needed</span>
                <span>·</span>
                <span>~132 MB download (auto, one-time)</span>
                <span>·</span>
                <span>cached at <code>~/.cache/huggingface/</code></span>
              </div>
              <div className="mt-3 rounded bg-surface border border-border p-3 font-mono text-xs">
                <span className="text-text-muted"># No setup — downloads automatically on first build</span>
                <div className="mt-1">prep build</div>
              </div>
            </div>
          </div>

          {/* Comparison table */}
          <div className="mt-8 overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 pr-4 font-medium text-text">Model</th>
                  <th className="text-left py-2 pr-4 font-medium text-text">Size</th>
                  <th className="text-left py-2 pr-4 font-medium text-text">GPU?</th>
                  <th className="text-right py-2 pr-4 font-medium text-text">Accuracy (R@1)</th>
                  <th className="text-right py-2 pr-4 font-medium text-text">Query speed</th>
                  <th className="text-left py-2 font-medium text-text">Best for</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr>
                  <td className="py-2 pr-4 font-mono text-xs">nomic-embed-code</td>
                  <td className="py-2 pr-4 text-text-muted">~4 GB</td>
                  <td className="py-2 pr-4 text-text-muted">Required</td>
                  <td className="py-2 pr-4 text-right text-text-muted">82.1%</td>
                  <td className="py-2 pr-4 text-right text-text-muted">~148 ms</td>
                  <td className="py-2 text-text-muted">Large code repos, Ollama users</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-mono text-xs">nomic-embed-text</td>
                  <td className="py-2 pr-4 text-text-muted">~274 MB</td>
                  <td className="py-2 pr-4 text-text-muted">Optional</td>
                  <td className="py-2 pr-4 text-right text-text-muted">82.1%</td>
                  <td className="py-2 pr-4 text-right text-text-muted">~25 ms</td>
                  <td className="py-2 text-text-muted">Mixed repos, Ollama users</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-mono text-xs">nomic-embed-text-v1.5</td>
                  <td className="py-2 pr-4 text-text-muted">~132 MB</td>
                  <td className="py-2 pr-4 text-text-muted">None</td>
                  <td className="py-2 pr-4 text-right font-semibold text-primary">84.6%</td>
                  <td className="py-2 pr-4 text-right text-text-muted">~7 ms</td>
                  <td className="py-2 text-text-muted">Best accuracy, zero-config default</td>
                </tr>
              </tbody>
            </table>
            <p className="mt-2 text-xs text-text-muted">
              Benchmark: 39 code-retrieval queries across a 22-file fixture.
              R@1 = percentage of queries where the correct file was the #1 result.
              All tiers achieve 97%+ Recall@5. Query speed = median embed + search (p50).
            </p>
          </div>
        </section>

        {/* Why CPU is fine */}
        <section id="cpu-is-fine">
          <AnchorHeading id="cpu-is-fine" level="h2">Why CPU inference is fine for the built-in model</AnchorHeading>
          <p className="mt-3 text-text-muted leading-relaxed">
            The built-in ONNX model runs on CPU using ONNX Runtime — and that is intentional.
            Embedding happens <em>at index build time</em> (once when you add or change files), not
            at query time. A 50 000-file codebase takes a few minutes to embed on a modern CPU.
            Subsequent incremental builds only re-embed changed files.
          </p>
          <p className="mt-3 text-text-muted leading-relaxed">
            During search, only the <em>query</em> is embedded on the fly (one tiny vector per
            search), which takes under 10 ms on CPU. There is no perceptible latency difference
            between CPU and GPU for query-time embedding.
          </p>
          <div className="mt-4 rounded-lg border border-border bg-surface p-4 text-sm text-text-muted">
            <span className="font-semibold text-text">Bottom line:</span> Use the built-in ONNX model if you
            don&apos;t have Ollama or a GPU. Upgrade to <code>nomic-embed-code</code> via Ollama
            when you want the highest retrieval quality and have a GPU available.
          </div>
        </section>

        {/* Configuring the tier */}
        <section id="configuring">
          <AnchorHeading id="configuring" level="h2">Configuring your embedding tier</AnchorHeading>

          <div className="not-prose mt-6">
            <DemoModelCardConnected />
            <p className="text-xs text-text-subtle italic -mt-4">
              The Embedding model slot in Settings → AI Models — pick an endpoint and the dashboard auto-detects the model.
            </p>
          </div>

          <h3 className="mt-6 text-base font-semibold">Tier 1: nomic-embed-code via Ollama (recommended)</h3>
          <ol className="mt-3 space-y-1.5 text-sm text-text-muted list-decimal pl-5">
            <li>Install Ollama and ensure a GPU is available</li>
            <li><code>ollama pull manutic/nomic-embed-code</code></li>
            <li>In the dashboard: <span className="font-semibold text-text">Settings → AI Models → Embedding → Use Endpoint</span></li>
            <li>Select your Ollama endpoint — the model is auto-selected if found</li>
            <li>Rebuild your project</li>
          </ol>

          <h3 className="mt-6 text-base font-semibold">Tier 2: nomic-embed-text via Ollama</h3>
          <ol className="mt-3 space-y-1.5 text-sm text-text-muted list-decimal pl-5">
            <li><code>ollama pull nomic-embed-text</code></li>
            <li>In the dashboard: <span className="font-semibold text-text">Settings → AI Models → Embedding → Use Endpoint</span></li>
            <li>Select your Ollama endpoint and choose <code>nomic-embed-text</code></li>
            <li>Rebuild your project</li>
          </ol>

          <h3 className="mt-6 text-base font-semibold">Tier 3: Built-in ONNX (default, no setup required)</h3>
          <p className="mt-3 text-sm text-text-muted">
            Nothing to configure — this is the default. On first build SourcePrep downloads
            the quantized ONNX model (~132 MB) from HuggingFace and caches it locally.
            To pre-download before your first build:
          </p>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm">
            prep models
          </div>
          <p className="mt-2 text-xs text-text-muted">
            Cached at <code>~/.cache/huggingface/hub/</code>. No re-download on subsequent runs.
          </p>
          <p className="mt-3 text-sm text-text-muted">
            You can also switch to it explicitly in the dashboard:
            <span className="font-semibold text-text"> Settings → AI Models → Embedding → Download from HF</span>.
          </p>

          <div className="mt-6 rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-4 text-sm text-text-muted">
            <span className="font-semibold text-yellow-600">Switching models requires a rebuild.</span>{' '}
            Embeddings from different models have different dimensions and are not compatible.
            After changing the embedding tier, trigger a full rebuild from the dashboard or
            run <code>prep build --full</code>.
          </div>
        </section>

        {/* Pre-download */}
        <section id="pre-download">
          <AnchorHeading id="pre-download" level="h2">Pre-downloading the built-in model</AnchorHeading>
          <p className="mt-3 text-text-muted leading-relaxed">
            Useful for restricted networks or air-gapped environments.
          </p>

          <h3 className="mt-4 text-base font-medium text-text">Via CLI</h3>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm">
            prep models
          </div>

          <h3 className="mt-4 text-base font-medium text-text">Via API</h3>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div className="text-text-muted"># Check status</div>
            <div>curl http://localhost:8400/embedding/status</div>
            <div className="mt-3 text-text-muted"># Trigger download</div>
            <div>curl -X POST http://localhost:8400/embedding/download</div>
          </div>
        </section>

        {/* API Reference */}
        <section id="api-reference">
          <AnchorHeading id="api-reference" level="h2">API reference</AnchorHeading>
          <div className="mt-4 space-y-4">
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-mono text-sm font-medium text-text">GET /embedding/status</div>
              <p className="mt-1 text-sm text-text-muted">
                Returns whether native embeddings are available, the model cache path, and HuggingFace
                repo info.
              </p>
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-mono text-sm font-medium text-text">POST /embedding/download</div>
              <p className="mt-1 text-sm text-text-muted">
                Downloads the ONNX model (~132 MB) from HuggingFace Hub to the local cache.
                Blocking — returns when complete. Safe to call multiple times (no-op if already cached).
              </p>
            </div>
          </div>
        </section>
    </ConceptPageShell>
  );
}
