import { AnchorHeading } from '../../../components/AnchorHeading';
import { DemoFolderTreePathWeights } from '../../../components/demos';

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto max-w-3xl px-6 pb-16 pt-0">
        <a href="/" className="text-sm text-text-muted">
          ← Back to Docs
        </a>

        <h1 className="mt-6 text-3xl font-bold tracking-tight">Path Weights</h1>
        <p className="mt-4 text-lg text-text-muted">
          Boost or suppress specific files and folders in search results without rebuilding your index.
        </p>

        {/* What are path weights */}
        <section className="mt-10">
          <AnchorHeading id="what-are-path-weights" level="h2">What are path weights?</AnchorHeading>
          <p className="mt-3 text-text-muted leading-relaxed">
            Path weights are multipliers applied to search scores at query time. A weight of{' '}
            <code>1.5</code> boosts a folder&apos;s chunks by 50%. A weight of <code>0.0</code>{' '}
            effectively excludes it. The default weight is <code>1.0</code> (no change).
          </p>
          <ul className="mt-4 space-y-2 text-sm text-text-muted list-disc pl-5">
            <li>Applied at search time — no rebuild required</li>
            <li>Hierarchical — a folder weight applies to all files inside it</li>
            <li>Most-specific wins — a file weight overrides its parent folder weight</li>
            <li>Range: <code>0.0</code> to <code>2.0</code></li>
          </ul>
        </section>

        {/* How it works */}
        <section className="mt-10">
          <AnchorHeading id="how-it-works" level="h2">How it works</AnchorHeading>
          <div className="mt-4 rounded-lg bg-surface border border-border p-6 text-sm">
            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <span className="shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">1</span>
                <div>
                  <div className="font-medium text-text">Set weights on folders or files</div>
                  <div className="mt-1 text-text-muted">Via the dashboard Knowledge Scope panel or the API.</div>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <span className="shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">2</span>
                <div>
                  <div className="font-medium text-text">SourcePrep resolves the most-specific weight</div>
                  <div className="mt-1 text-text-muted">
                    For <code>src/auth/login.py</code>, SourcePrep checks: <code>src/auth/login.py</code> → <code>src/auth/</code> → <code>src/</code> → default (1.0).
                  </div>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <span className="shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">3</span>
                <div>
                  <div className="font-medium text-text">Weight is applied as a multiplier to the similarity score</div>
                  <div className="mt-1 text-text-muted">
                    <code>final_score = base_score × role_weight × path_weight</code>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Dashboard usage */}
        <section className="mt-10">
          <AnchorHeading id="using-the-dashboard" level="h2">Using the dashboard</AnchorHeading>
          <p className="mt-3 text-text-muted leading-relaxed">
            In the project&apos;s <span className="font-semibold text-text">Knowledge Scope</span> panel,
            each file and folder shows its current weight as a small{' '}
            <code>×N.N</code> control on the right side of the row. Click any weight to edit it
            inline.
          </p>

          <div className="not-prose">
            <DemoFolderTreePathWeights />
            <p className="text-xs text-text-subtle italic -mt-4">
              Path-weight controls. <code>src/core</code> is boosted (×1.5), <code>src/utils</code> and <code>tests</code> are suppressed (×0.7 and ×0.3), <code>docs/README.md</code> is boosted (×1.8). Child files show inherited weights in italic.
            </p>
          </div>

          <p className="mt-4 text-text-muted leading-relaxed">
            Visual cues on the <code>×N.N</code> control:
          </p>
          <ul className="mt-2 space-y-2 text-sm text-text-muted list-disc pl-5">
            <li><span className="font-mono text-success bg-success/10 px-1.5 py-0.5 rounded">×1.5</span> — green tint means a boost ({'>'} 1.0).</li>
            <li><span className="font-mono text-warning bg-warning/10 px-1.5 py-0.5 rounded">×0.5</span> — amber tint means a suppression ({'<'} 1.0).</li>
            <li><span className="font-mono text-text-subtle/40 px-1.5 py-0.5">×1.0</span> — faded means default (no override on this path).</li>
            <li><em>italic</em> — the weight is inherited from a parent folder, not explicitly set on this row.</li>
          </ul>
          <p className="mt-3 text-sm text-text-muted">
            The colored dots/circles you may see elsewhere on the row are <strong>indexing
            status</strong> indicators (indexed, pending, ignored), not weight indicators —
            different concept.
          </p>
          <p className="mt-3 text-sm text-text-muted">
            Changes take effect immediately on the next search — no rebuild needed.
          </p>
        </section>

        {/* API usage */}
        <section className="mt-10">
          <h2 className="text-2xl font-semibold">API usage</h2>

          <h3 className="mt-6 text-lg font-medium text-text">Set weights</h3>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div>curl -X PUT http://localhost:8400/projects/my-project/path_weights \</div>
            <div>  -H &quot;Content-Type: application/json&quot; \</div>
            <div>  -d &apos;{'{'}</div>
            <div>    &quot;path_weights&quot;: {'{'}</div>
            <div>      &quot;src/core/&quot;: 1.5,</div>
            <div>      &quot;src/tests/&quot;: 0.3,</div>
            <div>      &quot;vendor/&quot;: 0.0,</div>
            <div>      &quot;README.md&quot;: 1.8</div>
            <div>    {'}'}</div>
            <div>  {'}'}&apos;</div>
          </div>

          <h3 className="mt-6 text-lg font-medium text-text">Get weights</h3>
          <div className="mt-2 rounded-lg bg-surface border border-border p-4 font-mono text-sm overflow-x-auto">
            <div>curl http://localhost:8400/projects/my-project/path_weights</div>
          </div>
        </section>

        {/* Examples */}
        <section className="mt-10">
          <AnchorHeading id="common-patterns" level="h2">Common patterns</AnchorHeading>
          <div className="mt-4 space-y-4">
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-medium text-sm">Focus on core business logic</div>
              <div className="mt-2 font-mono text-xs text-text-muted">
                <div>&quot;src/core/&quot;: 1.5, &quot;src/utils/&quot;: 0.8, &quot;tests/&quot;: 0.3</div>
              </div>
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-medium text-sm">Exclude vendored / generated code</div>
              <div className="mt-2 font-mono text-xs text-text-muted">
                <div>&quot;vendor/&quot;: 0.0, &quot;generated/&quot;: 0.0, &quot;node_modules/&quot;: 0.0</div>
              </div>
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-medium text-sm">Boost documentation for onboarding queries</div>
              <div className="mt-2 font-mono text-xs text-text-muted">
                <div>&quot;docs/&quot;: 1.8, &quot;README.md&quot;: 2.0, &quot;CONTRIBUTING.md&quot;: 1.5</div>
              </div>
            </div>
          </div>
        </section>

        {/* API Reference */}
        <section className="mt-10">
          <AnchorHeading id="api-reference" level="h2">API reference</AnchorHeading>
          <div className="mt-4 space-y-4">
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-mono text-sm font-medium text-text">PUT /projects/{'{id}'}/path_weights</div>
              <p className="mt-1 text-sm text-text-muted">
                Set path weights. Body: <code>{`{ "path_weights": { "path": weight } }`}</code>.
                Weights are clamped to 0.0–2.0 and persisted to <code>repo_policy.json</code>.
              </p>
            </div>
            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="font-mono text-sm font-medium text-text">GET /projects/{'{id}'}/path_weights</div>
              <p className="mt-1 text-sm text-text-muted">
                Returns the current path weights for the project.
              </p>
            </div>
          </div>
        </section>

        <hr className="my-12 border-border" />

        {/* Project Scope UI */}
        <section className="mt-10">
          <AnchorHeading id="project-scope" level="h2">Project Scope & Patterns</AnchorHeading>
          <p className="mt-3 text-text-muted leading-relaxed">
            While path weights control ranking, the <span className="font-semibold text-text">Project Settings</span> panel controls <em>what</em> gets indexed in the first place. This is the coarse-grained filter before weights are applied.
          </p>

          <div className="mt-8 grid gap-6 md:grid-cols-2">
            <div className="rounded-lg border border-border bg-surface p-6">
              <h4 className="font-semibold text-text mb-2 flex items-center gap-2">
                Include Patterns
              </h4>
              <p className="text-sm text-text-muted mb-4">
                Glob patterns that define the allowed set of files. Think of this as an allowlist.
              </p>
              <ul className="space-y-2 text-sm text-text-muted list-disc pl-4">
                <li><code>**/*.py</code> - All Python files</li>
                <li><code>src/**/*</code> - Everything in src</li>
                <li><code>docs/*.md</code> - Root docs only</li>
              </ul>
              <div className="mt-4 p-3 bg-surface-raised rounded text-xs text-text-subtle">
                <span className="font-semibold text-text">Presets:</span> Click the "Presets" button to auto-populate standard patterns for stacks like Next.js, Python, or Rust.
              </div>
            </div>

            <div className="rounded-lg border border-border bg-surface p-6">
              <h4 className="font-semibold text-text mb-2 flex items-center gap-2">
                Exclude Patterns
              </h4>
              <p className="text-sm text-text-muted mb-4">
                Glob patterns for files to strictly ignore, even if they match an include pattern.
              </p>
              <ul className="space-y-2 text-sm text-text-muted list-disc pl-4">
                <li><code>**/node_modules/**</code> - Dependencies</li>
                <li><code>**/dist/**</code> - Build artifacts</li>
                <li><code>**/*.test.ts</code> - Tests (optional)</li>
              </ul>
              <div className="mt-4 flex items-center gap-2 text-xs text-text-subtle">
                <span className="w-2 h-2 rounded-full bg-primary"></span>
                SourcePrep also respects your <code>.gitignore</code> automatically.
              </div>
            </div>
          </div>

          <div className="mt-6 p-4 rounded-lg border border-info/20 bg-info/5 text-sm text-info-text">
            <span className="font-semibold text-text">Pro Tip:</span> Use the <span className="font-semibold text-text">Auto-Detect Stack</span> button in the dashboard to scan your repository structure and automatically configure optimal Include/Exclude patterns for your language and framework.
          </div>
        </section>
      </div>
    </main>
  );
}
