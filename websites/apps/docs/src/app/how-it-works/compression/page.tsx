"use client";

import { ConceptPageShell } from '../../../components/ConceptPageShell';
import { DemoContextOutput } from '../../../components/demos';

const SECTIONS = [
  { id: 'overview',              label: 'How It Works' },
  { id: 'structural-compression', label: 'Levels of Detail' },
  { id: 'tier-adaptive',         label: 'Tier-Adaptive' },
  { id: 'compression-flow',      label: 'Compression Flow' },
  { id: 'usage',                 label: 'Usage' },
  { id: 'response-metadata',     label: 'Response Metadata' },
  { id: 'preview',               label: 'Output Preview' },
  { id: 'languages',             label: 'Supported Languages' },
  { id: 'fallback',              label: 'Fallback Behaviour' },
  { id: 'language-compression',  label: 'Roadmap' },
];

export default function Page() {
  return (
    <ConceptPageShell
      subtitle="How It Works"
      title="Smart Context Compression"
      description="Structural LOD compression delivers code context at variable fidelity. Top results stay at full source; peripheral files show just names and imports — achieving 3–20× compression with zero dependencies, adapting automatically to your AI tool's context window tier."
      sections={SECTIONS}
    >
        <section id="overview">
          <h2 className="text-2xl font-semibold">How it works</h2>
          <p className="mt-3 text-text-muted leading-relaxed">
            LOD (Levels of Detail) uses SourcePrep&apos;s trace graph to understand your code&apos;s
            structure &mdash; functions, classes, imports, docstrings &mdash; and extracts at
            variable fidelity based on relevance score. No model inference, no GPU, no dependencies.
          </p>
          <ul className="mt-4 space-y-2 text-sm text-text-muted list-disc pl-5">
            <li><span className="font-semibold text-text">Score-aware</span> &mdash; high-relevance code stays full, low-relevance compresses more</li>
            <li><span className="font-semibold text-text">Tier-adaptive</span> &mdash; Claude/Gemini (50K budget) gets more full-source files; local models (20K) get tighter compression</li>
            <li><span className="font-semibold text-text">Code-aware</span> &mdash; understands functions, classes, imports (not just token probabilities)</li>
            <li><span className="font-semibold text-text">Instant</span> &mdash; &lt;10ms per file (no model inference)</li>
            <li><span className="font-semibold text-text">No extra license</span> &mdash; LOD compression is part of the core engine on every plan, including the $0 self-hosted build</li>
          </ul>
        </section>

        <hr className="my-10 border-border" />

        {/* LOD Levels */}
        <section id="structural-compression">
          <h2 className="text-2xl font-semibold">Levels of Detail</h2>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-text">
                  <th className="py-2 pr-4 font-medium text-text">LOD</th>
                  <th className="py-2 pr-4 font-medium text-text">What&apos;s kept</th>
                  <th className="py-2 pr-4 font-medium text-text">Measured ratio</th>
                  <th className="py-2 font-medium text-text">When used</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono font-bold">0</td>
                  <td className="py-2 pr-4">Full source</td>
                  <td className="py-2 pr-4">1:1</td>
                  <td className="py-2">Top results (score &ge; threshold)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono font-bold">1</td>
                  <td className="py-2 pr-4">Source minus comments</td>
                  <td className="py-2 pr-4">1.1&ndash;1.3&times;</td>
                  <td className="py-2">Tier 1 neighbours</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono font-bold">2</td>
                  <td className="py-2 pr-4">Signatures + docstrings + <code>...</code></td>
                  <td className="py-2 pr-4">1.3&ndash;2.6&times;</td>
                  <td className="py-2">Mid-relevance results, Tier 2 neighbours</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono font-bold">3</td>
                  <td className="py-2 pr-4">Class skeletons only</td>
                  <td className="py-2 pr-4">~2.6&times;</td>
                  <td className="py-2">Class-heavy files</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono font-bold">4</td>
                  <td className="py-2 pr-4">Imports + symbol names</td>
                  <td className="py-2 pr-4">8&ndash;14&times;</td>
                  <td className="py-2">Low-relevance or trace-expanded neighbours</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-mono font-bold">5</td>
                  <td className="py-2 pr-4">File path + summary + exports</td>
                  <td className="py-2 pr-4">50&ndash;140&times;</td>
                  <td className="py-2">Peripheral files (score &lt; 0.20)</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-sm text-text-muted">
            Ratios measured on real SourcePrep source files (7K&ndash;18K chars). Files with more code inside
            functions achieve higher ratios; files with heavy module-level constants compress less at LOD 2.
          </p>
        </section>

        {/* Tier-adaptive */}
        <section id="tier-adaptive">
          <h2 className="text-2xl font-semibold">Tier-Adaptive Compression</h2>
          <p className="mt-3 text-text-muted leading-relaxed">
            SourcePrep detects your AI tool from the MCP handshake and adapts compression to match
            the context window. Larger windows get more full-source files; smaller windows get
            tighter compression so the same structural information fits.
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-text">
                  <th className="py-2 pr-4 font-medium text-text">Tier</th>
                  <th className="py-2 pr-4 font-medium text-text">Clients</th>
                  <th className="py-2 pr-4 font-medium text-text">Budget</th>
                  <th className="py-2 pr-4 font-medium text-text">Hub files</th>
                  <th className="py-2 font-medium text-text">Neighbour LOD</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text">Tier 1</td>
                  <td className="py-2 pr-4">Claude Code, Gemini CLI</td>
                  <td className="py-2 pr-4">50K chars</td>
                  <td className="py-2 pr-4">10 at full source</td>
                  <td className="py-2">LOD 1 (source minus comments)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-semibold text-text">Tier 2</td>
                  <td className="py-2 pr-4">Cursor, Windsurf, Copilot</td>
                  <td className="py-2 pr-4">24&ndash;30K chars</td>
                  <td className="py-2 pr-4">6 at full source</td>
                  <td className="py-2">LOD 2.5 (sigs + docstrings)</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-semibold text-text">Tier 2.5</td>
                  <td className="py-2 pr-4">Cline, Roo, Continue</td>
                  <td className="py-2 pr-4">20K chars</td>
                  <td className="py-2 pr-4">4 at LOD 2.5</td>
                  <td className="py-2">LOD 4 (names + imports)</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-sm text-text-muted">
            Tier detection is automatic &mdash; no configuration needed. The first <code>prep</code> call
            in each session also gets a 50% orientation boost for richer initial context.
          </p>
        </section>

        {/* Flow diagram */}
        <section id="compression-flow">
          <h2 className="text-2xl font-semibold">Compression flow</h2>
          <div className="mt-4 rounded-lg bg-surface border border-border p-6 font-mono text-sm leading-relaxed">
            <div className="text-text-muted">Query arrives</div>
            <div className="text-text-muted">&nbsp; &darr;</div>
            <div className="text-text-muted">Semantic search &rarr; scored chunks</div>
            <div className="text-text-muted">&nbsp; &darr;</div>
            <div className="text-text-muted">Detect client tier (1 / 2 / 2.5)</div>
            <div className="text-text-muted">&nbsp; &darr;</div>
            <div className="text-text-muted">assign_lod(score, tier) per file:</div>
            <div className="text-text-muted">&nbsp; Tier 1: &ge;0.40 &rarr; LOD 0, &ge;0.25 &rarr; LOD 2, &ge;0.15 &rarr; LOD 4, &lt;0.15 &rarr; LOD 5</div>
            <div className="text-text-muted">&nbsp; Tier 2: &ge;0.50 &rarr; LOD 0, &ge;0.35 &rarr; LOD 2, &ge;0.20 &rarr; LOD 4, &lt;0.20 &rarr; LOD 5</div>
            <div className="text-text-muted">&nbsp; Tier 2.5: &ge;0.60 &rarr; LOD 0, &ge;0.40 &rarr; LOD 2, &ge;0.25 &rarr; LOD 4, &lt;0.25 &rarr; LOD 5</div>
            <div className="text-text-muted">&nbsp; &darr;</div>
            <div className="text-text-muted">LODExtractor.extract(file, lod, trace_nodes)</div>
            <div className="text-text-muted">&nbsp; &darr;</div>
            <div className="text-text-muted">Compressed context assembled within budget</div>
          </div>
          <p className="mt-3 text-sm text-text-muted">
            The extractor uses SourcePrep&apos;s pre-computed trace graph (symbol spans, class hierarchy,
            import edges) to know exactly where functions start and end &mdash; no re-parsing needed
            at query time.
          </p>
        </section>

        {/* Usage */}
        <section id="usage">
          <h2 className="text-2xl font-semibold">Usage</h2>

          <h3 className="mt-6 text-lg font-medium text-text">Via MCP (automatic)</h3>
          <p className="mt-2 text-sm text-text-muted">
            LOD compression is <span className="font-semibold text-text">always active</span> for MCP tool calls.
            When you call <code>prep_search</code>, results are automatically LOD-compressed based on your
            client tier. No configuration needed.
          </p>

          <h3 className="mt-6 text-lg font-medium text-text">Via Dashboard</h3>
          <p className="mt-2 text-sm text-text-muted">
            LOD compression is <span className="font-semibold text-text">always applied</span>. In the
            <span className="font-semibold text-text"> Context Assembler</span> panel, click &ldquo;Assemble&rdquo; &mdash; each source citation
            automatically shows an <code>LOD&#123;n&#125;</code> badge and compression ratio.
          </p>

          <h3 className="mt-6 text-lg font-medium text-text">Via API</h3>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div>curl -X POST http://localhost:8400/projects/my-project/context \</div>
            <div>&nbsp; -H &quot;Content-Type: application/json&quot; \</div>
            <div>&nbsp; -d &apos;{'{'}</div>
            <div>&nbsp;&nbsp;&nbsp; &quot;query&quot;: &quot;How does authentication work?&quot;,</div>
            <div>&nbsp;&nbsp;&nbsp; &quot;k&quot;: 10,</div>
            <div>&nbsp;&nbsp;&nbsp; &quot;max_chars&quot;: 12000,</div>
            <div>&nbsp;&nbsp;&nbsp; &quot;structured&quot;: true,</div>
            <div>&nbsp; {'}'}&apos;</div>
          </div>
        </section>

        {/* Response metadata */}
        <section id="response-metadata">
          <h2 className="text-2xl font-semibold">Response metadata</h2>
          <p className="mt-3 text-text-muted leading-relaxed">
            When LOD compression is active, the response includes a <code>compression</code> object
            and per-chunk <code>lod</code> / <code>compression_ratio</code> fields:
          </p>
          <div className="mt-3 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <pre className="text-text-muted">{`{
  "context": "[src/auth.py | lod=2]\\ndef login(...):\\n    ...",
  "chunks": [
    {
      "source_path": "src/auth.py",
      "score": 0.47,
      "lod": 2,
      "compression_ratio": 2.6
    }
  ],
  "compression": {
    "enabled": true,
    "mode": "lod",
    "input_chars": 8200,
    "output_chars": 1840,
    "lod_distribution": { "0": 1, "2": 3, "4": 2 }
  }
}`}</pre>
          </div>
        </section>

        {/* Live preview of compressed output */}
        <section id="preview">
          <h2 className="text-2xl font-semibold">What the assembled output looks like</h2>
          <p className="mt-3 text-text-muted leading-relaxed">
            The Context Output panel in the dashboard renders the same payload your AI agent
            receives — including the per-chunk <code>LOD</code> badges and compression-ratio
            annotations.
          </p>
          <div className="not-prose mt-4">
            <DemoContextOutput />
            <p className="text-xs text-text-subtle italic -mt-4">
              Live preview: the Context Output panel showing source citations and LOD-compressed chunks.
            </p>
          </div>
        </section>

        {/* Languages */}
        <section id="languages">
          <h2 className="text-2xl font-semibold">Supported languages</h2>
          <p className="mt-3 text-text-muted leading-relaxed">
            LOD extraction supports signature detection and import recognition for:
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {['Python', 'TypeScript', 'JavaScript', 'Rust', 'Go', 'Java', 'Kotlin', 'Swift', 'C#', 'C++', 'C', 'PHP', 'Ruby', 'Dart', 'Scala'].map((lang) => (
              <span key={lang} className="px-2 py-1 text-xs rounded bg-surface border border-border font-mono">{lang}</span>
            ))}
          </div>
          <p className="mt-3 text-sm text-text-muted">
            For unsupported languages, files fall back to LOD 0 (full source) gracefully.
          </p>
        </section>

        {/* Fallback */}
        <section id="fallback">
          <h2 className="text-2xl font-semibold">Fallback behaviour</h2>
          <p className="mt-3 text-text-muted leading-relaxed">
            Compression is <span className="font-semibold text-text">best-effort</span>. If the trace graph doesn&apos;t have symbol
            data for a file (e.g., the file was added after the last build), SourcePrep falls back to
            LOD 0 and returns the full source. The <code>fallback</code> field in the chunk metadata
            will be <code>true</code>.
          </p>
          <div className="mt-4 rounded-lg border border-blue-500/20 bg-blue-500/5 p-4 text-sm text-text-muted">
            <span className="font-semibold text-blue-600">Tip:</span> Keep your index up to date (enable the
            file watcher or rebuild regularly) for the best compression results.
          </div>
        </section>

        <hr className="my-10 border-border" />

        {/* Roadmap: Language compression */}
        <section id="language-compression">
          <h2 className="text-2xl font-semibold">Roadmap: Language Compression for Documentation</h2>
          <p className="mt-3 text-text-muted leading-relaxed">
            We evaluated language-aware compression for markdown and documentation files
            (an LLMLingua-2-based approach) and removed it — quality testing showed unacceptable
            term retention on technical documentation. Structural LOD compression for code remains
            the shipped engine; documentation compression may be revisited later.
          </p>
        </section>
    </ConceptPageShell>
  );
}
