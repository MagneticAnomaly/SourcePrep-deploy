import { AnchorHeading } from '../../../components/AnchorHeading';
import { ConceptPageShell } from '../../../components/ConceptPageShell';
import { DemoAdvancedLLMSettings } from '../../../components/demos';

const SECTIONS = [
  { id: 'should-you',         label: 'Should You Run Local?' },
  { id: 'recommended-models', label: 'Recommended Models' },
  { id: 'how-it-works',       label: 'How Dynamic Loading Works' },
  { id: 'provider-support',   label: 'Provider Support' },
  { id: 'always-available',   label: 'Persistent Models' },
  { id: 'recommended-setups', label: 'Recommended Setups' },
  { id: 'mlx-vs-gguf',        label: 'MLX vs GGUF' },
  { id: 'pipeline-safety',    label: 'Pipeline Safety' },
];

export default function Page() {
  return (
    <ConceptPageShell
      subtitle="How It Works"
      title="Local LLM Setup"
      description="Running SourcePrep's pipeline against models on your own hardware — when it's worth it, what to run, and how SourcePrep handles model swapping for you."
      sections={SECTIONS}
    >
        <div className="prose max-w-none">

          {/* ── Should you even run local? ── */}
          <AnchorHeading id="should-you" level="h2">Should you run local LLMs at all?</AnchorHeading>
          <p>
            For most users, no. While SourcePrep is designed local-first architecturally, for most
            users a cloud service like Ollama&apos;s cloud will provide faster and better intelligence
            and — importantly — the concurrency needed for swarm aggregation.
          </p>
          <p>Running local makes sense when:</p>
          <ul>
            <li>You have a hard requirement that no codebase data leaves your machine.</li>
            <li>You&apos;re on a low-/no-connectivity setup and need to keep working.</li>
            <li>You already own a Mac with 32GB+ unified memory or a 24GB+ NVIDIA GPU, and want to use it.</li>
          </ul>

          <div className="my-6 rounded-lg border border-warning/30 bg-warning/5 p-4">
            <p className="text-sm">
              <span className="font-semibold text-warning">Hardware floor:</span>{' '}
              Don&apos;t try to run SourcePrep&apos;s pipeline against local LLMs on a 16GB Mac
              (or anything similar). The pipeline drives 14B+ parameter models with long context
              windows; 16GB just doesn&apos;t have the headroom. Use cloud LLMs at that scale —
              they&apos;ll be faster, more reliable, and won&apos;t lock up your machine.
            </p>
          </div>

          {/* ── Recommended models ── */}
          <AnchorHeading id="recommended-models" level="h2">Recommended models</AnchorHeading>
          <p>
            SourcePrep&apos;s pipeline runs reasoning and code-generation tasks that need real
            capability. Don&apos;t bother with sub-14B models — they don&apos;t hold up under
            multi-hop reasoning and produce noisy enrichments. The flagship recommendation is
            <strong> Qwen 3.5 35B</strong> (the MoE 35B-active-3B variant); we benchmark against it
            in development and it&apos;s what we tune the prompt budgets for.
          </p>

          <div className="my-6 overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-border text-left text-text">
                  <th className="py-2 pr-4 font-medium">Model</th>
                  <th className="py-2 pr-4 font-medium">VRAM (Q4)</th>
                  <th className="py-2 font-medium">When to pick it</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-primary whitespace-nowrap">qwen3.5:35b-a3b</td>
                  <td className="py-2 pr-4">~24 GB</td>
                  <td className="py-2"><strong>Recommended.</strong> MoE: 35B params, 3B active. Strong reasoning, fits on 32GB Mac (tight) or 48GB+ (comfortable).</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono whitespace-nowrap">qwen3.5:35b-a3b-q8_0</td>
                  <td className="py-2 pr-4">~39 GB</td>
                  <td className="py-2">Higher-precision MoE. Needs 48GB+ unified memory or a real GPU.</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-mono whitespace-nowrap">qwen3.5:122b-a10b</td>
                  <td className="py-2 pr-4">~81 GB</td>
                  <td className="py-2">Flagship MoE. Only on workstations with 96GB+ unified memory or a multi-GPU rig.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="text-sm text-text-muted">
            VRAM figures are SourcePrep&apos;s measured ceilings (see <code>src/prep/core/context_config.py</code>)
            including the 256K-token context window we provision per slot. Smaller context windows save
            a few GB but cap how much codebase the agent can reason over.
          </p>

          {/* ── How dynamic loading works ── */}
          <AnchorHeading id="how-it-works" level="h2">How dynamic loading works</AnchorHeading>
          <p>
            SourcePrep&apos;s pipeline runs several different LLM tasks per project — fast file
            cataloguing, deeper reasoning passes, code-aware refactor planning, etc. On a single
            machine you can&apos;t keep every model resident, so SourcePrep loads, unloads, and
            re-warms models between stages on your behalf.
          </p>

          <ol className="space-y-2">
            <li><strong>Stage starts</strong> — the orchestrator picks the model for the upcoming task.</li>
            <li><strong>Room check</strong> — if a different model is currently loaded and the next task uses a different one, the loaded model is unloaded first.</li>
            <li><strong>Preload</strong> — the new model is loaded into memory, with the right context length, before the stage executes.</li>
            <li><strong>Ready</strong> — the stage runs.</li>
            <li><strong>Next stage</strong> — if the same model is needed again, it stays put. Otherwise the cycle repeats.</li>
          </ol>

          <p>
            None of this requires manual intervention — you configure your endpoints and models
            once and SourcePrep handles the choreography per run.
          </p>

          <div className="not-prose">
            <DemoAdvancedLLMSettings />
            <p className="text-xs text-text-subtle italic -mt-4">
              The Advanced LLM Settings panel — cloud token-safety limits and the max thinking budget live here. Per-slot &quot;Always Available&quot; toggles (which keep a model resident in VRAM) live on each model slot in the AI Gateway, not here.
            </p>
          </div>

          {/* ── Provider support ── */}
          <AnchorHeading id="provider-support" level="h2">Provider support</AnchorHeading>
          <p>
            Both Ollama and LM Studio are fully supported peers — SourcePrep&apos;s pipeline calls
            the same load/unload/ensure-ready logic against either backend.
          </p>

          <div className="my-6 overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-border text-left text-text">
                  <th className="py-2 pr-4 font-medium">Provider</th>
                  <th className="py-2 pr-4 font-medium">Dynamic Loading</th>
                  <th className="py-2 pr-4 font-medium">MLX Backend</th>
                  <th className="py-2 font-medium">Notes</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-primary">Ollama</td>
                  <td className="py-2 pr-4 text-success font-semibold">✅ Full</td>
                  <td className="py-2 pr-4 text-success font-semibold">✅ Supported</td>
                  <td className="py-2">Cross-platform. Ollama&apos;s recent MLX support brings Apple Silicon performance close to LM Studio on equivalent models.</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono text-primary">LM Studio</td>
                  <td className="py-2 pr-4 text-success font-semibold">✅ Full</td>
                  <td className="py-2 pr-4 text-success font-semibold">✅ Built-in</td>
                  <td className="py-2">Apple Silicon only. SourcePrep auto-sets context length on load; no manual UI fiddling required.</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-mono text-primary">Cloud APIs</td>
                  <td className="py-2 pr-4 text-text-muted">N/A (always ready)</td>
                  <td className="py-2 pr-4 text-text-muted">N/A</td>
                  <td className="py-2">No VRAM management needed. Recommended for most users.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="text-sm text-text-muted">
            On Apple Silicon, both backends now run MLX-quantized models. Pick whichever you&apos;re
            already comfortable with; the SourcePrep integration is the same either way.
          </p>

          {/* ── Always available ── */}
          <AnchorHeading id="always-available" level="h2">Persistent models</AnchorHeading>
          <p>
            One model can be marked <strong>Always Available</strong> in the AI Models settings —
            typically the smaller of your two slots, kept resident to skip the 5–15 second cold
            start when stages cycle.
          </p>
          <p>If VRAM pressure forces an eviction, SourcePrep will:</p>
          <ul>
            <li>Temporarily unload the persistent model to make room for a larger task.</li>
            <li>Automatically reload it once the heavy task finishes.</li>
            <li>Show an eviction warning in the AI Gateway so you know it happened.</li>
          </ul>

          {/* ── Recommended setups ── */}
          <AnchorHeading id="recommended-setups" level="h2">Recommended setups</AnchorHeading>

          <AnchorHeading id="setup-mac-48gb" level="h3">Mac with 48–64GB unified memory</AnchorHeading>
          <div className="my-4 rounded-lg border border-border bg-surface p-4 space-y-2 text-sm">
            <div><span className="font-semibold text-primary">All slots:</span> <code>qwen3.5:35b-a3b</code> via Ollama or LM Studio</div>
            <p className="text-text-muted pt-2">
              The MoE 35B fits with comfortable headroom. Pick either backend — both now use MLX
              on Apple Silicon. With 48GB+ you can leave the model resident as Always Available
              and skip cold starts entirely.
            </p>
          </div>

          <AnchorHeading id="setup-mac-32gb" level="h3">Mac with 32GB unified memory</AnchorHeading>
          <div className="my-4 rounded-lg border border-border bg-surface p-4 space-y-2 text-sm">
            <div><span className="font-semibold text-primary">Primary model:</span> <code>qwen3.5:35b-a3b</code></div>
            <p className="text-text-muted pt-2">
              Tight but workable — the 35B-a3b MoE consumes ~24 GB at the provisioned context
              window, leaving roughly 8 GB for the OS and your other apps. Run a single model
              and let SourcePrep cycle it across stages; don&apos;t try to keep a second model
              resident. If 32 GB feels constrained in practice, drop down to the hybrid setup
              and route reasoning to a cloud endpoint.
            </p>
          </div>

          <AnchorHeading id="setup-workstation" level="h3">Workstation with 96GB+ memory or a 48GB+ NVIDIA GPU</AnchorHeading>
          <div className="my-4 rounded-lg border border-border bg-surface p-4 space-y-2 text-sm">
            <div><span className="font-semibold text-primary">Primary model:</span> <code>qwen3.5:35b-a3b-q8_0</code> or <code>qwen3.5:122b-a10b</code></div>
            <p className="text-text-muted pt-2">
              At this scale you can run the higher-precision Qwen variants or the flagship 122B
              MoE. Dynamic loading is still on, but mostly to swap between specialised models
              (reasoning vs code) rather than because you&apos;re out of memory.
            </p>
          </div>

          <AnchorHeading id="setup-hybrid" level="h3">Hybrid: local fast + cloud heavy</AnchorHeading>
          <div className="my-4 rounded-lg border border-border bg-surface p-4 space-y-2 text-sm">
            <div><span className="font-semibold text-primary">Fast tasks:</span> local <code>qwen3.5:35b-a3b</code></div>
            <div><span className="font-semibold text-primary">Reasoning + code tasks:</span> cloud (Claude / GPT / Ollama Cloud)</div>
            <p className="text-text-muted pt-2">
              Often the most pragmatic setup: keep a single local model resident for high-volume
              fast-sync work, and route the heavy reasoning / refactor stages to a cloud API.
              No VRAM pressure, frontier-quality results where they matter, and your codebase
              data still stays local for the fast-sync passes.
            </p>
          </div>

          {/* ── MLX backends ── */}
          <AnchorHeading id="mlx-vs-gguf" level="h2">MLX vs GGUF (Apple Silicon)</AnchorHeading>
          <p>
            On Apple Silicon both backends now offer MLX runtimes — Apple&apos;s ML framework
            optimised for unified memory. The performance gap that historically favored LM Studio
            has largely closed now that Ollama ships MLX support.
          </p>
          <p>
            Practically: pick whichever you already have installed. If neither, Ollama&apos;s CLI +
            REST API is easier to script and works the same on Mac, Linux, and Windows; LM Studio
            is the better choice if you prefer a GUI for browsing and downloading models. Both
            give SourcePrep the same dynamic-loading behaviour.
          </p>

          {/* ── Pipeline safety ── */}
          <AnchorHeading id="pipeline-safety" level="h2">Pipeline safety</AnchorHeading>
          <p>
            Changing your model configuration while a pipeline is running could cause the next
            stage to resolve to a different (or missing) model. SourcePrep handles this with a
            <strong> pipeline-safe mode switch</strong>:
          </p>
          <ol className="space-y-2">
            <li>When you save a configuration change, SourcePrep <strong>pauses</strong> any active pipeline stages.</li>
            <li>The new configuration is written atomically.</li>
            <li>SourcePrep verifies the next stage&apos;s model is available under the new config.</li>
            <li>The pipeline <strong>resumes</strong> from where it left off.</li>
          </ol>
          <p>
            This means you can safely switch endpoints, swap models, or move between Structured
            and Assigned mode — even mid-pipeline — without data loss or crashes.
          </p>

        </div>
    </ConceptPageShell>
  );
}
