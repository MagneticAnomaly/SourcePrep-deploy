import { AnchorHeading } from '../../../components/AnchorHeading';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/guides" className="text-sm text-text-muted">
          ← Back to Guides
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">
          Dynamic Model Loading
        </h1>
        <p className="mt-4 text-lg text-text-muted">
          How CoDRAG manages VRAM by loading and unloading local models on demand,
          and what that means for your hardware setup.
        </p>

        <div className="mt-8 prose max-w-none">

          {/* ── Overview ── */}
          <AnchorHeading id="overview" level="h2">Overview</AnchorHeading>
          <p>
            CoDRAG&apos;s trace pipeline runs up to 10 different LLM tasks — from fast
            file cataloguing to deep group reasoning. Each task may use a different
            model optimized for that job. On most consumer hardware, only one or two
            models fit in VRAM/RAM at a time.
          </p>
          <p>
            <strong>Dynamic model loading</strong> is CoDRAG&apos;s system for
            automatically loading the right model before each pipeline stage and
            unloading the previous one to free memory. This happens transparently —
            you configure your models once and CoDRAG handles the rest.
          </p>

          <div className="my-6 rounded-lg border border-primary/30 bg-primary/5 p-4">
            <p className="text-sm">
              <span className="font-semibold text-text">Key concept:</span>{' '}
              Dynamic model loading only applies to <strong>local model servers</strong>.
              Cloud API providers (OpenAI, Anthropic, Google) are always &ldquo;ready&rdquo; and
              don&apos;t require VRAM management.
            </p>
          </div>

          {/* ── Provider Support ── */}
          <AnchorHeading id="provider-support" level="h2">Provider Support</AnchorHeading>

          <div className="my-6 overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 pr-4 font-semibold">Provider</th>
                  <th className="text-left py-2 pr-4 font-semibold">Dynamic Loading</th>
                  <th className="text-left py-2 pr-4 font-semibold">MLX Engine</th>
                  <th className="text-left py-2 font-semibold">Best For</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-primary">Ollama</td>
                  <td className="py-2 pr-4 text-success font-semibold">✅ Full support</td>
                  <td className="py-2 pr-4 text-text-muted">❌ Not yet (planned)</td>
                  <td className="py-2">Multi-model pipelines, automation, headless servers</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-primary">LM Studio</td>
                  <td className="py-2 pr-4 text-warning font-semibold">⚠️ Manual only</td>
                  <td className="py-2 pr-4 text-success font-semibold">✅ Built-in</td>
                  <td className="py-2">Mac users, single-model setups, maximum performance</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-primary">Cloud APIs</td>
                  <td className="py-2 pr-4 text-text-muted">N/A (always ready)</td>
                  <td className="py-2 pr-4 text-text-muted">N/A</td>
                  <td className="py-2">Zero-config, no local hardware needed</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* ── How It Works ── */}
          <AnchorHeading id="how-it-works" level="h2">How It Works (Ollama)</AnchorHeading>
          <p>
            Ollama is the only local provider that supports fully automated dynamic model loading.
            Here&apos;s what happens during a pipeline run:
          </p>

          <ol className="space-y-2">
            <li>
              <strong>Stage starts</strong> — CoDRAG checks which model is needed for the
              next task (e.g. <code>qwen3:4b</code> for cataloguing).
            </li>
            <li>
              <strong>Room check</strong> — If a different model is currently loaded,
              CoDRAG sends a <code>keep_alive=0</code> request to Ollama to unload it.
            </li>
            <li>
              <strong>Preload</strong> — CoDRAG sends an empty generate request to Ollama
              with the new model name. Ollama loads it into memory.
            </li>
            <li>
              <strong>Ready</strong> — Once loaded, the pipeline stage runs its LLM calls.
            </li>
            <li>
              <strong>Next stage</strong> — If the next stage uses the same model, it stays loaded.
              If it needs a different model, the cycle repeats.
            </li>
          </ol>

          <p>
            The entire process is transparent. You never need to manually run{' '}
            <code>ollama run</code> or worry about which model is loaded.
          </p>

          {/* ── Always Available ── */}
          <AnchorHeading id="always-available" level="h2">Always Available (Persistent Models)</AnchorHeading>
          <p>
            Some models — typically the Fast model used for cataloguing — benefit from staying
            loaded at all times. This avoids the 5–15 second cold-start delay every time a
            file changes and triggers a fast sync.
          </p>
          <p>
            In the AI Models settings, check <strong>&ldquo;Always available (Keep loaded)&rdquo;</strong> on
            any model card. CoDRAG will:
          </p>
          <ul>
            <li>Skip unloading this model between pipeline stages</li>
            <li>
              If VRAM pressure forces an eviction (e.g. a large reasoning model needs to load),
              CoDRAG will temporarily unload the persistent model, run the heavy task,
              then <strong>automatically reload</strong> the persistent model afterward
            </li>
            <li>Show a warning indicator in the AI Gateway if a persistent model was temporarily evicted</li>
          </ul>

          <div className="my-6 rounded-lg border border-warning/30 bg-warning/5 p-4">
            <p className="text-sm">
              <span className="font-semibold text-warning">VRAM tip:</span>{' '}
              On machines with limited RAM (16GB or less), avoid marking large models as
              &ldquo;Always available&rdquo;. A persistent 8B model (5GB) alongside a 30B reasoning
              model won&apos;t fit — CoDRAG will handle it gracefully via eviction, but the
              constant load/unload cycle defeats the purpose.
            </p>
          </div>

          {/* ── LM Studio ── */}
          <AnchorHeading id="lm-studio" level="h2">LM Studio &amp; MLX</AnchorHeading>
          <p>
            <a href="https://lmstudio.ai" target="_blank" rel="noreferrer" className="text-primary hover:underline">LM Studio</a>{' '}
            is a graphical model server with a built-in <strong>MLX backend</strong>. MLX is
            Apple&apos;s machine learning framework, purpose-built for Apple Silicon. It uses
            unified memory more efficiently than the GGUF/llama.cpp backend that Ollama uses.
          </p>

          <AnchorHeading id="why-lm-studio" level="h3">Why consider LM Studio?</AnchorHeading>
          <ul>
            <li>
              <strong>MLX performance:</strong> On Apple Silicon Macs (M1–M5), MLX models
              run faster and use less memory than the equivalent GGUF model in Ollama.
            </li>
            <li>
              <strong>Unified memory advantage:</strong> MLX is designed around Apple&apos;s shared
              CPU/GPU memory architecture. It can fit larger models into the same RAM.
            </li>
            <li>
              <strong>Great UI:</strong> Download, configure, and chat with models without
              touching the terminal.
            </li>
          </ul>

          <AnchorHeading id="lm-studio-limitations" level="h3">Limitations with CoDRAG</AnchorHeading>
          <p>
            LM Studio does <strong>not</strong> expose an API for loading or unloading models.
            This means CoDRAG <strong>cannot</strong> perform dynamic model loading with LM Studio.
            Specifically:
          </p>
          <ul>
            <li>
              <strong>No automatic model switching.</strong> If your pipeline uses different models
              for different tasks, you must manually load the correct model in LM Studio&apos;s UI.
              CoDRAG will warn you if the loaded model doesn&apos;t match what&apos;s configured.
            </li>
            <li>
              <strong>Context window is manual.</strong> LM Studio defaults to 4,096 tokens.
              Deep reasoning tasks routinely send 8K–32K token prompts. You must increase the
              context window in LM Studio&apos;s UI (Load → Context Length) before running
              the trace pipeline.
            </li>
            <li>
              <strong>&ldquo;Always available&rdquo; is implicit.</strong> Whatever model you load in
              LM Studio stays loaded. The checkbox in CoDRAG has no effect on LM Studio.
            </li>
          </ul>

          <div className="my-6 rounded-lg border border-info/30 bg-info/5 p-4">
            <p className="text-sm">
              <span className="font-semibold text-info">Recommendation:</span>{' '}
              LM Studio is ideal for <strong>Mac users with 32GB+ RAM</strong> who want to keep
              a single powerful model loaded at all times and leverage MLX performance.
              Use it as your Fast model endpoint, and optionally pair it with an Ollama
              endpoint (or cloud API) for the Thinking/Code slots that benefit from
              dynamic model loading.
            </p>
          </div>

          {/* ── MLX vs GGUF ── */}
          <AnchorHeading id="mlx-vs-gguf" level="h2">MLX vs GGUF (llama.cpp)</AnchorHeading>
          <p>
            The local AI landscape on Mac currently has two main inference backends:
          </p>

          <div className="my-6 overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 pr-4 font-semibold"></th>
                  <th className="text-left py-2 pr-4 font-semibold">MLX (LM Studio)</th>
                  <th className="text-left py-2 font-semibold">GGUF / llama.cpp (Ollama)</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text-muted">Platform</td>
                  <td className="py-2 pr-4">Apple Silicon only</td>
                  <td className="py-2">Cross-platform (Mac, Linux, Windows)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text-muted">Memory usage</td>
                  <td className="py-2 pr-4">Lower (unified memory optimized)</td>
                  <td className="py-2">Higher (Metal backend, less optimized for shared memory)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text-muted">Inference speed</td>
                  <td className="py-2 pr-4">Faster on Apple Silicon</td>
                  <td className="py-2">Good, but slightly slower on Mac</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text-muted">Dynamic loading</td>
                  <td className="py-2 pr-4 text-warning">❌ No API</td>
                  <td className="py-2 text-success">✅ Full API</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text-muted">Model format</td>
                  <td className="py-2 pr-4">MLX (safetensors)</td>
                  <td className="py-2">GGUF (quantized)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text-muted">Server mode</td>
                  <td className="py-2 pr-4">GUI app with local server</td>
                  <td className="py-2">Daemon with CLI + REST API</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p>
            Ollama uses llama.cpp under the hood with a Metal backend on Mac. It does <strong>not</strong> use
            MLX and there are no current plans for Ollama to ship MLX support (though it&apos;s been
            discussed in the community). Similarly, llama.cpp itself does not use MLX — it has its
            own Metal GPU acceleration layer.
          </p>
          <p>
            If you want MLX performance, LM Studio is currently the only practical option with
            a CoDRAG-compatible OpenAI API endpoint.
          </p>

          {/* ── Recommended Setups ── */}
          <AnchorHeading id="recommended-setups" level="h2">Recommended Setups</AnchorHeading>

          <AnchorHeading id="setup-mac-32gb" level="h3">Mac with 32GB+ RAM</AnchorHeading>
          <div className="my-4 rounded-lg border border-border bg-surface p-4 space-y-2 text-sm">
            <div><span className="font-semibold text-primary">Fast Model:</span> LM Studio (MLX) — <code>qwen3:4b</code> — Always Available ✅</div>
            <div><span className="font-semibold text-primary">Thinking Model:</span> Ollama — <code>qwen3:8b</code> — Dynamic loading</div>
            <div><span className="font-semibold text-primary">Code Model:</span> Ollama — <code>qwen3-coder:30b</code> — Dynamic loading</div>
            <p className="text-text-muted pt-2">
              The Fast model stays hot in LM Studio via MLX (low memory, fast inference).
              Ollama handles the heavier models with dynamic loading — swapping them in
              and out of VRAM as the pipeline progresses.
            </p>
          </div>

          <AnchorHeading id="setup-mac-16gb" level="h3">Mac with 16GB RAM</AnchorHeading>
          <div className="my-4 rounded-lg border border-border bg-surface p-4 space-y-2 text-sm">
            <div><span className="font-semibold text-primary">All models:</span> Ollama — Dynamic loading</div>
            <div><span className="font-semibold text-primary">Fast:</span> <code>qwen3:4b</code> (2.5GB) — optionally Always Available</div>
            <div><span className="font-semibold text-primary">Thinking:</span> <code>qwen3:8b</code> (5.2GB)</div>
            <p className="text-text-muted pt-2">
              With 16GB, dynamic model loading is essential. Only one model fits comfortably
              at a time. Ollama&apos;s automated load/unload cycle keeps the pipeline moving
              without manual intervention.
            </p>
          </div>

          <AnchorHeading id="setup-hybrid" level="h3">Hybrid: Local + Cloud</AnchorHeading>
          <div className="my-4 rounded-lg border border-border bg-surface p-4 space-y-2 text-sm">
            <div><span className="font-semibold text-primary">Fast tasks:</span> Ollama or LM Studio — local model</div>
            <div><span className="font-semibold text-primary">Reasoning tasks:</span> Cloud API (Claude, GPT-4o) — no VRAM needed</div>
            <p className="text-text-muted pt-2">
              Offload the heavy reasoning tasks (group reasoning, atlas generation, deepening)
              to a cloud API. This eliminates VRAM pressure entirely for those tasks and
              gets frontier-quality results. Local models handle the high-volume fast sync tasks.
            </p>
          </div>

          <AnchorHeading id="setup-linux" level="h3">Linux / Windows with NVIDIA GPU</AnchorHeading>
          <div className="my-4 rounded-lg border border-border bg-surface p-4 space-y-2 text-sm">
            <div><span className="font-semibold text-primary">All models:</span> Ollama — Dynamic loading with CUDA</div>
            <p className="text-text-muted pt-2">
              Ollama with CUDA acceleration is the recommended setup. Dynamic model loading
              works identically to Mac. MLX is not available on Linux/Windows — it&apos;s
              Apple Silicon only.
            </p>
          </div>

          {/* ── Pipeline Safety ── */}
          <AnchorHeading id="pipeline-safety" level="h2">Pipeline Safety</AnchorHeading>
          <p>
            Changing your model configuration while a pipeline is running could cause
            the next stage to resolve to a different (or missing) model. CoDRAG handles this
            with a <strong>pipeline-safe mode switch</strong>:
          </p>
          <ol className="space-y-2">
            <li>When you save a configuration change, CoDRAG <strong>pauses</strong> any active pipeline stages</li>
            <li>The new configuration is written atomically</li>
            <li>CoDRAG verifies the next stage&apos;s model is available under the new config</li>
            <li>The pipeline <strong>resumes</strong> from where it left off</li>
          </ol>
          <p>
            This means you can safely switch between Structured and Assigned mode, change
            endpoints, or swap models — even mid-pipeline — without data loss or crashes.
          </p>

        </div>
      </div>
    </main>
  );
}
