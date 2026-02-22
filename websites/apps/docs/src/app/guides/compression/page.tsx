export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/guides" className="text-sm text-text-muted">
          &larr; Guides
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Smart Context Compression</h1>
        <p className="mt-4 text-lg text-text-muted">
          CoDRAG uses two compression engines, each optimized for what it handles. <strong>Code files</strong> are
          structurally compressed &mdash; keeping full source for top results, signatures for mid-relevance, and
          names for peripheral files (3&ndash;20&times;). <strong>Documentation and markdown</strong> are compressed
          with a lightweight language model that removes filler while preserving meaning (~1.6&times;, 89% concept
          retention). Both run on CPU with no GPU required.
        </p>

        {/* Overview */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">How it works</h2>
          <p className="mt-3 text-text-muted leading-relaxed">
            When you set <code>compression: &quot;auto&quot;</code>, CoDRAG automatically picks the right
            engine for each chunk:
          </p>
          <ul className="mt-4 space-y-2 text-sm text-text-muted list-disc pl-5">
            <li><strong>Code files</strong> (.py, .ts, .rs, etc.) &rarr; <strong>Structural compression (LOD)</strong> &mdash; uses your code&apos;s trace graph to extract at variable fidelity</li>
            <li><strong>Documentation</strong> (.md, .txt, .rst) &rarr; <strong>Language compression</strong> &mdash; a lightweight BERT model removes filler tokens while preserving key facts</li>
          </ul>
          <p className="mt-3 text-sm text-text-muted">
            You can also force a specific engine: <code>compression: &quot;lod&quot;</code> for structural only,
            or <code>compression: &quot;lingua&quot;</code> for language only.
          </p>
        </section>

        <hr className="my-10 border-border" />

        {/* LOD section */}
        <section>
          <h2 className="text-2xl font-semibold">Structural Compression (LOD) &mdash; for Code</h2>
          <p className="mt-3 text-text-muted leading-relaxed">
            LOD (Levels of Detail) is a structural code compression system inspired by the
            Stingy&nbsp;Context / TREEFRAG research (arXiv:2601.19929). Instead of removing tokens
            probabilistically, it uses CoDRAG&apos;s trace graph to understand your code&apos;s
            structure &mdash; functions, classes, imports, docstrings &mdash; and extracts at
            variable fidelity based on relevance.
          </p>
          <ul className="mt-4 space-y-2 text-sm text-text-muted list-disc pl-5">
            <li>Zero dependencies &mdash; built into the CoDRAG engine</li>
            <li>Score-aware &mdash; high-relevance code stays full, low-relevance shows names only</li>
            <li>Code-aware &mdash; understands functions, classes, imports (not just token probabilities)</li>
            <li>Instant &mdash; &lt;10ms per file (no model inference)</li>
            <li>Available on all tiers including Free</li>
          </ul>
        </section>

        {/* LOD Levels */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">Levels of Detail</h2>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="py-2 pr-4 font-medium">LOD</th>
                  <th className="py-2 pr-4 font-medium">What&apos;s kept</th>
                  <th className="py-2 pr-4 font-medium">Typical ratio</th>
                  <th className="py-2 font-medium">When used</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono font-bold">0</td>
                  <td className="py-2 pr-4">Full source</td>
                  <td className="py-2 pr-4">1:1</td>
                  <td className="py-2">Score &ge; 0.50 (top results)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono font-bold">1</td>
                  <td className="py-2 pr-4">Source minus comments</td>
                  <td className="py-2 pr-4">~1.2&times;</td>
                  <td className="py-2">Slightly compressed</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono font-bold">2</td>
                  <td className="py-2 pr-4">Signatures + docstrings + <code>...</code></td>
                  <td className="py-2 pr-4">3&ndash;4&times;</td>
                  <td className="py-2">Score 0.35&ndash;0.49 (medium relevance)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono font-bold">3</td>
                  <td className="py-2 pr-4">Class skeletons only</td>
                  <td className="py-2 pr-4">~5&times;</td>
                  <td className="py-2">Class-heavy files</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-mono font-bold">4</td>
                  <td className="py-2 pr-4">Imports + symbol names</td>
                  <td className="py-2 pr-4">8&ndash;10&times;</td>
                  <td className="py-2">Score 0.20&ndash;0.34 or trace-expanded neighbours</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-mono font-bold">5</td>
                  <td className="py-2 pr-4">File path + summary + exports</td>
                  <td className="py-2 pr-4">15&ndash;20&times;</td>
                  <td className="py-2">Score &lt; 0.20 (peripheral)</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-sm text-text-muted">
            LOD is assigned automatically based on each file&apos;s search relevance score.
            The most relevant files stay at full fidelity; less relevant files are progressively
            compressed &mdash; freeing token budget for more files in the same context window.
          </p>
        </section>

        {/* How it works */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">How it works</h2>
          <div className="mt-4 rounded-lg bg-surface border border-border p-6 font-mono text-sm leading-relaxed">
            <div className="text-text-muted">Query arrives</div>
            <div className="text-text-muted">&nbsp; &darr;</div>
            <div className="text-text-muted">Semantic search &rarr; scored chunks</div>
            <div className="text-text-muted">&nbsp; &darr;</div>
            <div className="text-text-muted">assign_lod(score) per file:</div>
            <div className="text-text-muted">&nbsp; &ge;0.50 &rarr; LOD 0 (full source)</div>
            <div className="text-text-muted">&nbsp; 0.35  &rarr; LOD 2 (sigs + docs)</div>
            <div className="text-text-muted">&nbsp; 0.20  &rarr; LOD 4 (names only)</div>
            <div className="text-text-muted">&nbsp; &lt;0.20 &rarr; LOD 5 (summary)</div>
            <div className="text-text-muted">&nbsp; &darr;</div>
            <div className="text-text-muted">LODExtractor.extract(file, lod, trace_nodes)</div>
            <div className="text-text-muted">&nbsp; &darr;</div>
            <div className="text-text-muted">Compressed context assembled</div>
          </div>
          <p className="mt-3 text-sm text-text-muted">
            The extractor uses CoDRAG&apos;s pre-computed trace graph (symbol spans, class hierarchy,
            import edges) to know exactly where functions start and end &mdash; no re-parsing needed
            at query time.
          </p>
        </section>

        {/* Usage */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">Usage</h2>

          <h3 className="mt-6 text-lg font-medium">Via Dashboard</h3>
          <p className="mt-2 text-sm text-text-muted">
            In the <strong>Context Options</strong> panel, select <strong>LOD (Structural)</strong> from
            the Compression dropdown. Click &ldquo;Assemble&rdquo; &mdash; each source citation will
            show an <code>LOD&#123;n&#125;</code> badge and compression ratio.
          </p>

          <h3 className="mt-6 text-lg font-medium">Via API</h3>
          <p className="mt-2 text-sm text-text-muted">
            Add <code>compression</code> and <code>structured</code> to your context request:
          </p>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div>curl -X POST http://localhost:4966/projects/my-project/context \</div>
            <div>&nbsp; -H &quot;Content-Type: application/json&quot; \</div>
            <div>&nbsp; -d &apos;{'{'}</div>
            <div>&nbsp;&nbsp;&nbsp; &quot;query&quot;: &quot;How does authentication work?&quot;,</div>
            <div>&nbsp;&nbsp;&nbsp; &quot;k&quot;: 10,</div>
            <div>&nbsp;&nbsp;&nbsp; &quot;max_chars&quot;: 12000,</div>
            <div>&nbsp;&nbsp;&nbsp; &quot;structured&quot;: true,</div>
            <div>&nbsp;&nbsp;&nbsp; &quot;compression&quot;: &quot;lod&quot;</div>
            <div>&nbsp; {'}'}&apos;</div>
          </div>

          <h3 className="mt-6 text-lg font-medium">Via MCP (Cursor / Windsurf)</h3>
          <p className="mt-2 text-sm text-text-muted">
            The <code>codrag_context</code> tool accepts compression parameters:
          </p>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div>{'{'}</div>
            <div>&nbsp; &quot;query&quot;: &quot;How does authentication work?&quot;,</div>
            <div>&nbsp; &quot;compression&quot;: &quot;lod&quot;</div>
            <div>{'}'}</div>
          </div>
        </section>

        {/* Response metadata */}
        <section className="mt-10">
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
      "compression_ratio": 3.21
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

        {/* Languages */}
        <section className="mt-10">
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
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">Fallback behaviour</h2>
          <p className="mt-3 text-text-muted leading-relaxed">
            Compression is <strong>best-effort</strong>. If the trace graph doesn&apos;t have symbol
            data for a file (e.g., the file was added after the last build), CoDRAG falls back to
            LOD 0 and returns the full source. The <code>fallback</code> field in the chunk metadata
            will be <code>true</code>.
          </p>
          <div className="mt-4 rounded-lg border border-blue-500/20 bg-blue-500/5 p-4 text-sm text-text-muted">
            <strong className="text-blue-600">Tip:</strong> Keep your index up to date (enable the
            file watcher or rebuild regularly) for the best compression results.
          </div>
        </section>

        <hr className="my-10 border-border" />

        {/* Language compression section */}
        <section>
          <h2 className="text-2xl font-semibold">Language Compression &mdash; for Documentation</h2>
          <p className="mt-3 text-text-muted leading-relaxed">
            For markdown, text, and other natural language files, CoDRAG uses a lightweight
            BERT-based language model (LLMLingua-2, ~178 MB) that identifies and removes
            low-importance tokens while preserving the meaning, facts, and file references
            in your documentation.
          </p>
          <ul className="mt-4 space-y-2 text-sm text-text-muted list-disc pl-5">
            <li>89% concept retention &mdash; key ideas survive compression</li>
            <li>~1.6&times; compression at &ldquo;light&rdquo; level (configurable to 2.5&times; or 3.9&times; for more aggressive compression)</li>
            <li>~200ms per chunk on CPU &mdash; no GPU needed</li>
            <li>Model downloads automatically on first use (~178 MB)</li>
            <li>File paths and code references are protected from removal</li>
          </ul>
          <div className="mt-4 rounded-lg border border-blue-500/20 bg-blue-500/5 p-4 text-sm text-text-muted">
            <strong className="text-blue-600">Why two engines?</strong> Code has rigid structure (functions, classes, imports)
            that can be compressed by understanding that structure. Documentation is free-form natural language &mdash;
            compressing it requires understanding which <em>words</em> matter, not which <em>blocks</em> matter.
            Using the right tool for each type gives better results than a one-size-fits-all approach.
          </div>
        </section>

        {/* Comparison */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">Comparison: Structural vs. Language Compression</h2>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="py-2 pr-4 font-medium">&nbsp;</th>
                  <th className="py-2 pr-4 font-medium">Structural (LOD)</th>
                  <th className="py-2 font-medium">Language (LLMLingua-2)</th>
                </tr>
              </thead>
              <tbody className="text-text-muted">
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-medium text-text">Approach</td>
                  <td className="py-2 pr-4">Structural &mdash; keeps signatures, removes bodies</td>
                  <td className="py-2">Statistical &mdash; removes low-importance tokens</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-medium text-text">Dependencies</td>
                  <td className="py-2 pr-4">None (built into engine)</td>
                  <td className="py-2">BERT model (~178 MB, auto-downloaded)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-medium text-text">GPU required</td>
                  <td className="py-2 pr-4">No</td>
                  <td className="py-2">No (CPU inference)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-medium text-text">Best for</td>
                  <td className="py-2 pr-4">Code files (.py, .ts, .rs, etc.)</td>
                  <td className="py-2">Documentation &amp; markdown (.md, .txt, .rst)</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-medium text-text">Compression</td>
                  <td className="py-2 pr-4">3&ndash;20&times;</td>
                  <td className="py-2">1.6&ndash;3.9&times;</td>
                </tr>
                <tr className="border-b border-border/50">
                  <td className="py-2 pr-4 font-medium text-text">Concept retention</td>
                  <td className="py-2 pr-4">100% (structure preserved)</td>
                  <td className="py-2">89% at light, 79% at standard</td>
                </tr>
                <tr>
                  <td className="py-2 pr-4 font-medium text-text">Latency</td>
                  <td className="py-2 pr-4">&lt;10ms per file</td>
                  <td className="py-2">~200ms per chunk</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-sm text-text-muted">
            With <code>compression: &quot;auto&quot;</code> (the default when compression is enabled),
            CoDRAG automatically routes each chunk to the right engine based on file type.
          </p>
        </section>
      </div>
    </main>
  );
}
